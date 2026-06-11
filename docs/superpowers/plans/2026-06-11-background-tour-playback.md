# Background Tour Playback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Android-first background long-form tour playback with auto-play/notify-only settings, portable/car profiles, and a POI playback queue.

**Architecture:** Add a `TourPlaybackQueue` provider between `TriggerProvider` and `NarrationProvider`. `TriggerProvider` discovers candidates and submits them to the queue or notification path; `NarrationProvider` remains responsible for one stream at a time; `AudioPlayerService` is prepared for Android background media playback through `audio_service + just_audio`.

**Tech Stack:** Flutter, Riverpod, geolocator, just_audio, audio_service, flutter_local_notifications, shared_preferences, flutter_test.

---

## Scope Check

This plan implements the Android-first "B now, C later" slice from the approved design:

- background trigger delivery while a journey is active
- playback queue for long-form POI narration
- auto-play versus notify-only mode
- portable versus car profile
- minimal queue UI
- Android media-service setup for background playback

It does not implement iOS background behavior, Android Auto, CarPlay, full queue management screens, route planning, or smart ranking.

## File Structure

- Create: `flutter_app/lib/features/narration/providers/tour_playback_queue_provider.dart`
  - Owns queue state, duplicate prevention, stale item filtering, skip-to-next, and queue-to-narration orchestration.
- Create: `flutter_app/test/unit/tour_playback_queue_provider_test.dart`
  - Tests queue behavior without real platform services.
- Modify: `flutter_app/lib/shared/settings/app_settings.dart`
  - Adds `TourPlaybackMode` and `TourUsageProfile`.
- Modify: `flutter_app/lib/shared/settings/settings_provider.dart`
  - Persists new settings in `SharedPreferences`.
- Modify: `flutter_app/test/unit/settings_provider_test.dart`
  - Covers defaults and persistence for new settings.
- Modify: `flutter_app/lib/features/settings/settings_screen.dart`
  - Adds segmented/toggle settings for playback mode and usage profile.
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
  - Sends candidates to `TourPlaybackQueue` or notification service; stops blocking active journeys only because the app is backgrounded.
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`
  - Verifies background active journeys queue candidates and notify-only mode notifies.
- Modify: `flutter_app/lib/features/narration/providers/narration_provider.dart`
  - Adds a queue-friendly `stopCurrent()` method and keeps `skip()` behavior compatible.
- Modify: `flutter_app/lib/features/narration/widgets/narration_mini_bar.dart`
  - Shows queue count/next POI and routes skip to queue advance.
- Modify: `flutter_app/lib/features/narration/widgets/narration_sheet.dart`
  - Shows minimal queue state if the file already owns expanded playback details.
- Modify: `flutter_app/test/widget/narration_sheet_test.dart`
  - Covers queue state display if `NarrationSheet` is changed.
- Modify: `flutter_app/pubspec.yaml`
  - Adds `audio_service` via `flutter pub add audio_service`.
- Modify: `flutter_app/lib/shared/audio/audio_player_service.dart`
  - Introduces an audio-service-backed Android implementation boundary while preserving the current interface and fake.
- Modify: `flutter_app/android/app/src/main/AndroidManifest.xml`
  - Adds media playback foreground service declarations required by `audio_service`.
- Create or modify: `tasks/todo.md`
  - Adds a review/results section for this implementation.

## Task 1: Add Tour Playback Settings

**Files:**
- Modify: `flutter_app/lib/shared/settings/app_settings.dart`
- Modify: `flutter_app/lib/shared/settings/settings_provider.dart`
- Modify: `flutter_app/test/unit/settings_provider_test.dart`

- [ ] **Step 1: Write failing settings tests**

Add these tests to `flutter_app/test/unit/settings_provider_test.dart`:

```dart
test('tour playback settings defaults are correct', () {
  const settings = AppSettings();
  expect(settings.tourPlaybackMode, TourPlaybackMode.autoPlay);
  expect(settings.tourUsageProfile, TourUsageProfile.portable);
});

test('setTourPlaybackMode updates state and persists', () async {
  SharedPreferences.setMockInitialValues({});
  final container = ProviderContainer();
  addTearDown(container.dispose);

  await container
      .read(appSettingsProvider.notifier)
      .setTourPlaybackMode(TourPlaybackMode.notifyOnly);

  expect(
    container.read(appSettingsProvider).tourPlaybackMode,
    TourPlaybackMode.notifyOnly,
  );
  final prefs = await SharedPreferences.getInstance();
  expect(prefs.getString('tour_playback_mode'), 'notifyOnly');
});

test('setTourUsageProfile updates state and persists', () async {
  SharedPreferences.setMockInitialValues({});
  final container = ProviderContainer();
  addTearDown(container.dispose);

  await container
      .read(appSettingsProvider.notifier)
      .setTourUsageProfile(TourUsageProfile.car);

  expect(
    container.read(appSettingsProvider).tourUsageProfile,
    TourUsageProfile.car,
  );
  final prefs = await SharedPreferences.getInstance();
  expect(prefs.getString('tour_usage_profile'), 'car');
});

