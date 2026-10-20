import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:just_audio/just_audio.dart';

import 'audio_focus.dart';
import 'fixed_phrase.dart';

abstract class PhrasePlayer {
  Future<void> play(FixedPhrase phrase);
  Future<void> dispose();
}

/// 音檔是被 git 忽略的本機資源；沒放進來時靜靜略過，App 其餘功能照常。
class JustAudioPhrasePlayer implements PhrasePlayer {
  final AudioPlayer _player = AudioPlayer();

  @override
  Future<void> play(FixedPhrase phrase) async {
    try {
      await _player.setAsset(phrase.assetPath);
      await _player.play();
      await releaseAudioFocus();
    } catch (error) {
      debugPrint('固定短句 ${phrase.number} 無法播放（音檔沒放進 assets/phrases/？）：$error');
    }
  }

  @override
  Future<void> dispose() => _player.dispose();
}

final phrasePlayerProvider = Provider<PhrasePlayer>((ref) {
  final player = JustAudioPhrasePlayer();
  ref.onDispose(player.dispose);
  return player;
});
