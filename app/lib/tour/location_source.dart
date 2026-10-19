import 'dart:async';

/// 一次原始定位，尚未加上行進方向；時間由控制器補上。
class RawFix {
  const RawFix(this.lat, this.lon);

  final double lat;
  final double lon;
}

abstract class LocationSource {
  /// 要求定位權限；使用者拒絕時回傳 false。
  Future<bool> ensurePermission();

  Future<RawFix?> current();

  /// 持續的位置串流（背景也要持續）。
  Stream<RawFix> positions();
}
