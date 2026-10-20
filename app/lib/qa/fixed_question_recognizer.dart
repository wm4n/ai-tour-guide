import 'speech_recognizer.dart';

/// 開發用：不開麥克風，每次都「聽到」同一句話。模擬器沒有麥克風，端到端測試用
/// `--dart-define=FAKE_QUESTION=那間廟拜的是誰` 啟用（見 app/README.md）。
class FixedQuestionRecognizer implements SpeechRecognizer {
  FixedQuestionRecognizer(this.question);

  final String question;

  @override
  Future<RecognitionSession> listen({required bool onDevice}) async =>
      _FixedSession(question);
}

class _FixedSession implements RecognitionSession {
  _FixedSession(this._question);

  final String _question;

  @override
  Future<String> finish() async => _question;

  @override
  Future<void> cancel() async {}
}
