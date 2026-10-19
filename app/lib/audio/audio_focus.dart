import 'package:audio_session/audio_session.dart';

/// 主動介紹與固定短句共用的 audio session 設定：播放時其他 App（音樂、Podcast）調小聲，
/// 播完要呼叫 [releaseAudioFocus] 才會恢復。
Future<void> configureAudioSession() async {
  final session = await AudioSession.instance;
  await session.configure(
    const AudioSessionConfiguration(
      avAudioSessionCategory: AVAudioSessionCategory.playback,
      avAudioSessionCategoryOptions: AVAudioSessionCategoryOptions.duckOthers,
      avAudioSessionMode: AVAudioSessionMode.spokenAudio,
      androidAudioAttributes: AndroidAudioAttributes(
        contentType: AndroidAudioContentType.speech,
        usage: AndroidAudioUsage.media,
      ),
      androidAudioFocusGainType: AndroidAudioFocusGainType.gainTransientMayDuck,
      androidWillPauseWhenDucked: false,
    ),
  );
}

/// just_audio 只會啟用 audio session，不會停用；不釋放的話其他 App 會一直被壓低音量。
/// 要帶 notifyOthersOnDeactivation，其他 App 才會收到通知把音量調回來。
Future<void> releaseAudioFocus() async {
  final session = await AudioSession.instance;
  await session.setActive(
    false,
    avAudioSessionSetActiveOptions:
        AVAudioSessionSetActiveOptions.notifyOthersOnDeactivation,
  );
}
