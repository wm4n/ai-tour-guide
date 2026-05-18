## MODIFIED Requirements

### Requirement: Countdown-based narration trigger
After each narration completes, `TriggerNotifier` SHALL start a configurable countdown timer. When the countdown expires, `TriggerNotifier` SHALL automatically send a new narration request with all currently available (non-excluded) candidates. If a narration error occurs, the countdown SHALL also start to avoid a stuck state. Before calling `narrate()`, `TriggerNotifier` SHALL apply a dedup guard: if the user has not moved more than 30m since the last `narrate()` call AND the Jaccard similarity of the current candidate POI IDs versus the previous set is ≥ 0.8, the request SHALL be skipped and a `triggerSkip` log event with `reason: "poi_unchanged"` SHALL be emitted.

#### Scenario: Countdown starts after narration ends
- **WHEN** `NarrationState.status` transitions from `playing` to `idle`
- **THEN** `TriggerState.isCountingDown` becomes true and `countdownRemaining` is set to the configured countdown duration

#### Scenario: Countdown updates every second
- **WHEN** countdown is active
- **THEN** `TriggerState.countdownRemaining` decreases by 1 second each tick

#### Scenario: Countdown expiry triggers new narration request
- **WHEN** `countdownRemaining` reaches zero
- **THEN** `TriggerNotifier` calls `_doCandidatesRequest()` with available non-excluded candidates

#### Scenario: Countdown starts on narration error
- **WHEN** `NarrationState.status` transitions from `loading` or `playing` to `error`
- **THEN** countdown starts to allow retry

#### Scenario: skipCountdown() fires immediately
- **WHEN** `TriggerNotifier.skipCountdown()` is called
- **THEN** the timer is cancelled, `isCountingDown` becomes false, and `_doCandidatesRequest()` is called immediately

#### Scenario: No countdown if narration is already active
- **WHEN** countdown expires but `NarrationState.status` is `loading` or `playing`
- **THEN** `_doCandidatesRequest()` returns without sending a request

#### Scenario: Dedup guard skips request when user hasn't moved and POIs unchanged
- **WHEN** countdown expires, user has moved < 30m from `_lastTriggerPosition`, and current candidate POI IDs have Jaccard similarity ≥ 0.8 with `_lastCandidateIds`
- **THEN** `narrate()` is NOT called and a `triggerSkip` log event with `reason: "poi_unchanged"` is emitted

#### Scenario: Dedup guard allows request when user has moved
- **WHEN** countdown expires and user has moved ≥ 30m from `_lastTriggerPosition`
- **THEN** `narrate()` is called regardless of POI similarity

#### Scenario: Dedup guard allows request when POI set has changed significantly
- **WHEN** countdown expires, user has not moved, but current candidate Jaccard similarity < 0.8 versus `_lastCandidateIds`
- **THEN** `narrate()` is called

#### Scenario: First-ever trigger bypasses dedup guard
- **WHEN** `_lastTriggerPosition` is null (no prior trigger in this session)
- **THEN** `narrate()` is called without checking distance or Jaccard similarity

#### Scenario: _lastTriggerPosition and _lastCandidateIds updated on each narrate() call
- **WHEN** `narrate()` is called (dedup guard passed)
- **THEN** `_lastTriggerPosition` is set to current GPS position and `_lastCandidateIds` is set to the current candidate POI ID set
