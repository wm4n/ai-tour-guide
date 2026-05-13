import 'dart:typed_data';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';

void main() {
  group('FakeMicRecorderService', () {
    test('stopAndGetBytes returns fakeAudio', () async {
      final fake = FakeMicRecorderService(
        fakeAudio: Uint8List.fromList([1, 2, 3, 4]),
      );
      await fake.startRecording();
      final bytes = await fake.stopAndGetBytes();
      expect(bytes, equals(Uint8List.fromList([1, 2, 3, 4])));
    });

    test('cancelRecording does not throw', () async {
      final fake = FakeMicRecorderService();
      await fake.startRecording();
      await fake.cancelRecording();
    });

    test('stopAndGetBytes after cancel returns empty bytes', () async {
      final fake = FakeMicRecorderService();
      await fake.startRecording();
      await fake.cancelRecording();
      final bytes = await fake.stopAndGetBytes();
      expect(bytes, isEmpty);
    });
  });
}
