// File-backed offline store. Moved out of main.dart.
// Fixes vs the old version:
//  * procedures/library/alerts are REPLACED by what the server says is published, even when that list is empty,
//    so retired or unpublished guidance disappears from phones (it used to stay forever).
//  * outbox sends client_id + reply_to so retries are idempotent and replies keep their link.
//  * dedupe never collapses two different replies that happen to share text.
import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'main.dart' show normalizeHost;

class OfflineCache {
  static Future<Directory> _dir() async {
    final root = await getApplicationDocumentsDirectory();
    final d = Directory('${root.path}/masomlimi_offline');
    if (!await d.exists()) await d.create(recursive: true);
    return d;
  }

  static Future<File> _file(String name) async => File('${(await _dir()).path}/$name');

  static Future<void> _writeList(String name, List items, {bool allowEmpty = false}) async {
    if (items.isEmpty && !allowEmpty) return; // transient empties must not wipe good local data
    final f = await _file(name);
    await f.writeAsString(jsonEncode(items), flush: true);
    final p = await SharedPreferences.getInstance();
    await p.setString('at_$name', DateTime.now().toIso8601String());
  }

  static Future<List> _readList(String name) async {
    try {
      final f = await _file(name);
      if (!await f.exists()) return [];
      final data = jsonDecode(await f.readAsString());
      return data is List ? data : [];
    } catch (_) {
      return [];
    }
  }

  static Future<void> saveProcedures(List items) async => _writeList('procedures.json', items, allowEmpty: true);
  static Future<List> loadProcedures() async => _readList('procedures.json');
  static Future<void> saveLibrary(List items) async => _writeList('library.json', items, allowEmpty: true);
  static Future<List> loadLibrary() async => _readList('library.json');
  static Future<void> saveExperts(List items) async => _writeList('experts.json', items);
  static Future<List> loadExperts() async => _readList('experts.json');
  static Future<void> saveAlerts(List items) async => _writeList('alerts.json', items, allowEmpty: true);
  static Future<List> loadAlerts() async => _readList('alerts.json');
  static Future<void> saveScanHistory(List items) async => _writeList('scan_history.json', items);
  static Future<List> loadScanHistory() async => _readList('scan_history.json');

  static Future<void> appendScanEpisode(Map episode) async {
    final all = List.from(await loadScanHistory())..add(episode);
    await saveScanHistory(all.length > 200 ? all.sublist(all.length - 200) : all);
  }

  static Future<List> historyForHost(String deviceId, String hostKey) async {
    final hk = normalizeHost(hostKey);
    final all = await loadScanHistory();
    return all.where((e) {
      if (e is! Map) return false;
      if (deviceId.isNotEmpty && '${e['device_id']}' != deviceId) return false;
      return normalizeHost('${e['host_key']}') == hk;
    }).toList().reversed.toList();
  }

  // ---------------------------------------------------------------- chat
  static String _chatName(String deviceId, String expertId) => 'chat_${'${deviceId}_$expertId'.replaceAll(RegExp(r'[^a-zA-Z0-9_-]'), '_')}.json';

  static Future<void> saveChat(String deviceId, String expertId, List messages) async =>
      _writeList(_chatName(deviceId, expertId), dedupeMessages(messages));

  static Future<List> loadChat(String deviceId, String expertId) async => _sortMessages(await _readList(_chatName(deviceId, expertId)));

  static List _sortMessages(List messages) {
    final copy = List.from(messages);
    copy.sort((a, b) {
      final at = a is Map ? '${a['at'] ?? ''}' : '';
      final bt = b is Map ? '${b['at'] ?? ''}' : '';
      final c = at.compareTo(bt);
      return c != 0 ? c : '${a is Map ? a['id'] : ''}'.compareTo('${b is Map ? b['id'] : ''}');
    });
    return copy;
  }

  static Future<void> appendOutgoingChat(String deviceId, String expertId, Map msg) async {
    final list = await loadChat(deviceId, expertId);
    final id = '${msg['id'] ?? ''}';
    if (id.isNotEmpty) list.removeWhere((m) => m is Map && '${m['id']}' == id);
    list.add(msg);
    await saveChat(deviceId, expertId, list);
  }

  // ---------------------------------------------------------------- outbox
  static Future<List> loadOutbox() async => _readList('outbox.json');

  static Future<void> saveOutbox(List items) async {
    final f = await _file('outbox.json');
    await f.writeAsString(jsonEncode(items), flush: true);
  }

  static Future<void> enqueueOutbox(Map item) async {
    final box = await loadOutbox();
    item['queued_at'] = item['queued_at'] ?? DateTime.now().toIso8601String();
    box.add(item);
    box.sort((a, b) => ('${a is Map ? a['queued_at'] : ''}').compareTo('${b is Map ? b['queued_at'] : ''}'));
    await saveOutbox(box);
  }

  static bool _flushing = false;

