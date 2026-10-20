import 'dart:typed_data';

/// 播放一段主動介紹。
abstract class NarrationPlayer {
  /// 播到結束（或被 [stop] 打斷）才完成。暫停期間不會完成。
  /// 播放期間其他 App 的聲音要調小，播完恢復；[releaseFocus] 為 false 時播完先不恢復，
  /// 連續播好幾段（例如一個答案的各段）時由呼叫端在最後一段之後呼叫 [release]，避免每段之間音樂跳回來。
  Future<void> play(
    Uint8List wav, {
    required String title,
    bool releaseFocus = true,
  });

  /// 釋放 audio session，讓其他 App 的聲音恢復。
  Future<void> release();

  Future<void> pause();

  Future<void> resume();

  Future<void> stop();

  Future<void> dispose();
}
