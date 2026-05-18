## 1. Backend: MetaEvent + log event

- [x] 1.1 Add `poi_name: str = ""` field to `MetaEvent` dataclass in `narration_service.py`
- [x] 1.2 Extract `poi_name = poi.osm.tags.get("name", poi.osm.id)` at start of `narrate()` and pass to both cache-hit and cache-miss `MetaEvent(...)` yield calls
- [x] 1.3 Add `POI_SELECTION = "POI_SELECTION"` constant to `log_events.py`
- [x] 1.4 Run `pytest tests/unit/test_narration_service.py -v` and verify all existing tests pass

## 2. Backend: New request models

- [x] 2.1 Add `POICandidate` Pydantic model to `narration.py` (fields: `poi_id`, `poi_name`, `poi_lat`, `poi_lon`, `distance_m`, `poi_tags`, `wiki_title`, `wiki_extract`)
- [x] 2.2 Add `PreviousSelection` Pydantic model to `narration.py` (fields: `poi_id`, `poi_name`, `script`)
- [x] 2.3 Replace single-POI `NarrationRequest` with multi-candidate version: `candidates: list[POICandidate]`, `previous_selection: PreviousSelection | None = None`
- [x] 2.4 Verify import: `python -c "from tour_guide.api.narration import NarrationRequest, POICandidate, PreviousSelection; print('OK')"`

## 3. Backend: POISelectorService (TDD)

- [x] 3.1 Create `backend/tests/unit/test_poi_selector.py` with 3 tests: valid selection, fallback on invalid response, previous_selection in prompt
- [x] 3.2 Run tests to confirm they fail with `ModuleNotFoundError`
- [x] 3.3 Create `backend/src/tour_guide/services/poi_selector.py` implementing `POISelectorService` with `select(candidates, persona, lang, previous=None) -> str`
- [x] 3.4 Run `pytest tests/unit/test_poi_selector.py -v` and verify all 3 tests pass

## 4. Backend: Wire POISelectorService into endpoint

- [x] 4.1 Add `get_poi_selector_service()` dependency getter stub to `narration.py`
- [x] 4.2 Import `POISelectorService` and update `narrate()` endpoint: call selector first, then build `POIContext` from selected candidate, then stream narration
- [x] 4.3 Add HTTP 400 guard for empty candidates list
- [x] 4.4 Instantiate `POISelectorService(llm=llm_provider)` in `main.py` and add `dependency_overrides` entry
- [x] 4.5 Verify app starts: `python -c "from tour_guide.main import create_app; from tour_guide.config import AppConfig; print('OK')"`
- [x] 4.6 Run full backend unit test suite: `pytest tests/unit/ -v`

## 5. Flutter: MetaEvent model update

- [x] 5.1 Add `poiName: String` field (default `''`) to `MetaEvent` class in `narration_event.dart`
- [x] 5.2 Add `poiName: json['poi_name'] as String? ?? ''` to `MetaEvent.fromJson()`
- [x] 5.3 Run `flutter test test/unit/models_test.dart -v` (or equivalent) and verify no breakage

## 6. Flutter: BackendClient candidates API

- [x] 6.1 Add `PreviousSelection` class to `backend_client.dart` (fields: `poiId`, `poiName`, `script`)
- [x] 6.2 Update `BackendClient` abstract `narrate()` signature: `List<POI> candidates`, `PreviousSelection? previousSelection`
- [x] 6.3 Implement `RealBackendClient.narrate()` to serialize candidates array and optional `previous_selection` into request body
- [x] 6.4 Update `FakeBackendClient.narrate()` to match new signature
- [x] 6.5 Run `flutter analyze lib/shared/backend/backend_client.dart` and verify no errors

## 7. Flutter: NarrationNotifier — candidates input + scriptBuffer

