import 'dart:async';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

const _poi = POI(
  id: 'osm:node:1',
  name: '無名景點',
  lat: 25.0,
  lon: 121.5,
  tags: {},
  distanceM: 80,
  confidence: 'low',
);

class _ScriptedBackendClient implements BackendClient {
  final List<List<NarrationEvent>> _scripts;
  int _callIndex = 0;

  _ScriptedBackendClient(this._scripts);

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async =>
      [];

  @override
  Stream<NarrationEvent> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    required String length,
    PreviousSelection? previousSelection,
    bool forceRegenerate = false,
  }) async* {
    final events = _scripts[_callIndex % _scripts.length];
    _callIndex++;
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

class _ManualAudioPlayerService implements AudioPlayerService {
  final Stream<bool> _playingStream;
  _ManualAudioPlayerService(this._playingStream);

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {}
  @override
  Future<void> reset() async {}
  @override
  Future<void> pause() async {}
  @override
  Future<void> resume() async {}
  @override
  Future<void> skip() async {}
  @override
  Future<void> duck() async {}
  @override
  Future<void> unduck() async {}
  @override
  Stream<bool> get isPlayingStream => _playingStream;
  @override
  Future<void> dispose() async {}
}

void main() {
  test('second consecutive no-data narration is suppressed (goes idle without playing)', () async {
    final noDataEvents = [
      const MetaEvent(
          poiId: 'osm:node:1',
          cacheHit: false,
          confidence: 'low',
          isNoData: true),
      const EndEvent(),
    ];

    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final client = _ScriptedBackendClient([noDataEvents, noDataEvents]);

    final container = ProviderContainer(
      overrides: [
        backendClientProvider.overrideWithValue(client),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    final notifier = container.read(narrationProvider.notifier);
    container.listen(narrationProvider, (_, __) {});

    // First no-data narration — plays normally (sets _lastWasNoData = true)
    await notifier.narrate(
        candidates: [_poi], persona: 'history_uncle', lang: 'zh-TW');
    await Future<void>.delayed(const Duration(milliseconds: 50));
    // No audio chunks since no-data path doesn't use AudioEvent in this test
    expect(fakeAudio.enqueuedChunks.length, 0);

    // Second no-data narration — should be suppressed
    await notifier.narrate(
        candidates: [_poi], persona: 'history_uncle', lang: 'zh-TW');
    await Future<void>.delayed(const Duration(milliseconds: 50));

    final state = container.read(narrationProvider);
    expect(state.status, NarrationStatus.idle);
    // Only 0 audio chunks — second narration was cancelled immediately
    expect(fakeAudio.enqueuedChunks.length, 0);
  });

  test('NarrationStatus stays playing after EndEvent until audio stops',
      () async {
    final playingController = StreamController<bool>.broadcast();
    final fakeAudio = _ManualAudioPlayerService(playingController.stream);
    final db = LocalDb.forTesting(NativeDatabase.memory());

    const events = [
      MetaEvent(
          poiId: 'osm:node:1',
          cacheHit: false,
          confidence: 'high',
          isNoData: false),
      EndEvent(),
    ];
    final client = _ScriptedBackendClient([events]);

    final container = ProviderContainer(
      overrides: [
        backendClientProvider.overrideWithValue(client),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
      ],
    );
    addTearDown(() {
      container.dispose();
      playingController.close();
    });
    addTearDown(db.close);

    container.listen(narrationProvider, (_, __) {});
    await container.read(narrationProvider.notifier).narrate(
          candidates: [_poi],
          persona: 'history_uncle',
          lang: 'zh-TW',
        );
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // After EndEvent, status should still be playing (audio not done yet)
    expect(container.read(narrationProvider).status, NarrationStatus.playing);

    // Now audio finishes
    playingController.add(false);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // Now idle
    expect(container.read(narrationProvider).status, NarrationStatus.idle);
  });
}
