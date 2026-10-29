import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../audio/fixed_phrase.dart';
import '../audio/narration_player.dart';
import '../host/host_connection.dart';
import '../tour/tour_controller.dart';
import 'phrase_store.dart';
import 'voice_api.dart';

final voiceApiProvider = Provider<VoiceApi>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return HttpVoiceApi(client);
});

/// 試聽用的播放器：和主動介紹、答案各用各的，被打斷的介紹才接得回去。
final previewPlayerProvider = Provider<NarrationPlayer>(
  (ref) => throw UnimplementedError('previewPlayerProvider must be overridden'),
);

final voiceProvider = NotifierProvider<VoiceController, VoiceState>(
  VoiceController.new,
);

/// [key] 是聲音鍵，用來找手機裡的短句；不知道（主機清單上沒有這個聲音）時是 null。
typedef CurrentVoice = ({String name, String displayName, String? key});

class VoiceState {
  const VoiceState({
    this.catalog,
    this.current,
    this.loading = false,
    this.previewing,
    this.switching,
    this.error,
  });

  /// 最近一次從主機拿到的清單；連不上主機時是 null。
  final VoiceCatalog? catalog;

  /// 目前使用中的聲音。連不上主機時是最後一次看到的（存在手機裡），從沒連上過是 null。
  final CurrentVoice? current;
  final bool loading;

  /// 正在試聽的聲音名稱。
  final String? previewing;

  /// 正在換過去的聲音名稱（下載短句、等主機回應）。
  final String? switching;
  final String? error;

  VoiceState copyWith({
    Object? catalog = _keep,
    Object? current = _keep,
    bool? loading,
    Object? previewing = _keep,
    Object? switching = _keep,
    Object? error = _keep,
  }) => VoiceState(
    catalog: identical(catalog, _keep)
        ? this.catalog
        : catalog as VoiceCatalog?,
    current: identical(current, _keep)
        ? this.current
        : current as CurrentVoice?,
    loading: loading ?? this.loading,
    previewing: identical(previewing, _keep)
        ? this.previewing
        : previewing as String?,
    switching: identical(switching, _keep)
        ? this.switching
        : switching as String?,
    error: identical(error, _keep) ? this.error : error as String?,
  );
}

const Object _keep = Object();

/// 設定頁的聲音區：主機上的聲音清單、試聽與切換。
///
/// 目前聲音以主機為準；記在手機裡的只用在連不上主機時挑短句、顯示。
class VoiceController extends Notifier<VoiceState> {
  static const _namePref = 'voice.current.name';
  static const _displayNamePref = 'voice.current.display_name';
  static const _voiceKeyPref = 'voice.current.key';

  int _refreshes = 0;
  int _previews = 0;
  int _selections = 0;
  Future<void> _choosing = Future.value(); // 換聲音的請求照點選的順序一個一個送

  @override
  VoiceState build() => VoiceState(current: _remembered());

  CurrentVoice? _remembered() {
    final prefs = ref.read(sharedPreferencesProvider);
    final name = prefs.getString(_namePref);
    if (name == null) return null;
    return (
      name: name,
      displayName: prefs.getString(_displayNamePref) ?? name,
      key: prefs.getString(_voiceKeyPref),
    );
  }

  Future<void> _remember(CurrentVoice voice) async {
    final prefs = ref.read(sharedPreferencesProvider);
    await prefs.setString(_namePref, voice.name);
    await prefs.setString(_displayNamePref, voice.displayName);
    final key = voice.key;
    await (key == null
        ? prefs.remove(_voiceKeyPref)
        : prefs.setString(_voiceKeyPref, key));
  }

  static CurrentVoice _currentOf(VoiceCatalog catalog) => (
    name: catalog.current,
    displayName: catalog.currentVoice?.displayName ?? catalog.current,
    key: catalog.currentVoice?.key,
  );

  Future<void> refresh() async {
    final generation = ++_refreshes;
    state = state.copyWith(loading: true);
    VoiceCatalog? catalog;
    try {
      catalog = await ref
          .read(voiceApiProvider)
          .list(ref.read(settingsProvider));
    } on TourApiException catch (error) {
      debugPrint('讀取聲音清單失敗：$error');
    }
    if (!ref.mounted || generation != _refreshes) return;
    if (catalog == null) {
      state = state.copyWith(catalog: null, loading: false);
      return;
    }
    final current = _currentOf(catalog);
    await _remember(current);
    if (!ref.mounted || generation != _refreshes) return;
    state = state.copyWith(catalog: catalog, current: current, loading: false);
    // 跟上主機：手機裡沒有目前聲音的短句就補下載（連不上主機時才念得出新聲音）
    final voice = catalog.currentVoice;
    if (voice == null || !voice.phrasesReady) return;
    try {
      await _savePhrases(voice, () => ref.mounted);
    } on TourApiException catch (error) {
      debugPrint('下載 ${voice.name} 的短句失敗：$error');
    }
  }

