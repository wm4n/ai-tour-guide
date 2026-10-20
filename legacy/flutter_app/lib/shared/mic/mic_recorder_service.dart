import 'dart:io';
import 'dart:typed_data';
import 'package:path_provider/path_provider.dart';
import 'package:record/record.dart';

abstract class MicRecorderService {
  Future<void> startRecording();
  Future<Uint8List> stopAndGetBytes();
  Future<void> cancelRecording();
  Future<void> dispose();
}

class RealMicRecorderService implements MicRecorderService {
  final AudioRecorder _recorder = AudioRecorder();
  String? _recordingPath;

  @override
  Future<void> startRecording() async {
    final dir = await getTemporaryDirectory();
    _recordingPath = '${dir.path}/qa_recording_${DateTime.now().millisecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(encoder: AudioEncoder.wav),
      path: _recordingPath!,
    );
  }

  @override
  Future<Uint8List> stopAndGetBytes() async {
    if (_recordingPath == null) return Uint8List(0);
    final path = await _recorder.stop();
    if (path == null) return Uint8List(0);
    final file = File(path);
    if (!await file.exists()) return Uint8List(0);
    final bytes = await file.readAsBytes();
    await file.delete();
    _recordingPath = null;
    return bytes;
  }

  @override
  Future<void> cancelRecording() async {
    await _recorder.cancel();
    _recordingPath = null;
  }

  @override
  Future<void> dispose() async {
    await _recorder.dispose();
  }
}

class FakeMicRecorderService implements MicRecorderService {
  final Uint8List fakeAudio;
  bool _cancelled = false;

  FakeMicRecorderService({Uint8List? fakeAudio})
      : fakeAudio = fakeAudio ?? Uint8List(0);

  @override
  Future<void> startRecording() async {
    _cancelled = false;
  }

  @override
  Future<Uint8List> stopAndGetBytes() async {
    if (_cancelled) return Uint8List(0);
    return fakeAudio;
  }

  @override
  Future<void> cancelRecording() async {
    _cancelled = true;
  }

  @override
  Future<void> dispose() async {}
}
