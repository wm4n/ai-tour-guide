import 'dart:async';
import 'dart:typed_data';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/narration_player.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/audio/remote_controls.dart';
import 'package:buddy_tour/tour/location_permission.dart';
import 'package:buddy_tour/tour/location_source.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/tour_api.dart';
import 'package:buddy_tour/tour/traveler_state.dart';

// 地點 A 在 25.0560, 121.5100；往北每 0.0001 度約 11 公尺。
const placeLat = 25.0560;
const placeLon = 121.5100;
RawFix farFix([double meters = 330]) =>
    RawFix(placeLat - meters / 111195, placeLon);
RawFix nearFix() => farFix(50);

class FakeTourApi implements TourApi {
  final calls = <String>[];
  final started = <(PositionFix, TravelerState)>[];
  final reported = <(PositionFix, TravelerState)>[];
  final polls = <int>[];
  final downloads = <String>[];
  final played = <String>[];
  Object? playedError;
  var polled = <NarrationPoll>[];
  Object? startError;
  Object? pollError;
  Object? reportError;
  Object? endError;
  TourSummary? summary;
  Object? downloadError;
  Completer<void>? downloadGate;
  Completer<void>? pollGate;

  void queue(List<NarrationInfo> narrations, {String? stoppedReason}) {
    polled.add(
      NarrationPoll(
        active: true,
        preparing: false,
        stoppedReason: stoppedReason,
        narrations: narrations,
      ),
    );
  }

  void queueInactive() {
    polled.add(
      const NarrationPoll(
        active: false,
        preparing: false,
        stoppedReason: null,
        narrations: [],
      ),
    );
  }

  @override
  Future<void> start(s, PositionFix fix, TravelerState traveler) async {
    calls.add('start');
    if (startError != null) throw startError!;
    started.add((fix, traveler));
  }

  @override
  Future<void> reportLocation(
    s,
    PositionFix fix,
    TravelerState traveler,
  ) async {
    calls.add('location');
    if (reportError != null) throw reportError!;
    reported.add((fix, traveler));
  }

  @override
  Future<TourSummary?> end(s) async {
    calls.add('end');
    if (endError != null) throw endError!;
    return summary;
  }

  @override
  Future<void> markPlayed(s, String id) async {
    calls.add('played');
    if (playedError != null) throw playedError!;
    played.add(id);
  }

  @override
  Future<NarrationPoll> poll(s, {required int after}) async {
    polls.add(after);
    await pollGate?.future;
    if (pollError != null) throw pollError!;
    if (polled.isEmpty) {
      return const NarrationPoll(
        active: true,
        preparing: false,
        stoppedReason: null,
        narrations: [],
      );
    }
    return polled.removeAt(0);
  }

  @override
  Future<Uint8List> downloadAudio(s, String id) async {
    downloads.add(id);
    await downloadGate?.future;
    if (downloadError != null) throw downloadError!;
    return Uint8List.fromList(id.codeUnits);
  }
}

class FakeLocation implements LocationSource {
  final controller = StreamController<RawFix>.broadcast();
  RawFix first = farFix();
  bool granted = true;

  @override
  LocationAccess access = LocationAccess.always;

  @override
  Future<bool> ensurePermission() async => granted;

  @override
  Future<RawFix?> current() async => first;

  @override
  Stream<RawFix> positions() => controller.stream;
}

class FakePlayer implements NarrationPlayer {
  final played = <String>[];
  final events = <String>[];

  /// 每次 play 從哪裡開始。
  final starts = <Duration>[];

  /// `position` 回傳這個值，測試用來安排「播到哪裡被打斷」。
  Duration positionNow = Duration.zero;
  Completer<bool>? _current;

  @override
  Duration get position => positionNow;

  @override
  Future<bool> play(
    Uint8List wav, {
    required String title,
    Duration start = Duration.zero,
    bool releaseFocus = true,
  }) {
    played.add(String.fromCharCodes(wav));
    events.add('play:$title');
    starts.add(start);
    focusReleasedAfter.add(releaseFocus);
    _current = Completer<bool>();
    return _current!.future;
  }

  /// 每次 play 是否要求播完就釋放 audio focus。
  final focusReleasedAfter = <bool>[];

  @override
  Future<void> release() async => events.add('release');

  /// 自然播完。
  void finish() {
    if (_current?.isCompleted == false) _current!.complete(true);
  }

  @override
  Future<void> pause() async => events.add('pause');

  @override
  Future<void> resume() async => events.add('resume');

  @override
  Future<void> stop({bool releaseFocus = true}) async {
    events.add(releaseFocus ? 'stop' : 'stop(keep focus)');
    if (_current?.isCompleted == false) _current!.complete(false);
  }

  @override
  Future<void> dispose() async {}
}

class FakeRemote implements RemoteControls {
  final controller = StreamController<RemoteCommand>.broadcast();
  final updates = <({bool paused, String? title})>[];

  @override
  Stream<RemoteCommand> get commands => controller.stream;

  @override
  void update({
    required bool tourActive,
    required bool paused,
    String? title,
  }) => updates.add((paused: paused, title: title));

  @override
  Future<void> dispose() async {}
}

class FakePhrases implements PhrasePlayer {
  final played = <FixedPhrase>[];

  /// 每次 play 是否要求念完就釋放 audio focus。
  final focusReleasedAfter = <bool>[];
  var stops = 0;
  Object? errorOnce; // 下一次 play 丟這個（Error 或 Exception 都可以）

  @override
  Future<void> play(FixedPhrase phrase, {bool releaseFocus = true}) async {
    final error = errorOnce;
    if (error != null) {
      errorOnce = null;
      throw error;
    }
    played.add(phrase);
    focusReleasedAfter.add(releaseFocus);
  }

  @override
  Future<void> stop() async => stops++;

  @override
  Future<void> dispose() async {}
}

class FakeTourApiFailingDownload extends FakeTourApi {
  @override
  Future<Uint8List> downloadAudio(s, String id) async =>
      throw TourApiException('gone');
}
