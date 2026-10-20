import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;

import '../audio/fixed_phrase.dart';
import '../audio/narration_player.dart';
import '../audio/phrase_player.dart';
import '../host/host_connection.dart';
import '../tour/playback_policy.dart';
import '../tour/tour_api.dart';
import '../tour/tour_controller.dart';
import 'compass_source.dart';
import 'photo_source.dart';
import 'qa_api.dart';
import 'speech_recognizer.dart';

final qaApiProvider = Provider<QaApi>((ref) {
  final client = http.Client();
  ref.onDispose(client.close);
  return HttpQaApi(client);
});

/// 拍照提問用的相機與指南針；模擬器沒有，端到端測試改用固定的假來源（見 main.dart）。
final photoSourceProvider = Provider<PhotoSource>((ref) => CameraPhotoSource());

final compassSourceProvider = Provider<CompassSource>(
  (ref) => FlutterCompassSource(),
);

final speechRecognizerProvider = Provider<SpeechRecognizer>(
  (ref) => SpeechToTextRecognizer(),
);

final questionListenerProvider = Provider<QuestionListener>(
  (ref) => QuestionListener(ref.watch(speechRecognizerProvider)),
);

/// 播答案各段的播放器（和主動介紹的播放器分開，檔名也不同）。
final answerPlayerProvider = Provider<NarrationPlayer>(
  (ref) => throw UnimplementedError('answerPlayerProvider must be overridden'),
);

final qaPollIntervalProvider = Provider<Duration>(
  (ref) => const Duration(milliseconds: 600),
);

/// 問完這麼久還沒有任何一段答案，就補一句「我想想怎麼說比較好」。
final qaSlowAfterProvider = Provider<Duration>(
  (ref) => const Duration(seconds: 8),
);

/// 等答案的上限；主機可能還在做，但使用者不會一直等。
final qaTimeoutProvider = Provider<Duration>(
  (ref) => const Duration(minutes: 2),
);

enum QaPhase {
  idle,
  listening, // 按住中
  photographing, // 相機開著，等使用者拍照
  asking, // 放開了，辨識完成、送出去、等第一段答案
  answering, // 答案的語音已經開始（或排好要播）
}

class QaState {
  const QaState({
    this.phase = QaPhase.idle,
    this.searchingWeb = false,
    this.error,
    this.quotaExhausted = false,
    this.mode,
  });

  final QaPhase phase;

  /// 主機說 Claude 正在上網查。
  final bool searchingWeb;

  /// 這一題沒能完成的原因（畫面提示用）；下一次按住說話就清掉。
  final String? error;

  /// Claude 額度用完：畫面提示、不念；下一次發問會再試（主機額度恢復後就會成功）。
  final bool quotaExhausted;

  /// 最近一次實際採用的辨識方式（本機或線上）。
  final RecognitionMode? mode;

  QaState copyWith({
    QaPhase? phase,
    bool? searchingWeb,
    Object? error = _keep,
    bool? quotaExhausted,
    Object? mode = _keep,
  }) => QaState(
    phase: phase ?? this.phase,
    searchingWeb: searchingWeb ?? this.searchingWeb,
    error: identical(error, _keep) ? this.error : error as String?,
    quotaExhausted: quotaExhausted ?? this.quotaExhausted,
    mode: identical(mode, _keep) ? this.mode : mode as RecognitionMode?,
  );
}

const Object _keep = Object();

final qaProvider = NotifierProvider<QaController, QaState>(QaController.new);

/// 「再多說一點」：主機要在旅程摘要裡帶上剛剛講的那段（設計文件第 8 節）。
bool isMoreRequest(String text) {
  const phrases = ['再多說', '多說一點', '再說一點', '再多講', '多講一點', '再講一點', '說多一點'];
  return phrases.any(text.contains);
}

/// 一次按住說話發問的完整流程：辨識 → 立刻回一句短句 → 送給主機 → 一段一段下載並播出答案。
class QaController extends Notifier<QaState> {
  static const _maxPollFailures = 3;

  int _generation = 0; // 每次按下、取消加一，讓遲到的非同步結果自己作廢
  RecognitionSession? _session;
  bool _releaseRequested = false; // 麥克風還沒開好就放開了
  bool _holding = false; // 已經通知旅程「正在發問」
  int _openings = 0;
  Future<void> _audio = Future.value(); // 要念、要播的東西排成一列，一件一件來
  Future<void>? _starting; // 最近一次「開麥克風」；沒收乾淨之前，下一次不能開始

