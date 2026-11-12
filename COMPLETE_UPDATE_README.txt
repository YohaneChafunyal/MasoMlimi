MasoMlimi — complete update pack (copy onto your PC project)

=== MOBILE (farmer app) ===
1. Replace:  mobile/lib/main.dart   <-- mobile-main.dart
2. Keep:     mobile/lib/theme.dart, pubspec.yaml, assets/
3. Rebuild:
   flutter pub get
   adb reverse tcp:8000 tcp:8000   (emulator)
   flutter run -d <device> --dart-define=API_BASE=http://192.168.1.136:8000
   OR release APK with same API_BASE

Includes:
- Officers: loads district=all (Dowa, Lilongwe, …)
- Offline cache: procedures, experts, chat
- Scan review + signs + photo upload to /v1/scan/analyze
- Live chat poll every 2s + offline offline
- Voice/video request buttons in chat

=== BACKEND (API) ===
Copy into apps/backend or backend/app/:
  main.py  store.py  extract.py
pip install pypdf python-multipart
$env:MASOMLIMI_API_KEY=""
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

Includes:
- GET /v1/experts/?district=all
- POST /v1/library/upload  (multi-file) + auto DRAFT extract
- POST /v1/scan/analyze    (photo + library ranking)
- WebSocket /v1/ws/chat/{device}/{expert}
- POST /v1/chat  (live broadcast)

=== PORTAL ===
Copy portal-index-NEW.html over portal served at /portal/
OR open http://PC_IP:8000/portal/

Tabs: Procedures | Officers | Farmer chat (live) | ML / reference library (uploads)

SAFETY: extracted treatments stay DRAFT until expert Publish.
