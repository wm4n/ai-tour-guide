## 1. Playback Settings

- [x] 1.1 Add `TourPlaybackMode` and `TourUsageProfile` to shared app settings with `autoPlay` and `portable` defaults.
- [x] 1.2 Persist the new settings in `settings_provider.dart` and cover load/update behavior with unit tests.
- [x] 1.3 Add settings-screen controls for playback mode and usage profile so the journey behavior is configurable before start.

## 2. Tour Playback Queue Core

- [x] 2.1 Create `tour_playback_queue_provider.dart` with queue state, enqueue ordering, duplicate prevention, and queue state exposure (`currentPoi`, `nextPoi`, `queuedCount`).
- [x] 2.2 Add focused unit tests for idle-start playback, non-interrupting queueing, duplicate suppression, notify-only behavior, skip, and clear.
- [x] 2.3 Implement stale-item filtering with a 10-minute TTL plus `portable` (250m) and `car` (800m) distance thresholds.
- [x] 2.4 Integrate queue advancement with narration idle/error transitions so the next valid POI starts automatically.

## 3. Trigger Delivery Integration

- [x] 3.1 Update `TriggerProvider` so active journeys can still deliver candidates while the app lifecycle is backgrounded.
- [x] 3.2 Preserve cooldown and dedup filtering, but route automatic delivery to the queue in `autoPlay` mode and to local notifications in `notifyOnly` mode.
- [x] 3.3 Remove obsolete direct automatic narration handoff state from the trigger layer and update trigger tests for background auto-play and notify-only coverage.

## 4. Narration and UI Integration

- [x] 4.1 Add a queue-friendly `stopCurrent()` boundary to `NarrationProvider` and route existing skip behavior through it.
- [x] 4.2 Update `NarrationMiniBar` and any expanded narration surface to show minimal queue state and treat skip as "next tour item" when appropriate.
- [x] 4.3 Add or adjust widget tests for queued next-item labels and next-item control behavior.

## 5. Android Background Media Playback

- [x] 5.1 Add the `audio_service` dependency and Android manifest declarations required for media playback foreground service support.
- [x] 5.2 Extend `AudioPlayerService` and its fake implementation with current-item metadata plus media next/play/pause hooks while keeping the interface testable.
- [x] 5.3 Publish current POI metadata before queued narration starts and verify the Android media path with analyzer, targeted tests, and manual-device follow-up notes.

## 6. Journey Cleanup and Permissions

- [x] 6.1 Update the session stop flow so ending a journey clears the playback queue and stops active narration/media state.
- [x] 6.2 Extend session tests to cover queue cleanup on stop and permission-guidance edge cases for background location and notification visibility.

## 7. Verification and Review

- [x] 7.1 Run targeted Flutter tests for settings, queue, trigger, session, and narration UI changes.
- [x] 7.2 Run `flutter analyze` and the broader Flutter test suite after the feature is integrated.
- [x] 7.3 Record review notes and remaining manual Android checks, including lock-screen playback and foreground-notification coexistence.