  @override
  QaState build() {
    ref.onDispose(() => _generation++);
    ref.listen(tourProvider, (previous, next) {
      // 旅程結束：還在進行的發問就不用了
      if ((previous?.active ?? false) &&
          !next.active &&
          state.phase != QaPhase.idle) {
        unawaited(cancel());
      }
    });
    return const QaState();
  }

  DateTime get _now => ref.read(clockProvider)();

  /// 按下：開始聽。
  Future<void> press() async {
    if (state.phase != QaPhase.idle) return;
    if (!ref.read(tourProvider).active) {
      state = QaState(error: '出發之後才能發問', mode: state.mode);
      return;
    }
    final generation = ++_generation;
    _releaseRequested = false;
    state = QaState(phase: QaPhase.listening, mode: state.mode);
    _hold();
    final started = _start(generation, _starting);
    _starting = started.then<void>((_) {}, onError: (Object _) {});
    final session = await started;
    if (session == null) return; // 失敗已經顯示，或這次已經被取消
    _session = session;
    state = state.copyWith(mode: ref.read(questionListenerProvider).mode);
    if (_releaseRequested) _submitInBackground(generation);
  }

  /// 開麥克風。上一次的錄音還沒收乾淨時先等它：舊的那次回來發現已取消，會對同一個辨識引擎
  /// 呼叫 cancel，不等的話會把新的錄音一起殺掉。回傳 null＝失敗（已顯示）或已被取消。
  Future<RecognitionSession?> _start(
    int generation,
    Future<void>? previous,
  ) async {
    if (previous != null) await previous;
    if (generation != _generation) return null;
    final RecognitionSession session;
    try {
      session = await ref.read(questionListenerProvider).start();
    } on SpeechPermissionDenied {
      _fail(generation, '需要麥克風與語音辨識的權限，請到「設定」開啟');
      return null;
    } on RecognitionFailed catch (error) {
      _fail(generation, '語音辨識失敗：${error.message}');
      return null;
    } on Exception catch (error) {
      debugPrint('開始聽失敗：$error');
      _fail(generation, '無法開始聽，再試一次');
      return null;
    }
    if (generation != _generation) {
      await session.cancel(); // 等麥克風的時候已經取消了
      return null;
    }
    return session;
  }

  /// 放開：問完了。辨識、送出、等答案、播答案都在背景進行，這裡立刻回來。
  Future<void> release() async {
    if (state.phase != QaPhase.listening) return;
    if (_session == null) {
      _releaseRequested = true; // 麥克風開好之後馬上送出
      return;
    }
    _submitInBackground(_generation);
  }

  /// 放棄這次發問（旅程結束、離開畫面）：丟掉錄音、停止播放、不再輪詢。
  Future<void> cancel() async {
    _generation++;
    final session = _session;
    _session = null;
    _releaseRequested = false;
    _unhold();
    state = QaState(mode: state.mode);
    if (session != null) await session.cancel();
    await ref.read(phrasePlayerProvider).stop();
    final player = ref.read(answerPlayerProvider);
    await player.stop();
    await player.release(); // 答案各段不釋放 focus；被取消時要補上，不然其他 App 會一直被壓低
  }

  void _submitInBackground(int generation) =>
      _inBackground(generation, () => _submit(generation));

  void _inBackground(int generation, Future<void> Function() flow) {
    unawaited(
      flow().catchError((Object error, StackTrace stack) {
        // 任何沒料到的錯都不能讓畫面卡在「處理中」
        debugPrint('發問流程出錯：$error\n$stack');
        _fail(generation, '這題出了點問題，再問一次看看');
      }),
    );
  }

  Future<void> _submit(int generation) async {
    final session = _session!;
    _session = null;
    state = state.copyWith(phase: QaPhase.asking);
    // 放開的當下就回一句：讓人知道有聽到、在處理，不用等辨識的最終結果（最久要等幾秒）。
    // 麥克風已經停了，不會把這句錄進去。
    _sayOpening();
    String heard;
    try {
      heard = (await session.finish()).trim();
    } on Exception catch (error) {
      debugPrint('結束辨識失敗：$error');
      heard = '';
    }
    if (generation != _generation) return;
    if (heard.isEmpty) {
      _fail(generation, '沒聽清楚，再說一次');
      return;
    }
    await _send(
      generation,
      '問題送不出去',
      (position) => ref
          .read(qaApiProvider)
          .ask(
            ref.read(settingsProvider),
            heard,
            position,
            ref.read(travelerProvider),
            more: isMoreRequest(heard),
          ),
    );
  }

