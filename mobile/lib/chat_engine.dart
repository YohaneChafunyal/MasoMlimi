// MasoMlimi chat + scan engine (phone side).
// Online : POST /v1/knowledge/chat (text) or POST /v1/scan/analyze (photo + symptoms) -> server engine + shared memory.
// Offline: same rules on the signed "chat pack" (GET /v1/sync/chatpack): per-language views, vet-gated doses,
//          expert-approved local words, and k-anonymous "nearby" counts. Emergency rules are FIXED here.
import 'dart:convert';
import 'dart:io';
import 'dart:math';
import 'package:http/http.dart' as http;
import 'package:path_provider/path_provider.dart';

class ChatAnswer {
  final String text, outcome, band, bandLabel, caseId, fbQ, fbYes, fbNo;
  final bool emergency;
  final List<String> sources, images, quick, notices;
  const ChatAnswer({
    required this.text,
    this.outcome = 'answer',
    this.band = 'low',
    this.bandLabel = '',
    this.emergency = false,
    this.sources = const [],
    this.images = const [],
    this.quick = const [],
    this.notices = const [],
    this.caseId = '',
    this.fbQ = '',
    this.fbYes = '',
    this.fbNo = '',
  });

  factory ChatAnswer.fromServer(Map j, String apiBase) {
    List<String> strs(dynamic v) => v is List ? v.map((e) => '$e').toList() : <String>[];
    final conf = j['confidence'] is Map ? j['confidence'] as Map : {};
    final fb = j['feedback'] is Map ? j['feedback'] as Map : {};
    final imgs = <String>[];
    for (final im in (j['images'] as List? ?? [])) {
      if (im is Map) {
        var u = '${im['image_url'] ?? ''}';
        if (u.startsWith('/')) u = '$apiBase$u';
        if (u.isNotEmpty) imgs.add(u);
      }
    }
    return ChatAnswer(
      text: '${j['reply'] ?? ''}',
      outcome: '${j['outcome'] ?? 'answer'}',
      band: '${conf['band'] ?? 'low'}',
      bandLabel: '${conf['label'] ?? ''}',
      emergency: j['emergency'] == true,
      sources: strs(j['sources']),
      images: imgs,
      quick: strs(j['quick_replies']),
      notices: strs(j['notices']),
      caseId: '${j['case_id'] ?? ''}',
      fbQ: '${fb['question'] ?? ''}',
      fbYes: '${fb['yes'] ?? ''}',
      fbNo: '${fb['no'] ?? ''}',
    );
  }

  /// Bubble map for KnowledgeChatPage (_msgs is List<Map<String,String>>).
  Map<String, String> toBubble() => {
        'role': 'bot',
        'text': text,
        'band': band,
        'band_label': bandLabel,
        'emergency': emergency ? '1' : '',
        'sources': sources.join('\n'),
        'quick': quick.join('|'),
        if (images.isNotEmpty) 'image_url': images.first,
        if (caseId.isNotEmpty && outcome == 'answer') 'case_id': caseId,
        if (fbQ.isNotEmpty) 'fb_q': fbQ,
        if (fbYes.isNotEmpty) 'fb_yes': fbYes,
        if (fbNo.isNotEmpty) 'fb_no': fbNo,
      };
}

/// Result of "what is in this photo?". Always a SUGGESTION: the farmer confirms before any advice.
class HostGuess {
  final bool ok, confident;
  final String? suggested, mismatch; // mismatch: 'crop' | 'livestock' = the photo looks like the OTHER category
  final List<String> candidates; // best first (from the model)
  final List<String> choices; // everything the farmer can pick (hosts with published advice first)
  final Set<String> guided; // hosts that have published advice
  const HostGuess({this.ok = false, this.confident = false, this.suggested, this.mismatch, this.candidates = const [], this.choices = const [], this.guided = const {}});
}

class _Doc {
  final Map p;
  final Map<String, int> tf;
  final int len;
  final String host;
  final bool dangerous;
  _Doc(this.p, this.tf, this.len, this.host, this.dangerous);
  String get id => '${p['id']}';
}

class ChatEngine {
  static Map<String, dynamic>? _pack;
  static List<_Doc> _docs = [];
  static Map<String, double> _idf = {};
  static double _avgdl = 1;