test('loads persisted tour playback settings on init', () async {
  SharedPreferences.setMockInitialValues({
    'tour_playback_mode': 'notifyOnly',
    'tour_usage_profile': 'car',
  });
  final container = ProviderContainer();
  addTearDown(container.dispose);

  container.listen(appSettingsProvider, (_, __) {});
  await Future<void>.delayed(const Duration(milliseconds: 50));

  final settings = container.read(appSettingsProvider);
  expect(settings.tourPlaybackMode, TourPlaybackMode.notifyOnly);
  expect(settings.tourUsageProfile, TourUsageProfile.car);
});
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
cd flutter_app
flutter test test/unit/settings_provider_test.dart
```

Expected: FAIL because `TourPlaybackMode`, `TourUsageProfile`, `tourPlaybackMode`, `tourUsageProfile`, `setTourPlaybackMode`, and `setTourUsageProfile` do not exist.

- [ ] **Step 3: Add settings types and fields**

Update `flutter_app/lib/shared/settings/app_settings.dart`:

```dart
enum TourPlaybackMode { autoPlay, notifyOnly }

enum TourUsageProfile { portable, car }

class AppSettings {
  final double skipDisplacementM;
  final int countdownSeconds;
  final TourPlaybackMode tourPlaybackMode;
  final TourUsageProfile tourUsageProfile;

  const AppSettings({
    this.skipDisplacementM = 1500.0,
    this.countdownSeconds = 90,
    this.tourPlaybackMode = TourPlaybackMode.autoPlay,
    this.tourUsageProfile = TourUsageProfile.portable,
  });

  AppSettings copyWith({
    double? skipDisplacementM,
    int? countdownSeconds,
    TourPlaybackMode? tourPlaybackMode,
    TourUsageProfile? tourUsageProfile,
  }) =>
      AppSettings(
        skipDisplacementM: skipDisplacementM ?? this.skipDisplacementM,
        countdownSeconds: countdownSeconds ?? this.countdownSeconds,
        tourPlaybackMode: tourPlaybackMode ?? this.tourPlaybackMode,
        tourUsageProfile: tourUsageProfile ?? this.tourUsageProfile,
      );
}
```

- [ ] **Step 4: Persist settings**

Update `flutter_app/lib/shared/settings/settings_provider.dart`:

```dart
class AppSettingsNotifier extends Notifier<AppSettings> {
  static const _keyDisplacement = 'skip_displacement_m';
  static const _keyCountdown = 'countdown_seconds';
  static const _keyTourPlaybackMode = 'tour_playback_mode';
  static const _keyTourUsageProfile = 'tour_usage_profile';

  @override
  AppSettings build() {
    _load();
    return const AppSettings();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = AppSettings(
      skipDisplacementM: prefs.getDouble(_keyDisplacement) ?? 1500.0,
      countdownSeconds: prefs.getInt(_keyCountdown) ?? 90,
      tourPlaybackMode: _parsePlaybackMode(
        prefs.getString(_keyTourPlaybackMode),
      ),
      tourUsageProfile: _parseUsageProfile(
        prefs.getString(_keyTourUsageProfile),
      ),
    );
  }

  TourPlaybackMode _parsePlaybackMode(String? value) {
    return TourPlaybackMode.values.firstWhere(
      (mode) => mode.name == value,
      orElse: () => TourPlaybackMode.autoPlay,
    );
  }

  TourUsageProfile _parseUsageProfile(String? value) {
    return TourUsageProfile.values.firstWhere(
      (profile) => profile.name == value,
      orElse: () => TourUsageProfile.portable,
    );
  }

  Future<void> setSkipDisplacement(double meters) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyDisplacement, meters);
    state = state.copyWith(skipDisplacementM: meters);
  }

  Future<void> setCountdownSeconds(int seconds) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCountdown, seconds);
    state = state.copyWith(countdownSeconds: seconds);
  }

  Future<void> setTourPlaybackMode(TourPlaybackMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTourPlaybackMode, mode.name);
    state = state.copyWith(tourPlaybackMode: mode);
  }

  Future<void> setTourUsageProfile(TourUsageProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTourUsageProfile, profile.name);
    state = state.copyWith(tourUsageProfile: profile);
  }
}
```

- [ ] **Step 5: Run settings tests**

Run:

```bash
cd flutter_app
flutter test test/unit/settings_provider_test.dart
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/shared/settings/app_settings.dart flutter_app/lib/shared/settings/settings_provider.dart flutter_app/test/unit/settings_provider_test.dart
git commit -m "feat(flutter): add tour playback settings"
```

## Task 2: Build TourPlaybackQueue Core

**Files:**
- Create: `flutter_app/lib/features/narration/providers/tour_playback_queue_provider.dart`
- Create: `flutter_app/test/unit/tour_playback_queue_provider_test.dart`

- [ ] **Step 1: Write failing queue tests**

Create `flutter_app/test/unit/tour_playback_queue_provider_test.dart` with:

```dart
import 'dart:typed_data';

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

const _poiA = POI(
  id: 'poi-a',
  name: 'A 景點',
  lat: 25.0,
  lon: 121.5,
  tags: {},
  distanceM: 50,
  confidence: 'high',
);

