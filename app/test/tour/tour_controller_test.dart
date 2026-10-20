import 'dart:async';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/audio/remote_controls.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/tour/location_permission.dart';
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
  group('location access', () {
    test('the tour remembers how much access it got', () async {
      final h = await makeHarness();
      h.location.access = LocationAccess.whileInUse;

      await h.tour.start();

      expect(h.state.locationAccess, LocationAccess.whileInUse);
    });

    test('coming back to the app picks up a change made in Settings', () async {
      final h = await makeHarness();
      h.location.access = LocationAccess.whileInUse;
      await h.tour.start();
      expect(h.state.locationAccess, LocationAccess.whileInUse);

      h.location.access = LocationAccess.always; // 使用者到「設定」改成永遠
      await h.tour.refreshLocationAccess();

      expect(h.state.locationAccess, LocationAccess.always);
    });

    test('refreshing without a tour changes nothing', () async {
      final h = await makeHarness();

      await h.tour.refreshLocationAccess();

      expect(h.state.active, isFalse);
    });

    test('always is the default and needs no warning', () async {
      final h = await makeHarness();

      await h.tour.start();

      expect(h.state.locationAccess.keepsWorkingWhenLocked, isTrue);
    });
  });

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

  group('telling the host what was heard', () {
    test('a narration that played to the end is reported as told', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.queue([info('A')]);
      await h.tick();
      expect(h.api.played, isEmpty); // 還在播，還不算講過

      h.player.finish();
      await h.settle();

      expect(h.api.played, ['A']);
    });

    test(
      'a narration dropped as stale was never heard, so not reported',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.api.queue([info('A')]);
        await h.tick(); // 人在很遠的地方，不會播

        await h.tick(after: const Duration(hours: 1)); // 放太久被丟掉

        expect(h.api.played, isEmpty);
      },
    );

    test(
      'ending in the middle of a narration does not count it as told',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();

        await h.tour.end();
        await h.settle();

        expect(h.api.played, isEmpty);
      },
    );

    test('reports the host keeps refusing do not pile up forever', () async {
      final h = await makeHarness();
      await h.tour.start();
      await h.moveTo(nearFix());
      h.api.playedError = TourApiException('500');

      for (var i = 0; i < 30; i++) {
        h.api.queue([info('N$i', seq: i + 1)]);
        await h.tick(after: const Duration(minutes: 5));
        h.player.finish();
        await h.settle();
      }
      expect(h.player.played, hasLength(30));

      h.api.playedError = null;
      await h.tick(after: const Duration(minutes: 5));
      await h.settle();

      expect(h.api.played.length, lessThanOrEqualTo(20)); // 只留最近的
      expect(h.api.played.last, 'N29');
    });

    test(
      'a report that could not be sent is sent again once the host is back',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.queue([info('A')]);
        await h.tick();
        h.api.playedError = TourApiException('down');
        h.player.finish();
        await h.settle();
        expect(h.api.played, isEmpty);

        h.api.playedError = null;
        await h.tick(after: const Duration(minutes: 1));
        await h.settle();

        expect(h.api.played, ['A']);

        await h.tick(after: const Duration(minutes: 1));
        expect(h.api.played, ['A']); // 送過就不再送
      },
    );
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

    test(
      'a narration the host no longer has is dropped, not retried',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.downloadError = TourApiException('gone', statusCode: 404);
        h.api.queue([info('A')]);

        await h.tick();
        final downloads = h.api.downloads.length;
        for (var i = 0; i < 5; i++) {
          await h.tick(after: const Duration(seconds: 15));
        }

        expect(h.api.downloads.length, downloads); // 不再重抓
        expect(h.player.played, isEmpty);
        expect(
          h.phrases.played.where((p) => p == FixedPhrase.hostUnreachable),
          isEmpty, // 主機還在，只是這段不在了：不是斷線
        );
      },
    );

    test(
      'a server error on the download is still treated as an outage',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        await h.moveTo(nearFix());
        h.api.downloadError = TourApiException('boom', statusCode: 503);
        h.api.queue([info('A')]);
        await h.tick();
        h.api.downloadError = null;

        await h.tick(after: retry);

        expect(h.player.played, ['A']);
      },
    );

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

  group('while a question is being asked', () {
    test(
      'a narration that is ready waits until the question is over',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.api.queue([info('A')]);
        await h.moveTo(nearFix());

        h.tour.beginQuestion();
        await h.tick();
        expect(h.player.played, isEmpty);

        h.tour.endQuestion();
        await h.tick();
        expect(h.player.played, ['A']);
      },
    );

    test(
      'overlapping questions only release the hold when all are done',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.api.queue([info('A')]);
        await h.moveTo(nearFix());

        h.tour.beginQuestion();
        h.tour.beginQuestion();
        h.tour.endQuestion();
        await h.tick();
        expect(h.player.played, isEmpty);

        h.tour.endQuestion();
        await h.tick();
        expect(h.player.played, ['A']);
      },
    );

    test('ending the tour clears the hold for the next tour', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.tour.beginQuestion();
      await h.tour.end();

      await h.tour.start();
      h.api.queue([info('A')]);
      await h.moveTo(nearFix());
      await h.tick();

      expect(h.player.played, ['A']);
    });

    test(
      'the unreachable phrase waits too, so it does not talk over an answer',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.tour.beginQuestion();
        h.api.pollError = TourApiException('down');

        await h.tick();
        expect(h.phrases.played, [FixedPhrase.startTour]);

        h.tour.endQuestion();
        await h.tick(after: const Duration(seconds: 70));
        expect(h.phrases.played, contains(FixedPhrase.hostUnreachable));
      },
    );
  });

  group('the host failing during a question', () {
    test('counts as an outage: the unreachable phrase is said once', () async {
      final h = await makeHarness();
      await h.tour.start();

      h.tour.noteHostFailed();
      h.tour.noteHostFailed();
      await h.tick();

      expect(
        h.phrases.played.where((p) => p == FixedPhrase.hostUnreachable),
        hasLength(1),
      );
    });

    test('reaching the host again ends the outage quietly', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.tour.noteHostFailed();
      await h.tick();
      final spoken = h.phrases.played.length;

      h.tour.noteHostReached();
      await h.tick();

      expect(h.phrases.played, hasLength(spoken));
    });

    test('exposes the latest position for questions', () async {
      final h = await makeHarness();
      expect(h.tour.position, isNull);
      await h.tour.start();
      await h.moveTo(nearFix());

      expect(h.tour.position!.lat, closeTo(nearFix().lat, 1e-9));
    });
  });

  group('a question interrupting a narration', () {
    NarrationInfo withStarts(String id) => NarrationInfo(
      seq: 1,
      id: id,
      name: '景點$id',
      lat: placeLat,
      lon: placeLon,
      audioSeconds: 30,
      unitStarts: const [0.0, 1.5, 3.5],
    );

    Future<Harness> playing() async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.queue([withStarts('A')]);
      await h.moveTo(nearFix());
      await h.tick();
      expect(h.player.played, ['A']);
      return h;
    }

    Duration at(double seconds) =>
        Duration(microseconds: (seconds * 1000000).round());

    test(
      'stops the narration and, after the answer, resumes from the start of the interrupted sentence',
      () async {
        final h = await playing();
        h.player.positionNow = at(2.0); // 第二句講到一半

        h.tour.beginQuestion();
        await h.settle();
        // 不釋放 audio focus：緊接著要念短句、播答案，其他 App 的音量不要在中間跳回來
        expect(h.player.events, contains('stop(keep focus)'));

        h.tour.endQuestion();
        await h.settle();

        expect(h.player.played, ['A', 'A']);
        expect(h.player.starts, [Duration.zero, at(1.5)]);
      },
    );

    test(
      'interrupted exactly at a sentence boundary resumes at that boundary',
      () async {
        final h = await playing();
        h.player.positionNow = at(3.5);

        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion();
        await h.settle();

        expect(h.player.starts.last, at(3.5));
      },
    );

    test(
      'is not counted as told until the resumed playback reaches the end',
      () async {
        final h = await playing();
        h.player.positionNow = at(2.0);
        h.tour.beginQuestion();
        await h.settle();
        expect(h.api.played, isEmpty); // 被打斷不算講過

        h.tour.endQuestion();
        await h.settle();
        expect(h.api.played, isEmpty); // 接著播的時候也還沒播完

        h.player.finish();
        await h.settle();
        expect(h.api.played, ['A']);
      },
    );

    test(
      'nothing else starts while it waits for the answer, and the status still shows it',
      () async {
        final h = await playing();
        h.api.queue([
          NarrationInfo(
            seq: 2,
            id: 'B',
            name: '景點B',
            lat: placeLat,
            lon: placeLon,
            audioSeconds: 30,
          ),
        ]);
        h.player.positionNow = at(2.0);

        h.tour.beginQuestion();
        await h.tick();

        expect(h.player.played, ['A']);
        expect(h.state.nowPlaying, '景點A');
      },
    );

    test(
      'a second question while resumed interrupts again from the new position',
      () async {
        final h = await playing();
        h.player.positionNow = at(2.0);
        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion();
        await h.settle();

        h.player.positionNow = at(4.0); // 接著播之後又被打斷
        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion();
        await h.settle();

        expect(h.player.starts, [Duration.zero, at(1.5), at(3.5)]);
        expect(h.api.played, isEmpty);
      },
    );

    test('with no narration playing a question changes nothing', () async {
      final h = await makeHarness();
      await h.tour.start();

      h.tour.beginQuestion();
      await h.settle();
      h.tour.endQuestion();
      await h.settle();

      expect(h.player.events, isEmpty);
      expect(h.player.played, isEmpty);
    });

    test(
      'when the tour is paused it stays paused until the user resumes',
      () async {
        final h = await playing();
        h.tour.pause();
        h.player.positionNow = at(2.0);

        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion();
        await h.settle();
        expect(h.player.played, ['A']); // 使用者要安靜：答完也不自己接著講

        h.tour.resume();
        await h.settle();
        expect(h.player.played, ['A', 'A']);
        expect(h.player.starts.last, at(1.5));
      },
    );

    test(
      'ending the tour while waiting for the answer drops the interrupted narration',
      () async {
        final h = await playing();
        h.player.positionNow = at(2.0);
        h.tour.beginQuestion();
        await h.settle();

        await h.tour.end();
        h.tour.endQuestion();
        await h.settle();

        expect(h.player.played, ['A']);
        expect(h.api.played, isEmpty);
      },
    );

    test(
      'a narration that is still being fetched waits for the answer instead of talking over it',
      () async {
        final h = await makeHarness();
        await h.tour.start();
        h.api.downloadGate = Completer<void>();
        h.api.queue([withStarts('A')]);
        await h.moveTo(nearFix());
        await h.tick();

        h.tour.beginQuestion();
        h.api.downloadGate!.complete();
        await h.settle();
        expect(h.player.played, isEmpty);

        h.tour.endQuestion();
        await h.tick();
        expect(h.player.played, ['A']);
        expect(h.player.starts, [Duration.zero]);
      },
    );

    test('without sentence starts it resumes where it was cut off', () async {
      final h = await makeHarness();
      await h.tour.start();
      h.api.queue([info('A')]); // 舊主機：沒有各句起點
      await h.moveTo(nearFix());
      await h.tick();
      h.player.positionNow = at(7.25);

      h.tour.beginQuestion();
      await h.settle();
      h.tour.endQuestion();
      await h.settle();

      expect(h.player.starts.last, at(7.25));
    });

    test(
      'an answer that is over almost at once still resumes exactly once and keeps others waiting',
      () async {
        final h = await playing();
        h.api.queue([
          NarrationInfo(
            seq: 2,
            id: 'B',
            name: '景點B',
            lat: placeLat,
            lon: placeLon,
            audioSeconds: 30,
          ),
        ]);
        h.player.positionNow = at(2.0);

        h.tour.beginQuestion();
        h.tour.endQuestion(); // 問題極短或辨識為空：幾乎馬上就答完了
        await h.settle();
        await h.tick();

        expect(h.player.played, ['A', 'A']);
        expect(h.player.starts.last, at(1.5));
        expect(h.state.nowPlaying, '景點A'); // 還在講 A，B 不能疊上來

        h.player.finish();
        await h.settle();
        expect(h.api.played, ['A']);
      },
    );

    test(
      'a narration that finishes at the very moment a question starts is not played again',
      () async {
        final h = await playing();

        h.player.finish();
        h.tour.beginQuestion(); // 同一刻
        await h.settle();
        h.tour.endQuestion();
        await h.settle();

        expect(h.player.played, ['A']);
        expect(h.api.played, ['A']);
        expect(h.state.nowPlaying, isNull);
      },
    );

    test(
      'a second question while already waiting does not move the resume point',
      () async {
        final h = await playing();
        h.tour.pause();
        h.player.positionNow = at(2.0);
        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion(); // 暫停中：不自己接著講，接續點留著
        await h.settle();

        h.player.positionNow = Duration.zero; // 播放器已經停了，位置不可靠
        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion();
        await h.settle();
        h.tour.resume();
        await h.settle();

        expect(h.player.starts.last, at(1.5));
      },
    );

    test(
      'a finished narration is reported once and the gap rule starts from then',
      () async {
        final h = await playing();
        h.player.positionNow = at(2.0);
        h.tour.beginQuestion();
        await h.settle();
        h.tour.endQuestion();
        await h.settle();

        h.player.finish();
        await h.settle();

        expect(h.api.played, ['A']);
        expect(h.state.nowPlaying, isNull);
      },
    );
  });
}
