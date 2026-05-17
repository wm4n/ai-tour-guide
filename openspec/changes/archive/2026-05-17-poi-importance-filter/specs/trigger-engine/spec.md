## MODIFIED Requirements

### Requirement: Countdown-based narration trigger
After each narration completes, `TriggerNotifier` SHALL start a countdown timer. The duration SHALL be read dynamically from `appSettingsProvider.countdownSeconds` (not a hardcoded constant). When the countdown expires, `TriggerNotifier` SHALL automatically send a new narration request with all currently available (non-excluded) candidates. If a narration error occurs, the countdown SHALL also start to avoid a stuck state.

#### Scenario: Countdown starts after narration ends
- **WHEN** `NarrationState.status` transitions from `playing` to `idle`
- **THEN** `TriggerState.isCountingDown` becomes true and `countdownRemaining` is set to `appSettingsProvider.countdownSeconds`

#### Scenario: Countdown uses dynamic seconds from settings
- **WHEN** the user has changed `countdownSeconds` in SettingsScreen to 120
- **THEN** the next countdown after narration ends lasts 120 seconds

#### Scenario: Countdown updates every second
- **WHEN** countdown is active
- **THEN** `TriggerState.countdownRemaining` decreases by 1 second each tick

#### Scenario: Countdown expiry triggers new narration request
- **WHEN** `countdownRemaining` reaches zero
- **THEN** `TriggerNotifier` calls `_doCandidatesRequest()` with available non-excluded candidates

#### Scenario: Countdown starts on narration error
- **WHEN** `NarrationState.status` transitions from `loading` or `playing` to `error`
- **THEN** countdown starts (using current `countdownSeconds` setting) to allow retry

#### Scenario: skipCountdown() fires immediately
- **WHEN** `TriggerNotifier.skipCountdown()` is called
- **THEN** the timer is cancelled, `isCountingDown` becomes false, and `_doCandidatesRequest()` is called immediately

#### Scenario: No countdown if narration is already active
- **WHEN** countdown expires but `NarrationState.status` is `loading` or `playing`
- **THEN** `_doCandidatesRequest()` returns without sending a request

## ADDED Requirements

### Requirement: Displacement-wait mode after SKIP
When `TriggerNotifier` detects `NarrationState.lastEventWasSkip` becomes `true`, it SHALL cancel any active countdown, enter displacement-wait mode, and subscribe to the location stream. Once the user has moved at least `appSettingsProvider.skipDisplacementM` meters from the skip origin, the provider SHALL exit displacement-wait mode and call `_doCandidatesRequest()`.

#### Scenario: Skip transitions TriggerState to displacement-wait
- **WHEN** `NarrationState.lastEventWasSkip` transitions from `false` to `true`
- **THEN** `TriggerState.isWaitingForDisplacement` becomes `true`, `isCountingDown` becomes `false`, and location subscription begins

#### Scenario: movedMeters updates as user moves
- **WHEN** the location stream emits new positions while `isWaitingForDisplacement` is `true`
- **THEN** `TriggerState.movedMeters` reflects the cumulative distance from the skip origin

#### Scenario: Threshold crossed re-triggers narration
- **WHEN** `movedMeters` meets or exceeds `skipDisplacementM`
- **THEN** `isWaitingForDisplacement` becomes `false` and `_doCandidatesRequest()` is called

#### Scenario: Location subscription cancelled on dispose
- **WHEN** `TriggerNotifier` is disposed while in displacement-wait mode
- **THEN** the location subscription is cancelled and no further position events are processed

### Requirement: CountdownBadge displacement-wait UI
When `TriggerState.isWaitingForDisplacement` is `true`, the `CountdownBadge` widget SHALL display a grey circular badge with a walking icon and `x.x/y.y km` progress text instead of the countdown timer.

#### Scenario: Badge shows displacement progress
- **WHEN** `TriggerState.isWaitingForDisplacement` is `true`
- **THEN** `CountdownBadge` shows a grey badge with walking icon and `movedMeters / skipDisplacementM` progress

#### Scenario: Displacement badge hidden when not waiting
- **WHEN** both `isWaitingForDisplacement` and `isCountingDown` are `false`
- **THEN** `CountdownBadge` renders as `SizedBox.shrink()`
