# District pilot (≈200 farmers) — security notes

## What is production-ready for a closed pilot
- Diagnosis returns only expert-published steps or fixed critical safety text
- Procedures persist to `backend/app/data/procedures.json`
- Optional API key: set env `MASOMLIMI_API_KEY` — portal must send header `X-API-Key`
- Security headers: nosniff, deny framing
- CORS open for pilot apps; restrict origins before public internet deploy
- Cleartext HTTP only on LAN / adb reverse — use HTTPS + reverse proxy for real field WAN

## Deploy checklist
1. `export MASOMLIMI_API_KEY='long-random-secret'`
2. `export MASOMLIMI_DISTRICT='Lilongwe'`
3. `uvicorn app.main:app --host 0.0.0.0 --port 8000`
4. Put nginx/Caddy TLS in front for phones on mobile data
5. Farmers: same signed APK; API_BASE = https://your-domain
6. Do not expose portal without API key + VPN or basic auth

## Not included yet (launch gates)
- Full auth (JWT) for experts
- Postgres multi-instance
- Independent penetration test
- Per-country legal review of safety messages
