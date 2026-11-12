# Part 2: scan + chat learn from published vet content, and share memory across farmers

Apply on top of `PATCHES.md` (part 1). New backend files: `app/structure.py`, `app/memory.py`, `app/chat_service.py`;
`app/kb_engine.py` and `mobile/lib/chat_engine.dart` are **replaced** by the versions in this delivery.
Tests: `cd backend && pytest tests -q` -> 38 pass (parser, engine, dose gating, memory, chat+scan service).

## How it works

1. **Vet uploads a file** -> `structure.drafts_from_text` splits it into **one draft per condition** and files each line under
   the heading it was written under: type, signs, symptoms, treatment, medication, dose (incl. withdrawal), prevention,
   when to refer. Text under no heading is never promoted to treatment or dose.
2. **Vet reviews and publishes.** Doses are shown to farmers **only if the publishing vet ticks "dose verified" and types the
   official source** (`dose_verified` + `dose_source`). Otherwise doses and withdrawal times stay hidden and the farmer is told to
   ask a vet or agro-dealer (safety rule 4). Antibiotics/chemicals always carry "ask an expert first".
3. **Chat and scan use one engine** (`chat_service.py`): published content -> `kb_engine` -> memory -> answer in the farmer's language.
4. **Memory** (`memory.py`), anonymous, district-level, tokens not raw text:
   - **Similar cases from other farmers**: "N other farmers near you asked about a similar problem in the last 30 days", shown
     only when N >= 3 distinct devices.
   - **Did it help?** After each answer the farmer taps yes/no. Only "yes" cases nudge ranking, and only between candidates that
     already pass the confidence threshold. The engine can never reinforce its own unconfirmed guesses.
   - **Local words**: words farmers use that the vet text lacks (from >= 3 devices who said it helped) appear in the portal as
     suggestions. They affect matching only after an expert approves them. Experts can also type local names directly.
   - **Photo fingerprint** (dHash, needs Pillow): a weak "similar photo seen" hint, never a diagnosis.
   - **Outbreak watch candidates**: `/v1/memory/trends`. Alerts are still published by experts only.
   - Memory never edits advice, doses or emergency rules. Retention 180 days; `delete my data` supported.

## store.py

```python
def add_procedure(body: dict) -> dict:           # extend the row built in add_procedure with:
    ...
    "sections": body.get("sections") or {},
    "condition_type": body.get("condition_type") or "",
    "source_lang": body.get("source_lang") or next(iter((body.get("steps") or {"en": 1}).keys()), "en"),
    "translation_status": body.get("translation_status") or {},
    "dose_verified": False,        # only publish_procedure can set this
    "dose_source": "",

def update_procedure(pid: str, fields: dict) -> Optional[dict]:
    """Vet edits a DRAFT (sections, titles, steps, products) before publishing."""
    global _cursor
    allowed = {"title", "steps", "prevention_steps", "sections", "products", "condition_type", "is_dangerous", "reportable", "zoonotic"}
    with _lock:
        for p in _procedures:
            if p["id"] == pid:
                for k, v in fields.items():
                    if k in allowed:
                        p[k] = v
                p["updated_at"] = datetime.now(timezone.utc).isoformat()
                _cursor += 1
                _save_procedures()
                return p
    return None

def publish_procedure(pid, approved_by="", country="MW", dose_verified=False, dose_source=""):
    global _cursor
    if dose_verified and not (dose_source or "").strip():
        raise ValueError("dose_source (official citation) is required to verify a dose")
    with _lock:
        for p in _procedures:
            if p["id"] == pid:
                now = datetime.now(timezone.utc).isoformat()
                p.update(status="published", updated_at=now, approved_at=now, approved_by=(approved_by or "").strip()[:120],
                         country=(country or "MW").upper(), dose_verified=bool(dose_verified),
                         dose_source=(dose_source or "").strip()[:300])
                _cursor += 1
                _save_procedures()
                return p
    return None
```
(Launch gate: dose/drug content needs the two-reviewer rule; `approved_by` should come from the logged-in expert, not a header.)

## main.py

```python
from app import chat_service, memory, structure
```

### chat (replaces part-1 2f body; keep `llm_translate_grounded`)
```python
@app.post("/v1/knowledge/chat")
async def knowledge_chat(body: dict):
    return chat_service.chat(store, body, translate=llm_translate_grounded)
```

