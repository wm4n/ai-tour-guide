import 'package:drift/drift.dart';
import 'package:drift_flutter/drift_flutter.dart';

part 'local_db.g.dart';

class Sessions extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get startedAt => integer()();
  IntColumn get endedAt => integer().nullable()();
  TextColumn get persona => text()();
  TextColumn get lang => text()();
}

class NarrationHistory extends Table {
  IntColumn get id => integer().autoIncrement()();
  IntColumn get sessionId => integer().references(Sessions, #id)();
  TextColumn get poiId => text()();
  TextColumn get poiName => text()();
  RealColumn get poiLat => real()();
  RealColumn get poiLon => real()();
  TextColumn get persona => text()();
  TextColumn get lang => text()();
  IntColumn get playedAt => integer()();
  IntColumn get completed => integer().withDefault(const Constant(0))();
}

@DriftDatabase(tables: [Sessions, NarrationHistory])
class LocalDb extends _$LocalDb {
  LocalDb([QueryExecutor? executor])
      : super(executor ?? driftDatabase(name: 'tour_guide_db'));

  LocalDb.forTesting(QueryExecutor executor) : super(executor);

  @override
  int get schemaVersion => 1;

  Future<int> startSession(String persona, String lang) =>
      into(sessions).insert(SessionsCompanion.insert(
        startedAt: DateTime.now().millisecondsSinceEpoch,
        persona: persona,
        lang: lang,
      ));

  Future<void> endSession(int sessionId) => (update(sessions)
        ..where((t) => t.id.equals(sessionId)))
      .write(SessionsCompanion(
        endedAt: Value(DateTime.now().millisecondsSinceEpoch),
      ));

  Future<void> recordNarration({
    required int sessionId,
    required String poiId,
    required String poiName,
    required double poiLat,
    required double poiLon,
    required String persona,
    required String lang,
    required bool completed,
  }) =>
      into(narrationHistory).insert(NarrationHistoryCompanion.insert(
        sessionId: sessionId,
        poiId: poiId,
        poiName: poiName,
        poiLat: poiLat,
        poiLon: poiLon,
        persona: persona,
        lang: lang,
        playedAt: DateTime.now().millisecondsSinceEpoch,
        completed: Value(completed ? 1 : 0),
      ));

  Future<bool> isCooldown(String poiId, Duration window) async {
    final cutoff =
        DateTime.now().subtract(window).millisecondsSinceEpoch;
    final rows = await (select(narrationHistory)
          ..where(
            (t) =>
                t.poiId.equals(poiId) &
                t.playedAt.isBiggerThanValue(cutoff),
          ))
        .get();
    return rows.isNotEmpty;
  }
}
