## Why

Six narration UX regressions were identified after the continuous audio pipeline shipped: personas speak in third person, the LLM uses close-proximity language for distant POIs, consecutive "no data" responses are played redundantly, the frontend wastes backend calls when the user hasn't moved, the countdown starts before audio finishes, and the progress ring overlaps the countdown text. These are all small, independently deployable fixes that together make the narration experience feel polished and reliable.

## What Changes

- **Persona YAML rewrite (5 files)**: Remove third-person role labels from `system_prompt`, `confidence_labels`, and `no_data_context`; add `{distance_hint}` variable to `narration_template`
- **`POIContext.distance_m`**: New `float` field on the backend data model carrying distance from user to POI
- **`PromptBuilder` distance hint**: Derives a natural-language distance phrase (`就在你附近`, `前方不遠處`, `這附近`, `這一帶`) from `distance_m` and injects it into the narration template
- **`narration.py` API**: Passes `selected.distance_m` into `POIContext` construction
- **`MetaEvent.is_no_data`**: New boolean on the backend event model, set `True` when the POI has no Wikipedia article
- **Flutter `MetaEvent`**: Parses `is_no_data` from JSON, adds `isNoData` field
- **`NarrationNotifier` no-data dedup**: Tracks `_lastWasNoData`; if second consecutive no-data meta-event arrives, cancels the SSE subscription and transitions directly to idle without playing audio
- **`NarrationNotifier` audio-deferred idle**: Sets `_sseStreamEnded = true` on `EndEvent`, then subscribes to `AudioPlayerService.isPlayingStream`; only transitions to `idle` when both SSE has ended and audio is not playing
- **`TriggerNotifier` dedup guard**: Tracks `_lastTriggerPosition` and `_lastCandidateIds`; skips calling `narrate()` if the user hasn't moved >30 m and Jaccard similarity of POI IDs ≥ 0.8
- **`CountdownBadge` layout fix**: Wraps `CircularProgressIndicator` in `SizedBox.expand()` so it fills its 72×72 container rather than using Flutter's intrinsic 48×48 default

## Capabilities

### New Capabilities

None — all changes are enhancements to existing capabilities.

### Modified Capabilities

- `narration-stream`: `MetaEvent` gains `is_no_data` flag; frontend dedup logic changes when idle is entered; `POIContext` gains `distance_m`; PromptBuilder injects `distance_hint`
- `trigger-engine`: `TriggerNotifier` gains position + POI-ID dedup guard before each `narrate()` call
- `poi-map`: `CountdownBadge` layout fix (progress ring overlapping text)

## Impact

- **Backend**: `models/poi.py`, `prompts/builder.py`, `api/narration.py`, `services/narration_service.py`, all 5 persona YAMLs under `backend/prompts/personas/`
- **Frontend**: `narration_event.dart`, `narration_provider.dart`, `trigger_provider.dart`, `countdown_badge.dart`
- **Tests**: `test_prompt_builder.py`, `test_narration_service.py`, `narration_provider_test.dart`, `trigger_provider_test.dart`, new `countdown_badge_test.dart`
- **No breaking changes** to the public SSE API contract (new `is_no_data` field is additive and defaults to `false`)
