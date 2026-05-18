## MODIFIED Requirements

### Requirement: Countdown-based narration trigger
After each narration completes, `TriggerNotifier` SHALL start a configurable countdown timer. When the countdown expires, `TriggerNotifier` SHALL automatically send a new narration request with all currently available (non-excluded) candidates. If a narration error occurs, the countdown SHALL also start to avoid a stuck state. Before calling `narrate()`, `TriggerNotifier` SHALL apply a dedup guard: if the user has not moved more than 30m since the last `narrate()` call AND the Jaccard similarity of the current candidate POI IDs versus the previous set is ≥ 0.8, the request SHALL be skipped, a `triggerSkip` log event with `reason: "poi_unchanged"` SHALL be emitted, and `_startCountdown()` SHALL be called to restart the heartbeat cycle. `_startCountdown()` SHALL NOT reset `_lastTriggerPosition` or `_lastCandidateIds`, preserving dedup state across countdown cycles.

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

---

### Requirement: CountdownBadge UI
The app SHALL display a circular countdown badge in the bottom-right corner of the map screen when `TriggerState.isCountingDown` is true. The badge SHALL be hidden during narration and when no countdown is active. The `CircularProgressIndicator` inside the badge SHALL be wrapped in `SizedBox.expand()` so it fills the full badge container (72×72 logical pixels), preventing the indicator from overlapping the centered countdown text.

#### Scenario: Badge visible during countdown
- **WHEN** `TriggerState.isCountingDown` is true
- **THEN** `CountdownBadge` widget is visible with a `CircularProgressIndicator` and remaining seconds text

#### Scenario: Badge hidden when not counting down
- **WHEN** `TriggerState.isCountingDown` is false
- **THEN** `CountdownBadge` renders as `SizedBox.shrink()` (zero size)

#### Scenario: Badge tap skips countdown
- **WHEN** user taps the `CountdownBadge`
- **THEN** `TriggerNotifier.skipCountdown()` is called

#### Scenario: CircularProgressIndicator fills container via SizedBox.expand
- **WHEN** `CountdownBadge` is rendered with `isCountingDown == true`
- **THEN** the `CircularProgressIndicator` is a direct child of a `SizedBox` with `width == null` and `height == null` (i.e. `SizedBox.expand()`), ensuring the ring fills the container and does not overlap the text column

---

### Requirement: Candidates list excludes session-played and cooled-down POIs
Before sending a narration request, `TriggerNotifier` SHALL filter out POIs that have been played in the current session (in-memory set) or are within the 24-hour DB cooldown window. If no candidates remain, `TriggerNotifier` SHALL call `_startCountdown()` to continue the heartbeat cycle.

#### Scenario: Session-played POI excluded from candidates
- **WHEN** a POI's `id` is in `_sessionPlayedIds`
- **THEN** that POI is NOT included in the `available` candidates list sent to the backend

#### Scenario: Cooldown POI excluded from candidates
- **WHEN** `LocalDB.isCooldown(poi.id, 24h)` returns true for a POI
- **THEN** that POI is NOT included in the `available` candidates list sent to the backend

#### Scenario: No available candidates restarts countdown
- **WHEN** all POIs in `_latestPois` are excluded by session or cooldown
- **THEN** `_doCandidatesRequest()` logs `triggerSkip` with reason "no_candidates_available" and calls `_startCountdown()` to continue the heartbeat

## REMOVED Requirements

### Requirement: Displacement-wait mode after SkipEvent
**Reason**: Displacement-wait は実際の都市旅遊場景中幾乎永遠無法滿足（500m 門檻），導致系統卡死。改為呼叫 `_startCountdown()` 讓倒數成為 heartbeat，行為更可預測。
**Migration**: SkipEvent 不再進入 displacement-wait 模式。系統改為重啟倒數計時，並在 countdown 到期後重試旁白（若 dedup guard 未阻擋）。`TriggerState` 移除 `isWaitingForDisplacement`、`skipLat`、`skipLon`、`movedMeters` 欄位。`_handleSkip()`、`_startDisplacementWatch()`、`_clearDisplacementWatch()` 方法和 `_locationSub` 欄位一併刪除。
