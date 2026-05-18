import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/widgets/countdown_badge.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class _FakeSettingsNotifier extends AppSettingsNotifier {
  @override
  AppSettings build() => const AppSettings(countdownSeconds: 90, skipDisplacementM: 500);
}

class _FakeTriggerNotifier extends TriggerNotifier {
  final TriggerState _s;
  _FakeTriggerNotifier(this._s);
  @override
  TriggerState build() => _s;
  @override
  void skipCountdown() {}
}

void main() {
  testWidgets('CountdownBadge CircularProgressIndicator fills container via SizedBox.expand', (tester) async {
    final countingState = TriggerState(
      isCountingDown: true,
      countdownRemaining: const Duration(seconds: 45),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          triggerProvider.overrideWith(() => _FakeTriggerNotifier(countingState)),
          appSettingsProvider.overrideWith(() => _FakeSettingsNotifier()),
        ],
        child: const MaterialApp(home: Scaffold(body: CountdownBadge())),
      ),
    );
    // SizedBox.expand must wrap the CircularProgressIndicator
    // SizedBox.expand() sets width and height to double.infinity
    final sizedBoxFinder = find.ancestor(
      of: find.byType(CircularProgressIndicator),
      matching: find.byWidgetPredicate(
        (w) => w is SizedBox && w.width == double.infinity && w.height == double.infinity,
      ),
    );
    expect(sizedBoxFinder, findsOneWidget);
  });
}
