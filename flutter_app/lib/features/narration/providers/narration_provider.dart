import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

enum NarrationStatus { idle, loading, playing, paused, error }

class NarrationState {
  final NarrationStatus status;
  final POI? currentPoi;
  final String subtitle;
  final String scriptBuffer;
  final double progress;
  final String? confidence;
  final String? errorMessage;
  final bool lastEventWasSkip;

  const NarrationState({
    required this.status,
    this.currentPoi,
    this.subtitle = '',
    this.scriptBuffer = '',
    this.progress = 0,
    this.confidence,
    this.errorMessage,
    this.lastEventWasSkip = false,
  });

  NarrationState copyWith({
    NarrationStatus? status,
    POI? currentPoi,
    String? subtitle,
    String? scriptBuffer,
    double? progress,
    String? confidence,
    String? errorMessage,
    bool? lastEventWasSkip,
  }) =>
      NarrationState(
        status: status ?? this.status,
        currentPoi: currentPoi ?? this.currentPoi,
        subtitle: subtitle ?? this.subtitle,
        scriptBuffer: scriptBuffer ?? this.scriptBuffer,
        progress: progress ?? this.progress,
        confidence: confidence ?? this.confidence,
        errorMessage: errorMessage ?? this.errorMessage,
        lastEventWasSkip: lastEventWasSkip ?? this.lastEventWasSkip,
      );
}

class NarrationNotifier extends StateNotifier<NarrationState> {
  NarrationNotifier(this._client, this._audio, this._db)
      : super(const NarrationState(status: NarrationStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _audio;
  final LocalDb _db;
  StreamSubscription<NarrationEvent>? _sub;
  StreamSubscription<bool>? _audioSub;
  bool _sseStreamEnded = false;
  int _audioChunkCount = 0;
  String _currentPersona = 'history_uncle';
  String _currentLang = 'zh-TW';
  DateTime? _narrationStartedAt;
  List<POI> _candidates = [];
  bool _lastWasNoData = false;

  Future<void> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    PreviousSelection? previousSelection,
  }) async {
    _currentPersona = persona;
    _currentLang = lang;
    _candidates = candidates;
    _sseStreamEnded = false;
    _audioSub?.cancel();
    _audioSub = null;
    await _sub?.cancel();
    await _audio.reset();
    _audioChunkCount = 0;
    _narrationStartedAt = DateTime.now();
    AppLogger.info(LogEvents.narrationStart, {'candidate_count': candidates.length});
    state = const NarrationState(status: NarrationStatus.loading, scriptBuffer: '');

    _sub = _client
        .narrate(
          candidates: candidates,
          persona: persona,
          lang: lang,
          length: 'medium',
          previousSelection: previousSelection,
        )
        .listen(
          _handle,
          onError: (Object e, StackTrace st) {
            AppLogger.error(LogEvents.apiError, {
              'context': 'narration_stream',
            }, e, st);
            state = state.copyWith(
              status: NarrationStatus.error,
              errorMessage: e.toString(),
            );
          },
          onDone: () {
            if (state.status == NarrationStatus.loading) {
              AppLogger.warn(LogEvents.apiError, {'context': 'narration_stream_empty'});
            }
          },
        );
  }

  void _handle(NarrationEvent event) {
    switch (event) {
      case MetaEvent(:final poiId, :final poiName, :final confidence, :final isNoData):
        if (isNoData && _lastWasNoData) {
          _lastWasNoData = true;
          _audioSub?.cancel();
          _audioSub = null;
          _sseStreamEnded = false;
          _sub?.cancel();
          _sub = null;
          state = state.copyWith(
            status: NarrationStatus.idle,
            lastEventWasSkip: false,
          );
          return;
        }
        _lastWasNoData = isNoData;
        final selectedPoi = _candidates.firstWhere(
          (p) => p.id == poiId,
          orElse: () => _candidates.isNotEmpty
              ? _candidates.first
              : POI(
                  id: poiId,
                  name: poiName,
                  lat: 0,
                  lon: 0,
                  tags: {},
                  distanceM: 0,
                  confidence: confidence,
                ),
        );
        AppLogger.info(LogEvents.narrationStart, {'poi_id': poiId, 'poi_name': poiName});
        state = state.copyWith(
          status: NarrationStatus.playing,
          currentPoi: selectedPoi,
          confidence: confidence,
        );
      case TextEvent(:final chunk, :final sentenceIdx):
        AppLogger.debug(LogEvents.narrationChunk, {
          'poi_id': state.currentPoi?.id ?? '',
          'sentence_idx': sentenceIdx,
          'chunk': chunk,
          'type': 'text',
        });
        state = state.copyWith(
          subtitle: state.subtitle + chunk,
          scriptBuffer: state.scriptBuffer + chunk,
        );
      case AudioEvent(:final chunkB64):
        _audioChunkCount++;
        AppLogger.debug(LogEvents.narrationChunk, {
          'poi_id': state.currentPoi?.id ?? '',
          'chunk_index': _audioChunkCount,
        });
        final bytes = base64.decode(chunkB64);
        _audio.enqueueBytes(bytes);
        state = state.copyWith(
          progress: (_audioChunkCount * 0.1).clamp(0.0, 0.9),
        );
      case EndEvent():
        final durationMs = _narrationStartedAt != null
            ? DateTime.now().difference(_narrationStartedAt!).inMilliseconds
            : 0;
        final poi = state.currentPoi;
        AppLogger.info(LogEvents.narrationComplete, {
          'poi_id': poi?.id ?? '',
          'duration_ms': durationMs,
          'total_chars': state.subtitle.length,
        });
        _narrationStartedAt = null;
        if (poi != null) _recordNarration(poi);
        _sseStreamEnded = true;
        // Defer idle until audio playback finishes
        _audioSub?.cancel();
        _audioSub = _audio.isPlayingStream.listen((isPlaying) {
          if (!isPlaying && _sseStreamEnded && state.status != NarrationStatus.paused) {
            _audioSub?.cancel();
            _audioSub = null;
            _sseStreamEnded = false;
            state = state.copyWith(
              status: NarrationStatus.idle,
              progress: 1.0,
            );
          }
        });
      case ErrorEvent(:final message):
        state = state.copyWith(
          status: NarrationStatus.error,
          errorMessage: message,
        );
      case SkipEvent():
        AppLogger.info(LogEvents.narrationSkip, {'reason': 'poi_trivial'});
        state = state.copyWith(
          status: NarrationStatus.idle,
          lastEventWasSkip: true,
        );
    }
  }

  void _recordNarration(POI poi) {
    _db
        .recordNarration(
          sessionId: 1,
          poiId: poi.id,
          poiName: poi.name,
          poiLat: poi.lat,
          poiLon: poi.lon,
          persona: _currentPersona,
          lang: _currentLang,
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
    _audioSub?.cancel();
    _audioSub = null;
    _sseStreamEnded = false;
    AppLogger.warn(LogEvents.narrationSkip, {
      'poi_id': state.currentPoi?.id ?? '',
      'reason': 'user_skip',
    });
    await _sub?.cancel();
    await _audio.skip();
    state = state.copyWith(status: NarrationStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _audioSub?.cancel();
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
