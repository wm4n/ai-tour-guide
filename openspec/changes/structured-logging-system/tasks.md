## 1. Flutter — Core Data Types

- [x] 1.1 Create `flutter_app/lib/shared/logging/log_entry.dart` — `LogLevel` enum + `LogEntry` data class
- [x] 1.2 Create `flutter_app/lib/shared/logging/log_events.dart` — `LogEvents` string constants (camelCase names, UPPER_SNAKE_CASE values)
- [x] 1.3 Create `flutter_app/lib/shared/logging/log_transport.dart` — abstract `LogTransport` interface
- [x] 1.4 Create `flutter_app/test/unit/app_logger_test.dart` with `LogEvents` constants tests
- [x] 1.5 Run `flutter test test/unit/app_logger_test.dart` — verify constants tests pass

## 2. Flutter — ConsoleTransport

- [x] 2.1 Create `flutter_app/test/unit/console_transport_test.dart` with all `formatDebug` and `formatRelease` tests
- [x] 2.2 Run console_transport tests — verify they fail (file does not exist yet)
- [x] 2.3 Create `flutter_app/lib/shared/logging/transports/console_transport.dart` — emoji (debug) / plain (release) formatter
- [x] 2.4 Run console_transport tests — verify all pass

## 3. Flutter — AppLogger Singleton + FirebaseTransport Stub

- [ ] 3.1 Extend `flutter_app/test/unit/app_logger_test.dart` with `AppLogger` routing and level tests
- [ ] 3.2 Run app_logger tests — verify they fail (AppLogger not yet defined)
- [ ] 3.3 Create `flutter_app/lib/shared/logging/app_logger.dart` — singleton with `init()`, `info()`, `debug()`, `warn()`, `error()` static methods
- [ ] 3.4 Create `flutter_app/lib/shared/logging/transports/firebase_transport.dart` — no-op stub with future integration comments
- [ ] 3.5 Run app_logger tests — verify all pass

## 4. Flutter — Initialization and Call Sites

- [ ] 4.1 Update `flutter_app/lib/main.dart` — call `AppLogger.init(transports: [ConsoleTransport()])` before `WidgetsFlutterBinding.ensureInitialized()`
- [ ] 4.2 Update `flutter_app/lib/features/session/providers/session_provider.dart` — add `SESSION_START`, `SESSION_END`, `LOCATION_PERMISSION` log calls
- [ ] 4.3 Update `flutter_app/lib/features/map/providers/poi_provider.dart` — add `POI_REQUEST`, `POI_LOADED`, `POI_EMPTY`, `API_ERROR` log calls
- [ ] 4.4 Update `flutter_app/lib/features/narration/providers/trigger_provider.dart` — add `NARRATION_TRIGGER` log call
- [ ] 4.5 Update `flutter_app/lib/features/narration/providers/narration_provider.dart` — add `NARRATION_START`, `NARRATION_CHUNK`, `NARRATION_COMPLETE`, `NARRATION_SKIP` log calls with duration tracking
- [ ] 4.6 Update `flutter_app/lib/features/qa/providers/qa_provider.dart` — add `QA_START`, `QA_ANSWER_COMPLETE` log calls
- [ ] 4.7 Run `flutter test` — verify all existing tests pass (log calls are additive)

## 5. Backend — log_events.py + logging_config.py

- [ ] 5.1 Create `backend/tests/unit/test_logging_config.py` with tests for `_HumanFormatter`, `_JsonFormatter`, `setup_logging`, and `log_event`
- [ ] 5.2 Run `pytest tests/unit/test_logging_config.py` — verify tests fail (modules do not exist)
- [ ] 5.3 Create `backend/src/tour_guide/log_events.py` — `LogEvents` class with all UPPER_SNAKE_CASE constants
- [ ] 5.4 Create `backend/src/tour_guide/logging_config.py` — `_HumanFormatter`, `_JsonFormatter`, `setup_logging()`, `log_event()` helper
- [ ] 5.5 Run `pytest tests/unit/test_logging_config.py` — verify all tests pass

## 6. Backend — AppConfig + main.py Wiring

- [ ] 6.1 Update `backend/src/tour_guide/config.py` — add `log_format: str = Field('text', alias='LOG_FORMAT')`
- [ ] 6.2 Update `backend/src/tour_guide/main.py` — call `setup_logging(level=config.log_level, fmt=config.log_format)` as first line of `create_app()`
- [ ] 6.3 Update `backend/.env.example` — add `LOG_LEVEL` and `LOG_FORMAT` entries with comments
- [ ] 6.4 Run `pytest tests/ --ignore=tests/smoke` — verify existing tests still pass

## 7. Backend — Client Call Sites (overpass + wikipedia)

- [ ] 7.1 Update `backend/src/tour_guide/clients/overpass.py` — add `OVERPASS_REQUEST`, `OVERPASS_RESPONSE`, `OVERPASS_RETRY` log calls
- [ ] 7.2 Update `backend/src/tour_guide/clients/wikipedia.py` — add `WIKI_REQUEST`, `WIKI_RESPONSE` log calls
- [ ] 7.3 Run `pytest tests/ --ignore=tests/smoke` — verify existing tests still pass

## 8. Backend — Service Call Sites (poi_service + api/poi)

- [ ] 8.1 Update `backend/src/tour_guide/services/poi_service.py` — add `POI_CACHE_HIT`, `POI_LOADED`, `POI_EMPTY`, `UPSTREAM_FAIL` log calls; replace existing bare `logger.warning` calls
- [ ] 8.2 Update `backend/src/tour_guide/api/poi.py` — add `POI_REQUEST`, `POI_LOADED`, `API_ERROR` log calls; replace existing bare `logger.exception` call
- [ ] 8.3 Run `pytest tests/ --ignore=tests/smoke` — verify existing tests still pass

## 9. Backend — Service Call Sites (narration + qa)

- [ ] 9.1 Update `backend/src/tour_guide/services/narration_service.py` — add `NARRATION_START`, `NARRATION_COMPLETE` log calls with duration tracking (cache hit and miss paths)
- [ ] 9.2 Update `backend/src/tour_guide/services/qa_service.py` — add `QA_START`, `QA_STT_DONE`, `QA_ANSWER_COMPLETE` log calls with duration tracking
- [ ] 9.3 Run `pytest tests/ --ignore=tests/smoke` — verify existing tests still pass

## 10. End-to-End Verification

- [ ] 10.1 Run `flutter test` — verify all Flutter tests pass
- [ ] 10.2 Run `pytest tests/ --ignore=tests/smoke` — verify all backend tests pass
- [ ] 10.3 Start backend with `LOG_LEVEL=DEBUG LOG_FORMAT=text` — verify human-readable log output appears on console
- [ ] 10.4 Start backend with `LOG_FORMAT=json` — verify one-line JSON per event with `event`, `level`, `ts` keys
