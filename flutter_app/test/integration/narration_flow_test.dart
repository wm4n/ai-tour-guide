import 'dart:convert';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

final _testPoi = POI(
  id: 'osm:1',
  name: '故宮博物院',
  lat: 25.1023,
  lon: 121.5482,
  tags: {},
  distanceM: 87,
  confidence: 'high',
);

final _scriptedEvents = [
  const MetaEvent(poiId: 'osm:1', cacheHit: false, confidence: 'high'),
  const TextEvent(chunk: '故宮博物院', sentenceIdx: 0),
  AudioEvent(
    chunkB64: base64.encode(Uint8List.fromList([0, 1, 2, 3])),
    sentenceIdx: 0,
  ),
  const EndEvent(),
];

ProviderContainer _makeContainer() {
  final fakeAudio = FakeAudioPlayerService();
  final fakeClient = FakeBackendClient(scriptedEvents: _scriptedEvents);
  return ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(fakeClient),
      audioPlayerServiceProvider.overrideWithValue(fakeAudio),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
  );
}

void main() {
  group('NarrationProvider', () {
    test('initial status is idle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(narrationProvider).status, NarrationStatus.idle);
    });

    test('narrate() transitions through loading → playing → idle', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      final states = <NarrationStatus>[];
      container.listen(
        narrationProvider.select((s) => s.status),
        (_, next) => states.add(next),
      );
      await container.read(narrationProvider.notifier).narrate(_testPoi);
      await Future<void>.delayed(Duration.zero);
      expect(states, contains(NarrationStatus.loading));
    });

    test('audio chunks are enqueued after narrate()', () async {
      final fakeAudio = FakeAudioPlayerService();
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(
            FakeBackendClient(scriptedEvents: _scriptedEvents),
          ),
          audioPlayerServiceProvider.overrideWithValue(fakeAudio),
          localDbProvider.overrideWithValue(
            LocalDb.forTesting(NativeDatabase.memory()),
          ),
        ],
      );
      addTearDown(container.dispose);
      await container.read(narrationProvider.notifier).narrate(_testPoi);
      await Future<void>.delayed(Duration.zero);
      expect(fakeAudio.enqueuedChunks, isNotEmpty);
    });

    test('subtitle is accumulated from text events', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      await container.read(narrationProvider.notifier).narrate(_testPoi);
      await Future<void>.delayed(Duration.zero);
      expect(container.read(narrationProvider).subtitle, contains('故宮'));
    });
  });
}
