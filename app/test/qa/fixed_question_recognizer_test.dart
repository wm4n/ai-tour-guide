import 'package:buddy_tour/qa/fixed_question_recognizer.dart';
import 'package:buddy_tour/qa/speech_recognizer.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('always hears the configured question, on either path', () async {
    final listener = QuestionListener(FixedQuestionRecognizer('這是什麼'));

    final session = await listener.start();

    expect(await session.finish(), '這是什麼');
    expect(listener.mode, RecognitionMode.onDevice);
  });
}
