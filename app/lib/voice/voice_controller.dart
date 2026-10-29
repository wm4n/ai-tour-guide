import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../audio/fixed_phrase.dart';
import '../audio/narration_player.dart';
import '../host/host_connection.dart';
import '../tour/tour_controller.dart';
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

typedef CurrentVoice = ({String name, String displayName});

class VoiceState {
  const VoiceState({
    this.catalog,
    this.current,
    this.loading = false,
    this.previewing,
    this.error,
  });

  /// 最近一次從主機拿到的清單；連不上主機時是 null。
  final VoiceCatalog? catalog;

  /// 目前使用中的聲音。連不上主機時是最後一次看到的（存在手機裡），從沒連上過是 null。
  final CurrentVoice? current;
  final bool loading;

  /// 正在試聽的聲音名稱。
  final String? previewing;
  final String? error;

  VoiceState copyWith({
    Object? catalog = _keep,
    Object? current = _keep,
    bool? loading,
    Object? previewing = _keep,
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
    error: identical(error, _keep) ? this.error : error as String?,
  );
}

const Object _keep = Object();

/// 設定頁的聲音區：主機上的聲音清單與試聽（這張還不能切換）。
class VoiceController extends Notifier<VoiceState> {
  static const _nameKey = 'voice.current.name';
  static const _displayNameKey = 'voice.current.display_name';

  int _refreshes = 0;
  int _previews = 0;

  @override
  VoiceState build() => VoiceState(current: _remembered());

  CurrentVoice? _remembered() {
    final prefs = ref.read(sharedPreferencesProvider);
    final name = prefs.getString(_nameKey);
    if (name == null) return null;
    return (name: name, displayName: prefs.getString(_displayNameKey) ?? name);
  }

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
    var current = state.current;
    if (catalog != null) {
      current = (
        name: catalog.current,
        displayName: catalog.currentVoice?.displayName ?? catalog.current,
      );
      final prefs = ref.read(sharedPreferencesProvider);
      await prefs.setString(_nameKey, current.name);
      await prefs.setString(_displayNameKey, current.displayName);
      if (!ref.mounted || generation != _refreshes) return;
    }
    state = state.copyWith(catalog: catalog, current: current, loading: false);
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
