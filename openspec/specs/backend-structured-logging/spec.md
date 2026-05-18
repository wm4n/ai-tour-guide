# Backend Structured Logging

## Purpose
Establish a consistent, structured logging system for the Flask backend to emit machine-readable events that can be aggregated, analyzed, and debugged in production environments.

## Requirements

### Requirement: LogEvents class defines all backend event name constants
The system SHALL provide a `LogEvents` class in `log_events.py` with class-level string constants for all recognized backend events, using UPPER_SNAKE_CASE naming. Values SHALL match the identical strings used by the Flutter `LogEvents` class.

#### Scenario: POI_LOADED constant value
- **WHEN** `LogEvents.POI_LOADED` is accessed
- **THEN** it SHALL equal the string `'POI_LOADED'`

#### Scenario: UPSTREAM_FAIL constant value
- **WHEN** `LogEvents.UPSTREAM_FAIL` is accessed
- **THEN** it SHALL equal the string `'UPSTREAM_FAIL'`

#### Scenario: OVERPASS_RETRY constant value
- **WHEN** `LogEvents.OVERPASS_RETRY` is accessed
- **THEN** it SHALL equal the string `'OVERPASS_RETRY'`

### Requirement: _HumanFormatter produces human-readable text log lines
The system SHALL provide a `_HumanFormatter(logging.Formatter)` that formats log records as `YYYY-MM-DD HH:MM:SS LEVEL [EVENT]  key=value key=value`. It SHALL read `event` and `params` from `record.extra`. If `params` is empty, no key=value pairs SHALL appear.

#### Scenario: Output includes event name in brackets
- **WHEN** a log record with `event='POI_LOADED'` is formatted by `_HumanFormatter`
- **THEN** the output SHALL contain `[POI_LOADED]`

#### Scenario: Output includes params as key=value pairs
- **WHEN** a log record with `params={'count': 5, 'lat': 37.785}` is formatted
- **THEN** the output SHALL contain `count=5` and `lat=37.785`

#### Scenario: Output includes level name
- **WHEN** a WARNING-level record is formatted
- **THEN** the output SHALL contain `WARNING`

#### Scenario: No params produces no key=value output
- **WHEN** a log record with empty `params` is formatted
- **THEN** the output SHALL NOT contain any `=` character (no spurious key=value pairs)

### Requirement: _JsonFormatter produces valid single-line JSON log entries
The system SHALL provide a `_JsonFormatter(logging.Formatter)` that formats log records as a single-line JSON object with fields: `ts` (ISO 8601 UTC), `level` (uppercase string), `event` (string), and all `params` merged into the top level.

#### Scenario: Output is valid JSON
- **WHEN** `_JsonFormatter` formats any log record
- **THEN** `json.loads(output)` SHALL succeed without raising an exception

#### Scenario: event field is present at top level
- **WHEN** a record with `event='POI_LOADED'` is formatted by `_JsonFormatter`
- **THEN** the parsed JSON SHALL have `doc['event'] == 'POI_LOADED'`

#### Scenario: params are merged into top-level JSON
- **WHEN** a record with `params={'count': 5, 'lat': 37.785}` is formatted
- **THEN** the parsed JSON SHALL have `doc['count'] == 5` and `doc['lat'] == 37.785`

#### Scenario: ts and level fields are present
- **WHEN** any record is formatted by `_JsonFormatter`
- **THEN** the parsed JSON SHALL have both `'ts'` and `'level'` keys

### Requirement: setup_logging() configures root logger idempotently
The system SHALL provide a `setup_logging(level: str, fmt: str)` function that clears existing handlers, adds a single `StreamHandler(sys.stdout)` with the appropriate formatter, and sets the root logger level. Calling it multiple times SHALL NOT add duplicate handlers.

#### Scenario: Sets log level on root logger
- **WHEN** `setup_logging(level='DEBUG', fmt='text')` is called
- **THEN** `logging.getLogger().level` SHALL equal `logging.DEBUG`

#### Scenario: Idempotent — repeated calls do not leak handlers
- **WHEN** `setup_logging(level='INFO', fmt='text')` is called twice
- **THEN** the number of root logger handlers after the second call SHALL equal the number after the first call

### Requirement: log_event() helper dispatches structured events via stdlib logging
The system SHALL provide a `log_event(logger, event, *, level='info', exc_info=False, **params)` function that calls `logger.<level>()` with `extra={'event': event, 'params': params}`. The `level` parameter SHALL accept lowercase strings matching stdlib logging methods.

#### Scenario: Default level is INFO
- **WHEN** `log_event(logger, LogEvents.POI_LOADED, count=5)` is called without a `level` argument
- **THEN** the emitted log record SHALL have level `INFO`

#### Scenario: Error level is applied correctly
- **WHEN** `log_event(logger, LogEvents.UPSTREAM_FAIL, level='error', service='overpass')` is called
- **THEN** the emitted log record SHALL have level `ERROR`

#### Scenario: Custom params appear in record.params
- **WHEN** `log_event(logger, 'POI_LOADED', count=5)` is called
- **THEN** the log record SHALL have `record.params == {'count': 5}`

### Requirement: AppConfig includes log_format field
The system SHALL add a `log_format: str` field to `AppConfig` with default value `'text'`, aliased to the `LOG_FORMAT` environment variable. Valid values are `'text'` (human-readable) and `'json'` (Cloud Run).

