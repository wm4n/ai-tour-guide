import 'dart:async';

import 'package:audio_service/audio_service.dart';

import 'remote_controls.dart';

/// 耳機與鎖定畫面的播放／暫停鍵，對應「暫停／恢復主動介紹」。
///
/// 一趟進行中就當作「播放中」（就算兩段之間是安靜的），這樣按一下暫停鍵就是暫停主動介紹，
/// 再按一下恢復——符合使用者的認知，而不是只在念稿的那幾十秒才有反應。
class TourAudioHandler extends BaseAudioHandler implements RemoteControls {
  final _commands = StreamController<RemoteCommand>.broadcast();

  @override
  Stream<RemoteCommand> get commands => _commands.stream;

  @override
  Future<void> play() async => _commands.add(RemoteCommand.play);

  @override
  Future<void> pause() async => _commands.add(RemoteCommand.pause);

  // 鎖定畫面的停止鍵與暫停同義：結束一趟只能在 App 內按「結束」。
  @override
  Future<void> stop() async => _commands.add(RemoteCommand.pause);

  @override
  void update({required bool tourActive, required bool paused, String? title}) {
    if (!tourActive) {
      playbackState.add(PlaybackState());
      return;
    }
    mediaItem.add(
      MediaItem(id: 'tour', title: title ?? '陪你走', album: 'Buddy Tour'),
    );
    playbackState.add(
      PlaybackState(
        controls: [paused ? MediaControl.play : MediaControl.pause],
        processingState: AudioProcessingState.ready,
        playing: !paused,
      ),
    );
  }

  @override
  Future<void> dispose() => _commands.close();
}
