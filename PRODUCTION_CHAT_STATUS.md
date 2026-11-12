# MasoMlimi messaging — real-world status (pilot)

## What works when configured correctly

| Flow | Status |
|------|--------|
| Text online farmer ↔ officer | Works (API + portal poll/WS) |
| Voice online (file uploaded, both play) | Works if mic captures real audio and API reachable |
| Offline text/voice queue | Works (outbox on phone → flush when online) |
| One bubble after sync | Improved (client dedupe + server dedupe + portal rebuild list) |
| WhatsApp-level UX | Partial (tap mic; portal hold-to-record) — not full WhatsApp |

## Production reality (honest)

This is a **district pilot stack**, not WhatsApp or a carrier-grade messenger.

**Will work well in the field if:**
1. Phone and PC on same network with correct API_BASE (or adb reverse on emulator)
2. API process stays running; data files under backend/data persist
3. User grants microphone; records >1s of real speech
4. Latest app build with dedupeMessages
5. Portal loadChat rebuilds the list (no poll-append duplicates)

**Will NOT match WhatsApp yet:**
- No end-to-end encryption between farmer and officer
- No push notifications when app is killed
- No multi-device sync beyond one API server
- Voice is file upload (m4a/webm/wav), not streaming VoIP
- Emulator mic often fails — test on real phones
- HTTPS required before public internet

## Fixed in this pass
- Portal 2s poll no longer appends forever (clears and redraws)
- Message DOM ids prevent WS double-append
- Server skips duplicate same text/voice rapidly
- Voice file MIME types for browser play

## Verify (10 minutes)
1. API: health OK
2. Farmer text → portal shows once
3. Farmer voice → one bubble, Play on phone, Play on portal
4. Officer hold-record → farmer hears after refresh
5. Airplane mode → text → back online → one message on portal
6. No second copy of the same voice after 10 seconds
