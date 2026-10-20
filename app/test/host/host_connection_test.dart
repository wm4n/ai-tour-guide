import 'package:buddy_tour/host/host_client.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/host/host_settings.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class FakeHostClient implements HostClient {
  ConnectionStatus next = ConnectionStatus.connected;
  int calls = 0;
  HostSettings? lastSettings;

  @override
  Future<ConnectionStatus> check(HostSettings settings) async {
    calls++;
    lastSettings = settings;
    return next;
  }
}

Future<(ProviderContainer, FakeHostClient)> makeContainer({
  Map<String, Object> stored = const {},
  Duration poll = const Duration(hours: 1),
}) async {
  SharedPreferences.setMockInitialValues(stored);
  final prefs = await SharedPreferences.getInstance();
  final fake = FakeHostClient();
  final container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      hostClientProvider.overrideWithValue(fake),
      pollIntervalProvider.overrideWithValue(poll),
    ],
  );
  addTearDown(container.dispose);
  return (container, fake);
}

void main() {
  test('not configured → state notConfigured, no network call', () async {
    final (container, fake) = await makeContainer();

    container.listen(connectionProvider, (_, _) {});
    await Future<void>.delayed(Duration.zero);

    expect(container.read(connectionProvider), ConnectionStatus.notConfigured);
    expect(fake.calls, 0);
  });

  test('configured → checks host and reports connected', () async {
    final (container, fake) = await makeContainer(
      stored: {'host.url': 'http://h:1', 'host.token': 't'},
    );

    container.listen(connectionProvider, (_, _) {});
    await Future<void>.delayed(Duration.zero);

    expect(container.read(connectionProvider), ConnectionStatus.connected);
    expect(fake.lastSettings!.token, 't');
  });

  test('saving new settings triggers a re-check', () async {
    final (container, fake) = await makeContainer();
    container.listen(connectionProvider, (_, _) {});
    await Future<void>.delayed(Duration.zero);
    fake.next = ConnectionStatus.unauthorized;

    await container
        .read(settingsProvider.notifier)
        .save(const HostSettings(url: 'http://h:1', token: 'bad'));
    await Future<void>.delayed(Duration.zero);

    expect(container.read(connectionProvider), ConnectionStatus.unauthorized);
    expect(container.read(settingsProvider).url, 'http://h:1');
  });

  test('polls periodically so a dropped host is noticed', () async {
    final (container, fake) = await makeContainer(
      stored: {'host.url': 'http://h:1'},
      poll: const Duration(milliseconds: 20),
    );
    container.listen(connectionProvider, (_, _) {});
    await Future<void>.delayed(Duration.zero);
    expect(container.read(connectionProvider), ConnectionStatus.connected);

    fake.next = ConnectionStatus.unreachable;
    await Future<void>.delayed(const Duration(milliseconds: 60));

    expect(container.read(connectionProvider), ConnectionStatus.unreachable);
    expect(fake.calls, greaterThan(1));
  });
}
