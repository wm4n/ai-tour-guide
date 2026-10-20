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
import 'resume_point.dart';
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
    this.summary,
  });

  final bool active;

  /// 使用者按了暫停鍵：主動介紹暫停，繼續之前不會開始新的。
  final bool paused;
  final String? nowPlaying;

  /// 主機停止準備的原因（`quota` 等）；畫面提示用，不念出來。
  final String? stoppedReason;
  final String? error;

  /// 上一趟結束時主機回報的用量摘要；下一次出發就清掉。
  final TourSummary? summary;

  TourState copyWith({
    bool? active,
    bool? paused,
    Object? nowPlaying = _keep,
    Object? stoppedReason = _keep,
    Object? error = _keep,
    Object? summary = _keep,
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
    summary: identical(summary, _keep) ? this.summary : summary as TourSummary?,
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
  final _unreportedPlayed = <String>[]; // 播完了、還沒成功告訴主機的
  static const _maxUnreportedPlayed = 20;
  bool _reportingPlayed = false;
  bool _polling = false; // 輪詢逾時比 tick 間隔長，不讓它們疊在一起
  final _queue = <QueuedNarration>[];
  final _audio = <String, Future<Uint8List?>>{};
  final _seen = <String>{};
  final _gone = <String>{}; // 主機已經沒有的介紹（下載回 404）：丟掉，不重試
  int _questionHolds = 0; // 使用者正在發問、等答案或聽答案：不開始新的主動介紹
  _Playing? _playing; // 正在播（含使用者暫停中）的介紹
  _Interrupted? _interrupted; // 被問題打斷、等答完從那一句的開頭接著播

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

  /// 最近一次定位；問答要把它連同問題一起送給主機。還沒出發或還沒定位時是 null。
  PositionFix? get position => _position;

  /// 使用者開始發問：正在播的介紹先停下、記住位置，到 [endQuestion] 之前不開始新的主動介紹
  /// （也不念「連不上主機」），免得蓋過答案。答完從被打斷的那一句的開頭接著播。
  /// 可以疊加，每個 begin 都要有對應的 end。
  void beginQuestion() {
    _questionHolds++;
    if (_questionHolds == 1) unawaited(_interruptNarration());
  }

  void endQuestion() {
    if (_questionHolds > 0) _questionHolds--;
    if (_questionHolds == 0) _evaluate();
  }

  /// 問答連不上主機：和輪詢失敗一樣算一次斷線（只念一次「連不上」，並退避重試）。
  void noteHostFailed() => _onHostFailed(_session);

  /// 問答連上了主機：結束斷線，安靜恢復。
  void noteHostReached() => _onHostReached();

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
      final summary = await ref.read(tourApiProvider).end(settings);
      if (!state.active) state = state.copyWith(summary: summary);
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
      unawaited(_reportPlayed(session)); // 連得上了：把之前送不出去的補送
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
  /// 例外是 404：主機還在、只是這段已經不存在（例如主機重啟過），不算斷線，直接丟掉。
  Future<Uint8List?> _download(String id, int session) async {
    try {
      final bytes = await ref
          .read(tourApiProvider)
          .downloadAudio(ref.read(settingsProvider), id);
      if (session == _session) _onHostReached();
      return bytes;
    } on TourApiException catch (error) {
      debugPrint('下載 $id 失敗：$error');
      if (error.statusCode == 404) {
        if (session == _session) _gone.add(id);
        return null;
      }
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
    if (!state.active || _questionHolds > 0) return;
    if (_interrupted != null) {
      // 被問題打斷的介紹先接著講完；使用者按了暫停就等他按繼續
      if (!state.paused) unawaited(_resumeInterrupted());
      return;
    }
    if (_unreachableDue && !_busy && !state.paused) {
      _unreachableDue = false;
      unawaited(
        ref.read(phrasePlayerProvider).play(FixedPhrase.hostUnreachable),
      );
      return; // 短句念完前不開始介紹，下一輪再評估
    }
    for (final item
        in _queue.where((q) => _gone.contains(q.info.id)).toList()) {
      _queue.remove(item);
      _audio.remove(item.info.id);
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
      // 下載失敗：放回去，主機回來後 _evaluate 會再抓（已經不存在的就不放回去）
      if (!_gone.contains(item.info.id)) _queue.insert(0, item);
      _busy = false;
      return;
    }
    if (state.paused || _questionHolds > 0) {
      // 等音檔的時候使用者按了暫停、或開始發問：先放回去，之後再講
      _queue.insert(0, item);
      _audio[item.info.id] = Future.value(bytes);
      _busy = false;
      return;
    }
    await _playBytes(session, item, bytes, Duration.zero);
  }

  /// 播一段介紹（或從 [start] 接著播）。被問題打斷時不算播完，也不放掉「正在播」的狀態。
  Future<void> _playBytes(
    int session,
    QueuedNarration item,
    Uint8List bytes,
    Duration start,
  ) async {
    state = state.copyWith(nowPlaying: item.info.name);
    _syncRemote(title: item.info.name);
    _playing = _Playing(item, bytes);
    try {
      final completed = await ref
          .read(narrationPlayerProvider)
          .play(bytes, title: item.info.name, start: start);
      if (completed && session == _session) {
        // 播到最後才算講過（被打斷、結束時被停掉的不算）；主機一直不收就只留最近的，不無限累積
        _unreportedPlayed.add(item.info.id);
        if (_unreportedPlayed.length > _maxUnreportedPlayed) {
          _unreportedPlayed.removeAt(0);
        }
        unawaited(_reportPlayed(session));
      }
    } on Exception catch (error) {
      debugPrint('播放 ${item.info.id} 失敗：$error');
    } finally {
      // 被問題打斷時（等答完接著播）還在「講」這一段，不收尾
      if (session == _session && _interrupted?.item != item) {
        _playing = null;
        _lastFinishedAt = _now;
        _busy = false;
        state = state.copyWith(nowPlaying: null);
        _syncRemote();
      }
    }
  }

  /// 發問開始：停下正在播的介紹，記住要從哪一句的開頭接著播。
  Future<void> _interruptNarration() async {
    final playing = _playing;
    if (playing == null) return;
    final player = ref.read(narrationPlayerProvider);
    _interrupted = _Interrupted(
      playing.item,
      playing.bytes,
      resumePoint(player.position, playing.item.info.unitStarts),
    );
    await player.stop();
  }

  Future<void> _resumeInterrupted() async {
    final interrupted = _interrupted;
    if (interrupted == null) return;
    _interrupted = null; // 同步清掉，下一次評估不會再接一次
    await _playBytes(
      _session,
      interrupted.item,
      interrupted.bytes,
      interrupted.resumeAt,
    );
  }

  /// 一次一個、照順序送；送不出去就留著，下次輪詢連上時再送。不算斷線（輪詢才是心跳）。
  Future<void> _reportPlayed(int session) async {
    if (_reportingPlayed) return;
    _reportingPlayed = true;
    try {
      while (_unreportedPlayed.isNotEmpty && session == _session) {
        final id = _unreportedPlayed.first;
        await ref
            .read(tourApiProvider)
            .markPlayed(ref.read(settingsProvider), id);
        if (session != _session) return;
        _unreportedPlayed.remove(id);
      }
    } on TourApiException catch (error) {
      debugPrint('回報播完失敗（連上後再送）：$error');
    } finally {
      if (session == _session) _reportingPlayed = false;
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
    _unreportedPlayed.clear();
    _reportingPlayed = false;
    _queue.clear();
    _audio.clear();
    _seen.clear();
    _gone.clear();
    _questionHolds = 0;
    _playing = null;
    _interrupted = null;
  }
}

class _Playing {
  const _Playing(this.item, this.bytes);

  final QueuedNarration item;
  final Uint8List bytes;
}

class _Interrupted {
  const _Interrupted(this.item, this.bytes, this.resumeAt);

  final QueuedNarration item;
  final Uint8List bytes;

  /// 答完要從這裡接著播（被打斷那一句的開頭）。
  final Duration resumeAt;
}
