// Check tab: choose Crop or Livestock, take a photo, the app SUGGESTS which crop/animal it is, the farmer confirms,
// ticks what they see, then chats. Replaces CheckPage / CameraScanPage / ScanReviewPage in main.dart.
// Photo recognition is a demo (not validated): it never decides alone, and nothing is advised before the farmer confirms.
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';
import 'chat_engine.dart';
import 'knowledge_chat_page.dart';
import 'main.dart' show t, hostLabel, hostIcon, hostTint, kApiBase;
import 'theme.dart';

String _nice(String h, String lang) {
  final l = hostLabel(h, lang);
  return (l == h && h.isNotEmpty) ? '${h[0].toUpperCase()}${h.substring(1)}' : l;
}

class CheckPage extends StatelessWidget {
  final String lang, deviceId;
  const CheckPage({super.key, required this.lang, required this.deviceId});

  void _open(BuildContext context, String organism) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => CameraScanPage(lang: lang, deviceId: deviceId, organismHint: organism)));
  }

  Widget _bigButton(BuildContext context, {required IconData icon, required String label, required Color bg, required String organism}) {
    return Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(24),
      child: InkWell(
        onTap: () => _open(context, organism),
        borderRadius: BorderRadius.circular(24),
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 26),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(24), boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 16, offset: const Offset(0, 6))]),
          child: Row(children: [
            Container(width: 72, height: 72, decoration: BoxDecoration(color: bg, borderRadius: BorderRadius.circular(22)), child: Icon(icon, color: C.greenDark, size: 40)),
            const SizedBox(width: 18),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(label, style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 22, color: Color(0xFF111827))),
                const SizedBox(height: 4),
                Text(t(lang, 'point'), style: const TextStyle(fontSize: 13, color: Color(0xFF9CA3AF))),
              ]),
            ),
            const Icon(Icons.camera_alt_outlined, color: C.greenDark, size: 28),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6),
      body: SafeArea(
        child: ListView(padding: const EdgeInsets.fromLTRB(16, 12, 16, 28), children: [
          Row(children: [
            CircleAvatar(radius: 18, backgroundColor: C.greenSoft, child: const Icon(Icons.person_outline, color: C.greenDark, size: 20)),
            const Spacer(),
            Text(t(lang, 'check'), style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, color: Color(0xFF111827))),
            const Spacer(),
            const SizedBox(width: 40),
          ]),
          const SizedBox(height: 16),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(24), boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 16, offset: const Offset(0, 6))]),
            child: Row(children: [
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(t(lang, 'check'), style: const TextStyle(fontSize: 28, fontWeight: FontWeight.w800, color: Color(0xFF15803D))),
                  const SizedBox(height: 4),
                  Text(t(lang, 'hold'), style: const TextStyle(fontSize: 13, color: Color(0xFF9CA3AF))),
                ]),
              ),
              Container(width: 64, height: 64, decoration: BoxDecoration(color: const Color(0xFFDCFCE7), borderRadius: BorderRadius.circular(20)), child: const Icon(Icons.eco, color: Color(0xFF16A34A), size: 34)),
            ]),
          ),
          const SizedBox(height: 18),
          _bigButton(context, icon: Icons.grass, label: t(lang, 'crops'), bg: const Color(0xFFDCFCE7), organism: 'crop'),
          const SizedBox(height: 14),
          _bigButton(context, icon: Icons.pets, label: t(lang, 'animals'), bg: const Color(0xFFFFF3E0), organism: 'livestock'),
        ]),
      ),
    );
  }
}

class CameraScanPage extends StatefulWidget {
  final String lang, deviceId, organismHint;
  const CameraScanPage({super.key, required this.lang, required this.deviceId, required this.organismHint});
  @override
  State<CameraScanPage> createState() => _CameraScanPageState();
}

class _CameraScanPageState extends State<CameraScanPage> {
  final picker = ImagePicker();

