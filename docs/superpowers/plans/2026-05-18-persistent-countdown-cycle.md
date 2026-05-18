# Persistent Countdown Cycle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The countdown badge always restarts after any non-narration outcome so the trigger engine never stalls.

**Architecture:** Three changes to `trigger_provider.dart`: (1) strip displacement-wait state and replace SkipEvent handling with `_startCountdown()`, (2) remove the position reset inside `_startCountdown()` so dedup tracking persists across cycles, (3) add `_startCountdown()` to the two early-return points in `_doCandidatesRequest()` that previously left the engine idle. Remove `_DisplacementBadge` from the UI widget.

**Tech Stack:** Flutter, Riverpod (`Notifier`), `dart:async` Timer, `flutter_test`

---

## File Map

| File | Change |
|---|---|
| `flutter_app/lib/features/narration/providers/trigger_provider.dart` | Main logic — remove displacement state/methods, fix `_startCountdown`, fix `_doCandidatesRequest` |
| `flutter_app/lib/features/narration/widgets/countdown_badge.dart` | Remove `_DisplacementBadge` widget |
| `flutter_app/test/unit/trigger_provider_test.dart` | Update SkipEvent test, add 2 new tests |

---

## Task 1: Remove displacement-wait state and fix SkipEvent handling

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: Update the SkipEvent test to expect countdown restart**

In `flutter_app/test/unit/trigger_provider_test.dart`, replace the test named `'SkipEvent sets isWaitingForDisplacement and clears countdown'` with:

```dart
test('SkipEvent restarts countdown instead of displacement-wait', () async {
  final fakeLocation = FakeLocationService();
  final fakeAudio = FakeAudioPlayerService();
  final db = LocalDb.forTesting(NativeDatabase.memory());

  final container = ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      backendClientProvider.overrideWithValue(
        FakeBackendClient(
          nearbyPois: const [_poi],
          scriptedEvents: const [SkipEvent()],
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appSettingsProvider.overrideWith(
        () => _FakeSettingsNotifier(
          const AppSettings(skipDisplacementM: 500, countdownSeconds: 90),
        ),
      ),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);

  container.listen(triggerProvider, (_, __) {});
  container.listen(narrationProvider, (_, __) {});

  fakeLocation.emit(fakePosition(25.1023, 121.5482));
  await Future<void>.delayed(const Duration(milliseconds: 200));

  final state = container.read(triggerProvider);
  expect(state.isCountingDown, isTrue);
  // isWaitingForDisplacement field has been removed from TriggerState
});
```

- [ ] **Step 2: Run test to confirm it fails**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart --reporter=compact
```

Expected: the renamed test fails because `isWaitingForDisplacement` doesn't exist (or is still true).

- [ ] **Step 3: Rewrite `TriggerState` — remove displacement fields**

Replace the entire `TriggerState` class in `trigger_provider.dart` with:

```dart
class TriggerState {
  final bool isCountingDown;
  final Duration countdownRemaining;

  const TriggerState({
    this.isCountingDown = false,
    this.countdownRemaining = Duration.zero,
  });

