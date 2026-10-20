# Tour Guide Backend

## Setup

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # then edit with your GEMINI_API_KEY
```

## Run

```bash
uvicorn tour_guide.main:app --reload
```

## Test

```bash
pytest                            # unit + integration (offline)
pytest -m real_provider           # smoke test against real Gemini (costs $)
```

## API Endpoints

The backend exposes three main endpoints:

### GET /health

Health check endpoint. Returns immediately.

```bash
curl http://localhost:8000/health
```

Response:
```json
{"status":"ok","uptime_s":42}
```

### GET /poi/nearby

Query nearby points of interest using Overpass API.

```bash
curl "http://localhost:8000/poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle"
```

Query parameters:
- `lat` (required): Latitude
- `lon` (required): Longitude
- `radius` (optional, default 500): Search radius in meters
- `lang` (optional, default zh-TW): Language code (zh-TW, en, etc.)
- `persona` (optional, default history_uncle): Persona type (history_uncle, food_critic, etc.)

Response:
```json
{
  "pois": [
    {
      "id": "osm:node:12345",
      "name": "故宮博物院",
      "lat": 25.1023,
      "lon": 121.5482,
      "category": "museum",
      "distance_m": 120
    }
  ],
  "queried_at": "2026-05-09T12:34:56Z"
}
```

### POST /narration (Server-Sent Events)

Generate narration for a POI using Server-Sent Events (SSE) stream. Returns metadata, text chunks, and audio chunks in real-time.

```bash
curl -N -X POST http://localhost:8000/narration \
  -H "Content-Type: application/json" \
  -d '{
    "poi_id": "osm:node:12345",
    "persona": "history_uncle",
    "lang": "zh-TW",
    "length": "medium"
  }' \
  --no-buffer
```

Request body:
- `poi_id` (required): The POI identifier from `/poi/nearby`
- `persona` (optional, default history_uncle): Storytelling persona
- `lang` (optional, default zh-TW): Language code
- `length` (optional, default medium): Narration length (short, medium, long)

Response: SSE stream with events

```
event: meta
data: {
  "poi_id": "osm:node:12345",
  "cache_hit": false,
  "confidence": "high",
  "estimated_duration_s": 45
}

event: text
data: {
  "chunk": "故宮博物院位於台北市士林區，是世界著名的中華文化藝術博物館。",
  "sentence_idx": 0
}

event: audio
data: {
  "chunk_b64": "//NExAAyUAIAHQAHQABkAA...",
  "sentence_idx": 0
}

event: text
data: {
  "chunk": "它收藏了來自世界各地的珍貴文物，包括青銅器、陶瓷和書畫。",
  "sentence_idx": 1
}

event: audio
data: {
  "chunk_b64": "//NExAAyUAIAHQAHQABkAA...",
  "sentence_idx": 1
}

event: end
data: {}
```

The stream delivers:
1. **meta**: Metadata about the narration generation
2. **text** (one per sentence): Text chunks for the narration
3. **audio** (one per sentence): Base64-encoded audio chunks
4. **end**: Marks the completion of the stream
