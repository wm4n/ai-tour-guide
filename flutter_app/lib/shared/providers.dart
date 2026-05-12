import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';

const _backendUrl = String.fromEnvironment(
  'BACKEND_URL',
  defaultValue: 'http://localhost:8000',
);

final backendClientProvider = Provider<BackendClient>((ref) {
  return RealBackendClient(baseUrl: _backendUrl);
});

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
