import 'dart:async';
import 'dart:io';

import 'package:flutter/foundation.dart';
import 'package:just_audio/just_audio.dart';

import 'audio_focus.dart';
import 'narration_player.dart';

class JustAudioNarrationPlayer implements NarrationPlayer {
  /// [fileName]：暫存音檔的名字。介紹與問答各用一個播放器，檔名要分開才不會互相覆蓋。
  JustAudioNarrationPlayer({this.fileName = 'buddy_narration.wav'});

  final String fileName;
  final AudioPlayer _player = AudioPlayer();
  Completer<void>? _done;
  bool _paused = false;
  bool _stopped = false; // 這一次是被 stop() 打斷的
  bool _releaseOnStop = true; // 被 stop() 打斷時要不要釋放 audio focus
  int _plays = 0; // 第幾次播放；收尾時用來確認自己沒有被下一次取代

  @override
  Future<bool> play(
    Uint8List wav, {
    required String title,
    Duration start = Duration.zero,
    bool releaseFocus = true,
  }) async {
    // 一開始（寫檔之前）就把狀態立好：寫檔與載入的空檔 stop() 進來也要有效，
    // 不然那次打斷會被吞掉，介紹照樣播完
    final id = ++_plays;
    _paused = false;
    _stopped = false;
    _releaseOnStop = true;
    final done = _done = Completer<void>();
    final file = File('${Directory.systemTemp.path}/$fileName');
    final finished = _player.processingStateStream.listen((state) {
      if (state == ProcessingState.completed && !done.isCompleted) {
        done.complete();
      }
    });
    try {
      await file.writeAsBytes(wav, flush: true);
      if (!_stopped) {
        await _player.setFilePath(file.path);
        if (start > Duration.zero && !_stopped) await _player.seek(start);
        // 寫檔與載入的空檔使用者可能已按暫停：此時不開始播，等 resume()
        // play() 在暫停時就會回傳，所以不等它，改等「播完」或被 stop()
        if (!_paused && !_stopped) unawaited(_player.play());
      }
      await done.future;
      return !_stopped;
    } finally {
      await finished.cancel();
      await _player.stop();
      // 被下一次播放取代了、或打斷的人說先別釋放（接著還有聲音要播）時，不恢復其他 App 的音量
      if (releaseFocus && _plays == id && _releaseOnStop) {
        await releaseAudioFocus();
      }
      if (_plays == id) {
        _done = null;
        try {
          await file.delete();
        } on FileSystemException catch (error) {
          debugPrint('刪除暫存音檔失敗：$error');
        }
      }
    }
  }

  @override
  Future<void> release() => releaseAudioFocus();

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
  Duration get position => _player.position;

  @override
  Future<void> stop({bool releaseFocus = true}) async {
    _stopped = true;
    _releaseOnStop = releaseFocus;
    final done = _done;
    if (done != null && !done.isCompleted) done.complete();
    await _player.stop();
  }

  @override
  Future<void> dispose() => _player.dispose();
}
