import 'dart:async';
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
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

const _poi = POI(
  id: 'osm:node:1',
  name: '故宮',
  lat: 25.1023,
  lon: 121.5482,
  tags: {},
  distanceM: 89,
  confidence: 'high',
);

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
}
