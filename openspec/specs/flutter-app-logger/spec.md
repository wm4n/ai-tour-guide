# Flutter App Logger

## Purpose
Establish a flexible, structured logging system for the Flutter app that can dispatch events to multiple transports (console, Firebase, etc.) with consistent formatting and rich contextual information.

## Requirements

### Requirement: AppLogger singleton dispatches log entries to registered transports
The system SHALL provide an `AppLogger` singleton with static methods (`info`, `debug`, `warn`, `error`) that dispatch `LogEntry` objects to all registered `LogTransport` instances. The logger SHALL be initialized via `AppLogger.init(transports: [...])` before first use.

#### Scenario: Multiple transports all receive the same entry
- **WHEN** `AppLogger.init(transports: [t1, t2])` is called and then `AppLogger.info('POI_LOADED', {'count': 5})` is invoked
- **THEN** both `t1` and `t2` SHALL each receive exactly one `LogEntry` with `level=INFO`, `event='POI_LOADED'`, and `params['count']=5`

#### Scenario: Re-initialization replaces previous transports
- **WHEN** `AppLogger.init(transports: [t1])` is called, followed by `AppLogger.init(transports: [t2])`
- **THEN** subsequent log calls SHALL only dispatch to `t2`; `t1` SHALL receive no further entries

#### Scenario: error() captures error object and stack trace
- **WHEN** `AppLogger.error('UPSTREAM_FAIL', {'service': 'overpass'}, err, st)` is called
- **THEN** the dispatched `LogEntry` SHALL have `level=ERROR`, `error=err`, and `stackTrace=st`

#### Scenario: No transports registered results in silent no-op
- **WHEN** `AppLogger.init(transports: [])` is called and any log method is invoked
- **THEN** the call SHALL complete without throwing an exception

### Requirement: LogEntry data class carries structured log fields
The system SHALL provide a `LogEntry` data class with fields: `level` (LogLevel enum), `event` (String), `params` (Map<String, dynamic>), `timestamp` (DateTime), `error` (Object?, optional), and `stackTrace` (StackTrace?, optional).

#### Scenario: Default params is empty map
- **WHEN** a `LogEntry` is created without specifying `params`
- **THEN** `params` SHALL be an empty map (`const {}`)

### Requirement: LogEvents constants define all event name strings
The system SHALL provide a `LogEvents` class with static string constants for all recognized events, organized by domain (SESSION, LOCATION, POI, NARRATION, QA, ERROR). Constant names SHALL use camelCase; values SHALL use UPPER_SNAKE_CASE.

#### Scenario: Constants have correct string values
- **WHEN** `LogEvents.sessionStart` is accessed
- **THEN** it SHALL equal the string `'SESSION_START'`

#### Scenario: poiLoaded constant value
- **WHEN** `LogEvents.poiLoaded` is accessed
- **THEN** it SHALL equal the string `'POI_LOADED'`

#### Scenario: narrationComplete constant value
- **WHEN** `LogEvents.narrationComplete` is accessed
- **THEN** it SHALL equal the string `'NARRATION_COMPLETE'`

### Requirement: ConsoleTransport formats entries for human and machine reading
The system SHALL provide a `ConsoleTransport` that implements `LogTransport`. In `kDebugMode`, it SHALL use `formatDebug()` which prepends a level-specific emoji and formats time as `HH:MM:SS`. In release/profile mode, it SHALL use `formatRelease()` which uses ISO 8601 timestamp and uppercase level name.

#### Scenario: Debug format uses green emoji for INFO level
- **WHEN** `ConsoleTransport.formatDebug()` is called with an INFO-level entry
- **THEN** the output SHALL contain `🟢`

#### Scenario: Debug format uses red emoji for ERROR level
- **WHEN** `ConsoleTransport.formatDebug()` is called with an ERROR-level entry
- **THEN** the output SHALL contain `🔴`

#### Scenario: Debug format uses yellow emoji for WARN level
- **WHEN** `ConsoleTransport.formatDebug()` is called with a WARN-level entry
- **THEN** the output SHALL contain `🟡`

#### Scenario: Debug format uses blue emoji for DEBUG level
- **WHEN** `ConsoleTransport.formatDebug()` is called with a DEBUG-level entry
- **THEN** the output SHALL contain `🔵`

#### Scenario: Debug format includes event name in brackets
- **WHEN** `ConsoleTransport.formatDebug()` is called with event `'POI_LOADED'`
- **THEN** the output SHALL contain `[POI_LOADED]`

#### Scenario: Debug format includes params as key=value pairs
- **WHEN** `ConsoleTransport.formatDebug()` is called with params `{'count': 5, 'lat': 37.785}`
- **THEN** the output SHALL contain `count=5` and `lat=37.785`

#### Scenario: Debug format includes error text when error is present
- **WHEN** `ConsoleTransport.formatDebug()` is called with an entry that has `error: Exception('503')`
- **THEN** the output SHALL contain the string `503`

#### Scenario: Release format includes ISO timestamp
- **WHEN** `ConsoleTransport.formatRelease()` is called with a UTC timestamp of 2026-05-14
- **THEN** the output SHALL contain `2026-05-14`

