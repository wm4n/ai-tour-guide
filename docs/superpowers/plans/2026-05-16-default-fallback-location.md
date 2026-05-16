# Default Fallback Location Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When no GPS arrives within 5 seconds of the location stream starting, inject a language-appropriate fallback position so the full map + POI experience works on simulators.

**Architecture:** Add `effectivePositionStreamProvider` that wraps the GPS stream with a 5-second timeout, emitting a fallback `Position` (故宮 for zh-TW, Smithsonian for en) if no real GPS arrives first. All UI consumers switch to this provider; the raw `positionStreamProvider` stays unchanged.

**Tech Stack:** Flutter, Riverpod 2.x (`StreamProvider`, `Provider`), `geolocator` (`Position`), Dart `dart:async` (`Timer`, `StreamController`)

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `lib/shared/location/fallback_locations.dart` | Fallback coordinate constants + `fallbackPosition()` helper |
| Modify | `lib/features/map/providers/poi_provider.dart` | Add `sessionLangProvider`, `fallbackTimeoutProvider`, `effectivePositionStreamProvider`; update `PoiNotifier` |
| Modify | `lib/features/map/screens/map_screen.dart` | Switch 2 references to `effectivePositionStreamProvider`; fix initial target |
| Modify | `lib/features/narration/providers/trigger_provider.dart` | Switch 1 reference to `effectivePositionStreamProvider` |
| Create | `test/unit/fallback_locations_test.dart` | Unit tests for `fallbackPosition()` |
| Create | `test/unit/effective_position_provider_test.dart` | Unit tests for `effectivePositionStreamProvider` |
| Modify | `test/unit/poi_provider_test.dart` | Add `sessionLangProvider` override |
| Modify | `test/unit/trigger_provider_test.dart` | Add `sessionLangProvider` override |

---

## Task 1: Create fallback_locations.dart

**Files:**
- Create: `lib/shared/location/fallback_locations.dart`
- Create: `test/unit/fallback_locations_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/unit/fallback_locations_test.dart`:

```dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/location/fallback_locations.dart';

void main() {
  test('fallbackPosition zh-TW returns 故宮 coordinates', () {
    final pos = fallbackPosition('zh-TW');
    expect(pos.latitude, closeTo(25.1023, 0.0001));
    expect(pos.longitude, closeTo(121.5484, 0.0001));
  });

  test('fallbackPosition en returns Smithsonian coordinates', () {
    final pos = fallbackPosition('en');
    expect(pos.latitude, closeTo(38.8882, 0.0001));
    expect(pos.longitude, closeTo(-77.0197, 0.0001));
  });

  test('fallbackPosition unknown lang falls back to en', () {
    final pos = fallbackPosition('fr');
    expect(pos.latitude, closeTo(38.8882, 0.0001));
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd flutter_app && flutter test test/unit/fallback_locations_test.dart
```

Expected: FAIL — `fallback_locations.dart` not found.

- [ ] **Step 3: Implement fallback_locations.dart**

Create `lib/shared/location/fallback_locations.dart`:

```dart
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:geolocator/geolocator.dart';

const _kFallbackZhTW = (lat: 25.1023, lon: 121.5484);
const _kFallbackEn   = (lat: 38.8882, lon: -77.0197);

Position fallbackPosition(String lang) {
  final coords = lang == 'zh-TW' ? _kFallbackZhTW : _kFallbackEn;
  return fakePosition(coords.lat, coords.lon);
}
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd flutter_app && flutter test test/unit/fallback_locations_test.dart
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/shared/location/fallback_locations.dart \
        flutter_app/test/unit/fallback_locations_test.dart
git commit -m "feat: add language-aware fallback location constants"
```

---

## Task 2: Add effectivePositionStreamProvider

**Files:**
- Modify: `lib/features/map/providers/poi_provider.dart`
- Create: `test/unit/effective_position_provider_test.dart`

- [ ] **Step 1: Write failing tests**

Create `test/unit/effective_position_provider_test.dart`:

