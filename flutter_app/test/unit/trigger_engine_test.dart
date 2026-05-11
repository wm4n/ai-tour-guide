import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';

POI _poi(String id, double lat, double lon) => POI(
      id: id,
      name: 'Test POI $id',
      lat: lat,
      lon: lon,
      tags: {},
      distanceM: 0,
      confidence: 'medium',
    );

void main() {
  const userLat = 25.1023;
  const userLon = 121.5482;

  group('TriggerEngine.evaluate', () {
    test('returns POI within 100m trigger radius', () {
      // ~89m north of user
      final poi = _poi('a', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {},
      );
      expect(triggers, [poi]);
    });

    test('excludes POI outside 100m radius', () {
      // ~200m north of user
      final poi = _poi('b', 25.1041, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {},
      );
      expect(triggers, isEmpty);
    });

    test('excludes POI already played in this session', () {
      final poi = _poi('c', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {'c'},
        cooldownPoiIds: {},
      );
      expect(triggers, isEmpty);
    });

    test('excludes POI in cooldown', () {
      final poi = _poi('d', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {'d'},
      );
      expect(triggers, isEmpty);
    });

    test('returns only qualifying POIs from mixed list', () {
      final near = _poi('near', 25.1031, 121.5482);     // ~89m, qualifies
      final far = _poi('far', 25.1041, 121.5482);       // ~200m, excluded
      final played = _poi('played', 25.1031, 121.5482); // near but played
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [near, far, played],
        playedPoiIds: {'played'},
        cooldownPoiIds: {},
      );
      expect(triggers.map((p) => p.id).toList(), ['near']);
    });
  });
}
