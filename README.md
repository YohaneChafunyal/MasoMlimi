# MasoMlimi Full Stack

## My Farm (analytics UI)
Green gradient weekly-checks card, stat tiles (hosts / alerts / published guides), soft list cards for farm items, alerts, recent activity.

## Run
Backend: `cd backend && pip install -r requirements.txt && uvicorn app.main:app --host 0.0.0.0 --port 8000`
Mobile: copy lib/ + assets/, `flutter pub get && dart run flutter_launcher_icons && flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8000 192.168.0.118`
Portal: `cd portal && python -m http.server 5500` → http://127.0.0.1:5500/index.html

Safety: published procedures only; critical livestock = fixed safety + refer.
## flutter run -d emulator-5554 --dart-define=API_BASE=http://127.0.0.1:8000
## flutter build apk --release --dart-define=API_BASE=http://192.168.1.136:8000
## python -m uvicorn app.main:app --host 0.0.0.0 --port 8000