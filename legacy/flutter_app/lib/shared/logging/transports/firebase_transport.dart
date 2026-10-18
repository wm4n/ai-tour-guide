// flutter_app/lib/shared/logging/transports/firebase_transport.dart
import 'package:flutter_app/shared/logging/log_entry.dart';
import 'package:flutter_app/shared/logging/log_transport.dart';

class FirebaseTransport implements LogTransport {
  @override
  void log(LogEntry entry) {
    // Future: ERROR → FirebaseCrashlytics.instance.recordError(entry.error, entry.stackTrace)
    //         INFO  → FirebaseAnalytics.instance.logEvent(name: entry.event, parameters: entry.params)
  }
}