```dart
import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  test('forwards GPS position when it arrives before timeout', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 500)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.microtask(() {});

    fakeLocation.emit(fakePosition(1.0, 2.0));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(positions, hasLength(1));
    expect(positions.first.latitude, 1.0);
    expect(positions.first.longitude, 2.0);
  });

  test('emits zh-TW fallback after timeout when no GPS arrives', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 100)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.delayed(const Duration(milliseconds: 250));

    expect(positions, hasLength(1));
    expect(positions.first.latitude, closeTo(25.1023, 0.001));
    expect(positions.first.longitude, closeTo(121.5484, 0.001));
  });

  test('emits en fallback after timeout when no GPS arrives', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('en'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 100)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.delayed(const Duration(milliseconds: 250));

    expect(positions, hasLength(1));
    expect(positions.first.latitude, closeTo(38.8882, 0.001));
    expect(positions.first.longitude, closeTo(-77.0197, 0.001));
  });

  test('continues forwarding GPS positions after fallback was emitted', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 100)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    // Wait for fallback to emit
    await Future<void>.delayed(const Duration(milliseconds: 250));
    expect(positions, hasLength(1));

    // Now GPS arrives
    fakeLocation.emit(fakePosition(1.0, 2.0));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(positions, hasLength(2));
    expect(positions.last.latitude, 1.0);
  });
}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd flutter_app && flutter test test/unit/effective_position_provider_test.dart
```

Expected: FAIL — `effectivePositionStreamProvider`, `sessionLangProvider`, `fallbackTimeoutProvider` not defined.

- [ ] **Step 3: Add the three new providers to poi_provider.dart**

Open `lib/features/map/providers/poi_provider.dart` and add these imports at the top:

```dart
import 'dart:async';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/location/fallback_locations.dart';
```

Then add the three providers **after** the existing `positionStreamProvider` definition (after line 13):

```dart
final sessionLangProvider = Provider<String>((ref) {
  return ref.watch(sessionProvider.select((s) => s.lang));
});

final fallbackTimeoutProvider = Provider<Duration>((ref) {
  return const Duration(seconds: 5);
});

final effectivePositionStreamProvider = StreamProvider<Position>((ref) {
  final lang = ref.watch(sessionLangProvider);
  final timeout = ref.watch(fallbackTimeoutProvider);
  final controller = StreamController<Position>.broadcast();
  var gotRealPosition = false;

  final timer = Timer(timeout, () {
    if (!gotRealPosition && !controller.isClosed) {
      controller.add(fallbackPosition(lang));
    }
  });

  final sub = ref.watch(locationServiceProvider).positionStream.listen(
    (pos) {
      gotRealPosition = true;
      timer.cancel();
      controller.add(pos);
    },
    onError: controller.addError,
  );

  ref.onDispose(() {
    timer.cancel();
    sub.cancel();
    controller.close();
  });

  return controller.stream;
});
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd flutter_app && flutter test test/unit/effective_position_provider_test.dart
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/map/providers/poi_provider.dart \
        flutter_app/test/unit/effective_position_provider_test.dart
git commit -m "feat: add effectivePositionStreamProvider with 5s GPS fallback"
```

---

## Task 3: Update PoiNotifier to use effectivePositionStreamProvider

**Files:**
- Modify: `lib/features/map/providers/poi_provider.dart` (PoiNotifier.build)
- Modify: `test/unit/poi_provider_test.dart`

- [ ] **Step 1: Update poi_provider_test.dart first (red)**

In `test/unit/poi_provider_test.dart`, add `sessionLangProvider` override to the `ProviderContainer`:

```dart
// BEFORE
final container = ProviderContainer(
  overrides: [
    locationServiceProvider.overrideWithValue(fakeLocation),
    backendClientProvider.overrideWithValue(fakeClient),
  ],
);

// AFTER
final container = ProviderContainer(
  overrides: [
    locationServiceProvider.overrideWithValue(fakeLocation),
    backendClientProvider.overrideWithValue(fakeClient),
    sessionLangProvider.overrideWithValue('zh-TW'),
  ],
);
```

Also add the import at the top:
```dart
import 'package:flutter_app/features/map/providers/poi_provider.dart'; // already present
```

`sessionLangProvider` is exported from `poi_provider.dart` so no extra import needed.

- [ ] **Step 2: Update PoiNotifier.build() in poi_provider.dart**

Change the `ref.listen` call inside `PoiNotifier.build()`:

```dart
// BEFORE (line ~21)
ref.listen<AsyncValue<Position>>(
  positionStreamProvider,
  (_, next) => next.whenData(_onPosition),
);

// AFTER
ref.listen<AsyncValue<Position>>(
  effectivePositionStreamProvider,
  (_, next) => next.whenData(_onPosition),
);
```

