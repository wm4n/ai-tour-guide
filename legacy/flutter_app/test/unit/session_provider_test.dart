import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/tour_playback_queue_provider.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:geolocator/geolocator.dart';
import 'package:shared_preferences/shared_preferences.dart';

const _poi = POI(
  id: 'poi-a',
  name: 'A 景點',
  lat: 25.0,
  lon: 121.5,
  tags: {},
  distanceM: 50,
  confidence: 'high',
);

void main() {
  ProviderContainer makeContainer({bool hasPermission = true}) {
    final fakeLocation = FakeLocationService(hasPermission: hasPermission);
    return ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
        notificationServiceProvider.overrideWithValue(FakeNotificationService()),
        localDbProvider.overrideWithValue(
          LocalDb.forTesting(NativeDatabase.memory()),
        ),
      ],
    );
  }

  group('SessionProvider', () {
    test('initial status is idle', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('start() transitions to active when permission granted', () async {
      final container = makeContainer(hasPermission: true);
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      expect(container.read(sessionProvider).status, SessionStatus.active);
    });

    test('start() returns to idle when permission denied', () async {
      final container = makeContainer(hasPermission: false);
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('stop() transitions back to idle', () async {
      final container = makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      await container.read(sessionProvider.notifier).stop();
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('default persona is history_uncle', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).persona, 'history_uncle');
    });

    test('setPersona() updates persona when idle', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      container.read(sessionProvider.notifier).setPersona('story_brother');
      expect(container.read(sessionProvider).persona, 'story_brother');
    });

    test('setPersona() is no-op when not idle', () async {
      final container = makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      container.read(sessionProvider.notifier).setPersona('story_brother');
      expect(container.read(sessionProvider).persona, 'history_uncle');
    });

    test('setLang() updates lang when idle', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      container.read(sessionProvider.notifier).setLang('en');
      expect(container.read(sessionProvider).lang, 'en');
    });

    test('setLang() is no-op when not idle', () async {
      final container = makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      container.read(sessionProvider.notifier).setLang('en');
      expect(container.read(sessionProvider).lang, 'zh-TW');
    });

    test('default lang is zh-TW', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).lang, 'zh-TW');
    });

    test('stop() clears tour playback queue', () async {
      SharedPreferences.setMockInitialValues({});
      final fakeLocation = FakeLocationService();
      fakeLocation.emit(fakePosition(25.0, 121.5));
      final db = LocalDb.forTesting(NativeDatabase.memory());
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(
            const FakeBackendClient(
              scriptedEvents: [
                MetaEvent(
                  poiId: 'poi-a',
                  poiName: 'A 景點',
                  cacheHit: false,
                  confidence: 'high',
                ),
              ],
            ),
          ),
          audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
          locationServiceProvider.overrideWithValue(fakeLocation),
          notificationServiceProvider.overrideWithValue(
            FakeNotificationService(),
          ),
          localDbProvider.overrideWithValue(db),
        ],
      );
      addTearDown(container.dispose);
      addTearDown(db.close);

      container.listen(tourPlaybackQueueProvider, (_, __) {});
      await container.read(sessionProvider.notifier).start();
      await container
          .read(tourPlaybackQueueProvider.notifier)
          .enqueue(candidates: const [_poi]);

      await container.read(sessionProvider.notifier).stop();

      expect(container.read(tourPlaybackQueueProvider).currentPoi, isNull);
      expect(container.read(tourPlaybackQueueProvider).queuedCount, 0);
    });

    test('while-in-use permission records background location guidance',
        () async {
      final db = LocalDb.forTesting(NativeDatabase.memory());
      final container = ProviderContainer(
        overrides: [
          locationServiceProvider.overrideWithValue(
            FakeLocationService(
              permissionStatus: LocationPermission.whileInUse,
            ),
          ),
          notificationServiceProvider.overrideWithValue(
            FakeNotificationService(),
          ),
          localDbProvider.overrideWithValue(db),
        ],
      );
      addTearDown(container.dispose);
      addTearDown(db.close);

      await container.read(sessionProvider.notifier).start();

      expect(
        container.read(sessionProvider).permissionGuidance,
        contains(SessionPermissionGuidance.backgroundLocationRecommended),
      );
    });

    test('missing notification permission records visibility guidance',
        () async {
      final db = LocalDb.forTesting(NativeDatabase.memory());
      final container = ProviderContainer(
        overrides: [
          locationServiceProvider.overrideWithValue(
            FakeLocationService(
              permissionStatus: LocationPermission.always,
            ),
          ),
          notificationServiceProvider.overrideWithValue(
            FakeNotificationService(hasPermission: false),
          ),
          localDbProvider.overrideWithValue(db),
        ],
      );
      addTearDown(container.dispose);
      addTearDown(db.close);

      await container.read(sessionProvider.notifier).start();

      expect(
        container.read(sessionProvider).permissionGuidance,
        contains(SessionPermissionGuidance.notificationVisibilityLimited),
      );
    });
  });
}
