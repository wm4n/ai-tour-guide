import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  const fakePois = [
    POI(
      id: 'osm:1',
      name: '故宮',
      lat: 25.1023,
      lon: 121.5482,
      tags: {},
      distanceM: 87,
      confidence: 'high',
    ),
  ];

  test('PoiProvider returns pois from BackendClient on position update',
      () async {
    final fakeLocation = FakeLocationService();
    const fakeClient = FakeBackendClient(nearbyPois: fakePois);
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(fakeClient),
      ],
    );
    addTearDown(container.dispose);

    // Initialize the provider so the stream listener is set up
    container.read(poiProvider);
    // Allow build() to complete
    await Future<void>.delayed(const Duration(milliseconds: 50));

    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    // Allow async fetch to complete
    await Future<void>.delayed(const Duration(milliseconds: 100));

    final state = container.read(poiProvider);
    expect(state.value, fakePois);
  });
}
