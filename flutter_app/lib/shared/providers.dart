import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';

const _backendUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://localhost:8000',
);

const _apiKey = String.fromEnvironment('API_KEY', defaultValue: '');

final backendClientProvider = Provider<BackendClient>((ref) {
  return RealBackendClient(baseUrl: _backendUrl, apiKey: _apiKey);
});

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return RealNotificationService();
});

final appLifecycleStateProvider =
    StateProvider<AppLifecycleState>((ref) => AppLifecycleState.resumed);

final locationServiceProvider = Provider<LocationService>((ref) {
  return RealLocationService();
});

final localDbProvider = Provider<LocalDb>((ref) {
  final db = LocalDb();
  ref.onDispose(db.close);
  return db;
});

final audioPlayerServiceProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});

// 旁白 AudioPlayer 的別名（語意更清楚）
final narrationAudioPlayerProvider = audioPlayerServiceProvider;

// Q&A 專用 AudioPlayer（獨立實例，不影響旁白音量）
final qaAudioPlayerProvider = Provider<AudioPlayerService>((ref) {
  final service = RealAudioPlayerService();
  ref.onDispose(service.dispose);
  return service;
});

final micRecorderProvider = Provider<MicRecorderService>((ref) {
  final service = RealMicRecorderService();
  ref.onDispose(service.dispose);
  return service;
});
