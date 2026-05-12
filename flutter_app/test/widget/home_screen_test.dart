import 'dart:async';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

class _FakeLocationService implements LocationService {
  final bool hasPermission;
  _FakeLocationService({this.hasPermission = true});
  @override Future<bool> requestPermission() async => hasPermission;
  @override void start() {}
  @override void stop() {}
  @override Stream<Position> get positionStream => const Stream.empty();
}

Widget _makeWidget({bool hasPermission = true}) {
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        _FakeLocationService(hasPermission: hasPermission),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
    child: const MaterialApp(home: HomeScreen()),
  );
}

void main() {
  testWidgets('shows Start Journey button when idle', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('開始旅程'), findsOneWidget);
  });

  testWidgets('shows persona chip with history_uncle', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('歷史大叔'), findsOneWidget);
  });
}
