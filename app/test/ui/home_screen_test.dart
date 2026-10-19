import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/tour/tour_controller.dart';
import 'package:buddy_tour/tour/tour_api.dart';
import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:buddy_tour/host/host_client.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/ui/home_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../tour/fakes.dart';

class _FixedClient implements HostClient {
  _FixedClient(this.status);
  final ConnectionStatus status;
  @override
  Future<ConnectionStatus> check(HostSettings settings) async => status;
}

late FakePhrases phrases;
late FakeTourApi api;
late FakeRemote remote;

Future<void> pumpHome(
  WidgetTester tester,
  ConnectionStatus status, {
  bool configured = true,
}) async {
  SharedPreferences.setMockInitialValues(
    configured ? {'host.url': 'http://h:1'} : {},
  );
  final prefs = await SharedPreferences.getInstance();
  phrases = FakePhrases();
  api = FakeTourApi();
  remote = FakeRemote();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        phrasePlayerProvider.overrideWithValue(phrases),
        tourApiProvider.overrideWithValue(api),
        locationSourceProvider.overrideWithValue(FakeLocation()),
        narrationPlayerProvider.overrideWithValue(FakePlayer()),
        remoteControlsProvider.overrideWithValue(remote),
        tourTickIntervalProvider.overrideWithValue(const Duration(hours: 1)),
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
    await tester.pumpAndSettle();
    expect(find.text('結束'), findsOneWidget);

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
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

  testWidgets('按「出發」播放短句 7，按「結束」不播', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected);

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
    expect(phrases.played, [FixedPhrase.startTour]);

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
    expect(phrases.played, [FixedPhrase.startTour]);
  });

  testWidgets('during a tour the pause button pauses and resumes narration', (
    tester,
  ) async {
    await pumpHome(tester, ConnectionStatus.connected);
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
    expect(find.text('陪你走，有好內容再開口'), findsOneWidget);

    await tester.tap(find.byKey(const Key('tour-pause')));
    await tester.pumpAndSettle();
    expect(find.text('主動介紹已暫停'), findsOneWidget);
    expect(find.text('繼續介紹'), findsOneWidget);
    expect(remote.updates.last.paused, isTrue);

    await tester.tap(find.byKey(const Key('tour-pause')));
    await tester.pumpAndSettle();
    expect(find.text('暫停介紹'), findsOneWidget);
  });

  testWidgets('the traveler choices are remembered and sent on departure', (
    tester,
  ) async {
    await pumpHome(tester, ConnectionStatus.connected);

    await tester.tap(find.text('家人'));
    await tester.tap(find.text('開車'));
    await tester.tap(find.byKey(const Key('traveler-children')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();

    final sent = api.started.single.$2;
    expect(sent.companions, Companions.family);
    expect(sent.mode, TravelMode.driving);
    expect(sent.withChildren, isTrue);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('traveler.companions'), 'family');
  });

  testWidgets('the traveler picker is hidden once the tour has started', (
    tester,
  ) async {
    await pumpHome(tester, ConnectionStatus.connected);
    expect(find.byKey(const Key('traveler-mode')), findsOneWidget);

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('traveler-mode')), findsNothing);
  });

  testWidgets('a refused departure shows why', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected);
    api.startError = TourApiException('down');

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('tour-error')), findsOneWidget);
    expect(find.text('出發'), findsOneWidget);
  });

  testWidgets('quota exhaustion is shown on screen', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected);
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
    api.queue([], stoppedReason: 'quota');

    final container = ProviderScope.containerOf(
      tester.element(find.byType(HomeScreen)),
    );
    await container.read(tourProvider.notifier).tick();
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('stopped-reason')), findsOneWidget);
    expect(find.textContaining('額度用完'), findsOneWidget);
  });
}
