// Farmer <-> expert chat (moved out of main.dart). Same look; adds reply-to for text and voice notes.
import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:url_launcher/url_launcher.dart';
import 'main.dart' show t, kApiBase;
import 'offline_cache.dart';
import 'theme.dart';

class ExpertChatPage extends StatefulWidget {
  final String lang, deviceId, expertId, expertName, expertRole;
  final String? phone;
  const ExpertChatPage({
    super.key,
    required this.lang,
    required this.deviceId,
    required this.expertId,
    required this.expertName,
    required this.expertRole,
    this.phone,
  });
  @override
  State<ExpertChatPage> createState() => _ExpertChatPageState();
}

class _ExpertChatPageState extends State<ExpertChatPage> {
  final _ctrl = TextEditingController();
  final _recorder = AudioRecorder();
  final _player = AudioPlayer();
  List messages = [];
  bool loading = true, _recording = false, _voiceBusy = false;
  String? _recordPath;
  Timer? _poll;
  Map? _replyTo; // the message or voice note being answered

  @override
  void initState() {
    super.initState();
    refresh();
    _poll = Timer.periodic(const Duration(seconds: 3), (_) => refresh(silent: true));
  }

  @override
  void dispose() {
    _poll?.cancel();
    _ctrl.dispose();
    _recorder.dispose();
    _player.dispose();
    super.dispose();
  }

  // ------------------------------------------------------------- reply-to helpers
  bool _isVoice(Map m) {
    final text = '${m['text'] ?? ''}';
    return m['type'] == 'audio_note' || text.contains('[voice_note:') || text.contains('[Voice note]');
  }

  /// Server id when known; otherwise the client id (the server resolves either).
  String _replyKey(Map m) {
    final id = '${m['id'] ?? ''}';
    return id.startsWith('local-') ? '${m['client_id'] ?? id}' : id;
  }

  Map<String, dynamic> _previewOf(Map m) {
    final voice = _isVoice(m);
    final text = '${m['text'] ?? ''}';
    return {'id': m['id'], 'sender': m['sender'], 'type': voice ? 'audio_note' : (m['type'] ?? 'text'), 'text': voice ? '' : (text.length > 140 ? text.substring(0, 140) : text)};
  }

  void _setReply(Map m) => setState(() => _replyTo = Map.from(m));

  Widget _quote(Map q) {
    final voice = q['type'] == 'audio_note';
    final who = q['sender'] == 'farmer' ? t(widget.lang, 'you') : widget.expertName;
    return Container(
      margin: const EdgeInsets.only(bottom: 6),
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
      decoration: BoxDecoration(
        color: Colors.black.withValues(alpha: 0.05),
        borderRadius: BorderRadius.circular(8),
        border: const Border(left: BorderSide(color: C.greenDark, width: 3)),
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(who, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: C.greenDark)),
        Row(mainAxisSize: MainAxisSize.min, children: [
          if (voice) const Icon(Icons.mic, size: 13),
          if (voice) const SizedBox(width: 4),
          Flexible(child: Text(voice ? t(widget.lang, 'voiceNote') : '${q['text'] ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12))),
        ]),
      ]),
    );
  }

  // ------------------------------------------------------------- voice playback
  Future<void> _playVoiceNote(Map m) async {
    try {
      await _player.stop();
      final local = '${m['local_path'] ?? ''}';
      if (local.isNotEmpty) {
        final f = File(local);
        if (await f.exists() && await f.length() > 200) {
          await _player.play(DeviceFileSource(local));
          return;
        }
      }
      final name = RegExp(r'\[voice_note:([^\]]+)\]').firstMatch('${m['text'] ?? ''}')?.group(1);
      if (name == null || name.isEmpty) {
        _snack('No audio on this bubble');
        return;
      }
      final prefs = await SharedPreferences.getInstance();
      final mapped = prefs.getString('voice_local_$name') ?? '';
      if (mapped.isNotEmpty && await File(mapped).exists()) {
        await _player.play(DeviceFileSource(mapped));
        return;
      }
      final dir = await getApplicationDocumentsDirectory();
      final cache = File('${dir.path}/masomlimi_offline/voice_cache/$name');
      if (await cache.exists() && await cache.length() > 200) {
        await _player.play(DeviceFileSource(cache.path));
        return;
      }
      await cache.parent.create(recursive: true);
      final res = await http.get(Uri.parse('$kApiBase/v1/chat/voice/$name')).timeout(const Duration(seconds: 25));
      if (res.statusCode == 200 && res.bodyBytes.length > 200) {
        await cache.writeAsBytes(res.bodyBytes);
        await prefs.setString('voice_local_$name', cache.path);
        await _player.play(DeviceFileSource(cache.path));
        return;
      }
      throw Exception('Server ${res.statusCode}');
    } catch (e) {
      _snack('Cannot play: $e');
    }
  }

