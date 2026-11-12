// Scan chat: a real conversation. Greets in the chosen language, understands hello / thanks / goodbye / "what can you do?",
// and answers ONLY from advice published by experts (online: server + shared memory, offline: signed chat pack).
// Emergency rules run first on every message. Follow-up questions are asked only when the answer would be "not sure".
import 'package:flutter/material.dart';
import 'chat_engine.dart';
import 'main.dart' show t, hostLabel, normalizeHost, isLivestockHost, cropHosts, kApiBase;
import 'offline_cache.dart';
import 'theme.dart';

class KnowledgeChatPage extends StatefulWidget {
  final String lang, deviceId, hostKey, organismType, scanOutcome, notes;
  final String? photoPath;
  final List<String> symptomKeys;
  final bool dangerSigns, startWithChat, hostConfirmed;
  const KnowledgeChatPage({
    super.key,
    required this.lang,
    required this.deviceId,
    required this.hostKey,
    required this.organismType,
    this.scanOutcome = '',
    this.photoPath,
    this.symptomKeys = const [],
    this.dangerSigns = false,
    this.notes = '',
    this.startWithChat = true,
    this.hostConfirmed = false,
  });
  @override
  State<KnowledgeChatPage> createState() => _KnowledgeChatPageState();
}

class _KnowledgeChatPageState extends State<KnowledgeChatPage> {
  final _ctrl = TextEditingController();
  final _scroll = ScrollController();
  final List<Map<String, String>> _msgs = [];
  final List<String> _described = []; // what the farmer has told us so far
  final List<String> _followups = ['signs', 'part', 'duration', 'spread', 'context'];
  String _host = '';
  bool _busy = false, _hostLocked = false, _photoSent = false;

  static const _qs = {
    'en': {
      'askHost': 'Which crop or animal is this? Type its name (for example maize, tomato, goat, chicken).',
      'signs': 'What do you see? (spots, yellow leaves, wilting, coughing, diarrhoea, weak...)',
      'part': 'Which part is affected? (leaves, stem, fruit, whole plant) - or for animals: age and which animals?',
      'duration': 'How long have you seen this? (days or weeks)',
      'spread': 'How many plants or animals are affected? Is it spreading?',
      'context': 'Any recent change? (rain, drought, new feed, new field, chemicals)',
      'chose': 'You chose {h}.',
    },
    'ny': {
      'askHost': 'Ndi mbewu kapena chiweto chanji? Lembani dzina (mwachitsanzo chimanga, nyanya, mbuzi, nkhuku).',
      'signs': 'Mukuwona chiyani? (mawanga, masamba achikasu, kufota, kutsokomola...)',
      'part': 'Ndi gawo liti lomwe lakhudzidwa? (masamba, tsinde, zipatso) - kapena chiweto: zaka ndi ziti?',
      'duration': 'Mwawona kwa nthawi yayitali bwanji? (masiku kapena masabata)',
      'spread': 'Zingati zakhudzidwa? Zikufalikira?',
      'context': 'Pali kusintha posachedwapa? (mvula, chilala, chakudya chatsopano)',
      'chose': 'Mwasankha {h}.',
    },
    'fr': {
      'askHost': 'Quelle culture ou quel animal ? Écrivez son nom (par exemple maïs, tomate, chèvre, poule).',
      'signs': 'Que voyez-vous ? (taches, feuilles jaunes, flétrissement, toux, diarrhée, faiblesse...)',
      'part': 'Quelle partie est touchée ? (feuilles, tige, fruit) - ou pour un animal : âge et lesquels ?',
      'duration': 'Depuis combien de temps ? (jours ou semaines)',
      'spread': 'Combien de plantes ou d\'animaux sont touchés ? Ça se propage ?',
      'context': 'Un changement récent ? (pluie, sécheresse, nouvel aliment, produits)',
      'chose': 'Vous avez choisi {h}.',
    },
    'sw': {
      'askHost': 'Ni zao gani au mnyama gani? Andika jina (mfano mahindi, nyanya, mbuzi, kuku).',
      'signs': 'Unaona nini? (madoa, majani ya njano, kunyauka, kikohozi, kuhara, udhaifu...)',
      'part': 'Sehemu gani imeathirika? (majani, shina, matunda) - au kwa mnyama: umri na wapi?',
      'duration': 'Umeona kwa muda gani? (siku au wiki)',
      'spread': 'Mimea au wanyama wangapi wameathirika? Inaenea?',
      'context': 'Kuna mabadiliko ya hivi karibuni? (mvua, ukame, chakula kipya)',
      'chose': 'Umechagua {h}.',
    },
    'pt': {
      'askHost': 'Que cultura ou animal é este? Escreva o nome (por exemplo milho, tomate, cabra, galinha).',
      'signs': 'O que vê? (manchas, folhas amarelas, murchar, tosse, diarreia, fraqueza...)',
      'part': 'Que parte está afetada? (folhas, caule, fruto) - ou, num animal: idade e quais?',
      'duration': 'Há quanto tempo vê isto? (dias ou semanas)',
      'spread': 'Quantas plantas ou animais estão afetados? Está a espalhar-se?',
      'context': 'Alguma mudança recente? (chuva, seca, nova ração, produtos)',
      'chose': 'Escolheu {h}.',
    },
  };

