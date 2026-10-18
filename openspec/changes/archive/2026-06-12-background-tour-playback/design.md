## Context

The current Flutter app can already stream narration audio, track location, and surface local notifications, but the trigger-to-playback path still assumes foreground app lifecycle. Once the app is backgrounded or the screen is locked, nearby POIs may still be detected, yet long-form narration does not continue as a true pocket or in-car tour experience.

This change delivers the Android-first background playback slice described in:
- `openspec/changes/background-tour-playback/proposal.md`
- `docs/superpowers/specs/2026-06-11-background-tour-playback-design.md`
- `docs/superpowers/plans/2026-06-11-background-tour-playback.md`

The implementation spans trigger delivery, narration orchestration, persisted settings, Android media service setup, and session cleanup. It must stay scoped to Android background playback for active journeys without expanding into iOS, Android Auto, CarPlay, or a full queue-management UI.

## Goals / Non-Goals

**Goals:**
- Allow active Android journeys to keep delivering triggered POIs while the app is backgrounded.
- Insert a queue layer between trigger discovery and narration playback so long-form POIs do not interrupt each other.
- Support `autoPlay` and `notifyOnly` playback modes plus `portable` and `car` usage profiles.
- Prepare the audio boundary for Android media-service playback, metadata, and next/play/pause controls.
- Ensure ending a journey clears queue state and stops background playback-related state.

**Non-Goals:**
- iOS background playback or background location behavior.
- Android Auto, CarPlay, or rich lock-screen queue browsing.
- Smart route ranking, AI reprioritization, or a dedicated queue screen.
- Rewriting backend narration selection or POI ranking rules.

## Decisions

### 1. Introduce `TourPlaybackQueue` as the orchestration boundary

`TriggerProvider` will stop calling `NarrationProvider` directly for automatic journey playback. Instead, it will submit eligible candidate POIs to a new `TourPlaybackQueue` provider, which becomes the single owner of:
- current-versus-queued POI state
- duplicate prevention
- stale-item filtering
- queue-driven skip and clear behavior
- starting the next narration only when the narration layer is idle

This keeps `NarrationProvider` focused on a single SSE/audio stream while the queue handles multi-POI sequencing.

**Alternative considered:** background triggers calling `narrate()` directly and dropping overlapping POIs. Rejected because it loses POIs during 2-5 minute narration segments and does not match the requested "next item" experience.

### 2. Keep trigger discovery logic, change only the delivery target

The existing trigger engine already owns active-session checks, cooldown filtering, and countdown/dedup behavior. This change keeps those responsibilities in the trigger layer, but updates the final delivery step:
- if journey is inactive, do nothing
- if playback mode is `notifyOnly`, show a local notification
- if playback mode is `autoPlay`, enqueue candidates even when the app lifecycle is backgrounded

This is the smallest change that unlocks background delivery without rewriting the trigger engine from scratch in the same slice.

**Alternative considered:** replacing the trigger flow with a brand-new background-specific engine. Rejected for this change because it increases scope and risk across an already cross-cutting feature.

### 3. Persist playback mode and usage profile in shared app settings

Two user-facing settings drive the queue and trigger behavior:
- `TourPlaybackMode`: `autoPlay` or `notifyOnly`
- `TourUsageProfile`: `portable` or `car`

These values belong in the existing shared app settings layer so they can be read consistently by settings UI, trigger delivery, and queue stale-item checks.

**Alternative considered:** storing queue mode inside the queue provider only. Rejected because the choice must survive app restarts and be editable from settings before a journey starts.

### 4. Move Android playback onto an `audio_service + just_audio` boundary

The app will keep the existing `AudioPlayerService` abstraction, but the real Android implementation will initialize an `audio_service` handler behind that interface. The first slice must support:
- foreground media playback service declarations
- current POI metadata publication
- play, pause, and next controls
- playback continuity while the app is backgrounded or the screen is locked

Keeping the interface stable preserves fake implementations for tests and limits blast radius in Flutter code.

**Alternative considered:** wiring `audio_service` directly into feature providers. Rejected because it would spread Android-specific playback concerns across unrelated providers and tests.

### 5. Treat journey stop as the hard cleanup boundary

Journey teardown must clear the playback queue, stop active narration, and end background playback state together with location updates. The session provider remains the lifecycle owner; queue cleanup is injected as a stop-completion callback instead of leaking provider references into the session model.

**Alternative considered:** letting queue state self-expire without explicit session cleanup. Rejected because it can leave stale media state or queued POIs after the user explicitly ends the journey.

## Risks / Trade-offs

- [Media and location foreground services may create confusing Android notifications] -> Keep the service boundary minimal in this slice and require manual Android verification before release.
- [Queue-delivered narration currently uses a narrower handoff than the old direct trigger path] -> Capture the queue contract explicitly in specs and keep the narration provider focused on one stream at a time.
- [Portable/car stale-distance defaults may need tuning in real travel conditions] -> Use fixed, testable thresholds now and leave ranking/tuning for future changes.
- [Background permissions vary by Android version] -> Start-journey guidance must distinguish foreground location, background location guidance, and notification visibility limitations.

## Migration Plan

1. Add persisted playback mode and usage profile settings, plus settings UI controls.
2. Create `TourPlaybackQueue` with unit tests for enqueueing, deduplication, stale filtering, skip, and clear.
3. Route trigger delivery through queue-or-notification behavior for active journeys, including background lifecycle states.
4. Make narration UI and provider behavior queue-aware, especially "next item" semantics.
5. Introduce Android media playback service wiring and metadata publication behind `AudioPlayerService`.
6. Update journey teardown to clear queue and playback state.
7. Run targeted Flutter tests, analyzer, and manual Android locked-screen verification.

**Rollback:** The implementation is additive around existing providers and Android manifest setup. If the feature needs to be reverted, remove the queue provider integration, the new settings, and the media-service declarations together so the app returns to direct foreground narration behavior.

## Open Questions

- No blocking design questions remain for `/opsx:apply`.
- Manual Android verification is still required to confirm that location and media foreground services coexist cleanly and that lock-screen controls match queue behavior.
