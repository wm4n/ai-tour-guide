// flutter_app/test/unit/console_transport_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/logging/log_entry.dart';
import 'package:flutter_app/shared/logging/transports/console_transport.dart';

void main() {
  late ConsoleTransport transport;
  late LogEntry infoEntry;

  setUp(() {
    transport = ConsoleTransport();
    infoEntry = LogEntry(
      level: LogLevel.info,
      event: 'POI_LOADED',
      params: {'count': 5, 'lat': 37.785},
      timestamp: DateTime.utc(2026, 5, 14, 10, 23, 45),
    );
  });

  group('ConsoleTransport.formatDebug', () {
    test('includes green emoji for INFO', () {
      expect(transport.formatDebug(infoEntry), contains('🟢'));
    });

    test('includes event name in brackets', () {
      expect(transport.formatDebug(infoEntry), contains('[POI_LOADED]'));
    });

    test('includes params as key=value', () {
      final out = transport.formatDebug(infoEntry);
      expect(out, contains('count=5'));
      expect(out, contains('lat=37.785'));
    });

    test('includes error text when error is present', () {
      final entry = LogEntry(
        level: LogLevel.error,
        event: 'UPSTREAM_FAIL',
        params: {'service': 'overpass'},
        timestamp: DateTime.now(),
        error: Exception('503'),
      );
      expect(transport.formatDebug(entry), contains('503'));
      expect(transport.formatDebug(entry), contains('🔴'));
    });

    test('uses yellow emoji for WARN', () {
      final entry = LogEntry(
        level: LogLevel.warn,
        event: 'POI_EMPTY',
        params: {},
        timestamp: DateTime.now(),
      );
      expect(transport.formatDebug(entry), contains('🟡'));
    });

    test('uses blue emoji for DEBUG', () {
      final entry = LogEntry(
        level: LogLevel.debug,
        event: 'NARRATION_CHUNK',
        params: {},
        timestamp: DateTime.now(),
      );
      expect(transport.formatDebug(entry), contains('🔵'));
    });
  });

  group('ConsoleTransport.formatRelease', () {
    test('includes ISO timestamp', () {
      final out = transport.formatRelease(infoEntry);
      expect(out, contains('2026-05-14'));
    });

    test('includes level name', () {
      expect(transport.formatRelease(infoEntry), contains('INFO'));
    });

    test('includes event name in brackets', () {
      expect(transport.formatRelease(infoEntry), contains('[POI_LOADED]'));
    });

    test('includes params', () {
      final out = transport.formatRelease(infoEntry);
      expect(out, contains('count=5'));
    });
  });
}
