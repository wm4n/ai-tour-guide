import 'dart:async';

import 'package:flutter_compass/flutter_compass.dart';

/// 手機的指南針。拿著手機拍照、看畫面時，「眼前、左右」以它為準，不用走路的方向
/// （設計文件第 8 節第 4 點）。
abstract class CompassSource {
  /// 手機背面（鏡頭）現在對著的方向，度（0＝北，0～360）；讀不到（沒有感測器、逾時）時是 null。
  Future<double?> cameraHeading();
}

class FlutterCompassSource implements CompassSource {
  FlutterCompassSource({this.timeout = const Duration(seconds: 2)});

  final Duration timeout;

  @override
  Future<double?> cameraHeading() async {
    final events = FlutterCompass.events;
    if (events == null) return null;
    try {
      final event = await events
          .firstWhere((e) => (e.headingForCameraMode ?? e.heading) != null)
          .timeout(timeout);
      return normalizeHeading((event.headingForCameraMode ?? event.heading)!);
    } on TimeoutException {
      return null;
    } on StateError {
      return null; // 串流沒有任何讀數就結束了
    }
  }
}

/// 把角度折回 0～360（感測器有時給負數）。
double normalizeHeading(double degrees) => (degrees % 360 + 360) % 360;

/// 開發用：固定的方向（模擬器沒有指南針）。
class FixedCompassSource implements CompassSource {
  FixedCompassSource(this.degrees);

  final double degrees;

  @override
  Future<double?> cameraHeading() async => degrees;
}
