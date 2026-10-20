/// 主機偵測「句子起點」的靜音門檻（`host/src/buddy_host/speech/units.py` 的 `MIN_GAP_SECONDS`）：
/// 每個句子（第一句除外）前面至少有這麼長的靜音。
const _silenceBeforeSentence = Duration(milliseconds: 300);

/// 介紹被問題打斷時，答完要從哪裡接著講：回到被打斷那一句的**開頭**，而不是從頭、也不是句子中間
/// （設計文件第 8 節）。
///
/// [unitStarts] 是主機附的各句起點（秒）。被打斷的位置落在某一句前面的靜音裡，等於剛好在句界，
/// 從下一句開始；不知道句子在哪（空的）時，從被打斷的位置接。
Duration resumePoint(Duration position, List<double> unitStarts) {
  if (unitStarts.isEmpty) return position;
  var start = _seconds(unitStarts.first);
  for (final value in unitStarts.skip(1)) {
    final candidate = _seconds(value);
    if (position >= candidate - _silenceBeforeSentence) {
      start = candidate;
    } else {
      break;
    }
  }
  return start;
}

Duration _seconds(double value) =>
    Duration(microseconds: (value * Duration.microsecondsPerSecond).round());
