import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/qa/widgets/push_to_talk_button.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/mic/mic_recorder_service.dart';
import 'package:flutter_app/shared/providers.dart';

// Fake SessionNotifier — mirrors pattern in narration_sheet_test.dart
class _FakeSessionNotifier extends StateNotifier<SessionState>
    implements SessionNotifier {
  _FakeSessionNotifier(SessionStatus status)
      : super(SessionState(
          status: status,
          persona: 'history_uncle',
          lang: 'zh-TW',
        ));

  @override void setPersona(String persona) {}
  @override void setLang(String lang) {}
  @override Future<void> start() async {}
  @override Future<void> stop() async {}
}

Widget _wrap(Widget child, {SessionStatus sessionStatus = SessionStatus.active}) {
  return ProviderScope(
    overrides: [
      backendClientProvider.overrideWithValue(const FakeBackendClient()),
      narrationAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
      qaAudioPlayerProvider.overrideWithValue(FakeAudioPlayerService()),
      micRecorderProvider.overrideWithValue(FakeMicRecorderService()),
      sessionProvider.overrideWith(
        (ref) => _FakeSessionNotifier(sessionStatus),
      ),
    ],
    child: MaterialApp(home: Scaffold(body: child)),
  );
}

void main() {
  group('PushToTalkButton', () {
    testWidgets('shows mic icon when idle and session active', (tester) async {
      await tester.pumpWidget(_wrap(const PushToTalkButton()));
      expect(find.byIcon(Icons.mic), findsOneWidget);
    });

    testWidgets('hidden when session is not active', (tester) async {
      await tester.pumpWidget(_wrap(
        const PushToTalkButton(),
        sessionStatus: SessionStatus.idle,
      ));
      expect(find.byType(SizedBox), findsWidgets);
      expect(find.byIcon(Icons.mic), findsNothing);
    });
  });
}
