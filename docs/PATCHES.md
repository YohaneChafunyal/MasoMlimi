# MasoMlimi: grounded multilingual chat + reply-to messages

New files (drop in as-is):
- `backend/app/kb_engine.py`: the chat engine (tested: `pytest backend/tests/test_kb_engine.py`, 15 pass)
- `backend/tests/test_kb_engine.py`
- `mobile/lib/chat_engine.dart`: online call + offline mirror of the same rules (NOT compiled here, no Dart SDK; run `flutter analyze`)

Design is untouched. Everything below is logic only.

---------------------------------------------------------------------------------------------------
## 1. backend/app/store.py

### 1a. content version (cache key for the index) and bump on delete
```python
def content_version() -> int:
    return _cursor
```
In `delete_procedure`, inside `if len(_procedures) < before:` add `global _cursor; _cursor += 1` before `_save_procedures()`
(add `global _procedures, _cursor` at the top of the function).

### 1b. approver + date on publish (safety rule 6)
```python
def publish_procedure(pid: str, approved_by: str = "", country: str = "MW") -> Optional[dict]:
    global _cursor
    with _lock:
        for p in _procedures:
            if p["id"] == pid:
                now = datetime.now(timezone.utc).isoformat()
                p.update(status="published", updated_at=now, approved_at=now,
                         approved_by=(approved_by or "").strip()[:120], country=(country or "MW").upper())
                _cursor += 1
                _save_procedures()
                return p
        return None
```

### 1c. source language + translations
In `add_procedure`'s `row`, add:
```python
"source_lang": body.get("source_lang") or next(iter((body.get("steps") or {"en": 1}).keys()), "en"),
"translation_status": body.get("translation_status") or {},
```
New function:
```python
def set_translation(pid, lang, title, steps, prevention, status="needs_review"):
    global _cursor
    with _lock:
        for p in _procedures:
            if p["id"] == pid:
                p.setdefault("title", {})[lang] = title
                p.setdefault("steps", {})[lang] = steps
                p.setdefault("prevention_steps", {})[lang] = prevention
                p.setdefault("translation_status", {})[lang] = status   # "reviewed" only via native reviewer
                p["updated_at"] = datetime.now(timezone.utc).isoformat()
                _cursor += 1
                _save_procedures()
                return p
        return None
```

### 1d. reply-to for chat (replace `post_chat`, add two helpers)
```python
def get_message(thread_id: str, msg_id: str) -> Optional[dict]:
    if not msg_id:
        return None
    with _lock:
        for m in _chats.get(thread_id, []):
            if m.get("id") == msg_id or (m.get("client_id") and m.get("client_id") == msg_id):
                return m
    return None

def _preview(m: dict) -> dict:
    text = m.get("text") or ""
    is_voice = m.get("type") == "audio_note" or "[voice_note:" in text or "[Voice note]" in text
    return {"id": m["id"], "sender": m.get("sender"), "type": "audio_note" if is_voice else m.get("type", "text"),
            "text": "" if is_voice else text[:140]}

def post_chat(thread_id, sender, text, msg_type="text", client_id=None, reply_to=None) -> dict:
    with _lock:
        existing = _chats.get(thread_id, [])
        if client_id:
            for prev in existing:
                if prev.get("client_id") == client_id:
                    return prev
        if msg_type == "audio_note" and text:
            for prev in reversed(existing[-12:]):
                if prev.get("type") == "audio_note" and prev.get("text") == text:
                    return prev
        if text and existing and not client_id:
            last = existing[-1]
            if (last.get("sender") == sender and last.get("text") == text and last.get("type") == msg_type
                    and (last.get("reply_to") or "") == (reply_to or "")):
                return last
        target = get_message(thread_id, reply_to) if reply_to else None
        msg = {"id": str(uuid.uuid4()), "thread_id": thread_id, "sender": sender, "type": msg_type, "text": text,
               "client_id": client_id or "", "at": datetime.now(timezone.utc).isoformat(),
               "reply_to": target["id"] if target else "", "reply_preview": _preview(target) if target else None}
        _chats.setdefault(thread_id, []).append(msg)
        _save_chats_disk()
        return msg
```
(The 15 s audio double-POST collapse is dropped because `client_id` now makes retries idempotent; the farmer app already sends one.)

