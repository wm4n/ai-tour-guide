#!/usr/bin/env bash
# deploy-backend.sh — Build and deploy AI Tour Guide backend to Cloud Run
#
# Usage:
#   bash scripts/deploy-backend.sh [--min-instances 1]
#
# Requires: gcloud CLI authenticated, setup-gcp.sh already run
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${SCRIPT_DIR}/.env"

# Load configuration
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck source=/dev/null
  source "${ENV_FILE}"
fi

# Configuration (override via .env or environment)
PROJECT_ID="${GCP_PROJECT_ID:-ai-tour-guide}"
REGION="${GCP_REGION:-asia-east1}"
ARTIFACT_REPO="${ARTIFACT_REPO:-tour-guide-backend}"
SERVICE_NAME="${CLOUD_RUN_SERVICE:-tour-guide-backend}"
SECRET_NAME="${SECRET_NAME:-api-key}"
MIN_INSTANCES="${MIN_INSTANCES:-0}"

# Parse CLI args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --min-instances)
      MIN_INSTANCES="$2"
      shift 2
      ;;
    *)
      echo "Unknown argument: $1"
      exit 1
      ;;
  esac
done

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${ARTIFACT_REPO}/backend"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
IMAGE_TAG="${IMAGE}:${TIMESTAMP}"

echo "=== AI Tour Guide Backend Deploy ==="
echo "  Project  : ${PROJECT_ID}"
echo "  Region   : ${REGION}"
echo "  Service  : ${SERVICE_NAME}"
echo "  Image    : ${IMAGE_TAG}"
echo "  Min inst : ${MIN_INSTANCES}"
echo ""

# 1. Build and push Docker image via Cloud Build
echo "[1/2] Building Docker image with Cloud Build..."
gcloud builds submit "${REPO_ROOT}/backend" \
  --tag "${IMAGE_TAG}" \
  --project "${PROJECT_ID}" \
  --quiet

echo "  Built: ${IMAGE_TAG}"

# 2. Deploy to Cloud Run
echo "[2/2] Deploying to Cloud Run..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_TAG}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --min-instances "${MIN_INSTANCES}" \
  --max-instances 10 \
  --memory 512Mi \
  --cpu 1 \
  --set-secrets "API_KEY=${SECRET_NAME}:latest" \
  --project "${PROJECT_ID}" \
  --quiet

# 3. Output service URL
SERVICE_URL=$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --project "${PROJECT_ID}" \
  --format "value(status.url)")

echo ""
echo "=== Deploy complete! ==="
echo ""
echo "  Service URL : ${SERVICE_URL}"
echo "  Health check: curl -H 'X-Api-Key: <key>' ${SERVICE_URL}/health"
echo ""
echo "  Update dart_defines/prod.json:"
echo "    BACKEND_URL = ${SERVICE_URL}"
