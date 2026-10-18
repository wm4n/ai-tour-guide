import 'dart:async';
import 'dart:io';
import 'package:geolocator/geolocator.dart';

abstract class LocationService {
  Future<bool> requestPermission();
  Future<LocationPermission> checkPermission();
  void start();
  void stop();
  Stream<Position> get positionStream;
  Position? get latestPosition;
}

class RealLocationService implements LocationService {
  StreamController<Position>? _controller;
  StreamSubscription<Position>? _subscription;
  Position? _latestPosition;

  @override
  Future<bool> requestPermission() async {
    var perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    return perm == LocationPermission.whileInUse ||
        perm == LocationPermission.always;
  }

  @override
  Future<LocationPermission> checkPermission() =>
      Geolocator.checkPermission();

  @override
  void start() {
    final LocationSettings locationSettings;
    if (Platform.isIOS) {
      locationSettings = AppleSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
        allowBackgroundLocationUpdates: true,
        activityType: ActivityType.fitness,
        pauseLocationUpdatesAutomatically: false,
      );
    } else {
      locationSettings = AndroidSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
        foregroundNotificationConfig: const ForegroundNotificationConfig(
          notificationText: 'AI Tour Guide 正在使用定位服務',
          notificationTitle: 'AI Tour Guide',
          enableWakeLock: true,
          notificationIcon: AndroidResource(name: 'ic_launcher', defType: 'mipmap'),
        ),
      );
    }

    _controller = StreamController<Position>.broadcast();
    _subscription = Geolocator.getPositionStream(
      locationSettings: locationSettings,
    ).listen(
      (position) {
        _latestPosition = position;
        _controller!.add(position);
      },
      onError: _controller!.addError,
    );
  }

  @override
  void stop() {
    _subscription?.cancel();
    _subscription = null;
    _controller?.close();
    _controller = null;
  }

  @override
  Stream<Position> get positionStream =>
      _controller?.stream ?? const Stream.empty();

  @override
  Position? get latestPosition => _latestPosition;
}

class FakeLocationService implements LocationService {
  final StreamController<Position> _controller =
      StreamController<Position>.broadcast();
  final bool _hasPermission;
  final LocationPermission _permissionStatus;
  Position? _latestPosition;

  FakeLocationService({
    bool hasPermission = true,
    LocationPermission permissionStatus = LocationPermission.whileInUse,
  })  : _hasPermission = hasPermission,
        _permissionStatus = permissionStatus;

  void emit(Position position) {
    _latestPosition = position;
    _controller.add(position);
  }

  @override
  Future<bool> requestPermission() async => _hasPermission;

  @override
  Future<LocationPermission> checkPermission() async =>
      _permissionStatus;

  @override
  void start() {}

  @override
  void stop() {}

  @override
  Stream<Position> get positionStream => _controller.stream;

  @override
  Position? get latestPosition => _latestPosition;
}

Position fakePosition(double lat, double lon) => Position(
      latitude: lat,
      longitude: lon,
      timestamp: DateTime.now(),
      accuracy: 5,
      altitude: 0,
      altitudeAccuracy: 0,
      heading: 0,
      headingAccuracy: 0,
      speed: 0,
      speedAccuracy: 0,
    );
