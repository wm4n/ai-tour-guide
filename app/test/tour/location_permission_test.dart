import 'dart:async';

import 'package:buddy_tour/tour/location_permission.dart';
import 'package:flutter_test/flutter_test.dart';

class FakePermissions implements LocationPermissionApi {
  FakePermissions({
    required this.current,
    this.afterWhenInUse = LocationAccess.whileInUse,
    this.afterAlways = LocationAccess.always,
  });

  LocationAccess current;
  final LocationAccess afterWhenInUse;
  final LocationAccess afterAlways;
  final requests = <String>[];

  @override
  Future<LocationAccess> status() async => current;

  @override
  Future<LocationAccess> requestWhenInUse() async {
    requests.add('whenInUse');
    return current = afterWhenInUse;
  }

  @override
  Future<LocationAccess> requestAlways() async {
    requests.add('always');
    return current = afterAlways;
  }
}

void main() {
  test('a fresh install asks for while-in-use, then for always', () async {
    final api = FakePermissions(current: LocationAccess.denied);

    final access = await ensureLocationAccess(api);

    expect(api.requests, ['whenInUse', 'always']);
    expect(access, LocationAccess.always);
  });

  test('already always: nothing more is asked', () async {
    final api = FakePermissions(current: LocationAccess.always);

    final access = await ensureLocationAccess(api);

    expect(api.requests, isEmpty);
    expect(access, LocationAccess.always);
  });

  test('while-in-use gets one upgrade request', () async {
    final api = FakePermissions(current: LocationAccess.whileInUse);

    await ensureLocationAccess(api);

    expect(api.requests, ['always']);
  });

  test('the user may keep while-in-use: the tour can still start', () async {
    final api = FakePermissions(
      current: LocationAccess.whileInUse,
      afterAlways: LocationAccess.whileInUse,
    );

    final access = await ensureLocationAccess(api);

    expect(access, LocationAccess.whileInUse);
    expect(access.canTrack, isTrue);
  });

  test('refusing everything means no tracking and no upgrade prompt', () async {
    final api = FakePermissions(
      current: LocationAccess.denied,
      afterWhenInUse: LocationAccess.denied,
    );

    final access = await ensureLocationAccess(api);

    expect(api.requests, ['whenInUse']);
    expect(access, LocationAccess.denied);
    expect(access.canTrack, isFalse);
  });

  test('only always keeps working with the screen locked', () {
    expect(LocationAccess.always.keepsWorkingWhenLocked, isTrue);
    expect(LocationAccess.whileInUse.keepsWorkingWhenLocked, isFalse);
    expect(LocationAccess.denied.keepsWorkingWhenLocked, isFalse);
  });

  test(
    'an error while asking for the upgrade does not lose the access we have',
    () async {
      final api = _ThrowingUpgrade();

      final access = await ensureLocationAccess(api);

      expect(access, LocationAccess.whileInUse);
    },
  );

  test(
    'an upgrade prompt that never answers does not hold up the tour',
    () async {
      final api = _NeverAnswers();

      final access = await ensureLocationAccess(
        api,
        upgradeTimeout: const Duration(milliseconds: 20),
      );

      expect(access, LocationAccess.whileInUse); // 沿用目前的權限，不卡住出發
    },
  );
}

class _ThrowingUpgrade extends FakePermissions {
  _ThrowingUpgrade() : super(current: LocationAccess.whileInUse);

  @override
  Future<LocationAccess> requestAlways() async => throw StateError('壞了');
}

class _NeverAnswers extends FakePermissions {
  _NeverAnswers() : super(current: LocationAccess.whileInUse);

  @override
  Future<LocationAccess> requestAlways() => Completer<LocationAccess>().future;
}
