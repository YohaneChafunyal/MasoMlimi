# Deploy and security checklist

Run: `cd backend && uvicorn app.main:app --host 127.0.0.1 --port 8000` behind a TLS reverse proxy (nginx/Caddy).
Expert portal: `https://your-host/portal/` (asks for the API key; kept in sessionStorage only).

## Built in (tested in backend/tests/test_api.py)
- Expert/admin endpoints need X-API-Key (constant-time compare). No key configured = denied.
- 10 failed keys in 5 minutes locks that IP out; per-route rate limits (scan 12/min, chat 40/min, uploads 20/min, 600/min overall).
- Farmers can never post as an expert (REST, voice, WebSocket).
- Strict ids (device/expert/voice filename), pydantic limits on every body, JSON cap 1 MB, uploads cap 25 MB.
- Uploads: magic-byte checks (PDF/DOCX/TXT/images; audio), safe filenames, path-traversal checks, zip-bomb guard.
- Source documents and unpublished images are not downloadable without the key. Public library never contains raw text.
- Chat history encrypted at rest when MASOMLIMI_DATA_KEY is set. Atomic writes.
- Editing a published procedure returns it to draft (re-review). Doses need a named approver + official source.
- Case memory: hashed device id, district only, tokens not raw text, k>=3 before anything is shown, 180-day retention, delete-my-data.
- No wildcard CORS, security headers, CSP on the portal (portal builds DOM with textContent, never innerHTML).

## You still must do (cannot be done in code)
1. Generate MASOMLIMI_API_KEY / PACK_SECRET / DATA_KEY; keep them in a vault, not in git. Rotate if shared.
2. TLS only (the Android manifest currently allows cleartext for the emulator: remove `usesCleartextTraffic` for release).
3. One API key = one shared secret. Before production give each expert their own login (phone + one-time code) and two-step for admins.
4. Move JSON files to PostgreSQL + private object storage; encrypted backups with restore tests.
5. Sign content packs with an asymmetric key and verify on the phone (HMAC secret cannot ship in the app).
6. Independent security test (OWASP MASVS/ASVS), dependency scanning, signed releases.
7. Legal review of the case memory and consent screens per country.
