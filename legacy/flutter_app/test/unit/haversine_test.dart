import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/location/haversine.dart';

void main() {
  group('haversine', () {
    test('returns 0 for same point', () {
      expect(haversine(25.1023, 121.5482, 25.1023, 121.5482), 0.0);
    });

    test('returns ~111km for 1 degree latitude difference', () {
      final dist = haversine(0.0, 0.0, 1.0, 0.0);
      expect(dist, closeTo(111195, 100));
    });

    test('returns ~87m for two nearby points', () {
      // Palace Museum to a nearby point ~87m north
      final dist = haversine(25.1023, 121.5482, 25.1031, 121.5482);
      expect(dist, closeTo(89, 5));
    });

    test('returns value within trigger radius for 50m apart', () {
      final dist = haversine(25.1023, 121.5482, 25.10275, 121.5482);
      expect(dist, lessThan(100.0));
    });

    test('returns value outside trigger radius for 200m apart', () {
      final dist = haversine(25.1023, 121.5482, 25.1041, 121.5482);
      expect(dist, greaterThan(100.0));
    });
  });
}
