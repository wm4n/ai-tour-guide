import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';

import 'audio_focus.dart';
import 'fixed_phrase.dart';

abstract class PhrasePlayer {
  /// 念完才完成。[releaseFocus] 為 false 時念完先不恢復其他 App 的音量（後面緊接著還有答案要播）。
  Future<void> play(FixedPhrase phrase, {bool releaseFocus = true});

  /// 立刻停下正在念的短句（例如發問被取消）。
  Future<void> stop();

  Future<void> dispose();
}

/// 優先念手機裡「目前聲音」的短句（從主機下載的）；沒有才念 App 內建的。
/// 內建的音檔是被 git 忽略的本機資源；沒放進來時靜靜略過，App 其餘功能照常。
///
/// 只有一個播放器：短句一句一句排隊念。同時來兩句（例如剛念完「出發」就發問）若直接對同一個播放器
/// 重新載入，前一句會被打斷（Loading interrupted）。
class JustAudioPhrasePlayer implements PhrasePlayer {
  JustAudioPhrasePlayer({String? Function(FixedPhrase phrase)? localFile})
    : _localFile = localFile;

  /// 念的當下才問：換了聲音，下一句就念新聲音的。
  final String? Function(FixedPhrase phrase)? _localFile;
  final AudioPlayer _player = AudioPlayer();
  Future<void> _tail = Future.value();
  int _stops = 0; // stop() 的次數：排隊中的短句看到它變了就不念

  @override
  Future<void> play(FixedPhrase phrase, {bool releaseFocus = true}) {
    final stops = _stops;
    final next = _tail.then((_) async {
      if (stops != _stops) return; // 排隊的時候已經被 stop() 取消了
      try {
        final local = _localFile?.call(phrase);
        if (local != null) {
          await _player.setFilePath(local);
        } else {
          await _player.setAsset(phrase.assetPath);
        }
        if (stops != _stops) return; // 載入的時候被 stop() 取消了
        await _player.play();
        if (releaseFocus) await releaseAudioFocus();
      } catch (error) {
        debugPrint(
          '固定短句 ${phrase.number} 無法播放（手機裡沒有、也沒放進 assets/phrases/？）：$error',
        );
      }
    });
    _tail = next; // 內部已經接住所有錯誤，這一列不會因為某一句失敗而斷掉
    return next;
  }

  @override
  Future<void> stop() async {
    _stops++;
    await _player.stop();
  }

  @override
  Future<void> dispose() => _player.dispose();
}

final phrasePlayerProvider = Provider<PhrasePlayer>((ref) {
  final player = JustAudioPhrasePlayer();
  ref.onDispose(player.dispose);
  return player;
});