  String _q(String k) => (_qs[widget.lang] ?? _qs['en']!)[k] ?? _qs['en']![k]!;
  String get _hostNow => normalizeHost(_host.isNotEmpty ? _host : widget.hostKey);
  String _nice(String h) {
    final l = hostLabel(h, widget.lang);
    return (l == h && h.isNotEmpty) ? '${h[0].toUpperCase()}${h.substring(1)}' : l;
  }

  String _symptomText() => [..._described.reversed.take(6).toList().reversed, ...widget.symptomKeys.map((k) => k.replaceAll('_', ' ')), widget.notes].where((e) => e.trim().isNotEmpty).join('. ');

  bool _isAdviceRequest(String text) {
    final low = text.toLowerCase().trim();
    const keys = ['advice', 'give advice', 'guidance', 'what should i do', 'uphungu', 'thandizeni', 'conseil', 'conseils', 'ushauri', 'nisaidie', 'conselho'];
    return keys.any((k) => low == k || low.contains(k));
  }

  @override
  void initState() {
    super.initState();
    _host = normalizeHost(widget.hostKey);
    _hostLocked = widget.hostConfirmed && _host.isNotEmpty && _host != 'other';
    _start();
  }

  @override
  void dispose() {
    _ctrl.dispose();
    _scroll.dispose();
    super.dispose();
  }

  Future<void> _start() async {
    final hello = await ChatEngine.helloText(widget.lang);
    if (!mounted) return;
    setState(() => _msgs.add({'role': 'bot', 'text': hello}));
    if (!_hostLocked) {
      setState(() => _msgs.add({'role': 'bot', 'text': _q('askHost')}));
      return;
    }
    final arrivedWithSymptoms = widget.symptomKeys.isNotEmpty || widget.notes.trim().isNotEmpty;
    if (arrivedWithSymptoms) {
      setState(() => _msgs.add({'role': 'bot', 'text': _q('chose').replaceAll('{h}', _nice(_hostNow))}));
      await _giveAdvice(); // they already told us what they see on the previous screen
    } else {
      setState(() => _msgs.add({'role': 'bot', 'text': '${_q('chose').replaceAll('{h}', _nice(_hostNow))} ${_q('signs')}'}));
      _followups.remove('signs');
    }
  }

  void _scrollEnd() => WidgetsBinding.instance.addPostFrameCallback((_) {
        if (_scroll.hasClients) _scroll.animateTo(_scroll.position.maxScrollExtent, duration: const Duration(milliseconds: 200), curve: Curves.easeOut);
      });

  Future<ChatAnswer> _ask(String q) {
    final first = !_photoSent && widget.photoPath != null;
    if (first) _photoSent = true;
    return ChatEngine.ask(
      apiBase: kApiBase,
      message: q,
      lang: widget.lang,
      hostKey: _hostNow,
      description: _symptomText(),
      deviceId: widget.deviceId,
      photoPath: first ? widget.photoPath : null, // the photo goes up once, with the first real question
      symptomKeys: widget.symptomKeys,
      danger: widget.dangerSigns,
    );
  }