- [ ] **Step 3: Run poi_provider tests**

```bash
cd flutter_app && flutter test test/unit/poi_provider_test.dart
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/map/providers/poi_provider.dart \
        flutter_app/test/unit/poi_provider_test.dart
git commit -m "feat: poi_provider uses effectivePositionStreamProvider"
```

---

## Task 4: Update trigger_provider to use effectivePositionStreamProvider

**Files:**
- Modify: `lib/features/narration/providers/trigger_provider.dart`
- Modify: `test/unit/trigger_provider_test.dart`

- [ ] **Step 1: Update trigger_provider_test.dart**

In `test/unit/trigger_provider_test.dart`, add `sessionLangProvider.overrideWithValue('zh-TW')` to **both** `ProviderContainer` overrides lists:

```dart
// First test container — add:
sessionLangProvider.overrideWithValue('zh-TW'),

// Second test container — add:
sessionLangProvider.overrideWithValue('zh-TW'),
```

`sessionLangProvider` is in `poi_provider.dart`, which is already imported:
```dart
import 'package:flutter_app/features/map/providers/poi_provider.dart';
```

- [ ] **Step 2: Update trigger_provider.dart**

In `lib/features/narration/providers/trigger_provider.dart`, change the `ref.watch` call inside `TriggerNotifier.build()`:

```dart
// BEFORE (line 18)
final positionAsync = ref.watch(positionStreamProvider);

// AFTER
final positionAsync = ref.watch(effectivePositionStreamProvider);
```

- [ ] **Step 3: Run trigger_provider tests**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "feat: trigger_provider uses effectivePositionStreamProvider"
```

---

## Task 5: Update map_screen to use effectivePositionStreamProvider

**Files:**
- Modify: `lib/features/map/screens/map_screen.dart`

No new tests needed — this is UI wiring; the provider tests cover the logic.

- [ ] **Step 1: Update the two positionStreamProvider references**

In `lib/features/map/screens/map_screen.dart`:

Change line 45-47:
```dart
// BEFORE
final position = ref.watch(
  positionStreamProvider.select((v) => v.valueOrNull),
);

// AFTER
final position = ref.watch(
  effectivePositionStreamProvider.select((v) => v.valueOrNull),
);
```

Change the `ref.listen` call (line ~51):
```dart
// BEFORE
ref.listen<AsyncValue<Position>>(
  positionStreamProvider,
  (_, next) => next.whenData(_centerOnPosition),
);

// AFTER
ref.listen<AsyncValue<Position>>(
  effectivePositionStreamProvider,
  (_, next) => next.whenData(_centerOnPosition),
);
```

- [ ] **Step 2: Fix the initialTarget fallback**

Change lines 89-91:
```dart
// BEFORE
final initialTarget = position != null
    ? LatLng(position.latitude, position.longitude)
    : const LatLng(25.1023, 121.5482);

// AFTER
final initialTarget = position != null
    ? LatLng(position.latitude, position.longitude)
    : const LatLng(0, 0);
```

The `LatLng(0, 0)` is only ever shown for a fraction of a second before `effectivePositionStreamProvider` moves the camera (either via real GPS or the 5-second fallback).

- [ ] **Step 3: Run all unit tests to confirm nothing broke**

```bash
cd flutter_app && flutter test test/unit/
```

Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/map/screens/map_screen.dart
git commit -m "feat: map_screen uses effectivePositionStreamProvider, removes hardcoded fallback LatLng"
```

---

## Task 6: Full test run + smoke check

- [ ] **Step 1: Run the full test suite**

```bash
cd flutter_app && flutter test
```

Expected: All tests PASS, no compilation errors.

- [ ] **Step 2: Build to confirm no analyzer errors**

```bash
cd flutter_app && flutter analyze --no-fatal-infos
```

Expected: No errors.

- [ ] **Step 3: Manual smoke check on simulator**

Run the app on a simulator (no GPS):
```bash
cd flutter_app && flutter run
```

Start a session. Within 5 seconds, the map camera should animate to:
- **zh-TW**: 台北故宮博物院 area (25.1023°N, 121.5484°E)
- **en**: Smithsonian area (38.8882°N, 77.0197°W)

POIs should appear at the fallback location within a few seconds after the camera moves.
