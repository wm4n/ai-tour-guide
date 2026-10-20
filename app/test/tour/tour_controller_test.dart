import 'dart:async';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/audio/remote_controls.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/tour/location_source.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/tour_api.dart';
import 'package:buddy_tour/tour/tour_controller.dart';
import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fakes.dart';
import 'package:shared_preferences/shared_preferences.dart';

NarrationInfo info(String id, {int seq = 1, double lat = placeLat}) =>
    NarrationInfo(
      seq: seq,
      id: id,
      name: '景點$id',
      lat: lat,
      lon: placeLon,
      audioSeconds: 30,
    );

class Harness {
  Harness(this.api);

  final FakeTourApi api;
  final location = FakeLocation();
  final player = FakePlayer();
  final remote = FakeRemote();
  final phrases = FakePhrases();
  var now = DateTime(2026, 10, 20, 15, 0);
  late ProviderContainer container;

  TourController get tour => container.read(tourProvider.notifier);
  TourState get state => container.read(tourProvider);

  Future<void> settle() => pumpEventQueue();

  /// 走到某處並讓控制器處理（定位與輪詢）。
  Future<void> moveTo(RawFix fix) async {
    location.controller.add(fix);
    await settle();
  }

  Future<void> tick({Duration after = Duration.zero}) async {
    now = now.add(after);
    await tour.tick();
    await settle();
  }
}

Future<Harness> makeHarness({
  FakeTourApi? api,
  bool configured = true,
  PlaybackPolicy policy = const PlaybackPolicy(),
  Duration reportInterval = Duration.zero,
}) async {
  SharedPreferences.setMockInitialValues(
    configured ? {'host.url': 'http://h:1'} : {},
  );
  final prefs = await SharedPreferences.getInstance();
  final h = Harness(api ?? FakeTourApi());
  h.container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      tourApiProvider.overrideWithValue(h.api),
      locationSourceProvider.overrideWithValue(h.location),
      narrationPlayerProvider.overrideWithValue(h.player),
      remoteControlsProvider.overrideWithValue(h.remote),
      phrasePlayerProvider.overrideWithValue(h.phrases),
      clockProvider.overrideWithValue(() => h.now),
      playbackPolicyProvider.overrideWithValue(policy),
      tourTickIntervalProvider.overrideWithValue(const Duration(hours: 1)),
      locationReportIntervalProvider.overrideWithValue(reportInterval),
    ],
  );
  addTearDown(h.container.dispose);
  // 讓控制器先建立（它會開始聽耳機指令）
  h.container.read(tourProvider);
  return h;
}

