import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';

import 'audio_focus.dart';
import 'narration_player.dart';

class JustAudioNarrationPlayer implements NarrationPlayer {
  final AudioPlayer _player = AudioPlayer();
  Completer<void>? _done;

  @override
  Future<void> play(Uint8List wav, {required String title}) async {
    final file = File('${Directory.systemTemp.path}/buddy_narration.wav');
    await file.writeAsBytes(wav, flush: true);
    final done = _done = Completer<void>();
    final finished = _player.processingStateStream.listen((state) {
      if (state == ProcessingState.completed && !done.isCompleted) {
        done.complete();
      }
    });
    try {
      await _player.setFilePath(file.path);
      // play() 在暫停時就會回傳，所以不等它，改等「播完」或被 stop()
      unawaited(_player.play());
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
  Future<void> pause() => _player.pause();

  @override
  Future<void> resume() async {
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