---------------------------------------------------------------------------------------------------
## 2. backend/app/main.py

### 2a. imports
```python
from app import kb_engine
```

### 2b. chat models and routes (reply-to)
```python
class ChatIn(BaseModel):
    device_id: str
    expert_id: str
    text: str
    sender: str = "farmer"
    msg_type: str = "text"
    client_id: Optional[str] = None
    reply_to: Optional[str] = None
```
`post_chat` route: `msg = store.post_chat(tid, body.sender, body.text, body.msg_type, client_id=body.client_id, reply_to=body.reply_to)`

WebSocket: `msg = store.post_chat(tid, sender, text, msg_type, client_id=data.get("client_id"), reply_to=data.get("reply_to"))`

Voice route: add param `reply_to: str = Form("")` and
`msg = store.post_chat(tid, sender, f"[voice_note:{name}]", "audio_note", client_id=client_id or None, reply_to=reply_to or None)`

### 2c. publish records the approver
```python
@app.post("/v1/procedures/{pid}/publish")
async def publish(pid: str, request: Request):
    approver = request.headers.get("X-Approver", "")
    row = store.publish_procedure(pid, approved_by=approver, country=request.headers.get("X-Country", "MW"))
    if not row:
        raise HTTPException(404, "Not found")
    return row
```
(Launch gate: protect with `security.require_api_key` and a real two-reviewer rule for serious diseases and dose/drug content.)

### 2d. translations (health/safety text stays `needs_review` until a native reviewer sets `reviewed`)
```python
class TranslationIn(BaseModel):
    lang: str
    title: str
    steps: List[str] = []
    prevention_steps: List[str] = []
    status: str = "needs_review"

@app.put("/v1/procedures/{pid}/translation")
def put_translation(pid: str, body: TranslationIn, request: Request):
    if not security.require_api_key(request.headers.get("X-API-Key")):
        raise HTTPException(401, "Invalid or missing X-API-Key")
    if body.lang not in kb_engine.LANGS:
        raise HTTPException(422, "unsupported language")
    row = store.set_translation(pid, body.lang, body.title, body.steps, body.prevention_steps, body.status)
    if not row:
        raise HTTPException(404, "Not found")
    return row
```

### 2e. library upload keeps the file's language (so a Chichewa PDF is stored under `ny`, not `en`)
Add `lang: str = Form("en")` to `library_upload`; then in the `store.add_procedure({...})` call use
```python
lang_k = lang if lang in kb_engine.LANGS else "en"
"title": {lang_k: str(title_en)[:200]},
"steps": {lang_k: step_list},
"prevention_steps": {lang_k: prev},
"source_lang": lang_k,
```
and send `fd.append('lang', ...)` from the portal (see section 5).

