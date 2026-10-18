import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/location/fallback_locations.dart';

void main() {
  test('fallbackPosition(zh-TW) returns 故宮博物院 coordinates', () {
    final pos = fallbackPosition('zh-TW');
    expect(pos.latitude, closeTo(25.1023, 0.001));
    expect(pos.longitude, closeTo(121.5484, 0.001));
  });

  test('fallbackPosition(en) returns Smithsonian coordinates', () {
    final pos = fallbackPosition('en');
    expect(pos.latitude, closeTo(38.8882, 0.001));
    expect(pos.longitude, closeTo(-77.0197, 0.001));
  });

  test('fallbackPosition(unknown) defaults to en coordinates', () {
    final pos = fallbackPosition('fr');
    expect(pos.latitude, closeTo(38.8882, 0.001));
    expect(pos.longitude, closeTo(-77.0197, 0.001));
  });
}
