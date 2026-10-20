import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';

import 'audio_focus.dart';
import 'narration_player.dart';

class JustAudioNarrationPlayer implements NarrationPlayer {
  final AudioPlayer _player = AudioPlayer();
  Completer<void>? _done;
  bool _paused = false;

  @override
  Future<void> play(Uint8List wav, {required String title}) async {
    final file = File('${Directory.systemTemp.path}/buddy_narration.wav');
    await file.writeAsBytes(wav, flush: true);
    _paused = false;
    final done = _done = Completer<void>();
    final finished = _player.processingStateStream.listen((state) {
      if (state == ProcessingState.completed && !done.isCompleted) {
        done.complete();
      }
    });
    try {
      await _player.setFilePath(file.path);
      // 寫檔與載入的空檔使用者可能已按暫停：此時不開始播，等 resume()
      // play() 在暫停時就會回傳，所以不等它，改等「播完」或被 stop()
      if (!_paused) unawaited(_player.play());
      await done.future;
    } finally {
      await finished.cancel();
      await _player.stop();
      await releaseAudioFocus();
      _done = null;
      try {
        await file.delete();
      } on FileSystemException catch (error) {
        debugPrint('刪除暫存音檔失敗：$error');
      }
    }
  }

  @override
  Future<void> pause() async {
    _paused = true;
    await _player.pause();
    // 暫停是「想安靜」：其他 App 的音量要先恢復，繼續時 just_audio 會重新啟用 session
    await releaseAudioFocus();
  }

  @override
  Future<void> resume() async {
    _paused = false;
    if (_done != null) unawaited(_player.play());
  }

  @override
  Future<void> stop() async {
    final done = _done;
    if (done != null && !done.isCompleted) done.complete();
    await _player.stop();
  }

  @override
  Future<void> dispose() => _player.dispose();
}
