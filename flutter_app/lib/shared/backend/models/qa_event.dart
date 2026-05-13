sealed class QaEvent {}

class TranscriptQaEvent extends QaEvent {
  final String text;
  TranscriptQaEvent({required this.text});
  factory TranscriptQaEvent.fromJson(Map<String, dynamic> j) =>
      TranscriptQaEvent(text: j['text'] as String);
}

class TextQaEvent extends QaEvent {
  final String chunk;
  final int sentenceIdx;
  TextQaEvent({required this.chunk, required this.sentenceIdx});
  factory TextQaEvent.fromJson(Map<String, dynamic> j) => TextQaEvent(
        chunk: j['chunk'] as String,
        sentenceIdx: j['sentence_idx'] as int,
      );
}

class AudioQaEvent extends QaEvent {
  final String chunkB64;
  final int sentenceIdx;
  AudioQaEvent({required this.chunkB64, required this.sentenceIdx});
  factory AudioQaEvent.fromJson(Map<String, dynamic> j) => AudioQaEvent(
        chunkB64: j['chunk_b64'] as String,
        sentenceIdx: j['sentence_idx'] as int,
      );
}

class EndQaEvent extends QaEvent {
  EndQaEvent();
}

class ErrorQaEvent extends QaEvent {
  final String code;
  final String message;
  ErrorQaEvent({required this.code, required this.message});
  factory ErrorQaEvent.fromJson(Map<String, dynamic> j) => ErrorQaEvent(
        code: j['code'] as String,
        message: j['message'] as String,
      );
}
