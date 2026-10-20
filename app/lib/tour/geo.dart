import 'dart:math' as math;

const _earthRadiusM = 6371000.0;

double _rad(double deg) => deg * math.pi / 180;

double haversineM(double lat1, double lon1, double lat2, double lon2) {
  final p1 = _rad(lat1);
  final p2 = _rad(lat2);
  final dp = _rad(lat2 - lat1);
  final dl = _rad(lon2 - lon1);
  final a =
      math.pow(math.sin(dp / 2), 2) +
      math.cos(p1) * math.cos(p2) * math.pow(math.sin(dl / 2), 2);
  return 2 * _earthRadiusM * math.asin(math.sqrt(a));
}

/// 從點 1 看向點 2 的方位角，0＝北、順時針。
double bearingDeg(double lat1, double lon1, double lat2, double lon2) {
  final p1 = _rad(lat1);
  final p2 = _rad(lat2);
  final dl = _rad(lon2 - lon1);
  final y = math.sin(dl) * math.cos(p2);
  final x =
      math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl);
  return (math.atan2(y, x) * 180 / math.pi + 360) % 360;
}

/// 用前後兩個定位點自己算行進方向：模擬器與靜止時，系統給的 course 常常不可信。
/// 移動不到 [minMoveM] 就沿用上一次的方向，避免 GPS 抖動讓方向亂跳。
class HeadingTracker {
  HeadingTracker({this.minMoveM = 10});

  final double minMoveM;
  double? _anchorLat;
  double? _anchorLon;
  double? _heading;

  double? update(double lat, double lon) {
    final anchorLat = _anchorLat;
    final anchorLon = _anchorLon;
    if (anchorLat == null || anchorLon == null) {
      _anchorLat = lat;
      _anchorLon = lon;
      return null;
    }
    if (haversineM(anchorLat, anchorLon, lat, lon) >= minMoveM) {
      _heading = bearingDeg(anchorLat, anchorLon, lat, lon);
      _anchorLat = lat;
      _anchorLon = lon;
    }
    return _heading;
  }
}
