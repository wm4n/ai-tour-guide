## 1. CountdownBadge Progress Ring Fix (Issue 6)

- [x] 1.1 Write failing widget test for `SizedBox.expand()` wrapping `CircularProgressIndicator` in `CountdownBadge`
- [x] 1.2 Run test to verify it fails (no `SizedBox` ancestor found)
- [x] 1.3 Wrap `CircularProgressIndicator` in `SizedBox.expand()` inside `CountdownBadge.build()` Stack
- [x] 1.4 Wrap `CircularProgressIndicator` in `SizedBox.expand()` inside `_DisplacementBadge.build()` Stack
- [x] 1.5 Run widget test to verify it passes

## 2. Persona YAML Rewrite — Remove Self-Naming (Issue 1)

- [x] 2.1 Update `test_prompt_builder.py` assertion to not depend on third-person role label in `system_prompt`
- [x] 2.2 Run existing prompt builder tests to confirm baseline passes
- [x] 2.3 Rewrite `backend/prompts/personas/story_brother.yaml` — first-person `system_prompt`, add `{distance_hint}` to `narration_template`, first-person `confidence_labels` and `no_data_context`
- [x] 2.4 Rewrite `backend/prompts/personas/history_uncle.yaml` — same changes as above
- [x] 2.5 Rewrite `backend/prompts/personas/kid_sister.yaml` — same changes as above
- [x] 2.6 Rewrite `backend/prompts/personas/gossip_auntie.yaml` — same changes as above
- [x] 2.7 Rewrite `backend/prompts/personas/foodie.yaml` — same changes as above
- [x] 2.8 Run persona loader + prompt builder tests to verify they still pass (KeyError on `{distance_hint}` expected until Task 3 is complete — note in test output)

## 3. Backend — distance_m in POIContext and PromptBuilder (Issue 2)

- [x] 3.1 Write failing unit tests for `distance_hint` binning in `test_prompt_builder.py` (4 distance ranges × zh-TW)
- [x] 3.2 Run tests to verify they fail with `KeyError: 'distance_hint'`
- [x] 3.3 Add `distance_m: float = 0.0` field to `POIContext` in `backend/src/tour_guide/models/poi.py`
- [x] 3.4 Add `DISTANCE_HINTS` class variable and `_distance_hint()` static method to `PromptBuilder`
- [x] 3.5 Update `PromptBuilder.build()` to compute `distance_hint` and pass it to `narration_template.format()`
- [x] 3.6 Update `backend/src/tour_guide/api/narration.py` to pass `distance_m=selected.distance_m` when constructing `POIContext`
- [x] 3.7 Run all prompt builder tests to verify they pass
- [x] 3.8 Run full backend unit test suite to verify nothing is broken

## 4. Backend — is_no_data Flag on MetaEvent (Issue 3)

- [x] 4.1 Write failing unit test: `test_no_data_meta_event_has_is_no_data_true` in `test_narration_service.py`
- [x] 4.2 Write failing unit test: `test_normal_meta_event_has_is_no_data_false` in `test_narration_service.py`
- [x] 4.3 Run tests to verify they fail with `AttributeError: 'MetaEvent' object has no attribute 'is_no_data'`
- [x] 4.4 Add `is_no_data: bool = False` field to `MetaEvent` dataclass in `narration_service.py`
- [x] 4.5 Update `NarrationService.narrate()` to set `is_no_data = poi.wiki is None` and pass it to `MetaEvent()`
- [x] 4.6 Run narration service tests to verify all pass

## 5. Frontend — MetaEvent isNoData + Consecutive No-Data Dedup (Issue 3)

- [x] 5.1 Add `isNoData: bool` field to `MetaEvent` in `flutter_app/lib/shared/backend/models/narration_event.dart`, parse from `is_no_data` JSON key with `?? false` default
- [x] 5.2 Write failing unit test for no-data dedup in `narration_provider_test.dart` (second consecutive no-data → `NarrationStatus.idle` without audio)
- [x] 5.3 Run test to verify it fails (second narration still plays)
- [x] 5.4 Add `bool _lastWasNoData = false` field to `NarrationNotifier`
- [x] 5.5 Update `_handle(MetaEvent)` to check `isNoData && _lastWasNoData` — if true, cancel `_sub`, set state to `idle`, return early; otherwise update `_lastWasNoData = isNoData` and continue
- [x] 5.6 Run narration provider tests to verify dedup test passes
- [x] 5.7 Run full Flutter unit test suite to verify no regressions

## 6. Frontend — Audio-Deferred Idle Transition (Issue 5)

- [x] 6.1 Write failing unit test: `NarrationStatus stays playing after EndEvent until audio stops` in `narration_provider_test.dart`
- [x] 6.2 Run test to verify it fails (status transitions to `idle` immediately after `EndEvent`)
- [x] 6.3 Add `StreamSubscription<bool>? _audioSub` and `bool _sseStreamEnded = false` fields to `NarrationNotifier`
- [x] 6.4 In `narrate()`, reset `_sseStreamEnded = false` and cancel `_audioSub` at the start of each call
- [x] 6.5 Replace the `EndEvent` case in `_handle()`: set `_sseStreamEnded = true`, subscribe to `_audio.isPlayingStream` via `_audioSub`; transition to `idle` only when `isPlaying == false && _sseStreamEnded`
- [x] 6.6 Cancel `_audioSub` and reset `_sseStreamEnded` in `skip()` method
- [x] 6.7 Cancel `_audioSub` in `dispose()` method
- [x] 6.8 Also cancel `_audioSub` in the no-data dedup early-return path (from Task 5)
- [x] 6.9 Run audio-deferred idle test to verify it passes
- [x] 6.10 Run full Flutter unit test suite to verify no regressions

## 7. Frontend — TriggerProvider POI Dedup Guard (Issue 4)

- [ ] 7.1 Write failing unit test: trigger skips `narrate()` when user hasn't moved and POIs are unchanged (second countdown fires but `callCount` stays at 1)
- [ ] 7.2 Run test to verify it fails (`callCount` is 2)
- [ ] 7.3 Add `Position? _currentPosition`, `Position? _lastTriggerPosition`, `Set<String> _lastCandidateIds = {}`, and `StreamSubscription<Position>? _positionTrackSub` fields to `TriggerNotifier`
- [ ] 7.4 In `build()`, subscribe to `locationServiceProvider.positionStream` to continuously update `_currentPosition`; cancel `_positionTrackSub` in `ref.onDispose()`
- [ ] 7.5 In `_doCandidatesRequest()`, add dedup guard before `narrate()` call: skip if `_lastTriggerPosition != null && moved < 30m && Jaccard >= 0.8`; log `triggerSkip` with `reason: "poi_unchanged"`
- [ ] 7.6 After dedup guard passes, update `_lastTriggerPosition = _currentPosition` and `_lastCandidateIds = available.map((p) => p.id).toSet()`
- [ ] 7.7 Run all trigger provider tests to verify they pass
- [ ] 7.8 Run full Flutter test suite to verify no regressions
