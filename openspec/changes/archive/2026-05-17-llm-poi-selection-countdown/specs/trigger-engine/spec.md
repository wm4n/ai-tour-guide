## REMOVED Requirements

### Requirement: Automatic narration triggering within radius
**Reason**: Replaced by countdown-based trigger. The `TriggerEngine` distance evaluation loop is removed entirely. Narration is now triggered by the countdown timer expiring or user tapping the CountdownBadge, not by distance thresholds.
**Migration**: `TriggerNotifier` no longer calls `TriggerEngine.evaluate()`. All trigger logic is now inside `TriggerNotifier` using `Timer.periodic`. Session dedup and 24h cooldown filtering remain in `TriggerNotifier._doCandidatesRequest()`.

### Requirement: Haversine distance calculation
**Reason**: No longer used as a trigger mechanism. Distance is now a metadata field (`distance_m`) included in each `POICandidate` sent to the backend for LLM selection context.
**Migration**: `distance_m` values in `POICandidate` are derived from `POIProvider`'s existing distance computation. The haversine utility function may be removed if unused elsewhere.

---

## MODIFIED Requirements

### Requirement: Manual trigger bypasses TriggerEngine
The app SHALL allow direct invocation of narration without going through the countdown timer. Users may tap the CountdownBadge to skip the countdown and trigger narration immediately. The manual map marker tap path SHALL remain unchanged.

#### Scenario: User taps CountdownBadge during countdown
- **WHEN** user taps the CountdownBadge while countdown is active
- **THEN** the countdown timer is cancelled and `TriggerNotifier.skipCountdown()` triggers a new narration request immediately

#### Scenario: User taps marker while POI is in cooldown
- **WHEN** user taps a POI marker on the map
- **THEN** narration is triggered regardless of cooldown or dedup state

---

## ADDED Requirements

### Requirement: Countdown-based narration trigger
After each narration completes, `TriggerNotifier` SHALL start a 90-second countdown timer. When the countdown expires, `TriggerNotifier` SHALL automatically send a new narration request with all currently available (non-excluded) candidates. If a narration error occurs, the countdown SHALL also start to avoid a stuck state.

#### Scenario: Countdown starts after narration ends
- **WHEN** `NarrationState.status` transitions from `playing` to `idle`
- **THEN** `TriggerState.isCountingDown` becomes true and `countdownRemaining` is set to 90 seconds

#### Scenario: Countdown updates every second
- **WHEN** countdown is active
- **THEN** `TriggerState.countdownRemaining` decreases by 1 second each tick

#### Scenario: Countdown expiry triggers new narration request
- **WHEN** `countdownRemaining` reaches zero
- **THEN** `TriggerNotifier` calls `_doCandidatesRequest()` with available non-excluded candidates

#### Scenario: Countdown starts on narration error
- **WHEN** `NarrationState.status` transitions from `loading` or `playing` to `error`
- **THEN** countdown starts (90s) to allow retry

#### Scenario: skipCountdown() fires immediately
- **WHEN** `TriggerNotifier.skipCountdown()` is called
- **THEN** the timer is cancelled, `isCountingDown` becomes false, and `_doCandidatesRequest()` is called immediately

#### Scenario: No countdown if narration is already active
- **WHEN** countdown expires but `NarrationState.status` is `loading` or `playing`
- **THEN** `_doCandidatesRequest()` returns without sending a request

---

### Requirement: CountdownBadge UI
The app SHALL display a circular countdown badge in the bottom-right corner of the map screen when `TriggerState.isCountingDown` is true. The badge SHALL be hidden during narration and when no countdown is active.

#### Scenario: Badge visible during countdown
- **WHEN** `TriggerState.isCountingDown` is true
- **THEN** `CountdownBadge` widget is visible with a `CircularProgressIndicator` and remaining seconds text

#### Scenario: Badge hidden when not counting down
- **WHEN** `TriggerState.isCountingDown` is false
- **THEN** `CountdownBadge` renders as `SizedBox.shrink()` (zero size)

#### Scenario: Badge tap skips countdown
- **WHEN** user taps the `CountdownBadge`
- **THEN** `TriggerNotifier.skipCountdown()` is called

---

### Requirement: First-run auto-trigger on POI load
On the first POI load in a session (before any narration has played), `TriggerNotifier` SHALL automatically trigger narration when POIs become available and narration is idle.

#### Scenario: Narration fires on first POI load
- **WHEN** `poiProvider` emits a non-empty list for the first time and no narration has ever played in this session
- **THEN** `TriggerNotifier` calls `_doCandidatesRequest()` immediately without waiting for countdown

#### Scenario: Subsequent POI updates do not re-trigger automatically
- **WHEN** `poiProvider` emits updated POIs after narration has already played once
- **THEN** `TriggerNotifier` does NOT trigger narration (waits for countdown to expire)

---

### Requirement: Candidates list excludes session-played and cooled-down POIs
Before sending a narration request, `TriggerNotifier` SHALL filter out POIs that have been played in the current session (in-memory set) or are within the 24-hour DB cooldown window.

#### Scenario: Session-played POI excluded from candidates
- **WHEN** a POI's `id` is in `_sessionPlayedIds`
- **THEN** that POI is NOT included in the `available` candidates list sent to the backend

#### Scenario: Cooldown POI excluded from candidates
- **WHEN** `LocalDB.isCooldown(poi.id, 24h)` returns true for a POI
- **THEN** that POI is NOT included in the `available` candidates list sent to the backend

#### Scenario: No available candidates skips request
- **WHEN** all POIs in `_latestPois` are excluded by session or cooldown
- **THEN** `_doCandidatesRequest()` returns without sending a request and logs `triggerSkip` with reason "no_candidates_available"

---

### Requirement: previous_selection passed on subsequent requests
`TriggerNotifier` SHALL track the last selected POI's id, name, and full script buffer after each narration completes, and include them as `PreviousSelection` in every subsequent narration request within the session.

#### Scenario: PreviousSelection sent on second request
- **WHEN** a second narration request is triggered after the first has completed
- **THEN** `BackendClient.narrate()` is called with `previousSelection` containing the first narration's `poi_id`, `poi_name`, and `scriptBuffer`

#### Scenario: No PreviousSelection on first request
- **WHEN** the very first narration request is triggered in a session
- **THEN** `BackendClient.narrate()` is called with `previousSelection == null`
