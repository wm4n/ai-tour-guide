## Context

After the continuous audio pipeline shipped, six UX regressions were identified through testing. These are independent, small fixes that together significantly improve narration quality and reliability. The existing architecture spans:

- **Backend**: Python/FastAPI with `POIContext` data model, `PromptBuilder` for LLM prompts, `NarrationService` for SSE event streaming, and 5 persona YAML files
- **Frontend**: Flutter/Riverpod with `NarrationNotifier` (SSE consumer), `TriggerNotifier` (countdown/fire controller), `AudioPlayerService` (async audio queue), and `CountdownBadge` widget

All fixes are additive or small rewrites. No breaking changes to the public SSE API contract.

## Goals / Non-Goals

**Goals:**
- Remove third-person persona self-references from all 5 YAML files
- Inject spatial distance language into LLM prompts so persona uses appropriate proximity vocabulary
- Suppress consecutive "no data" narrations so the same "I don't know this area" audio is not replayed
- Prevent redundant backend calls when the user hasn't moved and visible POIs are the same
- Defer the `idle` transition until audio playback truly finishes (not just when SSE stream ends)
- Fix `CircularProgressIndicator` layout overlap with countdown text in `CountdownBadge`

**Non-Goals:**
- Changing the narration pipeline architecture or SSE event contract (beyond additive `is_no_data` field)
- Adding new persona types or languages
- Changing TTS provider or audio format
- Modifying POI discovery or ranking logic

## Decisions

**D1: `is_no_data` as an additive field on `MetaEvent`**

The backend already emits a `MetaEvent` at the start of every narration. Adding `is_no_data: bool = False` as a defaulted field means old clients ignore it and no API versioning is needed. Alternative considered: a separate `NoDataEvent` type — rejected because it adds a new SSE event discriminator requiring coordinated frontend + backend deploys.

**D2: `_lastWasNoData` persists across narrations within a session (not reset on `narrate()` start)**

This means the second and all subsequent consecutive no-data responses are suppressed. If the user moves to a new POI with data, `_lastWasNoData` becomes `false` and the next no-data narration plays again (first time). This gives the user one "I don't know this area" message and then silence — which is a better UX than repeated apologies.

**D3: Audio-deferred idle via `isPlayingStream` subscription**

`NarrationNotifier` subscribes to `AudioPlayerService.isPlayingStream` when `EndEvent` arrives instead of transitioning to idle immediately. Alternative considered: adding an explicit "audio done" callback or event — rejected because `isPlayingStream` already exists and polling it via a stream listener is simpler. Edge case where audio finishes before `EndEvent` is handled naturally (stream emits `false` immediately when subscribed).

**D4: Jaccard similarity + 30m distance for TriggerProvider dedup**

Two conditions must both be true to skip a `narrate()` call: (1) user moved less than 30m from last trigger position, and (2) Jaccard similarity of current vs. previous candidate POI IDs ≥ 0.8. This is more robust than exact-match dedup because POIs can appear/disappear at range edges without being truly "new" content. The 30m threshold matches the smallest `distance_hint` bucket (`"就在你附近"` < 30m) so movement that changes spatial context always fires.

**D5: `SizedBox.expand()` for `CircularProgressIndicator`**

Flutter's intrinsic size for `CircularProgressIndicator` is ~48×48 which is smaller than the 72×72 container, causing misalignment. `SizedBox.expand()` forces the indicator to fill the full container. `strokeWidth: 3` keeps the ring thin enough to leave the center clear for text. Applied to both `CountdownBadge` and `_DisplacementBadge` for consistency.

**D6: `{distance_hint}` injected via `PromptBuilder` from `POIContext.distance_m`**

Distance is computed server-side (in `poi_selector.py`) when POIs are ranked and stored as `distance_m` on the selected POI. Passing it through `POIContext` to `PromptBuilder` keeps distance-to-language mapping centralized in the backend. The 4-bucket binning (`< 30`, `30–150`, `150–500`, `> 500` in meters) maps to natural Chinese and English expressions. Alternative: pass raw meters to the LLM and let it choose — rejected because LLMs are inconsistent at converting numeric distances to natural spatial language.

## Risks / Trade-offs

- **`_lastWasNoData` is session-scoped**: If a user walks to an interesting POI and back to an unknown one, the second unknown area visit will be silently suppressed. This is an acceptable trade-off — repeated apologies are more annoying than silent skips.

- **Jaccard threshold of 0.8 is heuristic**: May need tuning if POI turnover rate is higher than expected in dense urban areas. Start with 0.8; can be made configurable in settings later. → Mitigation: log `triggerSkip` events with Jaccard value to diagnose after deployment.

- **Audio subscription timing**: If `isPlayingStream` emits `false` before any audio is enqueued (fast "no data" path), the notifier goes idle immediately — which is correct behavior but depends on `AudioPlayerService` emitting `false` before audio starts. Current implementation does this. → Mitigation: ensure `reset()` in `AudioPlayerService` emits `false` synchronously.

- **Persona YAML rewrite is destructive**: Old persona text with self-labels is replaced entirely. No migration needed (YAMLs are not stored in DB), but the change requires careful QA to verify voice and tone are preserved.

## Migration Plan

All changes are backward-compatible and can be deployed independently:

1. **Backend deploy first**: Add `is_no_data`, `distance_m`, update persona YAMLs, update `PromptBuilder`
2. **Frontend deploy second**: Add `isNoData` parsing, `_lastWasNoData` dedup, audio-deferred idle, TriggerProvider dedup guard, `SizedBox.expand()` fix

Old frontend + new backend: `is_no_data` field ignored by old client (default `false` behavior). New frontend + old backend: `isNoData` defaults to `false` (JSON parsing has `?? false`), dedup never triggers — safe.

Rollback: Revert YAML files and backend model changes independently. No DB migrations involved.

## Open Questions

None — all design decisions resolved in the proposal and specs.
