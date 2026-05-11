sealed class NarrationEvent {
  const NarrationEvent();
}

class MetaEvent extends NarrationEvent {
  final String poiId;
  final bool cacheHit;
  final String confidence;
  final int estimatedDurationS;

  const MetaEvent({
    required this.poiId,
    required this.cacheHit,
    required this.confidence,
    this.estimatedDurationS = 0,
  });

  factory MetaEvent.fromJson(Map<String, dynamic> json) => MetaEvent(
        poiId: json['poi_id'] as String,
        cacheHit: json['cache_hit'] as bool,
        confidence: json['confidence'] as String,
        estimatedDurationS: (json['estimated_duration_s'] as num? ?? 0).toInt(),
      );
}

class TextEvent extends NarrationEvent {
  final String chunk;
  final int sentenceIdx;

  const TextEvent({required this.chunk, required this.sentenceIdx});

  factory TextEvent.fromJson(Map<String, dynamic> json) => TextEvent(
        chunk: json['chunk'] as String,
        sentenceIdx: (json['sentence_idx'] as num? ?? 0).toInt(),
      );
}

class AudioEvent extends NarrationEvent {
  final String chunkB64;
  final int sentenceIdx;

  const AudioEvent({required this.chunkB64, required this.sentenceIdx});

  factory AudioEvent.fromJson(Map<String, dynamic> json) => AudioEvent(
        chunkB64: json['chunk_b64'] as String,
        sentenceIdx: (json['sentence_idx'] as num? ?? 0).toInt(),
      );
}

class EndEvent extends NarrationEvent {
  const EndEvent();
}

class ErrorEvent extends NarrationEvent {
  final String code;
  final String message;
  final int retryAfterS;

  const ErrorEvent({
    required this.code,
    required this.message,
    this.retryAfterS = 0,
  });

  factory ErrorEvent.fromJson(Map<String, dynamic> json) => ErrorEvent(
        code: json['code'] as String,
        message: json['message'] as String,
        retryAfterS: (json['retry_after_s'] as num? ?? 0).toInt(),
      );
}
