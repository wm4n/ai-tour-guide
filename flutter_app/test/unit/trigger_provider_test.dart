import 'dart:async';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

const _poi = POI(
  id: 'osm:node:1',
  name: '故宮',
  lat: 25.1023,
  lon: 121.5482,
  tags: {},
  distanceM: 89,
  confidence: 'high',
);

class _FakeSettingsNotifier extends AppSettingsNotifier {
  final AppSettings _initial;
  _FakeSettingsNotifier(this._initial);
  @override
  AppSettings build() => _initial;
}

class _CountingBackendClient implements BackendClient {
  final List<POI> nearbyPois;
  final List<NarrationEvent> firstEvents;
  final List<NarrationEvent> subsequentEvents;
  int callCount = 0;

  _CountingBackendClient({
    required this.nearbyPois,
    required this.firstEvents,
    required this.subsequentEvents,
  });

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async =>
      nearbyPois;

  @override
  Stream<NarrationEvent> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    required String length,
    PreviousSelection? previousSelection,
    bool forceRegenerate = false,
  }) async* {
    callCount++;
    final events = callCount == 1 ? firstEvents : subsequentEvents;
    for (final e in events) {
      yield e;
    }
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

ProviderContainer _buildContainer({
  List<NarrationEvent> scriptedEvents = const [],
  AppLifecycleState lifecycle = AppLifecycleState.resumed,
}) {
  final fakeLocation = FakeLocationService();
  final fakeAudio = FakeAudioPlayerService();
  final db = LocalDb.forTesting(NativeDatabase.memory());

  final container = ProviderContainer(
    overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      backendClientProvider.overrideWithValue(
        FakeBackendClient(
          nearbyPois: const [_poi],
          scriptedEvents: scriptedEvents,
        ),
      ),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(db),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      appLifecycleStateProvider.overrideWith((ref) => lifecycle),
    ],
  );
  return container;
}

void main() {
  test('TriggerProvider starts with non-counting state', () async {
    final container = _buildContainer();
    addTearDown(container.dispose);

    container.listen(triggerProvider, (_, __) {});
    await Future<void>.delayed(const Duration(milliseconds: 50));

    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isFalse);
    expect(state.countdownRemaining, Duration.zero);
  });

  test('TriggerProvider fires narrate() when POIs load on first run', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          FakeBackendClient(
            nearbyPois: const [_poi],
            scriptedEvents: const [EndEvent()],
          ),
        ),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    // Emit POIs — should trigger narration immediately (first run)
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    final narState = container.read(narrationProvider);
    // After EndEvent, status should be idle (narration completed)
    expect(narState.status, NarrationStatus.idle);
  });

  test('skipCountdown() triggers narration immediately', () async {
    final container = _buildContainer(
      scriptedEvents: const [EndEvent()],
    );
    addTearDown(container.dispose);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    await Future<void>.delayed(const Duration(milliseconds: 50));

    // Call skipCountdown — should not throw
    container.read(triggerProvider.notifier).skipCountdown();
    await Future<void>.delayed(const Duration(milliseconds: 200));

    // Provider should not be in counting-down state after skip
    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isFalse);
  });

  test('SkipEvent sets isWaitingForDisplacement and clears countdown', () async {
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
    expect(state.isWaitingForDisplacement, isTrue);
    expect(state.isCountingDown, isFalse);
  });

  test('TriggerProvider skips narrate() when POIs unchanged and user did not move', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    // Same POI, same position → second countdown should not call narrate()
    const narrationEvents = [
      MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'high'),
      EndEvent(),
    ];
    final trackingClient = _CountingBackendClient(
      nearbyPois: const [_poi],
      firstEvents: narrationEvents,
      subsequentEvents: narrationEvents,
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

    // Emit position and let first narration fire
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    final firstCallCount = trackingClient.callCount;
    expect(firstCallCount, 1); // First trigger always fires

    // Wait for 1-second countdown to expire and check if second call is skipped
    await Future<void>.delayed(const Duration(seconds: 2));

    // No movement emitted — same position, same POIs → guard should skip
    expect(trackingClient.callCount, firstCallCount); // No second call
  });

  test('displacement exceeding threshold re-triggers narration', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final fakeClient = _CountingBackendClient(
      nearbyPois: const [_poi],
      firstEvents: const [SkipEvent()],
      subsequentEvents: const [EndEvent()],
    );

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(fakeClient),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(
            const AppSettings(skipDisplacementM: 100, countdownSeconds: 90),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    // Trigger first narration (will get SkipEvent)
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(container.read(triggerProvider).isWaitingForDisplacement, isTrue);

    // Emit origin position (first position after displacement watch starts)
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // Move > 100m
    fakeLocation.emit(fakePosition(25.1033, 121.5492)); // ~150m
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(container.read(triggerProvider).isWaitingForDisplacement, isFalse);
    expect(fakeClient.callCount, greaterThan(1));
  });
}