  /// 拍照提問：開相機 → 讀指南針 → 回一句短句 → 連照片送給主機 → 之後和一般問答一樣聽答案。
  /// 使用者取消拍照就安靜結束（暫停的介紹接著播）。開相機之後的流程在背景進行，這裡立刻回來。
  Future<void> askWithPhoto() async {
    if (state.phase != QaPhase.idle) return;
    if (!ref.read(tourProvider).active) {
      state = QaState(error: '出發之後才能發問', mode: state.mode);
      return;
    }
    final generation = ++_generation;
    state = QaState(phase: QaPhase.photographing, mode: state.mode);
    _hold(); // 相機一開，正在播的介紹就先停下（也不要讓新的介紹蓋過拍照）
    _inBackground(generation, () => _photoFlow(generation));
  }

  Future<void> _photoFlow(int generation) async {
    final Uint8List? photo;
    try {
      photo = await ref.read(photoSourceProvider).take();
    } on PhotoUnavailable catch (error) {
      _fail(generation, error.message);
      return;
    }
    if (generation != _generation) return;
    if (photo == null) {
      _finish(generation); // 使用者取消：沒有發生過這件事
      return;
    }
    // 照片拍完、手機還對著那個東西：這時讀指南針
    final compass = await ref.read(compassSourceProvider).cameraHeading();
    if (generation != _generation) return;
    state = state.copyWith(phase: QaPhase.asking);
    _sayOpening();
    await _send(
      generation,
      '照片送不出去',
      (position) => ref
          .read(qaApiProvider)
          .askPhoto(
            ref.read(settingsProvider),
            '這是什麼？',
            position,
            ref.read(travelerProvider),
            photo!,
            compassHeading: compass,
          ),
    );
  }

  /// 把問題送給主機並開始聽答案；[send] 回傳答案的 id。
  Future<void> _send(
    int generation,
    String failure,
    Future<String> Function(PositionFix position) send,
  ) async {
    final tour = ref.read(tourProvider.notifier);
    final position = tour.position;
    if (position == null) {
      _fail(generation, '還沒有定位，等一下再問');
      return;
    }
    final String id;
    try {
      id = await send(position);
    } on TourApiException catch (error) {
      _hostFailed(generation, error, failure);
      return;
    }
    if (generation != _generation) return;
    tour.noteHostReached();
    await _follow(generation, id);
  }

  void _sayOpening() {
    final opening = _openings.isEven
        ? FixedPhrase.thinkingLookup
        : FixedPhrase.thinkingGoodQuestion;
    _openings++;
    _say(opening);
  }

  /// 輪詢答案：出現一段就下載一段、排進播放；等不到時補短句；結束時整理畫面。
  Future<void> _follow(int generation, String id) async {
    final asked = _now;
    final timeout = ref.read(qaTimeoutProvider);
    final slowAfter = ref.read(qaSlowAfterProvider);
    final queued = <int>{};
    var failures = 0;
    var saidSlow = false;
    var saidWeb = false;

    while (true) {
      final AnswerPoll poll;
      try {
        poll = await ref
            .read(qaApiProvider)
            .answer(ref.read(settingsProvider), id);
      } on TourApiException catch (error) {
        if (generation != _generation) return;
        failures++;
        // 404＝主機已經沒有這題（例如重啟過），重試沒有用；其他失敗跟旅程輪詢一樣多試幾次
        if (_isGone(error) || failures >= _maxPollFailures) {
          _hostFailed(generation, error, '等不到答案');
          return;
        }
        await _pause();
        if (generation != _generation) return;
        continue;
      }
      if (generation != _generation) return;
      failures = 0;
      ref.read(tourProvider.notifier).noteHostReached();

      for (final segment in poll.segments) {
        if (queued.add(segment.index)) {
          _queueSegment(generation, id, segment.index);
          state = state.copyWith(phase: QaPhase.answering);
        }
      }
      if (poll.searchingWeb && !state.searchingWeb) {
        state = state.copyWith(searchingWeb: true);
      }
      final silent = queued.isEmpty; // 還沒有任何答案的語音，才需要用短句填空檔
      if (silent && poll.searchingWeb && !saidWeb) {
        saidWeb = true;
        _say(FixedPhrase.thinkingWeb);
      }
      if (silent &&
          !saidWeb &&
          !saidSlow &&
          _now.difference(asked) >= slowAfter) {
        saidSlow = true;
        _say(FixedPhrase.thinkingHowToPutIt);
      }

      if (poll.status != AnswerStatus.answering) {
        await _audio;
        _conclude(generation, poll);
        return;
      }
      if (_now.difference(asked) > timeout) {
        await _audio;
        _fail(generation, '答案等太久了，先不等了');
        return;
      }
      await _pause();
      if (generation != _generation) return;
    }
  }

