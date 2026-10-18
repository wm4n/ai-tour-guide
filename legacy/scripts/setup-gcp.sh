#!/usr/bin/env bash
# setup-gcp.sh — Idempotent GCP project bootstrap for AI Tour Guide backend
#
# Usage:
#   cp scripts/.env.example scripts/.env
#   # Edit scripts/.env with your project settings
#   bash scripts/setup-gcp.sh
#
# Requires: gcloud CLI authenticated, sufficient IAM permissions
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Load configuration
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

# Required variables (override via .env or environment)
PROJECT_ID="${GCP_PROJECT_ID:-ai-tour-guide}"
REGION="${GCP_REGION:-asia-east1}"
ARTIFACT_REPO="${ARTIFACT_REPO:-tour-guide-backend}"
SECRET_NAME="${SECRET_NAME:-api-key}"

echo "=== AI Tour Guide GCP Setup ==="
echo "  Project : ${PROJECT_ID}"
echo "  Region  : ${REGION}"
echo ""

# 1. Set current project
echo "[1/5] Setting active project..."
gcloud config set project "${PROJECT_ID}" --quiet

# 2. Enable required APIs (idempotent)
echo "[2/5] Enabling required APIs..."
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  secretmanager.googleapis.com \
  --project "${PROJECT_ID}" \
  --quiet

# 3. Create Artifact Registry repository (idempotent — skip if exists)
echo "[3/5] Creating Artifact Registry repository..."
if ! gcloud artifacts repositories describe "${ARTIFACT_REPO}" \
    --location "${REGION}" \
    --project "${PROJECT_ID}" \
    --quiet 2>/dev/null; then
  gcloud artifacts repositories create "${ARTIFACT_REPO}" \
    --repository-format docker \
    --location "${REGION}" \
    --project "${PROJECT_ID}" \
    --description "AI Tour Guide backend Docker images" \
    --quiet
  echo "  Created repository: ${ARTIFACT_REPO}"
else
  echo "  Repository already exists: ${ARTIFACT_REPO}"
fi

# 4. Create Secret Manager secret for API_KEY (idempotent)
echo "[4/5] Setting up Secret Manager..."
if ! gcloud secrets describe "${SECRET_NAME}" \
    --project "${PROJECT_ID}" \
    --quiet 2>/dev/null; then
  gcloud secrets create "${SECRET_NAME}" \
    --replication-policy automatic \
    --project "${PROJECT_ID}" \
    --quiet
  echo "  Created secret: ${SECRET_NAME}"
  echo ""
  echo "  ACTION REQUIRED: Add your API key value:"
  echo "  echo -n 'your-secret-key' | gcloud secrets versions add ${SECRET_NAME} --data-file=-"
else
  echo "  Secret already exists: ${SECRET_NAME}"
fi

# 5. Grant Cloud Run SA access to secret
echo "[5/5] Configuring IAM..."
PROJECT_NUMBER=$(gcloud projects describe "${PROJECT_ID}" --format="value(projectNumber)")
CLOUD_RUN_SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"

gcloud secrets add-iam-policy-binding "${SECRET_NAME}" \
  --member "serviceAccount:${CLOUD_RUN_SA}" \
  --role "roles/secretmanager.secretAccessor" \
  --project "${PROJECT_ID}" \
  --quiet

echo ""
echo "=== Setup complete! ==="
echo ""
echo "Next steps:"
echo "  1. Add API key: echo -n 'your-key' | gcloud secrets versions add ${SECRET_NAME} --data-file=-"
echo "  2. Deploy backend: bash scripts/deploy-backend.sh"