  Future<void> _saveEpisode(String advice) async {
    await OfflineCache.appendScanEpisode({
      'id': 'local-${DateTime.now().millisecondsSinceEpoch}',
      'at': DateTime.now().toUtc().toIso8601String(),
      'device_id': widget.deviceId,
      'host_key': _hostNow,
      'farmer_description': _symptomText(),
      'advice_summary': advice.length > 500 ? advice.substring(0, 500) : advice,
      'language': widget.lang,
    });
  }

  Future<void> _giveAdvice({String question = ''}) async {
    setState(() => _busy = true);
    final q = (question.isEmpty || _isAdviceRequest(question)) ? _symptomText() : question;
    final ans = await _ask(q);
    if (!mounted) return;
    if (ans.outcome == 'answer') await _saveEpisode(ans.text);
    setState(() {
      _msgs.add(ans.toBubble());
      // ask ONE useful follow-up only when we could not help yet
      if ((ans.outcome == 'not_sure' || ans.outcome == 'prompt') && _followups.isNotEmpty) {
        _msgs.add({'role': 'bot', 'text': _q(_followups.removeAt(0))});
      }
      _busy = false;
    });
    _scrollEnd();
  }

  Future<void> _send([String? preset]) async {
    final text = (preset ?? _ctrl.text).trim();
    if (text.isEmpty || _busy) return;
    _ctrl.clear();
    setState(() {
      _msgs.add({'role': 'you', 'text': text});
      _busy = true;
    });
    _scrollEnd();

    // 1) fixed emergency rules, every message, before anything else
    final em = await ChatEngine.emergencyIfAny(text, widget.lang, _hostNow, symptomKeys: widget.symptomKeys, danger: widget.dangerSigns);
    if (em != null) {
      if (!mounted) return;
      setState(() {
        _msgs.add(em.toBubble());
        _busy = false;
      });
      _scrollEnd();
      return;
    }
    // 2) hello / thanks / goodbye / "what can you do?"
    final talk = await ChatEngine.smalltalk(text, widget.lang);
    if (talk != null) {
      if (!mounted) return;
      setState(() {
        _msgs.add(talk.toBubble());
        if (_hostLocked && _described.isEmpty && widget.symptomKeys.isEmpty && talk.text.isNotEmpty && _followups.contains('signs')) {
          _followups.remove('signs');
          _msgs.add({'role': 'bot', 'text': _q('signs')});
        }
        _busy = false;
      });
      _scrollEnd();
      return;
    }
    // 3) which crop/animal? (only when the chat was opened without a confirmed one)
    if (!_hostLocked) {
      final h = normalizeHost(text);
      final wrong = h.isEmpty || (widget.organismType == 'crop' && isLivestockHost(h)) || (widget.organismType == 'livestock' && cropHosts.contains(h));
      if (wrong) {
        setState(() {
          _msgs.add({'role': 'bot', 'text': _q('askHost')});
          _busy = false;
        });
        return;
      }
      _host = h;
      _hostLocked = true;
      setState(() {
        _msgs.add({'role': 'bot', 'text': '${_q('chose').replaceAll('{h}', _nice(h))} ${_q('signs')}'});
        _followups.remove('signs');
        _busy = false;
      });
      _scrollEnd();
      return;
    }
    // 4) a real question or description: answer from the published library
    if (!_isAdviceRequest(text)) _described.add(text);
    await _giveAdvice(question: text);
  }

  Future<void> _sendFeedback(int i, bool helped) async {
    final id = _msgs[i]['case_id'] ?? '';
    setState(() {
      _msgs[i].remove('fb_q');
      _msgs[i].remove('fb_yes');
      _msgs[i].remove('fb_no');
    });
    await ChatEngine.feedback(kApiBase, id, helped); // queued if offline
  }

