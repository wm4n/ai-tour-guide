/// 每個單位（第一個除外）前面的靜音：語音管線預設在單位之間停 0.45 秒（段落之間 1 秒），
/// 所以起點前 0.45 秒內一定是靜音。主機偵測起點的門檻（`units.py` 的 `MIN_GAP_SECONDS`）比這個小，
/// 是為了容許不同的設定。
const _silenceBeforeSentence = Duration(milliseconds: 450);

/// 介紹被問題打斷時，答完要從哪裡接著講：回到被打斷那一句的**開頭**，而不是從頭、也不是句子中間
/// （設計文件第 8 節）。
///
/// [unitStarts] 是主機附的各「合成單位」起點（秒）。單位通常是一句，但很短的句子會併在同一個單位裡，
/// 所以被打斷在併起來的短句中間時，會回到那一組的開頭。被打斷的位置落在某個單位前面的靜音裡，
/// 等於剛好在句界，從下一個單位開始；不知道單位在哪（空的）時，從被打斷的位置接。
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
