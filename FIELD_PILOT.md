# MasoMlimi field pilot checklist (20–80 farmers, one district)

## Must do before leaving the office

### 1. Always online once after install (download packs)
- [ ] API running: `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000`
- [ ] Phone/emulator on same path as API (`adb reverse` or LAN IP)
- [ ] Open app → **My Farm** shows **Online**
- [ ] Check `GET /v1/pilot/status` → `ready_for_field_pilot: true`
- [ ] On phone: guides/experts counts > 0 (offline pack written under app documents)

### 2. Publish procedures (drafts never reach farmers)
- [ ] Portal → upload library/PDF if needed → review **drafts**
- [ ] **Publish** only verified steps (no invented medicines)
- [ ] `GET /v1/procedures` returns only published for the app
- [ ] Farmer scan shows published steps only

### 3. Real-device mic test
- [ ] Physical Android phone (not only emulator)
- [ ] Microphone permission granted
- [ ] Record ≥2 seconds of speech → one bubble → Play on phone
- [ ] Same note Play on portal
- [ ] Empty/short recordings blocked (no silent upload)

### 4. Same Wi-Fi / correct API_BASE
- [ ] Phone APK built with: `--dart-define=API_BASE=http://PC_LAN_IP:8000`
- [ ] Browser on phone opens `http://PC_LAN_IP:8000/health`
- [ ] Windows firewall allows port 8000
- [ ] Emulator uses `http://127.0.0.1:8000` + `adb reverse tcp:8000 tcp:8000`

### 5. Photo-only ML (do NOT claim yet)
- [ ] Collect local labelled photos
- [ ] Train + held-out eval
- [ ] Safety review for dangerous diseases
- [ ] Until then: scan = published matching only (`photo_ml_certified: false`)

### 6. HTTPS + auth before public internet
- [ ] Reverse proxy TLS (Caddy/Nginx)
- [ ] Set `MASOMLIMI_API_KEY` for write endpoints
- [ ] Portal not exposed open to the world

### 7. Field pilot 20–80 farmers
- [ ] One district, verified officers registered
- [ ] No duplicate chat bubbles on latest app build
- [ ] Offline: packs present → scan still returns published advice when possible
- [ ] Online: chat + voice + new publishes sync on next open

## Day-of field workflow
1. Officer publishes morning updates on portal (Wi-Fi).
2. Farmers open app on Wi-Fi once (sync packs).
3. In the field (offline OK): Check → photo/signs → guidance from pack.
4. Critical / unsure → Experts chat (queues if offline).
5. Back online → outbox flushes; portal sees messages.

## Pass criteria for "go field"
- At least 1 published procedure per major host (maize, cassava, chicken, goats, …)
- ≥1 active officer
- Mic voice round-trip on a real phone
- Offline scan returns guidance after one prior sync
- Zero silent voice notes (rejected if too short)