  @override
  Widget build(BuildContext context) {
    final title = _hostLocked ? '${t(widget.lang, 'scanChat')} \u00b7 ${_nice(_hostNow)}' : t(widget.lang, 'scanChat');
    return Scaffold(
      appBar: AppBar(title: Text(title)),
      body: Column(children: [
        if (_hostLocked)
          Container(
            width: double.infinity,
            color: C.green.withValues(alpha: 0.12),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            child: Text('${_nice(_hostNow)} \u00b7 ${isLivestockHost(_hostNow) ? t(widget.lang, 'animal') : t(widget.lang, 'crop')}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 13)),
          ),
        Expanded(
          child: ListView.builder(
            controller: _scroll,
            padding: const EdgeInsets.all(12),
            itemCount: _msgs.length + (_busy ? 1 : 0),
            itemBuilder: (_, i) {
              if (i >= _msgs.length) {
                return const Align(alignment: Alignment.centerLeft, child: Padding(padding: EdgeInsets.all(12), child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 3))));
              }
              final m = _msgs[i];
              final bot = m['role'] == 'bot';
              final emergency = (m['emergency'] ?? '').isNotEmpty;
              final band = m['band'] ?? '';
              final bandColor = emergency ? C.red : band == 'high' ? C.greenDark : band == 'medium' ? C.amber : C.muted;
              final img = m['image_url'] ?? '';
              final labelled = bot && (m['band_label'] ?? '').isNotEmpty;
              return Align(
                alignment: bot ? Alignment.centerLeft : Alignment.centerRight,
                child: Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(12),
                  constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
                  decoration: BoxDecoration(
                    color: emergency ? C.redSoft : (bot ? Colors.white : C.green.withValues(alpha: 0.15)),
                    borderRadius: BorderRadius.circular(14),
                    border: Border.all(color: (labelled || emergency) ? bandColor : const Color(0xFFE5E7EB), width: emergency ? 2 : 1),
                  ),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    if (labelled && !emergency) Padding(padding: const EdgeInsets.only(bottom: 4), child: Text(m['band_label']!, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: bandColor))),
                    if ((m['text'] ?? '').isNotEmpty) Text(m['text']!, style: const TextStyle(height: 1.35)),
                    if (img.isNotEmpty) ...[
                      const SizedBox(height: 8),
                      ClipRRect(borderRadius: BorderRadius.circular(10), child: Image.network(img, height: 160, width: double.infinity, fit: BoxFit.cover, errorBuilder: (_, __, ___) => const SizedBox.shrink())),
                    ],
                    if ((m['quick'] ?? '').isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Wrap(spacing: 6, runSpacing: 6, children: [for (final q in m['quick']!.split('|')) ActionChip(label: Text(q), onPressed: () => _send(q))]),
                      ),
                    if ((m['case_id'] ?? '').isNotEmpty && (m['fb_q'] ?? '').isNotEmpty)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                          Text(m['fb_q']!, style: const TextStyle(fontSize: 12, color: C.muted)),
                          Row(children: [
                            TextButton(onPressed: () => _sendFeedback(i, true), child: Text(m['fb_yes'] ?? 'Yes')),
                            TextButton(onPressed: () => _sendFeedback(i, false), child: Text(m['fb_no'] ?? 'No')),
                          ]),
                        ]),
                      ),
                  ]),
                ),
              );
            },
          ),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 8),
          child: Row(children: [
            Expanded(
              child: TextField(
                controller: _ctrl,
                maxLength: 600,
                buildCounter: (_, {required currentLength, required isFocused, maxLength}) => null,
                decoration: InputDecoration(hintText: t(widget.lang, 'typeAnswer'), border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)), isDense: true),
                onSubmitted: (_) => _send(),
              ),
            ),
            const SizedBox(width: 8),
            IconButton.filled(onPressed: _busy ? null : () => _send(), icon: const Icon(Icons.send)),
          ]),
        ),
        Padding(
          padding: const EdgeInsets.fromLTRB(12, 0, 12, 16),
          child: SizedBox(width: double.infinity, child: FilledButton(onPressed: _busy || !_hostLocked ? null : () => _giveAdvice(), child: Text(t(widget.lang, 'getAdvice')))),
        ),
      ]),
    );
  }
}