### scan (replaces the whole `scan_analyze`)
```python
@app.post("/v1/scan/analyze")
async def scan_analyze(
    host_key: str = Form(...), organism_hint: str = Form("crop"), language: str = Form("en"),
    device_id: str = Form(""), district: str = Form("Lilongwe"), symptom_keys: str = Form("[]"),
    notes: str = Form(""), danger_signs_present: bool = Form(False), image: UploadFile = File(...),
):
    raw = await image.read()
    if len(raw) > 12 * 1024 * 1024:
        raise HTTPException(400, "Photo too large")
    try:
        keys = [str(k) for k in json.loads(symptom_keys)][:30]
    except Exception:
        keys = []
    return chat_service.scan(store, host_key=host_key, organism=organism_hint, lang=language, device_id=device_id,
                             district=district, symptom_keys=keys, notes=notes[:1000], danger_flag=danger_signs_present,
                             image=raw, translate=llm_translate_grounded)
```
The photo is stored only as a fingerprint (no file kept). Strip EXIF before any future upload to storage.

### memory + expert endpoints
```python
class FeedbackIn(BaseModel):
    case_id: str
    helped: str            # "yes" | "no"

@app.post("/v1/memory/feedback")
def memory_feedback(body: FeedbackIn):
    if not chat_service.give_feedback(body.case_id, body.helped, store):
        raise HTTPException(404, "case not found")
    return {"ok": True}

@app.get("/v1/memory/trends")                      # portal: watch candidates (>=3 farmers)
def memory_trends(district: str = "", days: int = 14):
    return {"items": memory.trends(district, days)}

@app.get("/v1/memory/suggestions")                 # portal: local words waiting for an expert
def memory_suggestions(request: Request):
    return {"items": memory.suggestions()}

class AliasIn(BaseModel):
    pid: str
    token: str
    approved: bool = True

@app.post("/v1/memory/aliases/approve")
def memory_alias_approve(body: AliasIn, request: Request):
    if not security.require_api_key(request.headers.get("X-API-Key")):
        raise HTTPException(401, "Invalid or missing X-API-Key")
    if not memory.approve_alias(body.pid, body.token, body.approved):
        raise HTTPException(404, "suggestion not found")
    return {"ok": True}

@app.post("/v1/memory/aliases")                    # expert types a local name for a condition
def memory_alias_add(body: dict, request: Request):
    if not security.require_api_key(request.headers.get("X-API-Key")):
        raise HTTPException(401, "Invalid or missing X-API-Key")
    memory.add_alias(str(body.get("pid", "")), str(body.get("phrase", ""))[:80])
    return {"ok": True}

@app.post("/v1/memory/delete-my-data")
def memory_delete(body: dict):
    return {"deleted": memory.delete_device(chat_service.device_hash(str(body.get("device_id", ""))))}
```

### vet edit + publish with dose verification
```python
@app.put("/v1/procedures/{pid}")
async def edit_procedure(pid: str, request: Request):
    if not security.require_api_key(request.headers.get("X-API-Key")):
        raise HTTPException(401, "Invalid or missing X-API-Key")
    row = store.update_procedure(pid, await request.json())
    if not row:
        raise HTTPException(404, "Not found")
    return row

@app.post("/v1/procedures/{pid}/publish")
async def publish(pid: str, request: Request):
    try:
        data = await request.json()
    except Exception:
        data = {}
    try:
        row = store.publish_procedure(pid, approved_by=data.get("approved_by") or request.headers.get("X-Approver", ""),
                                      country=data.get("country", "MW"), dose_verified=bool(data.get("dose_verified")),
                                      dose_source=data.get("dose_source", ""))
    except ValueError as e:
        raise HTTPException(422, str(e))
    if not row:
        raise HTTPException(404, "Not found")
    return row
```

### chat pack (replaces part-1 `chatpack`)
```python
@app.get("/v1/sync/chatpack")
def chatpack():
    pack = kb_engine.build_pack(store.list_procedures(include_draft=False), store.CRITICAL,
                                (store.content_version(), memory.alias_version()),
                                aliases=memory.approved_aliases(), nearby=memory.nearby_counts("", 30))
    pack["signature"] = security.sign_payload(json.dumps({k: v for k, v in pack.items() if k != "signature"},
                                                         sort_keys=True, ensure_ascii=False, default=str))
    pack["alg"] = "HMAC-SHA256"
    return pack
```

