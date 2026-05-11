## ADDED Requirements

### Requirement: Haversine distance calculation
The app SHALL compute the great-circle distance between two GPS coordinates in metres using the haversine formula.

#### Scenario: Distance within trigger radius
- **WHEN** user is 80m from a POI
- **THEN** haversine returns a value ≤ 100.0

#### Scenario: Distance outside trigger radius
- **WHEN** user is 150m from a POI
- **THEN** haversine returns a value > 100.0

#### Scenario: Same coordinates
- **WHEN** user coordinates equal POI coordinates
- **THEN** haversine returns 0.0

### Requirement: Automatic narration triggering within radius
The TriggerEngine SHALL evaluate the POI list each time position updates and trigger narration for POIs within 100m that are not in cooldown or already played.

#### Scenario: POI enters trigger radius
- **WHEN** user moves within 100m of a POI that is not in cooldown and not yet played this session
- **THEN** TriggerEngine emits a trigger event and NarrationProvider.narrate(poi) is called

#### Scenario: POI in cooldown is skipped
- **WHEN** a POI is within 100m but `LocalDB.isCooldown(poi.id, 24h)` returns true
- **THEN** TriggerEngine does NOT trigger narration for that POI

#### Scenario: Already-played POI deduped within session
- **WHEN** a POI has already been narrated in the current session (in-memory dedup set)
- **THEN** TriggerEngine does NOT trigger narration again, even if cooldown has not been written yet

#### Scenario: Low GPS accuracy pauses evaluation
- **WHEN** position accuracy > 100m
- **THEN** TriggerEngine pauses evaluation and does not trigger any POI

### Requirement: Manual trigger bypasses TriggerEngine
The app SHALL allow direct invocation of NarrationProvider.narrate(poi) without going through TriggerEngine.

#### Scenario: User taps marker while POI is in cooldown
- **WHEN** user taps a POI marker on the map
- **THEN** narration is triggered regardless of cooldown or dedup state
