import 'dart:async';

import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/tour_controller.dart';
import 'package:buddy_tour/voice/voice_api.dart';
import 'package:buddy_tour/voice/voice_controller.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../tour/fakes.dart';
import 'fakes.dart';

class Harness {
  Harness({FakePlayer? preview}) : preview = preview ?? FakePlayer();

  final api = FakeVoiceApi();
  final tourApi = FakeTourApi();
  final location = FakeLocation();
  final narration = FakePlayer();
  final FakePlayer preview;
  late SharedPreferences prefs;
  late ProviderContainer container;

  VoiceController get voices => container.read(voiceProvider.notifier);
  VoiceState get state => container.read(voiceProvider);
  TourController get tour => container.read(tourProvider.notifier);

  Future<void> settle() => pumpEventQueue();
}

Future<Harness> makeHarness({
  Map<String, Object> stored = const {},
  FakePlayer? preview,
}) async {
  SharedPreferences.setMockInitialValues({'host.url': 'http://h:1', ...stored});
  final h = Harness(preview: preview);
  h.prefs = await SharedPreferences.getInstance();
  h.container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(h.prefs),
      voiceApiProvider.overrideWithValue(h.api),
      previewPlayerProvider.overrideWithValue(h.preview),
      tourApiProvider.overrideWithValue(h.tourApi),
      locationSourceProvider.overrideWithValue(h.location),
      narrationPlayerProvider.overrideWithValue(h.narration),
      remoteControlsProvider.overrideWithValue(FakeRemote()),
      phrasePlayerProvider.overrideWithValue(FakePhrases()),
      tourTickIntervalProvider.overrideWithValue(const Duration(hours: 1)),
      locationReportIntervalProvider.overrideWithValue(Duration.zero),
    ],
  );
  addTearDown(h.container.dispose);
  h.container.read(tourProvider);
  return h;
}

Duration at(double seconds) =>
    Duration(microseconds: (seconds * 1000000).round());

/// 出發並開始播一段有三句的介紹 A。
Future<void> playNarration(Harness h) async {
  await h.tour.start();
  h.tourApi.queue([
    const NarrationInfo(
      seq: 1,
      id: 'A',
      name: '景點A',
      lat: placeLat,
      lon: placeLon,
      audioSeconds: 30,
      unitStarts: [0.0, 1.5, 3.5],
    ),
  ]);
  h.location.controller.add(nearFix());
  await h.settle();
  await h.tour.tick();
  await h.settle();
  expect(h.narration.played, ['A']);
}

