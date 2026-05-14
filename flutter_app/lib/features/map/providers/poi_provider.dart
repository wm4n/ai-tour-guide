import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

const _refetchThresholdM = 250.0;

final positionStreamProvider = StreamProvider<Position>((ref) {
  return ref.watch(locationServiceProvider).positionStream;
});

class PoiNotifier extends AsyncNotifier<List<POI>> {
  Position? _lastFetchPosition;

  @override
  Future<List<POI>> build() async {
    ref.listen<AsyncValue<Position>>(
      positionStreamProvider,
      (_, next) => next.whenData(_onPosition),
    );
    return [];
  }

  Future<void> _onPosition(Position position) async {
    if (_lastFetchPosition != null) {
      final dist = haversine(
        _lastFetchPosition!.latitude,
        _lastFetchPosition!.longitude,
        position.latitude,
        position.longitude,
      );
      if (dist < _refetchThresholdM) return;
    }
    _lastFetchPosition = position;
    AppLogger.debug(LogEvents.poiRequest, {
      'lat': position.latitude,
      'lon': position.longitude,
      'radius': 500,
    });
    state = const AsyncLoading();
    final result = await AsyncValue.guard(() =>
        ref.read(backendClientProvider).fetchNearby(
              lat: position.latitude,
              lon: position.longitude,
              radius: 500,
              lang: 'zh-TW',
              persona: 'history_uncle',
            ));
    result.whenOrNull(
      data: (pois) {
        if (pois.isEmpty) {
          AppLogger.warn(LogEvents.poiEmpty, {
            'lat': position.latitude,
            'lon': position.longitude,
            'radius': 500,
          });
        } else {
          AppLogger.info(LogEvents.poiLoaded, {'count': pois.length, 'source': 'osm'});
        }
      },
      error: (e, _) => AppLogger.error(LogEvents.apiError, {'endpoint': '/poi/nearby'}, e),
    );
    state = result;
  }
}

final poiProvider = AsyncNotifierProvider<PoiNotifier, List<POI>>(
  PoiNotifier.new,
);
