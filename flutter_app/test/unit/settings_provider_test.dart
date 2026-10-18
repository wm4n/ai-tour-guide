import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';

void main() {
  setUp(() {
    SharedPreferences.setMockInitialValues({});
  });

  test('AppSettings defaults are correct', () {
    const settings = AppSettings();
    expect(settings.skipDisplacementM, 1500.0);
    expect(settings.countdownSeconds, 90);
    expect(settings.tourPlaybackMode, TourPlaybackMode.autoPlay);
    expect(settings.tourUsageProfile, TourUsageProfile.portable);
  });

  test('setSkipDisplacement updates state and persists', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appSettingsProvider.notifier).setSkipDisplacement(2000.0);

    expect(container.read(appSettingsProvider).skipDisplacementM, 2000.0);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getDouble('skip_displacement_m'), 2000.0);
  });

  test('setCountdownSeconds updates state and persists', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container.read(appSettingsProvider.notifier).setCountdownSeconds(120);

    expect(container.read(appSettingsProvider).countdownSeconds, 120);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getInt('countdown_seconds'), 120);
  });

  test('loads persisted values on init', () async {
    SharedPreferences.setMockInitialValues({
      'skip_displacement_m': 3000.0,
      'countdown_seconds': 60,
      'tour_playback_mode': 'notifyOnly',
      'tour_usage_profile': 'car',
    });
    final container = ProviderContainer();
    addTearDown(container.dispose);

    container.listen(appSettingsProvider, (_, __) {});
    await Future<void>.delayed(const Duration(milliseconds: 50));

    final settings = container.read(appSettingsProvider);
    expect(settings.skipDisplacementM, 3000.0);
    expect(settings.countdownSeconds, 60);
    expect(settings.tourPlaybackMode, TourPlaybackMode.notifyOnly);
    expect(settings.tourUsageProfile, TourUsageProfile.car);
  });

  test('setTourPlaybackMode updates state and persists', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container
        .read(appSettingsProvider.notifier)
        .setTourPlaybackMode(TourPlaybackMode.notifyOnly);

    expect(
      container.read(appSettingsProvider).tourPlaybackMode,
      TourPlaybackMode.notifyOnly,
    );
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('tour_playback_mode'), 'notifyOnly');
  });

  test('setTourUsageProfile updates state and persists', () async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    addTearDown(container.dispose);

    await container
        .read(appSettingsProvider.notifier)
        .setTourUsageProfile(TourUsageProfile.car);

    expect(
      container.read(appSettingsProvider).tourUsageProfile,
      TourUsageProfile.car,
    );
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('tour_usage_profile'), 'car');
  });
}
