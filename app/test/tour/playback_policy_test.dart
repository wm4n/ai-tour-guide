import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:flutter_test/flutter_test.dart';

final t0 = DateTime(2026, 10, 20, 15, 0);

// 25.0 / 121.5 往北每 0.0001 度約 11.1 公尺
PositionFix at(double metersNorth, {DateTime? time}) =>
    PositionFix(lat: 25.0 + metersNorth / 111195, lon: 121.5, time: time ?? t0);

QueuedNarration queued(
  String id, {
  double metersNorth = 0,
  int seq = 1,
  DateTime? receivedAt,
}) => QueuedNarration(
  NarrationInfo(
    seq: seq,
    id: id,
    name: id,
    lat: 25.0 + metersNorth / 111195,
    lon: 121.5,
    audioSeconds: 30,
  ),
  receivedAt ?? t0,
);

PlaybackDecision decide(
  PlaybackPolicy policy,
  List<QueuedNarration> queue, {
  PositionFix? position,
  DateTime? now,
  DateTime? lastFinishedAt,
  bool paused = false,
  bool busy = false,
}) => policy.decide(
  now: now ?? t0,
  position: position ?? at(0),
  queue: queue,
  lastFinishedAt: lastFinishedAt,
  paused: paused,
  busy: busy,
);

void main() {
  const policy = PlaybackPolicy();

  test('plays a narration once the user is close to the place', () {
    final result = decide(policy, [queued('A', metersNorth: 100)]);

    expect(result.play?.info.id, 'A');
    expect(result.drop, isEmpty);
  });

  test('does not play while the place is still far away, but keeps it', () {
    final result = decide(policy, [queued('A', metersNorth: 300)]);

    expect(result.play, isNull);
    expect(result.drop, isEmpty);
  });

  test('the nearest of several nearby places goes first', () {
    final result = decide(policy, [
      queued('far', metersNorth: 140, seq: 1),
      queued('near', metersNorth: 30, seq: 2),
    ]);

    expect(result.play?.info.id, 'near');
  });

  group('minimum gap between two narrations', () {
    final finished = t0;

    test('waits until 3 minutes after the last one finished', () {
      final queue = [queued('A')];

      final early = decide(
        policy,
        queue,
        now: finished.add(const Duration(minutes: 2, seconds: 59)),
        lastFinishedAt: finished,
      );
      final due = decide(
        policy,
        queue,
        now: finished.add(const Duration(minutes: 3)),
        lastFinishedAt: finished,
      );

      expect(early.play, isNull);
      expect(due.play?.info.id, 'A');
    });

    test('the first narration of a tour has no gap to wait for', () {
      expect(decide(policy, [queued('A')]).play, isNotNull);
    });

    test('the gap is configurable', () {
      const quick = PlaybackPolicy(minGap: Duration(seconds: 20));

      final result = decide(
        quick,
        [queued('A')],
        now: t0.add(const Duration(seconds: 20)),
        lastFinishedAt: t0,
      );

      expect(result.play, isNotNull);
    });

    test('the default gap is 3 minutes', () {
      expect(const PlaybackPolicy().minGap, const Duration(minutes: 3));
    });
  });

  group('pausing proactive narration', () {
    test('nothing is played while paused', () {
      final result = decide(policy, [queued('A')], paused: true);

      expect(result.play, isNull);
      expect(result.drop, isEmpty);
    });

    test('nothing new starts while another narration is playing', () {
      expect(decide(policy, [queued('A')], busy: true).play, isNull);
    });
  });

  group('stale narrations are dropped', () {
    test('the user has walked far away from the place', () {
      final result = decide(policy, [queued('A', metersNorth: 700)]);

      expect(result.drop.map((e) => e.info.id), ['A']);
      expect(result.play, isNull);
    });

    test('the narration is too old', () {
      final result = decide(policy, [
        queued('A', receivedAt: t0),
      ], now: t0.add(const Duration(minutes: 31)));

      expect(result.drop.map((e) => e.info.id), ['A']);
    });

    test('a stale one is dropped even while paused, and a fresh one stays', () {
      final result = decide(policy, [
        queued('old', metersNorth: 700, seq: 1),
        queued('fresh', metersNorth: 100, seq: 2),
      ], paused: true);

      expect(result.drop.map((e) => e.info.id), ['old']);
      expect(result.play, isNull);
    });

    test('a stale one never blocks a fresh one in the same decision', () {
      final result = decide(policy, [
        queued('old', metersNorth: 700, seq: 1),
        queued('fresh', metersNorth: 100, seq: 2),
      ]);

      expect(result.drop.map((e) => e.info.id), ['old']);
      expect(result.play?.info.id, 'fresh');
    });
  });

  test('without a position nothing is played or dropped', () {
    final result = policy.decide(
      now: t0,
      position: null,
      queue: [queued('A')],
      lastFinishedAt: null,
      paused: false,
      busy: false,
    );

    expect(result.play, isNull);
    expect(result.drop, isEmpty);
  });
}
