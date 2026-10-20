import 'dart:typed_data';

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
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/db/local_db.dart';

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

class _NoopBackendClient implements BackendClient {
  const _NoopBackendClient();

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
  }) async* {}

  @override
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async* {}
}

class _FakeNarrationNotifier extends NarrationNotifier {
  _FakeNarrationNotifier(NarrationState initial)
      : super(
          const _NoopBackendClient(),
          FakeAudioPlayerService(),
          LocalDb.forTesting(NativeDatabase.memory()),
        ) {
    state = initial;
  }
}

class _FakeTourPlaybackQueueNotifier extends TourPlaybackQueueNotifier {
  _FakeTourPlaybackQueueNotifier(this.initialState);

  final TourPlaybackQueueState initialState;
  bool skipCalled = false;

  @override
  TourPlaybackQueueState build() => initialState;

  @override
  Future<void> skipToNext() async {
    skipCalled = true;
  }
}

void main() {
  testWidgets('mini bar shows next queued POI and skip advances queue',
      (tester) async {
    const narrationState = NarrationState(
      status: NarrationStatus.playing,
      currentPoi: _poiA,
    );
    final queueNotifier = _FakeTourPlaybackQueueNotifier(
      TourPlaybackQueueState(
        currentPoi: _poiA,
        queue: [
          QueuedPoi(poi: _poiB, queuedAt: DateTime(2026, 6, 11)),
        ],
      ),
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(narrationState),
          ),
          tourPlaybackQueueProvider.overrideWith(() => queueNotifier),
        ],
        child: const MaterialApp(home: Scaffold(body: NarrationMiniBar())),
      ),
    );

    expect(find.textContaining('下一段：B 景點'), findsOneWidget);

    await tester.tap(find.widgetWithIcon(IconButton, Icons.skip_next));
    await tester.pump();

    expect(queueNotifier.skipCalled, isTrue);
  });
}
