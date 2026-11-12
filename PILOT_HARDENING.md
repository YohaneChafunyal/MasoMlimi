# Pilot hardening checklist

## 1. Real-device mic
- Test on 3+ physical Android phones (not emulator only).
- Grant RECORD_AUDIO; speak 3+ seconds; confirm Play on phone and portal.
- Target: >90% successful capture on real devices before scale-up.

## 2. HTTPS + auth
- Put API behind Caddy or Nginx with TLS certificates.
- Set environment: `MASOMLIMI_API_KEY`, `MASOMLIMI_PACK_SECRET`.
- Portal and mobile should use `https://your-domain` only on public networks.
- Cleartext HTTP only on private LAN pilot.

## 3. Push notifications
- `POST /v1/push/register` stores device tokens.
- Production: send via Firebase Cloud Messaging when officer replies or outbreak alert publishes.
- App should call register after login/device id is known (stub ready).

## 4. Hardening / pen-test
- Independent security review before public release.
- Rate-limit diagnose/chat endpoints at reverse proxy.
- Do not expose portal unauthenticated on the internet.

## 5. API restart monitoring
- Chat and knowledge now file-backed under `backend/data/` (chats.json, contributions.json, kb_memory.json).
- `GET /health` returns `uptime_started_at` for process monitors.
- Use systemd/Docker restart + disk volume for `data/`.
- Optional: uptime kuma / healthchecks.io on `/health`.

## Knowledge safety
- Farmer post-scan chat saves **observations** only (`pending_expert_review`).
- Treatment steps still require expert **Publish**.
- Chatbot answers only from **published** procedures + shared descriptive memory.
