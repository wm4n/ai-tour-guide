// flutter_app/test/unit/app_logger_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

void main() {
  group('LogEvents', () {
    test('constants have correct string values', () {
      expect(LogEvents.sessionStart, 'SESSION_START');
      expect(LogEvents.poiLoaded, 'POI_LOADED');
      expect(LogEvents.narrationComplete, 'NARRATION_COMPLETE');
      expect(LogEvents.upstreamFail, 'UPSTREAM_FAIL');
    });
  });
}