### 2f. replace `/v1/knowledge/chat` completely (delete `optional_llm_grounded` too)
```python
def llm_translate_grounded(context: str, lang: str) -> str:
    """Optional. Translate ONLY the given approved text. Output is number-verified before use."""
    key = os.environ.get("MASOMLIMI_LLM_API_KEY", "").strip()
    if not key or not context.strip():
        return ""
    names = {"ny": "Chichewa", "fr": "French", "sw": "Swahili", "pt": "Portuguese", "en": "English"}
    try:
        import urllib.request
        body = json.dumps({
            "model": os.environ.get("MASOMLIMI_LLM_MODEL", "gpt-4o-mini"), "temperature": 0,
            "messages": [
                {"role": "system", "content": (
                    f"Translate the text between <approved> tags into {names.get(lang, 'English')}. "
                    "Translate only. Do not add, remove, explain or reorder advice. Do not add numbers, "
                    "product names or doses. Keep line breaks and bullets. Output the translation only.")},
                {"role": "user", "content": f"<approved>\n{context[:8000]}\n</approved>"}]}).encode()
        req = urllib.request.Request(
            os.environ.get("MASOMLIMI_LLM_BASE", "https://api.openai.com/v1/chat/completions"), data=body,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return (json.loads(resp.read().decode())["choices"][0]["message"]["content"] or "").strip()
    except Exception:
        return ""


@app.post("/v1/knowledge/chat")
async def knowledge_chat(body: dict):
    message = str(body.get("message") or body.get("text") or "")
    lang = body.get("language") if body.get("language") in kb_engine.LANGS else "en"
    host_in = body.get("host_key") or body.get("host") or ""
    host = store.normalize_host_key(host_in) if host_in else ""
    idx = kb_engine.get_index(store.list_procedures(include_draft=False), store.content_version())
    ans = kb_engine.answer(idx, message, lang, host, str(body.get("description") or ""),
                           critical_steps=store.critical_steps, normalize_host=store.normalize_host_key)
    # images: only those joined to the procedure we answered from
    if ans["outcome"] in ("answer", "catalog") and host:
        try:
            bun = store.resolve_condition_bundle(host, ans["passages"][0]["name"] if ans["passages"] else "", lang)
            keep = set(ans.get("procedure_ids") or [])
            ans["images"] = [{"image_url": b["image_url"], "title": b["condition_name"]}
                             for b in bun.get("bundles", [])
                             if b.get("image_url") and (not keep or b.get("matched_procedure_id") in keep)][:3]
        except Exception:
            pass
    # model is used ONLY to translate approved text, never on emergency / not_sure / catalog paths
    if ans["outcome"] == "answer" and ans.get("needs_translation") and body.get("use_llm", True):
        t = llm_translate_grounded(ans["llm_context"], lang)
        if t and kb_engine.verify_llm_output(t, ans["llm_context"]):
            ans = kb_engine.finalize_translation(ans, t, lang)
    ans.pop("llm_context", None)
    ans.pop("text_parts", None)
    return ans


@app.get("/v1/sync/chatpack")
def chatpack():
    pack = kb_engine.build_pack(store.list_procedures(include_draft=False), store.CRITICAL, store.content_version())
    pack["signature"] = security.sign_payload(json.dumps({k: v for k, v in pack.items() if k != "signature"},
                                                         sort_keys=True, ensure_ascii=False, default=str))
    pack["alg"] = "HMAC-SHA256"
    return pack
```

### 2g. housekeeping bugs found while reading
- `/v1/scans/record` is defined twice. FastAPI uses the first one, so the API-key and device-hash version never runs. Delete the first (unauthenticated) definition.
- `store.published_corpus` / `retrieve_from_corpus` include raw `_library` text that is **not published**. That breaks safety rule 6. The new chat route no longer uses them; delete both once nothing else calls them.

---------------------------------------------------------------------------------------------------
## 3. mobile/lib/main.dart

### 3a. import and pack sync
```dart
import 'chat_engine.dart';
```
In `_AppState._init`, after `await OfflineCache.syncAll(kApiBase).catchError((_) => null);` add
`await ChatEngine.syncPack(kApiBase);`

### 3b. fix the broken `'pt'` map in `ui`
The last four keys (`rememberHost`, `lastNotes`, `noPackTip`, and a second `packLine`) sit **outside** the `'pt'` map, so Portuguese never gets them.
Move these three lines inside `'pt': { ... }` before its closing `},` and delete the stray ones after it:
```dart
    'rememberHost': 'Lembramos que isto é {h}. Pode atualizar o que vê, ou toque Obter conselho.',
    'lastNotes': 'Notas anteriores: {n}',
    'noPackTip': 'Um técnico deve Publicar um procedimento para {h}. Depois Quinta → Atualizar packs online.',
```

### 3c. new UI strings (add to the `extra` map inside `t()`)
```dart
    'reply': {'en': 'Reply', 'ny': 'Yankhani', 'fr': 'Répondre', 'sw': 'Jibu', 'pt': 'Responder'},
    'replyingTo': {'en': 'Replying to', 'ny': 'Mukuyankha', 'fr': 'Réponse à', 'sw': 'Unajibu', 'pt': 'A responder a'},
    'sourceLbl': {'en': 'Source', 'ny': 'Gwero', 'fr': 'Source', 'sw': 'Chanzo', 'pt': 'Fonte'},
```
(machine-drafted: native review needed)

