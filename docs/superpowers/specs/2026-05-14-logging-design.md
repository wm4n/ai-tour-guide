# Logging System Design

**Date:** 2026-05-14  
**Status:** Approved  
**Scope:** Flutter app (client) + Python backend

---

## Overview

A structured, event-driven logging system for both the Flutter app and the Python backend. Designed for human-readable console output during development, with a pluggable transport layer that allows future integration with Firebase Crashlytics and Analytics at near-zero migration cost.

---

## Goals

- Systematically track milestone stages, errors, and key parameters across the full stack
- Human-readable console output (emoji format in debug, plain text in release/CI)
- Backend output switchable between human-readable text (local) and JSON (Cloud Run)
- Transport abstraction: Console works today; Firebase slots in later without refactoring callers
- No new dependencies on either end (Flutter uses `dart:developer`, backend uses stdlib `logging`)

---

## Architecture

Both ends share the same conceptual model:

```
Caller → AppLogger (singleton) → [ConsoleTransport, FirebaseTransport, ...]
```

Every log call produces a `LogEntry` with:

| Field       | Type                        | Description                        |
|-------------|-----------------------------|------------------------------------|
| `level`     | DEBUG \| INFO \| WARN \| ERROR | Severity                          |
| `event`     | String (LogEvents constant) | Named milestone identifier         |
| `params`    | Map / dict                  | Structured key-value parameters    |
| `timestamp` | DateTime / datetime         | UTC timestamp                      |
| `error`     | Object?                     | Exception instance (optional)      |
| `stackTrace`| StackTrace?                 | Stack trace (optional)             |

---

## Event Catalog

All event names are defined as constants in `LogEvents` (Flutter) and `LogEvents` (Python). Both sides use identical **string values** (e.g. `"POI_LOADED"`), but constant names follow each language's convention:

- **Dart:** `LogEvents.poiLoaded` (camelCase) → value `"POI_LOADED"`
- **Python:** `LogEvents.POI_LOADED` (UPPER_SNAKE_CASE) → value `"POI_LOADED"`

### Level Rules
- `INFO` — human-readable milestone (SESSION_START, POI_LOADED, NARRATION_COMPLETE)
- `DEBUG` — pipeline detail (NARRATION_CHUNK, OVERPASS_REQUEST, WIKI_REQUEST)
- `WARN` — recoverable anomaly (NARRATION_SKIP, POI_EMPTY)
- `ERROR` — failure requiring attention (API_ERROR, UPSTREAM_FAIL)

### Events by Domain

**SESSION**
| Event | Level | params |
|-------|-------|--------|
| `SESSION_START` | INFO | persona, lang |
| `SESSION_END` | INFO | duration_s |

**LOCATION**
| Event | Level | params |
|-------|-------|--------|
| `LOCATION_UPDATE` | DEBUG | lat, lon, accuracy_m |
| `LOCATION_PERMISSION` | INFO | status |

**POI**
| Event | Level | params |
|-------|-------|--------|
| `POI_REQUEST` | DEBUG | lat, lon, radius |
| `POI_CACHE_HIT` | DEBUG | key |
| `POI_LOADED` | INFO | count, source (osm\|cache) |
| `POI_EMPTY` | WARN | lat, lon, radius |

**NARRATION**
| Event | Level | params |
|-------|-------|--------|
| `NARRATION_TRIGGER` | INFO | poi_id, poi_name, persona |
| `NARRATION_START` | INFO | poi_id |
| `NARRATION_CHUNK` | DEBUG | poi_id, chunk_index |
| `NARRATION_COMPLETE` | INFO | poi_id, duration_ms |
| `NARRATION_SKIP` | WARN | poi_id, reason |

**QA**
| Event | Level | params |
|-------|-------|--------|
| `QA_START` | INFO | poi_id |
| `QA_STT_DONE` | DEBUG | duration_ms |
| `QA_ANSWER_COMPLETE` | INFO | poi_id, duration_ms |

**EXTERNAL (backend only)**
| Event | Level | params |
|-------|-------|--------|
| `OVERPASS_REQUEST` | DEBUG | bbox, tag_count |
| `OVERPASS_RESPONSE` | DEBUG | node_count, duration_ms |
| `OVERPASS_RETRY` | WARN | attempt, status_code |
| `WIKI_REQUEST` | DEBUG | title, lang |
| `WIKI_RESPONSE` | DEBUG | found (bool), duration_ms |

**ERROR**
| Event | Level | params |
|-------|-------|--------|
| `API_ERROR` | ERROR | endpoint, status, detail |
| `UPSTREAM_FAIL` | ERROR | service (overpass\|wiki\|gemini), error |

---

## Flutter App Implementation

### File Structure

```
flutter_app/lib/shared/logging/
├── app_logger.dart           ← singleton, public API
├── log_entry.dart            ← LogEntry data class
├── log_events.dart           ← LogEvents constants
└── transports/
    ├── log_transport.dart        ← abstract interface
    ├── console_transport.dart    ← immediate implementation
    └── firebase_transport.dart   ← stub for future use
```

### Public API

```dart
AppLogger.info(LogEvents.poiLoaded, {'count': 5, 'lat': lat});
AppLogger.debug(LogEvents.narrationChunk, {'poi_id': id, 'index': i});
AppLogger.warn(LogEvents.poiEmpty, {'lat': lat, 'lon': lon});
AppLogger.error(LogEvents.upstreamFail, {'service': 'overpass'}, error: e, stack: st);
```