const _poiB = POI(
  id: 'poi-b',
  name: 'B 景點',
  lat: 25.0005,
  lon: 121.5005,
  tags: {},
  distanceM: 80,
  confidence: 'high',
);

class _SettingsNotifier extends AppSettingsNotifier {
  final AppSettings _settings;
  _SettingsNotifier(this._settings);
  @override
  AppSettings build() => _settings;
}

class _Client implements BackendClient {
  int narrateCalls = 0;

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async => const [];

  @override
  Stream<NarrationEvent> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    required String length,
    PreviousSelection? previousSelection,
    bool forceRegenerate = false,
  }) async* {
    narrateCalls++;
    yield MetaEvent(
      poiId: candidates.first.id,
      poiName: candidates.first.name,
      cacheHit: false,
      confidence: candidates.first.confidence,
    );
  }

  @override
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async* {}
}

ProviderContainer _container({
  AppSettings settings = const AppSettings(),
}) {
  final db = LocalDb.forTesting(NativeDatabase.memory());
  final fakeLocation = FakeLocationService();
  fakeLocation.emit(fakePosition(25.0, 121.5));

  final container = ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(_Client()),
      audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
      localDbProvider.overrideWithValue(db),
      locationServiceProvider.overrideWithValue(fakeLocation),
      appSettingsProvider.overrideWith(() => _SettingsNotifier(settings)),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);
  return container;
}

void main() {
  test('enqueue starts playback when narration is idle', () async {
    final container = _container();
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(container.read(tourPlaybackQueueProvider).currentPoi?.id, 'poi-a');
    expect(container.read(narrationProvider).currentPoi?.id, 'poi-a');
  });

  test('playing item is not interrupted when a new POI is triggered', () async {
    final container = _container();
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiB]);

    final state = container.read(tourPlaybackQueueProvider);
    expect(state.currentPoi?.id, 'poi-a');
    expect(state.queuedCount, 1);
    expect(state.nextPoi?.id, 'poi-b');
  });

  test('duplicate POIs are not queued twice', () async {
    final container = _container();
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA, _poiA]);
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);

    expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
    expect(container.read(tourPlaybackQueueProvider).currentPoi?.id, 'poi-a');
  });

  test('notify-only mode does not enqueue', () async {
    final container = _container(
      settings: const AppSettings(
        tourPlaybackMode: TourPlaybackMode.notifyOnly,
      ),
    );
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);

    expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
    expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
  });

  test('clear empties current and queued POIs', () async {
    final container = _container();
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiB]);

    await container.read(tourPlaybackQueueProvider.notifier).clear();

    final state = container.read(tourPlaybackQueueProvider);
    expect(state.currentPoi, isNull);
    expect(state.queuedCount, 0);
  });
}
```

- [ ] **Step 2: Run queue tests to verify failure**

Run:

```bash
cd flutter_app
flutter test test/unit/tour_playback_queue_provider_test.dart
```

Expected: FAIL because `tour_playback_queue_provider.dart` does not exist.

- [ ] **Step 3: Implement queue provider**

Create `flutter_app/lib/features/narration/providers/tour_playback_queue_provider.dart`:

```dart
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class QueuedPoi {
  final POI poi;
  final DateTime queuedAt;

  const QueuedPoi({
    required this.poi,
    required this.queuedAt,
  });
}

class TourPlaybackQueueState {
  final POI? currentPoi;
  final List<QueuedPoi> queue;

  const TourPlaybackQueueState({
    this.currentPoi,
    this.queue = const [],
  });

  POI? get nextPoi => queue.isEmpty ? null : queue.first.poi;
  int get queuedCount => queue.length;

  TourPlaybackQueueState copyWith({
    POI? currentPoi,
    bool clearCurrentPoi = false,
    List<QueuedPoi>? queue,
  }) {
    return TourPlaybackQueueState(
      currentPoi: clearCurrentPoi ? null : currentPoi ?? this.currentPoi,
      queue: queue ?? this.queue,
    );
  }
}

class TourPlaybackQueueNotifier extends Notifier<TourPlaybackQueueState> {
  static const itemTtl = Duration(minutes: 10);

  @override
  TourPlaybackQueueState build() {
    ref.listen<NarrationState>(narrationProvider, (prev, next) {
      final completed = prev?.status == NarrationStatus.playing &&
          next.status == NarrationStatus.idle;
      final errored = (prev?.status == NarrationStatus.loading ||
              prev?.status == NarrationStatus.playing) &&
          next.status == NarrationStatus.error;
      if (completed || errored) {
        state = state.copyWith(clearCurrentPoi: true);
        unawaited(_playNextValid());
      }
    });
    return const TourPlaybackQueueState();
  }

