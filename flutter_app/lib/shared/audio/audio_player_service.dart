import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:audio_service/audio_service.dart';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

abstract class AudioPlayerService {
  Future<void> enqueueBytes(Uint8List bytes);
  Future<void> setCurrentItem({
    required String id,
    required String title,
    String? subtitle,
  });
  void setNextHandler(Future<void> Function()? handler);
  Future<void> reset();
  Future<void> pause();
  Future<void> resume();
  Future<void> skip();
  Future<void> duck();    // 音量降至 50%
  Future<void> unduck();  // 音量恢復 100%
  Stream<bool> get isPlayingStream;
  Future<void> dispose();
}

class RealAudioPlayerService implements AudioPlayerService {
  RealAudioPlayerService({bool useMediaService = true})
      : _useMediaService = useMediaService;

  final bool _useMediaService;
  final AudioPlayer _player = AudioPlayer();
  final ConcatenatingAudioSource _playlist =
      ConcatenatingAudioSource(children: []);
  late final Directory _tempDir;
  TourAudioHandler? _handler;
  Future<void> Function()? _nextHandler;
  int _chunkIndex = 0;
  bool _initialized = false;
  bool _tempDirReady = false;

  Future<void> _init() async {
    if (_initialized) return;
    _tempDir = await getTemporaryDirectory();
    _tempDirReady = true;
    if (_useMediaService) {
      final handler = await AudioService.init(
        builder: () => TourAudioHandler(_player),
        config: const AudioServiceConfig(
          androidNotificationChannelId: 'ai_tour_guide.playback',
          androidNotificationChannelName: 'AI Tour Guide playback',
          androidNotificationOngoing: true,
        ),
      );
      _handler = handler;
      _handler?.setNextHandler(_nextHandler);
    }
    await _player.setAudioSource(_playlist);
    _initialized = true;
  }

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    await _init();
    final file = File('${_tempDir.path}/narration_${_chunkIndex++}.mp3');
    await file.writeAsBytes(bytes);
    final newIndex = _playlist.length;
    await _playlist.add(AudioSource.uri(Uri.file(file.path)));
    // After reset() → stop() + clear(), processingState becomes idle (not
    // completed), so we must seek explicitly for the first chunk to ensure
    // the player is positioned correctly after the cleared playlist state.
    if (_player.processingState == ProcessingState.completed || newIndex == 0) {
      await _player.seek(Duration.zero, index: newIndex);
      await _player.play();
    } else if (!_player.playing) {
      await _player.play();
    }
  }

  @override
  Future<void> setCurrentItem({
    required String id,
    required String title,
    String? subtitle,
  }) async {
    await _init();
    await _handler?.setMediaItem(
      id: id,
      title: title,
      subtitle: subtitle,
    );
  }

  @override
  void setNextHandler(Future<void> Function()? handler) {
    _nextHandler = handler;
    _handler?.setNextHandler(handler);
  }

  @override
  Future<void> reset() async {
    await _player.stop();
    await _playlist.clear();
    _chunkIndex = 0;
  }

  @override
  Future<void> pause() => _player.pause();

  @override
  Future<void> resume() => _player.play();

  @override
  Future<void> skip() async {
    if (_player.hasNext) {
      await _player.seekToNext();
    } else {
      await _player.stop();
    }
  }

  @override
  Future<void> duck() => _player.setVolume(0.5);

  @override
  Future<void> unduck() => _player.setVolume(1.0);

  @override
  Stream<bool> get isPlayingStream => _player.playerStateStream.map(
        (s) => s.playing && s.processingState != ProcessingState.completed,
      );

  @override
  Future<void> dispose() async {
    await _player.stop();
    await _player.dispose();
    if (!_tempDirReady) return;
    for (var i = 0; i < _chunkIndex; i++) {
      final f = File('${_tempDir.path}/narration_$i.mp3');
      if (await f.exists()) await f.delete();
    }
  }
}

class TourAudioHandler extends BaseAudioHandler with QueueHandler, SeekHandler {
  TourAudioHandler(this._player) {
    _player.playerStateStream.listen(_publishPlaybackState);
  }

  final AudioPlayer _player;
  Future<void> Function()? _onSkipToNext;

  void setNextHandler(Future<void> Function()? handler) {
    _onSkipToNext = handler;
  }

  Future<void> setMediaItem({
    required String id,
    required String title,
    String? subtitle,
  }) async {
    mediaItem.add(
      MediaItem(
        id: id,
        title: title,
        artist: subtitle ?? 'AI Tour Guide',
      ),
    );
  }

  @override
  Future<void> play() => _player.play();

  @override
  Future<void> pause() => _player.pause();

  @override
  Future<void> stop() => _player.stop();

  @override
  Future<void> skipToNext() async {
    final handler = _onSkipToNext;
    if (handler != null) {
      await handler();
      return;
    }
    if (_player.hasNext) {
      await _player.seekToNext();
    } else {
      await _player.stop();
    }
  }

  void _publishPlaybackState(PlayerState state) {
    playbackState.add(
      playbackState.value.copyWith(
        controls: [
          if (state.playing) MediaControl.pause else MediaControl.play,
          MediaControl.skipToNext,
        ],
        androidCompactActionIndices: const [0, 1],
        processingState: _mapProcessingState(state.processingState),
        playing: state.playing,
      ),
    );
  }

  AudioProcessingState _mapProcessingState(ProcessingState state) {
    switch (state) {
      case ProcessingState.idle:
        return AudioProcessingState.idle;
      case ProcessingState.loading:
        return AudioProcessingState.loading;
      case ProcessingState.buffering:
        return AudioProcessingState.buffering;
      case ProcessingState.ready:
        return AudioProcessingState.ready;
      case ProcessingState.completed:
        return AudioProcessingState.completed;
    }
  }
}

class FakeAudioPlayerService implements AudioPlayerService {
  final List<Uint8List> enqueuedChunks = [];
  String? currentItemId;
  String? currentItemTitle;
  String? currentItemSubtitle;
  bool isDucked = false;
  bool _isPlaying = false;
  Future<void> Function()? nextHandler;
  final _controller = StreamController<bool>.broadcast();

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    enqueuedChunks.add(bytes);
    _isPlaying = true;
    _controller.add(true);
  }

  @override
  Future<void> setCurrentItem({
    required String id,
    required String title,
    String? subtitle,
  }) async {
    currentItemId = id;
    currentItemTitle = title;
    currentItemSubtitle = subtitle;
  }

  @override
  void setNextHandler(Future<void> Function()? handler) {
    nextHandler = handler;
  }

  @override
  Future<void> reset() async {
    enqueuedChunks.clear();
    _isPlaying = false;
    _controller.add(false);
  }

  @override
  Future<void> pause() async {
    _isPlaying = false;
    _controller.add(false);
  }

  @override
  Future<void> resume() async {
    _isPlaying = true;
    _controller.add(true);
  }

  @override
  Future<void> skip() async {
    final handler = nextHandler;
    if (handler != null) {
      await handler();
      return;
    }
    _isPlaying = false;
    _controller.add(false);
  }

  @override
  Future<void> duck() async {
    isDucked = true;
  }

  @override
  Future<void> unduck() async {
    isDucked = false;
  }

  @override
  Stream<bool> get isPlayingStream async* {
    // Emit current state immediately on subscribe, then follow live events
    yield _isPlaying;
    yield* _controller.stream;
  }

  @override
  Future<void> dispose() async => _controller.close();
}