  // ---- embedded fallback so emergency flows work before the first pack download ----
  static const _critical = {
    'en': ['Isolate the animal from other animals and people.', 'Do not handle more than necessary. Wear gloves if available.', 'Do not eat or sell meat, milk or eggs until a vet advises.', 'Keep children and other animals away.', 'Contact the nearest verified vet or district office immediately.'],
    'fr': ["Isolez l'animal des autres animaux et des personnes.", 'Ne manipulez pas plus que nécessaire. Portez des gants si possible.', "Ne mangez ni ne vendez viande, lait ou œufs tant qu'un vétérinaire n'a pas conseillé.", 'Éloignez les enfants et les autres animaux.', 'Contactez immédiatement le vétérinaire ou le bureau de district.'],
    'ny': ['Patulani chiweto kuchokera ku ziweto ndi anthu ena.', 'Osagwira kwambiri. Valani magolovesi ngati mulinawo.', 'Osadya kapena kugulitsa nyama, mkaka kapena mazira mpaka vet atanene.', 'Sungani ana ndi ziweto zina kutali.', 'Lumikizanani ndi vet kapena ofesi ya boma posachedwa.'],
    'sw': ['Tenganisha mnyama na wanyama na watu wengine.', 'Usishike zaidi ya inavyohitajika. Vaa glavu ikiwa zinapatikana.', 'Usile au uuze nyama, maziwa au mayai hadi daktari wa mifugo ashauri.', 'Weka watoto na wanyama wengine mbali.', 'Wasiliana na daktari wa mifugo au ofisi ya wilaya mara moja.'],
    'pt': ['Isole o animal de outros animais e pessoas.', 'Não manuseie mais do que o necessário. Use luvas se disponíveis.', 'Não coma nem venda carne, leite ou ovos até um veterinário aconselhar.', 'Mantenha crianças e outros animais afastados.', 'Contacte o veterinário ou o posto distrital imediatamente.'],
  };
  static const _emTitle = {
    'en': 'This may be a serious or reportable disease. Do not treat at home.',
    'ny': 'Ichi chikhoza kukhala matenda oopsa. Musachize kunyumba.',
    'fr': "Il peut s'agir d'une maladie grave ou à déclaration obligatoire. Ne traitez pas à la maison.",
    'sw': 'Huu unaweza kuwa ugonjwa mkubwa au wa kuripotiwa. Usitibu nyumbani.',
    'pt': 'Pode ser uma doença grave ou de notificação obrigatória. Não trate em casa.',
  };
  static const _emExpert = {
    'en': 'Contact the nearest verified vet or district office now.',
    'ny': 'Lumikizanani ndi vet kapena ofesi ya boma tsopano.',
    'fr': 'Contactez dès maintenant le vétérinaire ou le bureau de district le plus proche.',
    'sw': 'Wasiliana na daktari wa mifugo au ofisi ya wilaya sasa.',
    'pt': 'Contacte agora o veterinário ou o posto distrital mais próximo.',
  };
  static const _dangerTerms = ['anthrax', 'charbon', 'carbunculo', 'kimeta', 'foot and mouth', 'fmd', 'fievre aphteuse', 'febre aftosa', 'east coast fever', 'ndigana kali', 'newcastle', 'kideri', 'african swine fever', 'peste porcine africaine', 'peste suina africana', 'rift valley', 'homa ya bonde la ufa', 'rabies', 'rage', 'raiva', 'kichaa cha mbwa'];
  static const _dangerSigns = ['sudden death', 'sudden deaths', 'died suddenly', 'many died', 'many dead', 'bleeding', 'blood from', 'bloody', 'cannot stand', 'unable to stand', 'mort subite', 'meurent', 'saignement', 'sang', 'ne peut pas se lever', 'morte subita', 'morreram', 'sangramento', 'sangue', 'kifo cha ghafla', 'wamekufa wengi', 'damu', 'hawezi kusimama', 'kufa mwadzidzidzi', 'zambiri zafa', 'magazi', 'sangathe kuyimirira'];
  static const _dangerKeys = {'sudden_many_dead', 'bloody_discharge', 'cannot_stand', 'high_fever_group'};
  static const _livestock = {'chicken', 'goats', 'cattle', 'pigs', 'sheep', 'ducks'};
  static const _cropDefaults = ['maize', 'cassava', 'tomato', 'beans', 'groundnuts', 'rice', 'tobacco'];
  static const _livestockDefaults = ['chicken', 'goats', 'cattle', 'pigs', 'sheep', 'ducks'];
  static const _intentsDefault = {
    'greeting': ['hello', 'hi', 'hey', 'greetings', 'good morning', 'good afternoon', 'good evening', 'how are you', 'moni', 'muli bwanji', 'mwadzuka bwanji', 'mwaswera bwanji', 'madzulo abwino', 'odi', 'habari', 'hujambo', 'mambo', 'salamu', 'shikamoo', 'habari za asubuhi', 'habari za mchana', 'habari za jioni', 'bonjour', 'salut', 'bonsoir', 'coucou', 'ca va', 'comment allez vous', 'comment ca va', 'ola', 'oi', 'bom dia', 'boa tarde', 'boa noite', 'tudo bem', 'como esta', 'como vai'],
    'thanks': ['thanks', 'thank you', 'thank', 'zikomo', 'zikomo kwambiri', 'asante', 'asante sana', 'merci', 'merci beaucoup', 'obrigado', 'obrigada', 'muito obrigado', 'muito obrigada'],
    'bye': ['bye', 'goodbye', 'see you', 'tsalani bwino', 'pitani bwino', 'kwaheri', 'au revoir', 'a bientot', 'adeus', 'ate logo', 'tchau'],
    'about': ['who are you', 'what can you do', 'what do you do', 'how does this work', 'help', 'ndinu ndani', 'wewe ni nani', 'unaweza kufanya nini', 'qui es tu', 'qui etes vous', 'que pouvez vous faire', 'quem es tu', 'quem e voce', 'o que voce faz'],
    'okay': ['ok', 'okay', 'alright', 'sawa', 'chabwino', 'd accord', 'daccord'],
  };
  // used only before the first pack download; the pack carries all texts in all 5 languages
  static const _helloFallback = {
    'en': 'Hello! I am MasoMlimi, your farm helper. Tell me what you see on your plant or animal. I answer only from advice approved by experts.',
    'ny': 'Moni! Ndine MasoMlimi, wothandiza wanu pa munda. Ndiuzeni zomwe mukuona pa mbewu kapena chiweto chanu. Ndimayankha pogwiritsa ntchito uphungu wovomerezeka ndi akatswiri okha.',
    'fr': 'Bonjour ! Je suis MasoMlimi, votre aide agricole. Dites-moi ce que vous voyez sur votre plante ou votre animal. Je réponds uniquement à partir de conseils approuvés par des experts.',
    'sw': 'Habari! Mimi ni MasoMlimi, msaidizi wako wa shamba. Niambie unachoona kwenye mmea au mnyama wako. Ninajibu tu kutokana na ushauri ulioidhinishwa na wataalamu.',
    'pt': 'Olá! Sou o MasoMlimi, o seu ajudante na quinta. Diga-me o que vê na sua planta ou animal. Respondo apenas com conselhos aprovados por especialistas.',
  };
  static const _acc = {'à': 'a', 'á': 'a', 'â': 'a', 'ã': 'a', 'ä': 'a', 'å': 'a', 'è': 'e', 'é': 'e', 'ê': 'e', 'ë': 'e', 'ì': 'i', 'í': 'i', 'î': 'i', 'ï': 'i', 'ò': 'o', 'ó': 'o', 'ô': 'o', 'õ': 'o', 'ö': 'o', 'ù': 'u', 'ú': 'u', 'û': 'u', 'ü': 'u', 'ç': 'c', 'ñ': 'n', 'œ': 'oe', '’': "'"};
  static final _doseQ = RegExp(r'\b(dose|dosage|dosagem|posologie|kipimo|kiasi|kuchuluka|how much|combien|quanto|withdrawal)\b', caseSensitive: false);
  static final _chem = RegExp(r'antibiotic|antibiotique|antibiotico|tetracycline|penicillin|ivermectin|albendazole|levamisole|pesticide|insecticide|fungicide|herbicide|acaricide|\bdip\b|\bspray|chemical|chimique|quimico|kemikali', caseSensitive: false);