### 3d. OfflineCache.flushOutbox: send `reply_to` and `client_id`
Voice branch, after `req.fields['client_id'] = ...`:
```dart
req.fields['reply_to'] = '${item['reply_to'] ?? ''}';
```
Text branch body:
```dart
body: jsonEncode({
  'device_id': item['device_id'], 'expert_id': item['expert_id'], 'text': item['text'],
  'sender': item['sender'] ?? 'farmer', 'msg_type': item['msg_type'] ?? 'text',
  'client_id': item['client_id'] ?? item['id'],
  'reply_to': (item['reply_to'] ?? '').toString().isEmpty ? null : item['reply_to'],
}),
```

### 3e. OfflineCache.dedupeMessages: a reply must not be collapsed into an earlier identical message
```dart
final tkey = '${m['sender']}|$text|${m['reply_to'] ?? ''}';
...
final idx = out.indexWhere((x) =>
    x is Map && '${x['sender']}|${x['text']}|${x['reply_to'] ?? ''}' == tkey && '${x['id']}'.startsWith('local-'));
```

### 3f. ExpertChatPage: reply to a message or voice note
State:
```dart
Map? _replyTo; // the message being answered

void _setReply(Map m) => setState(() => _replyTo = Map.from(m));

Map<String, dynamic>? _previewOf(Map m) {
  final text = '${m['text'] ?? ''}';
  final voice = m['type'] == 'audio_note' || text.contains('[voice_note:') || text.contains('[Voice note]');
  return {'id': m['id'], 'sender': m['sender'], 'type': voice ? 'audio_note' : (m['type'] ?? 'text'),
          'text': voice ? '' : (text.length > 140 ? text.substring(0, 140) : text)};
}
```
Server id if known, otherwise the client id (the server accepts either):
```dart
String _replyKey(Map m) {
  final id = '${m['id'] ?? ''}';
  return id.startsWith('local-') ? '${m['client_id'] ?? id}' : id;
}
```
In `send(...)` build the local message and outbox item with the reply:
```dart
final reply = _replyTo;
final cid = 'tx-${DateTime.now().millisecondsSinceEpoch}';
final localMsg = {
  'id': 'local-${DateTime.now().millisecondsSinceEpoch}', 'client_id': cid, 'sender': 'farmer', 'type': type,
  'text': body, 'at': DateTime.now().toIso8601String(), 'pending_sync': true,
  if (reply != null) 'reply_to': _replyKey(reply),
  if (reply != null) 'reply_preview': _previewOf(reply),
};
await OfflineCache.enqueueOutbox({
  'type': 'text', 'device_id': widget.deviceId, 'expert_id': widget.expertId, 'sender': 'farmer',
  'text': body, 'msg_type': type, 'client_id': cid, if (reply != null) 'reply_to': _replyKey(reply),
});
setState(() => _replyTo = null);
```
In `_sendVoiceFile`, add `if (_replyTo != null) 'reply_to': _replyKey(_replyTo!)` to the `enqueueOutbox` map and to `localMsg`
(`'reply_preview': _previewOf(_replyTo!)`), then `setState(() => _replyTo = null)` after queuing.

Bubble: wrap the bubble `Container` in a gesture detector (swipe right or long-press = reply) and add the quote block as the first child of its `Column`:
```dart
return Align(
  alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
  child: GestureDetector(
    onLongPress: () => _setReply(m),
    onHorizontalDragEnd: (d) { if ((d.primaryVelocity ?? 0) > 150) _setReply(m); },
    child: Container( /* existing decoration */
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        if (m['reply_preview'] is Map) _quote(m['reply_preview'] as Map),
        /* existing audio / video / text children */
      ]),
    ),
  ),
);
```
```dart
Widget _quote(Map q) {
  final voice = q['type'] == 'audio_note';
  final who = q['sender'] == 'farmer' ? t(widget.lang, 'you') : widget.expertName;
  return Container(
    margin: const EdgeInsets.only(bottom: 6),
    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
    decoration: BoxDecoration(color: Colors.black.withValues(alpha: 0.05), borderRadius: BorderRadius.circular(8),
        border: const Border(left: BorderSide(color: C.greenDark, width: 3))),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text(who, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: C.greenDark)),
      Row(mainAxisSize: MainAxisSize.min, children: [
        if (voice) const Icon(Icons.mic, size: 13),
        if (voice) const SizedBox(width: 4),
        Flexible(child: Text(voice ? t(widget.lang, 'voiceNote') : '${q['text'] ?? ''}',
            maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12))),
      ]),
    ]),
  );
}
```
Reply bar: insert between the `_recording` banner and the input row:
```dart
if (_replyTo != null)
  Container(
    width: double.infinity, color: Colors.white,
    padding: const EdgeInsets.fromLTRB(12, 6, 4, 6),
    child: Row(children: [
      Expanded(child: _quote(_previewOf(_replyTo!)!)),
      IconButton(icon: const Icon(Icons.close), onPressed: () => setState(() => _replyTo = null)),
    ]),
  ),
```
Server messages already carry `reply_to` and `reply_preview`, so quotes show up identically for synced and offline messages.

