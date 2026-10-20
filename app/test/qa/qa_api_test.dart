import 'dart:convert';
import 'dart:typed_data';

import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/qa/qa_api.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/tour_api.dart';
import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const settings = HostSettings(url: 'http://100.64.0.1:8765', token: 's3cret');
final fix = PositionFix(
  lat: 25.056,
  lon: 121.51,
  heading: 200,
  time: DateTime.parse('2026-10-20T15:04:09+08:00'),
);
const traveler = TravelerState(
  mode: TravelMode.walking,
  companions: Companions.couple,
);

HttpQaApi apiWith(Future<http.Response> Function(http.Request) handler) =>
    HttpQaApi(MockClient(handler), offset: const Duration(hours: 8));

http.Response answerResponse({
  String status = 'answering',
  List<Map<String, Object>> segments = const [],
  bool searching = false,
  String? reason,
  String text = '',
  double? first,
}) => http.Response.bytes(
  utf8.encode(
    jsonEncode({
      'id': 'a1',
      'status': status,
      'text': text,
      'segments': segments,
      'first_segment_seconds': first,
      'searching_web': searching,
      'reason': reason,
    }),
  ),
  200,
);

void main() {
  test('ask posts the question with position and traveler state', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response('{"id":"a1"}', 200);
    });

    final id = await api.ask(settings, '那間廟拜的是誰？', fix, traveler);

    expect(id, 'a1');
    expect(seen.method, 'POST');
    expect(seen.url.toString(), 'http://100.64.0.1:8765/v1/qa/ask');
    expect(seen.headers['X-Buddy-Token'], 's3cret');
    expect(jsonDecode(seen.body), {
      'question': '那間廟拜的是誰？',
      'lat': 25.056,
      'lon': 121.51,
      'heading_deg': 200,
      'mode': 'walking',
      'companions': 'couple',
      'with_children': false,
      'local_time': '2026-10-20T15:04:09+08:00',
      'more': false,
    });
  });

  test('asking for more sets the flag', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response('{"id":"a1"}', 200);
    });

    await api.ask(settings, '再多說一點', fix, traveler, more: true);

    expect(jsonDecode(seen.body)['more'], true);
  });

  test('answer polls by id and parses segments and status', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return answerResponse(
        segments: [
          {'index': 0, 'audio_seconds': 2.5},
          {'index': 1, 'audio_seconds': 4.0},
        ],
        searching: true,
        first: 7.5,
      );
    });

    final poll = await api.answer(settings, 'a1');

    expect(seen.url.path, '/v1/qa/answer');
    expect(seen.url.queryParameters, {'id': 'a1'});
    expect(poll.status, AnswerStatus.answering);
    expect(
      [for (final s in poll.segments) (s.index, s.audioSeconds)],
      [(0, 2.5), (1, 4.0)],
    );
    expect(poll.searchingWeb, isTrue);
    expect(poll.firstSegmentSeconds, 7.5);
    expect(poll.reason, isNull);
  });

  test('answer parses done and failed with the reason', () async {
    final done = await apiWith(
      (_) async => answerResponse(status: 'done', text: '答案'),
    ).answer(settings, 'a1');
    final failed = await apiWith(
      (_) async => answerResponse(status: 'failed', reason: 'quota'),
    ).answer(settings, 'a1');

    expect(done.status, AnswerStatus.done);
    expect(done.text, '答案');
    expect(failed.status, AnswerStatus.failed);
    expect(failed.reason, 'quota');
  });

  test('an unknown status is an error rather than a silent success', () async {
    final api = apiWith((_) async => answerResponse(status: 'weird'));

    expect(api.answer(settings, 'a1'), throwsA(isA<TourApiException>()));
  });

  test('downloadSegment fetches one wav by index', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response.bytes([1, 2, 3], 200);
    });

    final bytes = await api.downloadSegment(settings, 'a1', 2);

    expect(seen.url.path, '/v1/qa/audio');
    expect(seen.url.queryParameters, {'id': 'a1', 'index': '2'});
    expect(bytes, [1, 2, 3]);
  });

  test('errors carry the status code, connection failures do not', () async {
    final missing = apiWith((_) async => http.Response('no', 404));
    final down = apiWith((_) async => throw http.ClientException('down'));

    await expectLater(
      missing.downloadSegment(settings, 'a1', 0),
      throwsA(
        isA<TourApiException>().having((e) => e.statusCode, 'status', 404),
      ),
    );
    await expectLater(
      down.answer(settings, 'a1'),
      throwsA(
        isA<TourApiException>().having((e) => e.statusCode, 'status', null),
      ),
    );
  });

  test('a host that is not configured is reported, not crashed on', () async {
    final api = apiWith((_) async => http.Response('{}', 200));

    expect(
      api.ask(const HostSettings(url: '', token: ''), 'q', fix, traveler),
      throwsA(isA<TourApiException>()),
    );
  });

  group('asking with a photo', () {
    final image = Uint8List.fromList([0xff, 0xd8, 0xff, 0xe0, 1, 2, 3]);

    test(
      'posts the photo with the compass heading, not the travel heading',
      () async {
        late http.Request seen;
        final api = apiWith((request) async {
          seen = request;
          return http.Response('{"id":"a1"}', 200);
        });

        final id = await api.askPhoto(
          settings,
          '這是什麼？',
          fix, // 行進方向 200
          traveler,
          image,
          compassHeading: 270,
        );

        expect(id, 'a1');
        expect(seen.url.path, '/v1/qa/ask-photo');
        final body = jsonDecode(seen.body) as Map<String, dynamic>;
        expect(body['question'], '這是什麼？');
        expect(body['heading_deg'], 270);
        expect(base64Decode(body['image_base64'] as String), image);
        expect(body['lat'], 25.056);
        expect(body['companions'], 'couple');
      },
    );

    test('without a compass reading no heading is sent at all', () async {
      late http.Request seen;
      final api = apiWith((request) async {
        seen = request;
        return http.Response('{"id":"a1"}', 200);
      });

      await api.askPhoto(settings, '這是什麼？', fix, traveler, image);

      // 走路的方向不能冒充拍照的方向
      expect(jsonDecode(seen.body), isNot(contains('heading_deg')));
    });

    test('a photo the host refuses is reported with its status', () async {
      final api = apiWith((_) async => http.Response('too big', 413));

      await expectLater(
        api.askPhoto(settings, 'q', fix, traveler, image),
        throwsA(
          isA<TourApiException>().having((e) => e.statusCode, 'status', 413),
        ),
      );
    });
  });
}
