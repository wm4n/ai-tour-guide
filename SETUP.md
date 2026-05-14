# AI Tour Guide — Setup Guide

This guide covers local development setup and production deployment.

---

## Prerequisites

- Flutter SDK 3.x
- Python 3.12
- gcloud CLI (for backend deployment)
- Google Maps API Key (Android + iOS separately recommended)
- GCP project with billing enabled

---

## Local Development

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Copy env template
cp .env.example .env
# Edit .env — add GEMINI_API_KEY and optionally GOOGLE_PLACES_API_KEY

# Run tests
.venv/bin/pytest -v

# Start server
.venv/bin/uvicorn tour_guide.main:app --reload
```

### 2. Flutter (Android)

**Inject Maps API Key:**

Add the following line to `flutter_app/android/local.properties` (create if it doesn't exist):
```
MAPS_API_KEY=your-android-google-maps-api-key
```

> `local.properties` is gitignored — never commit your actual key.

**Run app:**
```bash
cd flutter_app
flutter pub get
flutter run --dart-define-from-file=dart_defines/dev.json
```

### 3. Flutter (iOS)

**Inject Maps API Key:**

```bash
# Create local config from example
cp flutter_app/ios/Flutter/LocalConfig.xcconfig.example \
   flutter_app/ios/Flutter/LocalConfig.xcconfig

# Edit LocalConfig.xcconfig — replace placeholder with your actual key:
# MAPS_API_KEY_IOS = your-ios-google-maps-api-key
```

> `LocalConfig.xcconfig` is gitignored — never commit your actual key.

**Run app:**
```bash
cd flutter_app
flutter pub get
flutter run --dart-define-from-file=dart_defines/dev.json
```

---

## Production Deployment

### Step 1: GCP Bootstrap (first time only)

```bash
# Configure deployment settings
cp scripts/.env.example scripts/.env
# Edit scripts/.env — set GCP_PROJECT_ID and other values

# Run bootstrap (idempotent)
bash scripts/setup-gcp.sh

# Add your API key to Secret Manager
echo -n "your-strong-api-key" | \
  gcloud secrets versions add api-key --data-file=-
```

### Step 2: Deploy Backend to Cloud Run

```bash
# Build Docker image and deploy
bash scripts/deploy-backend.sh

# Keep one instance warm (prevents cold starts, costs more)
bash scripts/deploy-backend.sh --min-instances 1
```

The script outputs the Cloud Run service URL.

### Step 3: Flutter Production Build

```bash
# Copy prod config template
cp flutter_app/dart_defines/prod.json.example \
   flutter_app/dart_defines/prod.json

# Edit prod.json:
# {
#   "BACKEND_URL": "https://your-service-url.run.app",
#   "API_KEY": "your-strong-api-key"
# }
```

**Android:**
```bash
cd flutter_app
flutter build apk --dart-define-from-file=dart_defines/prod.json
```

**iOS:**
```bash
cd flutter_app
flutter build ios --dart-define-from-file=dart_defines/prod.json
```

### Verify Deployment

```bash
# Test backend API (replace URL and key)
curl -H "X-Api-Key: your-key" https://your-service.run.app/health
# Expected: {"status": "ok"}
```

---

## Background Location Notes

### Android
- The app requests `ACCESS_BACKGROUND_LOCATION` at runtime
- A foreground notification appears when location tracking is active
- Users must grant "Allow all the time" permission for background tracking

### iOS
- The app uses `AppleSettings` with `allowBackgroundLocationUpdates: true`
- Users must grant "Always" location permission for background tracking
- A blue status bar appears when the app uses background location

---

## API Key Security

| Secret | Storage | Gitignored |
|--------|---------|-----------|
| `GEMINI_API_KEY` | `backend/.env` | Yes |
| `API_KEY` (backend auth) | GCP Secret Manager + `dart_defines/prod.json` | Yes |
| Android Maps Key | `flutter_app/android/local.properties` | Yes (Android default) |
| iOS Maps Key | `flutter_app/ios/Flutter/LocalConfig.xcconfig` | Yes |

**Never commit any of these files to git.**