  // ------------------------------------------------------------------ text helpers (mirror kb_engine.py)
  static String fold(String s) {
    final b = StringBuffer();
    for (final ch in s.toLowerCase().split('')) {
      b.write(_acc[ch] ?? ch);
    }
    return b.toString().replaceAll("'", '');
  }

  static String plain(String s) => fold(s).replaceAll(RegExp(r'[^a-z0-9]+'), ' ').trim();

  static String stem(String t) {
    if (t.length > 4 && t.endsWith('ies')) return '${t.substring(0, t.length - 3)}y';
    if (t.length > 5 && RegExp(r'(ches|shes|xes|sses)$').hasMatch(t)) return t.substring(0, t.length - 2);
    if (t.length > 3 && t.endsWith('s') && !RegExp(r'(ss|us|is)$').hasMatch(t)) t = t.substring(0, t.length - 1);
    if (t.length > 5 && t.endsWith('ing')) return t.substring(0, t.length - 3);
    if (t.length > 5 && t.endsWith('ed')) return t.substring(0, t.length - 2);
    return t;
  }

  static List<String> tokens(String s) {
    final lex = Map<String, dynamic>.from((_pack?['lexicon'] as Map?) ?? const {});
    final stop = ((_pack?['stop'] as List?) ?? const ['the', 'a', 'is', 'of', 'and', 'my', 'what', 'how', 'do', 'it', 'this', 'with', 'for', 'have', 'has']).toSet();
    final out = <String>[];
    for (final m in RegExp(r'[a-z0-9]+').allMatches(fold(s))) {
      final t = m.group(0)!;
      if (t.length < 2 || stop.contains(t)) continue;
      out.add(stem('${lex[t] ?? t}'));
    }
    return out;
  }

