
# Rename app to MasoMlimi + apply logo

## 1. Copy icon assets
- assets/icon.png  (launcher)
- assets/logo.png  (in-app)

## 2. pubspec.yaml
name: masomlimi
flutter_launcher_icons:
  android: true
  image_path: "assets/icon.png"

## 3. Android display name
Edit android/app/src/main/AndroidManifest.xml:

  android:label="MasoMlimi"

(not masomlimi_app)

## 4. Generate launcher icons
```
flutter pub get
dart run flutter_launcher_icons
flutter clean
flutter run ...
```

## 5. Optional applicationId (only if you want a clean package id)
In android/app/build.gradle.kts:
  applicationId = "com.masomlimi.pilot"
After changing applicationId, uninstall the old app from the device first.
