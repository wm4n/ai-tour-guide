// flutter_app/test/unit/app_logger_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/logging/log_events.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_entry.dart';
import 'package:flutter_app/shared/logging/log_transport.dart';

class _CaptureTransport implements LogTransport {
  final List<LogEntry> entries = [];
  @override
  void log(LogEntry entry) => entries.add(entry);
}

void main() {
  group('LogEvents', () {
    test('constants have correct string values', () {
      expect(LogEvents.sessionStart, 'SESSION_START');
      expect(LogEvents.poiLoaded, 'POI_LOADED');
      expect(LogEvents.narrationComplete, 'NARRATION_COMPLETE');
      expect(LogEvents.upstreamFail, 'UPSTREAM_FAIL');
    });
  });

  group('AppLogger', () {
    late _CaptureTransport t1;
    late _CaptureTransport t2;

    setUp(() {
      t1 = _CaptureTransport();
      t2 = _CaptureTransport();
      AppLogger.init(transports: [t1, t2]);
    });

    test('routes each entry to all registered transports', () {
      AppLogger.info('POI_LOADED', {'count': 3});
      expect(t1.entries.length, 1);
      expect(t2.entries.length, 1);
    });

    test('info() creates INFO level entry with correct event and params', () {
      AppLogger.info('POI_LOADED', {'count': 3});
      final entry = t1.entries.first;
      expect(entry.level, LogLevel.info);
      expect(entry.event, 'POI_LOADED');
      expect(entry.params['count'], 3);
    });

    test('debug() creates DEBUG level entry', () {
      AppLogger.debug('NARRATION_CHUNK');
      expect(t1.entries.first.level, LogLevel.debug);
    });

    test('warn() creates WARN level entry', () {
      AppLogger.warn('POI_EMPTY');
      expect(t1.entries.first.level, LogLevel.warn);
    });

    test('error() captures error object and stackTrace', () {
      final err = Exception('upstream 503');
      final st = StackTrace.current;
      AppLogger.error('UPSTREAM_FAIL', {'service': 'overpass'}, err, st);
      final entry = t1.entries.first;
      expect(entry.level, LogLevel.error);
      expect(entry.error, err);
      expect(entry.stackTrace, st);
    });

    test('init() replaces previous transports', () {
      final t3 = _CaptureTransport();
      AppLogger.init(transports: [t3]);
      AppLogger.info('SESSION_START');
      expect(t1.entries, isEmpty);
      expect(t3.entries.length, 1);
    });
  });
}
