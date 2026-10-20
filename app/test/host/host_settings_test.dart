import 'package:buddy_tour/host/host_settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('empty store → empty settings', () async {
    SharedPreferences.setMockInitialValues({});
    final store = SettingsStore(await SharedPreferences.getInstance());

    final loaded = store.load();

    expect(loaded.url, '');
    expect(loaded.token, '');
    expect(loaded.isConfigured, isFalse);
  });

  test('save then load round-trips', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();

    await SettingsStore(
      prefs,
    ).save(const HostSettings(url: 'http://h:1', token: 't'));
    final loaded = SettingsStore(prefs).load();

    expect(loaded.url, 'http://h:1');
    expect(loaded.token, 't');
    expect(loaded.isConfigured, isTrue);
  });

  test('build-time default url is used only when nothing is stored', () async {
    SharedPreferences.setMockInitialValues({});
    final prefs = await SharedPreferences.getInstance();
    final store = SettingsStore(
      prefs,
      defaults: const HostSettings(url: 'http://d:1', token: 'dt'),
    );

    expect(store.load().url, 'http://d:1');

    await store.save(const HostSettings(url: 'http://mine:2', token: ''));

    expect(store.load().url, 'http://mine:2');
    expect(store.load().token, '');
  });
}
