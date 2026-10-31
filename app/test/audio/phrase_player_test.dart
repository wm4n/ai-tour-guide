import 'dart:async';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:just_audio_platform_interface/just_audio_platform_interface.dart';
import 'package:plugin_platform_interface/plugin_platform_interface.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  const audioSession = MethodChannel('com.ryanheise.audio_session');
  late _FakeJustAudio platform;

  setUp(() {
    platform = _FakeJustAudio();
    JustAudioPlatform.instance = platform;
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(audioSession, (_) async => null);
  });

  tearDown(() {
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(audioSession, null);
  });

  test('every phrase keeps the audio focus until it has been heard', () async {
    final events = <String>[];
    final player = JustAudioPhrasePlayer(
      localFile: (phrase) => '/phrases/${phrase.number}.wav',
      releaseFocus: () async => events.add('released'),
    );

    for (final phrase in [FixedPhrase.startTour, FixedPhrase.hostUnreachable]) {
      final done = player.play(phrase);
      await _settle();
      events.add('heard ${phrase.number}');
      platform.current!.finish();
      await done;
    }
    // 第二句以後也一樣：還在念就放掉 focus 的話，iOS 會把它掐斷
    expect(events, [
      'heard ${FixedPhrase.startTour.number}',
      'released',
      'heard ${FixedPhrase.hostUnreachable.number}',
      'released',
    ]);
  });
}

Future<void> _settle() async {
  for (var i = 0; i < 20; i++) {
    await Future<void>.delayed(Duration.zero);
  }
}

class _FakeJustAudio extends JustAudioPlatform with MockPlatformInterfaceMixin {
  _FakePlayer? current;

  @override
  Future<AudioPlayerPlatform> init(InitRequest request) async =>
      current = _FakePlayer(request.id);

  @override
  Future<DisposePlayerResponse> disposePlayer(
    DisposePlayerRequest request,
  ) async {
    current?.stopPlaying();
    return DisposePlayerResponse();
  }

  @override
  Future<DisposeAllPlayersResponse> disposeAllPlayers(
    DisposeAllPlayersRequest request,
  ) async => DisposeAllPlayersResponse();
}

/// 原生播放器：載入就緒；play 一直到 [finish]（念完）或被停下才返回。
class _FakePlayer extends AudioPlayerPlatform {
  _FakePlayer(super.id);

  final _events = StreamController<PlaybackEventMessage>.broadcast();
  var _state = ProcessingStateMessage.idle;
  Completer<void>? _playing;

  void finish() {
    _broadcast(ProcessingStateMessage.completed);
    stopPlaying();
  }

  void stopPlaying() {
    _playing?.complete();
    _playing = null;
  }

  void _broadcast(ProcessingStateMessage state) {
    _state = state;
    _events.add(
      PlaybackEventMessage(
        processingState: state,
        updateTime: DateTime.now(),
        updatePosition: Duration.zero,
        bufferedPosition: Duration.zero,
        duration: const Duration(seconds: 2),
        icyMetadata: null,
        currentIndex: 0,
        androidAudioSessionId: null,
      ),
    );
  }

  @override
  Stream<PlaybackEventMessage> get playbackEventMessageStream => _events.stream;

  @override
  Future<LoadResponse> load(LoadRequest request) async {
    _broadcast(ProcessingStateMessage.ready);
    return LoadResponse(duration: const Duration(seconds: 2));
  }

  @override
  Future<PlayResponse> play(PlayRequest request) async {
    if (_playing == null && _state != ProcessingStateMessage.completed) {
      _playing = Completer<void>();
      await _playing!.future;
    }
    return PlayResponse();
  }

  @override
  Future<PauseResponse> pause(PauseRequest request) async {
    stopPlaying();
    return PauseResponse();
  }

  @override
  Future<SeekResponse> seek(SeekRequest request) async => SeekResponse();

  @override
  Future<SetVolumeResponse> setVolume(SetVolumeRequest request) async =>
      SetVolumeResponse();

  @override
  Future<SetSpeedResponse> setSpeed(SetSpeedRequest request) async =>
      SetSpeedResponse();

  @override
  Future<SetPitchResponse> setPitch(SetPitchRequest request) async =>
      SetPitchResponse();

  @override
  Future<SetSkipSilenceResponse> setSkipSilence(
    SetSkipSilenceRequest request,
  ) async => SetSkipSilenceResponse();

  @override
  Future<SetLoopModeResponse> setLoopMode(SetLoopModeRequest request) async =>
      SetLoopModeResponse();

  @override
  Future<SetShuffleModeResponse> setShuffleMode(
    SetShuffleModeRequest request,
  ) async => SetShuffleModeResponse();

  @override
  Future<SetShuffleOrderResponse> setShuffleOrder(
    SetShuffleOrderRequest request,
  ) async => SetShuffleOrderResponse();

  @override
  Future<SetAutomaticallyWaitsToMinimizeStallingResponse>
  setAutomaticallyWaitsToMinimizeStalling(
    SetAutomaticallyWaitsToMinimizeStallingRequest request,
  ) async => SetAutomaticallyWaitsToMinimizeStallingResponse();

  @override
  Future<SetCanUseNetworkResourcesForLiveStreamingWhilePausedResponse>
  setCanUseNetworkResourcesForLiveStreamingWhilePaused(
    SetCanUseNetworkResourcesForLiveStreamingWhilePausedRequest request,
  ) async => SetCanUseNetworkResourcesForLiveStreamingWhilePausedResponse();

  @override
  Future<SetPreferredPeakBitRateResponse> setPreferredPeakBitRate(
    SetPreferredPeakBitRateRequest request,
  ) async => SetPreferredPeakBitRateResponse();

  @override
  Future<SetAndroidAudioAttributesResponse> setAndroidAudioAttributes(
    SetAndroidAudioAttributesRequest request,
  ) async => SetAndroidAudioAttributesResponse();

  @override
  Future<DisposeResponse> dispose(DisposeRequest request) async {
    stopPlaying();
    return DisposeResponse();
  }
}
