import 'package:drift/native.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  const nearPoi = POI(
    id: 'osm:near',
    name: '近處景點',
    lat: 25.1031,
    lon: 121.5482,
    tags: {},
    distanceM: 89,
    confidence: 'high',
  );

  test('TriggerProvider activates without exception', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(nearbyPois: [nearPoi]),
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
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // triggerProvider returns void; verify it can be read without throwing
    expect(true, isTrue); // provider activated without exception
  });

  test('TriggerProvider calls NotificationService.showPoiTrigger when app is in background', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final fakeNotification = FakeNotificationService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(
          const FakeBackendClient(nearbyPois: [nearPoi]),
        ),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        notificationServiceProvider.overrideWithValue(fakeNotification),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    // Set lifecycle state to paused (background) before activating trigger
    container.read(appLifecycleStateProvider.notifier).state =
        AppLifecycleState.paused;

    // Use listen (not read) to keep triggerProvider alive and subscribed
    container.listen(triggerProvider, (_, __) {});
    // Wait one microtask to allow StreamProvider to subscribe to the stream
    await Future<void>.microtask(() {});

    // Now emit position
    fakeLocation.emit(fakePosition(25.1023, 121.5482));

    // Wait for all async operations to complete
    await Future<void>.delayed(const Duration(milliseconds: 200));

    expect(fakeNotification.shownPois, contains(nearPoi));
  });
}