### library upload: one draft per condition (replace the `if auto_draft:` block body)
```python
if auto_draft:
    full_text = built.get("full_text") or built.get("extracted_text_preview") or ""
    lang_k = lang if lang in kb_engine.LANGS else "en"
    drafts_local = []
    for d in structure.drafts_from_text(full_text, host_key or "maize", lang_k, f.filename or safe,
                                        title_override=condition_label or "",
                                        split_hosts=extract.split_document_by_hosts):
        proc = store.add_procedure(d)
        drafts_local.append(proc)
        try:
            store.link_library_procedure(row.get("id"), proc.get("id"))
        except Exception:
            pass
    if drafts_local:
        draft_info = {"procedure_ids": [p["id"] for p in drafts_local], "hosts": [p.get("host_key") for p in drafts_local],
                      "status": "draft", "count": len(drafts_local), "title": (drafts_local[0].get("title") or {}).get(lang_k),
                      "auto_extracted": True}
        drafts.append(draft_info)
```
(`lang: str = Form("en")` param, as in part 1 section 2e.) Scanned PDFs rely on OCR (pytesseract); check the draft text before publishing.

### cleanup
Remove the legacy `/v1/diagnosis/diagnose` home-treatment fallbacks from the farmer flow when you can. It still returns the old flat
structure; the app now uses chat/scan. Keep it for old clients only.

## Flutter (main.dart)

1. `import 'chat_engine.dart';` and `await ChatEngine.syncPack(kApiBase);` in `_init` (part 1).
2. `KnowledgeChatPage._ask` becomes the single entry point and passes the scan context, so a **photo scan** and a chat question use
   the same engine and memory:
```dart
Future<ChatAnswer> _ask(String q) => ChatEngine.ask(
      apiBase: kApiBase, message: q, lang: widget.lang,
      hostKey: normalizeHost(_confirmedHost.isNotEmpty ? _confirmedHost : widget.hostKey),
      description: _symptomText(), deviceId: widget.deviceId,
      photoPath: _adviceGiven ? null : widget.photoPath,     // upload the photo once, with the first advice request
      symptomKeys: widget.symptomKeys, danger: widget.dangerSigns);
Future<ChatAnswer> _loadAdvice() => _ask(_symptomText());
```
   and the emergency pre-check in `_send` passes `symptomKeys: widget.symptomKeys, danger: widget.dangerSigns`.
3. **"Did this help?"** In the bubble `itemBuilder`, after the quick-reply chips:
```dart
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
```
```dart
Future<void> _sendFeedback(int i, bool helped) async {
  final id = _msgs[i]['case_id'] ?? '';
  setState(() { _msgs[i].remove('fb_q'); _msgs[i].remove('fb_yes'); _msgs[i].remove('fb_no'); });
  await ChatEngine.feedback(kApiBase, id, helped);       // queued if offline
}
```
4. The old `LocalKb.similarAdvice` memory is no longer needed for advice (it stored advice text on the phone). Remove its use in
   `_loadAdvice`. The shared server memory replaces it; the engine now shows the "other farmers" note itself.
5. Optional: show the result colour (green/amber/red) on `ResultPage` from `result_color`. The scan response keeps all old fields.

## Portal

- **Drafts view**: render each draft's sections (type, signs, symptoms, treatment, medication, dose, prevention, refer) as editable
  fields; save with `PUT /v1/procedures/{id}` (`sections: {en: {...}}`, plus `title`, `steps`, `prevention_steps`).
- **Publish dialog**: officer name, checkbox "Dose and withdrawal verified", text box "Official source (required)". Send
  `POST /v1/procedures/{id}/publish` `{approved_by, dose_verified, dose_source}`.
- **Local names tab**: list `GET /v1/memory/suggestions`; Approve/Reject call `/v1/memory/aliases/approve`; a text box adds a name via
  `POST /v1/memory/aliases`.
- **Dashboard**: show `GET /v1/memory/trends` as "watch candidates", with a button that opens the existing alert form
  (experts publish alerts).

## Launch gates added (append to LAUNCH_GATES.md)
1. A vet reviews every auto-extracted draft. Scanned/OCR PDFs especially.
2. Dose/drug content: two-reviewer rule, official citation in `dose_source`, tested per country.
3. Native review of the new strings (`symptoms`, `medicines`, `dose_label`, `similar_seen`, `feedback_q`, ...) and of approved local words.
4. Calibrate coverage thresholds and the 0.3 prior weight on an expert-labelled set. Target: zero dangerous misses.
5. Privacy: legal review of the case memory (district + hashed device + tokens) per country; confirm k=3 and 180-day retention; wire "delete my data" in the app.
6. A validated photo model on local photos is still required before the photo itself can drive a diagnosis.
7. Replace shared-secret pack signing with asymmetric signing and verify on the phone.
