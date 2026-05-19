## MODIFIED Requirements

### Requirement: Countdown-based narration trigger
After each narration completes, `TriggerNotifier` SHALL start a configurable countdown timer. When the countdown expires, `TriggerNotifier` SHALL automatically send a new narration request with all currently available (non-excluded) candidates. If a narration error occurs, the countdown SHALL also start to avoid a stuck state. Before calling `narrate()`, `TriggerNotifier` SHALL apply a dedup guard: if the user has not moved more than 30m since the last `narrate()` call AND the Jaccard similarity of the current candidate POI IDs versus the previous set is ≥ 0.8, the request SHALL be skipped, a `triggerSkip` log event with `reason: "poi_unchanged"` SHALL be emitted, and `_startCountdown()` SHALL be called to restart the heartbeat cycle. `_startCountdown()` SHALL NOT reset `_lastTriggerPosition` or `_lastCandidateIds`, preserving dedup state across countdown cycles. When the backend selects a POI and narration begins (`prev.currentPoi == null && next.currentPoi != null`), `TriggerNotifier` SHALL clear `_lastCandidateIds` to empty, ensuring the dedup guard does not block the next request after a narration is consumed.

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

#### Scenario: skipCountdown() fires immediately and resets dedup state
- **WHEN** `TriggerNotifier.skipCountdown()` is called
- **THEN** the timer is cancelled, `isCountingDown` becomes false, `_lastTriggerPosition` and `_lastCandidateIds` are reset to null/empty, and `_doCandidatesRequest()` is called immediately

#### Scenario: No countdown if narration is already active
- **WHEN** countdown expires but `NarrationState.status` is `loading` or `playing`
- **THEN** `_doCandidatesRequest()` returns without sending a request

#### Scenario: Dedup guard skips request and restarts countdown when user hasn't moved and POIs unchanged
- **WHEN** countdown expires, user has moved < 30m from `_lastTriggerPosition`, and current candidate POI IDs have Jaccard similarity ≥ 0.8 with `_lastCandidateIds`
- **THEN** `narrate()` is NOT called, a `triggerSkip` log event with `reason: "poi_unchanged"` is emitted, and `_startCountdown()` is called

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

#### Scenario: _startCountdown() preserves dedup state
- **WHEN** `_startCountdown()` is called (from any path: narration end, error, dedup block, SkipEvent, available.isEmpty)
- **THEN** `_lastTriggerPosition` and `_lastCandidateIds` are NOT reset

#### Scenario: _lastCandidateIds cleared when backend selects a POI for narration
- **WHEN** `narrationProvider` state transitions from `currentPoi == null` to `currentPoi != null` (backend selected a POI and narration begins)
- **THEN** `TriggerNotifier` SHALL set `_lastCandidateIds = {}`, so the next countdown expiry sends a narration request rather than being blocked by the dedup guard

#### Scenario: Dedup guard does not block after narration is consumed (stationary user)
- **WHEN** a narration plays (backend selected POI from 5 candidates), countdown expires again, user has not moved, and available candidates are now 4 (one consumed)
- **THEN** `narrate()` is called (Jaccard of 4-element set vs empty `_lastCandidateIds` has no prior baseline, so guard is bypassed)

#### Scenario: Dedup guard still blocks after backend SKIP with unchanged POIs
- **WHEN** backend returns `SkipEvent` (no POI selected, `currentPoi` remains null), countdown expires again, user has not moved, and POI list is unchanged
- **THEN** `narrate()` is NOT called and `_startCountdown()` restarts the heartbeat
