import 'package:buddy_tour/qa/speech_recognizer.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';

void main() {
  test('uses the on-device recognizer when the device can do zh-TW', () async {
    final engine = FakeRecognizer(heard: '聽到的字');
    final listener = QuestionListener(engine);

    final session = await listener.start();

    expect(engine.attempts, [true]);
    expect(listener.mode, RecognitionMode.onDevice);
    expect(await session.finish(), '聽到的字');
  });

  test('falls back to online recognition when on-device is refused', () async {
    final engine = FakeRecognizer(onDeviceSupported: false);
    final listener = QuestionListener(engine);

    final session = await listener.start();

    expect(engine.attempts, [true, false]);
    expect(listener.mode, RecognitionMode.online);
    expect(await session.finish(), engine.heard);
  });

  test(
    'remembers that on-device does not work and goes straight online',
    () async {
      final engine = FakeRecognizer(onDeviceSupported: false);
      final listener = QuestionListener(engine);
      await listener.start();

      await listener.start();

      expect(engine.attempts, [true, false, false]); // 第二次不再白試一次本機
    },
  );

  test('remembers that on-device works', () async {
    final engine = FakeRecognizer();
    final listener = QuestionListener(engine);

    await listener.start();
    await listener.start();

    expect(engine.attempts, [true, true]);
    expect(listener.mode, RecognitionMode.onDevice);
  });

  test('other failures are not mistaken for "no on-device support"', () async {
    final engine = FakeRecognizer(error: SpeechPermissionDenied());
    final listener = QuestionListener(engine);

    await expectLater(listener.start(), throwsA(isA<SpeechPermissionDenied>()));

    expect(engine.attempts, [true]); // 沒權限不會再試線上，也不會記成「本機不行」
    expect(listener.mode, isNull);
  });

  test('a failing online fallback is reported', () async {
    final listener = QuestionListener(_OnlineBroken());

    await expectLater(listener.start(), throwsA(isA<RecognitionFailed>()));
  });
}

class _OnlineBroken implements SpeechRecognizer {
  @override
  Future<RecognitionSession> listen({required bool onDevice}) async {
    if (onDevice) throw OnDeviceUnavailable();
    throw RecognitionFailed('線上也不行');
  }
}
