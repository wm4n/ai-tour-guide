## MODIFIED Requirements

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
