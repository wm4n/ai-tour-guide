import 'dart:async';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
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
      notificationServiceProvider.overrideWithValue(FakeNotificationService()),
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
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(
            nearbyPois: [_poi],
            scriptedEvents: [EndEvent()],
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

  test('SkipEvent restarts countdown instead of displacement-wait', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(
            nearbyPois: [_poi],
            scriptedEvents: [SkipEvent()],
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

    await container.read(sessionProvider.notifier).start();
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isTrue);
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
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
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

    await container.read(sessionProvider.notifier).start();
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

  test('countdown restarts when all nearby POIs have been played', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(
            nearbyPois: [_poi],
            scriptedEvents: [
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
    await container.read(sessionProvider.notifier).start();
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    await Future<void>.delayed(const Duration(seconds: 2));
    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isTrue,
        reason: 'countdown should restart when available.isEmpty');
  });

  test('queued narration advances after first selected POI completes', () async {
    const pois = [
      POI(id: 'osm:node:1', name: 'POI 1', lat: 25.10, lon: 121.54, tags: {}, distanceM: 50, confidence: 'high'),
      POI(id: 'osm:node:2', name: 'POI 2', lat: 25.10, lon: 121.54, tags: {}, distanceM: 60, confidence: 'high'),
      POI(id: 'osm:node:3', name: 'POI 3', lat: 25.10, lon: 121.54, tags: {}, distanceM: 70, confidence: 'high'),
      POI(id: 'osm:node:4', name: 'POI 4', lat: 25.10, lon: 121.54, tags: {}, distanceM: 80, confidence: 'high'),
      POI(id: 'osm:node:5', name: 'POI 5', lat: 25.10, lon: 121.54, tags: {}, distanceM: 90, confidence: 'high'),
    ];
    // The trigger submits all eligible candidates to the queue. Once node:1
    // completes, queue advancement starts node:2 without waiting for another
    // countdown cycle.
    const firstNarrationEvents = [
      MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'high'),
      EndEvent(),
    ];
    const subsequentEvents = [
      SkipEvent(),
    ];
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final trackingClient = _CountingBackendClient(
      nearbyPois: pois,
      firstEvents: firstNarrationEvents,
      subsequentEvents: subsequentEvents,
    );
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
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
    await container.read(sessionProvider.notifier).start();
    fakeLocation.emit(fakePosition(25.10, 121.54));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    expect(trackingClient.callCount, 5,
        reason: 'queue should advance through queued POIs as each item ends or skips');
  });

  test('dedup guard blocks second narrate() after backend SKIP with unchanged POIs', () async {
    // Scenario: backend returns SkipEvent (no playback) for a single candidate.
    // _lastCandidateIds is not cleared, so the next countdown sees the same
    // candidate set with no movement and dedup blocks duplicate delivery.
    const pois = [
      POI(id: 'osm:node:1', name: 'POI 1', lat: 25.10, lon: 121.54, tags: {}, distanceM: 50, confidence: 'high'),
    ];
    const skipEvent = [SkipEvent()];
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final trackingClient = _CountingBackendClient(
      nearbyPois: pois,
      firstEvents: skipEvent,
      subsequentEvents: skipEvent,
    );
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
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
    await container.read(sessionProvider.notifier).start();
    fakeLocation.emit(fakePosition(25.10, 121.54));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    expect(trackingClient.callCount, 1);
    await Future<void>.delayed(const Duration(seconds: 2));
    expect(trackingClient.callCount, 1, reason: 'dedup should prevent second narration after SKIP with unchanged POIs');
    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isTrue,
        reason: 'countdown should restart after dedup guard blocks');
  });

  test('background active journey queues candidates in auto-play mode', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(
            nearbyPois: [_poi],
            scriptedEvents: [
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
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(const AppSettings()),
        ),
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
          const FakeBackendClient(
            nearbyPois: [_poi],
            scriptedEvents: [],
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

  test('inactive journey does not queue notify or start narration', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final fakeNotification = FakeNotificationService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        notificationServiceProvider.overrideWithValue(fakeNotification),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(
            nearbyPois: [_poi],
            scriptedEvents: [
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
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
    expect(fakeNotification.shownPois, isEmpty);
    expect(container.read(narrationProvider).currentPoi, isNull);
  });
}