  void _snack(String s) {
    if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(s)));
  }

  // ------------------------------------------------------------- recording
  Future<void> _toggleVoice() async => _recording ? _stopAndSendVoice() : _startVoice();

  Future<void> _startVoice() async {
    try {
      if (await _recorder.isRecording()) await _recorder.stop();
      if (!await _recorder.hasPermission()) {
        _snack('Allow microphone in Android settings for MasoMlimi');
        return;
      }
      final dir = await getApplicationDocumentsDirectory();
      final voiceDir = Directory('${dir.path}/masomlimi_offline/voice_notes');
      if (!await voiceDir.exists()) await voiceDir.create(recursive: true);
      _recordPath = '${voiceDir.path}/vn_${DateTime.now().millisecondsSinceEpoch}.m4a';
      try {
        await _recorder.start(const RecordConfig(encoder: AudioEncoder.aacLc, numChannels: 1, bitRate: 128000, sampleRate: 44100), path: _recordPath!);
      } catch (_) {
        _recordPath = '${voiceDir.path}/vn_${DateTime.now().millisecondsSinceEpoch}.wav';
        await _recorder.start(const RecordConfig(encoder: AudioEncoder.wav, numChannels: 1, sampleRate: 16000), path: _recordPath!);
      }
      if (mounted) setState(() => _recording = true);
    } catch (e) {
      if (mounted) setState(() => _recording = false);
      _snack('Could not start mic: $e');
    }
  }

  Future<void> _stopAndSendVoice() async {
    try {
      String? filePath;
      try {
        filePath = await _recorder.stop();
      } catch (_) {}
      filePath = filePath ?? _recordPath;
      if (mounted) setState(() => _recording = false);
      if (filePath == null || filePath.isEmpty) return _snack('No audio captured - try again');
      final f = File(filePath);
      if (!await f.exists() || await f.length() < 800) return _snack('No voice captured - speak longer');
      await _sendVoiceFile(filePath);
    } catch (e) {
      if (mounted) setState(() => _recording = false);
      _snack('Voice error: $e');
    }
  }

  Future<void> _sendVoiceFile(String filePath) async {
    if (_voiceBusy) return;
    _voiceBusy = true;
    final reply = _replyTo;
    final cid = 'vn-${DateTime.now().millisecondsSinceEpoch}';
    try {
      final box = await OfflineCache.loadOutbox();
      await OfflineCache.saveOutbox(box.where((o) => !(o is Map && '${o['type']}' == 'audio_note' && '${o['file_path']}' == filePath)).toList());
      await OfflineCache.enqueueOutbox({
        'type': 'audio_note',
        'device_id': widget.deviceId,
        'expert_id': widget.expertId,
        'file_path': filePath,
        'msg_type': 'audio_note',
        'text': '[Voice note]',
        'client_id': cid,
        if (reply != null) 'reply_to': _replyKey(reply),
      });
      if (mounted) setState(() => _replyTo = null);
      try {
        if (await OfflineCache.flushOutbox(kApiBase) > 0) {
          await refresh(silent: true);
          _snack('Voice note sent');
          return;
        }
      } catch (_) {}
      final localMsg = {
        'id': 'local-vn-${DateTime.now().millisecondsSinceEpoch}',
        'client_id': cid,
        'sender': 'farmer',
        'type': 'audio_note',
        'text': '[Voice note]',
        'at': DateTime.now().toIso8601String(),
        'pending_sync': true,
        'local_path': filePath,
        if (reply != null) 'reply_to': _replyKey(reply),
        if (reply != null) 'reply_preview': _previewOf(reply),
      };
      await OfflineCache.appendOutgoingChat(widget.deviceId, widget.expertId, localMsg);
      if (mounted) setState(() => messages = OfflineCache.dedupeMessages([...messages, localMsg]));
      _snack('Voice saved offline - will sync when online');
    } finally {
      _voiceBusy = false;
    }
  }

  // ------------------------------------------------------------- sync + send
  Future<void> refresh({bool silent = false}) async {
    try {
      await OfflineCache.flushOutbox(kApiBase);
    } catch (_) {}
    List server = [];
    var onlineOk = false;
    try {
      final res = await http.get(Uri.parse('$kApiBase/v1/chat/${widget.deviceId}/${widget.expertId}')).timeout(const Duration(seconds: 6));
      if (res.statusCode == 200) {
        server = (jsonDecode(utf8.decode(res.bodyBytes))['messages'] as List?) ?? [];
        onlineOk = true;
      }
    } catch (_) {}
    final local = await OfflineCache.loadChat(widget.deviceId, widget.expertId);
    final outbox = await OfflineCache.loadOutbox();
    bool stillQueued(Map m) {
      for (final o in outbox) {
        if (o is! Map) continue;
        final cid = '${m['client_id'] ?? ''}';
        if (cid.isNotEmpty && '${o['client_id']}' == cid) return true;
      }
      return false;
    }

    List merged;
    if (onlineOk) {
      merged = List.from(server);
      for (final p in local) {
        if (p is! Map || p['pending_sync'] != true || !stillQueued(p)) continue;
        final cid = '${p['client_id'] ?? ''}';
        if (cid.isNotEmpty && server.any((s) => s is Map && '${s['client_id']}' == cid)) continue;
        merged.add(p);
      }
      await OfflineCache.saveChat(widget.deviceId, widget.expertId, merged);
    } else {
      merged = local.isNotEmpty ? local : server;
    }
    merged = OfflineCache.dedupeMessages(merged);
    if (!mounted) return;
    setState(() {
      messages = merged;
      loading = false;
    });
  }

  Future<void> send({String type = 'text', String? text}) async {
    final body = text ?? _ctrl.text.trim();
    if (body.isEmpty) return;
    final reply = _replyTo;
    final cid = 'tx-${DateTime.now().millisecondsSinceEpoch}';
    final localMsg = {
      'id': 'local-${DateTime.now().millisecondsSinceEpoch}',
      'client_id': cid,
      'sender': 'farmer',
      'type': type,
      'text': body,
      'at': DateTime.now().toIso8601String(),
      'pending_sync': true,
      if (reply != null) 'reply_to': _replyKey(reply),
      if (reply != null) 'reply_preview': _previewOf(reply),
    };
    await OfflineCache.enqueueOutbox({
      'type': 'text',
      'device_id': widget.deviceId,
      'expert_id': widget.expertId,
      'text': body,
      'msg_type': type,
      'client_id': cid,
      if (reply != null) 'reply_to': _replyKey(reply),
    });
    _ctrl.clear();
    if (mounted) setState(() => _replyTo = null);
    try {
      if (await OfflineCache.flushOutbox(kApiBase) > 0) {
        await refresh();
        return;
      }
    } catch (_) {}
    await OfflineCache.appendOutgoingChat(widget.deviceId, widget.expertId, localMsg);
    if (mounted) {
      setState(() => messages = OfflineCache.dedupeMessages([...messages, localMsg]));
      _snack('Saved offline. Will sync when online.');
    }
  }

  // ------------------------------------------------------------- UI
  @override
  Widget build(BuildContext context) {
    final shown = OfflineCache.dedupeMessages(messages);
    return Scaffold(
      appBar: AppBar(
        title: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(widget.expertName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w800)),
          Text(widget.expertRole, style: const TextStyle(fontSize: 12, color: C.muted, fontWeight: FontWeight.w400)),
        ]),
        actions: [
          IconButton(
            tooltip: t(widget.lang, 'voiceCall'),
            icon: const Icon(Icons.call),
            onPressed: () {
              if (widget.phone != null && widget.phone!.isNotEmpty) {
                launchUrl(Uri.parse('tel:${widget.phone}'));
              } else {
                send(text: 'Farmer requested a voice call');
                _snack('Request sent in chat. The officer will call back.');
              }
            },
          ),
          IconButton(
            tooltip: t(widget.lang, 'videoCall'),
            icon: const Icon(Icons.videocam_outlined),
            onPressed: () {
              send(type: 'video_request', text: 'Farmer requested a video call');
              showDialog(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: Text(t(widget.lang, 'videoCall')),
                  content: const Text('A video request was sent. For this pilot the officer can reply in chat or call you.'),
                  actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('OK'))],
                ),
              );
            },
          ),
        ],
      ),
      body: Column(children: [
        Expanded(
          child: loading
              ? const Center(child: CircularProgressIndicator())
              : shown.isEmpty
                  ? Center(child: Text(t(widget.lang, 'noMessages'), textAlign: TextAlign.center))
                  : ListView.builder(
                      padding: const EdgeInsets.all(12),
                      itemCount: shown.length,
                      itemBuilder: (_, i) {
                        final m = shown[i] as Map;
                        final mine = m['sender'] == 'farmer';
                        final voice = _isVoice(m);
                        return Align(
                          alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
                          child: GestureDetector(
                            onLongPress: () => _setReply(m),
                            onHorizontalDragEnd: (d) {
                              if ((d.primaryVelocity ?? 0) > 150) _setReply(m);
                            },
                            child: Container(
                              margin: const EdgeInsets.symmetric(vertical: 4),
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
                              constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.78),
                              decoration: BoxDecoration(color: mine ? C.greenSoft : Colors.white, borderRadius: BorderRadius.circular(14), border: Border.all(color: C.border)),
                              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                if (m['reply_preview'] is Map) _quote(m['reply_preview'] as Map),
                                if (voice) ...[
                                  Row(children: [const Icon(Icons.mic, size: 16), const SizedBox(width: 6), Text(t(widget.lang, 'voiceNote'), style: const TextStyle(fontWeight: FontWeight.w700))]),
                                  TextButton.icon(onPressed: () => _playVoiceNote(Map<String, dynamic>.from(m)), icon: const Icon(Icons.play_arrow, size: 18), label: Text(t(widget.lang, 'play'))),
                                ] else if (m['type'] == 'video_request')
                                  Row(children: [const Icon(Icons.videocam, size: 16), const SizedBox(width: 6), Text(t(widget.lang, 'videoRequest'), style: const TextStyle(fontWeight: FontWeight.w700))])
                                else
                                  Text('${m['text'] ?? ''}', style: const TextStyle(height: 1.3)),
                                Align(
                                  alignment: Alignment.centerRight,
                                  child: InkWell(
                                    onTap: () => _setReply(m),
                                    child: Padding(padding: const EdgeInsets.only(top: 4), child: Text(t(widget.lang, 'reply'), style: const TextStyle(fontSize: 11, color: C.greenDark, fontWeight: FontWeight.w700))),
                                  ),
                                ),
                              ]),
                            ),
                          ),
                        );
                      },
                    ),
        ),
        if (_recording)
          Container(width: double.infinity, padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16), color: Colors.red.shade50, child: Text(t(widget.lang, 'recording'), style: const TextStyle(color: Colors.red, fontWeight: FontWeight.w700))),
        if (_replyTo != null)
          Container(
            width: double.infinity,
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(12, 6, 4, 6),
            child: Row(children: [
              Expanded(child: _quote(_previewOf(_replyTo!))),
              IconButton(icon: const Icon(Icons.close), onPressed: () => setState(() => _replyTo = null)),
            ]),
          ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(10, 6, 10, 10),
            child: Row(children: [
              IconButton(icon: Icon(_recording ? Icons.stop_circle : Icons.mic, color: _recording ? Colors.red : C.greenDark, size: 30), onPressed: _toggleVoice),
              Expanded(
                child: TextField(
                  controller: _ctrl,
                  maxLength: 2000,
                  buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                  decoration: InputDecoration(
                    hintText: t(widget.lang, 'message'),
                    filled: true,
                    fillColor: Colors.white,
                    border: OutlineInputBorder(borderRadius: BorderRadius.circular(24), borderSide: BorderSide.none),
                    contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  ),
                  onSubmitted: (_) => send(),
                ),
              ),
              const SizedBox(width: 6),
              IconButton.filled(onPressed: () => send(), icon: const Icon(Icons.send)),
            ]),
          ),
        ),
      ]),
    );
  }
}