  Future<void> enqueue({required List<POI> candidates}) async {
    final settings = ref.read(appSettingsProvider);
    if (settings.tourPlaybackMode == TourPlaybackMode.notifyOnly) return;

    final now = DateTime.now();
    final knownIds = <String>{
      if (state.currentPoi != null) state.currentPoi!.id,
      ...state.queue.map((item) => item.poi.id),
    };
    final additions = <QueuedPoi>[];
    for (final poi in candidates) {
      if (knownIds.add(poi.id)) {
        additions.add(QueuedPoi(poi: poi, queuedAt: now));
      }
    }
    if (additions.isNotEmpty) {
      state = state.copyWith(queue: [...state.queue, ...additions]);
    }
    await _playNextValid();
  }

  Future<void> skipToNext() async {
    await ref.read(narrationProvider.notifier).stopCurrent();
    state = state.copyWith(clearCurrentPoi: true);
    await _playNextValid();
  }

  Future<void> clear() async {
    await ref.read(narrationProvider.notifier).stopCurrent();
    state = const TourPlaybackQueueState();
  }

  Future<void> _playNextValid() async {
    final narration = ref.read(narrationProvider);
    if (narration.status == NarrationStatus.loading ||
        narration.status == NarrationStatus.playing ||
        narration.status == NarrationStatus.paused ||
        state.currentPoi != null) {
      return;
    }

    final next = _takeNextValid();
    if (next == null) return;

    state = state.copyWith(
      currentPoi: next.poi,
      queue: state.queue.where((item) => item.poi.id != next.poi.id).toList(),
    );

    final session = ref.read(sessionProvider);
    await ref.read(narrationProvider.notifier).narrate(
          candidates: [next.poi],
          persona: session.persona,
          lang: session.lang,
          previousSelection: null,
        );
  }

  QueuedPoi? _takeNextValid() {
    final settings = ref.read(appSettingsProvider);
    final location = ref.read(locationServiceProvider);
    final now = DateTime.now();
    final maxDistance = settings.tourUsageProfile == TourUsageProfile.car
        ? 800.0
        : 250.0;

    for (final item in state.queue) {
      if (now.difference(item.queuedAt) > itemTtl) continue;
      final position = location.latestPosition;
      if (position != null) {
        final distance = haversine(
          position.latitude,
          position.longitude,
          item.poi.lat,
          item.poi.lon,
        );
        if (distance > maxDistance) continue;
      }
      return item;
    }
    state = state.copyWith(queue: const []);
    return null;
  }
}

final tourPlaybackQueueProvider =
    NotifierProvider<TourPlaybackQueueNotifier, TourPlaybackQueueState>(
  TourPlaybackQueueNotifier.new,
);
```

- [ ] **Step 4: Add latest position to LocationService**

Modify `flutter_app/lib/shared/location/location_service.dart`:

```dart
abstract class LocationService {
  Future<bool> requestPermission();
  Future<LocationPermission> checkPermission();
  void start();
  void stop();
  Stream<Position> get positionStream;
  Position? get latestPosition;
}
```

In `RealLocationService`, add:

```dart
Position? _latestPosition;

@override
Position? get latestPosition => _latestPosition;
```

And update the listener:

```dart
).listen(
  (position) {
    _latestPosition = position;
    _controller!.add(position);
  },
  onError: _controller!.addError,
);
```

In `FakeLocationService`, add:

```dart
Position? _latestPosition;

void emit(Position position) {
  _latestPosition = position;
  _controller.add(position);
}

@override
Position? get latestPosition => _latestPosition;
```

- [ ] **Step 5: Add queue-friendly stopCurrent to NarrationProvider**

Modify `flutter_app/lib/features/narration/providers/narration_provider.dart`:

```dart
Future<void> stopCurrent() async {
  _audioSub?.cancel();
  _audioSub = null;
  _sseStreamEnded = false;
  await _sub?.cancel();
  _sub = null;
  await _audio.reset();
  state = const NarrationState(status: NarrationStatus.idle);
}
```

Then simplify `skip()` to call `stopCurrent()` after logging:

```dart
Future<void> skip() async {
  AppLogger.warn(LogEvents.narrationSkip, {
    'poi_id': state.currentPoi?.id ?? '',
    'reason': 'user_skip',
  });
  await stopCurrent();
}
```

- [ ] **Step 6: Run queue tests**

Run:

```bash
cd flutter_app
flutter test test/unit/tour_playback_queue_provider_test.dart
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/narration/providers/tour_playback_queue_provider.dart flutter_app/test/unit/tour_playback_queue_provider_test.dart flutter_app/lib/shared/location/location_service.dart flutter_app/lib/features/narration/providers/narration_provider.dart
git commit -m "feat(flutter): add tour playback queue"
```

## Task 3: Route TriggerProvider Through Queue and Notification Mode

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: Add failing trigger tests**

Add tests to `flutter_app/test/unit/trigger_provider_test.dart`:

```dart
test('background active journey queues candidates in auto-play mode', () async {
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
            MetaEvent(
              poiId: 'osm:node:1',
              poiName: '故宮',
              cacheHit: false,
              confidence: 'high',
            ),
          ],
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appLifecycleStateProvider.overrideWith(
        (ref) => AppLifecycleState.paused,
      ),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);

  container.listen(triggerProvider, (_, __) {});
  container.listen(narrationProvider, (_, __) {});
  container.listen(tourPlaybackQueueProvider, (_, __) {});
  await container.read(sessionProvider.notifier).start();

  fakeLocation.emit(fakePosition(25.1023, 121.5482));
  await Future<void>.delayed(const Duration(milliseconds: 200));

  expect(container.read(tourPlaybackQueueProvider).currentPoi?.id, 'osm:node:1');
});

