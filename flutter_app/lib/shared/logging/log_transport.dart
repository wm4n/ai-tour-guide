// flutter_app/lib/shared/logging/log_transport.dart
import 'package:flutter_app/shared/logging/log_entry.dart';

abstract class LogTransport {
  void log(LogEntry entry);
}