  Future<void> shoot(ImageSource src) async {
    final f = await picker.pickImage(source: src, imageQuality: 75, maxWidth: 1600);
    if (f == null || !mounted) return;
    Navigator.of(context).pushReplacement(MaterialPageRoute(builder: (_) => ScanReviewPage(lang: widget.lang, deviceId: widget.deviceId, organismHint: widget.organismHint, photoPath: f.path)));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      body: SafeArea(
        child: Column(children: [
          Container(
            color: Colors.white,
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 8),
            child: Row(children: [
              IconButton(icon: const Icon(Icons.close), onPressed: () => Navigator.pop(context)),
              const Text('MasoMlimi', style: TextStyle(fontWeight: FontWeight.w800)),
              const Spacer(),
              Text(widget.organismHint == 'livestock' ? t(widget.lang, 'animals') : t(widget.lang, 'crops'), style: const TextStyle(color: C.muted)),
              const SizedBox(width: 12),
            ]),
          ),
          Expanded(
            child: Stack(fit: StackFit.expand, children: [
              Container(
                color: const Color(0xFF1A2A1C),
                child: Center(
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    const Icon(Icons.photo_camera_outlined, size: 56, color: Colors.white54),
                    const SizedBox(height: 12),
                    Text(t(widget.lang, 'point'), textAlign: TextAlign.center, style: const TextStyle(color: Colors.white70)),
                  ]),
                ),
              ),
              Center(child: Container(width: 260, height: 260, decoration: BoxDecoration(border: Border.all(color: Colors.white70, width: 2), borderRadius: BorderRadius.circular(18)))),
              Positioned(
                top: 16,
                left: 0,
                right: 0,
                child: Center(
                  child: Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                    decoration: BoxDecoration(color: Colors.black54, borderRadius: BorderRadius.circular(20)),
                    child: Row(mainAxisSize: MainAxisSize.min, children: [
                      const Icon(Icons.check_circle, color: Color(0xFF81C784), size: 16),
                      const SizedBox(width: 6),
                      Text(t(widget.lang, 'hold'), style: const TextStyle(color: Colors.white, fontSize: 12)),
                    ]),
                  ),
                ),
              ),
            ]),
          ),
          Container(
            color: Colors.white,
            padding: const EdgeInsets.fromLTRB(20, 14, 20, 20),
            child: Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
              IconButton.filledTonal(onPressed: () => shoot(ImageSource.gallery), icon: const Icon(Icons.photo_library_outlined)),
              GestureDetector(
                onTap: () => shoot(ImageSource.camera),
                child: Container(width: 74, height: 74, decoration: BoxDecoration(shape: BoxShape.circle, color: C.greenDark, border: Border.all(color: C.greenSoft, width: 5)), child: const Icon(Icons.camera_alt, color: Colors.white, size: 30)),
              ),
              const SizedBox(width: 48),
            ]),
          ),
        ]),
      ),
    );
  }
}

class ScanReviewPage extends StatefulWidget {
  final String lang, deviceId, organismHint, photoPath;
  const ScanReviewPage({super.key, required this.lang, required this.deviceId, required this.organismHint, required this.photoPath});
  @override
  State<ScanReviewPage> createState() => _ScanReviewPageState();
}

class _ScanReviewPageState extends State<ScanReviewPage> {
  late String _organism = widget.organismHint;
  HostGuess? _guess;
  bool _loading = true, _choosing = false, _feedbackSent = false;
  String? _host;
  final selected = <String>{};
  bool danger = false;
  final notes = TextEditingController();

  static const _cropSigns = [
    ['yellow_leaves', 'Yellow leaves'],
    ['spots', 'Spots on leaves'],
    ['holes', 'Holes / chewed leaves'],
    ['wilting', 'Wilting'],
    ['stunted', 'Stunted growth'],
    ['rot', 'Rot / soft tissue'],
    ['insects_seen', 'Insects seen'],
  ];
  static const _animalSigns = [
    ['not_eating', 'Not eating'],
    ['weak', 'Weak / lying down'],
    ['diarrhea', 'Diarrhea'],
    ['cough', 'Cough / breathing hard'],
    ['skin', 'Skin / feathers problem'],
    ['sudden_many_dead', 'Many sudden deaths'],
    ['high_fever_group', 'Fever in several animals'],
  ];

  @override
  void initState() {
    super.initState();
    _identify();
  }

  @override
  void dispose() {
    notes.dispose();
    super.dispose();
  }

  Future<void> _identify() async {
    setState(() {
      _loading = true;
      _host = null;
      _feedbackSent = false;
    });
    final g = await ChatEngine.identify(apiBase: kApiBase, photoPath: widget.photoPath, organism: _organism);
    if (!mounted) return;
    setState(() {
      _guess = g;
      _loading = false;
      _choosing = !(g.confident && g.suggested != null);
    });
  }

  void _pick(String h) {
    final g = _guess;
    if (!_feedbackSent && g != null && g.ok) {
      _feedbackSent = true;
      ChatEngine.identifyFeedback(kApiBase, detected: g.candidates.isNotEmpty ? g.candidates.first : '', chosen: h, organism: _organism);
    }
    setState(() {
      _host = h;
      _choosing = false;
    });
  }

