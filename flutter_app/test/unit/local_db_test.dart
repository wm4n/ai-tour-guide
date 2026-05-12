import 'package:drift/drift.dart';
import 'package:drift/native.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/db/local_db.dart';

LocalDb _makeInMemoryDb() =>
    LocalDb.forTesting(NativeDatabase.memory());

void main() {
  late LocalDb db;

  setUp(() => db = _makeInMemoryDb());
  tearDown(() => db.close());

  group('LocalDb.isCooldown', () {
    test('returns false when no history exists', () async {
      final result = await db.isCooldown('poi:123', Duration(hours: 24));
      expect(result, isFalse);
    });

    test('returns true when played within cooldown window', () async {
      final sessionId = await db.startSession('history_uncle', 'zh-TW');
      await db.recordNarration(
        sessionId: sessionId,
        poiId: 'poi:123',
        poiName: 'Test POI',
        poiLat: 25.1,
        poiLon: 121.5,
        persona: 'history_uncle',
        lang: 'zh-TW',
        completed: true,
      );
      final result = await db.isCooldown('poi:123', Duration(hours: 24));
      expect(result, isTrue);
    });

    test('returns false when last played is outside cooldown window', () async {
      final sessionId = await db.startSession('history_uncle', 'zh-TW');
      // Insert a narration from 25 hours ago
      final oldTime = DateTime.now()
          .subtract(const Duration(hours: 25))
          .millisecondsSinceEpoch;
      await db.into(db.narrationHistory).insert(
        NarrationHistoryCompanion.insert(
          sessionId: sessionId,
          poiId: 'poi:old',
          poiName: 'Old POI',
          poiLat: 25.0,
          poiLon: 121.0,
          persona: 'history_uncle',
          lang: 'zh-TW',
          playedAt: oldTime,
          completed: const Value(0),
        ),
      );
      final result = await db.isCooldown('poi:old', Duration(hours: 24));
      expect(result, isFalse);
    });
  });
}
