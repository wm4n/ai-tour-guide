import 'package:audio_session/audio_session.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/app.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/transports/console_transport.dart';

void main() async {
  AppLogger.init(transports: [ConsoleTransport()]);
  WidgetsFlutterBinding.ensureInitialized();
  final session = await AudioSession.instance;
  await session.configure(const AudioSessionConfiguration.music());
  runApp(const ProviderScope(child: App()));
}
