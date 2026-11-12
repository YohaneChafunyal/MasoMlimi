# Apply the update (about 10 minutes)

Copy this folder over your project root (it matches your structure), then:

## 1. Backend
- REPLACES: `backend/app/main.py`, `store.py`, `security.py`
- NEW: `backend/app/kb_engine.py`, `structure.py`, `memory.py`, `chat_service.py`, `doc_text.py`
- DELETE (no longer used): `backend/app/extract.py`, `backend/tests_test_api.py`, old `backend/tests/test_api.py` (replaced), `backend/portal/index.html` (the portal lives in `portal/`)
- Your existing JSON data in `backend/data` keeps working (procedures, experts, library, chats). Old chats stay readable; new ones are encrypted when MASOMLIMI_DATA_KEY is set.
- Existing PUBLISHED procedures have no `approved_by` / `dose_verified`: they keep working, but doses stay hidden until a vet re-publishes with a source.
```
cd backend
pip install -r requirements.txt
cp .env.example .env   # fill MASOMLIMI_API_KEY, PACK_SECRET, DATA_KEY (openssl rand -hex 32)
export $(grep -v '^#' .env | xargs)
pytest tests -q        # 54 tests
uvicorn app.main:app --host 127.0.0.1 --port 8000
```
## 2. Portal
- REPLACES `portal/index.html`. Open `/portal/`, enter the API key when asked.

## 3. Mobile
- NEW in `mobile/lib/`: `chat_engine.dart`, `offline_cache.dart`, `expert_chat_page.dart`, `knowledge_chat_page.dart`
- Patch your existing `main.dart` automatically (makes `main.dart.bak` first, refuses to write if anything looks wrong):
```
python tools/patch_main_dart.py mobile/lib/main.dart
cd mobile && flutter pub get && flutter analyze
```
- Release build: remove `android:usesCleartextTraffic="true"` and point `API_BASE` at your https URL.
- Android: the `record` and `audioplayers` imports move to the new chat file; no pubspec change needed.

## 4. First run checklist
1. Portal -> Library: upload a vet file (one block per condition, see structure in the upload card).
2. Procedures: review each draft, fill/verify sections, tick "dose verified" + official source ONLY if the source states it, Publish.
3. Phone: open app online once (downloads the offline chat pack), scan or chat, tap "Did this help?".
4. Portal -> Local names & watch: approve farmer words; publish watch alerts yourself.

See docs/DEPLOY_AND_SECURITY.md for the security checklist and what still needs people (key per expert, PostgreSQL, signed packs, legal review).

## 5. Re-process files uploaded with the OLD version (tools/reprocess_library.py)
Stop the API, then from the project root:
```
python tools/reprocess_library.py             # dry run: lists the conditions it finds in each stored PDF
python tools/reprocess_library.py --apply     # creates one DRAFT per condition (never publishes, never deletes)
```
Restart the API, open Portal -> Procedures, check each draft (crop/animal, sections, doses), delete the old whole-document
entries, and publish the good ones.

## 6. New: Crop/Livestock check flow, auto-suggest, and a conversational chat
- NEW `mobile/lib/scan_flow.dart` (Check page with two big buttons, photo, "This looks like ...", symptoms) and a rewritten
  `knowledge_chat_page.dart` (greets in the chosen language, thanks/goodbye/"what can you do", follow-up questions only when needed).
- Re-run the patcher (safe to run again; it adds the new strings and removes the old Check classes):
  `python tools/patch_main_dart.py mobile/lib/main.dart`  then  `flutter pub get && flutter analyze`
- Backend: replace `app/main.py`, `kb_engine.py`, `chat_service.py`; NEW `app/host_detector.py`. Restart the API.
- Auto-detection is a demo: read `docs/PHOTO_DETECTION.md` (without a model the app shows a list to pick from).
