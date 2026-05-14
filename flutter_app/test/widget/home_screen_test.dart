import 'dart:async';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

class _FakeLocationService implements LocationService {
  final bool hasPermission;
  final LocationPermission permissionLevel;
  _FakeLocationService({
    this.hasPermission = true,
    this.permissionLevel = LocationPermission.always,
  });
  @override Future<bool> requestPermission() async => hasPermission;
  @override Future<LocationPermission> checkPermission() async =>
      permissionLevel;
  @override void start() {}
  @override void stop() {}
  @override Stream<Position> get positionStream => const Stream.empty();
}

Widget _makeWidget({
  bool hasPermission = true,
  LocationPermission permissionLevel = LocationPermission.always,
}) {
  final router = GoRouter(
    routes: [
      GoRoute(path: '/', builder: (_, __) => const HomeScreen()),
      GoRoute(path: '/map', builder: (_, __) => const Scaffold()),
    ],
  );
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        _FakeLocationService(
          hasPermission: hasPermission,
          permissionLevel: permissionLevel,
        ),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
    child: MaterialApp.router(routerConfig: router),
  );
}

void main() {
  testWidgets('shows Start Journey button when idle', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('開始旅程'), findsOneWidget);
  });

  testWidgets('shows all 5 persona cards', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('歷史大叔'), findsOneWidget);
    expect(find.text('故事大哥哥'), findsOneWidget);
    expect(find.text('八卦阿姨'), findsOneWidget);
    expect(find.text('童趣小妹'), findsOneWidget);
    expect(find.text('美食家'), findsOneWidget);
  });

  testWidgets('shows language segmented button', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('中文'), findsOneWidget);
    expect(find.text('EN'), findsOneWidget);
  });

  testWidgets('history_uncle is selected by default', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('shows background location SnackBar when permission is whileInUse', (tester) async {
    await tester.pumpWidget(_makeWidget(
      hasPermission: true,
      permissionLevel: LocationPermission.whileInUse,
    ));
    // Scroll the button into view (it may be below the fold)
    await tester.ensureVisible(find.text('開始旅程'));
    await tester.pumpAndSettle();
    // Tap the start button to trigger _start() — ignore GoRouter error
    await tester.tap(find.text('開始旅程'), warnIfMissed: false);
    // pump multiple frames to allow async _start() to execute
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 100));
    await tester.pump(const Duration(milliseconds: 100));
    // Expect a SnackBar with background location guidance (shown before push)
    expect(find.byType(SnackBar), findsWidgets);
    expect(find.textContaining('背景'), findsWidgets);
  });
}