test('notify-only mode shows notification without queueing', () async {
  final fakeLocation = FakeLocationService();
  final fakeAudio = FakeAudioPlayerService();
  final fakeNotification = FakeNotificationService();
  final db = LocalDb.forTesting(NativeDatabase.memory());

  final container = ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      notificationServiceProvider.overrideWithValue(fakeNotification),
      backendClientProvider.overrideWithValue(
        FakeBackendClient(
          nearbyPois: const [_poi],
          scriptedEvents: const [],
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appLifecycleStateProvider.overrideWith(
        (ref) => AppLifecycleState.paused,
      ),
      appSettingsProvider.overrideWith(
        () => _FakeSettingsNotifier(
          const AppSettings(tourPlaybackMode: TourPlaybackMode.notifyOnly),
        ),
      ),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);

  container.listen(triggerProvider, (_, __) {});
  container.listen(tourPlaybackQueueProvider, (_, __) {});
  await container.read(sessionProvider.notifier).start();

  fakeLocation.emit(fakePosition(25.1023, 121.5482));
  await Future<void>.delayed(const Duration(milliseconds: 200));

  expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
  expect(fakeNotification.shownPois.map((p) => p.id), contains('osm:node:1'));
});
```

Also add this import to the same test file:

```dart
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
```

- [ ] **Step 2: Run trigger tests to verify failure**

Run:

```bash
cd flutter_app
flutter test test/unit/trigger_provider_test.dart
```

Expected: FAIL because `TriggerProvider` still returns early when lifecycle is not resumed and still calls `narrationProvider.narrate()` directly.

- [ ] **Step 3: Modify TriggerProvider delivery path**

In `flutter_app/lib/features/narration/providers/trigger_provider.dart`, add imports:

```dart
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
```

Replace the lifecycle early return block:

```dart
final lifecycleState = ref.read(appLifecycleStateProvider);
if (lifecycleState != AppLifecycleState.resumed) return;
```

with:

```dart
final session = ref.read(sessionProvider);
if (session.status != SessionStatus.active) return;
```

At the final delivery point, replace:

```dart
ref.read(narrationProvider.notifier).narrate(
      candidates: available,
      persona: session.persona,
      lang: session.lang,
      previousSelection: previous,
    );
```

with:

```dart
final settings = ref.read(appSettingsProvider);
if (settings.tourPlaybackMode == TourPlaybackMode.notifyOnly) {
  await ref.read(notificationServiceProvider).showPoiTrigger(available.first);
} else {
  await ref
      .read(tourPlaybackQueueProvider.notifier)
      .enqueue(candidates: available);
}
```

Remove the local `previous` variable from `_doCandidatesRequest()` in this task. Keep `_lastSelectedPoiId`, `_lastSelectedPoiName`, and `_lastScript` fields only if existing countdown behavior still reads them elsewhere in the file after the replacement; otherwise remove those fields and their assignments in the same edit.

- [ ] **Step 4: Run trigger tests**

Run:

```bash
cd flutter_app
flutter test test/unit/trigger_provider_test.dart test/unit/tour_playback_queue_provider_test.dart
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart flutter_app/test/unit/trigger_provider_test.dart
git commit -m "feat(flutter): route triggers through tour queue"
```

## Task 4: Add Settings UI and Queue UI

**Files:**
- Modify: `flutter_app/lib/features/settings/settings_screen.dart`
- Modify: `flutter_app/lib/features/narration/widgets/narration_mini_bar.dart`
- Create: `flutter_app/test/widget/narration_mini_bar_test.dart`

- [ ] **Step 1: Add settings controls**

In `flutter_app/lib/features/settings/settings_screen.dart`, import `AppSettings` if needed:

```dart
import 'package:flutter_app/shared/settings/app_settings.dart';
```

Add this section after the existing countdown controls:

```dart
const SizedBox(height: 32),
const Text(
  '導覽播放模式',
  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
),
const SizedBox(height: 4),
const Text(
  '背景偵測到景點時要自動播放，或只顯示通知',
  style: TextStyle(color: Colors.grey, fontSize: 13),
),
const SizedBox(height: 12),
SegmentedButton<TourPlaybackMode>(
  segments: const [
    ButtonSegment(
      value: TourPlaybackMode.autoPlay,
      label: Text('自動播放'),
      icon: Icon(Icons.play_circle_outline),
    ),
    ButtonSegment(
      value: TourPlaybackMode.notifyOnly,
      label: Text('只通知'),
      icon: Icon(Icons.notifications_none),
    ),
  ],
  selected: {settings.tourPlaybackMode},
  onSelectionChanged: (selection) {
    notifier.setTourPlaybackMode(selection.first);
  },
),
const SizedBox(height: 32),
const Text(
  '使用情境',
  style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
),
const SizedBox(height: 4),
const Text(
  '車用模式會提前觸發，並允許較遠的待播距離',
  style: TextStyle(color: Colors.grey, fontSize: 13),
),
const SizedBox(height: 12),
SegmentedButton<TourUsageProfile>(
  segments: const [
    ButtonSegment(
      value: TourUsageProfile.portable,
      label: Text('隨身'),
      icon: Icon(Icons.headphones),
    ),
    ButtonSegment(
      value: TourUsageProfile.car,
      label: Text('車用'),
      icon: Icon(Icons.directions_car),
    ),
  ],
  selected: {settings.tourUsageProfile},
  onSelectionChanged: (selection) {
    notifier.setTourUsageProfile(selection.first);
  },
),
```

- [ ] **Step 2: Route mini bar skip through queue**

Modify `flutter_app/lib/features/narration/widgets/narration_mini_bar.dart`:

```dart
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
```

Read queue state:

```dart
final queue = ref.watch(tourPlaybackQueueProvider);
```

Replace the status text with:

```dart
Text(
  queue.nextPoi != null
      ? '下一段：${queue.nextPoi!.name}（待播 ${queue.queuedCount}）'
      : state.status == NarrationStatus.playing
          ? '▶ 正在播放...'
          : '⏸ 已暫停',
  style: const TextStyle(color: Colors.grey, fontSize: 12),
  overflow: TextOverflow.ellipsis,
),
```

Replace skip handler:

```dart
onPressed: () => ref
    .read(tourPlaybackQueueProvider.notifier)
    .skipToNext(),
```

- [ ] **Step 3: Run widget tests**

Create `flutter_app/test/widget/narration_mini_bar_test.dart` with:

```dart
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/features/narration/widgets/narration_mini_bar.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

const _poiA = POI(
  id: 'poi-a',
  name: 'A 景點',
  lat: 25.0,
  lon: 121.5,
  tags: {},
  distanceM: 50,
  confidence: 'high',
);

const _poiB = POI(
  id: 'poi-b',
  name: 'B 景點',
  lat: 25.0005,
  lon: 121.5005,
  tags: {},
  distanceM: 80,
  confidence: 'high',
);

void main() {
  testWidgets('mini bar shows next queued POI', (tester) async {
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final fakeLocation = FakeLocationService();
    fakeLocation.emit(fakePosition(25.0, 121.5));

    final container = ProviderContainer(
      overrides: [
        backendClientProvider.overrideWithValue(
          FakeBackendClient(
            nearbyPois: const [_poiA, _poiB],
            scriptedEvents: const [
              MetaEvent(
                poiId: 'poi-a',
                poiName: 'A 景點',
                cacheHit: false,
                confidence: 'high',
              ),
            ],
          ),
        ),
        audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
        localDbProvider.overrideWithValue(db),
        locationServiceProvider.overrideWithValue(fakeLocation),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiB]);

    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: Scaffold(body: NarrationMiniBar())),
      ),
    );
    await tester.pump();

    expect(find.textContaining('下一段：B 景點'), findsOneWidget);
  });
}
```

Run:

```bash
cd flutter_app
flutter test test/widget/narration_mini_bar_test.dart test/widget/narration_sheet_test.dart test/widget/home_screen_test.dart
```

Expected: PASS after updating any expected labels affected by the mini bar.

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/settings/settings_screen.dart flutter_app/lib/features/narration/widgets/narration_mini_bar.dart flutter_app/test/widget/narration_mini_bar_test.dart
git commit -m "feat(flutter): expose tour queue controls"
```

