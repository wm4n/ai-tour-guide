import 'dart:async';
import 'package:geolocator/geolocator.dart';

abstract class LocationService {
  Future<bool> requestPermission();
  void start();
  void stop();
  Stream<Position> get positionStream;
}

class RealLocationService implements LocationService {
  StreamController<Position>? _controller;
  StreamSubscription<Position>? _subscription;

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
  void start() {
    _controller = StreamController<Position>.broadcast();
    _subscription = Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 10,
      ),
    ).listen(
      _controller!.add,
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
}

class FakeLocationService implements LocationService {
  final StreamController<Position> _controller =
      StreamController<Position>.broadcast();
  final bool _hasPermission;

  FakeLocationService({bool hasPermission = true})
      : _hasPermission = hasPermission;

  void emit(Position position) => _controller.add(position);

  @override
  Future<bool> requestPermission() async => _hasPermission;

  @override
  void start() {}

  @override
  void stop() {}

  @override
  Stream<Position> get positionStream => _controller.stream;
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