#### Scenario: Default value is text
- **WHEN** `AppConfig` is instantiated without setting `LOG_FORMAT`
- **THEN** `config.log_format` SHALL equal `'text'`

#### Scenario: LOG_FORMAT=json is applied
- **WHEN** `AppConfig` is instantiated with `LOG_FORMAT='json'`
- **THEN** `config.log_format` SHALL equal `'json'`

### Requirement: create_app() calls setup_logging() at startup
The system SHALL call `setup_logging(level=config.log_level, fmt=config.log_format)` as the first statement in `create_app()` in `main.py`.

#### Scenario: setup_logging is called with config values
- **WHEN** `create_app(config)` is called
- **THEN** the root logger SHALL be configured with the level and format from `config.log_level` and `config.log_format`

### Requirement: All backend services and clients emit structured log events at key milestones
The system SHALL add `log_event()` calls to `overpass.py`, `wikipedia.py`, `poi_service.py`, `api/poi.py`, `narration_service.py`, and `qa_service.py` at the milestones defined in the event catalog. All log calls SHALL be additive and SHALL NOT change existing behavior.

#### Scenario: overpass.py logs OVERPASS_REQUEST before each query
- **WHEN** `OverpassClient.query()` is called
- **THEN** `log_event(logger, LogEvents.OVERPASS_REQUEST, level='debug', tag_count=...)` SHALL be called before the HTTP request

#### Scenario: overpass.py logs OVERPASS_RESPONSE on success
- **WHEN** `OverpassClient.query()` receives a successful response
- **THEN** `log_event(logger, LogEvents.OVERPASS_RESPONSE, level='debug', node_count=..., duration_ms=...)` SHALL be called

#### Scenario: overpass.py logs OVERPASS_RETRY on transient failure
- **WHEN** `OverpassClient.query()` catches a retryable exception
- **THEN** `log_event(logger, LogEvents.OVERPASS_RETRY, level='warning', attempt=..., status_code=...)` SHALL be called

#### Scenario: wikipedia.py logs WIKI_REQUEST before each fetch
- **WHEN** `WikipediaClient.summary()` is called
- **THEN** `log_event(logger, LogEvents.WIKI_REQUEST, level='debug', title=..., lang=...)` SHALL be called

#### Scenario: wikipedia.py logs WIKI_RESPONSE with found status
- **WHEN** `WikipediaClient.summary()` receives any response (200 or 404)
- **THEN** `log_event(logger, LogEvents.WIKI_RESPONSE, level='debug', found=..., duration_ms=...)` SHALL be called

#### Scenario: poi_service.py logs POI_CACHE_HIT on cache hit
- **WHEN** `_nearby_osm()` finds a cached result
- **THEN** `log_event(logger, LogEvents.POI_CACHE_HIT, level='debug', key=...)` SHALL be called

#### Scenario: poi_service.py logs POI_LOADED when results are found
- **WHEN** `_nearby_osm()` fetches POIs and the list is non-empty
- **THEN** `log_event(logger, LogEvents.POI_LOADED, count=..., source='osm')` SHALL be called

#### Scenario: poi_service.py logs POI_EMPTY when no results found
- **WHEN** `_nearby_osm()` fetches POIs and the list is empty
- **THEN** `log_event(logger, LogEvents.POI_EMPTY, level='warning', lat=..., lon=..., radius=...)` SHALL be called

#### Scenario: api/poi.py logs POI_REQUEST at endpoint entry
- **WHEN** `GET /poi/nearby` is called
- **THEN** `log_event(logger, LogEvents.POI_REQUEST, level='debug', lat=..., lon=..., radius=..., persona=...)` SHALL be called

#### Scenario: api/poi.py logs API_ERROR on unhandled exception
- **WHEN** `poi_nearby()` raises an unexpected exception
- **THEN** `log_event(logger, LogEvents.API_ERROR, level='error', endpoint='/poi/nearby', ...)` SHALL be called

#### Scenario: narration_service.py logs NARRATION_START before streaming
- **WHEN** `NarrationService.narrate()` begins (cache hit or miss)
- **THEN** `log_event(logger, LogEvents.NARRATION_START, poi_id=..., cache_hit=...)` SHALL be called

#### Scenario: narration_service.py logs NARRATION_COMPLETE after streaming
- **WHEN** `NarrationService.narrate()` is about to yield `EndEvent()`
- **THEN** `log_event(logger, LogEvents.NARRATION_COMPLETE, poi_id=..., duration_ms=...)` SHALL be called

#### Scenario: qa_service.py logs QA_START at the beginning of answer()
- **WHEN** `QAService.answer()` is called
- **THEN** `log_event(logger, LogEvents.QA_START, poi_id=...)` SHALL be called

#### Scenario: qa_service.py logs QA_STT_DONE after transcription
- **WHEN** `self._stt.transcribe()` completes in `QAService.answer()`
- **THEN** `log_event(logger, LogEvents.QA_STT_DONE, level='debug', duration_ms=...)` SHALL be called

#### Scenario: qa_service.py logs QA_ANSWER_COMPLETE before EndEvent
- **WHEN** `QAService.answer()` is about to yield `EndEvent()`
- **THEN** `log_event(logger, LogEvents.QA_ANSWER_COMPLETE, poi_id=..., duration_ms=...)` SHALL be called
