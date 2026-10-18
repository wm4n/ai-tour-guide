# Capability: Background Media Playback

## Purpose

Defines Android foreground media playback support for queued tour narration so playback and transport controls remain available while the app is backgrounded.

---

## Requirements

### Requirement: Android playback uses a media foreground service
The Android app SHALL run long-form journey narration through a media-playback foreground service backed by the app's audio service abstraction. Once a queued narration item starts, playback SHALL continue while the app is backgrounded or the screen is locked, as long as the journey remains active.

#### Scenario: Locked screen playback continues during an active journey
- **WHEN** a queued narration item is already playing and the user locks the screen
- **THEN** the narration continues without requiring the app to return to the foreground

#### Scenario: Media service starts when queued playback begins
- **WHEN** the queue starts a narration item on Android
- **THEN** the app initializes the media foreground service before or during playback startup

---

### Requirement: Current POI metadata and controls are published to Android media surfaces
Before narration begins for a queued POI, the app SHALL publish the POI identity to the media service as the current media item. The Android playback notification and lock-screen controls SHALL expose play, pause, and next actions, where next maps to the queue's next-item behavior.

#### Scenario: Current POI metadata is published before playback
- **WHEN** the queue selects the next POI to narrate
- **THEN** the media service publishes that POI's identifier and title as the active media item

#### Scenario: Next control advances the queue
- **WHEN** the user taps the Android media notification's next action while narration is playing
- **THEN** the app routes that action through the queue skip path and starts the next valid queued POI if one exists

---

### Requirement: Media service lifecycle matches journey lifecycle
The Android build SHALL declare the media playback foreground-service permission, service, and media-button receiver required by the selected audio service package. When the journey ends or the queue is cleared with no active playback left, the media foreground state SHALL stop.

#### Scenario: Android manifest declares media playback service support
- **WHEN** the Android app is built for this capability
- **THEN** the manifest includes the media playback foreground-service permission plus the required audio service and media-button receiver declarations

#### Scenario: Journey end stops media foreground playback state
- **WHEN** the user ends the active journey
- **THEN** the media foreground playback state stops and its ongoing playback notification is removed
