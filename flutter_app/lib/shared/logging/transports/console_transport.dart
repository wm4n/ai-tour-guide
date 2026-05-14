// flutter_app/lib/shared/logging/transports/console_transport.dart
import 'dart:developer' as dev;
import 'package:flutter/foundation.dart';
import 'package:flutter_app/shared/logging/log_entry.dart';
import 'package:flutter_app/shared/logging/log_transport.dart';

class ConsoleTransport implements LogTransport {
  static const _emoji = {
    LogLevel.debug: '🔵',
    LogLevel.info: '🟢',
    LogLevel.warn: '🟡',
    LogLevel.error: '🔴',
  };

  @override
  void log(LogEntry entry) {
    final message = kDebugMode ? formatDebug(entry) : formatRelease(entry);
    dev.log(message, name: 'AppLogger');
  }

  String formatDebug(LogEntry entry) {
    final emoji = _emoji[entry.level]!;
    final time = _hms(entry.timestamp);
    final paramsPart = _paramsStr(entry);
    final errorPart = entry.error != null ? '  ← ${entry.error}' : '';
    return '$emoji $time [${entry.event}]${paramsPart.isNotEmpty ? '  $paramsPart' : ''}$errorPart';
  }

  String formatRelease(LogEntry entry) {
    final ts = entry.timestamp.toUtc().toIso8601String();
    final level = entry.level.name.toUpperCase().padRight(5);
    final paramsPart = _paramsStr(entry);
    final errorPart = entry.error != null ? ' error="${entry.error}"' : '';
    return '$ts $level [${entry.event}]${paramsPart.isNotEmpty ? ' $paramsPart' : ''}$errorPart';
  }

  String _hms(DateTime dt) {
    return '${dt.hour.toString().padLeft(2, '0')}:'
        '${dt.minute.toString().padLeft(2, '0')}:'
        '${dt.second.toString().padLeft(2, '0')}';
  }

  String _paramsStr(LogEntry entry) {
    if (entry.params.isEmpty) return '';
    return entry.params.entries.map((e) => '${e.key}=${e.value}').join(' ');
  }
}
