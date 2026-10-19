import 'package:audio_service/audio_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'audio/audio_focus.dart';
import 'audio/audio_service_remote_controls.dart';
import 'audio/just_audio_narration_player.dart';
import 'host/host_connection.dart';
import 'tour/geolocator_location_source.dart';
import 'tour/tour_controller.dart';
import 'ui/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final prefs = await SharedPreferences.getInstance();
  await configureAudioSession();
  final remote = await AudioService.init(
    builder: TourAudioHandler.new,
    config: const AudioServiceConfig(
      androidNotificationChannelId: 'buddy_tour.playback',
      androidNotificationChannelName: 'Buddy Tour',
    ),
  );
  runApp(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        remoteControlsProvider.overrideWithValue(remote),
        locationSourceProvider.overrideWithValue(GeolocatorLocationSource()),
        narrationPlayerProvider.overrideWith((ref) {
          final player = JustAudioNarrationPlayer();
          ref.onDispose(player.dispose);
          return player;
        }),
      ],
      child: const BuddyTourApp(),
    ),
  );
}

class BuddyTourApp extends StatelessWidget {
  const BuddyTourApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AI Buddy Tour',
      theme: ThemeData(colorSchemeSeed: Colors.teal, useMaterial3: true),
      home: const HomeScreen(),
    );
  }
}
