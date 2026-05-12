import 'dart:async';
import 'dart:io';
import 'dart:typed_data';
import 'package:just_audio/just_audio.dart';
import 'package:path_provider/path_provider.dart';

abstract class AudioPlayerService {
  Future<void> enqueueBytes(Uint8List bytes);
  Future<void> pause();
  Future<void> resume();
  Future<void> skip();
  Stream<bool> get isPlayingStream;
  Future<void> dispose();
}

class RealAudioPlayerService implements AudioPlayerService {
  final AudioPlayer _player = AudioPlayer();
  final ConcatenatingAudioSource _playlist =
      ConcatenatingAudioSource(children: []);
  late final Directory _tempDir;
  int _chunkIndex = 0;
  bool _initialized = false;

  Future<void> _init() async {
    if (_initialized) return;
    _tempDir = await getTemporaryDirectory();
    await _player.setAudioSource(_playlist);
    _initialized = true;
  }

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    await _init();
    final file = File('${_tempDir.path}/narration_${_chunkIndex++}.mp3');
    await file.writeAsBytes(bytes);
    await _playlist.add(AudioSource.uri(Uri.file(file.path)));
    if (!_player.playing) await _player.play();
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
  Stream<bool> get isPlayingStream => _player.playingStream;

  @override
  Future<void> dispose() async {
    await _player.stop();
    await _player.dispose();
    for (var i = 0; i < _chunkIndex; i++) {
      final f = File('${_tempDir.path}/narration_$i.mp3');
      if (await f.exists()) await f.delete();
    }
  }
}

class FakeAudioPlayerService implements AudioPlayerService {
  final List<Uint8List> enqueuedChunks = [];
  final _controller = StreamController<bool>.broadcast();

  @override
  Future<void> enqueueBytes(Uint8List bytes) async {
    enqueuedChunks.add(bytes);
    _controller.add(true);
  }

  @override
  Future<void> pause() async {
    _controller.add(false);
  }

  @override
  Future<void> resume() async {
    _controller.add(true);
  }

  @override
  Future<void> skip() async {
    _controller.add(false);
  }

  @override
  Stream<bool> get isPlayingStream => _controller.stream;

  @override
  Future<void> dispose() async => _controller.close();
}
