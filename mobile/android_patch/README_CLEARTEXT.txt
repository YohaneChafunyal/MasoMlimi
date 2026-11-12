
CRITICAL for farmer app to reach API on emulator:

1. Open:
   mobile/android/app/src/main/AndroidManifest.xml

2. On the <application> tag, add:
   android:usesCleartextTraffic="true"

3. Save, then:
   flutter clean
   flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8000

Without this, Android blocks http://10.0.2.2:8000 and Result never shows published steps.

Also ensure API:
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
