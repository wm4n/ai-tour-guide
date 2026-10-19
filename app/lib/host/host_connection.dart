import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../audio/fixed_phrase.dart';
import '../audio/phrase_player.dart';
import 'host_client.dart';
import 'host_settings.dart';

/// 在 main() 以 SharedPreferences.getInstance() 的結果覆寫。
final sharedPreferencesProvider = Provider<SharedPreferences>(
  (ref) =>
      throw UnimplementedError('sharedPreferencesProvider must be overridden'),
);

/// repo 外的 `--dart-define-from-file` 可提供第一次啟動的預設值，之後以 App 內設定為準。
final settingsStoreProvider = Provider<SettingsStore>(
  (ref) => SettingsStore(
    ref.watch(sharedPreferencesProvider),
    defaults: const HostSettings(
      url: String.fromEnvironment('HOST_URL'),
      token: String.fromEnvironment('HOST_TOKEN'),
    ),
  ),
);

final hostClientProvider = Provider<HostClient>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return HostClient(client);
});

final pollIntervalProvider = Provider<Duration>(
  (ref) => const Duration(seconds: 5),
);

final settingsProvider = NotifierProvider<SettingsNotifier, HostSettings>(
  SettingsNotifier.new,
);

class SettingsNotifier extends Notifier<HostSettings> {
  @override
  HostSettings build() => ref.watch(settingsStoreProvider).load();

  Future<void> save(HostSettings settings) async {
    await ref.read(settingsStoreProvider).save(settings);
    state = settings;
  }
}

final connectionProvider =
    NotifierProvider<ConnectionNotifier, ConnectionStatus>(
      ConnectionNotifier.new,
    );

class ConnectionNotifier extends Notifier<ConnectionStatus> {
  int _generation = 0;

  @override
  ConnectionStatus build() {
    final timer = Timer.periodic(
      ref.watch(pollIntervalProvider),
      (_) => refresh(),
    );
    ref.onDispose(timer.cancel);
    ref.listen(settingsProvider, (_, _) => refresh());
    Future.microtask(refresh);
    return ref.read(settingsProvider).isConfigured
        ? ConnectionStatus.checking
        : ConnectionStatus.notConfigured;
  }

  Future<void> refresh() async {
    final generation = ++_generation;
    final settings = ref.read(settingsProvider);
    if (!settings.isConfigured) {
      state = ConnectionStatus.notConfigured;
      return;
    }
    final result = await ref.read(hostClientProvider).check(settings);
    // 較新的檢查已經送出，或 provider 已被銷毀時，丟棄這次結果。
    if (!ref.mounted || generation != _generation) return;
    state = result;
  }
}

final tourActiveProvider = NotifierProvider<TourActiveNotifier, bool>(
  TourActiveNotifier.new,
);

/// 出發／結束的雛形：目前只切換狀態，之後由旅程流程接手。
class TourActiveNotifier extends Notifier<bool> {
  @override
  bool build() => false;

  void toggle() {
    state = !state;
    if (state) {
      unawaited(ref.read(phrasePlayerProvider).play(FixedPhrase.startTour));
    }
  }
}