### 3g. KnowledgeChatPage: use the engine, drop the client-side word swapping
1. Replace `_loadAdvice` and `_askLibrary` with:
```dart
String _symptomText() => '${_answers['part'] ?? ''} ${_answers['signs'] ?? ''} ${_answers['context'] ?? ''}'.trim();

Future<ChatAnswer> _ask(String q) => ChatEngine.ask(
      apiBase: kApiBase, message: q, lang: widget.lang,
      hostKey: normalizeHost(_confirmedHost.isNotEmpty ? _confirmedHost : widget.hostKey),
      description: _symptomText(), deviceId: widget.deviceId);

Future<ChatAnswer> _loadAdvice() => _ask(_symptomText());
```
`translateTo()` is no longer applied to engine replies (the server already answers in the farmer's language; the old word-replace turned "Water" into "Madzi" inside English sentences).

2. Replace each `final advice = await _loadAdvice();` + `_msgs.add({'role': 'bot', 'text': advice});` with
```dart
final ans = await _loadAdvice();
final advice = ans.text;
...
_msgs.add(ans.toBubble());
```
(3 places: `_send` twice, and the "Get advice" button).

3. At the top of `_send`, right after the user bubble is added, run the fixed emergency check on **every** message:
```dart
final em = await ChatEngine.emergencyIfAny(text, widget.lang, normalizeHost(_confirmedHost.isNotEmpty ? _confirmedHost : widget.hostKey));
if (em != null) {
  if (!mounted) return;
  setState(() { _msgs.add(em.toBubble()); _busy = false; });
  return;
}
```
4. The free-question branch at the end of `_send` becomes:
```dart
final ans = await _ask(text);
if (!mounted) return;
setState(() { _msgs.add(ans.toBubble()); _busy = false; });
```
5. Bubble rendering: confidence, sources and quick replies (same cards, only extra children). In the `itemBuilder`, replace the bubble's `decoration` colour/border and children:
```dart
final emergency = (m['emergency'] ?? '').isNotEmpty;
final band = m['band'] ?? '';
final bandColor = emergency ? C.red : band == 'high' ? C.greenDark : band == 'medium' ? C.amber : band == 'low' && bot && (m['band_label'] ?? '').isNotEmpty ? C.muted : null;
...
decoration: BoxDecoration(
  color: emergency ? C.redSoft : (bot ? Colors.white : C.green.withValues(alpha: 0.15)),
  borderRadius: BorderRadius.circular(14),
  border: Border.all(color: bandColor ?? const Color(0xFFE5E7EB), width: emergency ? 2 : 1),
),
...
children: [
  if ((m['band_label'] ?? '').isNotEmpty && !emergency)
    Padding(padding: const EdgeInsets.only(bottom: 4),
      child: Text(m['band_label']!, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: bandColor ?? C.muted))),
  if ((m['text'] ?? '').isNotEmpty) Text(m['text']!, style: const TextStyle(height: 1.35)),
  /* existing image block */
  if ((m['quick'] ?? '').isNotEmpty)
    Padding(padding: const EdgeInsets.only(top: 8),
      child: Wrap(spacing: 6, runSpacing: 6, children: [
        for (final q in m['quick']!.split('|'))
          ActionChip(label: Text(q), onPressed: () { _ctrl.text = q; _send(); }),
      ])),
],
```
Confidence is shown as words and colour (never a percentage), as the spec requires. Emergency bubbles are red, with fixed safe first actions only.

---------------------------------------------------------------------------------------------------
## 4. Expert portal (portal/index.html and backend/portal/index.html)

CSS:
```css
.msg .quote { border-left: 3px solid #0F6B36; background: rgba(0,0,0,.05); border-radius: 6px; padding: 4px 8px; margin-bottom: 4px; font-size: 12px; }
.msg .rbtn { background: none; border: 0; color: #0F6B36; font-weight: 700; cursor: pointer; font-size: 12px; padding: 0; margin-left: 8px; }
#replyBar { display: none; background: #f3f4f6; border-left: 3px solid #0F6B36; border-radius: 8px; padding: 6px 10px; margin-top: 8px; font-size: 13px; }
```
HTML: directly above the reply input row add `<div id="replyBar"></div>`.

JS (inside the IIFE):
```js
var replyTo = null;
function previewText(m) {
  var t = m.text || '';
  return (m.type === 'audio_note' || t.indexOf('[voice_note:') >= 0) ? 'Voice note' : t.slice(0, 140);
}
function setReply(m) {
  replyTo = m;
  var bar = document.getElementById('replyBar');
  bar.style.display = 'block';
  bar.innerHTML = '';
  bar.appendChild(document.createTextNode('Replying to ' + (m.sender === 'expert' ? 'yourself' : 'farmer') + ': ' + previewText(m) + '  '));
  var x = document.createElement('button'); x.className = 'rbtn'; x.textContent = 'cancel';
  x.onclick = function () { replyTo = null; bar.style.display = 'none'; };
  bar.appendChild(x);
}
```
In `appendMsg`, before the voice/text branches add the quote, and after building `d` add the reply button (the text branch must not wipe children, so use `appendChild`):
```js
if (m.reply_preview) {
  var q = document.createElement('div'); q.className = 'quote';
  q.textContent = (m.reply_preview.sender === 'expert' ? 'You' : 'Farmer') + ': ' +
                  (m.reply_preview.type === 'audio_note' ? 'Voice note' : (m.reply_preview.text || ''));
  d.appendChild(q);
}
...
// replace  d.textContent = who + ': ' + text;  with:
d.appendChild(document.createTextNode(who + ': ' + text));
...
var rb = document.createElement('button'); rb.className = 'rbtn'; rb.textContent = 'Reply';
rb.onclick = function () { setReply(m); };
d.appendChild(rb);
```
In the voice branch use `d.insertAdjacentHTML` only for the header (it already sets `innerHTML` first, so put the quote **after** that line).
Send handler body:
```js
body: JSON.stringify({ device_id: deviceId, expert_id: expertId, text: text, sender: 'expert', msg_type: 'text',
                       client_id: 'px-' + Date.now(), reply_to: replyTo ? replyTo.id : null })
```
then clear it: `replyTo = null; document.getElementById('replyBar').style.display = 'none';`
Voice recording upload: `if (replyTo) fd.append('reply_to', replyTo.id);` before the `fetch`, and clear `replyTo` after sending.

Library upload: add a language `<select id="lib_lang">` (en/ny/fr/sw/pt) and `fd.append('lang', document.getElementById('lib_lang').value);`
Publish button: send the officer's name, `headers: { 'X-Approver': prompt('Your name (approver):') || '' }`

---------------------------------------------------------------------------------------------------
## 5. Launch gates this change creates (add to LAUNCH_GATES.md)
1. Native-speaker review of `kb_engine.UI` (ny, sw, fr, pt) and of `LEXICON`. They are machine-drafted and flagged `ui_review_status: needs_native_review`.
2. Calibrate `MIN_COVERAGE` / `HIGH_COVERAGE` on an expert-labelled question set per language (target: wrong-answer rate on confident replies ≤ 10%, danger misses = 0).
3. Entries for serious diseases need the `is_dangerous` / `reportable` flag set by a vet (the engine also detects it from the title). Add the two-reviewer rule in the publish flow.
4. Doses stay hidden until a vet sets `dose_verified` with an official citation (portal field still to build).
5. Translations of each approved procedure must be authored and reviewed by native experts (`PUT /v1/procedures/{id}/translation`, status `reviewed`).
6. Verify the chat-pack signature on the phone (stub marked TODO in `chat_engine.dart`). The HMAC secret must not ship in the app, so move to asymmetric signing.
