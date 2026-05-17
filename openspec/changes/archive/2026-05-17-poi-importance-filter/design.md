## Context

The app currently narrates every nearby POI regardless of importance — trivial objects like map signs, bus stop markers, and information boards trigger full LLM narration and TTS synthesis. This wastes tokens, produces low-quality narration, and causes the countdown to re-trigger immediately after finishing, creating a loop of meaningless narration near dense infrastructure signage.

Current data flow:
1. `TriggerProvider` fires when POIs are loaded
2. `BackendClient.narrate()` sends candidates to `/narration`
3. `POISelectorService.select()` always returns a `poi_id`
4. Narration always plays; countdown restarts

There is no signal path for "all candidates are trivial, skip this cycle."

**Stack:** FastAPI (SSE streaming) on backend; Riverpod Notifier pattern on Flutter frontend; `shared_preferences` not yet in project.

## Goals / Non-Goals

**Goals:**
- Backend `POISelectorService.select()` returns `None` when LLM decides all candidates are trivial
- Backend streams a `skip` SSE event (with `min_displacement_m` payload) instead of narration
- Flutter `NarrationNotifier` sets `lastEventWasSkip = true` on receiving `SkipEvent`
- Flutter `TriggerNotifier` enters displacement-wait mode: pauses countdown, watches location, re-triggers once threshold is crossed
- `CountdownBadge` shows a grey walking-progress indicator during displacement-wait mode
- New `SettingsScreen` lets users adjust `countdownSeconds` (30–300 s) and `skipDisplacementM` (500–5000 m)
- Settings persist via `shared_preferences`

**Non-Goals:**
- Per-persona differentiated thresholds
- Google Places quality scoring
- SKIP after-toast notifications (badge visual is sufficient)
- Server-side configurable thresholds (client-controlled for now)

## Decisions

### Decision 1: `select()` returns `str | None` rather than a sentinel string

**Chosen:** Change return type to `Optional[str]`; caller uses `if selected_id is None:`.

**Alternative considered:** Return a special string like `"SKIP"` and check equality at the call site.

**Rationale:** `None` is idiomatic Python for "no result". It prevents accidental matching against a real POI id, is easier to type-check with mypy, and keeps the check at the endpoint level clean.

### Decision 2: Skip handled in `narration.py` endpoint, not in `NarrationService`

**Chosen:** The endpoint checks `selected_id is None` immediately after `poi_selector.select()` and returns a `StreamingResponse` with a single `skip` SSE event before `NarrationService` is invoked.

**Alternative considered:** Pass `None` into `NarrationService` and let it emit the skip event.

**Rationale:** `NarrationService` is responsible for text/audio narration, not control-flow signalling. Keeping the skip branch in the endpoint layer keeps each service cohesive and avoids adding a special case to `NarrationService`.

### Decision 3: Displacement origin is set on first position after skip, not at skip time

**Chosen:** `_startDisplacementWatch()` sets `originLat/originLon` from the first `positionStream` emission.

**Alternative considered:** Capture position at the moment `SkipEvent` is processed.

**Rationale:** There may be a short lag between skip event receipt and the next position update. Using the first stream position avoids a race condition where a slightly stale GPS coordinate is used as origin. Difference in practice is < 5 m and negligible relative to a 1500 m threshold.

### Decision 4: `appSettingsProvider` is a `Notifier<AppSettings>` (sync build, async load)

**Chosen:** `build()` returns `const AppSettings()` (defaults) synchronously, then calls `_load()` which is `async` and updates state from SharedPreferences.

**Alternative considered:** Use `AsyncNotifier<AppSettings>` with `AsyncValue`.

**Rationale:** The default values (90 s countdown, 1500 m threshold) are safe to use before SharedPreferences loads. Using `AsyncNotifier` would require all consumers to handle `AsyncValue.loading`, complicating `CountdownBadge` and `TriggerNotifier`. The sync-first pattern is simpler with acceptable UX.

### Decision 5: `lastEventWasSkip` flag on `NarrationState` (not a direct provider-to-provider call)

**Chosen:** `NarrationNotifier` sets `lastEventWasSkip = true`; `TriggerNotifier` uses `ref.listen<NarrationState>` to detect the transition.

**Alternative considered:** Have `BackendClient.narrate()` return `SkipEvent` via a separate stream or callback.

**Rationale:** Preserves the existing unidirectional `NarrationState → TriggerNotifier` listener pattern. Avoids new coupling between providers at the backend-client level.

## Risks / Trade-offs

- **LLM over-skipping**: The SKIP prompt criteria may be too aggressive, causing the app to skip interesting POIs. Mitigation: start with conservative criteria ("no Wikipedia AND name clearly indicates infrastructure") and monitor in production. The `POI_SELECTION_SKIP` log event enables monitoring.
- **Location subscription leak**: `_locationSub` must be cancelled when `isWaitingForDisplacement` becomes false via any path (manual skip, app background, dispose). Mitigation: `ref.onDispose` cancels `_locationSub`; `_clearDisplacementWatch()` is called on all exit paths.
- **SharedPreferences cold-start flash**: Default values are shown for ~50 ms before prefs load. Mitigation: defaults (90 s, 1500 m) are sensible, so no visible UX degradation. For SettingsScreen, values snap to correct state before the user can interact (navigation takes longer than prefs load).
- **Backward compat**: Existing callers of `poi_selector.select()` that don't handle `None` will crash. Mitigation: only one call site in `narration.py`; updated in this change. Type hints + mypy will catch any future regressions.

## Migration Plan

1. Deploy backend with updated `poi_selector.py` and `narration.py` — the skip branch is additive; existing narration path is unchanged.
2. Ship Flutter update with `SkipEvent` parser, `AppSettings`, updated `TriggerNotifier`, `CountdownBadge`, and `SettingsScreen`.
3. No database migration needed.
4. **Rollback**: Revert `poi_selector.py` to always return a non-None string — backend will never emit `skip` SSE events, Flutter code handles `SkipEvent` but never receives it (safe no-op).

## Open Questions

- Should the SKIP threshold criteria be configurable via the backend config file, allowing A/B testing? (Currently hard-coded in the prompt.) — Deferred to a future change.
- Is 1500 m the right default displacement threshold for dense urban environments vs. rural areas? — Start with 1500 m; adjust based on usage telemetry.