  Widget _card(Widget child) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        margin: const EdgeInsets.only(bottom: 12),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(20)),
        child: child,
      );

  Widget _whatIsThis() {
    final g = _guess;
    if (_loading) {
      return _card(Row(children: [
        const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 3)),
        const SizedBox(width: 14),
        Expanded(child: Text(t(widget.lang, 'lookingPhoto'), style: const TextStyle(fontWeight: FontWeight.w600))),
      ]));
    }
    if (_host != null) {
      return _card(Row(children: [
        CircleAvatar(backgroundColor: hostTint(_host!), child: Icon(hostIcon(_host!), color: C.greenDark)),
        const SizedBox(width: 12),
        Expanded(child: Text(_nice(_host!, widget.lang), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 18))),
        TextButton(onPressed: () => setState(() => _choosing = true), child: Text(t(widget.lang, 'chooseOther'))),
      ]));
    }
    final children = <Widget>[];
    if (g != null && g.mismatch != null) {
      final toLive = g.mismatch == 'livestock';
      children.addAll([
        Text(t(widget.lang, toLive ? 'looksAnimal' : 'looksCrop'), style: const TextStyle(fontWeight: FontWeight.w700, height: 1.35)),
        const SizedBox(height: 10),
        FilledButton(
          onPressed: () {
            setState(() => _organism = toLive ? 'livestock' : 'crop');
            _identify();
          },
          child: Text(t(widget.lang, 'switchYes')),
        ),
        const SizedBox(height: 10),
      ]);
    }
    if (!_choosing && g != null && g.suggested != null) {
      children.addAll([
        Text(t(widget.lang, 'looksLike'), style: const TextStyle(color: C.muted)),
        const SizedBox(height: 4),
        Text(_nice(g.suggested!, widget.lang), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 24)),
        const SizedBox(height: 12),
        FilledButton(onPressed: () => _pick(g.suggested!), child: Text(t(widget.lang, 'yesRight'))),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: () => setState(() => _choosing = true), child: Text(t(widget.lang, 'chooseOther'))),
      ]);
    } else {
      final choices = g?.choices ?? const <String>[];
      final top = <String>{...(g?.candidates ?? const <String>[])};
      children.addAll([
        Text(t(widget.lang, 'whatIsThis'), style: const TextStyle(fontWeight: FontWeight.w800, fontSize: 17)),
        const SizedBox(height: 10),
        Wrap(spacing: 8, runSpacing: 8, children: [
          for (final h in [...top, ...choices.where((c) => !top.contains(c))])
            ActionChip(
              avatar: CircleAvatar(backgroundColor: hostTint(h), child: Icon(hostIcon(h), size: 16, color: C.greenDark)),
              label: Text(_nice(h, widget.lang), style: TextStyle(fontWeight: top.contains(h) ? FontWeight.w800 : FontWeight.w500)),
              onPressed: () => _pick(h),
            ),
        ]),
      ]);
    }
    if (g != null && g.ok) {
      children.addAll([const SizedBox(height: 10), Text(t(widget.lang, 'demoNote'), style: const TextStyle(fontSize: 11.5, color: C.muted, height: 1.3))]);
    }
    return _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: children));
  }

  @override
  Widget build(BuildContext context) {
    final signs = _organism == 'livestock' ? _animalSigns : _cropSigns;
    return Scaffold(
      backgroundColor: const Color(0xFFF3F4F6),
      appBar: AppBar(title: Text(_organism == 'livestock' ? t(widget.lang, 'animals') : t(widget.lang, 'crops'))),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        ClipRRect(borderRadius: BorderRadius.circular(20), child: Image.file(File(widget.photoPath), height: 180, width: double.infinity, fit: BoxFit.cover)),
        const SizedBox(height: 14),
        _whatIsThis(),
        if (_host != null) ...[
          _card(Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(t(widget.lang, 'symptoms'), style: const TextStyle(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            Wrap(spacing: 8, runSpacing: 8, children: [
              for (final s in signs)
                FilterChip(
                  label: Text(s[1]),
                  selected: selected.contains(s[0]),
                  onSelected: (v) => setState(() => v ? selected.add(s[0]) : selected.remove(s[0])),
                ),
            ]),
            if (_organism == 'livestock')
              CheckboxListTile(contentPadding: EdgeInsets.zero, title: Text(t(widget.lang, 'dangerSigns')), value: danger, onChanged: (v) => setState(() => danger = v ?? false)),
            const SizedBox(height: 8),
            TextField(controller: notes, maxLines: 2, maxLength: 500, decoration: InputDecoration(labelText: t(widget.lang, 'extraNotes'), border: const OutlineInputBorder())),
          ])),
          const SizedBox(height: 8),
          FilledButton.icon(
            onPressed: () => Navigator.of(context).pushReplacement(MaterialPageRoute(
              builder: (_) => KnowledgeChatPage(
                lang: widget.lang,
                deviceId: widget.deviceId,
                hostKey: _host!,
                organismType: _organism,
                photoPath: widget.photoPath,
                symptomKeys: selected.toList(),
                dangerSigns: danger,
                notes: notes.text.trim(),
                hostConfirmed: true,
              ),
            )),
            icon: const Icon(Icons.chat_bubble_outline),
            label: Text(t(widget.lang, 'continueChat')),
          ),
        ],
      ]),
    );
  }
}
