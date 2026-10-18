import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';

void main() {
  group('FakeAudioPlayerService duck/unduck', () {
    test('isDucked is false by default', () {
      final fake = FakeAudioPlayerService();
      expect(fake.isDucked, isFalse);
    });

    test('duck() sets isDucked to true', () async {
      final fake = FakeAudioPlayerService();
      await fake.duck();
      expect(fake.isDucked, isTrue);
    });

    test('unduck() sets isDucked to false', () async {
      final fake = FakeAudioPlayerService();
      await fake.duck();
      await fake.unduck();
      expect(fake.isDucked, isFalse);
    });
  });
}
