import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/app.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/transports/console_transport.dart';

void main() {
  AppLogger.init(transports: [ConsoleTransport()]);
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const ProviderScope(child: App()));
}
