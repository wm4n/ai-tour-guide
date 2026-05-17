# Narration UX Polish — Design Spec

**Date**: 2026-05-18
**Status**: Approved

## Overview

Six narration UX issues identified after the continuous audio pipeline was working:

1. Persona self-naming (e.g. "故事大哥哥" constantly refers to itself in third person)
2. Distance language — LLM says "請看看前面這個" even when POI is 100m away
3. Consecutive "I don't know this area" responses are played redundantly
4. Frontend sends identical POI batches to the backend even when user hasn't moved
5. Countdown timer starts when SSE stream ends, not when audio finishes playing
6. Circular progress bar overlaps the countdown text

---

## Issue 1 — Persona Self-Naming

### Root Cause

All persona YAMLs define `system_prompt` with explicit self-labeling (e.g. "你是「故事大哥哥」"). The `confidence_labels` and `no_data_context` fields also use third-person self-references.

### Design

Modify all 5 persona YAML files (`story_brother`, `history_uncle`, `kid_sister`, `gossip_auntie`, `foodie`):

- **`system_prompt`**: Remove the third-person role label. Replace with first-person framing: "你是一位 ... 的旅遊夥伴，請用「我/你」的口吻與對方交流，就像一起旅遊的朋友。"
- **`narration_template`**: Change "請用故事大哥哥的風格" → "請用你的風格"
- **`confidence_labels`**: Replace third-person self-references with first-person (e.g. "大哥哥知道的故事..." → "我所知道的...")
- **`no_data_context`**: Change to first-person (e.g. "這附近大哥哥也不太熟" → "我對這裡了解不多")

---

## Issue 2 — Distance Language in Prompt

### Root Cause

`POIContext` has no distance field. `PromptBuilder.build()` receives no distance information, so the LLM has no basis for choosing appropriate spatial language.

### Design

**Backend — `models/poi.py`**: Add `distance_m: float = 0.0` to `POIContext`.

**Backend — `api/narration.py`**: Pass `selected.distance_m` when constructing `poi_context`.

**Backend — `prompts/builder.py`**: Add `distance_m: float` parameter to `PromptBuilder.build()`. Derive a `distance_hint` string using these bins:

| distance_m | hint |
|---|---|
| < 30 | `"就在你附近"` |
| 30–150 | `"前方不遠處"` |
| 150–500 | `"這附近"` |
| > 500 | `"這一帶"` |

**Backend — `services/narration_service.py`**: Forward `poi.distance_m` to `PromptBuilder.build()`.

**All persona `narration_template` (zh-TW)**:

Add a `{distance_hint}` variable and a rule in the template:

```
景點距離提示：{distance_hint}
開頭規則：...，並根據距離提示選擇合適的空間語言。若距離 > 50m，禁止使用「眼前」、「正前方」等近距離詞彙；請改用「這附近」、「前方不遠處」等自然表達。
```

---

## Issue 3 — Consecutive No-Data Responses

### Root Cause

Frontend cannot distinguish a no-data short-circuit response from a real narration. It plays the "I don't know this area" audio every time a wiki-less POI is selected.

### Design

**Backend — `services/narration_service.py`**: In the `poi.wiki is None` short-circuit path, yield `MetaEvent(is_no_data=True, ...)`.

**Backend — `models` / `services/narration_service.py`**: Add `is_no_data: bool = False` to `MetaEvent`.

**Frontend — `models/narration_event.dart`**: Add `isNoData: bool` to `MetaEvent`, parse from JSON.

**Frontend — `narration_provider.dart`**: Add `bool _lastWasNoData = false`. In `_handle(MetaEvent)`:
- If `event.isNoData && _lastWasNoData`: cancel SSE subscription, set `_lastWasNoData = true`, transition directly to `idle` (no audio played, no DB record)
- Otherwise: update `_lastWasNoData = event.isNoData` and continue normally

`_lastWasNoData` is NOT reset when `narrate()` starts — it persists across narrations within a session so consecutive no-data responses are all suppressed after the first.

---

## Issue 4 — Redundant Frontend LLM Requests

### Root Cause

`TriggerProvider._doCandidatesRequest()` fires unconditionally on countdown expiry, even when the user hasn't moved and the same POIs are visible.