  static Future<int> flushOutbox(String apiBase) async {
    if (_flushing) return 0;
    _flushing = true;
    try {
      final box = await loadOutbox();
      if (box.isEmpty) return 0;
      final remain = <dynamic>[];
      var sent = 0;
      for (final raw in box) {
        if (raw is! Map) continue;
        final item = Map<String, dynamic>.from(raw);
        try {
          final replyTo = '${item['reply_to'] ?? ''}';
          if ('${item['type']}' == 'audio_note' && item['file_path'] != null) {
            final path = '${item['file_path']}';
            final file = File(path);
            if (!await file.exists()) {
              remain.add(item);
              continue;
            }
            if (await file.length() < 500) {
              sent++; // drop empty recordings
              continue;
            }
            final req = http.MultipartRequest('POST', Uri.parse('$apiBase/v1/chat/voice'));
            req.fields['device_id'] = '${item['device_id']}';
            req.fields['expert_id'] = '${item['expert_id']}';
            req.fields['sender'] = 'farmer';
            req.fields['client_id'] = '${item['client_id'] ?? item['id'] ?? ''}';
            if (replyTo.isNotEmpty) req.fields['reply_to'] = replyTo;
            req.files.add(await http.MultipartFile.fromPath('audio', path, filename: path.split(Platform.pathSeparator).last));
            final streamed = await req.send().timeout(const Duration(seconds: 45));
            final body = await streamed.stream.bytesToString();
            if (streamed.statusCode >= 200 && streamed.statusCode < 300) {
              try {
                final m = RegExp(r'\[voice_note:([^\]]+)\]').firstMatch(body);
                if (m != null) {
                  final dir = await getApplicationDocumentsDirectory();
                  final cache = File('${dir.path}/masomlimi_offline/voice_cache/${m.group(1)}');
                  await cache.parent.create(recursive: true);
                  await file.copy(cache.path);
                  final prefs = await SharedPreferences.getInstance();
                  await prefs.setString('voice_local_${m.group(1)}', cache.path);
                }
              } catch (_) {}
              sent++;
              continue;
            }
            remain.add(item);
          } else {
            final res = await http
                .post(Uri.parse('$apiBase/v1/chat'),
                    headers: {'Content-Type': 'application/json'},
                    body: jsonEncode({
                      'device_id': item['device_id'],
                      'expert_id': item['expert_id'],
                      'text': item['text'],
                      'sender': 'farmer',
                      'msg_type': item['msg_type'] ?? 'text',
                      'client_id': item['client_id'] ?? item['id'],
                      if (replyTo.isNotEmpty) 'reply_to': replyTo,
                    }))
                .timeout(const Duration(seconds: 15));
            if (res.statusCode >= 200 && res.statusCode < 300) {
              sent++;
              continue;
            }
            // 4xx other than rate limit = will never succeed: drop instead of retrying forever
            if (res.statusCode >= 400 && res.statusCode < 500 && res.statusCode != 429) {
              sent++;
              continue;
            }
            remain.add(item);
          }
        } catch (_) {
          remain.add(item);
        }
      }
      await saveOutbox(remain);
      return sent;
    } finally {
      _flushing = false;
    }
  }

  // ---------------------------------------------------------------- packs
  static Future<Map<String, int>> packSummary() async => {
        'procedures': (await loadProcedures()).length,
        'library': (await loadLibrary()).length,
        'experts': (await loadExperts()).length,
        'alerts': (await loadAlerts()).length,
      };