## Task 5: Add Android Background Media Service Boundary

**Files:**
- Modify: `flutter_app/pubspec.yaml`
- Modify: `flutter_app/lib/shared/audio/audio_player_service.dart`
- Modify: `flutter_app/android/app/src/main/AndroidManifest.xml`

- [ ] **Step 1: Add dependency**

Run:

```bash
cd flutter_app
flutter pub add audio_service
```

Expected: `pubspec.yaml` and `pubspec.lock` include `audio_service`.

- [ ] **Step 2: Add media metadata methods to AudioPlayerService**

Modify `flutter_app/lib/shared/audio/audio_player_service.dart` interface:

```dart
Future<void> setCurrentItem({
  required String id,
  required String title,
  String? subtitle,
});
```

Add to `FakeAudioPlayerService`:

```dart
String? currentItemId;
String? currentItemTitle;
String? currentItemSubtitle;

@override
Future<void> setCurrentItem({
  required String id,
  required String title,
  String? subtitle,
}) async {
  currentItemId = id;
  currentItemTitle = title;
  currentItemSubtitle = subtitle;
}
```

Add a no-op or real metadata update to `RealAudioPlayerService` first:

```dart
@override
Future<void> setCurrentItem({
  required String id,
  required String title,
  String? subtitle,
}) async {}
```

- [ ] **Step 3: Set metadata before narration starts**

In `TourPlaybackQueueNotifier._playNextValid()`, before `narrate(...)`, add:

