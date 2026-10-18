# AI Tour Guide

A Flutter app that uses your device's GPS to detect nearby points of interest and narrates their stories in real-time using AI. The app streams audio narration as you walk past landmarks, temples, parks, and historic sites — like having a knowledgeable local guide in your pocket.

---

## Features

- **Automatic POI Detection** — Detects nearby points of interest using OpenStreetMap + Google Places data
- **AI-Generated Narration** — Streams text and audio narration via Gemini LLM + TTS
- **Multiple Personas** — Choose storytelling styles (e.g. history uncle, foodie critic)
- **Background Location** — Continues detecting POIs when screen is locked, sends local notifications
- **Q&A Mode** — Ask questions about a POI via voice, get spoken answers
- **Offline Caching** — Previously visited POIs and narrations are cached locally

---

## Architecture

```
┌─────────────────────────────────────────────────┐
│                 Flutter App (iOS / Android)      │
│                                                 │
│  GPS → TriggerEngine → BackendClient            │
│              ↓                 ↓                │
│         Notification      AudioPlayer           │
│         (background)      (foreground)          │
└──────────────────┬──────────────────────────────┘
                   │ HTTPS + X-Api-Key
                   ▼
┌─────────────────────────────────────────────────┐
│           FastAPI Backend (Cloud Run)            │
│                                                 │
│  /poi/nearby  →  Overpass + Google Places       │
│  /narration   →  Gemini LLM + Edge TTS (SSE)   │
│  /qa          →  Gemini STT + LLM + TTS        │
└─────────────────────────────────────────────────┘
```

**Tech Stack:**
- **Frontend:** Flutter 3.x / Dart 3.x / Riverpod / Google Maps
- **Backend:** Python 3.12 / FastAPI / LiteLLM / Edge TTS
- **Data:** OpenStreetMap (Overpass API) / Google Places API / Wikipedia
- **Infrastructure:** Google Cloud Run / Artifact Registry / Secret Manager

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Flutter SDK | 3.x | Mobile app |
| Python | 3.12+ | Backend |
| gcloud CLI | latest | GCP deployment |
| Docker | any | Local container testing (optional) |

---

## Local Development

### 1. Backend

```bash
cd backend

# Create Python virtual environment
python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"

# Configure environment
cp .env.example .env
# Edit .env and set GEMINI_API_KEY
```

Start the server:

```bash
.venv/bin/uvicorn tour_guide.main:app --reload
# Server runs at http://localhost:8000
```

Run tests:

```bash
.venv/bin/pytest -v
```

### 2. Flutter — Android

