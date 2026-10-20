import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';

import 'location_source.dart';

class GeolocatorLocationSource implements LocationSource {
  /// iOS 背景定位：要有 `UIBackgroundModes: location`；關掉自動暫停，
  /// 否則靜止一陣子後系統會停止回報，走起來也不會再更新。
  static LocationSettings get _settings =>
      defaultTargetPlatform == TargetPlatform.iOS
      ? AppleSettings(
          accuracy: LocationAccuracy.best,
          activityType: ActivityType.fitness,
          distanceFilter: 5,
          pauseLocationUpdatesAutomatically: false,
          showBackgroundLocationIndicator: true,
          allowBackgroundLocationUpdates: true,
        )
      : const LocationSettings(
          accuracy: LocationAccuracy.best,
          distanceFilter: 5,
        );

  @override
  Future<bool> ensurePermission() async {
    var permission = await Geolocator.checkPermission();
    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }
    return permission == LocationPermission.whileInUse ||
        permission == LocationPermission.always;
  }

  @override
  Future<RawFix?> current() async {
    try {
      final position = await Geolocator.getCurrentPosition(
        locationSettings: _settings,
      );
      return RawFix(position.latitude, position.longitude);
    } on Exception catch (error) {
      debugPrint('取得目前位置失敗：$error');
      return null;
    }
  }

  @override
  Stream<RawFix> positions() => Geolocator.getPositionStream(
    locationSettings: _settings,
  ).map((p) => RawFix(p.latitude, p.longitude));
}
