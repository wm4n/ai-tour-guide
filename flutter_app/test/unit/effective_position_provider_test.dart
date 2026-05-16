import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

void main() {
  test('forwards GPS position when it arrives before timeout', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 500)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.microtask(() {});

    fakeLocation.emit(fakePosition(1.0, 2.0));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(positions, hasLength(1));
    expect(positions.first.latitude, 1.0);
    expect(positions.first.longitude, 2.0);
  });

  test('emits zh-TW fallback after timeout when no GPS arrives', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 100)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.delayed(const Duration(milliseconds: 250));

    expect(positions, hasLength(1));
    expect(positions.first.latitude, closeTo(25.1023, 0.001));
    expect(positions.first.longitude, closeTo(121.5484, 0.001));
  });

  test('emits en fallback after timeout when no GPS arrives', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('en'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 100)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.delayed(const Duration(milliseconds: 250));

    expect(positions, hasLength(1));
    expect(positions.first.latitude, closeTo(38.8882, 0.001));
    expect(positions.first.longitude, closeTo(-77.0197, 0.001));
  });

  test('continues forwarding GPS positions after fallback was emitted', () async {
    final fakeLocation = FakeLocationService();
    final container = ProviderContainer(overrides: [
      locationServiceProvider.overrideWithValue(fakeLocation),
      sessionLangProvider.overrideWithValue('zh-TW'),
      fallbackTimeoutProvider.overrideWithValue(const Duration(milliseconds: 100)),
    ]);
    addTearDown(container.dispose);

    final positions = <Position>[];
    container.listen<AsyncValue<Position>>(
      effectivePositionStreamProvider,
      (_, next) => next.whenData(positions.add),
      fireImmediately: true,
    );
    await Future<void>.delayed(const Duration(milliseconds: 250));
    expect(positions, hasLength(1));

    fakeLocation.emit(fakePosition(1.0, 2.0));
    await Future<void>.delayed(const Duration(milliseconds: 50));

    expect(positions, hasLength(2));
    expect(positions.last.latitude, 1.0);
  });
}
