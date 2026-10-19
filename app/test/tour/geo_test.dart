import 'package:buddy_tour/tour/geo.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('haversineM', () {
    test('same point is zero', () {
      expect(haversineM(25.05, 121.51, 25.05, 121.51), 0);
    });

    test('0.001 degree of latitude is about 111 m', () {
      expect(haversineM(25.0, 121.5, 25.001, 121.5), closeTo(111.2, 0.5));
    });
  });

  group('bearingDeg', () {
    test('north, east, south, west', () {
      expect(bearingDeg(25.0, 121.5, 25.01, 121.5), closeTo(0, 0.01));
      expect(bearingDeg(25.0, 121.5, 25.0, 121.51), closeTo(90, 0.1));
      expect(bearingDeg(25.0, 121.5, 24.99, 121.5), closeTo(180, 0.01));
      expect(bearingDeg(25.0, 121.5, 25.0, 121.49), closeTo(270, 0.1));
    });
  });

  group('HeadingTracker', () {
    test('has no heading until the user has really moved', () {
      final tracker = HeadingTracker(minMoveM: 10);

      expect(tracker.update(25.0, 121.5), isNull);
      expect(tracker.update(25.00003, 121.5), isNull); // 約 3 公尺：GPS 抖動
    });

    test('computes the heading from two fixes far enough apart', () {
      final tracker = HeadingTracker(minMoveM: 10)..update(25.0, 121.5);

      expect(tracker.update(25.0002, 121.5), closeTo(0, 0.5));
    });

    test('keeps the last heading while the user stands still', () {
      final tracker = HeadingTracker(minMoveM: 10)
        ..update(25.0, 121.5)
        ..update(25.0, 121.5003); // 往東

      expect(tracker.update(25.0, 121.50031), closeTo(90, 1));
    });

    test('measures from the last accepted fix, not the previous jitter', () {
      final tracker = HeadingTracker(minMoveM: 10)..update(25.0, 121.5);
      tracker.update(25.00003, 121.5); // 抖動，不採用
      tracker.update(25.00006, 121.5); // 累計 6.6 公尺，還不夠

      expect(tracker.update(25.00012, 121.5), closeTo(0, 0.5));
    });
  });
}
