## ADDED Requirements

### Requirement: LLM SKIP signal for trivial candidates
When ALL POI candidates in a selection request are trivial (infrastructure signage with no Wikipedia data), the backend LLM selector SHALL return a SKIP decision and the system SHALL NOT generate any narration for that cycle.

Trivial candidates are defined as POIs whose names contain terms such as 地圖 / map / 導覽圖 / 公車 / 巴士 / bus / signboard / information board, AND which have no Wikipedia extract data. A POI with Wikipedia data SHALL always be considered worth narrating regardless of name.

#### Scenario: All candidates are trivial map signs
- **WHEN** the POI selector receives only candidates with infrastructure names and no Wikipedia data
- **THEN** `POISelectorService.select()` returns `None`

#### Scenario: Mixed candidates — at least one worth narrating
- **WHEN** the POI selector receives candidates that include at least one POI with Wikipedia data
- **THEN** `POISelectorService.select()` returns a valid `poi_id` (not None)

#### Scenario: Backend streams skip event
- **WHEN** `POISelectorService.select()` returns `None`
- **THEN** the `/narration` endpoint streams a single SSE event with `event: skip` and JSON data `{"min_displacement_m": 1500.0}`, then closes the stream

#### Scenario: Flutter receives skip event
- **WHEN** the Flutter `BackendClient` parses an SSE event with `event: skip`
- **THEN** it emits a `SkipEvent` with `minDisplacementM` parsed from the JSON payload (defaulting to 1500.0 if absent)

#### Scenario: Flutter enters displacement-wait mode
- **WHEN** `NarrationNotifier` processes a `SkipEvent`
- **THEN** `NarrationState.lastEventWasSkip` is set to `true` and the narration status remains `idle`

#### Scenario: TriggerProvider switches to displacement-wait
- **WHEN** `TriggerNotifier` detects `lastEventWasSkip` becomes `true`
- **THEN** the active countdown (if any) is cancelled, `TriggerState.isWaitingForDisplacement` is set to `true`, and location monitoring begins

#### Scenario: Displacement threshold triggers re-narration
- **WHEN** the user has moved at least `skipDisplacementM` meters from the skip origin
- **THEN** `TriggerNotifier` exits displacement-wait mode and calls `_doCandidatesRequest()` to re-trigger narration

#### Scenario: CountdownBadge shows displacement progress
- **WHEN** `TriggerState.isWaitingForDisplacement` is `true`
- **THEN** `CountdownBadge` displays a grey circular badge with a walking icon and `x.x / y.ykm` progress text

#### Scenario: POI_SELECTION_SKIP log event emitted
- **WHEN** `POISelectorService.select()` returns `None`
- **THEN** a `POI_SELECTION_SKIP` log event is emitted with `candidate_count` and `has_previous` fields
