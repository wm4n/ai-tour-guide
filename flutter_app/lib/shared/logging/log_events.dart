// flutter_app/lib/shared/logging/log_events.dart
class LogEvents {
  LogEvents._();

  // SESSION
  static const sessionStart = 'SESSION_START';
  static const sessionEnd = 'SESSION_END';

  // LOCATION
  static const locationUpdate = 'LOCATION_UPDATE';
  static const locationPermission = 'LOCATION_PERMISSION';

  // POI
  static const poiRequest = 'POI_REQUEST';
  static const poiCacheHit = 'POI_CACHE_HIT';
  static const poiLoaded = 'POI_LOADED';
  static const poiEmpty = 'POI_EMPTY';

  // NARRATION
  static const narrationTrigger = 'NARRATION_TRIGGER';
  static const narrationStart = 'NARRATION_START';
  static const narrationChunk = 'NARRATION_CHUNK';
  static const narrationComplete = 'NARRATION_COMPLETE';
  static const narrationSkip = 'NARRATION_SKIP';

  // QA
  static const qaStart = 'QA_START';
  static const qaSttDone = 'QA_STT_DONE';
  static const qaAnswerComplete = 'QA_ANSWER_COMPLETE';

  // ERROR
  static const apiError = 'API_ERROR';
  static const upstreamFail = 'UPSTREAM_FAIL';
}
