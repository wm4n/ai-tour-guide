import 'package:shared_preferences/shared_preferences.dart';

enum TravelMode { walking, driving }

enum Companions { solo, couple, family, friends }

/// 使用者出發前自己選的即時狀態（設計文件第 7 節步驟 1）；當地時間在回報時另外帶上。
class TravelerState {
  const TravelerState({
    this.mode = TravelMode.walking,
    this.companions = Companions.solo,
    this.withChildren = false,
  });

  final TravelMode mode;
  final Companions companions;
  final bool withChildren;

  TravelerState copyWith({
    TravelMode? mode,
    Companions? companions,
    bool? withChildren,
  }) => TravelerState(
    mode: mode ?? this.mode,
    companions: companions ?? this.companions,
    withChildren: withChildren ?? this.withChildren,
  );

  Map<String, Object> toJson() => {
    'mode': mode.name,
    'companions': companions.name,
    'with_children': withChildren,
  };
}

/// 帶時區偏移的 ISO 8601；Dart 的 toIso8601String 沒有偏移，主機會分不出幾點。
String isoWithOffset(DateTime time, {Duration? offset}) {
  final shift = offset ?? time.timeZoneOffset;
  final wall = time.toUtc().add(shift);
  String two(int value) => value.toString().padLeft(2, '0');
  final minutes = shift.inMinutes.abs();
  final sign = shift.isNegative ? '-' : '+';
  return '${wall.year.toString().padLeft(4, '0')}-${two(wall.month)}-${two(wall.day)}'
      'T${two(wall.hour)}:${two(wall.minute)}:${two(wall.second)}'
      '$sign${two(minutes ~/ 60)}:${two(minutes % 60)}';
}

class TravelerStore {
  TravelerStore(this._prefs);

  static const modeKey = 'traveler.mode';
  static const companionsKey = 'traveler.companions';
  static const childrenKey = 'traveler.children';

  final SharedPreferences _prefs;

  TravelerState load() {
    T pick<T extends Enum>(List<T> values, String key, T fallback) {
      final stored = _prefs.getString(key);
      return values.firstWhere((v) => v.name == stored, orElse: () => fallback);
    }

    const defaults = TravelerState();
    return TravelerState(
      mode: pick(TravelMode.values, modeKey, defaults.mode),
      companions: pick(Companions.values, companionsKey, defaults.companions),
      withChildren: _prefs.getBool(childrenKey) ?? defaults.withChildren,
    );
  }

  Future<void> save(TravelerState state) async {
    await _prefs.setString(modeKey, state.mode.name);
    await _prefs.setString(companionsKey, state.companions.name);
    await _prefs.setBool(childrenKey, state.withChildren);
  }
}