void main() {
  group('the voice list', () {
    test('loads the host\'s voices and remembers the current one', () async {
      final h = await makeHarness();

      await h.voices.refresh();

      expect(h.state.catalog?.voices.map((v) => v.name), ['F2', 'M1']);
      expect(h.state.loading, isFalse);
      expect(h.state.current, (name: 'F2', displayName: '示範女聲'));
    });

    test('offline it still knows the voice it last saw', () async {
      final h = await makeHarness();
      await h.voices.refresh();
      h.api.listError = TourApiException('unreachable');

      await h.voices.refresh();

      expect(h.state.catalog, isNull);
      expect(h.state.current, (name: 'F2', displayName: '示範女聲'));
    });

    test('the remembered voice survives a restart of the app', () async {
      final first = await makeHarness();
      await first.voices.refresh();
      final stored = {
        for (final key in first.prefs.getKeys())
          key: first.prefs.get(key) as Object,
      };

      final h = await makeHarness(stored: stored);
      h.api.listError = TourApiException('unreachable');
      await h.voices.refresh();

      expect(h.state.current, (name: 'F2', displayName: '示範女聲'));
    });

    test('never having reached the host there is no current voice', () async {
      final h = await makeHarness();
      h.api.listError = TourApiException('unreachable');

      await h.voices.refresh();

      expect(h.state.catalog, isNull);
      expect(h.state.current, isNull);
    });

    test(
      'a current voice missing from the list is shown by its name',
      () async {
        final h = await makeHarness();
        h.api.catalog = VoiceCatalog(current: 'X9', voices: [voice('M1')]);

        await h.voices.refresh();

        expect(h.state.current, (name: 'X9', displayName: 'X9'));
      },
    );
  });

  group('previewing a voice', () {
    test('plays phrase 7 of that voice from the host', () async {
      final h = await makeHarness();

      final done = h.voices.preview('M1');
      await h.settle();
      expect(h.api.phrases, [('M1', 7)]);
      expect(h.preview.played, ['M1#7']);
      expect(h.state.previewing, 'M1');

      h.preview.finish();
      await done;
      expect(h.state.previewing, isNull);
    });

    test(
      'interrupts a narration like a question and resumes it from the start of that sentence',
      () async {
        final h = await makeHarness();
        await playNarration(h);
        h.narration.positionNow = at(2.0); // 第二句講到一半

        final done = h.voices.preview('M1');
        await h.settle();
        expect(h.narration.events, contains('stop(keep focus)'));
        expect(h.preview.played, ['M1#7']);

        h.preview.finish();
        await done;
        await h.settle();

        expect(h.narration.played, ['A', 'A']);
        expect(h.narration.starts, [Duration.zero, at(1.5)]);
      },
    );

    test('a failed download lets the tour carry on', () async {
      final h = await makeHarness();
      await playNarration(h);
      h.narration.positionNow = at(2.0);
      h.api.phraseError = TourApiException(
        '/v1/voices/M1/phrases/7 answered 404',
      );

      await h.voices.preview('M1');
      await h.settle();

      expect(h.preview.played, isEmpty);
      expect(h.state.previewing, isNull);
      expect(h.state.error, isNotNull);
      expect(h.narration.starts, [Duration.zero, at(1.5)]); // 照樣接著播
    });

    test('a phrase the host does not have says so', () async {
      final h = await makeHarness();
      h.api.phraseError = TourApiException('answered 404', statusCode: 404);

      await h.voices.preview('M1');

      expect(h.state.error, contains('短句'));
    });

    test('an unreachable host says so', () async {
      final h = await makeHarness();
      h.api.phraseError = TourApiException('timed out');

      await h.voices.preview('M1');

      expect(h.state.error, contains('連不上主機'));
    });

    test(
      'audio that cannot be played says so and lets the tour carry on',
      () async {
        final h = await makeHarness(preview: BrokenPlayer());
        await playNarration(h);
        h.narration.positionNow = at(2.0);

        await h.voices.preview('M1');
        await h.settle();

        expect(h.state.error, contains('無法播放'));
        expect(h.state.previewing, isNull);
        expect(h.narration.starts, [Duration.zero, at(1.5)]);
      },
    );

    test('a new preview clears the last error', () async {
      final h = await makeHarness();
      h.api.phraseError = TourApiException('timed out');
      await h.voices.preview('M1');
      h.api.phraseError = null;

      final done = h.voices.preview('M1');
      await h.settle();

      expect(h.state.error, isNull);
      h.preview.finish();
      await done;
    });

    test(
      'previewing another voice stops the first without resuming the narration in between',
      () async {
        final h = await makeHarness();
        await playNarration(h);
        h.narration.positionNow = at(2.0);

        final first = h.voices.preview('F2');
        await h.settle();
        final second = h.voices.preview('M1');
        await h.settle();

        expect(h.preview.played, ['F2#7', 'M1#7']);
        expect(h.narration.played, ['A']); // 兩段試聽之間沒有偷播介紹
        expect(h.state.previewing, 'M1');

        h.preview.finish();
        await Future.wait([first, second]);
        await h.settle();

        expect(h.state.previewing, isNull);
        expect(h.narration.played, ['A', 'A']);
        expect(h.narration.starts.last, at(1.5));
      },
    );

    test('a slow download that is overtaken is never played', () async {
      final h = await makeHarness();
      h.api.phraseGate = Completer<void>();

      final first = h.voices.preview('F2');
      await h.settle();
      final second = h.voices.preview('M1');
      await h.settle();
      h.api.phraseGate!.complete();
      await h.settle();

      expect(h.preview.played, ['M1#7']);
      h.preview.finish();
      await Future.wait([first, second]);
    });
  });
}
