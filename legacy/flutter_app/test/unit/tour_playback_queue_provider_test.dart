import 'dart:typed_data';

import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
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

const _farPoi = POI(
  id: 'poi-far',
  name: '遠方景點',
  lat: 25.004,
  lon: 121.5,
  tags: {},
  distanceM: 450,
  confidence: 'high',
);

class _SettingsNotifier extends AppSettingsNotifier {
  _SettingsNotifier(this._settings);

  final AppSettings _settings;

  @override
  AppSettings build() => _settings;
}

class _Client implements BackendClient {
  int narrateCalls = 0;
  final List<String> narratedPoiIds = [];

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async =>
      const [];

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
    narratedPoiIds.add(candidates.first.id);
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
  DateTime Function()? now,
  _Client? client,
}) {
  final db = LocalDb.forTesting(NativeDatabase.memory());
  final fakeLocation = FakeLocationService();
  fakeLocation.emit(fakePosition(25.0, 121.5));

  final container = ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(client ?? _Client()),
      audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
      localDbProvider.overrideWithValue(db),
      locationServiceProvider.overrideWithValue(fakeLocation),
      appSettingsProvider.overrideWith(() => _SettingsNotifier(settings)),
      if (now != null)
        tourPlaybackClockProvider.overrideWithValue(now),
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
    expect(state.nextPoi?.id, 'poi-b');
    expect(state.queuedCount, 1);
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

  test('skip advances to the next valid queued POI', () async {
    final client = _Client();
    final container = _container(client: client);
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiB]);
    await container.read(tourPlaybackQueueProvider.notifier).skipToNext();
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(container.read(tourPlaybackQueueProvider).currentPoi?.id, 'poi-b');
    expect(client.narratedPoiIds, ['poi-a', 'poi-b']);
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

  test('items older than ten minutes are dropped before playback', () async {
    var now = DateTime(2026, 6, 11, 12);
    final container = _container(now: () => now);
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiB]);
    now = now.add(const Duration(minutes: 11));
    await container.read(tourPlaybackQueueProvider.notifier).skipToNext();

    expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
    expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
  });

  test('portable profile drops queued items farther than 250m', () async {
    final container = _container();
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_farPoi]);
    await container.read(tourPlaybackQueueProvider.notifier).skipToNext();

    expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
  });

  test('car profile allows queued items within 800m', () async {
    final container = _container(
      settings: const AppSettings(tourUsageProfile: TourUsageProfile.car),
    );
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA]);
    await Future<void>.delayed(const Duration(milliseconds: 50));
    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_farPoi]);
    await container.read(tourPlaybackQueueProvider.notifier).skipToNext();
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(container.read(tourPlaybackQueueProvider).currentPoi?.id, 'poi-far');
  });

  test('backend skip advances beyond the skipped queue item', () async {
    final client = _ClientWithEvents(
      firstEvents: const [
        MetaEvent(
          poiId: 'poi-a',
          poiName: 'A 景點',
          cacheHit: false,
          confidence: 'high',
        ),
        EndEvent(),
      ],
      subsequentEvents: const [SkipEvent()],
    );
    final container = _container(client: client);
    container.listen(narrationProvider, (_, __) {});
    container.listen(tourPlaybackQueueProvider, (_, __) {});

    await container
        .read(tourPlaybackQueueProvider.notifier)
        .enqueue(candidates: const [_poiA, _poiB]);
    await Future<void>.delayed(const Duration(milliseconds: 100));

    expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
    expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
    expect(client.narratedPoiIds, ['poi-a', 'poi-b']);
  });
}

class _ClientWithEvents extends _Client {
  _ClientWithEvents({
    required this.firstEvents,
    required this.subsequentEvents,
  });

  final List<NarrationEvent> firstEvents;
  final List<NarrationEvent> subsequentEvents;

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
    narratedPoiIds.add(candidates.first.id);
    final events = narrateCalls == 1 ? firstEvents : subsequentEvents;
    for (final event in events) {
      yield event;
    }
  }
}
