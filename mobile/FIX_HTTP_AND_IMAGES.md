# Fix: published steps not showing + host images

## A. Allow HTTP to local API (main cause)

Edit `android/app/src/main/AndroidManifest.xml`

On `<application ...>` add:

```xml
android:usesCleartextTraffic="true"
```

Then:

```bat
flutter clean
flutter pub get
flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8000
```

On Result top card you must see:
- Expert-published guidance
- Outcome: published_guidance
- API: http://10.0.2.2:8000

If you see "Could not load from server", cleartext or API_BASE is still wrong.

## B. Host images

Copy `assets/hosts/*.png` into your project and ensure pubspec has:

```yaml
  assets:
    - assets/hosts/
```

Check page shows maize, rice, chicken, etc. image tiles.
