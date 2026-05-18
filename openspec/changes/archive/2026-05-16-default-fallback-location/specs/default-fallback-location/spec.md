## ADDED Requirements

### Requirement: Language-aware GPS fallback after timeout
The app SHALL inject a language-appropriate fallback `Position` when no real GPS position arrives within 5 seconds of the location stream starting. The fallback SHALL be `zh-TW → 台北故宮博物院 (25.1023°N, 121.5484°E)` and `en → Smithsonian National Air and Space Museum (38.8882°N, 77.0197°W)`.

#### Scenario: zh-TW fallback injected after timeout
- **WHEN** session language is `zh-TW` AND no GPS position arrives within 5 seconds
- **THEN** `effectivePositionStreamProvider` emits `Position(latitude=25.1023, longitude=121.5484)`

#### Scenario: en fallback injected after timeout
- **WHEN** session language is `en` AND no GPS position arrives within 5 seconds
- **THEN** `effectivePositionStreamProvider` emits `Position(latitude=38.8882, longitude=-77.0197)`

#### Scenario: Unknown language falls back to en coordinates
- **WHEN** session language is not `zh-TW` (e.g. `fr`, `ja`) AND no GPS position arrives within 5 seconds
- **THEN** `effectivePositionStreamProvider` emits the `en` fallback coordinates

#### Scenario: GPS arrives before timeout — no fallback injected
- **WHEN** a real GPS position arrives within 5 seconds of stream start
- **THEN** `effectivePositionStreamProvider` forwards the real position and does NOT inject a fallback

#### Scenario: GPS arrives after fallback was injected
- **WHEN** a real GPS position arrives after the 5-second timeout has already injected a fallback
- **THEN** `effectivePositionStreamProvider` continues forwarding the real GPS positions

### Requirement: Fallback timeout is test-overridable
The timeout duration SHALL be exposed as `fallbackTimeoutProvider` (default `Duration(seconds: 5)`) so tests can override it to milliseconds without modifying production code.

#### Scenario: Test overrides timeout to 100ms
- **WHEN** `fallbackTimeoutProvider` is overridden with `Duration(milliseconds: 100)` in a test
- **THEN** `effectivePositionStreamProvider` emits the fallback position after ~100ms

### Requirement: Session language is exposed as a provider
The current session language SHALL be exposed as `sessionLangProvider` (reads from `sessionProvider.lang`) so `effectivePositionStreamProvider` and tests can access it independently.

#### Scenario: sessionLangProvider reflects session language
- **WHEN** `sessionProvider` has `lang == 'zh-TW'`
- **THEN** `sessionLangProvider` returns `'zh-TW'`
