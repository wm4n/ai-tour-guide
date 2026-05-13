import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/session/widgets/persona_selector.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

Widget _makeWidget() {
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        FakeLocationService(hasPermission: true),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
    child: const MaterialApp(home: Scaffold(body: PersonaSelector())),
  );
}

void main() {
  testWidgets('shows all 5 persona names', (tester) async {
    await tester.pumpWidget(_makeWidget());
    for (final persona in kPersonas) {
      expect(find.text(persona.displayName), findsOneWidget);
    }
  });

  testWidgets('history_uncle is selected by default', (tester) async {
    await tester.pumpWidget(_makeWidget());
    // The default selected persona card should show a check icon
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('tapping a different persona updates selection', (tester) async {
    await tester.pumpWidget(_makeWidget());
    // Tap story_brother card
    await tester.tap(find.text('故事大哥哥'));
    await tester.pump();
    // Now check_circle should still be exactly one (moved to story_brother)
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
    // Verify sessionProvider updated
    final container = ProviderScope.containerOf(
      tester.element(find.byType(PersonaSelector)),
    );
    expect(container.read(sessionProvider).persona, 'story_brother');
  });

  testWidgets('shows emoji for each persona', (tester) async {
    await tester.pumpWidget(_makeWidget());
    for (final persona in kPersonas) {
      expect(find.text(persona.emoji), findsOneWidget);
    }
  });
}
