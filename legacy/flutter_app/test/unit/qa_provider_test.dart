import 'dart:typed_data';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

final _scriptedQaEvents = [
  TranscriptQaEvent(text: '這裡有多少文物？'),
  TextQaEvent(chunk: '故宮有約七十萬件文物。', sentenceIdx: 0),
  AudioQaEvent(chunkB64: 'AAAA', sentenceIdx: 0),
  EndQaEvent(),
];

ProviderContainer _makeContainer({
  List<QaEvent> qaEvents = const [],
}) {
  final fakeNarrationAudio = FakeAudioPlayerService();
  final fakeQaAudio = FakeAudioPlayerService();
  final fakeMic = FakeMicRecorderService(
    fakeAudio: Uint8List.fromList([1, 2, 3]),
  );
  final fakeClient = FakeBackendClient(scriptedQaEvents: qaEvents);

  return ProviderContainer(
    overrides: [
      backendClientProvider.overrideWithValue(fakeClient),
      narrationAudioPlayerProvider.overrideWithValue(fakeNarrationAudio),
      qaAudioPlayerProvider.overrideWithValue(fakeQaAudio),
      micRecorderProvider.overrideWithValue(fakeMic),
    ],
  );
}

void main() {
  group('QaNotifier', () {
    test('initial status is idle', () {
      final container = _makeContainer();
      addTearDown(container.dispose);
      expect(container.read(qaProvider).status, QaStatus.idle);
    });

    test('startRecording transitions to recording', () async {
      final container = _makeContainer();
      addTearDown(container.dispose);
      await container.read(qaProvider.notifier).startRecording();
      expect(container.read(qaProvider).status, QaStatus.recording);
    });

    test('startRecording ducks narration audio', () async {
      final fakeNarrationAudio = FakeAudioPlayerService();
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(const FakeBackendClient()),
          narrationAudioPlayerProvider.overrideWithValue(fakeNarrationAudio),
          qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
          micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
        ],
      );
      addTearDown(container.dispose);
      await container.read(qaProvider.notifier).startRecording();
      expect(fakeNarrationAudio.isDucked, isTrue);
    });

    test('stopAndSend transitions through processing → answering → idle', () async {
      final container = _makeContainer(qaEvents: _scriptedQaEvents);
      addTearDown(container.dispose);

      final statuses = <QaStatus>[];
      container.listen(
        qaProvider.select((s) => s.status),
        (_, next) => statuses.add(next),
      );

      await container.read(qaProvider.notifier).startRecording();
      // Wait > 500ms to pass the mistouch guard
      await Future<void>.delayed(const Duration(milliseconds: 600));
      await container.read(qaProvider.notifier).stopAndSend(
        persona: 'history_uncle',
        lang: 'zh-TW',
        currentPoiId: 'osm:1',
        narrationSoFar: '故宮是台灣最重要的博物館。',
      );
      await Future<void>.delayed(Duration.zero);

      expect(statuses, contains(QaStatus.processing));
    });

    test('stopAndSend sets transcript from TranscriptQaEvent', () async {
      final container = _makeContainer(qaEvents: _scriptedQaEvents);
      addTearDown(container.dispose);

      await container.read(qaProvider.notifier).startRecording();
      // Wait > 500ms to pass the mistouch guard
      await Future<void>.delayed(const Duration(milliseconds: 600));
      await container.read(qaProvider.notifier).stopAndSend(
        persona: 'history_uncle',
        lang: 'zh-TW',
      );
      await Future<void>.delayed(Duration.zero);

      expect(container.read(qaProvider).transcript, contains('這裡有多少文物'));
    });

    test('cancelRecording resets to idle and unduckes audio', () async {
      final fakeNarrationAudio = FakeAudioPlayerService();
      final container = ProviderContainer(
        overrides: [
          backendClientProvider.overrideWithValue(const FakeBackendClient()),
          narrationAudioPlayerProvider.overrideWithValue(fakeNarrationAudio),
          qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
          micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
        ],
      );
      addTearDown(container.dispose);

      await container.read(qaProvider.notifier).startRecording();
      await container.read(qaProvider.notifier).cancelRecording();
      expect(container.read(qaProvider).status, QaStatus.idle);
      expect(fakeNarrationAudio.isDucked, isFalse);
    });
  });
}
