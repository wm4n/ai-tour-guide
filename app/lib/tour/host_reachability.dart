/// 連得上主機與否，以及斷線時重試的退避（設計文件 12 節）。
///
/// 只記狀態與時間，不做 I/O；由呼叫端在每次請求成功或失敗時回報。
class HostReachability {
  HostReachability({
    this.firstDelay = const Duration(seconds: 10),
    this.maxDelay = const Duration(seconds: 60),
  });

  /// 第一次失敗後等多久再試；之後每次失敗加倍，最長 [maxDelay]。
  final Duration firstDelay;
  final Duration maxDelay;

  int _failures = 0;
  DateTime? _nextTryAt;

  bool get reachable => _failures == 0;

  bool canTry(DateTime now) {
    final next = _nextTryAt;
    return next == null || !now.isBefore(next);
  }

  /// 回傳 true 代表這是一次斷線的第一次失敗（只有這時候才該提示使用者）。
  bool recordFailure(DateTime now) {
    final firstOfOutage = _failures == 0;
    _failures++;
    final scaled = firstDelay * (1 << (_failures - 1).clamp(0, 16));
    _nextTryAt = now.add(scaled > maxDelay ? maxDelay : scaled);
    return firstOfOutage;
  }

  /// 回傳 true 代表剛從斷線恢復。
  bool recordSuccess() {
    final recovered = _failures > 0;
    _failures = 0;
    _nextTryAt = null;
    return recovered;
  }
}
