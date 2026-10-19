import 'package:buddy_tour/tour/host_reachability.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  final t0 = DateTime(2026, 10, 20, 15, 0);

  test('starts reachable and may always try', () {
    final link = HostReachability();

    expect(link.reachable, isTrue);
    expect(link.canTry(t0), isTrue);
  });

  test('only the first failure of an outage is reported as a new outage', () {
    final link = HostReachability();

    expect(link.recordFailure(t0), isTrue);
    expect(link.reachable, isFalse);
    expect(link.recordFailure(t0.add(const Duration(seconds: 10))), isFalse);
    expect(link.recordFailure(t0.add(const Duration(seconds: 30))), isFalse);
  });

  test('retry delay doubles after each failure and stops at the cap', () {
    final link = HostReachability(
      firstDelay: const Duration(seconds: 10),
      maxDelay: const Duration(seconds: 60),
    );
    final delays = <int>[];
    var now = t0;
    for (var i = 0; i < 6; i++) {
      link.recordFailure(now);
      // 找出最早可以重試的時間
      var seconds = 0;
      while (!link.canTry(now.add(Duration(seconds: seconds)))) {
        seconds++;
      }
      delays.add(seconds);
      now = now.add(Duration(seconds: seconds));
    }

    expect(delays, [10, 20, 40, 60, 60, 60]);
  });

  test('does not allow a retry before the delay has passed', () {
    final link = HostReachability(firstDelay: const Duration(seconds: 10));

    link.recordFailure(t0);

    expect(link.canTry(t0.add(const Duration(seconds: 9))), isFalse);
    expect(link.canTry(t0.add(const Duration(seconds: 10))), isTrue);
  });

  test('a success after an outage is reported once and resets the backoff', () {
    final link = HostReachability(firstDelay: const Duration(seconds: 10));
    link.recordFailure(t0);
    link.recordFailure(t0.add(const Duration(seconds: 10)));

    expect(link.recordSuccess(), isTrue);
    expect(link.reachable, isTrue);
    expect(link.recordSuccess(), isFalse);

    // 下一次斷線又從最短的間隔開始，而且會再被當成新的斷線
    final later = t0.add(const Duration(minutes: 5));
    expect(link.recordFailure(later), isTrue);
    expect(link.canTry(later.add(const Duration(seconds: 10))), isTrue);
    expect(link.canTry(later.add(const Duration(seconds: 9))), isFalse);
  });
}
