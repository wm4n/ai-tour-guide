import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

enum QaStatus { idle, recording, processing, answering, error }

class QaState {
  final QaStatus status;
  final String transcript;
  final String responseText;
  final String? errorMessage;

  const QaState({
    required this.status,
    this.transcript = '',
    this.responseText = '',
    this.errorMessage,
  });

  QaState copyWith({
    QaStatus? status,
    String? transcript,
    String? responseText,
    String? errorMessage,
  }) =>
      QaState(
        status: status ?? this.status,
        transcript: transcript ?? this.transcript,
        responseText: responseText ?? this.responseText,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

class QaNotifier extends StateNotifier<QaState> {
  QaNotifier(
    this._client,
    this._narrationAudio,
    this._qaAudio,
    this._mic,
  ) : super(const QaState(status: QaStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _narrationAudio;
  final AudioPlayerService _qaAudio;
  final MicRecorderService _mic;
  StreamSubscription<QaEvent>? _sub;
  DateTime? _recordingStartedAt;

  Future<void> startRecording() async {
    await _sub?.cancel();
    _sub = null;
    await _narrationAudio.duck();
    await _mic.startRecording();
    _recordingStartedAt = DateTime.now();
    state = state.copyWith(
      status: QaStatus.recording,
      transcript: '',
      responseText: '',
      errorMessage: null,
    );
  }

  Future<void> stopAndSend({
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async {
    final started = _recordingStartedAt;
    _recordingStartedAt = null;

    // guard: < 500ms → silent cancel
    if (started != null &&
        DateTime.now().difference(started).inMilliseconds < 500) {
      await cancelRecording();
      return;
    }

    final audioBytes = await _mic.stopAndGetBytes();
    state = state.copyWith(status: QaStatus.processing);

    _sub = _client
        .qa(
          audioBytes: audioBytes,
          persona: persona,
          lang: lang,
          currentPoiId: currentPoiId,
          narrationSoFar: narrationSoFar,
        )
        .listen(
          _handleEvent,
          onError: (Object e) async {
            await _narrationAudio.unduck();
            state = state.copyWith(
              status: QaStatus.error,
              errorMessage: e.toString(),
            );
          },
        );
  }

  void _handleEvent(QaEvent event) {
    switch (event) {
      case TranscriptQaEvent(:final text):
        state = state.copyWith(
          status: QaStatus.answering,
          transcript: '你說：$text',
        );
      case TextQaEvent(:final chunk):
        state = state.copyWith(responseText: state.responseText + chunk);
      case AudioQaEvent(:final chunkB64):
        _qaAudio.enqueueBytes(base64.decode(chunkB64));
      case EndQaEvent():
        _narrationAudio.unduck();
        state = state.copyWith(status: QaStatus.idle);
      case ErrorQaEvent(:final message):
        _narrationAudio.unduck();
        state = state.copyWith(
          status: QaStatus.error,
          errorMessage: message,
        );
    }
  }

  Future<void> cancelRecording() async {
    await _sub?.cancel();
    _sub = null;
    await _mic.cancelRecording();
    await _narrationAudio.unduck();
    state = const QaState(status: QaStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final qaProvider = StateNotifierProvider<QaNotifier, QaState>((ref) {
  return QaNotifier(
    ref.watch(backendClientProvider),
    ref.watch(narrationAudioPlayerProvider),
    ref.watch(qaAudioPlayerProvider),
    ref.watch(micRecorderProvider),
  );
});