  static Future<void> syncAll(String apiBase) async {
    try {
      await flushOutbox(apiBase);
    } catch (_) {}
    try {
      final pr = await http.get(Uri.parse('$apiBase/v1/procedures')).timeout(const Duration(seconds: 8));
      if (pr.statusCode == 200) {
        final data = jsonDecode(utf8.decode(pr.bodyBytes));
        final items = data is Map ? (data['items'] as List? ?? []) : [];
        await saveProcedures(items.where((p) => p is Map && '${p['status']}' == 'published').toList());
      }
    } catch (_) {}
    try {
      final lib = await http.get(Uri.parse('$apiBase/v1/library')).timeout(const Duration(seconds: 8));
      if (lib.statusCode == 200) {
        final data = jsonDecode(utf8.decode(lib.bodyBytes));
        await saveLibrary(data is Map ? (data['items'] as List? ?? []) : []);
      }
    } catch (_) {}
    try {
      final res = await http.get(Uri.parse('$apiBase/v1/experts/?district=all')).timeout(const Duration(seconds: 6));
      if (res.statusCode == 200) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        if (data is List && data.isNotEmpty) await saveExperts(data);
      }
    } catch (_) {}
    try {
      final a = await http.get(Uri.parse('$apiBase/v1/alerts?district=Lilongwe')).timeout(const Duration(seconds: 6));
      if (a.statusCode == 200) {
        final data = jsonDecode(utf8.decode(a.bodyBytes));
        await saveAlerts(data is Map ? (data['items'] as List? ?? []) : []);
      }
    } catch (_) {}
  }

  /// One bubble per logical message.
  static List dedupeMessages(List messages) {
    final sorted = _sortMessages(messages);
    final hasServerVoice = sorted.any((m) => m is Map && '${m['text']}'.contains('[voice_note:'));
    final filtered = <dynamic>[];
    for (final m in sorted) {
      if (m is! Map) continue;
      final id = '${m['id'] ?? ''}';
      final isLocalVoice = id.startsWith('local-') && ('${m['type']}' == 'audio_note' || '${m['text']}'.contains('[Voice note]'));
      if (hasServerVoice && isLocalVoice) continue;
      filtered.add(m);
    }
    final out = <dynamic>[];
    final seenIds = <String>{};
    final seenVoice = <String>{};
    final seenText = <String>{};
    for (final m in filtered) {
      if (m is! Map) continue;
      final id = '${m['id'] ?? ''}';
      if (id.isNotEmpty && !id.startsWith('local-')) {
        if (seenIds.contains(id)) continue;
        seenIds.add(id);
      }
      final text = '${m['text'] ?? ''}';
      final isVoice = '${m['type']}' == 'audio_note' || text.contains('[voice_note:') || text.contains('[Voice note]');
      if (isVoice) {
        var vkey = '${m['local_path'] ?? ''}';
        final match = RegExp(r'\[voice_note:([^\]]+)\]').firstMatch(text);
        if (match != null) vkey = match.group(1) ?? text;
        final cid = '${m['client_id'] ?? ''}';
        final at = DateTime.tryParse('${m['at'] ?? ''}') ?? DateTime.now();
        final bucket = '${m['sender']}|vn|${m['reply_to'] ?? ''}|${at.millisecondsSinceEpoch ~/ 120000}';
        if (cid.isNotEmpty && seenVoice.contains('cid:$cid')) continue;
        if (vkey.isNotEmpty && seenVoice.contains(vkey)) continue;
        if (seenVoice.contains(bucket)) continue;
        if (cid.isNotEmpty) seenVoice.add('cid:$cid');
        if (vkey.isNotEmpty) seenVoice.add(vkey);
        seenVoice.add(bucket);
        out.add(m);
        continue;
      }
      final tkey = '${m['sender']}|$text|${m['reply_to'] ?? ''}';
      if (text.isNotEmpty) {
        if (seenText.contains(tkey)) {
          if (id.startsWith('local-')) continue;
          final idx = out.indexWhere((x) => x is Map && '${x['sender']}|${x['text']}|${x['reply_to'] ?? ''}' == tkey && '${x['id']}'.startsWith('local-'));
          if (idx >= 0) out[idx] = m;
          continue;
        }
        seenText.add(tkey);
      }
      if (id.startsWith('local-') && id.isNotEmpty) {
        if (seenIds.contains(id)) continue;
        seenIds.add(id);
      }
      out.add(m);
    }
    return _sortMessages(out);
  }

  // ---------------------------------------------------------------- legacy offline result (ResultPage)
  static Map<String, dynamic>? matchPublished(List procs, String hostKey, List<String> symptomKeys) {
    final hk = normalizeHost(hostKey);
    final matches = procs.where((p) => p is Map && '${p['status']}' == 'published' && normalizeHost('${p['host_key']}') == hk).toList();
    if (matches.isEmpty) return null;
    int score(Map p) {
      final blob = '${p['title']} ${p['steps']} ${p['prevention_steps']}'.toLowerCase();
      var s = 0;
      for (final k in symptomKeys) {
        if (blob.contains(k.replaceAll('_', ' ')) || blob.contains(k)) s++;
      }
      return s;
    }
    matches.sort((a, b) => score(b as Map).compareTo(score(a as Map)));
    return Map<String, dynamic>.from(matches.first as Map);
  }

  static Map<String, dynamic> resultFromProcedure(Map p, String lang) {
    final title = p['title'];
    var name = 'Guidance';
    if (title is Map && title.isNotEmpty) name = '${title[lang] ?? title['en'] ?? title.values.first}';
    List pick(dynamic raw) {
      if (raw is Map) {
        final v = raw[lang] ?? raw['en'] ?? (raw.values.isNotEmpty ? raw.values.first : []);
        return v is List ? v : [];
      }
      return [];
    }
    return {
      'outcome': 'published_guidance',
      'result_color': 'green',
      'confidence_band': 'medium',
      'condition': {'id': p['id'], 'common_name': name, 'is_dangerous': false},
      'procedure_steps': pick(p['steps']).map((s) => {'type': 'published', 'text': '$s'}).toList(),
      'prevention_steps': pick(p['prevention_steps']).map((s) => {'type': 'prevention', 'text': '$s'}).toList(),
      'products': [],
      'messages': {'primary': name, 'published_note': 'From saved expert guidance (offline pack).', 'ask_expert_note': 'Ask a verified officer if unsure.'},
      'referral_required': false,
      'from_published_library': true,
      'from_offline_cache': true,
      'procedure_id': p['id'],
    };
  }
}
