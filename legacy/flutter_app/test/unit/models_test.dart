import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';

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

    test('parses foodie POI with rating fields', () {
      final json = {
        'id': 'gplace:ChIJ001',
        'name': '鼎泰豐',
        'lat': 25.033,
        'lon': 121.564,
        'tags': <String, dynamic>{},
        'wiki': null,
        'distance_m': 47.3,
        'confidence': 'high',
        'rating': 4.6,
        'user_ratings_total': 328,
        'price_level': 2,
        'place_types': ['restaurant', 'food'],
        'vicinity': '信義區松高路12號',
      };
      final poi = POI.fromJson(json);
      expect(poi.rating, 4.6);
      expect(poi.userRatingsTotal, 328);
      expect(poi.priceLevel, 2);
      expect(poi.placeTypes, ['restaurant', 'food']);
      expect(poi.vicinity, '信義區松高路12號');
    });

    test('non-foodie POI has null foodie fields', () {
      final json = {
        'id': 'osm:way:12345',
        'name': '故宮博物院',
        'lat': 25.1023,
        'lon': 121.5482,
        'tags': <String, dynamic>{},
        'wiki': null,
        'distance_m': 87.5,
        'confidence': 'high',
      };
      final poi = POI.fromJson(json);
      expect(poi.rating, isNull);
      expect(poi.userRatingsTotal, isNull);
      expect(poi.priceLevel, isNull);
      expect(poi.placeTypes, isNull);
      expect(poi.vicinity, isNull);
    });
  });

  group('NarrationEvent', () {
    test('MetaEvent.fromJson parses all fields', () {
      final event = MetaEvent.fromJson({
        'poi_id': 'osm:way:12345',
        'cache_hit': false,
        'confidence': 'high',
        'estimated_duration_s': 30,
      });
      expect(event.confidence, 'high');
      expect(event.estimatedDurationS, 30);
      expect(event.cacheHit, isFalse);
    });

    test('MetaEvent.estimatedDurationS defaults to 0', () {
      final event = MetaEvent.fromJson({
        'poi_id': 'abc',
        'cache_hit': true,
        'confidence': 'low',
      });
      expect(event.estimatedDurationS, 0);
    });

    test('TextEvent.fromJson parses chunk and sentenceIdx', () {
      final event = TextEvent.fromJson({'chunk': 'Hello', 'sentence_idx': 1});
      expect(event.chunk, 'Hello');
      expect(event.sentenceIdx, 1);
    });

    test('AudioEvent has base64 chunk and sentenceIdx', () {
      const event = AudioEvent(chunkB64: 'abc123', sentenceIdx: 2);
      expect(event.sentenceIdx, 2);
    });

    test('EndEvent constructs with no fields', () {
      const event = EndEvent();
      expect(event, isA<NarrationEvent>());
    });

    test('ErrorEvent.fromJson parses retry_after_s', () {
      final event = ErrorEvent.fromJson({
        'code': 'RATE_LIMITED',
        'message': 'Too many requests',
        'retry_after_s': 30,
      });
      expect(event.code, 'RATE_LIMITED');
      expect(event.retryAfterS, 30);
    });
  });

  group('QaEvent', () {
    test('TranscriptQaEvent.fromJson', () {
      final e = TranscriptQaEvent.fromJson({'text': '這是問題'});
      expect(e.text, '這是問題');
    });

    test('TextQaEvent.fromJson', () {
      final e = TextQaEvent.fromJson({'chunk': '回答', 'sentence_idx': 0});
      expect(e.chunk, '回答');
      expect(e.sentenceIdx, 0);
    });

    test('AudioQaEvent.fromJson', () {
      final e = AudioQaEvent.fromJson({'chunk_b64': 'AAAA', 'sentence_idx': 1});
      expect(e.chunkB64, 'AAAA');
      expect(e.sentenceIdx, 1);
    });

    test('ErrorQaEvent.fromJson', () {
      final e = ErrorQaEvent.fromJson({'code': 'stt_error', 'message': 'timeout'});
      expect(e.code, 'stt_error');
    });
  });
}