```dart
await ref.read(audioPlayerServiceProvider).setCurrentItem(
      id: next.poi.id,
      title: next.poi.name,
      subtitle: 'AI Tour Guide',
    );
```

- [ ] **Step 4: Introduce audio_service handler**

Refactor `RealAudioPlayerService` so it can be backed by an audio handler. Keep the public `AudioPlayerService` interface stable. Use this minimal structure inside `audio_player_service.dart` or split to `shared/audio/tour_audio_handler.dart` if the file becomes too large:

Add imports:

```dart
import 'package:audio_service/audio_service.dart';
```

```dart
class TourAudioHandler extends BaseAudioHandler with QueueHandler, SeekHandler {
  TourAudioHandler(this.player) {
    player.playbackEventStream.listen((event) {
      playbackState.add(playbackState.value.copyWith(
        controls: [
          if (player.playing) MediaControl.pause else MediaControl.play,
          MediaControl.skipToNext,
        ],
        androidCompactActionIndices: const [0, 1],
        processingState: _mapProcessingState(player.processingState),
        playing: player.playing,
      ));
    });
  }

  final AudioPlayer player;

  AudioProcessingState _mapProcessingState(ProcessingState state) {
    switch (state) {
      case ProcessingState.idle:
        return AudioProcessingState.idle;
      case ProcessingState.loading:
        return AudioProcessingState.loading;
      case ProcessingState.buffering:
        return AudioProcessingState.buffering;
      case ProcessingState.ready:
        return AudioProcessingState.ready;
      case ProcessingState.completed:
        return AudioProcessingState.completed;
    }
  }

  @override
  Future<void> play() => player.play();

  @override
  Future<void> pause() => player.pause();

  @override
  Future<void> stop() => player.stop();

  @override
  Future<void> skipToNext() async {
    if (player.hasNext) {
      await player.seekToNext();
    } else {
      await player.stop();
    }
  }

  Future<void> setMediaItem({
    required String id,
    required String title,
    String? subtitle,
  }) async {
    mediaItem.add(MediaItem(
      id: id,
      title: title,
      artist: subtitle ?? 'AI Tour Guide',
    ));
  }
}
```

Initialize it in `_init()`:

```dart
late final TourAudioHandler _handler;

Future<void> _init() async {
  if (_initialized) return;
  _tempDir = await getTemporaryDirectory();
  _handler = await AudioService.init(
    builder: () => TourAudioHandler(_player),
    config: const AudioServiceConfig(
      androidNotificationChannelId: 'ai_tour_guide.playback',
      androidNotificationChannelName: 'AI Tour Guide playback',
      androidNotificationOngoing: true,
    ),
  );
  await _player.setAudioSource(_playlist);
  _initialized = true;
}
```

Update `setCurrentItem()`:

```dart
@override
Future<void> setCurrentItem({
  required String id,
  required String title,
  String? subtitle,
}) async {
  await _init();
  await _handler.setMediaItem(id: id, title: title, subtitle: subtitle);
}
```

- [ ] **Step 5: Add Android media service manifest declarations**

Modify `flutter_app/android/app/src/main/AndroidManifest.xml`.

Add permission:

```xml
<uses-permission android:name="android.permission.FOREGROUND_SERVICE_MEDIA_PLAYBACK"/>
```

Inside `<application>`, add the audio service declarations required by `audio_service`:

```xml
<service
    android:name="com.ryanheise.audioservice.AudioService"
    android:exported="true"
    android:foregroundServiceType="mediaPlayback">
    <intent-filter>
        <action android:name="android.media.browse.MediaBrowserService"/>
    </intent-filter>
</service>

<receiver
    android:name="com.ryanheise.audioservice.MediaButtonReceiver"
    android:exported="true">
    <intent-filter>
        <action android:name="android.intent.action.MEDIA_BUTTON"/>
    </intent-filter>
</receiver>
```

- [ ] **Step 6: Run analyzer and audio tests**

Run:

```bash
cd flutter_app
flutter analyze
flutter test test/unit/audio_duck_test.dart test/unit/tour_playback_queue_provider_test.dart
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add flutter_app/pubspec.yaml flutter_app/pubspec.lock flutter_app/lib/shared/audio/audio_player_service.dart flutter_app/lib/features/narration/providers/tour_playback_queue_provider.dart flutter_app/android/app/src/main/AndroidManifest.xml
git commit -m "feat(flutter): prepare background media playback"
```

## Task 6: End Journey Clears Queue

**Files:**
- Modify: `flutter_app/lib/features/session/providers/session_provider.dart`
- Modify: `flutter_app/test/unit/session_provider_test.dart`

- [ ] **Step 1: Write failing session test**

Add to `flutter_app/test/unit/session_provider_test.dart`:

