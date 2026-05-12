import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/widgets/narration_mini_bar.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';

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
}

class _FakeNarrationNotifier extends StateNotifier<NarrationState>
    implements NarrationNotifier {
  _FakeNarrationNotifier(super.state);
  @override
  Future<void> narrate(POI poi) async {}
  @override
  Future<void> pause() async {}
  @override
  Future<void> resume() async {}
  @override
  Future<void> skip() async {}
}