  TriggerState copyWith({
    bool? isCountingDown,
    Duration? countdownRemaining,
  }) =>
      TriggerState(
        isCountingDown: isCountingDown ?? this.isCountingDown,
        countdownRemaining: countdownRemaining ?? this.countdownRemaining,
      );
}
```

- [ ] **Step 4: Remove displacement fields and methods from `TriggerNotifier`**

In `TriggerNotifier`, remove:
- Field: `StreamSubscription<Position>? _locationSub;`
- Remove `_locationSub?.cancel();` from `onDispose()`
- Remove method `_handleSkip()`
- Remove method `_startDisplacementWatch()`
- Remove method `_clearDisplacementWatch()`

Also remove the `haversine` import if it is no longer used by `_startDisplacementWatch` — keep it if still used in `_doCandidatesRequest` (it is, for the dedup guard).

- [ ] **Step 5: Replace SkipEvent handler in `build()` listener**

In the `narrationProvider` listener inside `build()`, replace:

```dart
// Handle skip: switch to displacement-wait mode
if (next.lastEventWasSkip && !(prev?.lastEventWasSkip ?? false)) {
  _handleSkip();
}
```

with:

```dart
// LLM decided all candidates trivial — restart countdown
// Position was already saved in _doCandidatesRequest before the narrate call
if (next.lastEventWasSkip && !(prev?.lastEventWasSkip ?? false)) {
  AppLogger.info(LogEvents.triggerSkip, {'reason': 'poi_trivial_restart_countdown'});
  _startCountdown();
}
```

- [ ] **Step 6: Remove position reset from `_startCountdown()`**

In `_startCountdown()`, delete these two lines (added in a previous fix that is now superseded):

```dart
// Reset dedup state so countdown expiry is never blocked by the guard
_lastTriggerPosition = null;
_lastCandidateIds = {};
```

The method should start with:

```dart
void _startCountdown() {
  _cooldownTimer?.cancel();
  // Position tracking NOT reset — dedup persists across cycles
  final seconds = ref.read(appSettingsProvider).countdownSeconds;
```

Also remove `_locationSub?.cancel(); _locationSub = null;` from `_startCountdown()` since `_locationSub` is being removed entirely.

- [ ] **Step 7: Run tests — all should pass**

```bash
flutter test test/unit/trigger_provider_test.dart --reporter=compact
```

Expected: all tests pass (including the renamed SkipEvent test and all existing tests).

- [ ] **Step 8: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "refactor(flutter): replace displacement-wait with countdown restart on SkipEvent"
```

---

## Task 2: Restart countdown when `_doCandidatesRequest()` returns early

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: Add test for `available.isEmpty` restarting countdown**

Append to `main()` in `trigger_provider_test.dart`:

```dart
test('countdown restarts when all nearby POIs have been played', () async {
  // One POI, it plays once, then available.isEmpty → countdown should restart
  final fakeLocation = FakeLocationService();
  final fakeAudio = FakeAudioPlayerService();
  final db = LocalDb.forTesting(NativeDatabase.memory());

  final container = ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      backendClientProvider.overrideWithValue(
        FakeBackendClient(
          nearbyPois: const [_poi],
          scriptedEvents: const [
            MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'high'),
            EndEvent(),
          ],
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appSettingsProvider.overrideWith(
        () => _FakeSettingsNotifier(
          const AppSettings(skipDisplacementM: 500, countdownSeconds: 1),
        ),
      ),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);

  container.listen(triggerProvider, (_, __) {});
  container.listen(narrationProvider, (_, __) {});

  // Trigger first (and only) narration
  fakeLocation.emit(fakePosition(25.1023, 121.5482));
  await Future<void>.delayed(const Duration(milliseconds: 200));

  // After narration completes, 1-second countdown starts, then expires
  // available.isEmpty → countdown should restart
  await Future<void>.delayed(const Duration(seconds: 2));

  final state = container.read(triggerProvider);
  expect(state.isCountingDown, isTrue,
      reason: 'countdown should restart when available.isEmpty');
});
```

- [ ] **Step 2: Add test for dedup guard restarting countdown**

Append to `main()` in `trigger_provider_test.dart`. Needs 5 POIs so jaccard = 4/5 = 0.8 ≥ threshold:

```dart
test('countdown restarts when dedup guard blocks (stationary, similar POIs)', () async {
  // 5 POIs: after first narration plays poi1, 4 remain
  // jaccard(4,5) = 4/5 = 0.8 >= 0.8, moved = 0 → dedup blocks → countdown restarts
  const pois = [
    POI(id: 'osm:node:1', name: 'POI 1', lat: 25.10, lon: 121.54, tags: {}, distanceM: 50, confidence: 'high'),
    POI(id: 'osm:node:2', name: 'POI 2', lat: 25.10, lon: 121.54, tags: {}, distanceM: 60, confidence: 'high'),
    POI(id: 'osm:node:3', name: 'POI 3', lat: 25.10, lon: 121.54, tags: {}, distanceM: 70, confidence: 'high'),
    POI(id: 'osm:node:4', name: 'POI 4', lat: 25.10, lon: 121.54, tags: {}, distanceM: 80, confidence: 'high'),
    POI(id: 'osm:node:5', name: 'POI 5', lat: 25.10, lon: 121.54, tags: {}, distanceM: 90, confidence: 'high'),
  ];
  const firstNarrationEvents = [
    MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'high'),
    EndEvent(),
  ];

  final fakeLocation = FakeLocationService();
  final fakeAudio = FakeAudioPlayerService();
  final db = LocalDb.forTesting(NativeDatabase.memory());
  final trackingClient = _CountingBackendClient(
    nearbyPois: pois,
    firstEvents: firstNarrationEvents,
    subsequentEvents: firstNarrationEvents, // Won't be reached if dedup works
  );

  final container = ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      backendClientProvider.overrideWithValue(trackingClient),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appSettingsProvider.overrideWith(
        () => _FakeSettingsNotifier(
          const AppSettings(skipDisplacementM: 500, countdownSeconds: 1),
        ),
      ),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);

  container.listen(triggerProvider, (_, __) {});
  container.listen(narrationProvider, (_, __) {});

  // First narration fires at initial position
  fakeLocation.emit(fakePosition(25.10, 121.54));
  await Future<void>.delayed(const Duration(milliseconds: 200));
  expect(trackingClient.callCount, 1);

  // 1-second countdown expires; user hasn't moved; jaccard(4/5)=0.8 → dedup blocks
  await Future<void>.delayed(const Duration(seconds: 2));

  expect(trackingClient.callCount, 1, reason: 'dedup should prevent second narration');
  final state = container.read(triggerProvider);
  expect(state.isCountingDown, isTrue,
      reason: 'countdown should restart after dedup guard blocks');
});
```

- [ ] **Step 3: Run tests to confirm they fail**

```bash
flutter test test/unit/trigger_provider_test.dart --reporter=compact
```

Expected: the two new tests fail with `isCountingDown` being `false`.

- [ ] **Step 4: Add `_startCountdown()` to the `available.isEmpty` early return**

In `_doCandidatesRequest()`, replace:

```dart
if (available.isEmpty) {
  AppLogger.info(LogEvents.triggerSkip, {'reason': 'no_candidates_available'});
  return;
}
```

with:

```dart
if (available.isEmpty) {
  AppLogger.info(LogEvents.triggerSkip, {'reason': 'no_candidates_available'});
  _startCountdown();
  return;
}
```

- [ ] **Step 5: Add `_startCountdown()` to the dedup guard early return**

In `_doCandidatesRequest()`, replace:

```dart
      if (moved < 30 && jaccard >= 0.8) {
        AppLogger.info(LogEvents.triggerSkip, {
          'reason': 'poi_unchanged',
          'moved_m': moved,
          'jaccard': jaccard,
        });
        return;
      }
```

with:

```dart
      if (moved < 30 && jaccard >= 0.8) {
        AppLogger.info(LogEvents.triggerSkip, {
          'reason': 'poi_unchanged',
          'moved_m': moved,
          'jaccard': jaccard,
        });
        _startCountdown();
        return;
      }
```

- [ ] **Step 6: Run all trigger provider tests**

```bash
flutter test test/unit/trigger_provider_test.dart --reporter=compact
```

Expected: all 8 tests pass. Verify the `TriggerProvider skips narrate() when POIs unchanged and user did not move` test still passes too (it checks `callCount` stays at 1, which remains true).

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "fix(flutter): restart countdown when available empty or dedup guard blocks"
```

---

## Task 3: Remove `_DisplacementBadge` from UI

**Files:**
- Modify: `flutter_app/lib/features/narration/widgets/countdown_badge.dart`

- [ ] **Step 1: Replace `countdown_badge.dart` with the trimmed version**

Remove the `isWaitingForDisplacement` branch and the entire `_DisplacementBadge` class. The file should become:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class CountdownBadge extends ConsumerWidget {
  const CountdownBadge({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final triggerState = ref.watch(triggerProvider);

    if (!triggerState.isCountingDown) return const SizedBox.shrink();

    final settings = ref.watch(appSettingsProvider);
    final totalMs = settings.countdownSeconds * 1000.0;
    final remaining = triggerState.countdownRemaining;
    final remainingSeconds = remaining.inSeconds;
    final progress = remaining.inMilliseconds / totalMs;

    return GestureDetector(
      onTap: () => ref.read(triggerProvider.notifier).skipCountdown(),
      child: Container(
        width: 72,
        height: 72,
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.7),
          shape: BoxShape.circle,
        ),
        child: Stack(
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
              children: [
                Text(
                  '$remainingSeconds',
                  style: const TextStyle(
                    color: Colors.white,
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const Text(
                  '下一個',
                  style: TextStyle(color: Colors.white70, fontSize: 9),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
```

- [ ] **Step 2: Run the full Flutter test suite**

```bash
flutter test --reporter=compact
```

Expected: all tests pass. No references to `isWaitingForDisplacement` remain.

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/narration/widgets/countdown_badge.dart
git commit -m "refactor(flutter): remove displacement badge, countdown is the only idle state"
```