  void _queueSegment(int generation, String id, int index) {
    final download = _download(generation, id, index); // 先開始下載，輪到它播時多半已經好了
    _enqueue(generation, () async {
      final bytes = await download;
      if (bytes == null || generation != _generation) return;
      await ref
          .read(answerPlayerProvider)
          // 各段之間不釋放：其他 App 的音量先壓著，整個答案播完才恢復
          .play(bytes, title: '回答', releaseFocus: false);
    });
  }

  /// 失敗回傳 null（這一段就跳過）。404＝主機已經沒有這段；其他失敗算一次斷線。
  Future<Uint8List?> _download(int generation, String id, int index) async {
    try {
      return await ref
          .read(qaApiProvider)
          .downloadSegment(ref.read(settingsProvider), id, index);
    } on TourApiException catch (error) {
      debugPrint('下載答案第 $index 段失敗：$error');
      if (!_isGone(error) && generation == _generation) {
        ref.read(tourProvider.notifier).noteHostFailed();
      }
      return null;
    }
  }

  void _conclude(int generation, AnswerPoll poll) {
    if (generation != _generation) return;
    final reason = poll.reason;
    final failed = poll.status == AnswerStatus.failed;
    _finish(
      generation,
      error: failed && reason != 'quota' ? _failureText(reason) : null,
      quotaExhausted: failed && reason == 'quota',
    );
  }

  static String _failureText(String? reason) => switch (reason) {
    'llm_budget' => '主機的 Claude 呼叫上限用完了，這題沒辦法回答',
    'forbidden_model' => '主機拒絕使用不允許的模型，這題沒辦法回答',
    'no_audio' => '這題的答案沒能合成語音，再問一次看看',
    _ => '這題沒能回答，再問一次看看',
  };

  /// 主機有回應、只是沒有這一段／這一題（例如重啟過）：不算斷線。其他失敗的判斷與旅程輪詢一致。
  static bool _isGone(TourApiException error) => error.statusCode == 404;

  void _hostFailed(int generation, TourApiException error, String what) {
    if (generation != _generation) return;
    if (_isGone(error)) {
      _fail(generation, '$what：主機已經沒有這一題');
      return;
    }
    // 和輪詢失敗一樣算一次斷線（只念一次「連不上」，並退避重試）
    ref.read(tourProvider.notifier).noteHostFailed();
    final code = error.statusCode;
    _fail(generation, code == null ? '$what：連不上主機' : '$what：主機回應 $code');
  }

  void _fail(int generation, String message) =>
      _finish(generation, error: message);

  void _finish(int generation, {String? error, bool quotaExhausted = false}) {
    if (generation != _generation) return;
    unawaited(ref.read(answerPlayerProvider).release());
    _unhold();
    _session = null;
    state = QaState(
      error: error,
      quotaExhausted: quotaExhausted,
      mode: state.mode,
    );
  }

  // 短句不釋放 focus：後面緊接著是答案，整個答案播完才由答案播放器一次恢復其他 App 的音量
  void _say(FixedPhrase phrase) => _enqueue(
    _generation,
    () => ref.read(phrasePlayerProvider).play(phrase, releaseFocus: false),
  );

  void _enqueue(int generation, Future<void> Function() task) {
    _audio = _audio.then((_) async {
      if (generation != _generation) return;
      try {
        await task();
      } catch (error) {
        // 連 Error 也要接住：否則這一列會永遠是失敗狀態，之後每個答案都沒聲音
        debugPrint('播放答案時出錯：$error');
      }
    });
  }

  Future<void> _pause() =>
      Future<void>.delayed(ref.read(qaPollIntervalProvider));

  void _hold() {
    if (_holding) return;
    _holding = true;
    ref.read(tourProvider.notifier).beginQuestion();
  }

  void _unhold() {
    if (!_holding) return;
    _holding = false;
    ref.read(tourProvider.notifier).endQuestion();
  }
}
