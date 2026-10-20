import 'dart:async';
import 'dart:typed_data';

import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/tour/tour_api.dart' show TourApiException;
import 'package:buddy_tour/qa/qa_api.dart';
import 'package:buddy_tour/qa/speech_recognizer.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/traveler_state.dart';

class FakeSession implements RecognitionSession {
  FakeSession(this.text, [this.log]);

  final String text;
  final List<String>? log;
  bool finished = false;
  bool cancelled = false;

  @override
  Future<String> finish() async {
    finished = true;
    return text;
  }

  @override
  Future<void> cancel() async {
    cancelled = true;
    log?.add('cancel');
  }
}

/// 假的辨識引擎：`heard` 是它「聽到」的字；本機不支援時照規定丟 [OnDeviceUnavailable]。
class FakeRecognizer implements SpeechRecognizer {
  FakeRecognizer({
    this.heard = '那間廟拜的是誰',
    this.onDeviceSupported = true,
    this.error,
  });

  String heard;
  final bool onDeviceSupported;
  Object? error;
  Completer<void>? gate; // 讓測試卡住「麥克風還沒開好」
  final attempts = <bool>[];
  final sessions = <FakeSession>[];
  final log = <String>[]; // listen／cancel 發生的順序

  @override
  Future<RecognitionSession> listen({required bool onDevice}) async {
    attempts.add(onDevice);
    log.add('listen');
    final wait = gate;
    await wait?.future;
    if (error != null) throw error!;
    if (onDevice && !onDeviceSupported) throw OnDeviceUnavailable();
    final session = FakeSession(heard, log);
    sessions.add(session);
    return session;
  }
}

typedef AskedQuestion = ({
  String question,
  bool more,
  PositionFix fix,
  TravelerState traveler,
});

class FakeQaApi implements QaApi {
  final asked = <AskedQuestion>[];
  Object? askError;
  Completer<void>? askGate;
  var answers = <AnswerPoll>[poll()]; // 依序回傳；剩最後一個時一直回它
  Object? answerError; // 輪詢時丟這個例外
  int? answerFailures; // 只失敗前幾次（之後正常）；null＝一直失敗
  final answerPolls = <String>[];
  final downloads = <(String, int)>[];
  Object? downloadError;
  var failingSegments = <int>{}; // 這幾段下載時回 404
  Completer<void>? downloadGate;

  @override
  Future<String> ask(
    HostSettings settings,
    String question,
    PositionFix fix,
    TravelerState traveler, {
    bool more = false,
  }) async {
    await askGate?.future;
    if (askError != null) throw askError!;
    asked.add((question: question, more: more, fix: fix, traveler: traveler));
    return 'a${asked.length}';
  }

  @override
  Future<AnswerPoll> answer(HostSettings settings, String id) async {
    answerPolls.add(id);
    if (answerError != null &&
        (answerFailures == null || answerFailures! > 0)) {
      if (answerFailures != null) answerFailures = answerFailures! - 1;
      throw answerError!;
    }
    return answers.length > 1 ? answers.removeAt(0) : answers.first;
  }

  @override
  Future<Uint8List> downloadSegment(
    HostSettings settings,
    String id,
    int index,
  ) async {
    downloads.add((id, index));
    await downloadGate?.future;
    if (downloadError != null) throw downloadError!;
    if (failingSegments.contains(index)) {
      throw TourApiException('gone', statusCode: 404);
    }
    return Uint8List.fromList('$id:$index'.codeUnits);
  }
}

AnswerPoll poll({
  AnswerStatus status = AnswerStatus.answering,
  int segments = 0,
  bool searching = false,
  String? reason,
}) => AnswerPoll(
  status: status,
  segments: [
    for (var i = 0; i < segments; i++)
      AnswerSegmentInfo(index: i, audioSeconds: 2.0),
  ],
  searchingWeb: searching,
  reason: reason,
);