  static bool hasPhrase(String plainText, String phrase) => ' $plainText '.contains(' ${plain(phrase)} ');

  // ------------------------------------------------------------------ pack
  static Future<Directory> _dir() async {
    final d = await getApplicationDocumentsDirectory();
    final dir = Directory('${d.path}/masomlimi_offline');
    if (!await dir.exists()) await dir.create(recursive: true);
    return dir;
  }

  static Future<File> _packFile() async => File('${(await _dir()).path}/chatpack.json');
  static Future<File> _fbFile() async => File('${(await _dir()).path}/fb_outbox.json');

  static Future<void> syncPack(String apiBase) async {
    await flushFeedback(apiBase);
    try {
      final res = await http.get(Uri.parse('$apiBase/v1/sync/chatpack')).timeout(const Duration(seconds: 12));
      if (res.statusCode == 200 && res.body.length > 20) {
        final data = jsonDecode(utf8.decode(res.bodyBytes));
        if (data is Map && data['procedures'] is List) {
          // TODO(launch gate): verify data['signature'] with the pack public key before load.
          await (await _packFile()).writeAsString(jsonEncode(data), flush: true);
          _load(Map<String, dynamic>.from(data));
        }
      }
    } catch (_) {}
  }

  static Future<void> _ensureLoaded() async {
    if (_pack != null) return;
    try {
      final f = await _packFile();
      if (await f.exists()) {
        final data = jsonDecode(await f.readAsString());
        if (data is Map) _load(Map<String, dynamic>.from(data));
      }
    } catch (_) {}
  }

  static void _load(Map<String, dynamic> pack) {
    _pack = pack;
    _docs = [];
    final df = <String, int>{};
    for (final p in (pack['procedures'] as List? ?? [])) {
      if (p is! Map) continue;
      final tf = <String, int>{};
      void add(dynamic text, int w) {
        for (final t in tokens('$text')) {
          tf[t] = (tf[t] ?? 0) + w;
        }
      }
      void addAll(dynamic l, int w) {
        if (l is List) {
          for (final x in l) {
            add(x, w);
          }
        }
      }
      for (final v in ((p['views'] as Map?) ?? {}).values) {
        if (v is! Map) continue;
        add(v['title'], 3);
        addAll(v['signs'], 2);
        addAll(v['symptoms'], 2);
        for (final k in ['treatment', 'medication', 'prevention', 'refer']) {
          addAll(v[k], 1);
        }
      }
      addAll(p['facts'], 1);
      addAll(p['aliases'], 2); // expert-approved local words
      for (final k in tf.keys) {
        df[k] = (df[k] ?? 0) + 1;
      }
      _docs.add(_Doc(p, tf, max(1, tf.values.fold(0, (a, b) => a + b)), '${p['host_key']}'.toLowerCase(), p['dangerous'] == true));
    }
    final n = _docs.length;
    _idf = {for (final e in df.entries) e.key: log(1 + (n - e.value + 0.5) / (e.value + 0.5))};
    _avgdl = n == 0 ? 1 : _docs.fold<int>(0, (a, d) => a + d.len) / n;
  }

  static Map ui(String lang) {
    final all = (_pack?['ui'] as Map?) ?? const {};
    return (all[lang] ?? all['en'] ?? const {}) as Map;
  }

  static String _u(String lang, String k, String fallback) => '${ui(lang)[k] ?? fallback}';

  // ------------------------------------------------------------------ small talk (fixed text, mirrors kb_engine.py)
  static Map<String, List<String>> _intents() {
    final p = _pack?['intents'];
    if (p is Map) return p.map((k, v) => MapEntry('$k', (v as List).map((e) => '$e').toList()));
    return _intentsDefault.map((k, v) => MapEntry(k, List<String>.from(v)));
  }

  /// (intents found, message with those phrases removed)
  static (Set<String>, String) splitIntents(String plainText) {
    var rest = ' $plainText ';
    final found = <String>{};
    final items = <MapEntry<String, String>>[];
    _intents().forEach((k, ps) {
      for (final p in ps) {
        items.add(MapEntry(p, k));
      }
    });
    items.sort((a, b) => plain(b.key).length.compareTo(plain(a.key).length));
    for (final it in items) {
      final pp = ' ${plain(it.key)} ';
      while (rest.contains(pp)) {
        found.add(it.value);
        rest = rest.replaceFirst(pp, ' ');
      }
    }
    return (found, rest.replaceAll(RegExp(r'\s+'), ' ').trim());
  }

