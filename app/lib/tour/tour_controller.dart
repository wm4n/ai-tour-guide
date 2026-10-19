import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../audio/fixed_phrase.dart';
import '../audio/narration_player.dart';
import '../audio/phrase_player.dart';
import '../audio/remote_controls.dart';
import '../host/host_connection.dart';
import 'geo.dart';
import 'host_reachability.dart';
import 'location_source.dart';
import 'playback_policy.dart';
import 'tour_api.dart';
import 'traveler_state.dart';

final tourApiProvider = Provider<TourApi>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return HttpTourApi(client);
});

final locationSourceProvider = Provider<LocationSource>(
  (ref) =>
      throw UnimplementedError('locationSourceProvider must be overridden'),
);

final narrationPlayerProvider = Provider<NarrationPlayer>(
  (ref) =>
      throw UnimplementedError('narrationPlayerProvider must be overridden'),
);

final remoteControlsProvider = Provider<RemoteControls>(
  (ref) =>
      throw UnimplementedError('remoteControlsProvider must be overridden'),
);

final clockProvider = Provider<DateTime Function()>((ref) => DateTime.now);

/// 兩段介紹之間的最短間隔預設 3 分鐘；開發時可用 `--dart-define=MIN_GAP_SECONDS=…` 調整。
final playbackPolicyProvider = Provider<PlaybackPolicy>(
  (ref) => const PlaybackPolicy(
    minGap: Duration(
      seconds: int.fromEnvironment('MIN_GAP_SECONDS', defaultValue: 180),
    ),
  ),
);

final tourTickIntervalProvider = Provider<Duration>(
  (ref) => const Duration(seconds: 5),
);

final locationReportIntervalProvider = Provider<Duration>(
  (ref) => const Duration(seconds: 10),
);

final travelerStoreProvider = Provider<TravelerStore>(
  (ref) => TravelerStore(ref.watch(sharedPreferencesProvider)),
);

final travelerProvider = NotifierProvider<TravelerNotifier, TravelerState>(
  TravelerNotifier.new,
);

class TravelerNotifier extends Notifier<TravelerState> {
  @override
  TravelerState build() => ref.watch(travelerStoreProvider).load();

  Future<void> save(TravelerState value) async {
    await ref.read(travelerStoreProvider).save(value);
    state = value;
  }
}

class TourState {
  const TourState({
    this.active = false,
    this.paused = false,
    this.nowPlaying,
    this.stoppedReason,
    this.error,
  });

  final bool active;

  /// 使用者按了暫停鍵：主動介紹暫停，繼續之前不會開始新的。
  final bool paused;
  final String? nowPlaying;

  /// 主機停止準備的原因（`quota` 等）；畫面提示用，不念出來。
  final String? stoppedReason;
  final String? error;

  TourState copyWith({
    bool? active,
    bool? paused,
    Object? nowPlaying = _keep,
    Object? stoppedReason = _keep,
    Object? error = _keep,
  }) => TourState(
    active: active ?? this.active,
    paused: paused ?? this.paused,
    nowPlaying: identical(nowPlaying, _keep)
        ? this.nowPlaying
        : nowPlaying as String?,
    stoppedReason: identical(stoppedReason, _keep)
        ? this.stoppedReason
        : stoppedReason as String?,
    error: identical(error, _keep) ? this.error : error as String?,
  );
}

const Object _keep = Object();

final tourProvider = NotifierProvider<TourController, TourState>(
  TourController.new,
);

/// 一趟旅程在手機端的流程：回報位置、問主機有什麼準備好了、依時機規則播放。
class TourController extends Notifier<TourState> {
  int _session = 0; // 每次出發／結束加一，讓遲到的非同步結果自己作廢
  StreamSubscription<RawFix>? _positions;
  Timer? _timer;
  var _heading = HeadingTracker();
  PositionFix? _position;
  DateTime? _lastReportAt;
  DateTime? _lastFinishedAt;
  int _cursor = 0;
  bool _busy = false;
  var _host = HostReachability();

  /// 剛斷線、還沒念 [FixedPhrase.hostUnreachable]；播放中或暫停時先等，等念得出來才念，一次斷線只念一次。
  bool _unreachableDue = false;
  bool _polling = false; // 輪詢逾時比 tick 間隔長，不讓它們疊在一起
  final _queue = <QueuedNarration>[];
  final _audio = <String, Future<Uint8List?>>{};
  final _seen = <String>{};

