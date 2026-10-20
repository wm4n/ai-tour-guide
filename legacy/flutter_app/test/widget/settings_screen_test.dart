import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/settings/settings_screen.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('settings screen exposes tour playback controls', (tester) async {
    SharedPreferences.setMockInitialValues({});

    await tester.pumpWidget(
      const ProviderScope(
        child: MaterialApp(home: SettingsScreen()),
      ),
    );
    await tester.pumpAndSettle();

    expect(find.text('導覽播放模式'), findsOneWidget);
    expect(find.text('自動播放'), findsOneWidget);
    expect(find.text('只通知'), findsOneWidget);
    expect(find.text('使用情境'), findsOneWidget);
    expect(find.text('隨身'), findsOneWidget);
    expect(find.text('車用'), findsOneWidget);
  });
}