  /// A pure greeting / thanks / goodbye / "what can you do?" gets a fixed, localized reply (no network needed).
  static Future<ChatAnswer?> smalltalk(String text, String lang) async {
    await _ensureLoaded();
    final r = splitIntents(plain(text));
    if (r.$1.isEmpty || tokens(r.$2).isNotEmpty) return null;
    const order = [['about', 'about'], ['greeting', 'hello'], ['thanks', 'thanks_reply'], ['bye', 'bye_reply'], ['okay', 'okay_reply']];
    for (final o in order) {
      if (r.$1.contains(o[0])) {
        return ChatAnswer(text: _u(lang, o[1], _helloFallback[lang] ?? _helloFallback['en']!), outcome: 'smalltalk', band: 'none');
      }
    }
    return null;
  }

  /// The localized opening line of a new chat.
  static Future<String> helloText(String lang) async {
    await _ensureLoaded();
    return _u(lang, 'hello', _helloFallback[lang] ?? _helloFallback['en']!);
  }

  // ------------------------------------------------------------------ which crop / animal is this? (suggestion only)
  static Future<Set<String>> guidedHosts() async {
    await _ensureLoaded();
    return _docs.map((d) => d.host).toSet();
  }

  static Future<List<String>> offlineChoices(String organism) async {
    final guided = await guidedHosts();
    final defaults = organism == 'livestock' ? _livestockDefaults : _cropDefaults;
    final isLive = organism == 'livestock';
    final first = guided.where((h) => _livestock.contains(h) == isLive && h != 'other' && h.isNotEmpty).toList();
    return [...first, ...defaults.where((h) => !first.contains(h))];
  }

  static Future<HostGuess> identify({required String apiBase, required String photoPath, required String organism}) async {
    final guided = await guidedHosts();
    try {
      final req = http.MultipartRequest('POST', Uri.parse('$apiBase/v1/scan/identify'));
      req.fields['organism_hint'] = organism;
      req.files.add(await http.MultipartFile.fromPath('image', photoPath));
      final res = await http.Response.fromStream(await req.send().timeout(const Duration(seconds: 25)));
      if (res.statusCode == 200) {
        final j = jsonDecode(utf8.decode(res.bodyBytes)) as Map;
        final cands = [for (final c in (j['candidates'] as List? ?? [])) if (c is Map) '${c['host_key']}'];
        final choices = [for (final c in (j['choices'] as List? ?? [])) if (c is Map) '${c['host_key']}'];
        final online = {for (final c in (j['choices'] as List? ?? [])) if (c is Map && c['has_guidance'] == true) '${c['host_key']}'};
        return HostGuess(
          ok: true,
          confident: j['confident'] == true,
          suggested: j['suggested'] == null ? null : '${j['suggested']}',
          mismatch: j['organism_mismatch'] == null ? null : '${j['organism_mismatch']}',
          candidates: cands,
          choices: choices.isEmpty ? await offlineChoices(organism) : choices,
          guided: online.isEmpty ? guided : online,
        );
      }
    } catch (_) {}
    return HostGuess(ok: false, choices: await offlineChoices(organism), guided: guided);
  }

  /// Tell the server whether the farmer agreed with the suggestion (no photo is sent). Best effort.
  static Future<void> identifyFeedback(String apiBase, {required String detected, required String chosen, required String organism}) async {
    try {
      await http
          .post(Uri.parse('$apiBase/v1/scan/identify/feedback'), headers: {'Content-Type': 'application/json'}, body: jsonEncode({'detected': detected, 'chosen': chosen, 'organism': organism}))
          .timeout(const Duration(seconds: 6));
    } catch (_) {}
  }

  // ------------------------------------------------------------------ emergency (fixed)
  static ChatAnswer emergencyAnswer(String lang, {String name = ''}) {
    final steps = ((_pack?['critical'] as Map?)?[lang] as List?)?.map((e) => '$e').toList() ?? (_critical[lang] ?? _critical['en']!);
    final title = _u(lang, 'emergency_title', _emTitle[lang] ?? _emTitle['en']!) + (name.isEmpty ? '' : ' ($name)');
    final expert = _u(lang, 'emergency_expert', _emExpert[lang] ?? _emExpert['en']!);
    final body = [for (var i = 0; i < steps.length; i++) '${i + 1}. ${steps[i]}'].join('\n');
    return ChatAnswer(text: '$title\n$body\n$expert', outcome: 'emergency', band: 'high', emergency: true);
  }

