// flutter_app/lib/shared/logging/app_logger.dart
import 'package:flutter_app/shared/logging/log_entry.dart';
import 'package:flutter_app/shared/logging/log_transport.dart';

class AppLogger {
  AppLogger._();

  static final List<LogTransport> _transports = [];

  static void init({required List<LogTransport> transports}) {
    _transports
      ..clear()
      ..addAll(transports);
  }

  static void info(String event, [Map<String, dynamic> params = const {}]) =>
      _dispatch(LogLevel.info, event, params);

  static void debug(String event, [Map<String, dynamic> params = const {}]) =>
      _dispatch(LogLevel.debug, event, params);

  static void warn(String event, [Map<String, dynamic> params = const {}]) =>
      _dispatch(LogLevel.warn, event, params);

  static void error(
    String event, [
    Map<String, dynamic> params = const {},
    Object? error,
    StackTrace? stack,
  ]) =>
      _dispatch(LogLevel.error, event, params, error: error, stackTrace: stack);

  static void _dispatch(
    LogLevel level,
    String event,
    Map<String, dynamic> params, {
    Object? error,
    StackTrace? stackTrace,
  }) {
    final entry = LogEntry(
      level: level,
      event: event,
      params: params,
      timestamp: DateTime.now(),
      error: error,
      stackTrace: stackTrace,
    );
    for (final t in _transports) {
      t.log(entry);
    }
  }
}
