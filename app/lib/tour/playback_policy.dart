import 'geo.dart';

/// 一次定位：位置、時間，以及自己算出來的行進方向（可能還沒有）。
class PositionFix {
  const PositionFix({
    required this.lat,
    required this.lon,
    required this.time,
    this.heading,
  });

  final double lat;
  final double lon;
  final DateTime time;
  final double? heading;

  /// 同一個位置換一個方向（拍照時用指南針方向取代走路的方向）；[heading] 為 null 就是不帶方向。
  PositionFix withHeading(double? heading) =>
      PositionFix(lat: lat, lon: lon, time: time, heading: heading);
}

/// 主機通知「這一段準備好了」。
class NarrationInfo {
  const NarrationInfo({
    required this.seq,
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.audioSeconds,
    this.unitStarts = const [],
    this.voice,
  });

  factory NarrationInfo.fromJson(Map<String, dynamic> json) => NarrationInfo(
    seq: json['seq'] as int,
    id: json['id'] as String,
    name: json['name'] as String,
    lat: (json['lat'] as num).toDouble(),
    lon: (json['lon'] as num).toDouble(),
    audioSeconds: (json['audio_seconds'] as num).toDouble(),
    unitStarts: [
      for (final value in json['unit_starts'] as List? ?? const [])
        (value as num).toDouble(),
    ],
    voice: json['voice'] as String?,
  );

  final int seq;
  final String id;
  final String name;
  final double lat;
  final double lon;
  final double audioSeconds;

  /// 各句（合成單位）開始播放的秒數；被問題打斷時回到那一句的開頭。舊主機沒給就是空的。
  final List<double> unitStarts;

  /// 這段是哪個聲音（聲音鍵）；舊主機沒給就是 null。
  final String? voice;
}

class QueuedNarration {
  const QueuedNarration(this.info, this.receivedAt);

  final NarrationInfo info;
  final DateTime receivedAt;
}

class PlaybackDecision {
  const PlaybackDecision({this.play, this.drop = const []});

  final QueuedNarration? play;
  final List<QueuedNarration> drop;
}

/// 「什麼時候講」的規則（設計文件第 7 節步驟 4）：只看位置、時間與狀態，不碰音訊，方便單元測試。
///
/// - 走到景點附近（[triggerRadiusM]）才講，同時有多段就先講最近的。
/// - 兩段之間至少隔 [minGap]，從上一段播完算起。
/// - 暫停主動介紹、或正在播另一段時，不開始新的。
/// - 走遠了（[staleDistanceM]）或放太久（[maxAge]）的就丟掉，不補講。
class PlaybackPolicy {
  const PlaybackPolicy({
    this.minGap = const Duration(minutes: 3),
    this.triggerRadiusM = 150,
    this.staleDistanceM = 500,
    this.maxAge = const Duration(minutes: 30),
  });

  final Duration minGap;
  final double triggerRadiusM;
  final double staleDistanceM;
  final Duration maxAge;

  PlaybackDecision decide({
    required DateTime now,
    required PositionFix? position,
    required List<QueuedNarration> queue,
    required DateTime? lastFinishedAt,
    required bool paused,
    required bool busy,
  }) {
    if (position == null) return const PlaybackDecision();

    double distanceTo(QueuedNarration item) =>
        haversineM(position.lat, position.lon, item.info.lat, item.info.lon);

    final drop = <QueuedNarration>[];
    final fresh = <QueuedNarration>[];
    for (final item in queue) {
      final stale =
          now.difference(item.receivedAt) > maxAge ||
          distanceTo(item) > staleDistanceM;
      (stale ? drop : fresh).add(item);
    }

    final gapElapsed =
        lastFinishedAt == null || now.difference(lastFinishedAt) >= minGap;
    if (paused || busy || !gapElapsed) return PlaybackDecision(drop: drop);

    QueuedNarration? best;
    var bestDistance = double.infinity;
    for (final item in fresh) {
      final distance = distanceTo(item);
      if (distance <= triggerRadiusM && distance < bestDistance) {
        best = item;
        bestDistance = distance;
      }
    }
    return PlaybackDecision(play: best, drop: drop);
  }
}