#### Scenario: Release format includes uppercase level name
- **WHEN** `ConsoleTransport.formatRelease()` is called with an INFO-level entry
- **THEN** the output SHALL contain `INFO`

#### Scenario: Release format includes event name in brackets
- **WHEN** `ConsoleTransport.formatRelease()` is called with event `'POI_LOADED'`
- **THEN** the output SHALL contain `[POI_LOADED]`

### Requirement: FirebaseTransport stub is a no-op placeholder
The system SHALL provide a `FirebaseTransport` class that implements `LogTransport` with a `log()` method that performs no action. Comments SHALL document the future integration points for `FirebaseCrashlytics` (ERROR level) and `FirebaseAnalytics` (INFO level).

#### Scenario: FirebaseTransport.log() does not throw
- **WHEN** `FirebaseTransport().log(entry)` is called with any `LogEntry`
- **THEN** the method SHALL complete without throwing an exception and with no observable side effects

### Requirement: AppLogger is initialized in main.dart before runApp
The system SHALL call `AppLogger.init(transports: [ConsoleTransport()])` in `main()` before `WidgetsFlutterBinding.ensureInitialized()` and `runApp()`.

#### Scenario: main.dart initializes AppLogger before running the app
- **WHEN** the Flutter app starts
- **THEN** `AppLogger.init()` with `ConsoleTransport` SHALL be called before any widget is built

### Requirement: All providers emit structured log events at key milestones
The system SHALL add `AppLogger` calls to `session_provider`, `poi_provider`, `trigger_provider`, `narration_provider`, and `qa_provider` at the milestones defined in the event catalog. All log calls SHALL be additive and SHALL NOT change existing behavior.

#### Scenario: session_provider logs SESSION_START on successful start
- **WHEN** `SessionNotifier.start()` completes successfully and location permission is granted
- **THEN** `AppLogger.info(LogEvents.sessionStart, {'persona': ..., 'lang': ...})` SHALL be called

#### Scenario: session_provider logs LOCATION_PERMISSION before starting
- **WHEN** `SessionNotifier.start()` requests location permission
- **THEN** `AppLogger.info(LogEvents.locationPermission, {'status': 'granted'|'denied'})` SHALL be called

#### Scenario: session_provider logs SESSION_END with duration on stop
- **WHEN** `SessionNotifier.stop()` is called
- **THEN** `AppLogger.info(LogEvents.sessionEnd, {'duration_s': <int>})` SHALL be called

#### Scenario: poi_provider logs POI_REQUEST before fetching
- **WHEN** `_onPosition()` determines a new fetch is needed
- **THEN** `AppLogger.debug(LogEvents.poiRequest, {'lat': ..., 'lon': ..., 'radius': 500})` SHALL be called

#### Scenario: poi_provider logs POI_LOADED when POIs are returned
- **WHEN** `fetchNearby()` returns a non-empty list
- **THEN** `AppLogger.info(LogEvents.poiLoaded, {'count': ..., 'source': 'osm'})` SHALL be called

#### Scenario: poi_provider logs POI_EMPTY when no POIs found
- **WHEN** `fetchNearby()` returns an empty list
- **THEN** `AppLogger.warn(LogEvents.poiEmpty, {'lat': ..., 'lon': ..., 'radius': 500})` SHALL be called

#### Scenario: narration_provider logs NARRATION_START when narration begins
- **WHEN** `NarrationNotifier.narrate()` is called
- **THEN** `AppLogger.info(LogEvents.narrationStart, {'poi_id': ...})` SHALL be called

#### Scenario: narration_provider logs NARRATION_COMPLETE with duration
- **WHEN** an `EndEvent` is received in `_handle()`
- **THEN** `AppLogger.info(LogEvents.narrationComplete, {'poi_id': ..., 'duration_ms': ...})` SHALL be called

#### Scenario: narration_provider logs NARRATION_SKIP when user skips
- **WHEN** `NarrationNotifier.skip()` is called
- **THEN** `AppLogger.warn(LogEvents.narrationSkip, {'poi_id': ..., 'reason': 'user_skip'})` SHALL be called

#### Scenario: trigger_provider logs NARRATION_TRIGGER when a POI triggers narration
- **WHEN** `_evaluate()` finds a triggerable POI and lifecycle is resumed
- **THEN** `AppLogger.info(LogEvents.narrationTrigger, {'poi_id': ..., 'poi_name': ..., 'persona': ...})` SHALL be called

#### Scenario: qa_provider logs QA_START when Q&A begins
- **WHEN** `QaNotifier.stopAndSend()` proceeds past the minimum duration check
- **THEN** `AppLogger.info(LogEvents.qaStart, {'poi_id': ...})` SHALL be called

#### Scenario: qa_provider logs QA_ANSWER_COMPLETE when answer finishes
- **WHEN** an `EndQaEvent` is received in `_handleEvent()`
- **THEN** `AppLogger.info(LogEvents.qaAnswerComplete, {'poi_id': ...})` SHALL be called
