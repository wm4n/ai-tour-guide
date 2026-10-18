import 'package:buddy_tour/host/host_client.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/ui/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

class _FixedClient implements HostClient {
  _FixedClient(this.status);
  final ConnectionStatus status;
  @override
  Future<ConnectionStatus> check(HostSettings settings) async => status;
}

Future<void> pumpHome(
  WidgetTester tester,
  ConnectionStatus status, {
  bool configured = true,
}) async {
  SharedPreferences.setMockInitialValues(
    configured ? {'host.url': 'http://h:1'} : {},
  );
  final prefs = await SharedPreferences.getInstance();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        hostClientProvider.overrideWithValue(_FixedClient(status)),
        pollIntervalProvider.overrideWithValue(const Duration(hours: 1)),
      ],
      child: const MaterialApp(home: HomeScreen()),
    ),
  );
  await tester.pump();
  await tester.pump();
}

void main() {
  testWidgets('shows 主機已連線 and enables 出發 when connected', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected);

    expect(find.text('主機已連線'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('tour-toggle')),
    );
    expect(button.onPressed, isNotNull);
  });

  testWidgets('shows 主機未連線 and disables 出發 when unreachable', (tester) async {
    await pumpHome(tester, ConnectionStatus.unreachable);

    expect(find.text('主機未連線'), findsOneWidget);
    final button = tester.widget<FilledButton>(
      find.byKey(const Key('tour-toggle')),
    );
    expect(button.onPressed, isNull);
  });

  testWidgets('unauthorized has its own wording', (tester) async {
    await pumpHome(tester, ConnectionStatus.unauthorized);

    expect(find.text('主機未連線：token 不正確'), findsOneWidget);
  });

  testWidgets('not configured asks for a host address', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected, configured: false);

    expect(find.text('尚未設定主機位址'), findsOneWidget);
  });

  testWidgets('出發 toggles to 結束 and back', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected);

    expect(find.text('出發'), findsOneWidget);
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pump();
    expect(find.text('結束'), findsOneWidget);

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pump();
    expect(find.text('出發'), findsOneWidget);
  });

  testWidgets('settings dialog saves url and token', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected, configured: false);

    await tester.tap(find.byKey(const Key('open-settings')));
    await tester.pumpAndSettle();
    await tester.enterText(
      find.byKey(const Key('setting-url')),
      'http://100.64.0.1:8765',
    );
    await tester.enterText(find.byKey(const Key('setting-token')), 'tok');
    await tester.tap(find.text('儲存'));
    await tester.pumpAndSettle();

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('host.url'), 'http://100.64.0.1:8765');
    expect(prefs.getString('host.token'), 'tok');
    expect(find.text('主機已連線'), findsOneWidget);
  });
}
