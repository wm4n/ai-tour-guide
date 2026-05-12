import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_app/shared/db/local_db.dart';

void main() {
  ProviderContainer _makeContainer({bool hasPermission = true}) {
    final fakeLocation = FakeLocationService(hasPermission: hasPermission);
    return ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        localDbProvider.overrideWithValue(
          LocalDb.forTesting(NativeDatabase.memory()),
        ),
      ],
    );
  }

  group('SessionProvider', () {
    test('initial status is idle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('start() transitions to active when permission granted', () async {
      final container = _makeContainer(hasPermission: true);
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      expect(container.read(sessionProvider).status, SessionStatus.active);
    });

    test('start() returns to idle when permission denied', () async {
      final container = _makeContainer(hasPermission: false);
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('stop() transitions back to idle', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      await container.read(sessionProvider.notifier).stop();
      expect(container.read(sessionProvider).status, SessionStatus.idle);
    });

    test('default persona is history_uncle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).persona, 'history_uncle');
    });
  });
}
