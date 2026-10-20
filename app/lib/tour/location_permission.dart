import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:permission_handler/permission_handler.dart' as handler;

/// 定位權限的程度。iPhone 放口袋、螢幕鎖定時要持續定位，最穩的是「永遠」
/// （設計文件第 13 節：定位權限要 Always）。
enum LocationAccess {
  denied,
  whileInUse,
  always;

  /// 可以開始一趟旅程（出發時 App 在前景、有背景定位指示，「使用 App 期間」也能持續更新）。
  bool get canTrack => this != denied;

  /// 螢幕鎖定、App 在背景時也確定會持續回報位置。
  bool get keepsWorkingWhenLocked => this == always;
}

abstract class LocationPermissionApi {
  Future<LocationAccess> status();
  Future<LocationAccess> requestWhenInUse();

  /// iOS 只有在已經是「使用 App 期間」之後才會跳出升級成「永遠」的詢問，而且只問一次。
  Future<LocationAccess> requestAlways();
}

/// 先要「使用 App 期間」，拿到了再請求升級成「永遠」。使用者可以只給前者：照樣能出發，
/// 呼叫端用回傳值決定要不要在畫面上提醒。升級詢問出任何錯都不影響已經拿到的權限。
Future<LocationAccess> ensureLocationAccess(LocationPermissionApi api) async {
  var access = await api.status();
  if (access == LocationAccess.denied) access = await api.requestWhenInUse();
  if (access == LocationAccess.whileInUse) {
    try {
      access = await api.requestAlways();
    } on Object catch (error) {
      debugPrint('請求「永遠」定位權限失敗（維持目前的權限）：$error');
    }
  }
  return access;
}

/// geolocator 只會要到「使用 App 期間」；升級成「永遠」要靠 permission_handler。
class PluginLocationPermissions implements LocationPermissionApi {
  static LocationAccess _fromGeolocator(LocationPermission permission) =>
      switch (permission) {
        LocationPermission.always => LocationAccess.always,
        LocationPermission.whileInUse => LocationAccess.whileInUse,
        _ => LocationAccess.denied,
      };

  @override
  Future<LocationAccess> status() async =>
      _fromGeolocator(await Geolocator.checkPermission());

  @override
  Future<LocationAccess> requestWhenInUse() async =>
      _fromGeolocator(await Geolocator.requestPermission());

  @override
  Future<LocationAccess> requestAlways() async {
    final result = await handler.Permission.locationAlways.request();
    if (result.isGranted) return LocationAccess.always;
    // 沒升級成功：看看現在實際是什麼
    return _fromGeolocator(await Geolocator.checkPermission());
  }
}
