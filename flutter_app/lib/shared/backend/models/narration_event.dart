sealed class NarrationEvent {
  const NarrationEvent();
}

class MetaEvent extends NarrationEvent {
  final String poiId;
  final bool cacheHit;
  final String confidence;

  const MetaEvent({
    required this.poiId,
    required this.cacheHit,
    required this.confidence,
  });
}

class TextEvent extends NarrationEvent {
  final String chunk;
  const TextEvent({required this.chunk});
}

class AudioEvent extends NarrationEvent {
  final String chunkB64;
  final int sentenceIdx;

  const AudioEvent({required this.chunkB64, required this.sentenceIdx});
}

class EndEvent extends NarrationEvent {
  final int totalDurationS;
  const EndEvent({required this.totalDurationS});
}

class ErrorEvent extends NarrationEvent {
  final String code;
  final String message;
  final int? retryAfterS;

  const ErrorEvent({
    required this.code,
    required this.message,
    this.retryAfterS,
  });
}
