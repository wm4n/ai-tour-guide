import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  test('defaults: walking, solo, no children', () {
    const state = TravelerState();

    expect(state.mode, TravelMode.walking);
    expect(state.companions, Companions.solo);
    expect(state.withChildren, isFalse);
  });

  test('json uses the names the host expects', () {
    const state = TravelerState(
      mode: TravelMode.driving,
      companions: Companions.family,
      withChildren: true,
    );

    expect(state.toJson(), {
      'mode': 'driving',
      'companions': 'family',
      'with_children': true,
    });
  });

  group('isoWithOffset', () {
    test('keeps the wall clock and appends the UTC offset', () {
      final taipei = DateTime.parse('2026-10-20T15:04:09+08:00');

      expect(
        isoWithOffset(taipei, offset: const Duration(hours: 8)),
        '2026-10-20T15:04:09+08:00',
      );
    });

    test('negative and half-hour offsets', () {
      final base = DateTime.utc(2026, 10, 20, 0, 0, 0);

      expect(
        isoWithOffset(base, offset: const Duration(hours: -5, minutes: -30)),
        '2026-10-19T18:30:00-05:30',
      );
    });
  });

  group('TravelerStore', () {
    test('nothing stored → defaults', () async {
      SharedPreferences.setMockInitialValues({});
      final store = TravelerStore(await SharedPreferences.getInstance());

      expect(store.load().companions, Companions.solo);
    });

    test('saved choices come back', () async {
      SharedPreferences.setMockInitialValues({});
      final store = TravelerStore(await SharedPreferences.getInstance());

      await store.save(
        const TravelerState(
          mode: TravelMode.driving,
          companions: Companions.couple,
          withChildren: true,
        ),
      );

      final loaded = store.load();
      expect(loaded.mode, TravelMode.driving);
      expect(loaded.companions, Companions.couple);
      expect(loaded.withChildren, isTrue);
    });

    test('an unknown stored value falls back to the default', () async {
      SharedPreferences.setMockInitialValues({'traveler.mode': 'flying'});
      final store = TravelerStore(await SharedPreferences.getInstance());

      expect(store.load().mode, TravelMode.walking);
    });
  });
}
