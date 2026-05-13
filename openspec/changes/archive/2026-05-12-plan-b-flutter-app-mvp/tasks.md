## 1. Project Scaffold

- [ ] 1.1 Create flutter_app/ with pubspec.yaml (all dependencies), dart_defines/dev.json, and platform Google Maps API Key config
- [ ] 1.2 Set up app.dart (MaterialApp + go_router routes: / → HomeScreen, /map → MapScreen)
- [ ] 1.3 Set up shared/providers.dart (backendClientProvider, locationServiceProvider, localDbProvider, audioPlayerServiceProvider)

## 2. Shared Models

- [ ] 2.1 Create POI model (id, name, lat, lon, confidence, distanceM)
- [ ] 2.2 Create NarrationEvent sealed class (MetaEvent, TextEvent, AudioEvent, EndEvent, ErrorEvent)

## 3. SSE Parser (TDD)

- [ ] 3.1 Write failing unit tests for SseParser (meta/text/audio/end/error events + partial chunk boundary)
- [ ] 3.2 Implement SseParser.parse() to pass all tests
- [ ] 3.3 Commit

## 4. Haversine (TDD)

- [ ] 4.1 Write failing unit tests for haversine() (within radius, outside, same coords)
- [ ] 4.2 Implement haversine() pure function
- [ ] 4.3 Commit

## 5. BackendClient (Interface + Real + Fake)

- [ ] 5.1 Create BackendClient abstract class (fetchNearby, narrate)
- [ ] 5.2 Implement RealBackendClient (HTTP + SseParser)
- [ ] 5.3 Implement FakeBackendClient (scripted POIs + event sequence)
- [ ] 5.4 Commit

## 6. TriggerEngine (TDD)

- [ ] 6.1 Write failing unit tests for TriggerEngine.evaluate() (distance, cooldown skip, dedup, low accuracy)
- [ ] 6.2 Implement TriggerEngine.evaluate() pure static method
- [ ] 6.3 Commit

## 7. Drift DB Schema (TDD)

- [ ] 7.1 Create local_db.dart schema (Sessions + NarrationHistory tables, minimal LocalDb class)
- [ ] 7.2 Run build_runner to generate local_db.g.dart
- [ ] 7.3 Write failing unit tests for isCooldown() and recordNarration()
- [ ] 7.4 Run tests to confirm they fail
- [ ] 7.5 Add helper methods to LocalDb (startSession, endSession, recordNarration, isCooldown)
- [ ] 7.6 Re-run build_runner
- [ ] 7.7 Run tests to confirm pass
- [ ] 7.8 Commit

## 8. LocationService (Interface + Real + Fake)

- [ ] 8.1 Create LocationService abstract class + RealLocationService + FakeLocationService
- [ ] 8.2 Commit

## 9. AudioPlayerService (Interface + Real + Fake)

- [ ] 9.1 Create AudioPlayerService abstract class + RealAudioPlayerService (just_audio) + FakeAudioPlayerService
- [ ] 9.2 Commit

## 10. SessionProvider (TDD)

- [ ] 10.1 Write failing unit tests for SessionNotifier state transitions (idle→starting→active, permission denied, stop)
- [ ] 10.2 Implement SessionNotifier
- [ ] 10.3 Run tests to confirm pass
- [ ] 10.4 Commit

## 11. PoiProvider (TDD)

- [ ] 11.1 Write failing unit tests for PoiProvider (initial fetch, >250m refresh, 429 handling)
- [ ] 11.2 Implement PoiProvider (AsyncNotifier watching positionStream)
- [ ] 11.3 Run tests to confirm pass
- [ ] 11.4 Commit

## 12. NarrationProvider (TDD)

- [ ] 12.1 Write failing unit tests for NarrationProvider (meta/text/audio/end/error event handling, state transitions)
- [ ] 12.2 Implement NarrationProvider (narrate, pause, resume, skip, _handle)
- [ ] 12.3 Run tests to confirm pass
- [ ] 12.4 Commit

## 13. TriggerProvider (TDD)

- [ ] 13.1 Write failing unit tests for TriggerProvider (auto-trigger on position update, cooldown skip, dedup)
- [ ] 13.2 Implement TriggerProvider (watches positionStream + poiList, calls TriggerEngine)
- [ ] 13.3 Run tests to confirm pass
- [ ] 13.4 Commit

## 14. NarrationSheet + NarrationMiniBar (Widget)

- [ ] 14.1 Write failing widget tests for NarrationSheet (collapsed/expanded state, subtitle update, button states)
- [ ] 14.2 Implement NarrationSheet (DraggableScrollableSheet) + NarrationMiniBar
- [ ] 14.3 Run widget tests to confirm pass
- [ ] 14.4 Commit

## 15. MapScreen (Widget)

- [ ] 15.1 Write failing widget tests for MapScreen (POI markers rendered, AppBar content, end button)
- [ ] 15.2 Implement MapScreen (GoogleMap + POI markers + NarrationSheet overlay)
- [ ] 15.3 Run widget tests to confirm pass
- [ ] 15.4 Commit

## 16. HomeScreen (Widget)

- [ ] 16.1 Write failing widget tests for HomeScreen (Start Journey button, persona chip)
- [ ] 16.2 Implement HomeScreen + PersonaChip
- [ ] 16.3 Run widget tests to confirm pass
- [ ] 16.4 Commit

## 17. Integration Test: Narration Flow

- [ ] 17.1 Write integration test with FakeBackendClient scripted events (narrate → meta → text → audio → end → cooldown written)
- [ ] 17.2 Run integration test to confirm pass
- [ ] 17.3 Commit

## 18. main.dart + Wiring

- [ ] 18.1 Wire main.dart (ProviderScope + runApp + MaterialApp)
- [ ] 18.2 Run `flutter run --dart-define-from-file=dart_defines/dev.json` on iOS Simulator + Android Emulator smoke test
- [ ] 18.3 Commit

## 19. Final Verification

- [ ] 19.1 Run full test suite: `flutter test`
- [ ] 19.2 Run `flutter analyze` — zero warnings
- [ ] 19.3 Smoke test golden path: start session → walk toward POI → auto-trigger → hear narration
