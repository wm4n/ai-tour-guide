## MODIFIED Requirements

### Requirement: Countdown-based narration trigger
After the first eligible POI load and after each narration completes or errors, `TriggerNotifier` SHALL continue to run its countdown and dedup cycle only while the journey is active. When that cycle produces eligible candidates, `TriggerNotifier` SHALL deliver them according to playback mode instead of calling narration directly: `autoPlay` submits candidates to `TourPlaybackQueue`, and `notifyOnly` shows a local notification for the first eligible POI. This delivery SHALL remain active even when the app lifecycle is backgrounded.

#### Scenario: Countdown starts after narration ends
- **WHEN** `NarrationState.status` transitions from `playing` to `idle` during an active journey
- **THEN** `TriggerState.isCountingDown` becomes true and the countdown restarts with the configured duration

#### Scenario: Background active journey queues candidates in auto-play mode
- **WHEN** the countdown or trigger cycle produces eligible candidates while the journey is active, playback mode is `autoPlay`, and the app lifecycle is not `resumed`
- **THEN** `TriggerNotifier` submits those candidates to `TourPlaybackQueue`

#### Scenario: Background active journey notifies instead of queueing in notify-only mode
- **WHEN** the countdown or trigger cycle produces eligible candidates while the journey is active and playback mode is `notifyOnly`
- **THEN** `TriggerNotifier` shows a local POI notification instead of starting narration or queueing items

#### Scenario: Inactive journey does not deliver candidates
- **WHEN** the countdown expires while the journey is not active
- **THEN** `TriggerNotifier` does not queue, notify, or start narration

#### Scenario: Dedup guard still blocks unchanged candidate sets
- **WHEN** the trigger cycle produces a candidate set that matches the existing dedup guard's unchanged-position and unchanged-candidates conditions
- **THEN** `TriggerNotifier` skips delivery, logs the dedup skip, and restarts the countdown

### Requirement: First-run auto-trigger on POI load
On the first eligible POI load in an active journey, `TriggerNotifier` SHALL immediately deliver candidates through the queue-or-notification path without waiting for the countdown. Subsequent POI refreshes SHALL continue using the normal trigger cycle.

#### Scenario: First POI load in auto-play mode queues immediately
- **WHEN** eligible POIs become available for the first time in an active journey and playback mode is `autoPlay`
- **THEN** `TriggerNotifier` immediately submits candidates to `TourPlaybackQueue`

#### Scenario: First POI load in notify-only mode notifies immediately
- **WHEN** eligible POIs become available for the first time in an active journey and playback mode is `notifyOnly`
- **THEN** `TriggerNotifier` immediately shows a local POI notification

#### Scenario: Later POI refreshes wait for the normal trigger cycle
- **WHEN** POIs update after the first eligible delivery has already happened in the same journey
- **THEN** `TriggerNotifier` does not perform another immediate first-run delivery

### Requirement: Candidates list excludes session-played and cooled-down POIs
Before delivering candidates to the queue or notification path, `TriggerNotifier` SHALL filter out POIs that have already played in the current session or remain inside the cooldown window. If no candidates remain after filtering, `TriggerNotifier` SHALL restart the countdown instead of attempting delivery.

#### Scenario: Session-played POI is excluded from delivery
- **WHEN** a POI is already present in the session-played set
- **THEN** that POI is omitted from the delivered candidate list

#### Scenario: Cooldown POI is excluded from delivery
- **WHEN** `LocalDB.isCooldown(poi.id, 24h)` returns true for a POI
- **THEN** that POI is omitted from the delivered candidate list

#### Scenario: No eligible candidates restarts the trigger cycle
- **WHEN** all available POIs are filtered out by session-played or cooldown rules
- **THEN** `TriggerNotifier` logs the empty-delivery skip and restarts the countdown

### Requirement: Manual trigger bypasses countdown
The app SHALL continue to support manual delivery without waiting for the countdown. Tapping the countdown badge SHALL cancel the active countdown and immediately re-run candidate delivery through the queue-or-notification path. The manual map-marker tap path SHALL continue to request direct narration immediately, bypassing the queue, cooldown, and dedup rules for that explicit user action.

#### Scenario: Countdown badge immediately re-runs auto-play delivery
- **WHEN** the user taps the countdown badge during an active countdown and playback mode is `autoPlay`
- **THEN** the countdown is cancelled and eligible candidates are submitted to `TourPlaybackQueue` immediately

#### Scenario: Countdown badge immediately re-runs notify-only delivery
- **WHEN** the user taps the countdown badge during an active countdown and playback mode is `notifyOnly`
- **THEN** the countdown is cancelled and the first eligible POI notification is shown immediately

#### Scenario: Manual map marker tap still bypasses queue policy
- **WHEN** the user taps a POI marker directly on the map
- **THEN** the app starts direct narration for that POI without waiting for countdown or queue ordering

## REMOVED Requirements

### Requirement: previous_selection passed on subsequent requests
**Reason**: In this Android-first queue slice, `TriggerNotifier` no longer owns the direct `BackendClient.narrate()` handoff for automatic playback, so previous-selection chaining is deferred until a later queue-aware narration handoff design.

**Migration**: Queue-initiated narration requests continue to use `previousSelection == null` until a future change reintroduces cross-item context passing at the queue boundary.
