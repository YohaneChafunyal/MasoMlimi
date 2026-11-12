# Apply MasoMlimi logo (replace Flutter default)

## Method A — automatic (recommended)

```powershell
cd mobile
flutter pub get
dart run flutter_launcher_icons
```

This uses `assets/icon.png` (green shield + plant).

## Method B — copy pre-made mipmaps

After `flutter create .`, copy from `android_icons/` into:

```
android/app/src/main/res/mipmap-mdpi/ic_launcher.png
android/app/src/main/res/mipmap-hdpi/ic_launcher.png
... (all densities)
```

Also copy `ic_launcher_round.png` the same way.

Then uninstall the old app from the emulator and reinstall:

```powershell
flutter run -d emulator-5554 --dart-define=API_BASE=http://10.0.2.2:8000
```

(Android caches launcher icons; reinstall clears the Flutter logo.)
