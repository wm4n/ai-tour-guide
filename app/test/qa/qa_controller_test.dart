import 'dart:async';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/audio/phrase_player.dart';
import 'package:buddy_tour/host/host_connection.dart';
import 'package:buddy_tour/qa/qa_api.dart';
import 'package:buddy_tour/qa/photo_source.dart';
import 'package:buddy_tour/qa/qa_controller.dart';
import 'package:buddy_tour/qa/speech_recognizer.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/tour_api.dart';
import 'package:buddy_tour/tour/tour_controller.dart';
import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../tour/fakes.dart';
import 'fakes.dart';

class QaHarness {
  QaHarness(this.recognizer);

  final FakeRecognizer recognizer;
  final tourApi = FakeTourApi();
  final qaApi = FakeQaApi();
  final photoSource = FakePhotoSource();
  final compass = FakeCompass();
  final location = FakeLocation();
  final narrationPlayer = FakePlayer();
  final answerPlayer = FakePlayer();
  final remote = FakeRemote();
  final phrases = FakePhrases();
  var now = DateTime(2026, 10, 20, 15, 0);
  late ProviderContainer container;

  QaController get qa => container.read(qaProvider.notifier);
  QaState get state => container.read(qaProvider);
  TourController get tour => container.read(tourProvider.notifier);

  Future<void> settle() => pumpEventQueue();

  /// 按住、說完、放開，並讓事件處理到沒有事可做為止。
  Future<void> ask() async {
    await qa.press();
    await qa.release();
    await settle();
  }

  /// 答案播放器把目前這一段播完，並讓下一段開始。
  Future<void> finishSegment() async {
    answerPlayer.finish();
    await settle();
  }

  List<FixedPhrase> get thinking => [
    for (final p in phrases.played)
      if (p != FixedPhrase.startTour && p != FixedPhrase.hostUnreachable) p,
  ];
}

Future<QaHarness> makeQaHarness({
  bool startTour = true,
  FakeRecognizer? recognizer,
  Duration slowAfter = const Duration(seconds: 8),
  Duration timeout = const Duration(minutes: 2),
}) async {
  SharedPreferences.setMockInitialValues({'host.url': 'http://h:1'});
  final prefs = await SharedPreferences.getInstance();
  final h = QaHarness(recognizer ?? FakeRecognizer());
  h.container = ProviderContainer(
    overrides: [
      sharedPreferencesProvider.overrideWithValue(prefs),
      tourApiProvider.overrideWithValue(h.tourApi),
      locationSourceProvider.overrideWithValue(h.location),
      narrationPlayerProvider.overrideWithValue(h.narrationPlayer),
      remoteControlsProvider.overrideWithValue(h.remote),
      phrasePlayerProvider.overrideWithValue(h.phrases),
      clockProvider.overrideWithValue(() => h.now),
      tourTickIntervalProvider.overrideWithValue(const Duration(hours: 1)),
      qaApiProvider.overrideWithValue(h.qaApi),
      photoSourceProvider.overrideWithValue(h.photoSource),
      compassSourceProvider.overrideWithValue(h.compass),
      speechRecognizerProvider.overrideWithValue(h.recognizer),
      answerPlayerProvider.overrideWithValue(h.answerPlayer),
      qaPollIntervalProvider.overrideWithValue(Duration.zero),
      qaSlowAfterProvider.overrideWithValue(slowAfter),
      qaTimeoutProvider.overrideWithValue(timeout),
    ],
  );
  addTearDown(h.container.dispose);
  h.container.read(tourProvider);
  h.container.read(qaProvider);
  if (startTour) {
    await h.tour.start();
    h.phrases.played.clear(); // 出發的招呼不是這裡要看的
    h.phrases.focusReleasedAfter.clear();
  }
  return h;
}

NarrationInfo info(String id, {int seq = 1}) => NarrationInfo(
  seq: seq,
  id: id,
  name: '景點$id',
  lat: placeLat,
  lon: placeLon,
  audioSeconds: 30,
);