### Design

Add two guard checks in `TriggerProvider._doCandidatesRequest()` before calling `narrate()`:

**State to track** (new fields on `TriggerNotifier`):
- `Position? _lastTriggerPosition` — GPS position at last successful `narrate()` call
- `Set<String> _lastCandidateIds` — POI IDs sent in the last `narrate()` call

**Guard logic** (both conditions must be true to skip):
1. **Didn't move**: `_lastTriggerPosition` is non-null AND current position is within 30m of it
2. **Content similar**: `_lastCandidateIds` is non-empty AND Jaccard similarity of current available POI IDs vs `_lastCandidateIds` ≥ 0.8

If both are true → log `triggerSkip` with `reason: 'poi_unchanged'` and return without calling `narrate()`.

First-ever trigger (both fields null/empty) always proceeds.

Update `_lastTriggerPosition` and `_lastCandidateIds` each time `narrate()` is actually called.

The current GPS position is read from `ref.read(locationServiceProvider).positionStream` last value, or obtained via a one-shot read at check time.

---

## Issue 5 — Countdown Starts Too Early

### Root Cause

`NarrationState` transitions to `idle` when the SSE `EndEvent` arrives (LLM stream done). But audio chunks are still playing in `AudioPlayerService`. `TriggerProvider` sees `playing → idle` and starts the countdown while audio is still playing.

### Design

Decouple "SSE stream done" from "narration truly complete" in `NarrationNotifier`:

1. Add `bool _sseStreamEnded = false` and `StreamSubscription? _audioSub` to `NarrationNotifier`.
2. In `_handle(EndEvent)`: set `_sseStreamEnded = true`, subscribe to `_audio.isPlayingStream` via `_audioSub`.
3. When `isPlayingStream` emits `false` **and** `_sseStreamEnded == true`: cancel `_audioSub`, transition state to `idle`.
4. Edge case — audio already done when EndEvent arrives (very fast): `isPlayingStream` emits `false` immediately.
5. Reset `_sseStreamEnded = false` and cancel any existing `_audioSub` at the start of each `narrate()` call.

`TriggerProvider` requires no changes — it already reacts to the `playing → idle` transition.

---

## Issue 6 — Progress Bar Overlaps Text

### Root Cause

`CircularProgressIndicator` inside a `Stack` has no explicit size constraint. Flutter falls back to a default intrinsic size (~48×48), which overlaps the centered text column inside the 72×72 container.

### Design

In `countdown_badge.dart`, wrap `CircularProgressIndicator` in `SizedBox.expand()` in both `CountdownBadge` and `_DisplacementBadge`:

```dart
Stack(
  alignment: Alignment.center,
  children: [
    SizedBox.expand(
      child: CircularProgressIndicator(
        value: progress.clamp(0.0, 1.0),
        strokeWidth: 3,
        color: Colors.white,
        backgroundColor: Colors.white24,
      ),
    ),
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [...],
    ),
  ],
)
```

`SizedBox.expand()` forces the indicator to fill the full 72×72 container. With `strokeWidth: 3`, the ring sits at the outer edge and the center is clear for text.

---

## Affected Files Summary

| File | Change |
|---|---|
| `backend/prompts/personas/*.yaml` (5 files) | Remove third-person self-labels, add `{distance_hint}` to templates |
| `backend/src/tour_guide/models/poi.py` | Add `distance_m` to `POIContext` |
| `backend/src/tour_guide/prompts/builder.py` | Accept `distance_m`, derive `distance_hint`, pass to template |
| `backend/src/tour_guide/services/narration_service.py` | Forward `distance_m`; set `is_no_data=True` on MetaEvent |
| `backend/src/tour_guide/api/narration.py` | Pass `distance_m` into `POIContext` |
| `flutter_app/lib/shared/backend/models/narration_event.dart` | Add `isNoData` to `MetaEvent` |
| `flutter_app/lib/features/narration/providers/narration_provider.dart` | Track `_lastWasNoData`, defer idle until audio done |
| `flutter_app/lib/features/narration/providers/trigger_provider.dart` | Add position + POI ID dedup guards |
| `flutter_app/lib/features/narration/widgets/countdown_badge.dart` | Fix progress bar with `SizedBox.expand()` |
