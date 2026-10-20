# Background Tour Playback Design

**Date:** 2026-06-11  
**Status:** Draft for review  
**Scope:** Android-first background long-form tour playback with a geographic playback queue

## 1. Problem

The current app behaves like a foreground tour guide. It can stream narration audio with `just_audio`, track location, and notify in the background, but the trigger path is still tied to foreground app lifecycle. When the app is in the background, the trigger provider returns early and does not start narration.

The desired product behavior is closer to a guided audio tour:

- The user starts a journey, puts the phone in a pocket, wears headphones, or mounts the device in a car.
- When the user passes important points of interest, the app plays long-form narration, typically 2-5 minutes.
- If another POI is detected while a narration is already playing, the new item should wait in a queue instead of interrupting the current story.
- The first implementation should support Android background playback and background location. Future work should extend the same model to fuller media controls and car-oriented experiences.

## 2. Goals

- Android-first background tour mode.
- Continue location-triggered narration while the app is backgrounded after the user explicitly starts a journey.
- Add a playback queue for long-form POI narration.
- Allow automatic background playback or notification-only mode.
- Support portable and car usage profiles.
- Introduce a media-service-oriented audio boundary so future lock-screen, headset, Android Auto, and CarPlay work can build on the same core model.
- Keep the first implementation focused enough to verify on an Android device.

## 3. Non-Goals

- iOS background implementation in this change.
- Android Auto or CarPlay UI integration.
- A complete queue management screen.
- Complex AI ranking or route planning.
- Short navigation-style ducking as the primary playback model.
- Rewriting backend narration selection.

## 4. Product Behavior

When the user taps "Start Journey", the app enters tour mode. On Android, tour mode keeps a foreground location notification alive and continues evaluating nearby POIs in the background.

The app supports two background trigger behaviors:

- **Auto-play:** nearby POIs are added to the tour playback queue. If nothing is playing, the next valid item starts automatically.
- **Notify only:** nearby POIs create a local notification but are not automatically queued.

The app supports two usage profiles:

- **Portable tour:** intended for walking, pocket use, and headphones. It uses a smaller trigger radius and stricter stale-item checks.
- **Car tour:** intended for driving and dashboard mounts. It uses a larger trigger radius and a larger distance allowance before a queued item becomes stale.

Long-form narration is treated as the main audio source during tour mode. This is different from short Google Maps-style prompts. If another music app is playing, AI Tour Guide is expected to take primary audio focus while narration plays.

## 5. Recommended Approach

Use a dedicated tour playback queue between the trigger engine and narration playback:

```text
LocationService / PoiProvider / TriggerProvider
  -> TourPlaybackQueue.enqueue(candidates)
  -> NarrationProvider.narrate(...)
  -> AudioPlayerService
```

`TriggerProvider` should discover candidate POIs. It should not decide whether to interrupt playback, queue an item, drop a duplicate, or notify only. Those responsibilities belong to `TourPlaybackQueue`.

This is the recommended approach because it supports the requested background long-form tour behavior while keeping future media controls and car features aligned with one playback model.

## 6. Alternatives Considered

### Option 1: Minimal Background Auto-Play

Trigger directly starts narration in the background. If narration is already playing, new POIs are skipped.

This is fastest, but it loses POIs during long-form narration and does not match the desired "next item" behavior.

### Option 2: Tour Playback Queue

Triggered POIs enter a queue. Current narration is not interrupted. Users can skip to the next queued item. Background behavior is controlled by tour settings.

This is the selected approach. It is larger than Option 1 but directly matches pocket, headphone, and car-mount use.

### Option 3: Full Media App / Car Mode

Build Option 2 plus complete lock-screen queue controls, Android Auto, and CarPlay direction.

This is the right long-term direction, but it is too large for the first Android-first background playback change.

## 7. Architecture

### 7.1 TourPlaybackQueue

Add a new feature-level provider responsible for queue state and playback orchestration.

Responsibilities:

- Track the currently playing POI.
- Track queued POIs.
- Prevent duplicate POIs from being queued.
- Respect auto-play versus notification-only mode.
- Start playback when the queue has an eligible item and narration is idle.
- Skip expired or distant queue items before playback.
- Handle user skip by stopping the current narration and advancing to the next valid queued item.
- Clear queue state when the journey ends.

The queue should expose simple state for UI:

- current POI
- next POI
- queued count
- playback mode
- usage profile

### 7.2 TriggerProvider

Change `TriggerProvider` from "trigger means narrate now" to "trigger means submit candidates".

Current foreground lifecycle behavior blocks background narration:

