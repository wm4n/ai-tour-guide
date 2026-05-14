// flutter_app/lib/shared/logging/log_entry.dart
enum LogLevel { debug, info, warn, error }

class LogEntry {
  final LogLevel level;
  final String event;
  final Map<String, dynamic> params;
  final DateTime timestamp;
  final Object? error;
  final StackTrace? stackTrace;

  const LogEntry({
    required this.level,
    required this.event,
    this.params = const {},
    required this.timestamp,
    this.error,
    this.stackTrace,
  });
}