- [x] 7.1 Add `scriptBuffer: String` field to `NarrationState` (default `''`) with `copyWith` support
- [x] 7.2 Update `NarrationNotifier.narrate()` to accept `List<POI> candidates` and `PreviousSelection? previousSelection`; store `_candidates` for MetaEvent resolution
- [x] 7.3 In `_handle(MetaEvent)`: match `poiId` against `_candidates` using `firstWhere(orElse: candidates.first)` to set `currentPoi`
- [x] 7.4 In `_handle(TextEvent)`: append chunk to `state.scriptBuffer` in `copyWith`
- [x] 7.5 Reset `scriptBuffer: ''` at start of each new `narrate()` call
- [x] 7.6 Run `flutter analyze lib/features/narration/providers/narration_provider.dart` and verify no errors

## 8. Flutter: TriggerNotifier countdown replacement (TDD)

- [x] 8.1 Write updated `test/unit/trigger_provider_test.dart` with 3 tests: initial non-counting state, first-run auto-trigger fires narration, skipCountdown() resets state
- [x] 8.2 Run tests to verify they fail (missing `TriggerState`, `skipCountdown`)
- [x] 8.3 Add `TriggerState` class with `isCountingDown` and `countdownRemaining` fields
- [x] 8.4 Replace `TriggerNotifier` body: remove `TriggerEngine` dependency, add `_cooldownTimer`, `_cooldownUntil`, `_lastSelectedPoiId`, `_lastSelectedPoiName`, `_lastScript`, `_hasEverFired`, `_sessionPlayedIds`
- [x] 8.5 Implement `_startCountdown()` with `Timer.periodic(1s)`: tick updates `countdownRemaining`, expiry calls `_doCandidatesRequest()`
- [x] 8.6 Implement `skipCountdown()`: cancel timer, reset state, call `_doCandidatesRequest()`
- [x] 8.7 Implement `_doCandidatesRequest()`: filter by session + 24h cooldown, build `PreviousSelection` if `_lastSelectedPoiId` set, call `narrationProvider.notifier.narrate()`
- [x] 8.8 Listen to `narrationProvider`: on `playing→idle` transition, capture `currentPoi` id/name and `scriptBuffer` into `_last*` fields, then call `_startCountdown()`; on `loading/playing→error`, call `_startCountdown()`
- [x] 8.9 Listen to `poiProvider`: update `_latestPois`; on first non-empty load with `!_hasEverFired`, call `_doCandidatesRequest()` immediately
- [x] 8.10 Run `flutter test test/unit/trigger_provider_test.dart -v` and verify all tests pass
- [x] 8.11 Run `flutter analyze lib/features/narration/providers/trigger_provider.dart`

## 9. Flutter: CountdownBadge widget

- [x] 9.1 Create `flutter_app/lib/features/narration/widgets/countdown_badge.dart` as `ConsumerWidget`
- [x] 9.2 Implement badge: returns `SizedBox.shrink()` when `!isCountingDown`; shows 72×72 circular badge with `CircularProgressIndicator`, remaining seconds, and "下一個" label
- [x] 9.3 Wire `GestureDetector.onTap` to call `ref.read(triggerProvider.notifier).skipCountdown()`
- [x] 9.4 Run `flutter analyze lib/features/narration/widgets/countdown_badge.dart`

## 10. Flutter: MapScreen integration + final verification

- [x] 10.1 Add import for `CountdownBadge` in `map_screen.dart`
- [x] 10.2 Add `Positioned(bottom: 110, right: 16, child: CountdownBadge())` to the map `Stack` children
- [x] 10.3 Verify `ref.read(triggerProvider)` in `initState` still compiles (reads TriggerState, initializing notifier as side effect)
- [x] 10.4 Run `flutter analyze` across all changed Flutter files
- [x] 10.5 Run full Flutter unit test suite: `flutter test test/unit/ -v`
- [x] 10.6 Run full backend unit test suite: `pytest tests/unit/ -v`
- [ ] 10.7 Manual smoke test: launch app, confirm countdown badge appears after narration ends, confirm tap triggers next narration, confirm 90s auto-trigger fires
