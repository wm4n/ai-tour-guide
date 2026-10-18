import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:permission_handler/permission_handler.dart';

/// Abstract interface for local notification services.
abstract class NotificationService {
  Future<void> init();
  Future<bool> hasNotificationPermission();
  Future<void> showPoiTrigger(POI poi);
}

/// Fake implementation for tests — records all calls without side effects.
class FakeNotificationService implements NotificationService {
  FakeNotificationService({this.hasPermission = true});

  bool initCalled = false;
  final bool hasPermission;
  final List<POI> shownPois = [];

  @override
  Future<void> init() async {
    initCalled = true;
  }

  @override
  Future<bool> hasNotificationPermission() async => hasPermission;

  @override
  Future<void> showPoiTrigger(POI poi) async {
    shownPois.add(poi);
  }
}

/// Real implementation using flutter_local_notifications.
class RealNotificationService implements NotificationService {
  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  @override
  Future<void> init() async {
    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: true,
      requestSoundPermission: true,
    );
    const settings = InitializationSettings(
      android: androidSettings,
      iOS: iosSettings,
    );
    await _plugin.initialize(settings);
  }

  @override
  Future<bool> hasNotificationPermission() async {
    final status = await Permission.notification.status;
    return status.isGranted || status.isLimited;
  }

  @override
  Future<void> showPoiTrigger(POI poi) async {
    const androidDetails = AndroidNotificationDetails(
      'poi_trigger',
      'POI Trigger',
      channelDescription: '附近景點提醒',
      importance: Importance.high,
      priority: Priority.high,
    );
    const iosDetails = DarwinNotificationDetails();
    const details = NotificationDetails(
      android: androidDetails,
      iOS: iosDetails,
    );
    await _plugin.show(
      poi.id.hashCode,
      '附近景點：${poi.name}',
      '您正在 ${poi.distanceM.toInt()} 公尺內。點此查看介紹。',
      details,
    );
  }
}
