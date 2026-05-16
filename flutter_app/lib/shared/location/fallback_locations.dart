import 'package:flutter_app/shared/location/location_service.dart';
import 'package:geolocator/geolocator.dart';

const _kFallbackZhTW = (lat: 25.1023, lon: 121.5484);
const _kFallbackEn = (lat: 38.8882, lon: -77.0197);

/// 根據語言回傳對應的 fallback 位置。
/// zh-TW → 台北故宮博物院 (25.1023°N, 121.5484°E)
/// en（或其他）→ Smithsonian National Air and Space Museum (38.8882°N, -77.0197°W)
Position fallbackPosition(String lang) {
  final coords = lang == 'zh-TW' ? _kFallbackZhTW : _kFallbackEn;
  return fakePosition(coords.lat, coords.lon);
}
