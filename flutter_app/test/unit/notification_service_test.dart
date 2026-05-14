import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/notification/notification_service.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';

void main() {
  const testPoi = POI(
    id: 'osm:test',
    name: '測試景點',
    lat: 25.1031,
    lon: 121.5482,
    tags: {},
    distanceM: 50,
    confidence: 'high',
  );

  group('FakeNotificationService', () {
    test('initCalled is false before init()', () {
      final service = FakeNotificationService();
      expect(service.initCalled, isFalse);
    });

    test('initCalled is true after init()', () async {
      final service = FakeNotificationService();
      await service.init();
      expect(service.initCalled, isTrue);
    });

    test('shownPois is empty before any showPoiTrigger()', () {
      final service = FakeNotificationService();
      expect(service.shownPois, isEmpty);
    });

    test('showPoiTrigger records the POI in shownPois', () async {
      final service = FakeNotificationService();
      await service.showPoiTrigger(testPoi);
      expect(service.shownPois, contains(testPoi));
    });

    test('showPoiTrigger accumulates multiple POIs', () async {
      final service = FakeNotificationService();
      const anotherPoi = POI(
        id: 'osm:another',
        name: '另一個景點',
        lat: 25.1040,
        lon: 121.5490,
        tags: {},
        distanceM: 80,
        confidence: 'medium',
      );
      await service.showPoiTrigger(testPoi);
      await service.showPoiTrigger(anotherPoi);
      expect(service.shownPois.length, equals(2));
    });
  });
}