void main() {
  group('pressing and releasing', () {
    test('listening starts on press', () async {
      final h = await makeQaHarness();

      await h.qa.press();

      expect(h.state.phase, QaPhase.listening);
      expect(h.recognizer.attempts, [true]); // 先試本機
      expect(h.state.mode, RecognitionMode.onDevice);
    });

    test(
      'releasing sends the recognized words with position and traveler',
      () async {
        final h = await makeQaHarness();
        h.recognizer.heard = '那間廟拜的是誰';
        await h.container
            .read(travelerProvider.notifier)
            .save(const TravelerState(companions: Companions.couple));
        h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

        await h.ask();

        final asked = h.qaApi.asked.single;
        expect(asked.question, '那間廟拜的是誰');
        expect(asked.more, isFalse);
        expect(asked.traveler.companions, Companions.couple);
        expect(asked.fix.lat, closeTo(farFix().lat, 1e-9));
      },
    );

    test('the words themselves are trimmed', () async {
      final h = await makeQaHarness();
      h.recognizer.heard = '  這是什麼  ';
      h.qaApi.answers = [poll(status: AnswerStatus.done)];

      await h.ask();

      expect(h.qaApi.asked.single.question, '這是什麼');
    });

    test(
      'says the thinking phrase as soon as the question is understood',
      () async {
        final h = await makeQaHarness();
        h.qaApi.askGate = Completer<void>(); // 主機還沒回應，短句也要先念

        await h.qa.press();
        await h.qa.release();
        await h.settle();

        expect(h.thinking, [FixedPhrase.thinkingLookup]);
        expect(h.state.phase, QaPhase.asking);
        h.qaApi.askGate!.complete();
        await h.settle();
      },
    );

    test('alternates between the two opening phrases', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.failed, reason: 'error')];

      await h.ask();
      await h.ask();
      await h.ask();

      expect(h.thinking, [
        FixedPhrase.thinkingLookup,
        FixedPhrase.thinkingGoodQuestion,
        FixedPhrase.thinkingLookup,
      ]);
    });

    test('releasing before the microphone is ready still asks', () async {
      final h = await makeQaHarness();
      h.recognizer.gate = Completer<void>();
      h.qaApi.answers = [poll(status: AnswerStatus.done)];

      final pressing = h.qa.press();
      await h.qa.release(); // 還沒開始聽就放開了
      h.recognizer.gate!.complete();
      await pressing;
      await h.settle();

      expect(h.qaApi.asked, hasLength(1));
    });

    test('an empty recognition asks nothing and says so', () async {
      final h = await makeQaHarness();
      h.recognizer.heard = '   ';

      await h.ask();

      expect(h.qaApi.asked, isEmpty);
      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, contains('沒聽清楚'));
    });

    test('pressing again while a question is in progress is ignored', () async {
      final h = await makeQaHarness();

      await h.qa.press();
      await h.qa.press();

      expect(h.recognizer.attempts, hasLength(1));
    });

    test('asking is only possible during a tour', () async {
      final h = await makeQaHarness(startTour: false);

      await h.qa.press();

      expect(h.recognizer.attempts, isEmpty);
      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, isNotNull);
    });

    test('a new question clears the previous notice', () async {
      final h = await makeQaHarness();
      h.recognizer.heard = '';
      await h.ask();
      expect(h.state.error, isNotNull);

      h.recognizer.heard = '這是什麼';
      await h.qa.press();

      expect(h.state.error, isNull);
    });

    test('"tell me more" is sent as a follow-up', () async {
      final h = await makeQaHarness();
      h.recognizer.heard = '剛剛那個，再多說一點';
      h.qaApi.answers = [poll(status: AnswerStatus.done)];

      await h.ask();

      expect(h.qaApi.asked.single.more, isTrue);
    });
  });

  group('recognition method', () {
    test(
      'goes online when this device cannot recognize zh-TW locally',
      () async {
        final h = await makeQaHarness(
          recognizer: FakeRecognizer(onDeviceSupported: false),
        );
        h.qaApi.answers = [poll(status: AnswerStatus.done)];

        await h.ask();

        expect(h.recognizer.attempts, [true, false]);
        expect(h.state.mode, RecognitionMode.online);
        expect(h.qaApi.asked, hasLength(1)); // 兩條路都問得出去
      },
    );

    test('a refused permission is explained and nothing is asked', () async {
      final h = await makeQaHarness(
        recognizer: FakeRecognizer(error: SpeechPermissionDenied()),
      );

      await h.qa.press();

      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, contains('權限'));
    });

    test('any other recognizer failure is shown, not thrown', () async {
      final h = await makeQaHarness(
        recognizer: FakeRecognizer(error: RecognitionFailed('壞了')),
      );

      await h.qa.press();

      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, isNotNull);
    });
  });

  group('playing the answer', () {
    test('segments are downloaded and played in order', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [
        poll(segments: 1),
        poll(status: AnswerStatus.done, segments: 2),
      ];

      await h.ask();
      expect(h.answerPlayer.played, ['a1:0']);
      await h.finishSegment();
      expect(h.answerPlayer.played, ['a1:0', 'a1:1']);
      await h.finishSegment();

      expect(h.qaApi.downloads, [('a1', 0), ('a1', 1)]);
      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, isNull);
    });

    test(
      'other apps stay ducked between segments and recover at the end',
      () async {
        final h = await makeQaHarness();
        h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 2)];

        await h.ask();
        await h.finishSegment();
        await h.finishSegment();

        expect(h.answerPlayer.focusReleasedAfter, [false, false]);
        expect(h.answerPlayer.events.last, 'release');
      },
    );

    test('the audio focus is released even when the answer fails', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.failed, reason: 'error')];

      await h.ask();

      expect(h.answerPlayer.events, contains('release'));
    });

    test('while answering the state says so', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

      await h.ask();

      expect(h.state.phase, QaPhase.answering); // 第一段還在播
      await h.finishSegment();
      expect(h.state.phase, QaPhase.idle);
    });

    test(
      'a segment that cannot be downloaded is skipped, the rest still play',
      () async {
        final h = await makeQaHarness();
        h.qaApi.failingSegments = {0};
        h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 2)];

        await h.ask();
        await h.finishSegment();

        expect(h.answerPlayer.played, ['a1:1']);
        expect(h.state.phase, QaPhase.idle);
      },
    );
  });

  group('filling the wait', () {
    test('a slow answer gets the second thinking phrase, once', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll()]; // 一直還沒有任何一段

      await h.ask();
      expect(h.thinking, [FixedPhrase.thinkingLookup]);

      h.now = h.now.add(const Duration(seconds: 9));
      await h.settle();
      await h.settle();

      expect(h.thinking, [
        FixedPhrase.thinkingLookup,
        FixedPhrase.thinkingHowToPutIt,
      ]);
      h.now = h.now.add(const Duration(seconds: 20));
      await h.settle();
      expect(h.thinking, hasLength(2)); // 不重複念
      h.qa.cancel();
    });

    test('a fast answer never gets the filler', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

      await h.ask();
      h.now = h.now.add(const Duration(seconds: 30));
      await h.finishSegment();

      expect(h.thinking, [FixedPhrase.thinkingLookup]);
    });

    test('searching the web says so once', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(searching: true)];

      await h.ask();
      await h.settle();

      expect(h.thinking, [FixedPhrase.thinkingLookup, FixedPhrase.thinkingWeb]);
      expect(h.state.searchingWeb, isTrue);
      h.qa.cancel();
    });

    test('no web phrase once the answer is already being spoken', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [
        poll(segments: 1),
        poll(segments: 1, searching: true, status: AnswerStatus.done),
      ];

      await h.ask();

      expect(h.thinking, [FixedPhrase.thinkingLookup]);
    });
  });

  group('when the answer cannot be given', () {
    test('quota exhausted is shown on screen and never spoken', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.failed, reason: 'quota')];

      await h.ask();

      expect(h.state.quotaExhausted, isTrue);
      expect(h.state.phase, QaPhase.idle);
      expect(h.thinking, [FixedPhrase.thinkingLookup]); // 只有一開始的短句
      expect(h.answerPlayer.played, isEmpty);
    });

    test('the next question clears the quota notice', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.failed, reason: 'quota')];
      await h.ask();

      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];
      await h.qa.press();

      expect(h.state.quotaExhausted, isFalse);
    });

    test('other failures are explained on screen', () async {
      final h = await makeQaHarness();
      for (final reason in [
        'llm_budget',
        'forbidden_model',
        'no_audio',
        'error',
      ]) {
        h.qaApi.answers = [poll(status: AnswerStatus.failed, reason: reason)];

        await h.ask();

        expect(h.state.error, isNotNull, reason: reason);
        expect(h.state.quotaExhausted, isFalse, reason: reason);
        expect(h.state.phase, QaPhase.idle, reason: reason);
      }
    });

    test('a failed answer still plays what was already made', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [
        poll(status: AnswerStatus.failed, segments: 1, reason: 'error'),
      ];

      await h.ask();
      expect(h.answerPlayer.played, ['a1:0']);
      await h.finishSegment();

      expect(h.state.error, isNotNull);
      expect(h.state.phase, QaPhase.idle);
    });

    test('an answer that never finishes is given up on', () async {
      final h = await makeQaHarness(timeout: const Duration(minutes: 1));
      h.qaApi.answers = [poll()];

      await h.ask();
      h.now = h.now.add(const Duration(minutes: 2));
      await h.settle();

      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, contains('太久'));
    });
  });

  group('host trouble', () {
    test(
      'an unreachable host when asking is an outage: said once, quietly retried',
      () async {
        final h = await makeQaHarness();
        h.qaApi.askError = TourApiException('down');

        await h.ask();

        expect(h.state.phase, QaPhase.idle);
        expect(h.state.error, contains('主機'));
        await h.tour.tick();
        await h.settle();
        expect(
          h.phrases.played.where((p) => p == FixedPhrase.hostUnreachable),
          hasLength(1),
        );
      },
    );

    test(
      'a host that answers with an error status is an outage, like polling',
      () async {
        final h = await makeQaHarness();
        h.qaApi.askError = TourApiException('no', statusCode: 503);

        await h.ask();
        await h.tour.tick();

        expect(h.state.error, contains('503'));
        expect(h.phrases.played, contains(FixedPhrase.hostUnreachable));
      },
    );

    test('a host that no longer knows the question is not an outage', () async {
      final h = await makeQaHarness();
      h.qaApi.askError = TourApiException('gone', statusCode: 404);

      await h.ask();
      await h.tour.tick();

      expect(h.state.error, isNotNull);
      expect(h.phrases.played, isNot(contains(FixedPhrase.hostUnreachable)));
    });

    test(
      'losing the host while waiting for the answer gives up after a few tries',
      () async {
        final h = await makeQaHarness();
        h.qaApi.answerError = TourApiException('down');

        await h.ask();

        expect(h.state.phase, QaPhase.idle);
        expect(h.state.error, isNotNull);
        expect(h.qaApi.answerPolls.length, 3);
      },
    );

    test('a hiccup while polling is ridden out', () async {
      final h = await makeQaHarness();
      h.qaApi.answerError = TourApiException('down');
      h.qaApi.answerFailures = 2;
      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

      await h.ask();
      await h.finishSegment();

      expect(h.state.error, isNull);
      expect(h.answerPlayer.played, ['a1:0']);
    });

    test(
      'the host forgetting the answer (restart) is an error, not a retry loop',
      () async {
        final h = await makeQaHarness();
        h.qaApi.answerError = TourApiException('gone', statusCode: 404);

        await h.ask();

        expect(h.qaApi.answerPolls, hasLength(1));
        expect(h.state.error, isNotNull);
      },
    );
  });

  group('with the tour', () {
    test('a narration that is ready waits until the answer is done', () async {
      final h = await makeQaHarness();
      h.tourApi.queue([info('A')]);
      h.location.controller.add(nearFix());
      await h.settle();
      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

      await h.ask();
      await h.tour.tick();
      expect(h.narrationPlayer.played, isEmpty);

      await h.finishSegment();
      await h.tour.tick();
      expect(h.narrationPlayer.played, ['A']);
    });

    test(
      'the hold starts at press, so nothing new starts while listening',
      () async {
        final h = await makeQaHarness();
        h.tourApi.queue([info('A')]);
        h.location.controller.add(nearFix());
        await h.settle();

        await h.qa.press();
        await h.tour.tick();

        expect(h.narrationPlayer.played, isEmpty);
        await h.qa.cancel();
      },
    );

    test('ending the tour cancels the question in progress', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(segments: 1)];
      await h.ask();
      expect(h.answerPlayer.played, ['a1:0']);

      await h.tour.end();
      await h.settle();

      expect(h.state.phase, QaPhase.idle);
      expect(h.answerPlayer.events, contains('stop'));
      final polls = h.qaApi.answerPolls.length;
      await h.settle();
      expect(h.qaApi.answerPolls.length, polls); // 不再輪詢
    });

    test('cancelling while listening throws the recording away', () async {
      final h = await makeQaHarness();
      await h.qa.press();

      await h.qa.cancel();

      expect(h.recognizer.sessions.single.cancelled, isTrue);
      expect(h.state.phase, QaPhase.idle);
      expect(h.qaApi.asked, isEmpty);
    });

    test('after a cancelled question the next one works normally', () async {
      final h = await makeQaHarness();
      await h.qa.press();
      await h.qa.cancel();
      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

      await h.ask();

      expect(h.qaApi.asked, hasLength(1));
    });
  });

  group('cancelling and recovering', () {
    test('cancelling mid-answer gives other apps their volume back', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(segments: 1)];
      await h.ask();
      expect(h.answerPlayer.played, ['a1:0']);

      await h.tour.end();
      await h.settle();

      final events = h.answerPlayer.events;
      expect(events, contains('stop'));
      expect(events.indexOf('release'), greaterThan(events.indexOf('stop')));
    });

    test('cancelling stops a phrase that is still being said', () async {
      final h = await makeQaHarness();
      await h.qa.press();
      await h.qa.cancel();

      expect(h.phrases.stops, 1);
    });

    test('the opening phrase leaves the volume down for the answer', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

      await h.ask();
      await h.finishSegment();

      // 短句與答案各段都不釋放；整個答案播完才由答案播放器釋放一次
      expect(h.phrases.focusReleasedAfter, [false]);
      expect(h.answerPlayer.events.where((e) => e == 'release'), hasLength(1));
    });

    test(
      'pressing again right after cancelling does not kill the new recording',
      () async {
        final h = await makeQaHarness();
        h.recognizer.gate = Completer<void>();

        final first = h.qa.press(); // 麥克風還沒開好
        await h.qa.cancel();
        final second = h.qa.press();
        h.recognizer.gate!.complete();
        await first;
        await second;
        await h.settle();

        expect(h.state.phase, QaPhase.listening);
        expect(h.recognizer.sessions.last.cancelled, isFalse);
        // 舊的那次先收乾淨，新的才開始聽
        expect(h.recognizer.log, ['listen', 'cancel', 'listen']);
      },
    );

    test(
      'one unexpected error in the audio queue does not silence later answers',
      () async {
        final h = await makeQaHarness();
        h.phrases.errorOnce = StateError('壞掉的一次');
        h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];
        await h.ask();
        await h.finishSegment();

        await h.ask();

        expect(h.answerPlayer.played, ['a1:0', 'a2:0']);
      },
    );
  });

  group('asking with a photo', () {
    Future<void> shoot(QaHarness h) async {
      await h.qa.askWithPhoto();
      await h.settle();
    }

    test(
      'takes a photo, reads the compass and sends both with the position',
      () async {
        final h = await makeQaHarness();
        h.compass.heading = 270;
        h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

        await shoot(h);

        final asked = h.qaApi.askedPhotos.single;
        expect(asked.question, '這是什麼？');
        expect(asked.compassHeading, 270);
        expect(asked.image, h.photoSource.photo);
        expect(asked.fix.lat, closeTo(farFix().lat, 1e-9));
      },
    );

    test(
      'says the thinking phrase once the photo is taken, then plays the answer',
      () async {
        final h = await makeQaHarness();
        h.qaApi.answers = [poll(status: AnswerStatus.done, segments: 1)];

        await shoot(h);

        expect(h.thinking, [FixedPhrase.thinkingLookup]);
        expect(h.answerPlayer.played, ['p1:0']);
      },
    );

    test(
      'holds the tour back (and interrupts the narration) while the camera is open',
      () async {
        final h = await makeQaHarness();
        h.photoSource.gate = Completer<void>();
        h.tourApi.queue([info('A')]);
        h.location.controller.add(nearFix());
        await h.settle();

        final shooting = h.qa.askWithPhoto();
        await h.settle();
        await h.tour.tick();
        expect(h.state.phase, QaPhase.photographing);
        expect(h.narrationPlayer.played, isEmpty);

        h.photoSource.gate!.complete();
        await shooting;
      },
    );

    test(
      'a cancelled camera ends quietly and lets the tour carry on',
      () async {
        final h = await makeQaHarness();
        h.photoSource.photo = null; // 使用者按了取消
        h.tourApi.queue([info('A')]);
        h.location.controller.add(nearFix());
        await h.settle();

        await shoot(h);
        await h.tour.tick();
        await h.settle();

        expect(h.state.phase, QaPhase.idle);
        expect(h.state.error, isNull);
        expect(h.qaApi.askedPhotos, isEmpty);
        expect(h.thinking, isEmpty);
        expect(h.narrationPlayer.played, ['A']); // 暫停的介紹繼續
      },
    );

    test('a camera that cannot be opened is explained', () async {
      final h = await makeQaHarness();
      h.photoSource.error = PhotoUnavailable('需要相機權限');

      await shoot(h);

      expect(h.state.phase, QaPhase.idle);
      expect(h.state.error, contains('相機'));
    });

    test(
      'an unreadable compass still asks, without pretending to know the direction',
      () async {
        final h = await makeQaHarness();
        h.compass.heading = null;
        h.qaApi.answers = [poll(status: AnswerStatus.done)];

        await shoot(h);

        expect(h.qaApi.askedPhotos.single.compassHeading, isNull);
      },
    );

    test('is only possible during a tour', () async {
      final h = await makeQaHarness(startTour: false);

      await shoot(h);

      expect(h.photoSource.taken, 0);
      expect(h.state.error, isNotNull);
    });

    test('ignored while another question is in progress', () async {
      final h = await makeQaHarness();
      await h.qa.press();

      await shoot(h);

      expect(h.photoSource.taken, 0);
    });

    test(
      'a host that is unreachable counts as an outage, like any question',
      () async {
        final h = await makeQaHarness();
        h.qaApi.askError = TourApiException('down');

        await shoot(h);
        await h.tour.tick();

        expect(h.state.error, contains('主機'));
        expect(h.phrases.played, contains(FixedPhrase.hostUnreachable));
      },
    );

    test('quota exhausted is shown, never spoken', () async {
      final h = await makeQaHarness();
      h.qaApi.answers = [poll(status: AnswerStatus.failed, reason: 'quota')];

      await shoot(h);

      expect(h.state.quotaExhausted, isTrue);
      expect(h.answerPlayer.played, isEmpty);
    });

    test('a photo too big for the host is explained', () async {
      final h = await makeQaHarness();
      h.qaApi.askError = TourApiException('big', statusCode: 413);

      await shoot(h);

      expect(h.state.error, contains('413'));
    });

    test('ending the tour while the camera is open drops the photo', () async {
      final h = await makeQaHarness();
      h.photoSource.gate = Completer<void>();

      final shooting = h.qa.askWithPhoto();
      await h.settle();
      await h.tour.end();
      h.photoSource.gate!.complete();
      await shooting;
      await h.settle();

      expect(h.qaApi.askedPhotos, isEmpty);
      expect(h.state.phase, QaPhase.idle);
    });
  });
}