  /// 換成這個聲音：先把它的固定短句全部存進手機，再請主機換；任何一步失敗就不換。
  ///
  /// 換的過程中可以再點別的聲音，以最後一次為準。
  Future<void> select(VoiceInfo voice) async {
    final generation = ++_selections;
    bool latest() => ref.mounted && generation == _selections;
    state = state.copyWith(switching: voice.name, error: null);
    try {
      if (!await _savePhrases(voice, latest) || !latest()) return;
      final settings = ref.read(settingsProvider);
      final api = ref.read(voiceApiProvider);
      // 照點選的順序送：先點的請求晚到，主機就會停在先點的那個聲音
      final sent = _choosing.then<String?>(
        (_) => latest() ? api.choose(settings, voice.name) : null,
      );
      _choosing = sent.then((_) {}, onError: (_) {});
      final chosen = await sent;
      if (chosen == null || !ref.mounted) return;
      // 主機已經換了：即使之後又點了別的，畫面也要和主機一致，直到下一個請求成功
      final catalog = VoiceCatalog(
        current: chosen,
        voices: state.catalog?.voices ?? [voice],
      );
      final current = _currentOf(catalog);
      await _remember(current);
      if (!ref.mounted) return;
      state = state.copyWith(
        current: current,
        catalog: state.catalog == null ? null : catalog,
      );
    } on TourApiException catch (error) {
      debugPrint('換成 ${voice.name} 失敗：$error');
      if (latest()) state = state.copyWith(error: _switchFailure(error));
    } on FileSystemException catch (error) {
      debugPrint('存 ${voice.name} 的短句失敗：$error');
      if (latest()) state = state.copyWith(error: '換聲音失敗：手機存不下這個聲音的短句');
    } finally {
      if (latest()) state = state.copyWith(switching: null);
    }
  }

  static String _switchFailure(TourApiException error) =>
      switch (error.statusCode) {
        404 => '換聲音失敗：主機上找不到這個聲音或它的短句',
        409 => '換聲音失敗：主機上這個聲音的短句還沒準備好',
        _ => '換聲音失敗：連不上主機',
      };

  /// 手機裡沒有這個聲音的短句就全部下載、一次存起來。[stillWanted] 變成 false 就放棄（回傳 false）。
  Future<bool> _savePhrases(
    VoiceInfo voice,
    bool Function() stillWanted,
  ) async {
    final store = ref.read(phraseStoreProvider);
    if (await store.has(voice.key)) return true;
    final settings = ref.read(settingsProvider);
    final api = ref.read(voiceApiProvider);
    final wavs = <FixedPhrase, Uint8List>{};
    for (final phrase in FixedPhrase.values) {
      wavs[phrase] = await api.phrase(settings, voice.name, phrase.number);
      if (!stillWanted()) return false;
    }
    await store.save(voice.key, wavs);
    return true;
  }

  /// 試聽某個聲音的 7 號短句（直接從主機下載來播，不存進手機）。
  ///
  /// 正在播的介紹視同被發問打斷：試聽完從那一句的開頭接著播。再按一次別的聲音就換成那個聲音。
  Future<void> preview(String name) async {
    final generation = ++_previews;
    final tour = ref.read(tourProvider.notifier);
    final player = ref.read(previewPlayerProvider);
    // 先占住再停前一段：前一段收尾放掉它的占用時，介紹才不會在兩段試聽之間被接回去
    tour.beginQuestion();
    try {
      state = state.copyWith(previewing: name, error: null);
      await player.stop();
      final wav = await ref
          .read(voiceApiProvider)
          .phrase(
            ref.read(settingsProvider),
            name,
            FixedPhrase.startTour.number,
          );
      if (generation != _previews) return; // 下載時又按了別的聲音
      await player.play(wav, title: '試聽');
    } on TourApiException catch (error) {
      debugPrint('試聽 $name 失敗：$error');
      if (ref.mounted && generation == _previews) {
        state = state.copyWith(
          error: error.statusCode == 404
              ? '試聽失敗：主機上這個聲音的短句還沒準備好'
              : '試聽失敗：連不上主機',
        );
      }
    } on Exception catch (error) {
      // 例如主機回了壞掉的 wav：播放器寫檔或載入失敗
      debugPrint('試聽 $name 無法播放：$error');
      if (ref.mounted && generation == _previews) {
        state = state.copyWith(error: '試聽失敗：這段聲音無法播放');
      }
    } finally {
      if (ref.mounted && generation == _previews) {
        state = state.copyWith(previewing: null);
      }
      tour.endQuestion();
    }
  }
}