  @override
  TourState build() {
    final remote = ref.watch(remoteControlsProvider);
    final commands = remote.commands.listen((command) {
      if (!state.active) return;
      switch (command) {
        case RemoteCommand.pause:
          pause();
        case RemoteCommand.play:
          resume();
      }
    });
    ref.onDispose(() {
      commands.cancel();
      _cancelWatching();
    });
    return const TourState();
  }

  DateTime get _now => ref.read(clockProvider)();

  Future<void> start() async {
    if (state.active) return;
    final settings = ref.read(settingsProvider);
    if (!settings.isConfigured) {
      state = state.copyWith(error: '尚未設定主機位址');
      return;
    }
    final location = ref.read(locationSourceProvider);
    if (!await location.ensurePermission()) {
      state = state.copyWith(error: '需要定位權限才能出發');
      return;
    }
    final first = await location.current();
    if (first == null) {
      state = state.copyWith(error: '拿不到目前位置');
      return;
    }

    final session = ++_session;
    _resetTour();
    final fix = _fixFrom(first);
    try {
      await ref
          .read(tourApiProvider)
          .start(settings, fix, ref.read(travelerProvider));
    } on TourApiException catch (error) {
      state = state.copyWith(error: '連不上主機：${error.message}');
      return;
    }
    if (session != _session) return; // 等待期間已經結束或重新出發

    state = const TourState(active: true);
    _lastReportAt = fix.time;
    _syncRemote();
    unawaited(ref.read(phrasePlayerProvider).play(FixedPhrase.startTour));
    _positions = location.positions().listen(_onRawFix);
    _timer = Timer.periodic(ref.read(tourTickIntervalProvider), (_) => tick());
  }

  Future<void> end() async {
    if (!state.active) return;
    final settings = ref.read(settingsProvider);
    _session++;
    _cancelWatching();
    _resetTour();
    state = const TourState();
    _syncRemote();
    await ref.read(narrationPlayerProvider).stop();
    try {
      await ref.read(tourApiProvider).end(settings);
    } on TourApiException catch (error) {
      debugPrint('通知主機結束失敗（主機會在下次出發時重置）：$error');
    }
  }

  void pause() {
    if (!state.active || state.paused) return;
    state = state.copyWith(paused: true);
    unawaited(ref.read(narrationPlayerProvider).pause());
    _syncRemote();
  }

  void resume() {
    if (!state.active || !state.paused) return;
    state = state.copyWith(paused: false);
    unawaited(ref.read(narrationPlayerProvider).resume());
    _syncRemote();
    _evaluate();
  }

  /// 問主機有什麼新的準備好了，然後看現在該不該播。
  ///
  /// 連不上主機時照退避間隔重試；已經下載好的介紹仍照常評估播放。
  Future<void> tick() async {
    if (!state.active) return;
    final session = _session;
    if (!_polling && _host.canTry(_now)) {
      _polling = true;
      try {
        if (!await _poll(session)) return;
      } finally {
        if (session == _session) _polling = false;
      }
    }
    if (session == _session) _evaluate();
  }

  /// 回傳 false 代表這一輪已處理完畢（例如主機重新開始），不必再評估播放。
  Future<bool> _poll(int session) async {
    final settings = ref.read(settingsProvider);
    try {
      final poll = await ref
          .read(tourApiProvider)
          .poll(settings, after: _cursor);
      if (session != _session) return false;
      _onHostReached();
      state = state.copyWith(stoppedReason: poll.stoppedReason);
      if (!poll.active) {
        await _restartOnHost(session);
        return false;
      }
      for (final info in poll.narrations) {
        if (info.seq > _cursor) _cursor = info.seq;
        if (_seen.add(info.id)) {
          _queue.add(QueuedNarration(info, _now));
          _audio[info.id] = _download(info.id, session);
        }
      }
    } on TourApiException catch (error) {
      debugPrint('輪詢主機失敗：$error');
      _onHostFailed(session);
    }
    return true;
  }

  void _onHostFailed(int session) {
    if (session == _session && _host.recordFailure(_now)) {
      _unreachableDue = true;
    }
  }

  /// 連上主機：恢復是安靜的（不念），並把斷線期間沒送出的最新位置補報。
  void _onHostReached() {
    if (!_host.recordSuccess()) return;
    _unreachableDue = false;
    final position = _position;
    if (position != null) _reportNow(position);
  }

  void _reportNow(PositionFix fix) {
    _lastReportAt = fix.time;
    unawaited(_report(fix));
  }

