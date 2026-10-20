import 'package:audio_service/audio_service.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'audio/audio_focus.dart';
import 'audio/audio_service_remote_controls.dart';
import 'audio/just_audio_narration_player.dart';
import 'host/host_connection.dart';
import 'qa/compass_source.dart';
import 'qa/fixed_question_recognizer.dart';
import 'qa/photo_source.dart';
import 'qa/qa_controller.dart';
import 'tour/geolocator_location_source.dart';
import 'tour/tour_controller.dart';
import 'ui/home_screen.dart';

/// 模擬器沒有麥克風：`--dart-define=FAKE_QUESTION=…` 讓按住說話固定「聽到」這句話。
const _fakeQuestion = String.fromEnvironment('FAKE_QUESTION');

/// 模擬器沒有相機與指南針：`--dart-define=FAKE_PHOTO=true` 讓拍照提問固定「拍到」一張小圖、朝向西方。
const _fakePhoto = bool.fromEnvironment('FAKE_PHOTO');

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
        // 答案各段另用一個播放器與暫存檔，不和主動介紹互相覆蓋
        answerPlayerProvider.overrideWith((ref) {
          final player = JustAudioNarrationPlayer(fileName: 'buddy_answer.wav');
          ref.onDispose(player.dispose);
          return player;
        }),
        if (_fakePhoto) ...[
          photoSourceProvider.overrideWithValue(FixedPhotoSource()),
          compassSourceProvider.overrideWithValue(FixedCompassSource(270)),
        ],
        if (_fakeQuestion.isNotEmpty)
          speechRecognizerProvider.overrideWithValue(
            FixedQuestionRecognizer(_fakeQuestion),
          ),
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
