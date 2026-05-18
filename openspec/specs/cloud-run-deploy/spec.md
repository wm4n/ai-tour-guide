# Capability: Cloud Run Deployment

## Purpose

Automates containerization and deployment of the backend FastAPI service to Google Cloud Run with automated secret management.

---

## Requirements

### Requirement: Backend Dockerfile for Cloud Run deployment
The `backend/Dockerfile` SHALL produce a container image that runs the FastAPI app via `uvicorn`. It SHALL use `python:3.12-slim` as the base image, install dependencies from `pyproject.toml`, and listen on `$PORT` (Cloud Run injects this).

#### Scenario: Docker image builds successfully
- **WHEN** `docker build -t ai-tour-guide-backend ./backend` is run
- **THEN** the build completes without error

#### Scenario: Container listens on PORT env variable
- **WHEN** container starts with `PORT=8080`
- **THEN** uvicorn listens on `0.0.0.0:8080`

#### Scenario: .dockerignore excludes non-essential files
- **WHEN** Docker build context is created
- **THEN** `__pycache__`, `.pytest_cache`, `.env`, `tests/`, and virtual env directories are excluded

---

### Requirement: setup-gcp.sh automates GCP project initialisation
The `scripts/setup-gcp.sh` script SHALL create (or use existing) a GCP project, enable required APIs (Cloud Run, Artifact Registry, Secret Manager, Cloud Build), create a Secret Manager secret for `API_KEY`, and output the project ID and region.

#### Scenario: setup-gcp.sh runs without error on first use
- **WHEN** `./scripts/setup-gcp.sh` is run with valid GCP credentials
- **THEN** all required APIs are enabled and the `API_KEY` secret is created in `asia-east1`

#### Scenario: setup-gcp.sh is idempotent
- **WHEN** `./scripts/setup-gcp.sh` is run a second time
- **THEN** it succeeds without error (existing resources are reused)

---

### Requirement: deploy-backend.sh builds and deploys to Cloud Run
The `scripts/deploy-backend.sh` script SHALL submit a Docker build to Cloud Build, push the image to Artifact Registry, and deploy it to Cloud Run in `asia-east1` with secrets mounted as environment variables.

#### Scenario: deploy-backend.sh deploys new revision
- **WHEN** `./scripts/deploy-backend.sh` is run
- **THEN** a new Cloud Run revision is deployed and the service URL is printed

#### Scenario: Cloud Run service is publicly accessible
- **WHEN** the service is deployed without `--no-allow-unauthenticated`
- **THEN** `curl <service-url>/healthz` returns 200

---

### Requirement: SETUP.md documents complete project setup
The `SETUP.md` SHALL document all steps required to set up the project from scratch: GCP setup, Flutter dart_defines configuration, iOS/Android API key injection, and how to run the app with `--dart-define-from-file`.

#### Scenario: Developer can follow SETUP.md without additional guidance
- **WHEN** a new developer follows SETUP.md step by step
- **THEN** they can run the app on a physical device pointing to the Cloud Run backend