  /// Run on EVERY farmer message / scan before anything else.
  static Future<ChatAnswer?> emergencyIfAny(String message, String lang, String host, {List<String> symptomKeys = const [], bool danger = false}) async {
    await _ensureLoaded();
    final h = host.toLowerCase();
    if (_livestock.contains(h) && (danger || symptomKeys.any(_dangerKeys.contains))) return emergencyAnswer(lang);
    if (h.isNotEmpty && !_livestock.contains(h)) return null;
    final p = plain(message);
    final terms = ((_pack?['danger_terms'] as List?)?.map((e) => '$e').toList()) ?? _dangerTerms;
    for (final t in terms) {
      if (hasPhrase(p, t)) return emergencyAnswer(lang);
    }
    if (_livestock.contains(h)) {
      final signs = ((_pack?['danger_signs'] as List?)?.map((e) => '$e').toList()) ?? _dangerSigns;
      for (final s in signs) {
        if (hasPhrase(p, s)) return emergencyAnswer(lang);
      }
    }
    return null;
  }

  // ------------------------------------------------------------------ ask / scan
  /// Text question, or (when [photoPath] is set) a photo scan with the selected symptoms.
  static Future<ChatAnswer> ask({
    required String apiBase,
    required String message,
    required String lang,
    required String hostKey,
    String description = '',
    String deviceId = '',
    String district = 'Lilongwe',
    String? photoPath,
    List<String> symptomKeys = const [],
    bool danger = false,
  }) async {
    final em = await emergencyIfAny('$message $description', lang, hostKey, symptomKeys: symptomKeys, danger: danger);
    if (em != null) return em;
    final talk = await smalltalk(message, lang);
    if (talk != null) return talk;
    try {
      http.Response res;
      if (photoPath != null && File(photoPath).existsSync()) {
        final req = http.MultipartRequest('POST', Uri.parse('$apiBase/v1/scan/analyze'));
        req.fields.addAll({
          'host_key': hostKey,
          'organism_hint': _livestock.contains(hostKey.toLowerCase()) ? 'livestock' : 'crop',
          'language': lang,
          'device_id': deviceId,
          'district': district,
          'symptom_keys': jsonEncode(symptomKeys),
          'notes': '$message $description'.trim(),
          'danger_signs_present': danger.toString(),
        });
        req.files.add(await http.MultipartFile.fromPath('image', photoPath));
        res = await http.Response.fromStream(await req.send().timeout(const Duration(seconds: 30)));
      } else {
        res = await http
            .post(Uri.parse('$apiBase/v1/knowledge/chat'),
                headers: {'Content-Type': 'application/json'},
                body: jsonEncode({'message': message, 'language': lang, 'host_key': hostKey, 'description': description, 'device_id': deviceId, 'district': district}))
            .timeout(const Duration(seconds: 14));
      }
      if (res.statusCode == 200) {
        final a = ChatAnswer.fromServer(jsonDecode(utf8.decode(res.bodyBytes)) as Map, apiBase);
        if (a.text.isNotEmpty) return a;
      }
    } catch (_) {}
    return offline(message: '$message ${symptomKeys.map((k) => k.replaceAll('_', ' ')).join(' ')}', lang: lang, hostKey: hostKey, description: description);
  }

