import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/widgets/narration_mini_bar.dart';
import 'package:flutter_app/features/narration/widgets/narration_sheet.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

final _testState = NarrationState(
  status: NarrationStatus.playing,
  currentPoi: POI(
    id: 'osm:1',
    name: '國立故宮博物院',
    lat: 25.1023,
    lon: 121.5482,
    tags: {},
    distanceM: 87,
    confidence: 'high',
  ),
  subtitle: '故宮博物院創建於 1925 年',
  progress: 0.4,
  confidence: 'high',
);

List<Override> _qaOverrides() => [
      backendClientProvider.overrideWithValue(const FakeBackendClient()),
      narrationAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
      qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
      micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
    ];

void main() {
  testWidgets('NarrationMiniBar shows POI name when playing', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(_testState),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationMiniBar()),
        ),
      ),
    );
    expect(find.text('國立故宮博物院'), findsOneWidget);
  });

  testWidgets('NarrationMiniBar is hidden when idle', (tester) async {
    const idleState = NarrationState(status: NarrationStatus.idle);
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(idleState),
          ),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationMiniBar()),
        ),
      ),
    );
    expect(find.text('國立故宮博物院'), findsNothing);
  });

  testWidgets('NarrationSheet shows rating bar for foodie POI', (tester) async {
    final foodiePoi = POI(
      id: 'gplace:001',
      name: '鼎泰豐',
      lat: 25.033,
      lon: 121.564,
      tags: const {},
      distanceM: 47,
      confidence: 'high',
      rating: 4.6,
      userRatingsTotal: 328,
      priceLevel: 2,
    );
    final state = NarrationState(
      status: NarrationStatus.playing,
      currentPoi: foodiePoi,
      subtitle: '美食推薦',
      progress: 0.5,
      confidence: 'high',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(state),
          ),
          ..._qaOverrides(),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationSheet()),
        ),
      ),
    );

    expect(find.textContaining('4.6'), findsOneWidget);
    expect(find.textContaining('328'), findsOneWidget);
    expect(find.textContaining('\$\$'), findsOneWidget);
  });

  testWidgets('NarrationSheet hides rating bar for non-foodie POI',
      (tester) async {
    final regularPoi = POI(
      id: 'osm:node:1',
      name: '故宮博物院',
      lat: 25.1023,
      lon: 121.5482,
      tags: const {},
      distanceM: 87,
      confidence: 'high',
    );
    final state = NarrationState(
      status: NarrationStatus.playing,
      currentPoi: regularPoi,
      subtitle: '故宮介紹',
      progress: 0.3,
      confidence: 'high',
    );

    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(state),
          ),
          ..._qaOverrides(),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationSheet()),
        ),
      ),
    );

    expect(find.byType(NarrationSheet), findsOneWidget);
    // rating star should NOT appear
    expect(find.textContaining('⭐'), findsNothing);
  });
}

class _FakeNarrationNotifier extends StateNotifier<NarrationState>
    implements NarrationNotifier {
  _FakeNarrationNotifier(super.state);
  @override
  Future<void> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    PreviousSelection? previousSelection,
  }) async {}
  @override
  Future<void> pause() async {}
  @override
  Future<void> resume() async {}
  @override
  Future<void> skip() async {}
}
