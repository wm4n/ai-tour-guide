# Capability: Tour Playback Queue

## Purpose

Defines queue-based automatic journey playback so triggered POIs can be ordered, filtered, and advanced without interrupting the current narration.

---

## Requirements

### Requirement: Queue triggered POIs during an active journey
The system SHALL create and maintain a tour playback queue for automatic journey playback. When an active journey in `autoPlay` mode receives triggered POI candidates, the queue SHALL keep the current narration uninterrupted, append new eligible POIs in trigger order, and reject POIs that are already playing, already queued, already played in the current session, or still filtered out by the trigger layer.

#### Scenario: Idle queue starts the first POI immediately
- **WHEN** an active journey in `autoPlay` mode enqueues a POI while narration is idle
- **THEN** that POI becomes the current queue item and narration starts without waiting for another trigger

#### Scenario: Current narration is not interrupted by a later trigger
- **WHEN** POI A is already playing and POI B is triggered
- **THEN** POI A continues playing and POI B is stored as the next queued item

#### Scenario: Duplicate or ineligible POIs are ignored
- **WHEN** a triggered POI matches the current item, a queued item, or a POI the trigger layer already marked as unavailable
- **THEN** the queue does not add a second copy of that POI

---

### Requirement: Queue honors playback mode and usage profile rules
The queue SHALL read the persisted playback mode and usage profile before accepting or starting items. In `notifyOnly` mode, enqueue requests SHALL not create a current item or queued items. Before starting any queued POI, the queue SHALL discard items older than 10 minutes and items whose current distance exceeds 250 metres in `portable` mode or 800 metres in `car` mode.

#### Scenario: Notify-only mode does not create queue state
- **WHEN** the trigger layer calls enqueue while playback mode is `notifyOnly`
- **THEN** the queue keeps `currentPoi == null` and `queuedCount == 0`

#### Scenario: Portable profile drops stale or too-distant items
- **WHEN** the next queued POI is older than 10 minutes or more than 250 metres away in `portable` mode
- **THEN** the queue discards that item and evaluates the next queued POI instead

#### Scenario: Car profile allows farther queued items
- **WHEN** the next queued POI is within 10 minutes and within 800 metres in `car` mode
- **THEN** the queue keeps the item eligible for playback

---

### Requirement: Queue exposes next-item controls and cleanup behavior
The queue SHALL expose `currentPoi`, `nextPoi`, and `queuedCount` for UI and playback controls. A queue-driven skip SHALL stop the current narration and immediately attempt playback of the next valid queued POI. Ending a journey SHALL clear the current item, all queued items, and any queue-owned playback state.

#### Scenario: Skip advances to the next valid queued POI
- **WHEN** the user invokes the queue's next-item action while one POI is playing and another is queued
- **THEN** the current narration stops and the next valid queued POI becomes the new current item

#### Scenario: Ending the journey clears queue state
- **WHEN** the journey transitions to its ending flow
- **THEN** the queue clears `currentPoi`, empties all queued POIs, and stops any active queue-managed narration