```dart
if (lifecycleState != AppLifecycleState.resumed) return;
```

That gate should be replaced by tour-mode-aware behavior:

- If journey is inactive, do nothing.
- If notify-only mode is active, show a notification.
- If auto-play mode is active, enqueue candidates even when the app is backgrounded.

Existing cooldown, session-played, and dedup guard behavior should remain, but final delivery goes through `TourPlaybackQueue`.

### 7.3 NarrationProvider

`NarrationProvider` remains responsible for one narration stream at a time:

- call backend `/narration`
- process SSE events
- enqueue audio chunks
- update current subtitle and progress
- record completed narration history

It should not own multi-POI queue policy.

The existing `skip()` behavior should become compatible with queue-level skip:

- user-level skip asks `TourPlaybackQueue` to advance
- queue stops the current narration
- queue starts the next valid item if available

### 7.4 AudioPlayerService

Move the real Android audio implementation toward an `audio_service + just_audio` boundary.

The first implementation should support:

- background playback while the screen is locked
- Android foreground media service declaration
- current POI media metadata
- play, pause, and next actions

The existing fake audio service should remain lightweight for unit tests.

### 7.5 Android Platform Setup

The existing Android manifest already declares background location and foreground location service permissions. Add the media playback side required by the selected audio service package:

- foreground service permission/type for media playback
- audio service media button receiver and service declarations, following the package's Android setup

The app will have two foreground-service concerns:

- location service for background positioning
- media playback service for long-form narration

The implementation should verify they do not produce conflicting or confusing persistent notifications.

## 8. Queue Rules

The first implementation should use these rules:

- If POI A is playing and POI B is triggered, B is queued and A continues.
- A POI is not queued if it is already playing, already queued, already played in the current session, or in cooldown.
- Queue order follows trigger order using the backend-selected candidate order. No complex re-ranking in this change.
- Queue items expire after a fixed time window. Initial default: 10 minutes.
- Before playback, the app checks the current user distance to the POI.
- Portable profile skips stale queued items beyond 250m.
- Car profile skips stale queued items beyond 800m.
- User skip stops the current narration and starts the next valid queued item.
- Ending the journey clears the queue, stops location updates, and stops active narration.

## 9. Settings and UX

Add settings for:

- **Tour playback mode**
  - Auto-play
  - Notify only
- **Usage profile**
  - Portable tour
  - Car tour

Surface minimal queue state in the existing narration UI:

- current POI
- next POI
- queued count

The narration mini bar's skip control should be treated as "next tour item" when queue mode is active.

When starting a journey, if Android background location or notification permission is missing, the app should explain what is missing and guide the user to settings. A full onboarding redesign is outside this change.

## 10. Error Handling

- If narration stream fails, mark the item failed and advance to the next valid queued item after a short cooldown.
- If audio service fails to start, show an error in the existing narration UI and keep the item available for retry.
- If location permission is revoked during a journey, stop background triggering and surface a permission error.
- If notification permission is denied, auto-play mode may still work, but the app should warn that background visibility and controls are limited.
- If all queued items expire or become too far away, clear them and wait for the next trigger cycle.

## 11. Testing

### Unit Tests

Add focused tests for `TourPlaybackQueue`:

- playing item is not interrupted when a new POI is triggered
- duplicate POIs are not queued
- skip advances to the next valid item
- expired items are dropped
- too-distant items are dropped based on usage profile
- notify-only mode does not enqueue
- ending a journey clears queue state

Update trigger tests:

- background lifecycle no longer blocks auto-play queueing during active journeys
- notify-only mode calls notification service
- inactive journey does not enqueue or notify

### Fakes

Extend fakes only where needed:

- fake queue/narration integration
- fake location position access for stale distance checks
- fake audio service state transitions for pause, resume, and skip

### Manual Android Verification

Verify on an Android device or emulator capable of foreground service behavior:

1. Start a journey.
2. Lock the screen or background the app.
3. Simulate or reach a POI trigger.
4. Confirm narration starts in auto-play mode.
5. Trigger a second POI while the first is playing.
6. Confirm the second POI enters queue without interrupting the first.
7. Use skip to advance to the next item.
8. Switch to notify-only mode and confirm triggers create notifications without queueing.
9. End the journey and confirm location/audio foreground notifications stop.

## 12. Future Work

- iOS background audio and background location support.
- Rich lock-screen queue controls.
- Android Auto support.
- CarPlay support.
- Smarter queue ranking by route direction, speed, distance, and POI importance.
- Optional short-summary mode for dense driving areas.
- Offline prefetching of generated narration for planned routes.
