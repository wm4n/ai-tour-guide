## 1. Backend — poi_selector SKIP support

- [x] 1.1 Add `POI_SELECTION_SKIP` log event to `backend/src/tour_guide/log_events.py`
- [x] 1.2 Write failing tests for SKIP behaviour in `backend/tests/unit/test_poi_selector.py`
- [x] 1.3 Run tests to verify they fail (LLM returns "SKIP" → None not yet implemented)
- [x] 1.4 Update `poi_selector.py` `select()` return type to `str | None` with SKIP prompt rule and None handling
- [x] 1.5 Run all poi_selector tests and verify all pass

## 2. Backend — narration endpoint handles SKIP

- [x] 2.1 Create `backend/tests/unit/test_narration_skip.py` with failing test for skip SSE response
- [x] 2.2 Run test to verify it fails (endpoint crashes when `select()` returns None)
- [x] 2.3 Update `narration.py` to handle `selected_id is None`: stream `skip` SSE event and return immediately
- [x] 2.4 Run skip test and verify it passes
- [x] 2.5 Run full backend unit test suite and verify all pass

## 3. Flutter — SkipEvent model + SSE parsing

- [x] 3.1 Add `SkipEvent` class to `flutter_app/lib/shared/backend/models/narration_event.dart`
- [x] 3.2 Update `_toNarrationEvent` switch in `backend_client.dart` to handle `'skip'` event type
- [x] 3.3 Verify `flutter analyze lib/shared/backend/` reports no errors

## 4. Flutter — AppSettings + shared_preferences

- [x] 4.1 Add `shared_preferences: ^2.3.2` dependency to `flutter_app/pubspec.yaml` and run `flutter pub get`
- [x] 4.2 Create `flutter_app/lib/shared/settings/app_settings.dart` with `skipDisplacementM` and `countdownSeconds` fields
- [x] 4.3 Write failing tests in `flutter_app/test/unit/settings_provider_test.dart` (defaults, persist, load)
- [x] 4.4 Run settings tests to verify they fail (settings_provider.dart does not exist yet)
- [x] 4.5 Create `flutter_app/lib/shared/settings/settings_provider.dart` with `AppSettingsNotifier` and `appSettingsProvider`
- [x] 4.6 Run settings tests and verify all 4 pass

## 5. Flutter — NarrationState skip flag

- [x] 5.1 Add `lastEventWasSkip` field to `NarrationState` class with `copyWith` support
- [x] 5.2 Handle `SkipEvent` in `NarrationNotifier._handle()`: set `lastEventWasSkip = true`, status stays `idle`
- [x] 5.3 Verify `flutter analyze lib/features/narration/providers/narration_provider.dart` reports no errors
- [x] 5.4 Run existing trigger_provider_test.dart and verify existing tests still pass

## 6. Flutter — TriggerProvider displacement watch

- [x] 6.1 Write failing tests for displacement behaviour in `trigger_provider_test.dart` (skip sets isWaitingForDisplacement, threshold re-triggers)
- [x] 6.2 Run tests to verify they fail (appSettingsProvider, isWaitingForDisplacement not defined)
- [x] 6.3 Rewrite `trigger_provider.dart`: add displacement fields to `TriggerState`, add `_handleSkip()` and `_startDisplacementWatch()` to `TriggerNotifier`, use dynamic `countdownSeconds` from settings
- [x] 6.4 Run all trigger provider tests and verify all 5 pass

## 7. Flutter — CountdownBadge displacement UI

- [x] 7.1 Update `countdown_badge.dart` to show grey walking-icon badge with `x.x/y.y km` progress when `isWaitingForDisplacement` is true
- [x] 7.2 Update countdown badge to read `countdownSeconds` dynamically from `appSettingsProvider` for progress calculation
- [x] 7.3 Verify `flutter analyze lib/features/narration/widgets/countdown_badge.dart` reports no errors

## 8. Flutter — SettingsScreen + MapScreen navigation

- [x] 8.1 Create `flutter_app/lib/features/settings/settings_screen.dart` with sliders for countdown (30–300 s) and displacement (500–5000 m)
- [x] 8.2 Add settings icon button to `MapScreen` AppBar that navigates to `SettingsScreen`
- [x] 8.3 Run full Flutter test suite and verify all tests pass
- [x] 8.4 Run `flutter analyze` on the full project and verify no errors

## 9. Final verification

- [x] 9.1 Run backend full unit test suite: `python -m pytest tests/unit/ -v --ignore=tests/unit/test_config.py`
- [x] 9.2 Run Flutter full test suite: `flutter test`
- [ ] 9.3 Manual smoke test: walk near a trivial POI → badge turns grey with walking icon
- [ ] 9.4 Manual smoke test: walk 1.5 km → narration re-triggers
- [ ] 9.5 Manual smoke test: open Settings → adjust displacement → verify badge threshold changes
- [ ] 9.6 Manual smoke test: open Settings → adjust countdown to 30 s → verify countdown uses new value
