## MODIFIED Requirements

### Requirement: Automatic narration triggering within radius
The TriggerEngine SHALL evaluate the POI list each time position updates and trigger narration for POIs within the per-persona trigger radius (not a hardcoded 100m) that are not in cooldown or already played. The `TriggerNotifier` SHALL read `defaultTriggerRadiusM` from `kPersonas` using the current session persona and pass it to `TriggerEngine.evaluate()`.

#### Scenario: POI enters trigger radius
- **WHEN** user moves within the persona's trigger radius of a POI that is not in cooldown and not yet played this session
- **THEN** TriggerEngine emits a trigger event and NarrationProvider.narrate(poi) is called

#### Scenario: POI in cooldown is skipped
- **WHEN** a POI is within the trigger radius but `LocalDB.isCooldown(poi.id, 24h)` returns true
- **THEN** TriggerEngine does NOT trigger narration for that POI

#### Scenario: Already-played POI deduped within session
- **WHEN** a POI has already been narrated in the current session (in-memory dedup set)
- **THEN** TriggerEngine does NOT trigger narration again, even if cooldown has not been written yet

#### Scenario: Low GPS accuracy pauses evaluation
- **WHEN** position accuracy > 100m
- **THEN** TriggerEngine pauses evaluation and does not trigger any POI

#### Scenario: Foodie persona uses 50m trigger radius
- **WHEN** session persona is `foodie`
- **THEN** TriggerNotifier passes `radiusM: 50.0` to TriggerEngine.evaluate()

#### Scenario: Non-foodie persona uses 100m trigger radius
- **WHEN** session persona is `history_uncle`, `story_brother`, `gossip_auntie`, or `kid_sister`
- **THEN** TriggerNotifier passes `radiusM: 100.0` to TriggerEngine.evaluate()
