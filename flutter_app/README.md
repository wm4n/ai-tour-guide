# AI Tour Guide — Flutter App

Flutter front-end for the AI Tour Guide, consuming the Plan A FastAPI backend.

## Prerequisites

- Flutter 3.x (`flutter --version`)
- A Google Maps API key with Maps SDK for Android + iOS enabled
- Plan A backend running locally (`cd ../backend && uvicorn tour_guide.main:app --reload`)

## Setup

1. **Clone and install:**
   ```bash
   flutter pub get
   dart run build_runner build --delete-conflicting-outputs
   ```

2. **Configure Google Maps API keys:**
   - Android: edit `android/app/src/main/AndroidManifest.xml`, replace `YOUR_ANDROID_MAPS_API_KEY`
   - iOS: edit `ios/Runner/AppDelegate.swift`, replace `YOUR_IOS_MAPS_API_KEY`

## Running

```bash
# Android Emulator (backend at 10.0.2.2:8000)
flutter run --dart-define-from-file=dart_defines/dev.json

# iOS Simulator (backend at localhost:8000)
flutter run --dart-define=BACKEND_URL=http://localhost:8000

# Real device on same WiFi (replace with your machine's IP)
flutter run --dart-define=BACKEND_URL=http://192.168.1.x:8000
```

## Testing

```bash
# All tests (unit + widget + integration)
flutter test

# Single file
flutter test test/unit/sse_parser_test.dart -v
```

## App Flow

1. Launch → HomeScreen shows 「歷史大叔」persona + 「開始旅程」 button
2. Tap → Grants location permission → MapScreen opens
3. Map shows nearby POI markers (blue=high confidence, yellow=medium, red=low)
4. Walk within 100m of POI → Auto-trigger narration (or tap marker to trigger manually)
5. NarrationSheet slides up from bottom → Shows subtitle + progress + pause/skip controls
6. Tap 「結束」 → Session ends, returns to HomeScreen
