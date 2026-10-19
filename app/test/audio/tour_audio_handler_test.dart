import 'package:audio_service/audio_service.dart';
import 'package:buddy_tour/audio/audio_service_remote_controls.dart';
import 'package:buddy_tour/audio/remote_controls.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('the headphone pause and play keys become remote commands', () async {
    final handler = TourAudioHandler();
    final commands = <RemoteCommand>[];
    handler.commands.listen(commands.add);

    await handler.pause();
    await handler.play();
    await Future<void>.delayed(Duration.zero);

    expect(commands, [RemoteCommand.pause, RemoteCommand.play]);
  });

  test(
    'the lock-screen stop key only pauses; ending a tour stays in the app',
    () async {
      final handler = TourAudioHandler();
      final commands = <RemoteCommand>[];
      handler.commands.listen(commands.add);

      await handler.stop();
      await Future<void>.delayed(Duration.zero);

      expect(commands, [RemoteCommand.pause]);
    },
  );

  test('during a tour the system sees "playing" even between narrations', () {
    final handler = TourAudioHandler();

    handler.update(tourActive: true, paused: false, narrating: false);

    final state = handler.playbackState.value;
    expect(state.playing, isTrue);
    expect(state.processingState, AudioProcessingState.ready);
    expect(state.controls.single, MediaControl.pause);
  });

  test('paused shows the play key', () {
    final handler = TourAudioHandler();

    handler.update(tourActive: true, paused: true, narrating: false);

    expect(handler.playbackState.value.playing, isFalse);
    expect(handler.playbackState.value.controls.single, MediaControl.play);
  });

  test('the title is the place being told about', () {
    final handler = TourAudioHandler();

    handler.update(
      tourActive: true,
      paused: false,
      narrating: true,
      title: '霞海城隍廟',
    );

    expect(handler.mediaItem.value?.title, '霞海城隍廟');
  });

  test('after the tour ends nothing is playing', () {
    final handler = TourAudioHandler();
    handler.update(tourActive: true, paused: false, narrating: false);

    handler.update(tourActive: false, paused: false, narrating: false);

    expect(handler.playbackState.value.playing, isFalse);
    expect(
      handler.playbackState.value.processingState,
      AudioProcessingState.idle,
    );
  });
}
