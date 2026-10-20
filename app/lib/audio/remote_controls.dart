import 'dart:async';

enum RemoteCommand { play, pause }

/// 耳機與鎖定畫面的播放／暫停鍵。對應的是「暫停／恢復主動介紹」（設計文件第 13 節）。
abstract class RemoteControls {
  Stream<RemoteCommand> get commands;

  /// 讓系統（鎖定畫面、耳機）知道現在的狀態。
  void update({required bool tourActive, required bool paused, String? title});

  Future<void> dispose();
}