  // ---- "did this help?" (feeds the shared memory; queued if offline) ----
  static Future<void> feedback(String apiBase, String caseId, bool helped) async {
    final item = {'case_id': caseId, 'helped': helped ? 'yes' : 'no'};
    try {
      final res = await http.post(Uri.parse('$apiBase/v1/memory/feedback'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(item)).timeout(const Duration(seconds: 8));
      if (res.statusCode >= 200 && res.statusCode < 300) return;
    } catch (_) {}
    final f = await _fbFile();
    final box = (await f.exists()) ? (jsonDecode(await f.readAsString()) as List) : [];
    box.add(item);
    await f.writeAsString(jsonEncode(box), flush: true);
  }

  static Future<void> flushFeedback(String apiBase) async {
    try {
      final f = await _fbFile();
      if (!await f.exists()) return;
      final box = jsonDecode(await f.readAsString()) as List;
      final remain = [];
      for (final it in box) {
        try {
          final res = await http.post(Uri.parse('$apiBase/v1/memory/feedback'), headers: {'Content-Type': 'application/json'}, body: jsonEncode(it)).timeout(const Duration(seconds: 8));
          if (res.statusCode < 200 || res.statusCode >= 300) remain.add(it);
        } catch (_) {
          remain.add(it);
        }
      }
      await f.writeAsString(jsonEncode(remain), flush: true);
    } catch (_) {}
  }

  // ------------------------------------------------------------------ offline answer (mirror of kb_engine.answer)
  static ChatAnswer _notSure(String lang, {List<String> quick = const []}) => ChatAnswer(
      text: '${_u(lang, 'not_sure', 'I am not sure about this. Please ask an expert. I will not guess.')}\n${_u(lang, 'ask_expert', 'Ask a vet, extension officer or agro-dealer before using any medicine or chemical.')}',
      outcome: 'not_sure',
      band: 'low',
      bandLabel: _u(lang, 'conf_low', 'Not sure'),
      quick: quick);

  static Map _view(_Doc d, String lang) {
    final views = (d.p['views'] as Map?) ?? {};
    return (views[lang] ?? views['en'] ?? (views.values.isNotEmpty ? views.values.first : {})) as Map;
  }

  static List<String> _list(dynamic v) => v is List ? v.map((e) => '$e').toList() : <String>[];

  static List<String> _rank(List<String> lines, Set<String> q, int limit) {
    if (q.isEmpty || lines.length <= limit) return lines.take(limit).toList();
    final sc = [for (var i = 0; i < lines.length; i++) [tokens(lines[i]).where(q.contains).length, i]];
    sc.sort((a, b) => a[0] != b[0] ? b[0].compareTo(a[0]) : a[1].compareTo(b[1]));
    final keep = sc.take(limit).map((e) => e[1]).toList()..sort();
    return keep.map((i) => lines[i]).toList();
  }

  static Future<ChatAnswer> offline({required String message, required String lang, required String hostKey, String description = ''}) async {
    await _ensureLoaded();
    if (_pack == null) return _notSure(lang);
    final sp = splitIntents(plain(message));
    final greeted = sp.$1.contains('greeting');
    if (sp.$1.isNotEmpty && tokens(sp.$2).isNotEmpty) message = sp.$2; // "Hello, my maize has spots" -> answer the question
    final host = hostKey.toLowerCase();
    final hostToks = tokens(host).toSet();
    var q = tokens(message).where((t) => !hostToks.contains(t)).toList();
    if (q.length < 2) q += tokens(description).where((t) => !hostToks.contains(t)).toList();
    q = q.toSet().toList();
    if (q.isEmpty) return ChatAnswer(text: _u(lang, 'empty_query', 'Please tell me what you see on the plant or animal.'), outcome: 'prompt');
    double w(String t) => max(_idf[t] ?? 1.0, 0.3);
    final total = q.fold<double>(0, (a, t) => a + w(t));
    final minCov = (_pack!['min_coverage'] as num?)?.toDouble() ?? 0.34;
    final highCov = (_pack!['high_coverage'] as num?)?.toDouble() ?? 0.60;

    final scored = <List>[]; // [score, cov, doc]
    for (final d in _docs) {
      if (host.isNotEmpty && d.host != host) continue;
      double score = 0, matched = 0;
      for (final t in q) {
        final f = d.tf[t] ?? 0;
        if (f > 0) {
          score += w(t) * f * 2.4 / (f + 1.4 * (0.25 + 0.75 * d.len / _avgdl));
          matched += w(t);
        }
      }
      scored.add([score, matched / total, d]);
    }
    scored.sort((a, b) => (b[0] as double).compareTo(a[0] as double));
    final ranked = <List>[]; // [score, cov, doc, title]
    final seen = <String>{};
    for (final s in scored) {
      final title = '${_view(s[2] as _Doc, lang)['title'] ?? ''}';
      final key = plain(title.isEmpty ? (s[2] as _Doc).id : title);
      if ((s[0] as double) <= 0 || seen.contains(key)) continue;
      seen.add(key);
      ranked.add([s[0], s[1], s[2], title]);
    }
    if (ranked.isEmpty || (ranked[0][1] as double) < minCov) {
      final near = ranked.take(3).where((r) => (r[1] as double) >= minCov * 0.5 && !(r[2] as _Doc).dangerous && '${r[3]}'.isNotEmpty).map((r) => '${r[3]}').toList();
      return _notSure(lang, quick: near);
    }
    final ok = ranked.where((r) => (r[1] as double) >= minCov).toList();
    final s1 = ok[0][0] as double;
    final close = ok.take(3).where((r) => (r[0] as double) >= 0.85 * s1).toList();
    if (close.length > 1) {
      final titles = close.map((r) => '${r[3]}').where((t) => t.isNotEmpty).toList();
      return ChatAnswer(
          text: '${_u(lang, 'did_you_mean', 'Which of these do you mean?')}\n${[for (var i = 0; i < titles.length; i++) '${i + 1}. ${titles[i]}'].join('\n')}',
          outcome: 'clarify', band: 'medium', quick: titles);
    }
    final top = ok[0][2] as _Doc;
    final c1 = ok[0][1] as double;
    if (top.dangerous) return emergencyAnswer(lang, name: '${ok[0][3]}');

    final v = _view(top, lang);
    final qset = q.toSet();
    final signs = _rank(_list(v['signs']), qset, 4);
    final symptoms = _rank(_list(v['symptoms']), qset, 4);
    final treat = _list(v['treatment']).take(6).toList();
    final meds = _list(v['medication']).take(6).toList();
    final dose = _list(v['dose']).take(6).toList();
    final prev = _list(v['prevention']).take(4).toList();
    final refer = _list(v['refer']).take(3).toList();
    if ([signs, symptoms, treat, meds, dose, prev, refer].every((l) => l.isEmpty)) return _notSure(lang);

    final body = <String>[];
    final type = '${v['type'] ?? ''}';
    if (type.isNotEmpty) body.add('${_u(lang, 'type_label', 'Type')}: ${_u(lang, 't_$type', type)}');
    void block(String label, List<String> l, {bool numbered = false}) {
      if (l.isEmpty) return;
      body.add('$label:');
      for (var i = 0; i < l.length; i++) {
        body.add(numbered ? '${i + 1}. ${l[i]}' : '\u2022 ${l[i]}');
      }
    }
    block(_u(lang, 'signs', 'Signs'), signs);
    block(_u(lang, 'symptoms', 'Symptoms'), symptoms);
    block(_u(lang, 'steps', 'What to do'), treat, numbered: true);
    block(_u(lang, 'medicines', 'Medicines and products'), meds);
    block(_u(lang, 'dose_label', 'Dose and withdrawal (as published by the vet)'), dose);
    block(_u(lang, 'prevention', 'Prevention'), prev);
    block(_u(lang, 'refer', 'When to get help'), refer);

    final notices = <String>[];
    if (v['fell_back'] == true) {
      notices.add(_u(lang, 'lang_fallback', 'This guidance is not yet available in your language. Showing the original.'));
    } else if ('${v['status']}' != 'reviewed') {
      notices.add(_u(lang, 'translation_unreviewed', 'Translation is waiting for expert review.'));
    }
    final foot = <String>[];
    final hidden = (v['dose_hidden'] as num?)?.toInt() ?? 0;
    if (dose.isNotEmpty) {
      foot.add('${_u(lang, 'dose_source', 'Dose source')}: ${v['dose_source']}');
      foot.add(_u(lang, 'follow_label', 'Follow the product label and ask a vet or agro-dealer if unsure.'));
    } else if (_doseQ.hasMatch(message) || hidden > 0) {
      foot.add(_u(lang, 'dose_ask', 'Doses and application rates are not given here. Ask a vet or agro-dealer to confirm.'));
    }
    if (meds.isNotEmpty || dose.isNotEmpty || _chem.hasMatch([...treat, ...prev, ...meds].join(' '))) {
      foot.add(_u(lang, 'chem_note', 'This involves a medicine or strong chemical - ask an expert first.'));
    }
    foot.add(_u(lang, 'ask_expert', 'Ask a vet, extension officer or agro-dealer before using any medicine or chemical.'));

    final p = top.p;
    final title = '${v['title'] ?? ok[0][3]}';
    final srcBits = <String>['${'${p['source_filename'] ?? ''}'.isNotEmpty ? p['source_filename'] : title}'];
    if ('${p['approved_at'] ?? ''}'.isNotEmpty) srcBits.add('${_u(lang, 'approved', 'Approved')}: ${p['approved_at']}');
    var srcLine = '${_u(lang, 'source', 'Source')}: ${srcBits.join(' \u00b7 ')}';
    if ('${p['approved_by'] ?? ''}'.isNotEmpty) srcLine += ' (${p['approved_by']})';

    // other farmers nearby (k-anonymous count shipped in the pack)
    final nearby = ((_pack!['nearby'] as Map?) ?? {})[top.id];
    final note = (nearby is num && nearby >= 3)
        ? _u(lang, 'similar_seen', '{n} other farmers near you asked about a similar problem in the last {d} days.').replaceAll('{n}', '$nearby').replaceAll('{d}', '30')
        : '';
    final band = c1 >= highCov ? 'high' : 'medium';
    return ChatAnswer(
      text: ['${greeted ? '${_u(lang, 'hello_short', 'Hello!')}\n' : ''}${_u(lang, 'from_library', 'From the approved expert library')}: $title', ...notices, body.join('\n'), if (note.isNotEmpty) note, ...foot, srcLine].join('\n'),
      outcome: 'answer',
      band: band,
      bandLabel: _u(lang, 'conf_$band', band),
      sources: [srcLine],
      notices: notices,
    );
  }
}