```dart
test('stop clears tour playback queue', () async {
  final fakeLocation = FakeLocationService();
  fakeLocation.emit(fakePosition(25.0, 121.5));
  final db = LocalDb.forTesting(NativeDatabase.memory());
  final container = ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(
        FakeBackendClient(
          nearbyPois: const [],
          scriptedEvents: const [
            MetaEvent(
              poiId: 'poi-a',
              poiName: 'A 景點',
              cacheHit: false,
              confidence: 'high',
            ),
          ],
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
      locationServiceProvider.overrideWithValue(fakeLocation),
      localDbProvider.overrideWithValue(db),
    ],
  );
  addTearDown(container.dispose);
  addTearDown(db.close);

  container.listen(tourPlaybackQueueProvider, (_, __) {});
  await container.read(sessionProvider.notifier).start();
  await container.read(tourPlaybackQueueProvider.notifier).enqueue(
    candidates: const [
      POI(
        id: 'poi-a',
        name: 'A 景點',
        lat: 25.0,
        lon: 121.5,
        tags: {},
        distanceM: 50,
        confidence: 'high',
      ),
    ],
  );

  await container.read(sessionProvider.notifier).stop();

  expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
  expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
});
```

Add imports:

```dart
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
```

- [ ] **Step 2: Run session test to verify failure**

Run:

```bash
cd flutter_app
flutter test test/unit/session_provider_test.dart
```

Expected: FAIL because `SessionNotifier.stop()` does not clear the queue.

- [ ] **Step 3: Clear queue on stop**

`SessionNotifier` currently receives only `LocationService` and `LocalDb`. Do not inject `Ref` into the class. Add an optional `Future<void> Function()? onStopCompleted` callback to `SessionNotifier`, pass it from the provider factory, and call it at the end of `stop()`:

```dart
SessionNotifier(this._location, this._db, {Future<void> Function()? onStopCompleted})
    : _onStopCompleted = onStopCompleted,
      super(const SessionState(status: SessionStatus.idle));

final Future<void> Function()? _onStopCompleted;
```

At the end of `stop()`:

```dart
await _onStopCompleted?.call();
```

Provider factory:

```dart
return SessionNotifier(
  ref.watch(locationServiceProvider),
  ref.watch(localDbProvider),
  onStopCompleted: () => ref.read(tourPlaybackQueueProvider.notifier).clear(),
);
```

- [ ] **Step 4: Run session test**

Run:

```bash
cd flutter_app
flutter test test/unit/session_provider_test.dart
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/session/providers/session_provider.dart flutter_app/test/unit/session_provider_test.dart
git commit -m "feat(flutter): clear tour queue when journey ends"
```

## Task 7: Full Verification and Review Notes

**Files:**
- Create or modify: `tasks/todo.md`

- [ ] **Step 1: Run targeted test suite**

Run:

```bash
cd flutter_app
flutter test test/unit/settings_provider_test.dart test/unit/tour_playback_queue_provider_test.dart test/unit/trigger_provider_test.dart test/unit/session_provider_test.dart test/widget/narration_sheet_test.dart
```

Expected: PASS.

- [ ] **Step 2: Run full Flutter verification**

Run:

```bash
cd flutter_app
flutter analyze
flutter test
```

Expected: analyzer has no issues and all tests pass.

- [ ] **Step 3: Inspect diff for accidental scope creep**

Run:

```bash
git diff --stat HEAD
git diff -- flutter_app/lib/features/narration/providers/tour_playback_queue_provider.dart
```

Expected: diff is limited to the files named in this plan. Queue provider contains queue orchestration only, not backend selection logic or route planning.

- [ ] **Step 4: Add review/results section**

Create or update `tasks/todo.md` with:

```markdown
## Review - Background Tour Playback

- Design: `docs/superpowers/specs/2026-06-11-background-tour-playback-design.md`
- Plan: `docs/superpowers/plans/2026-06-11-background-tour-playback.md`
- Verification:
  - `cd flutter_app && flutter analyze`
  - `cd flutter_app && flutter test`
- Manual Android verification still required on a device for locked-screen background playback, foreground service notifications, and media controls.
```

- [ ] **Step 5: Commit review notes**

```bash
git add tasks/todo.md
git commit -m "docs: record background tour playback review notes"
```

## Manual Android Acceptance Checklist

Run after code implementation on an Android device or emulator with foreground service behavior:

- [ ] Start a journey.
- [ ] Background or lock the app.
- [ ] Simulate or reach a POI trigger.
- [ ] Confirm narration starts in auto-play mode.
- [ ] Trigger a second POI while the first is playing.
- [ ] Confirm the second POI enters the queue without interrupting the first.
- [ ] Use skip to advance to the next item.
- [ ] Switch to notify-only mode.
- [ ] Confirm triggers create notifications without queueing.
- [ ] End the journey.
- [ ] Confirm location and audio foreground notifications stop.

## Self-Review

- Spec coverage: The plan covers playback settings, usage profiles, queue behavior, trigger routing, Android media-service setup, minimal queue UI, end-journey cleanup, automated tests, and manual Android verification.
- Scope: iOS, Android Auto, CarPlay, full queue management, and smart ranking are intentionally excluded.
- Placeholder scan: No placeholder tokens or open-ended implementation instructions remain.
- Type consistency: `TourPlaybackMode`, `TourUsageProfile`, `TourPlaybackQueueState`, `TourPlaybackQueueNotifier`, `tourPlaybackQueueProvider`, and `stopCurrent()` are defined before later tasks use them.
