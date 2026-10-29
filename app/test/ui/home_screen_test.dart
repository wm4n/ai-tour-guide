import 'dart:async';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/qa/photo_source.dart';
import 'package:buddy_tour/qa/qa_api.dart';
import 'package:buddy_tour/qa/qa_controller.dart';
import 'package:buddy_tour/tour/location_permission.dart';
import 'package:buddy_tour/tour/tour_controller.dart';
import 'package:buddy_tour/tour/tour_api.dart';
import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:buddy_tour/host/host_client.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/ui/home_screen.dart';
import 'package:buddy_tour/voice/phrase_store.dart';
import 'package:buddy_tour/voice/voice_api.dart';
import 'package:buddy_tour/voice/voice_controller.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../qa/fakes.dart';
import '../tour/fakes.dart';
import '../voice/fakes.dart';

class _FixedClient implements HostClient {
  _FixedClient(this.status);
  final ConnectionStatus status;
  @override
  Future<ConnectionStatus> check(HostSettings settings) async => status;
}

late FakePhrases phrases;
late FakeTourApi api;
late FakeRemote remote;
late FakeQaApi qaApi;
late FakeRecognizer recognizer;
late FakePlayer answerPlayer;
late FakePhotoSource photoSource;
late FakeCompass compass;
late FakeLocation location;
late FakeVoiceApi voiceApi;
late FakePlayer previewPlayer;
late FakePhraseStore phraseStore;

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
  qaApi = FakeQaApi();
  recognizer = FakeRecognizer();
  answerPlayer = FakePlayer();
  photoSource = FakePhotoSource();
  compass = FakeCompass();
  location = FakeLocation();
  voiceApi = FakeVoiceApi();
  previewPlayer = FakePlayer();
  phraseStore = FakePhraseStore();
  await tester.pumpWidget(
    ProviderScope(
      overrides: [
        sharedPreferencesProvider.overrideWithValue(prefs),
        phrasePlayerProvider.overrideWithValue(phrases),
        tourApiProvider.overrideWithValue(api),
        locationSourceProvider.overrideWithValue(location),
        narrationPlayerProvider.overrideWithValue(FakePlayer()),
        remoteControlsProvider.overrideWithValue(remote),
        tourTickIntervalProvider.overrideWithValue(const Duration(hours: 1)),
        hostClientProvider.overrideWithValue(_FixedClient(status)),
        pollIntervalProvider.overrideWithValue(const Duration(hours: 1)),
        qaApiProvider.overrideWithValue(qaApi),
        photoSourceProvider.overrideWithValue(photoSource),
        compassSourceProvider.overrideWithValue(compass),
        speechRecognizerProvider.overrideWithValue(recognizer),
        answerPlayerProvider.overrideWithValue(answerPlayer),
        qaPollIntervalProvider.overrideWithValue(const Duration(seconds: 1)),
        voiceApiProvider.overrideWithValue(voiceApi),
        previewPlayerProvider.overrideWithValue(previewPlayer),
        phraseStoreProvider.overrideWithValue(phraseStore),
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

  testWidgets('connecting to the host follows its current voice', (
    tester,
  ) async {
    await pumpHome(tester, ConnectionStatus.connected);

    expect(voiceApi.lists, 1);
    expect(await phraseStore.has('F2@1.2'), isTrue);
  });

  testWidgets('not reaching the host does not ask for its voices', (
    tester,
  ) async {
    await pumpHome(tester, ConnectionStatus.unreachable);

    expect(voiceApi.lists, 0);
  });

  group('settings page', () {
    Future<void> openSettings(WidgetTester tester) async {
      await tester.tap(find.byKey(const Key('open-settings')));
      await tester.pumpAndSettle();
    }

    Finder tile(String name) => find.byKey(Key('voice-$name'));

    Finder inTile(String name, Finder finder) =>
        find.descendant(of: tile(name), matching: finder);

    testWidgets('saves url and token', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected, configured: false);
      await openSettings(tester);

      await tester.enterText(
        find.byKey(const Key('setting-url')),
        'http://100.64.0.1:8765',
      );
      await tester.enterText(find.byKey(const Key('setting-token')), 'tok');
      await tester.ensureVisible(find.byKey(const Key('setting-save')));
      await tester.tap(find.byKey(const Key('setting-save')));
      await tester.pumpAndSettle();

      final prefs = await SharedPreferences.getInstance();
      expect(prefs.getString('host.url'), 'http://100.64.0.1:8765');
      expect(prefs.getString('host.token'), 'tok');
      // 開頁讀一次；換了主機再讀一次；連上新主機時又跟上一次主機的目前聲音
      expect(voiceApi.lists, 3);

      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('主機已連線'), findsOneWidget);
    });

    testWidgets('is a full page with a voice and a host section', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester);

      expect(find.byType(AlertDialog), findsNothing);
      expect(find.text('聲音'), findsOneWidget);
      expect(find.text('家裡的主機'), findsOneWidget);
      expect(
        tester
            .widget<TextField>(find.byKey(const Key('setting-url')))
            .controller!
            .text,
        'http://h:1',
      );
    });

    testWidgets('lists the host\'s voices with the current one ticked', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester);

      expect(inTile('F2', find.text('示範女聲')), findsOneWidget);
      expect(inTile('F2', find.text('女聲・溫暖')), findsOneWidget);
      expect(inTile('F2', find.text('示')), findsOneWidget); // 頭像：顯示名稱首字
      expect(inTile('F2', find.byIcon(Icons.check_circle)), findsOneWidget);
      expect(inTile('M1', find.text('示範男聲')), findsOneWidget);
      expect(inTile('M1', find.byIcon(Icons.check_circle)), findsNothing);
      expect(find.byKey(const Key('voice-current-not-ready')), findsNothing);
    });

    testWidgets(
      'a voice without phrases is greyed out and cannot be previewed',
      (tester) async {
        await pumpHome(tester, ConnectionStatus.connected);
        voiceApi.catalog = VoiceCatalog(
          current: 'F2',
          voices: [voice('F2'), voice('M1', phrasesReady: false)],
        );
        await openSettings(tester);

        expect(tester.widget<ListTile>(tile('M1')).enabled, isFalse);
        expect(inTile('M1', find.text('短句尚未準備')), findsOneWidget);
        expect(
          tester
              .widget<IconButton>(find.byKey(const Key('voice-preview-M1')))
              .onPressed,
          isNull,
        );
        expect(tester.widget<ListTile>(tile('F2')).enabled, isTrue);
      },
    );

    testWidgets('warns when the current voice has no phrases yet', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      voiceApi.catalog = VoiceCatalog(
        current: 'M1',
        voices: [voice('F2'), voice('M1', phrasesReady: false)],
      );
      await openSettings(tester);

      expect(find.byKey(const Key('voice-current-not-ready')), findsOneWidget);
    });

    testWidgets('warns when the current voice is missing from the list', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      voiceApi.catalog = VoiceCatalog(current: 'X9', voices: [voice('M1')]);
      await openSettings(tester);

      expect(find.byKey(const Key('voice-current-missing')), findsOneWidget);
      expect(find.byIcon(Icons.check_circle), findsNothing);
    });

    testWidgets('offline it shows only the current voice', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester); // 先連上一次，記住目前的聲音
      await tester.pageBack();
      await tester.pumpAndSettle();
      voiceApi.listError = TourApiException('unreachable');

      await openSettings(tester);

      expect(find.byKey(const Key('voices-offline')), findsOneWidget);
      expect(inTile('F2', find.text('示範女聲')), findsOneWidget);
      expect(tile('M1'), findsNothing);
      expect(find.byKey(const Key('voice-preview-F2')), findsNothing);
    });

    testWidgets('offline without ever reaching the host says so', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.unreachable);
      voiceApi.listError = TourApiException('unreachable');
      await openSettings(tester);

      expect(find.byKey(const Key('voices-offline')), findsOneWidget);
      expect(find.text('連不上主機，還不知道目前用的是哪個聲音'), findsOneWidget);
    });

    testWidgets('the play button previews phrase 7 of that voice', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester);
      voiceApi.phrases.clear(); // 連上主機時補下載的目前聲音短句

      await tester.tap(find.byKey(const Key('voice-preview-M1')));
      await tester.pump();
      await tester.pump();

      expect(voiceApi.phrases, [('M1', 7)]);
      expect(previewPlayer.played, ['M1#7']);
      previewPlayer.finish();
      await tester.pumpAndSettle();
    });

    testWidgets('a failed preview says so', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      voiceApi.phraseError = TourApiException('answered 404');
      await openSettings(tester);

      await tester.tap(find.byKey(const Key('voice-preview-M1')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('voice-error')), findsOneWidget);
    });

    testWidgets('tapping a voice switches to it', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester);

      await tester.tap(tile('M1'));
      await tester.pumpAndSettle();

      expect(voiceApi.chosen, ['M1']);
      expect(inTile('M1', find.byIcon(Icons.check_circle)), findsOneWidget);
      expect(inTile('F2', find.byIcon(Icons.check_circle)), findsNothing);
    });

    testWidgets('shows progress on the voice being switched to', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester);
      voiceApi.chooseGate = Completer<void>();

      await tester.tap(tile('M1'));
      await tester.pump();
      await tester.pump();

      expect(
        inTile('M1', find.byType(CircularProgressIndicator)),
        findsOneWidget,
      );
      voiceApi.chooseGate!.complete();
      await tester.pumpAndSettle();
      expect(find.byType(CircularProgressIndicator), findsNothing);
    });

    testWidgets('a failed switch says why and keeps the old voice', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await openSettings(tester);
      voiceApi.chooseError = TourApiException('timed out');

      await tester.tap(tile('M1'));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('voice-error')), findsOneWidget);
      expect(inTile('F2', find.byIcon(Icons.check_circle)), findsOneWidget);
    });

    testWidgets(
      'the current voice, a voice without phrases and the play button do not switch',
      (tester) async {
        await pumpHome(tester, ConnectionStatus.connected);
        voiceApi.catalog = VoiceCatalog(
          current: 'F2',
          voices: [voice('F2'), voice('M1'), voice('M2', phrasesReady: false)],
        );
        await openSettings(tester);

        await tester.tap(tile('F2'));
        await tester.tap(tile('M2'));
        await tester.tap(find.byKey(const Key('voice-preview-M1')));
        await tester.pump();
        await tester.pump();
        previewPlayer.finish();
        await tester.pumpAndSettle();

        expect(voiceApi.chosen, isEmpty);
      },
    );

    testWidgets('previews are disabled while a question is in progress', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await tester.tap(find.byKey(const Key('tour-toggle')));
      await tester.pumpAndSettle();
      await openSettings(tester);
      final container = ProviderScope.containerOf(
        tester.element(find.byType(Scaffold).last),
      );

      unawaited(container.read(qaProvider.notifier).press());
      await tester.pump();
      await tester.pump();

      expect(
        tester
            .widget<IconButton>(find.byKey(const Key('voice-preview-M1')))
            .onPressed,
        isNull,
      );
      await container.read(qaProvider.notifier).cancel();
      await tester.pumpAndSettle();
    });
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

  testWidgets('the end of a tour shows the usage summary', (tester) async {
    await pumpHome(tester, ConnectionStatus.connected);
    api.summary = const TourSummary(
      calls: 4,
      narrations: 3,
      durationSeconds: 2400,
      hitLimit: true,
      utilization: {
        'five_hour': WindowUse(last: 0.38, change: 0.12),
        'seven_day': WindowUse(last: 0.47, change: 0.02),
      },
    );
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('tour-summary')), findsNothing);

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('tour-summary')), findsOneWidget);
    expect(find.textContaining('3 段介紹'), findsOneWidget);
    expect(find.textContaining('40 分鐘'), findsOneWidget);
    expect(find.textContaining('呼叫 Claude 4 次'), findsOneWidget);
    expect(find.textContaining('5 小時額度 38%（本趟 +12%）'), findsOneWidget);
    expect(find.textContaining('7 天額度 47%（本趟 +2%）'), findsOneWidget);
    expect(find.textContaining('撞到額度上限'), findsOneWidget);
  });

  testWidgets('without a summary the end of a tour shows nothing extra', (
    tester,
  ) async {
    await pumpHome(tester, ConnectionStatus.connected);
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('tour-summary')), findsNothing);
  });

  group('asking a question', () {
    Future<void> startTour(WidgetTester tester) async {
      await tester.tap(find.byKey(const Key('tour-toggle')));
      await tester.pumpAndSettle();
    }

    /// 結束測試前讓背景的輪詢收尾（待處理的計時器會讓測試失敗）。
    Future<void> wrapUp(WidgetTester tester) async {
      final container = ProviderScope.containerOf(
        tester.element(find.byType(HomeScreen)),
      );
      await container.read(qaProvider.notifier).cancel();
      await tester.pump(const Duration(seconds: 5));
    }

    testWidgets('there is no ask button before the tour starts', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);

      expect(find.byKey(const Key('ask-button')), findsNothing);
    });

    testWidgets('during a tour there is a hold-to-talk button', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);

      expect(find.byKey(const Key('ask-button')), findsOneWidget);
      expect(find.text('按住說話'), findsOneWidget);
    });

    testWidgets('holding listens, releasing sends the question', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      qaApi.answers = [poll(status: AnswerStatus.done)];

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      expect(find.text('聽你說…'), findsOneWidget);
      expect(recognizer.attempts, [true]);

      await gesture.up();
      await tester.pump();
      await tester.pump();

      expect(qaApi.asked.single.question, '那間廟拜的是誰');
      await wrapUp(tester);
    });

    testWidgets(
      'a cancelled touch while the answer is playing does not stop it',
      (tester) async {
        await pumpHome(tester, ConnectionStatus.connected);
        await startTour(tester);
        qaApi.answers = [poll(segments: 1)]; // 答案的第一段在播

        final first = await tester.startGesture(
          tester.getCenter(find.byKey(const Key('ask-button'))),
        );
        await tester.pump();
        await first.up();
        for (var i = 0; i < 5; i++) {
          await tester.pump();
        }
        expect(answerPlayer.played, isNotEmpty);

        // 答案播放中又碰了一下按鈕（按下會被忽略），然後被系統取消
        final second = await tester.startGesture(
          tester.getCenter(find.byKey(const Key('ask-button'))),
        );
        await tester.pump();
        await second.cancel();
        await tester.pump();

        expect(answerPlayer.events, isNot(contains('stop')));
        await wrapUp(tester);
      },
    );

    testWidgets('a cancelled touch throws the recording away', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      await gesture.cancel();
      await tester.pump();
      await tester.pump();

      expect(qaApi.asked, isEmpty);
      expect(find.text('按住說話'), findsOneWidget);
    });

    testWidgets('shows when Claude is searching the web', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      qaApi.answers = [poll(searching: true)];

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      await gesture.up();
      await tester.pump();
      await tester.pump();
      await tester.pump();

      expect(find.byKey(const Key('qa-searching')), findsOneWidget);
      await wrapUp(tester);
    });

    testWidgets('quota exhausted is shown on screen', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      qaApi.answers = [poll(status: AnswerStatus.failed, reason: 'quota')];

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      await gesture.up();
      for (var i = 0; i < 5; i++) {
        await tester.pump();
      }

      expect(find.byKey(const Key('qa-quota')), findsOneWidget);
      expect(find.textContaining('額度'), findsWidgets);
      await wrapUp(tester);
    });

    testWidgets('an error is shown and the button works again', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      recognizer.heard = '';

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      await gesture.up();
      for (var i = 0; i < 5; i++) {
        await tester.pump();
      }

      expect(find.byKey(const Key('qa-error')), findsOneWidget);
      expect(find.text('按住說話'), findsOneWidget);
      await wrapUp(tester);
    });

    testWidgets('says which recognition method is in use', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      qaApi.answers = [poll(status: AnswerStatus.done)];

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      await tester.pump();

      expect(find.textContaining('本機辨識'), findsOneWidget);
      await gesture.up();
      await wrapUp(tester);
    });
  });

  group('asking with a photo', () {
    Future<void> startTour(WidgetTester tester) async {
      await tester.tap(find.byKey(const Key('tour-toggle')));
      await tester.pumpAndSettle();
    }

    Future<void> wrapUp(WidgetTester tester) async {
      final container = ProviderScope.containerOf(
        tester.element(find.byType(HomeScreen)),
      );
      await container.read(qaProvider.notifier).cancel();
      await tester.pump(const Duration(seconds: 5));
    }

    testWidgets('there is a photo button during a tour only', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      expect(find.byKey(const Key('photo-button')), findsNothing);

      await startTour(tester);

      expect(find.byKey(const Key('photo-button')), findsOneWidget);
      expect(find.text('拍照問'), findsOneWidget);
    });

    testWidgets('tapping it takes a photo and asks about it', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      qaApi.answers = [poll(status: AnswerStatus.done)];

      await tester.tap(find.byKey(const Key('photo-button')));
      for (var i = 0; i < 5; i++) {
        await tester.pump();
      }

      expect(photoSource.taken, 1);
      expect(qaApi.askedPhotos.single.compassHeading, 270);
      await wrapUp(tester);
    });

    testWidgets('a camera that cannot open shows why', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);
      photoSource.error = PhotoUnavailable('需要相機權限才能拍照');

      await tester.tap(find.byKey(const Key('photo-button')));
      for (var i = 0; i < 5; i++) {
        await tester.pump();
      }

      expect(find.byKey(const Key('qa-error')), findsOneWidget);
      expect(find.text('需要相機權限才能拍照'), findsOneWidget);
      await wrapUp(tester);
    });

    testWidgets('is disabled while another question is in progress', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await startTour(tester);

      final gesture = await tester.startGesture(
        tester.getCenter(find.byKey(const Key('ask-button'))),
      );
      await tester.pump();
      await tester.pump();

      final button = tester.widget<OutlinedButton>(
        find.byKey(const Key('photo-button')),
      );
      expect(button.onPressed, isNull);
      await gesture.up();
      await wrapUp(tester);
    });
  });

  group('location access hint', () {
    testWidgets('no hint when always is granted', (tester) async {
      await pumpHome(tester, ConnectionStatus.connected);
      await tester.tap(find.byKey(const Key('tour-toggle')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('location-hint')), findsNothing);
    });

    testWidgets(
      'the hint goes away once the user switches to always in Settings',
      (tester) async {
        await pumpHome(tester, ConnectionStatus.connected);
        location.access = LocationAccess.whileInUse;
        await tester.tap(find.byKey(const Key('tour-toggle')));
        await tester.pumpAndSettle();
        expect(find.byKey(const Key('location-hint')), findsOneWidget);

        location.access = LocationAccess.always;
        tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.paused);
        tester.binding.handleAppLifecycleStateChanged(
          AppLifecycleState.resumed,
        );
        await tester.pumpAndSettle();

        expect(find.byKey(const Key('location-hint')), findsNothing);
      },
    );

    testWidgets('while-in-use warns that locking the screen may cut it off', (
      tester,
    ) async {
      await pumpHome(tester, ConnectionStatus.connected);
      location.access = LocationAccess.whileInUse;
      await tester.tap(find.byKey(const Key('tour-toggle')));
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('location-hint')), findsOneWidget);
      expect(find.textContaining('永遠'), findsOneWidget);
    });
  });
}
