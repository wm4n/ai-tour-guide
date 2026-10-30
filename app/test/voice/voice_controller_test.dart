import 'dart:async';
import 'dart:io';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/tour_controller.dart';
import 'package:buddy_tour/voice/phrase_store.dart';
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
  final store = FakePhraseStore();
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
      phraseStoreProvider.overrideWithValue(h.store),
      previewPlayerProvider.overrideWithValue(h.preview),
      tourApiProvider.overrideWithValue(h.tourApi),
      locationSourceProvider.overrideWithValue(h.location),
      narrationPlayerProvider.overrideWithValue(h.narration),
      remoteControlsProvider.overrideWithValue(FakeRemote()),
      phrasePlayerProvider.overrideWithValue(FakePhrases()),
      // 不必等兩段之間的間隔：播完就能接下一段
      playbackPolicyProvider.overrideWithValue(
        const PlaybackPolicy(minGap: Duration.zero),
      ),
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
      expect(h.state.current, (name: 'F2', displayName: '示範女聲', key: 'F2@1.2'));
    });

    test('offline it still knows the voice it last saw', () async {
      final h = await makeHarness();
      await h.voices.refresh();
      h.api.listError = TourApiException('unreachable');

      await h.voices.refresh();

      expect(h.state.catalog, isNull);
      expect(h.state.current, (name: 'F2', displayName: '示範女聲', key: 'F2@1.2'));
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

      expect(h.state.current, (name: 'F2', displayName: '示範女聲', key: 'F2@1.2'));
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

        expect(h.state.current, (name: 'X9', displayName: 'X9', key: null));
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

  group('switching voice', () {
    final everyPhrase = [
      for (final phrase in FixedPhrase.values) phrase.number,
    ];

    Future<Harness> ready() async {
      final h = await makeHarness();
      h.api.catalog = VoiceCatalog(
        current: 'F2',
        voices: [
          voice('F2', displayName: '示範女聲'),
          voice('M1', displayName: '示範男聲'),
          voice('M2'),
        ],
      );
      await h.voices.refresh();
      h.api.phrases.clear(); // 連上主機時已經補下載了目前聲音的短句
      return h;
    }

    VoiceInfo of(Harness h, String name) =>
        h.state.catalog!.voices.firstWhere((v) => v.name == name);

    test(
      'downloads every phrase of the new voice, asks the host, then remembers it',
      () async {
        final h = await ready();

        await h.voices.select(of(h, 'M1'));

        expect(h.api.phrases, [for (final n in everyPhrase) ('M1', n)]);
        expect(await h.store.has('M1@1.2'), isTrue);
        expect(h.api.chosen, ['M1']);
        expect(h.state.current, (
          name: 'M1',
          displayName: '示範男聲',
          key: 'M1@1.2',
        ));
        expect(h.state.catalog!.current, 'M1');
        expect(h.state.switching, isNull);
        expect(h.prefs.getString('voice.current.key'), 'M1@1.2');
      },
    );

    test('phrases already on the phone are not downloaded again', () async {
      final h = await ready();
      await h.voices.select(of(h, 'M1'));
      await h.voices.select(of(h, 'F2'));
      h.api.phrases.clear();

      await h.voices.select(of(h, 'M1'));

      expect(h.api.phrases, isEmpty);
      expect(h.api.chosen, ['M1', 'F2', 'M1']);
    });

    test('a failed download does not switch', () async {
      final h = await ready();
      h.api.phraseError = TourApiException('timed out');

      await h.voices.select(of(h, 'M1'));

      expect(h.api.chosen, isEmpty);
      expect(h.state.current?.name, 'F2');
      expect(h.state.catalog!.current, 'F2');
      expect(await h.store.has('M1@1.2'), isFalse);
      expect(h.state.error, isNotNull);
      expect(h.state.switching, isNull);
    });

    test('phrases the phone cannot store do not switch', () async {
      final h = await ready();
      h.store.saveError = const FileSystemException('No space left on device');

      await h.voices.select(of(h, 'M1'));

      expect(h.api.chosen, isEmpty);
      expect(h.state.current?.name, 'F2');
      expect(h.state.error, contains('手機'));
      expect(h.state.switching, isNull);
    });

    test('tapping the old voice while switching cancels the switch', () async {
      final h = await ready();
      h.api.phraseGates['M1'] = Completer<void>();

      final first = h.voices.select(of(h, 'M1'));
      await h.settle();
      await h.voices.select(of(h, 'F2'));
      h.api.phraseGates['M1']!.complete();
      await first;

      expect(h.api.chosen, ['F2']); // 主機已經是 F2：什麼都不換
      expect(h.state.current?.name, 'F2');
      expect(h.state.switching, isNull);
    });

    test('a switch the host refuses keeps the old voice', () async {
      final h = await ready();
      h.api.chooseError = TourApiException('answered 409', statusCode: 409);

      await h.voices.select(of(h, 'M1'));

      expect(h.state.current?.name, 'F2');
      expect(h.state.error, contains('短句'));
    });

    test('shows which voice it is switching to', () async {
      final h = await ready();
      h.api.chooseGate = Completer<void>();

      final done = h.voices.select(of(h, 'M1'));
      await h.settle();
      expect(h.state.switching, 'M1');
      expect(h.state.current?.name, 'F2');

      h.api.chooseGate!.complete();
      await done;
      expect(h.state.switching, isNull);
      expect(h.state.current?.name, 'M1');
    });

    test('the last tap wins even when the first download is slower', () async {
      final h = await ready();
      h.api.phraseGates['M1'] = Completer<void>();

      final first = h.voices.select(of(h, 'M1'));
      await h.settle();
      final second = h.voices.select(of(h, 'M2'));
      await second;
      h.api.phraseGates['M1']!.complete();
      await first;

      expect(h.api.chosen, ['M2']);
      expect(h.state.current?.name, 'M2');
      expect(h.state.switching, isNull);
    });

    test('switches reach the host in the order they were tapped', () async {
      final h = await ready();
      h.api.chooseGate = Completer<void>();

      final first = h.voices.select(of(h, 'M1'));
      await h.settle();
      expect(h.api.chosen, ['M1']); // 第一個切換已送出，主機還沒回
      final second = h.voices.select(of(h, 'M2'));
      await h.settle();
      expect(h.api.chosen, ['M1']); // 第二個要等第一個回來才送

      h.api.chooseGate!.complete();
      await Future.wait([first, second]);

      expect(h.api.chosen, ['M1', 'M2']);
      expect(h.state.current?.name, 'M2');
    });
  });

  group('following the host', () {
    test(
      'the host\'s current voice is followed and its phrases fetched',
      () async {
        final h = await makeHarness();
        h.api.catalog = VoiceCatalog(
          current: 'M1',
          voices: [
            voice('F2'),
            voice('M1', displayName: '示範男聲'),
          ],
        );

        await h.voices.refresh();

        expect(h.state.current, (
          name: 'M1',
          displayName: '示範男聲',
          key: 'M1@1.2',
        ));
        expect(await h.store.has('M1@1.2'), isTrue);
        expect(h.api.chosen, isEmpty); // 只是跟上主機，不是切換
      },
    );

    test('phrases already on the phone are not fetched again', () async {
      final h = await makeHarness();
      await h.voices.refresh();
      h.api.phrases.clear();

      await h.voices.refresh();

      expect(h.api.phrases, isEmpty);
    });

    test(
      'a current voice whose phrases the host lacks is not fetched',
      () async {
        final h = await makeHarness();
        h.api.catalog = VoiceCatalog(
          current: 'M1',
          voices: [voice('M1', phrasesReady: false)],
        );

        await h.voices.refresh();

        expect(h.api.phrases, isEmpty);
        expect(await h.store.has('M1@1.2'), isFalse);
      },
    );

    test('phrases the phone cannot store still show the list', () async {
      final h = await makeHarness();
      h.store.saveError = const FileSystemException('No space left on device');

      await h.voices.refresh(); // 不丟例外

      expect(h.state.catalog, isNotNull);
      expect(h.state.current?.name, 'F2');
    });

    test('a list asked for before a switch does not undo it', () async {
      final h = await makeHarness();
      await h.voices.refresh();
      h.api.listGate = Completer<void>();
      final stale = h.voices.refresh(); // 主機這時還是 F2
      await h.settle();

      await h.voices.select(voice('M1', displayName: '示範男聲'));
      h.api.listGate!.complete();
      await stale;

      expect(h.state.current?.name, 'M1');
      expect(h.state.catalog!.current, 'M1');
      expect(h.state.loading, isFalse);
      expect(h.prefs.getString('voice.current.key'), 'M1@1.2');
    });

    test('a failed fetch still shows the list', () async {
      final h = await makeHarness();
      h.api.phraseError = TourApiException('timed out');

      await h.voices.refresh();

      expect(h.state.catalog, isNotNull);
      expect(h.state.current?.name, 'F2');
    });
  });

  group('switching during a tour', () {
    const f2 = 'F2@1.2';
    const m1 = 'M1@1.2';

    NarrationInfo inVoice(String key, String id, {required int seq}) =>
        NarrationInfo(
          seq: seq,
          id: id,
          name: '景點$id',
          lat: placeLat,
          lon: placeLon,
          audioSeconds: 30,
          voice: key,
        );

    TourState tourState(Harness h) => h.container.read(tourProvider);

    Future<void> tick(Harness h) async {
      await h.tour.tick();
      await h.settle();
    }

    Future<void> finishPlaying(Harness h) async {
      h.narration.finish();
      await h.settle();
      await tick(h);
    }

    /// 主機與 App 都是 F2：出發，收到 F2 的 A、B；A 開始播，B 在佇列裡。
    Future<Harness> touring() async {
      final h = await makeHarness();
      await h.voices.refresh();
      await h.tour.start();
      h.tourApi.queue([
        inVoice(f2, 'A', seq: 1),
        inVoice(f2, 'B', seq: 2),
      ], voice: f2);
      h.location.controller.add(nearFix());
      await h.settle();
      await tick(h);
      expect(h.narration.played, ['A']);
      return h;
    }

    test(
      'the narration playing finishes; the rest of the old voice is dropped',
      () async {
        final h = await touring();

        await h.voices.select(voice('M1'));
        await finishPlaying(h);

        expect(h.api.playingIds, ['A']); // 主機不必重做 A
        expect(h.narration.events, isNot(contains('stop')));
        expect(h.narration.played, ['A']); // 舊聲音的 B 不播
        expect(h.tourApi.played, ['A']);
      },
    );

    test('the redo in the new voice comes back in and plays', () async {
      final h = await touring();
      await h.voices.select(voice('M1'));

      h.tourApi.queue([inVoice(m1, 'B', seq: 3)], voice: m1);
      await finishPlaying(h);

      expect(h.narration.played, ['A', 'B']);
      // 舊聲音那份的下載作廢，重做的另外下載
      expect(h.tourApi.downloads.where((id) => id == 'B'), hasLength(2));
    });

    test('a poll sent before the switch is not trusted', () async {
      final h = await touring();
      h.tourApi.pollGate = Completer<void>();
      h.tourApi.queue([inVoice(f2, 'C', seq: 3)], voice: f2);
      final inFlight = h.tour.tick();
      await h.settle();

      await h.voices.select(voice('M1'));
      h.tourApi.pollGate!.complete();
      await inFlight;
      await h.settle();
      h.tourApi.pollGate = null;
      await finishPlaying(h);

      expect(h.narration.played, ['A']); // 舊聲音的 C 沒有進佇列
      expect(h.tourApi.polls, [0, 2, 2]); // 游標不動，下一輪重抓
      expect(h.state.current?.key, m1); // 沒有被舊回應拉回 F2
      expect(h.api.lists, 1);
    });

    test(
      'narrations in another voice than the host\'s are not queued',
      () async {
        final h = await touring();
        await h.voices.select(voice('M1'));

        h.tourApi.queue([
          inVoice(f2, 'X', seq: 3),
          inVoice(m1, 'Y', seq: 4),
        ], voice: m1);
        await finishPlaying(h);

        expect(h.narration.played, ['A', 'Y']);
        expect(h.tourApi.downloads, isNot(contains('X')));
      },
    );

    test('a voice changed on the host is followed during a tour', () async {
      final h = await touring();
      h.api.catalog = VoiceCatalog(current: 'M1', voices: h.api.catalog.voices);

      h.tourApi.queue([inVoice(m1, 'B', seq: 3)], voice: m1);
      await tick(h);
      await finishPlaying(h);

      expect(h.state.current?.key, m1);
      expect(await h.store.has(m1), isTrue); // 補下載新聲音的短句
      expect(h.narration.played, ['A', 'B']);
      expect(h.tourApi.downloads.where((id) => id == 'B'), hasLength(2));
    });

    test(
      'a first tour with no remembered voice keeps what the host sends',
      () async {
        final h = await makeHarness(); // 從沒連上過：不知道目前聲音
        await h.tour.start();
        h.tourApi.queue([inVoice(f2, 'A', seq: 1)], voice: f2);
        h.location.controller.add(nearFix());
        await h.settle();
        await tick(h);

        expect(h.narration.played, ['A']);
        expect(h.state.current?.key, f2);
      },
    );

    test(
      'a narration waiting for its audio when the voice changes is not played, its redo is',
      () async {
        final h = await makeHarness();
        await h.voices.refresh();
        await h.tour.start();
        h.tourApi.downloadGate = Completer<void>();
        h.tourApi.queue([inVoice(f2, 'A', seq: 1)], voice: f2);
        h.location.controller.add(nearFix());
        await h.settle();
        await tick(h); // A 開始等音檔

        await h.voices.select(voice('M1'));
        h.tourApi.downloadGate!.complete();
        h.tourApi.downloadGate = null;
        await h.settle();
        expect(h.narration.played, isEmpty);

        h.tourApi.queue([inVoice(m1, 'A', seq: 2)], voice: m1);
        await tick(h);

        expect(h.api.playingIds, [null]); // 還沒開始播：主機要重做
        expect(h.narration.played, ['A']);
      },
    );

    test(
      'a late "gone" for the dropped version does not drop its redo',
      () async {
        final h = await makeHarness();
        await h.voices.refresh();
        await h.tour.start();
        h.tourApi.downloadGate = Completer<void>();
        h.tourApi.queue([inVoice(f2, 'A', seq: 1)], voice: f2);
        h.location.controller.add(nearFix());
        await h.settle();
        await tick(h); // 舊聲音的 A 開始等音檔

        await h.voices.select(voice('M1'));
        h.tourApi.queue([inVoice(m1, 'A', seq: 2)], voice: m1);
        await tick(h); // 重做的 A 先進佇列，也在等音檔
        // 主機已經撤下舊聲音的 A：舊的那份下載這時才回來，是 404
        h.tourApi.downloadErrorOnce = TourApiException('gone', statusCode: 404);
        h.tourApi.downloadGate!.complete();
        h.tourApi.downloadGate = null;
        await h.settle();
        await tick(h);

        expect(h.narration.played, ['A']);
      },
    );

    test(
      'a narration already gone before the switch still lets its redo in',
      () async {
        final h = await makeHarness();
        await h.voices.refresh();
        await h.tour.start();
        h.tourApi.downloadGate = Completer<void>();
        h.tourApi.queue([inVoice(f2, 'A', seq: 1)], voice: f2);
        h.location.controller.add(nearFix());
        await h.settle();
        await tick(h); // A 開始等音檔
        // 主機一收到切換就撤下 A：App 還沒收到切換的回應，下載就先回 404
        h.tourApi.downloadErrorOnce = TourApiException('gone', statusCode: 404);
        h.tourApi.downloadGate!.complete();
        h.tourApi.downloadGate = null;
        await h.settle();

        await h.voices.select(voice('M1'));
        h.tourApi.queue([inVoice(m1, 'A', seq: 2)], voice: m1);
        await tick(h);

        expect(h.narration.played, ['A']);
      },
    );

    test(
      'a narration waiting for its audio across away-and-back is heard once',
      () async {
        final h = await makeHarness();
        await h.voices.refresh();
        await h.tour.start();
        h.tourApi.downloadGate = Completer<void>();
        h.tourApi.queue([inVoice(f2, 'A', seq: 1)], voice: f2);
        h.location.controller.add(nearFix());
        await h.settle();
        await tick(h); // A 開始等音檔

        await h.voices.select(voice('M1'));
        await h.voices.select(voice('F2')); // 主機兩次都撤下 A，最後用 F2 重做
        h.tourApi.downloadGate!.complete();
        h.tourApi.downloadGate = null;
        await h.settle();
        h.tourApi.queue([inVoice(f2, 'A', seq: 3)], voice: f2);
        await tick(h);
        await finishPlaying(h);

        expect(h.narration.played, ['A']);
      },
    );

    test('following the host does not claim a switch is coming', () async {
      final h = await touring();
      h.api.catalog = VoiceCatalog(current: 'M1', voices: h.api.catalog.voices);

      h.tourApi.queue([], voice: m1);
      await tick(h);

      expect(h.state.current?.key, m1);
      expect(tourState(h).voiceChanging, isFalse);
    });

    test('switching away and back does not get a place stuck', () async {
      final h = await touring();
      await h.voices.select(voice('M1'));
      h.tourApi.queue([inVoice(m1, 'B', seq: 3)], voice: m1);
      await tick(h);

      await h.voices.select(voice('F2'));
      h.tourApi.queue([inVoice(f2, 'B', seq: 4)], voice: f2);
      await tick(h);
      await finishPlaying(h);

      expect(h.api.playingIds, ['A', 'A']);
      expect(h.narration.played, ['A', 'B']);
    });

    test('a failed switch keeps the narrations of the old voice', () async {
      final h = await touring();
      h.api.chooseError = TourApiException('refused', statusCode: 409);

      await h.voices.select(voice('M1'));
      await finishPlaying(h);

      expect(h.narration.played, ['A', 'B']);
    });

    test('says the next one is being prepared until it starts', () async {
      final h = await touring();
      expect(tourState(h).voiceChanging, isFalse);

      await h.voices.select(voice('M1'));
      expect(tourState(h).voiceChanging, isTrue);

      await finishPlaying(h); // 舊聲音的 A 播完，新聲音的還沒來
      expect(tourState(h).voiceChanging, isTrue);

      h.tourApi.queue([inVoice(m1, 'B', seq: 3)], voice: m1);
      await tick(h);
      expect(h.narration.played, ['A', 'B']);
      expect(tourState(h).voiceChanging, isFalse);
    });

    test('switching outside a tour says nothing about narrations', () async {
      final h = await makeHarness();
      await h.voices.refresh();

      await h.voices.select(voice('M1'));

      expect(tourState(h).voiceChanging, isFalse);
      expect(h.api.playingIds, [null]);
      expect(h.api.playedIds, [isEmpty]);
    });
  });

  group('switching does not repeat what was heard', () {
    const f2 = 'F2@1.2';
    const m1 = 'M1@1.2';

    NarrationInfo inVoice(String key, String id, {required int seq}) =>
        NarrationInfo(
          seq: seq,
          id: id,
          name: '景點$id',
          lat: placeLat,
          lon: placeLon,
          audioSeconds: 30,
          unitStarts: const [0.0, 1.5],
          voice: key,
        );

    Future<void> tick(Harness h) async {
      await h.tour.tick();
      await h.settle();
    }

    Future<void> finishPlaying(Harness h) async {
      h.narration.finish();
      await h.settle();
      await tick(h);
    }

    /// 主機與 App 都是 F2：出發，收到 F2 的 A、B；A 開始播，B 在佇列裡。
    Future<Harness> touring() async {
      final h = await makeHarness();
      await h.voices.refresh();
      await h.tour.start();
      h.tourApi.queue([
        inVoice(f2, 'A', seq: 1),
        inVoice(f2, 'B', seq: 2),
      ], voice: f2);
      h.location.controller.add(nearFix());
      await h.settle();
      await tick(h);
      expect(h.narration.played, ['A']);
      return h;
    }

    test(
      'nothing of the old voice starts while the switch is under way',
      () async {
        final h = await touring();
        h.api.phraseGate = Completer<void>(); // 還在下載新聲音的短句

        final switching = h.voices.select(voice('M1'));
        await h.settle();
        await finishPlaying(h); // A 剛好在空檔播完

        expect(h.narration.played, ['A']); // B 沒有趁空檔開播
        h.api.phraseGate!.complete();
        await switching;
        await tick(h);

        expect(h.api.playingIds, [null]);
        expect(h.tourApi.played, ['A']);
        expect(h.narration.played, ['A']); // B 丟掉，等主機重做
      },
    );

    test(
      'a narration finished in the gap and not yet reported is sent along',
      () async {
        final h = await touring();
        h.tourApi.playedError = TourApiException('unreachable');
        h.api.phraseGate = Completer<void>();

        final switching = h.voices.select(voice('M1'));
        await h.settle();
        await finishPlaying(h); // A 在空檔播完，回報送不出去
        h.api.phraseGate!.complete();
        await switching;

        expect(h.api.playingIds, [null]);
        expect(h.api.playedIds, [
          ['A'],
        ]);
      },
    );

    test('a tour restarted during a switch waits for it too', () async {
      final h = await touring();
      h.api.chooseGate = Completer<void>();
      final switching = h.voices.select(voice('M1'));
      await h.settle();

      await h.tour.end();
      await h.tour.start();
      h.tourApi.queue([inVoice(f2, 'C', seq: 1)], voice: f2);
      h.location.controller.add(nearFix());
      await h.settle();
      await tick(h);
      expect(h.narration.played, ['A']); // 舊聲音的 C 不趁空檔開播

      h.api.chooseGate!.complete();
      await switching;
      h.tourApi.queue([inVoice(m1, 'C', seq: 2)], voice: m1);
      await tick(h);
      expect(h.narration.played, ['A', 'C']);
    });

    test('a narration whose audio arrives during the switch waits', () async {
      final h = await makeHarness();
      await h.voices.refresh();
      await h.tour.start();
      h.tourApi.downloadGate = Completer<void>();
      h.tourApi.queue([inVoice(f2, 'A', seq: 1)], voice: f2);
      h.location.controller.add(nearFix());
      await h.settle();
      await tick(h); // A 開始等音檔
      h.api.chooseGate = Completer<void>();

      final switching = h.voices.select(voice('M1'));
      await h.settle();
      h.tourApi.downloadGate!.complete();
      h.tourApi.downloadGate = null;
      await tick(h);

      expect(h.narration.played, isEmpty);
      h.api.chooseError = TourApiException('refused', statusCode: 409);
      h.api.chooseGate!.complete();
      await switching;
      await tick(h);
      expect(h.narration.played, ['A']); // 失敗：照常播
    });

    test(
      'a failed switch lets the old voice carry on where it left off',
      () async {
        final h = await touring();
        h.api.phraseGate = Completer<void>();

        final switching = h.voices.select(voice('M1'));
        await h.settle();
        await finishPlaying(h);
        expect(h.narration.played, ['A']);

        h.api.phraseError = TourApiException('timed out');
        h.api.phraseGate!.complete();
        await switching;
        await h.settle();

        expect(h.narration.played, ['A', 'B']);
      },
    );

    test(
      'reports the host has not received are sent with the switch',
      () async {
        final h = await touring();
        h.tourApi.playedError = TourApiException('unreachable');
        await finishPlaying(h); // A 播完，回報送不出去；B 開始播

        await h.voices.select(voice('M1'));

        expect(h.api.playedIds, [
          ['A'],
        ]);
        expect(h.api.playingIds, ['B']);
        h.tourApi.playedError = null;
        await finishPlaying(h);
        expect(h.tourApi.played, ['B']); // A 主機已經記了，不再送
      },
    );

    test('reports still pending after a failed switch are kept', () async {
      final h = await touring();
      h.tourApi.playedError = TourApiException('unreachable');
      await finishPlaying(h);
      h.api.chooseError = TourApiException('refused', statusCode: 409);

      await h.voices.select(voice('M1'));
      h.tourApi.playedError = null;
      await tick(h);

      expect(h.tourApi.played, ['A']);
    });

    test(
      'the narration interrupted by a preview is told, not resumed',
      () async {
        final h = await touring();
        final previewing = h.voices.preview('M1'); // 試聽打斷 A
        await h.settle();

        await h.voices.select(voice('M1'));
        h.preview.finish();
        await previewing;
        await tick(h);

        expect(h.api.playingIds, [null]);
        expect(h.api.playedIds, [
          ['A'],
        ]);
        expect(h.narration.starts, [Duration.zero]); // 沒有接著播
        expect(h.container.read(tourProvider).nowPlaying, isNull);

        h.tourApi.queue([inVoice(m1, 'B', seq: 3)], voice: m1);
        await tick(h);
        expect(h.narration.played, ['A', 'B']); // 新聲音的介紹照常開播
        expect(h.tourApi.played, isEmpty); // A 已隨切換記了，不另外回報
      },
    );

    test(
      'an interrupted narration does not resume while the switch is under way',
      () async {
        final h = await touring();
        h.api.chooseGate = Completer<void>();
        final previewing = h.voices.preview('M1');
        await h.settle();
        final switching = h.voices.select(voice('M1'));
        await h.settle();

        h.preview.finish(); // 試聽完了，但還在換聲音
        await previewing;
        await tick(h);
        expect(h.narration.starts, [Duration.zero]);

        h.api.chooseGate!.complete();
        await switching;
        await tick(h);
        expect(h.narration.starts, [Duration.zero]);
      },
    );

    test(
      'a narration interrupted after the switch was sent is reported as heard',
      () async {
        final h = await touring();
        h.api.chooseGate = Completer<void>();
        final switching = h.voices.select(voice('M1'));
        await h.settle(); // 請求已送出，A 還在播（playing_id）

        final previewing = h.voices.preview('M1');
        await h.settle();
        h.api.chooseGate!.complete();
        await switching;
        h.preview.finish();
        await previewing;
        await tick(h);

        expect(h.api.playingIds, ['A']);
        expect(h.narration.starts, [Duration.zero]);
        expect(h.tourApi.played, ['A']);
      },
    );

    test('an interrupted narration resumes when the switch fails', () async {
      final h = await touring();
      h.narration.positionNow = at(2);
      h.api.chooseError = TourApiException('refused', statusCode: 409);
      final previewing = h.voices.preview('M1');
      await h.settle();

      await h.voices.select(voice('M1'));
      h.preview.finish();
      await previewing;
      await h.settle();

      expect(h.narration.starts, [Duration.zero, at(1.5)]);
    });

    test(
      'going back to the same voice keeps the interrupted narration',
      () async {
        final h = await touring();
        h.narration.positionNow = at(2);
        final previewing = h.voices.preview('M1');
        await h.settle();

        await h.voices.select(voice('F2')); // 主機回 200，聲音沒變
        h.preview.finish();
        await previewing;
        await h.settle();

        expect(h.api.playedIds, [
          ['A'],
        ]);
        expect(h.narration.starts, [Duration.zero, at(1.5)]);
      },
    );
  });
}
