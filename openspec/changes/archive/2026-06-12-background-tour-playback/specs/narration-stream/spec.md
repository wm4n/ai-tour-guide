## ADDED Requirements

### Requirement: Queue-friendly narration stop boundary
`NarrationNotifier` SHALL expose a stop-current operation that cancels the active SSE subscription, resets queued audio playback state, and transitions narration back to `idle` without deciding what the next POI should be. Queue and session owners SHALL use that boundary to advance playback or clear state. The existing user-facing skip action SHALL delegate to the same stop-current behavior.

#### Scenario: Queue stop-current resets active narration to idle
- **WHEN** queue management requests the current narration to stop while audio or SSE streaming is active
- **THEN** `NarrationNotifier` cancels the active playback pipeline and transitions to `idle`

#### Scenario: User skip delegates to stop-current behavior
- **WHEN** the user activates skip while narration is active
- **THEN** the app uses the same stop-current path that queue advancement uses

## MODIFIED Requirements

### Requirement: NarrationSheet subtitle and controls
The narration sheet SHALL remain a draggable playback surface with a collapsed mini bar and an expanded subtitle/controls view. When queue mode is active, the collapsed and expanded controls SHALL expose the current POI plus minimal next-item queue state, and the skip control SHALL mean "next tour item" rather than "drop audio only".

#### Scenario: Collapsed mini bar shows next queued POI
- **WHEN** narration is active and the queue has another waiting POI
- **THEN** the mini bar shows the current POI plus the next queued POI name and queued count

#### Scenario: Skip control advances to the next queued POI
- **WHEN** the user taps skip while queue mode has a waiting item
- **THEN** the current narration stops and the next valid queued POI starts through the queue provider

#### Scenario: Existing playback controls remain visible without a queued item
- **WHEN** narration is active but no next queued POI exists
- **THEN** the narration sheet still shows the current POI and normal playback controls without queue metadata
