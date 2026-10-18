import 'package:shared_preferences/shared_preferences.dart';

class HostSettings {
  const HostSettings({required this.url, required this.token});

  final String url;
  final String token;

  bool get isConfigured => url.trim().isNotEmpty;
}

/// 主機位址與 token 存在裝置上（SharedPreferences），不寫進程式碼或 repo。
/// [defaults] 只在裝置上尚未存過任何設定時使用，來源是 repo 外的 --dart-define-from-file。
class SettingsStore {
  SettingsStore(
    this._prefs, {
    this.defaults = const HostSettings(url: '', token: ''),
  });

  static const urlKey = 'host.url';
  static const tokenKey = 'host.token';

  final SharedPreferences _prefs;
  final HostSettings defaults;

  HostSettings load() => HostSettings(
    url: _prefs.getString(urlKey) ?? defaults.url,
    token: _prefs.getString(tokenKey) ?? defaults.token,
  );

  Future<void> save(HostSettings settings) async {
    await _prefs.setString(urlKey, settings.url);
    await _prefs.setString(tokenKey, settings.token);
  }
}