### Initialization (main.dart)

```dart
void main() {
  AppLogger.init(transports: [
    ConsoleTransport(),
    // FirebaseTransport(),  // uncomment when Firebase is integrated
  ]);
  runApp(const App());
}
```

### Console Output Format

**Debug mode** (`kDebugMode == true`) — emoji, optimized for human scanning:

```
🟢 10:23:45 [POI_LOADED]       count=5 lat=37.785 lon=-122.406
🔵 10:23:45 [NARRATION_CHUNK]  poi_id=osm:123 index=2
🟡 10:23:45 [POI_EMPTY]        lat=37.785 lon=-122.406
🔴 10:23:45 [UPSTREAM_FAIL]    service=overpass  ← Connection refused
```

Level → emoji: `INFO=🟢` `DEBUG=🔵` `WARN=🟡` `ERROR=🔴`

**Profile/Release mode** — plain text, machine-friendly:

```
2026-05-14T10:23:45Z INFO  [POI_LOADED]    count=5 lat=37.785 lon=-122.406
2026-05-14T10:23:45Z ERROR [UPSTREAM_FAIL] service=overpass error="Connection refused"
```

### Transport Interface

```dart
abstract class LogTransport {
  void log(LogEntry entry);
}
```

`FirebaseTransport` stub maps:
- `ERROR` level → `FirebaseCrashlytics.instance.recordError()`
- `INFO` level + named event → `FirebaseAnalytics.instance.logEvent()`

### Dependencies

No new packages required. Uses `dart:developer` for console output.

---

## Backend Implementation

### File Structure

```
backend/src/tour_guide/
├── logging_config.py   ← setup_logging(), formatters, log_event() helper
└── log_events.py       ← event name constants
```

### Initialization

`setup_logging()` called at the top of `create_app()` in `main.py`:

```python
def create_app(config: AppConfig) -> FastAPI:
    setup_logging(level=config.log_level, fmt=config.log_format)
    ...
```

### log_event() Helper

All milestone log calls use this helper to guarantee consistent structure:

```python
log_event(logger, LogEvents.POI_LOADED, count=len(pois), lat=lat, lon=lon)
log_event(logger, LogEvents.UPSTREAM_FAIL, service="overpass", error=str(e), level="error")
```

Signature:
```python
def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: str = "info",
    **params,
) -> None
```

### Console Output Format

**`LOG_FORMAT=text`** (local development, default):

```
2026-05-14 10:23:45 INFO  [POI_LOADED]      count=5 lat=37.785 lon=-122.406
2026-05-14 10:23:45 WARN  [OVERPASS_RETRY]  attempt=2 status_code=503
2026-05-14 10:23:45 ERROR [UPSTREAM_FAIL]   service=overpass error="503"
```

**`LOG_FORMAT=json`** (Cloud Run):

```json
{"ts":"2026-05-14T10:23:45Z","level":"INFO","event":"POI_LOADED","count":5,"lat":37.785,"lon":-122.406}
```

### Environment Variables

Added to `.env.example`:

```
LOG_LEVEL=INFO     # DEBUG | INFO | WARNING | ERROR
LOG_FORMAT=text    # text | json
```

`AppConfig` adds `log_format: str = Field("text", alias="LOG_FORMAT")`.

### Coverage: Where log_event() Calls Are Added

| File | Events added |
|------|-------------|
| `api/poi.py` | `POI_REQUEST`, `POI_LOADED`, `API_ERROR` |
| `services/poi_service.py` | `POI_CACHE_HIT`, `POI_LOADED`, `POI_EMPTY` |
| `clients/overpass.py` | `OVERPASS_REQUEST`, `OVERPASS_RESPONSE`, `OVERPASS_RETRY` |
| `clients/wikipedia.py` | `WIKI_REQUEST`, `WIKI_RESPONSE` |
| `services/narration_service.py` | `NARRATION_START`, `NARRATION_COMPLETE` |
| `services/qa_service.py` | `QA_START`, `QA_ANSWER_COMPLETE` |

### Dependencies

No new pip packages required. Uses Python stdlib `logging` only.

---

## Firebase Integration (Future)

When ready to integrate Firebase:

**Flutter:**
1. Add `firebase_crashlytics` and `firebase_analytics` to `pubspec.yaml`
2. Implement `FirebaseTransport.log()` — map level/event to the appropriate Firebase call
3. Add `FirebaseTransport()` to `AppLogger.init()` in `main.dart`

**Backend:**
No backend changes needed for Firebase. Backend logs to Cloud Run stdout, which GCP Cloud Logging ingests automatically when `LOG_FORMAT=json`.

---

## Testing

**Flutter:**
- Unit test `ConsoleTransport` formats (emoji vs plain text based on mode)
- Unit test `AppLogger` routes entries to all registered transports
- `FirebaseTransport` stub is a no-op in tests — no mocking needed

**Backend:**
- Unit test `log_event()` produces correct text and JSON output for each format
- Unit test `setup_logging()` respects `LOG_LEVEL` and `LOG_FORMAT` env vars
- Existing integration tests unchanged — logging is additive, not behaviorally breaking
