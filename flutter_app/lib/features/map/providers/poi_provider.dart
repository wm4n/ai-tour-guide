import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/location/fallback_locations.dart';
import 'package:flutter_app/shared/location/haversine.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:flutter_app/shared/logging/app_logger.dart';
import 'package:flutter_app/shared/logging/log_events.dart';

const _refetchThresholdM = 250.0;

final positionStreamProvider = StreamProvider<Position>((ref) {
  return ref.watch(locationServiceProvider).positionStream;
});

/// 讀取 sessionProvider 的 lang 欄位，方便測試時 override。
final sessionLangProvider = Provider<String>((ref) {
  return ref.watch(sessionProvider.select((s) => s.lang));
});

/// GPS fallback 等待時間，預設 5 秒；測試可 override 為較短時間。
final fallbackTimeoutProvider = Provider<Duration>((ref) {
  return const Duration(seconds: 5);
});

/// 包裝 positionStreamProvider，加入語言感知的 fallback 機制：
/// 若 [fallbackTimeoutProvider] 時間內未收到 GPS，注入 [fallbackPosition(lang)]。
/// fallback 後若 GPS 恢復，繼續轉發真實位置。
final effectivePositionStreamProvider = StreamProvider<Position>((ref) {
  final lang = ref.watch(sessionLangProvider);
  final timeout = ref.watch(fallbackTimeoutProvider);
  final controller = StreamController<Position>.broadcast();
  var gotRealPosition = false;

  final timer = Timer(timeout, () {
    if (!gotRealPosition && !controller.isClosed) {
      controller.add(fallbackPosition(lang));
    }
  });

  final sub = ref.watch(locationServiceProvider).positionStream.listen(
    (pos) {
      gotRealPosition = true;
      timer.cancel();
      controller.add(pos);
    },
    onError: controller.addError,
  );

  ref.onDispose(() {
    timer.cancel();
    sub.cancel();
    controller.close();
  });

  return controller.stream;
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
