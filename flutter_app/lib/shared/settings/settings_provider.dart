import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';

class AppSettingsNotifier extends Notifier<AppSettings> {
  static const _keyDisplacement = 'skip_displacement_m';
  static const _keyCountdown = 'countdown_seconds';

  @override
  AppSettings build() {
    _load();
    return const AppSettings();
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    state = AppSettings(
      skipDisplacementM: prefs.getDouble(_keyDisplacement) ?? 1500.0,
      countdownSeconds: prefs.getInt(_keyCountdown) ?? 90,
    );
  }

  Future<void> setSkipDisplacement(double meters) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble(_keyDisplacement, meters);
    state = state.copyWith(skipDisplacementM: meters);
  }

  Future<void> setCountdownSeconds(int seconds) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setInt(_keyCountdown, seconds);
    state = state.copyWith(countdownSeconds: seconds);
  }
}

final appSettingsProvider = NotifierProvider<AppSettingsNotifier, AppSettings>(
  AppSettingsNotifier.new,
);