void main() {
  group('starting', () {
    test(
      'reports the start position and traveler state, then says hello',
      () async {
        final h = await makeHarness();
        await h.container
            .read(travelerProvider.notifier)
            .save(const TravelerState(companions: Companions.family));

        await h.tour.start();

        expect(h.state.active, isTrue);
        expect(h.api.started.single.$1.lat, closeTo(farFix().lat, 1e-9));
        expect(h.api.started.single.$2.companions, Companions.family);
        expect(h.phrases.played, [FixedPhrase.startTour]);
      },
    );

    test('a host that refuses leaves the tour unstarted and quiet', () async {
      final h = await makeHarness();
      h.api.startError = TourApiException('down');

      await h.tour.start();

      expect(h.state.active, isFalse);
      expect(h.state.error, isNotNull);
      expect(h.phrases.played, isEmpty);
    });

    test('refused location permission leaves the tour unstarted', () async {
      final h = await makeHarness();
      h.location.granted = false;

      await h.tour.start();

      expect(h.state.active, isFalse);
      expect(h.api.calls, isEmpty);
    });

    test('an unconfigured host does not start', () async {
      final h = await makeHarness(configured: false);

      await h.tour.start();

      expect(h.state.active, isFalse);
      expect(h.api.calls, isEmpty);
    });
  });

  group('reporting position', () {
    test(
      'every fix is reported with the heading worked out from movement',
      () async {
        final h = await makeHarness();
        await h.tour.start();

        await h.moveTo(farFix(325)); // 只走了 5 公尺：方向還算不出來
        await h.moveTo(farFix(300)); // 離起點 30 公尺，往北

        expect(h.api.reported.first.$1.heading, isNull);
        expect(h.api.reported.last.$1.heading, closeTo(0, 1));
      },
    );

    test('reports are spaced out by the report interval', () async {
      final h = await makeHarness(reportInterval: const Duration(seconds: 10));
      await h.tour.start(); // 出發本身就是第一次回報

      await h.moveTo(farFix(320));
      await h.moveTo(farFix(310)); // 還不到 10 秒：不回報
      expect(h.api.reported, isEmpty);

      h.now = h.now.add(const Duration(seconds: 11));
      await h.moveTo(farFix(300));
      await h.moveTo(farFix(290)); // 剛回報過

      expect(h.api.reported, hasLength(1));
      expect(h.api.reported.single.$1.lat, closeTo(farFix(300).lat, 1e-9));
    });

    test(
      'a traveler change during the tour goes out with the next report',
      () async {
        final h = await makeHarness();
        await h.tour.start();

        await h.container
            .read(travelerProvider.notifier)
            .save(const TravelerState(withChildren: true));
        await h.moveTo(farFix(300));

        expect(h.api.reported.last.$2.withChildren, isTrue);
      },
    );

    test('a failed report does not stop the tour', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.reportError = TourApiException('down');

      await h.moveTo(farFix(300));

      expect(h.state.active, isTrue);
    });
  });

  group('playing narrations', () {
    test('plays a narration once the user is near the place', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.queue([info('A')]);

      await h.moveTo(nearFix());
      await h.tick();

      expect(h.api.downloads, ['A']);
      expect(h.player.played, ['A']);
      expect(h.state.nowPlaying, '景點A');
    });

    test('waits while the place is far, plays when the user arrives', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.queue([info('A')]);
      await h.tick();
      expect(h.player.played, isEmpty);

      await h.moveTo(nearFix());
      await h.tick();

      expect(h.player.played, ['A']);
    });

    test('polls with a cursor so a narration is never fetched twice', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.queue([info('A', seq: 4)]);

      await h.tick();
      await h.tick();

      expect(h.api.polls, [0, 4]);
    });

    test(
      'the next narration waits for the gap after the last one finished',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();
        h.player.finish();
        await h.settle();
        expect(h.state.nowPlaying, isNull);

        h.api.queue([info('B', seq: 2)]);
        await h.tick(after: const Duration(minutes: 2, seconds: 59));
        expect(h.player.played, ['A']);

        await h.tick(after: const Duration(seconds: 1));
        expect(h.player.played, ['A', 'B']);
      },
    );

    test('never starts one narration on top of another', () async {
      final h = await makeHarness(
        policy: const PlaybackPolicy(minGap: Duration.zero),
      );
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([info('A'), info('B', seq: 2)]);

      await h.tick();
      await h.tick(after: const Duration(minutes: 10));

      expect(h.player.played, ['A']);
    });

    test('a narration is not played twice', () async {
      final h = await makeHarness(
        policy: const PlaybackPolicy(minGap: Duration.zero),
      );
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([info('A')]);
      await h.tick();
      h.player.finish();
      await h.settle();

      h.api.queue([info('A')]);
      await h.tick(after: const Duration(minutes: 5));

      expect(h.player.played, ['A']);
    });

    test('a narration whose audio cannot be fetched stays quiet', () async {
      final h = await makeHarness(api: FakeTourApiFailingDownload());
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([info('A')]);

      await h.tick();

      expect(h.player.played, isEmpty);
      expect(h.state.nowPlaying, isNull);
      expect(h.state.active, isTrue);
    });
  });

  group('pausing proactive narration', () {
    test(
      'the headphone pause key pauses the narration that is playing',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();

        h.remote.controller.add(RemoteCommand.pause);
        await h.settle();

        expect(h.state.paused, isTrue);
        expect(h.player.events, contains('pause'));
        expect(h.remote.updates.last.paused, isTrue);
      },
    );

    test(
      'nothing new is played while paused, and it plays after resuming',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.remote.controller.add(RemoteCommand.pause);
        await h.settle();
        h.api.queue([info('A')]);

        await h.tick();
        expect(h.player.played, isEmpty);

        h.remote.controller.add(RemoteCommand.play);
        await h.settle();
        await h.tick();
        expect(h.player.played, ['A']);
      },
    );

    test(
      'resuming continues the paused narration instead of restarting it',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();
        h.remote.controller.add(RemoteCommand.pause);
        await h.settle();

        h.remote.controller.add(RemoteCommand.play);
        await h.settle();

        expect(h.player.events, ['play:景點A', 'pause', 'resume']);
        expect(h.player.played, ['A']);
        expect(h.state.paused, isFalse);
      },
    );

    test(
      'the gap is counted from when the narration finished, not from the pause',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();
        h.remote.controller.add(RemoteCommand.pause);
        await h.settle();
        await h.tick(after: const Duration(minutes: 20));
        h.remote.controller.add(RemoteCommand.play);
        await h.settle();
        h.player.finish();
        await h.settle();

        h.api.queue([info('B', seq: 2)]);
        await h.tick(after: const Duration(minutes: 1));

        expect(h.player.played, ['A']);
      },
    );

    test(
      'pausing while the audio is still downloading holds the narration back',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.downloadGate = Completer<void>();
        h.api.queue([info('A')]);
        await h.tick();

        h.tour.pause();
        h.api.downloadGate!.complete();
        await h.settle();
        expect(h.player.played, isEmpty);
        expect(h.state.nowPlaying, isNull);

        h.tour.resume();
        await h.settle();
        expect(h.player.played, ['A']);
      },
    );

    test('remote keys are ignored when no tour is running', () async {
      final h = await makeHarness();

      h.remote.controller.add(RemoteCommand.pause);
      await h.settle();

      expect(h.state.paused, isFalse);
    });
  });

  group('ending', () {
    test(
      'tells the host, stops the audio and stops listening to the position',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();

        await h.tour.end();
        final reports = h.api.reported.length;
        await h.moveTo(farFix(100));

        expect(h.api.calls.last, 'end');
        expect(h.player.events, contains('stop'));
        expect(h.state.active, isFalse);
        expect(h.state.nowPlaying, isNull);
        expect(h.api.reported, hasLength(reports));
      },
    );

    test(
      'a narration that finishes after the tour ended changes nothing',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();

        await h.tour.end();
        h.player.finish();
        await h.settle();

        expect(h.state.nowPlaying, isNull);
        expect(h.state.active, isFalse);
      },
    );

    test('a new tour starts clean', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.queue([info('A', seq: 7)]);
      await h.tick();
      await h.tour.end();

      await h.tour.start();
      await h.tick();

      expect(h.api.polls.last, 0);
    });
  });

  group('usage summary', () {
    const summary = TourSummary(
      calls: 4,
      narrations: 3,
      durationSeconds: 2400,
      hitLimit: false,
      utilization: {'five_hour': WindowUse(last: 0.38, change: 0.12)},
    );

    test('the summary from the host is kept after the tour ends', () async {
      final h = await makeHarness();
      h.api.summary = summary;
      await h.tour.start();

      await h.tour.end();

      expect(h.state.active, isFalse);
      expect(h.state.summary, same(summary));
    });

    test('an unreachable host at the end just means no summary', () async {
      final h = await makeHarness();
      h.api.endError = TourApiException('down');
      await h.tour.start();

      await h.tour.end();

      expect(h.state.active, isFalse);
      expect(h.state.summary, isNull);
    });

    test('a new tour clears the previous summary', () async {
      final h = await makeHarness();
      h.api.summary = summary;
      await h.tour.start();
      await h.tour.end();

      await h.tour.start();

      expect(h.state.summary, isNull);
    });
  });

  group('host state', () {
    test(
      'quota exhaustion is shown to the user and nothing is said aloud',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.api.queue([], stoppedReason: 'quota');

        await h.tick();

        expect(h.state.stoppedReason, 'quota');
        expect(h.phrases.played, [FixedPhrase.startTour]);
      },
    );

    test('the quota notice goes away by itself when the host recovers, '
        'and narrations keep playing', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([], stoppedReason: 'quota');
      await h.tick();
      expect(h.state.stoppedReason, 'quota');

      h.api.queue([info('A')]);
      await h.tick();

      expect(h.state.stoppedReason, isNull);
      expect(h.player.played, ['A']);
      expect(h.phrases.played, [FixedPhrase.startTour]);
    });

    test(
      'a host that lost the tour (restart) is told to start again',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.api.queueInactive();

        await h.tick();

        expect(h.api.calls.where((c) => c == 'start'), hasLength(2));
        expect(h.state.active, isTrue);
      },
    );

    test('a failed poll is survived and the next one works', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.pollError = TourApiException('down');
      await h.tick();
      expect(h.state.active, isTrue);

      h.api.pollError = null;
      h.api.queue([info('A')]);
      await h.tick(after: const Duration(minutes: 1));

      expect(h.player.played, ['A']);
    });
  });

  group('host unreachable', () {
    const retry = Duration(seconds: 70); // 比退避上限長，保證下一次一定會重試

    test('says the unreachable phrase once, however long the outage', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.pollError = TourApiException('down');

      await h.tick();
      await h.tick(after: retry);
      await h.tick(after: retry);

      expect(h.phrases.played, [
        FixedPhrase.startTour,
        FixedPhrase.hostUnreachable,
      ]);
    });

    test('backs off instead of polling on every tick', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.pollError = TourApiException('down');
      await h.tick();
      final pollsAfterFailure = h.api.polls.length;

      await h.tick(after: const Duration(seconds: 5));
      expect(h.api.polls.length, pollsAfterFailure);

      await h.tick(after: const Duration(seconds: 5));
      expect(h.api.polls.length, pollsAfterFailure + 1);
    });

    test('recovering resumes narration quietly and never replays', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([info('A', seq: 1)]);
      await h.tick();
      h.player.finish();
      await h.settle();
      h.api.pollError = TourApiException('down');
      await h.tick(after: const Duration(minutes: 5));
      expect(h.phrases.played, contains(FixedPhrase.hostUnreachable));
      final spoken = h.phrases.played.length;

      h.api.pollError = null;
      h.api.queue([info('B', seq: 2)]);
      await h.tick(after: retry);

      expect(h.api.polls.last, 1); // 還是從上次的進度往後問
      expect(h.player.played, ['A', 'B']);
      expect(h.phrases.played, hasLength(spoken)); // 重新連上不念
    });

    test('a second outage is announced again', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.pollError = TourApiException('down');
      await h.tick();
      h.api.pollError = null;
      await h.tick(after: retry);
      h.api.pollError = TourApiException('down');

      await h.tick(after: retry);

      expect(
        h.phrases.played.where((p) => p == FixedPhrase.hostUnreachable),
        hasLength(2),
      );
    });

    test('waits for the narration in progress before speaking', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([info('A')]);
      await h.tick();
      expect(h.player.events, contains('play:景點A'));

      h.api.pollError = TourApiException('down');
      await h.tick(after: retry);
      expect(h.phrases.played, [FixedPhrase.startTour]);

      h.player.finish();
      await h.settle();
      await h.tick(after: const Duration(seconds: 5));
      expect(h.phrases.played, [
        FixedPhrase.startTour,
        FixedPhrase.hostUnreachable,
      ]);
    });

    test(
      'a host that comes back before the phrase is due stays quiet',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();
        h.api.pollError = TourApiException('down');
        await h.tick(after: retry);
        h.api.pollError = null;
        await h.tick(after: retry);

        h.player.finish();
        await h.settle();
        await h.tick(after: retry);

        expect(h.phrases.played, [FixedPhrase.startTour]);
      },
    );

    test('stays silent while paused and speaks once resumed', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.tour.pause();
      h.api.pollError = TourApiException('down');

      await h.tick();
      expect(h.phrases.played, [FixedPhrase.startTour]);

      h.tour.resume();
      await h.settle();
      expect(h.phrases.played, [
        FixedPhrase.startTour,
        FixedPhrase.hostUnreachable,
      ]);
    });

    test('position reports pause during the outage, then catch up', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.pollError = TourApiException('down');
      await h.tick();
      final reported = h.api.reported.length;

      await h.moveTo(farFix(200));
      expect(h.api.reported.length, reported);

      h.api.pollError = null;
      await h.tick(after: retry);

      expect(h.api.reported.length, reported + 1);
      expect(h.api.reported.last.$1.lat, closeTo(farFix(200).lat, 1e-9));
    });

    test('a narration whose download failed is fetched again once the host is '
        'back', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.downloadError = TourApiException('dropped');
      h.api.queue([info('A')]);

      await h.tick();
      expect(h.player.played, isEmpty);
      await h.tick(after: const Duration(seconds: 5)); // 退避中，只評估播放
      expect(h.phrases.played, contains(FixedPhrase.hostUnreachable));

      h.api.downloadError = null;
      await h.tick(after: retry);

      expect(h.player.played, ['A']);
    });

    test('overlapping ticks do not poll twice at once', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.pollGate = Completer<void>();

      final first = h.tour.tick();
      final second = h.tour.tick();
      h.api.pollGate!.complete();
      await Future.wait([first, second]);

      expect(h.api.polls, hasLength(1));
    });

    test('the phrase is not spoken on top of a narration that starts at the '
        'same moment', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.tour.pause();
      h.api.queue([info('A')]);
      await h.tick();
      h.api.pollError = TourApiException('down');
      await h.tick(after: retry);

      h.tour.resume();
      await h.settle();
      expect(h.phrases.played, contains(FixedPhrase.hostUnreachable));
      expect(h.player.played, isEmpty);

      await h.tick(after: const Duration(seconds: 5));
      expect(h.player.played, ['A']);
    });

    test('a new tour starts with a healthy link', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.pollError = TourApiException('down');
      await h.tick();
      await h.tour.end();
      h.api.pollError = null;

      await h.tour.start();
      h.api.pollError = TourApiException('down');
      await h.tick(); // 沒有往返重試等待，應該立刻輪詢並再提示一次

      expect(
        h.phrases.played.where((p) => p == FixedPhrase.hostUnreachable),
        hasLength(2),
      );
    });
  });
}
