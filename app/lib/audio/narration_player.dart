import 'dart:typed_data';

/// 播放一段主動介紹。
abstract class NarrationPlayer {
  /// 播到結束（或被 [stop] 打斷）才完成。暫停期間不會完成。
  /// 播放期間其他 App 的聲音要調小，播完恢復。
  Future<void> play(Uint8List wav, {required String title});

  Future<void> pause();

  Future<void> resume();

  Future<void> stop();

  Future<void> dispose();
}