  Future<void> _restartOnHost(int session) async {
    final position = _position;
    if (position == null) return;
    try {
      await ref
          .read(tourApiProvider)
          .start(
            ref.read(settingsProvider),
            position,
            ref.read(travelerProvider),
          );
      if (session == _session) _cursor = 0; // 主機重新開始計數
    } on TourApiException catch (error) {
      debugPrint('重新通知主機出發失敗：$error');
    }
  }

  /// 失敗回傳 null：算一次斷線，介紹留在佇列裡，主機回來後再抓。
  Future<Uint8List?> _download(String id, int session) async {
    try {
      final bytes = await ref
          .read(tourApiProvider)
          .downloadAudio(ref.read(settingsProvider), id);
      if (session == _session) _onHostReached();
      return bytes;
    } on TourApiException catch (error) {
      debugPrint('下載 $id 失敗：$error');
      _onHostFailed(session);
      return null;
    }
  }

  void _onRawFix(RawFix raw) {
    if (!state.active) return;
    final fix = _fixFrom(raw);
    final lastReport = _lastReportAt;
    if (_host.reachable &&
        (lastReport == null ||
            fix.time.difference(lastReport) >=
                ref.read(locationReportIntervalProvider))) {
      _reportNow(fix);
    }
    _evaluate();
  }

  PositionFix _fixFrom(RawFix raw) {
    final fix = PositionFix(
      lat: raw.lat,
      lon: raw.lon,
      time: _now,
      heading: _heading.update(raw.lat, raw.lon),
    );
    _position = fix;
    return fix;
  }

  Future<void> _report(PositionFix fix) async {
    try {
      await ref
          .read(tourApiProvider)
          .reportLocation(
            ref.read(settingsProvider),
            fix,
            ref.read(travelerProvider),
          );
    } on TourApiException catch (error) {
      debugPrint('回報位置失敗：$error');
    }
  }

  void _evaluate() {
    if (!state.active) return;
    if (_unreachableDue && !_busy && !state.paused) {
      _unreachableDue = false;
      unawaited(
        ref.read(phrasePlayerProvider).play(FixedPhrase.hostUnreachable),
      );
      return; // 短句念完前不開始介紹，下一輪再評估
    }
    if (_host.canTry(_now)) {
      for (final item in _queue) {
        _audio.putIfAbsent(
          item.info.id,
          () => _download(item.info.id, _session),
        );
      }
    }
    final decision = ref
        .read(playbackPolicyProvider)
        .decide(
          now: _now,
          position: _position,
          queue: List.of(_queue),
          lastFinishedAt: _lastFinishedAt,
          paused: state.paused,
          busy: _busy,
        );
    for (final stale in decision.drop) {
      _queue.remove(stale);
      _audio.remove(stale.info.id);
    }
    final next = decision.play;
    if (next != null) {
      _queue.remove(next);
      unawaited(_playNarration(next));
    }
  }

  Future<void> _playNarration(QueuedNarration item) async {
    _busy = true; // 同步設定，下一次評估就不會再開始別段
    final session = _session;
    final bytes = await _audio.remove(item.info.id);
    if (session != _session) return;
    if (bytes == null) {
      // 下載失敗：放回去，主機回來後 _evaluate 會再抓
      _queue.insert(0, item);
      _busy = false;
      return;
    }
    if (state.paused) {
      // 等音檔的時候使用者按了暫停：先放回去，繼續後再講
      _queue.insert(0, item);
      _audio[item.info.id] = Future.value(bytes);
      _busy = false;
      return;
    }

    state = state.copyWith(nowPlaying: item.info.name);
    _syncRemote(title: item.info.name);
    try {
      await ref
          .read(narrationPlayerProvider)
          .play(bytes, title: item.info.name);
    } on Exception catch (error) {
      debugPrint('播放 ${item.info.id} 失敗：$error');
    } finally {
      if (session == _session) {
        _lastFinishedAt = _now;
        _busy = false;
        state = state.copyWith(nowPlaying: null);
        _syncRemote();
      }
    }
  }

  void _syncRemote({String? title}) {
    ref
        .read(remoteControlsProvider)
        .update(
          tourActive: state.active,
          paused: state.paused,
          title: title ?? state.nowPlaying,
        );
  }

  void _cancelWatching() {
    _positions?.cancel();
    _positions = null;
    _timer?.cancel();
    _timer = null;
  }

  void _resetTour() {
    _heading = HeadingTracker();
    _position = null;
    _lastReportAt = null;
    _lastFinishedAt = null;
    _cursor = 0;
    _busy = false;
    _host = HostReachability();
    _unreachableDue = false;
    _polling = false;
    _queue.clear();
    _audio.clear();
    _seen.clear();
  }
}
