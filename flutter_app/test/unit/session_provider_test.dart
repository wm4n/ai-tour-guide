import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_app/shared/db/local_db.dart';

void main() {
  ProviderContainer makeContainer({bool hasPermission = true}) {
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
  });
}
