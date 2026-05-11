import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';

void main() {
  group('POI.fromJson', () {
    test('parses full POI with wiki', () {
      final json = {
        'id': 'osm:way:12345',
        'name': '國立故宮博物院',
        'lat': 25.1023,
        'lon': 121.5482,
        'tags': {'tourism': 'museum'},
        'wiki': {
          'title': '國立故宮博物院',
          'extract': '博物院位於...',
          'url': 'https://zh.wikipedia.org/wiki/...',
        },
        'distance_m': 87.5,
        'confidence': 'high',
      };
      final poi = POI.fromJson(json);
      expect(poi.id, 'osm:way:12345');
      expect(poi.name, '國立故宮博物院');
      expect(poi.wiki?.title, '國立故宮博物院');
      expect(poi.distanceM, 87.5);
      expect(poi.confidence, 'high');
    });

    test('parses POI without wiki', () {
      final json = {
        'id': 'osm:node:999',
        'name': 'Test POI',
        'lat': 25.0,
        'lon': 121.0,
        'tags': <String, dynamic>{},
        'wiki': null,
        'distance_m': 50.0,
        'confidence': 'low',
      };
      final poi = POI.fromJson(json);
      expect(poi.wiki, isNull);
    });
  });

  group('NarrationEvent', () {
    test('MetaEvent has poiId and confidence', () {
      const event = MetaEvent(
        poiId: 'osm:way:12345',
        cacheHit: false,
        confidence: 'high',
      );
      expect(event.confidence, 'high');
    });

    test('AudioEvent has base64 chunk and sentenceIdx', () {
      const event = AudioEvent(chunkB64: 'abc123', sentenceIdx: 2);
      expect(event.sentenceIdx, 2);
    });
  });
}
