import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';

class AppSettingsNotifier extends Notifier<AppSettings> {
  static const _keyDisplacement = 'skip_displacement_m';
  static const _keyCountdown = 'countdown_seconds';
  static const _keyTourPlaybackMode = 'tour_playback_mode';
  static const _keyTourUsageProfile = 'tour_usage_profile';

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
      tourPlaybackMode: _parsePlaybackMode(
        prefs.getString(_keyTourPlaybackMode),
      ),
      tourUsageProfile: _parseUsageProfile(
        prefs.getString(_keyTourUsageProfile),
      ),
    );
  }

  TourPlaybackMode _parsePlaybackMode(String? value) {
    return TourPlaybackMode.values.firstWhere(
      (mode) => mode.name == value,
      orElse: () => TourPlaybackMode.autoPlay,
    );
  }

  TourUsageProfile _parseUsageProfile(String? value) {
    return TourUsageProfile.values.firstWhere(
      (profile) => profile.name == value,
      orElse: () => TourUsageProfile.portable,
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

  Future<void> setTourPlaybackMode(TourPlaybackMode mode) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTourPlaybackMode, mode.name);
    state = state.copyWith(tourPlaybackMode: mode);
  }

  Future<void> setTourUsageProfile(TourUsageProfile profile) async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_keyTourUsageProfile, profile.name);
    state = state.copyWith(tourUsageProfile: profile);
  }
}

final appSettingsProvider = NotifierProvider<AppSettingsNotifier, AppSettings>(
  AppSettingsNotifier.new,
);
