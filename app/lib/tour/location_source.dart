import 'dart:async';

import 'location_permission.dart';

/// 一次原始定位，尚未加上行進方向；時間由控制器補上。
class RawFix {
  const RawFix(this.lat, this.lon);

  final double lat;
  final double lon;
}

abstract class LocationSource {
  /// 要求定位權限（先「使用 App 期間」，再請求升級成「永遠」）；使用者拒絕時回傳 false。
  Future<bool> ensurePermission();

  /// 最近一次 [ensurePermission] 之後拿到的權限程度；畫面用它提醒「鎖定螢幕時可能中斷」。
  LocationAccess get access;

  Future<RawFix?> current();

  /// 持續的位置串流（背景也要持續）。
  Stream<RawFix> positions();
}