Add your Google Maps API key to `flutter_app/android/local.properties` (create if it doesn't exist):

```properties
MAPS_API_KEY=your-android-maps-api-key
```

> `local.properties` is gitignored — never commit your actual key.

Run the app:

```bash
cd flutter_app
flutter pub get
flutter run --dart-define-from-file=dart_defines/dev.json
```

### 3. Flutter — iOS

```bash
# Create local xcconfig from the example
cp flutter_app/ios/Flutter/LocalConfig.xcconfig.example \
   flutter_app/ios/Flutter/LocalConfig.xcconfig

# Edit LocalConfig.xcconfig and replace the placeholder:
# MAPS_API_KEY_IOS = your-ios-maps-api-key
```

> `LocalConfig.xcconfig` is gitignored — never commit your actual key.

```bash
cd flutter_app
flutter pub get
flutter run --dart-define-from-file=dart_defines/dev.json
```

---

## Deploying to Google Cloud

This section walks through deploying the backend to Cloud Run from scratch. No prior Google Cloud experience required.

### What you'll need

Before starting, obtain these API keys and save them somewhere safe:

| Key | Where to get it |
|-----|----------------|
| Gemini API Key | [Google AI Studio](https://aistudio.google.com/apikey) |
| Google Maps API Key (Android) | GCP Console → APIs & Services → Maps SDK for Android |
| Google Maps API Key (iOS) | GCP Console → APIs & Services → Maps SDK for iOS |
| Google Places API Key | GCP Console → APIs & Services → Places API |

---

### Step 1: Install and configure gcloud CLI

**Install gcloud CLI:**

- macOS: `brew install --cask google-cloud-sdk`
- Other platforms: https://cloud.google.com/sdk/docs/install

**Log in:**

```bash
gcloud auth login
# A browser window opens — sign in with your Google account
```

**Verify the login worked:**

```bash
gcloud auth list
# Should show your email as the active account
```

---

### Step 2: Create a GCP project

1. Go to [console.cloud.google.com](https://console.cloud.google.com/)
2. Click the project dropdown at the top → **New Project**
3. Give it a name (e.g. `ai-tour-guide`) and note the **Project ID** that gets auto-generated
4. Wait for the project to be created (~30 seconds)

**Enable Billing** (required for Cloud Run and other APIs):

1. In the GCP Console, go to **Billing**
2. Link a billing account to your new project

> Cloud Run has a generous free tier. A low-traffic app typically costs less than $1/month.

---

### Step 3: Configure deployment settings

```bash
# Copy the example config
cp scripts/.env.example scripts/.env
```

Edit `scripts/.env` and set your Project ID:

```bash
GCP_PROJECT_ID=your-project-id-here   # The Project ID from Step 2
GCP_REGION=asia-east1                 # Change if you prefer a different region
ARTIFACT_REPO=tour-guide-backend
CLOUD_RUN_SERVICE=tour-guide-backend
SECRET_NAME=api-key
```

> `scripts/.env` is gitignored — safe to store your Project ID here.

---

### Step 4: Bootstrap GCP infrastructure (first time only)

This script enables the required Google Cloud APIs, creates the Docker image registry, and sets up the secret vault. It is safe to run multiple times — it skips resources that already exist.

```bash
bash scripts/setup-gcp.sh
```

The script will:
1. Activate your GCP project
2. Enable Cloud Run, Cloud Build, Artifact Registry, and Secret Manager APIs
3. Create a Docker image repository in Artifact Registry
4. Create a Secret Manager entry for the backend API key
5. Grant the Cloud Run service account permission to read secrets

---

### Step 5: Add secrets to Secret Manager

The backend needs two secrets at runtime. Store them with these commands, replacing the placeholder values:

**Gemini API Key** (used by the LLM and TTS):

```bash
echo -n "your-gemini-api-key" | \
  gcloud secrets create gemini-api-key \
    --data-file=- \
    --project=your-project-id
```

Grant Cloud Run access to it:

```bash
PROJECT_NUMBER=$(gcloud projects describe your-project-id --format="value(projectNumber)")

gcloud secrets add-iam-policy-binding gemini-api-key \
  --member "serviceAccount:${PROJECT_NUMBER}-compute@developer.gserviceaccount.com" \
  --role "roles/secretmanager.secretAccessor" \
  --project your-project-id
```

**Backend API Key** (protects your Cloud Run endpoint from unauthorised access):

Generate a strong random key:

```bash
openssl rand -base64 32
# Example output: kG7+mXz1Qp3wR9vLnJ2dYfAeHsBtCuN0oI4kM5pZqWs=
# Save this value — you'll need it for the Flutter app too
```

Store it in Secret Manager:

```bash
echo -n "your-generated-key" | \
  gcloud secrets versions add api-key \
    --data-file=- \
    --project=your-project-id
```

---

### Step 6: Deploy the backend

```bash
bash scripts/deploy-backend.sh
```

This script:
1. Builds a Docker image from `backend/` using Cloud Build (runs in the cloud, no local Docker needed)
2. Pushes the image to Artifact Registry
3. Deploys it to Cloud Run with the secrets mounted as environment variables

When it finishes, you'll see output like:

```
=== Deploy complete! ===

  Service URL : https://tour-guide-backend-xxxxxxxxxx-de.a.run.app
  Health check: curl -H 'X-Api-Key: <key>' https://tour-guide-backend-xxxxxxxxxx-de.a.run.app/health
```

Note the **Service URL** — you'll need it in the next step.

---

### Step 7: Verify the deployment

```bash
curl -H "X-Api-Key: your-generated-key" \
  https://your-service-url.a.run.app/health
```

Expected response:

```json
{"status": "ok", "uptime_s": 12}
```

If you get `401 Unauthorized`, double-check that you're using the same key you stored in Secret Manager.

---

### Step 8: Configure Flutter for production

```bash
cp flutter_app/dart_defines/prod.json.example \
   flutter_app/dart_defines/prod.json
```

Edit `prod.json` with the values from the steps above:

```json
{
  "BACKEND_URL": "https://your-service-url.a.run.app",
  "API_KEY": "your-generated-key"
}
```

> `prod.json` is gitignored — never commit your actual keys.

Build and run the Flutter app pointing to production:

```bash
cd flutter_app

# Run on device
flutter run --dart-define-from-file=dart_defines/prod.json

# Build Android APK
flutter build apk --dart-define-from-file=dart_defines/prod.json

# Build iOS
flutter build ios --dart-define-from-file=dart_defines/prod.json
```

---

### Updating the backend

After code changes, re-deploy with the same command:

```bash
bash scripts/deploy-backend.sh
```

Each deploy creates a new revision. Traffic shifts to the new revision automatically once it passes startup checks.

---

### Cold starts

By default, Cloud Run scales to zero when idle (no cost). The first request after a period of inactivity takes a few extra seconds to start the container.

To keep one instance always warm (eliminates cold starts, adds ~$5–10/month):

```bash
bash scripts/deploy-backend.sh --min-instances 1
```

---

## API Reference

See [`backend/README.md`](backend/README.md) for full API documentation including request/response examples for:

- `GET /health`
- `GET /poi/nearby`
- `POST /narration` (SSE stream)
- `POST /qa` (SSE stream)

---

## Security

| Secret | Where stored | Gitignored |
|--------|-------------|-----------|
| `GEMINI_API_KEY` | GCP Secret Manager + `backend/.env` (local only) | Yes |
| Backend `API_KEY` | GCP Secret Manager + `dart_defines/prod.json` (local only) | Yes |
| Android Maps Key | `flutter_app/android/local.properties` | Yes |
| iOS Maps Key | `flutter_app/ios/Flutter/LocalConfig.xcconfig` | Yes |

None of these files should ever be committed to git.

---

## Project Structure

```
.
├── backend/                  # FastAPI backend
│   ├── src/tour_guide/
│   │   ├── api/              # Route handlers (health, poi, narration, qa)
│   │   ├── clients/          # Overpass, Google Places, Wikipedia, Nominatim
│   │   ├── providers/        # LLM, TTS, STT adapters
│   │   ├── services/         # Business logic
│   │   ├── cache/            # POI and narration disk cache
│   │   └── config.py         # Environment variable config
│   ├── tests/
│   │   ├── unit/
│   │   └── integration/
│   └── Dockerfile
├── flutter_app/
│   ├── lib/
│   │   ├── features/
│   │   │   ├── map/          # Map screen, POI markers
│   │   │   ├── narration/    # Trigger engine, audio playback
│   │   │   ├── qa/           # Voice Q&A
│   │   │   └── session/      # Home screen, persona selection
│   │   └── shared/           # Location, audio, backend client, DB
│   ├── dart_defines/
│   │   ├── dev.json          # Local backend URL
│   │   └── prod.json.example # Production template
│   └── test/
├── scripts/
│   ├── setup-gcp.sh          # One-time GCP bootstrap
│   ├── deploy-backend.sh     # Build and deploy to Cloud Run
│   └── .env.example          # Deployment config template
└── SETUP.md                  # Quick-start reference
```
