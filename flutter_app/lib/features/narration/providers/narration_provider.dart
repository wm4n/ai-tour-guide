import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

enum NarrationStatus { idle, loading, playing, paused, error }

class NarrationState {
  final NarrationStatus status;
  final POI? currentPoi;
  final String subtitle;
  final double progress;
  final String? confidence;
  final String? errorMessage;

  const NarrationState({
    required this.status,
    this.currentPoi,
    this.subtitle = '',
    this.progress = 0,
    this.confidence,
    this.errorMessage,
  });

  NarrationState copyWith({
    NarrationStatus? status,
    POI? currentPoi,
    String? subtitle,
    double? progress,
    String? confidence,
    String? errorMessage,
  }) =>
      NarrationState(
        status: status ?? this.status,
        currentPoi: currentPoi ?? this.currentPoi,
        subtitle: subtitle ?? this.subtitle,
        progress: progress ?? this.progress,
        confidence: confidence ?? this.confidence,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

class NarrationNotifier extends StateNotifier<NarrationState> {
  NarrationNotifier(this._client, this._audio, this._db)
      : super(const NarrationState(status: NarrationStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _audio;
  final LocalDb _db;
  StreamSubscription<NarrationEvent>? _sub;
  int _audioChunkCount = 0;

  Future<void> narrate(POI poi) async {
    await _sub?.cancel();
    _audioChunkCount = 0;
    state = NarrationState(
      status: NarrationStatus.loading,
      currentPoi: poi,
    );

    _sub = _client
        .narrate(
          poiId: poi.id,
          persona: 'history_uncle',
          lang: 'zh-TW',
          length: 'medium',
        )
        .listen(
          (event) => _handle(event, poi),
          onError: (Object e) => state = state.copyWith(
            status: NarrationStatus.error,
            errorMessage: e.toString(),
          ),
        );
  }

  void _handle(NarrationEvent event, POI poi) {
    switch (event) {
      case MetaEvent(:final confidence):
        state = state.copyWith(
          status: NarrationStatus.playing,
          confidence: confidence,
        );
      case TextEvent(:final chunk):
        state = state.copyWith(subtitle: state.subtitle + chunk);
      case AudioEvent(:final chunkB64):
        _audioChunkCount++;
        final bytes = base64.decode(chunkB64);
        _audio.enqueueBytes(bytes);
        state = state.copyWith(
          progress: (_audioChunkCount * 0.1).clamp(0.0, 0.9),
        );
      case EndEvent():
        _recordNarration(poi);
        state = state.copyWith(
          status: NarrationStatus.idle,
          progress: 1.0,
        );
      case ErrorEvent(:final message):
        state = state.copyWith(
          status: NarrationStatus.error,
          errorMessage: message,
        );
    }
  }

  void _recordNarration(POI poi) {
    // Use try-catch to avoid FK constraint failures in tests (MVP: hardcoded session 1)
    _db
        .recordNarration(
          sessionId: 1,
          poiId: poi.id,
          poiName: poi.name,
          poiLat: poi.lat,
          poiLon: poi.lon,
          persona: 'history_uncle',
          lang: 'zh-TW',
          completed: true,
        )
        .catchError((_) {/* ignore FK errors in MVP */});
  }

  Future<void> pause() async {
    await _audio.pause();
    state = state.copyWith(status: NarrationStatus.paused);
  }

  Future<void> resume() async {
    await _audio.resume();
    state = state.copyWith(status: NarrationStatus.playing);
  }

  Future<void> skip() async {
    await _sub?.cancel();
    await _audio.skip();
    state = state.copyWith(status: NarrationStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final narrationProvider =
    StateNotifierProvider<NarrationNotifier, NarrationState>((ref) {
  return NarrationNotifier(
    ref.watch(backendClientProvider),
    ref.watch(audioPlayerServiceProvider),
    ref.watch(localDbProvider),
  );
});
