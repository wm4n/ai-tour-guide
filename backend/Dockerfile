FROM python:3.12-slim

WORKDIR /app

# Install dependencies first for layer caching
COPY pyproject.toml ./
COPY src/ ./src/
COPY prompts/ ./prompts/

RUN pip install --no-cache-dir .

# Cloud Run injects PORT; default to 8080 if not set
ENV PORT=8080

CMD ["sh", "-c", "uvicorn tour_guide.main:app --host 0.0.0.0 --port ${PORT}"]
