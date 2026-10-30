import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../audio/fixed_phrase.dart';
import '../audio/narration_player.dart';
import '../audio/phrase_player.dart';
import '../audio/remote_controls.dart';
import '../host/host_connection.dart';
import '../voice/voice_controller.dart';
import 'geo.dart';
import 'host_reachability.dart';
import 'location_permission.dart';
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
    this.locationAccess = LocationAccess.always,
    this.voiceChanging = false,
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

  /// 這一趟拿到的定位權限程度；不是「永遠」時畫面會提醒鎖定螢幕可能收不到位置。
  final LocationAccess locationAccess;

  /// 旅程中換了聲音、新聲音的介紹還沒開始：畫面提示「這段播完就換，下一段準備中…」。
  final bool voiceChanging;

  TourState copyWith({
    bool? active,
    bool? paused,
    Object? nowPlaying = _keep,
    Object? stoppedReason = _keep,
    Object? error = _keep,
    Object? summary = _keep,
    LocationAccess? locationAccess,
    bool? voiceChanging,
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
    locationAccess: locationAccess ?? this.locationAccess,
    voiceChanging: voiceChanging ?? this.voiceChanging,
  );
}

const Object _keep = Object();

/// 換聲音時告訴主機的播放狀況，見 [TourController.playbackReport]。
typedef PlaybackReport = ({String? playingId, List<String> playedIds});

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
  // 使用者點了新聲音、還沒換好或失敗：不開始任何介紹（正在播的照常播完）。
  // 跟著換聲音的請求走、不跟旅程走，所以出發／結束時不歸零：切換途中重新出發，
  // 新的這趟在換好之前也不會開播，換好時就不會有這趟的回報被當成已隨切換送出
  int _voiceHolds = 0;
  _Playing? _playing; // 正在播（含使用者暫停中、或被問題打斷等著接續）的介紹
  _Interrupted? _interrupted; // 被問題打斷、等答完從那一句的開頭接著播
  QueuedNarration? _starting; // 輪到它播、正在等音檔（已不在佇列裡）

  /// 佇列裡的介紹該是哪個聲音（聲音鍵）；舊主機沒有聲音鍵時是 null（什麼都收）。
  String? _voiceKey;
  int _voiceSwitches = 0; // 每換一次聲音加一，讓換之前送出的請求自己作廢

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

  /// 使用者點了新聲音：換好（[useVoice]）或失敗之前，不開始任何舊聲音的介紹，被問題打斷的也先不接。
  /// 正在播的照常播完。可以疊加（切換中又點了別的），每個 hold 都要有對應的 [releaseVoiceSwitch]。
  void holdForVoiceSwitch() => _voiceHolds++;

  void releaseVoiceSwitch() {
    if (_voiceHolds > 0) _voiceHolds--;
    if (_voiceHolds == 0) _evaluate();
  }

  /// 換聲音的請求要帶的：正在播、會用舊聲音播完的那段（主機不必重做），以及主機該先記成講過的
  /// （播完了還沒送達的回報，加上被問題打斷、換了聲音就不再接續的那段）。
  PlaybackReport get playbackReport {
    final playing = _playing;
    final interrupted = _interrupted?.playing;
    return (
      playingId:
          playing == null || playing.finished || identical(playing, interrupted)
          ? null
          : playing.item.info.id,
      playedIds: [..._unreportedPlayed, ?interrupted?.item.info.id],
    );
  }

  /// 使用者換了聲音、主機已經換成這個聲音（聲音鍵）：旅程中提示「這段播完就換，下一段準備中…」。
  /// [reported] 是隨換聲音的請求送出、主機已記成講過的（[playbackReport] 的 playedIds）。
  void useVoice(String key, {List<String> reported = const []}) {
    _unreportedPlayed.removeWhere(reported.contains);
    if (key == _voiceKey) return;
    _switchTo(key, reported: reported);
    if (state.active) state = state.copyWith(voiceChanging: true);
  }

  /// 佇列裡別的聲音的介紹丟掉（正在播的那段照常播完），也不再算「看過」，
  /// 主機用新聲音重做的同一個景點（同一個 id）才進得來。被問題打斷的那段不接續、算講過。
  void _switchTo(String key, {List<String> reported = const []}) {
    _voiceKey = key;
    _voiceSwitches++;
    if (!state.active) return;
    _dropInterrupted(reported);
    for (final item in _queue.where((q) => !_inCurrentVoice(q.info)).toList()) {
      _queue.remove(item);
      _audio.remove(item.info.id);
      _seen.remove(item.info.id);
    }
    // 正在等音檔的那段主機也撤下了（它還沒開始播，不是 playing_id）：音檔回來時不播
    final starting = _starting;
    if (starting != null) _seen.remove(starting.info.id);
  }

  /// 換了聲音：被打斷的舊聲音介紹不接著講（也不用新聲音重講），當作講完了。
  /// 主機還不知道的（打斷時換聲音的請求已經送出）照一般播完回報。
  void _dropInterrupted(List<String> reported) {
    final interrupted = _interrupted;
    if (interrupted == null) return;
    _interrupted = null;
    final playing = interrupted.playing;
    final id = playing.item.info.id;
    if (!reported.contains(id)) _notePlayed(id, _session);
    // 被打斷時 _playBytes 刻意沒收尾（還在「講」這一段）：替它收尾，下一段才開得了
    _finishPlaying(playing);
  }

  bool _inCurrentVoice(NarrationInfo info) =>
      info.voice == null || _voiceKey == null || info.voice == _voiceKey;

  /// 旅程中主機的聲音和 App 記的不同（例如換聲音的回應沒收到）：跟上主機，補下載它的短句。
  void _followHost(String key) {
    _switchTo(key);
    if (ref.read(voiceProvider).current?.key != key) {
      unawaited(ref.read(voiceProvider.notifier).refresh());
    }
  }

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
    _voiceKey = ref.read(voiceProvider).current?.key;
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

    state = TourState(active: true, locationAccess: location.access);
    _lastReportAt = fix.time;
    _syncRemote();
    unawaited(ref.read(phrasePlayerProvider).play(FixedPhrase.startTour));
    _positions = location.positions().listen(_onRawFix);
    _timer = Timer.periodic(ref.read(tourTickIntervalProvider), (_) => tick());
  }

  /// App 回到前景：使用者可能剛到「設定」把定位改成「永遠」，重讀一次讓畫面的提醒跟上。
  Future<void> refreshLocationAccess() async {
    if (!state.active) return;
    final session = _session;
    final access = await ref.read(locationSourceProvider).refreshAccess();
    if (session == _session && state.active) {
      state = state.copyWith(locationAccess: access);
    }
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
    final switches = _voiceSwitches;
    try {
      final poll = await ref
          .read(tourApiProvider)
          .poll(settings, after: _cursor);
      if (session != _session) return false;
      _onHostReached();
      unawaited(_reportPlayed(session)); // 連得上了：把之前送不出去的補送
      // 換聲音之前送出的：裡面可能有舊聲音的介紹、或把聲音拉回去。不採用，游標不動，下一輪重抓
      if (switches != _voiceSwitches) return true;
      state = state.copyWith(stoppedReason: poll.stoppedReason);
      if (!poll.active) {
        await _restartOnHost(session);
        return false;
      }
      final voice = poll.voice;
      if (voice != null && voice != _voiceKey) _followHost(voice);
      for (final info in poll.narrations) {
        if (info.seq > _cursor) _cursor = info.seq;
        // 換聲音之前做好的：主機會用新聲音重做（同一個 id、新的 seq）
        if (!_inCurrentVoice(info)) continue;
        if (_seen.add(info.id)) {
          _gone.remove(info.id); // 主機重新發布了：之前的「不存在」作廢
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
    final switches = _voiceSwitches;
    try {
      final bytes = await ref
          .read(tourApiProvider)
          .downloadAudio(ref.read(settingsProvider), id);
      if (session == _session) _onHostReached();
      return bytes;
    } on TourApiException catch (error) {
      debugPrint('下載 $id 失敗：$error');
      if (error.statusCode == 404) {
        // 換聲音之後才回來的 404 是撤下的舊版：同一個 id 可能正要用新聲音重做，不記成不存在
        if (session == _session && switches == _voiceSwitches) {
          _gone.add(id);
          // 主機之後若重新發布同一個 id（例如換聲音重做），要進得來
          _seen.remove(id);
        }
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
      // 被問題打斷的介紹先接著講完；使用者按了暫停就等他按繼續，正在換聲音就等換好
      // （換成了就不接）
      if (!state.paused && _voiceHolds == 0) unawaited(_resumeInterrupted());
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
          paused: state.paused || _voiceHolds > 0,
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
    final switches = _voiceSwitches;
    _starting = item;
    final bytes = await _audio.remove(item.info.id);
    if (session != _session) return;
    _starting = null;
    if (switches != _voiceSwitches) {
      // 等音檔的時候換了聲音（即使又換回來）：主機已撤下這段、會重做，不播也不放回去
      _busy = false;
      return;
    }
    if (bytes == null) {
      // 下載失敗：放回去，主機回來後 _evaluate 會再抓（已經不存在的就不放回去）
      if (!_gone.contains(item.info.id)) _queue.insert(0, item);
      _busy = false;
      return;
    }
    if (state.paused || _questionHolds > 0 || _voiceHolds > 0) {
      // 等音檔的時候使用者按了暫停、開始發問、或點了新聲音：先放回去，之後再講
      _queue.insert(0, item);
      _audio[item.info.id] = Future.value(bytes);
      _busy = false;
      return;
    }
    await _playBytes(session, item, bytes, Duration.zero);
  }

  /// 播一段介紹（或從 [start] 接著播）。被問題打斷時不算播完，也不收尾（還在「講」這一段）。
  Future<void> _playBytes(
    int session,
    QueuedNarration item,
    Uint8List bytes,
    Duration start,
  ) async {
    state = state.copyWith(
      nowPlaying: item.info.name,
      // 新聲音的介紹開始了：不必再提示「下一段準備中」
      voiceChanging: state.voiceChanging && !_inCurrentVoice(item.info),
    );
    _syncRemote(title: item.info.name);
    final playing = _Playing(item, bytes);
    _playing = playing;
    try {
      final completed = await ref
          .read(narrationPlayerProvider)
          .play(bytes, title: item.info.name, start: start);
      if (completed && session == _session) {
        playing.finished = true;
        // 剛好在播完的同一刻被問：已經講完了，答完不用再接
        if (_interrupted?.playing == playing) _interrupted = null;
        // 播到最後才算講過（被打斷、結束時被停掉的不算）
        _notePlayed(item.info.id, session);
      }
    } on Exception catch (error) {
      debugPrint('播放 ${item.info.id} 失敗：$error');
    } finally {
      if (session == _session && (playing.finished || !playing.interrupted)) {
        _finishPlaying(playing);
      }
      playing.done.complete(); // 這一次播放（含收尾）結束了：接續才可以開始
    }
  }

  void _finishPlaying(_Playing playing) {
    if (identical(_playing, playing)) _playing = null;
    _lastFinishedAt = _now;
    _busy = false;
    state = state.copyWith(nowPlaying: null);
    _syncRemote();
  }

  /// 發問開始：停下正在播的介紹，記住要從哪一句的開頭接著播。
  Future<void> _interruptNarration() async {
    final playing = _playing;
    // 已經播完的不用打斷；已經在等著接續的（例如使用者暫停中又問一次）要保留原本的接續點，
    // 這時播放器已經停了，位置不可靠
    if (playing == null || playing.finished || playing.interrupted) return;
    playing.interrupted = true;
    final player = ref.read(narrationPlayerProvider);
    _interrupted = _Interrupted(
      playing,
      resumePoint(player.position, playing.item.info.unitStarts),
    );
    // 不釋放 audio focus：緊接著要念短句、播答案，其他 App 的音量不要在中間跳回來
    await player.stop(releaseFocus: false);
  }

  Future<void> _resumeInterrupted() async {
    final interrupted = _interrupted;
    if (interrupted == null) return;
    _interrupted = null; // 同步清掉，下一次評估不會再接一次
    final session = _session;
    // 被停掉的那一次播放要先收尾完（播放器、暫存檔），才能開始下一次
    await interrupted.playing.done.future;
    if (session != _session) return;
    if (_questionHolds > 0 || state.paused || _voiceHolds > 0) {
      // 等收尾的時候又開始發問、使用者按了暫停、或點了新聲音：接續點留著，等之後
      _interrupted = interrupted;
      return;
    }
    await _playBytes(
      session,
      interrupted.playing.item,
      interrupted.playing.bytes,
      interrupted.resumeAt,
    );
  }

  /// 告訴主機這段講過了；主機一直不收就只留最近的，不無限累積。
  void _notePlayed(String id, int session) {
    _unreportedPlayed.add(id);
    if (_unreportedPlayed.length > _maxUnreportedPlayed) {
      _unreportedPlayed.removeAt(0);
    }
    unawaited(_reportPlayed(session));
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
    _starting = null;
  }
}

/// 一次播放。每次播放各有一個，旗標與完成訊號不會和下一次混在一起。
class _Playing {
  _Playing(this.item, this.bytes);

  final QueuedNarration item;
  final Uint8List bytes;

  /// 被問題打斷了（等答完接著播）。
  bool interrupted = false;

  /// 自然播到最後。
  bool finished = false;

  /// 這一次播放（含收尾）結束。
  final done = Completer<void>();
}

class _Interrupted {
  const _Interrupted(this.playing, this.resumeAt);

  final _Playing playing;

  /// 答完要從這裡接著播（被打斷那一句的開頭）。
  final Duration resumeAt;
}
