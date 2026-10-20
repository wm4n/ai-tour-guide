import 'dart:convert';

import 'package:buddy_tour/host/host_settings.dart';
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
  mode: TravelMode.driving,
  companions: Companions.family,
  withChildren: true,
);

HttpTourApi apiWith(Future<http.Response> Function(http.Request) handler) =>
    HttpTourApi(MockClient(handler), offset: const Duration(hours: 8));

void main() {
  test('start posts the position together with the traveler state', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response('{"status":"started"}', 200);
    });

    await api.start(settings, fix, traveler);

    expect(seen.method, 'POST');
    expect(seen.url.toString(), 'http://100.64.0.1:8765/v1/tour/start');
    expect(seen.headers['X-Buddy-Token'], 's3cret');
    expect(jsonDecode(seen.body), {
      'lat': 25.056,
      'lon': 121.51,
      'heading_deg': 200,
      'mode': 'driving',
      'companions': 'family',
      'with_children': true,
      'local_time': '2026-10-20T15:04:09+08:00',
    });
  });

  test('heading is left out until it is known', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response('{}', 200);
    });

    await api.reportLocation(
      settings,
      PositionFix(lat: 25.0, lon: 121.5, time: fix.time),
      traveler,
    );

    expect(seen.url.path, '/v1/tour/location');
    expect(jsonDecode(seen.body), isNot(contains('heading_deg')));
  });

  test('end returns the usage summary the host sends back', () async {
    final api = apiWith(
      (request) async => http.Response(
        jsonEncode({
          'status': 'ended',
          'summary': {
            'calls': 4,
            'narrations': 3,
            'duration_seconds': 2400,
            'hit_limit': true,
            'utilization': {
              'five_hour': {'last': 0.38, 'change': 0.12},
              'seven_day': {'last': 0.47, 'change': 0.02},
            },
          },
        }),
        200,
      ),
    );

    final summary = await api.end(settings);

    expect(summary!.calls, 4);
    expect(summary.narrations, 3);
    expect(summary.durationSeconds, 2400);
    expect(summary.hitLimit, isTrue);
    expect(summary.utilization['five_hour']!.last, 0.38);
    expect(summary.utilization['five_hour']!.change, 0.12);
    expect(summary.utilization.keys, ['five_hour', 'seven_day']);
  });

  test('end gives no summary when the host has none to give', () async {
    final noSummary = apiWith(
      (request) async =>
          http.Response('{"status":"ended","summary":null}', 200),
    );
    final oldHost = apiWith(
      (request) async => http.Response('{"status":"ended"}', 200),
    );

    expect(await noSummary.end(settings), isNull);
    expect(await oldHost.end(settings), isNull);
  });

  test('end posts to /v1/tour/end', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response('{}', 200);
    });

    await api.end(settings);

    expect(seen.method, 'POST');
    expect(seen.url.path, '/v1/tour/end');
  });

  test('poll asks for narrations after the cursor and parses them', () async {
    late http.Request seen;
    final api = apiWith((request) async {
      seen = request;
      return http.Response(
        jsonEncode({
          'active': true,
          'preparing': true,
          'stopped_reason': 'quota',
          'narrations': [
            {
              'seq': 3,
              'id': 'wiki:霞海城隍廟',
              'name': '霞海城隍廟',
              'lat': 25.0556,
              'lon': 121.5103,
              'audio_seconds': 34.7,
            },
          ],
        }),
        200,
        headers: {'content-type': 'application/json; charset=utf-8'},
      );
    });

    final poll = await api.poll(settings, after: 2);

    expect(seen.url.queryParameters, {'after': '2'});
    expect(poll.active, isTrue);
    expect(poll.preparing, isTrue);
    expect(poll.stoppedReason, 'quota');
    expect(poll.narrations.single.id, 'wiki:霞海城隍廟');
    expect(poll.narrations.single.audioSeconds, 34.7);
  });

  test(
    'download returns the audio bytes, id passed as a query value',
    () async {
      late http.Request seen;
      final api = apiWith((request) async {
        seen = request;
        return http.Response.bytes([1, 2, 3], 200);
      });

      final bytes = await api.downloadAudio(settings, 'wiki:霞海城隍廟');

      expect(bytes, [1, 2, 3]);
      expect(seen.url.path, '/v1/tour/audio');
      expect(seen.url.queryParameters, {'id': 'wiki:霞海城隍廟'});
    },
  );

  test('a non-200 answer is an error', () async {
    final api = apiWith((_) async => http.Response('nope', 409));

    expect(
      api.reportLocation(settings, fix, traveler),
      throwsA(isA<TourApiException>()),
    );
  });

  test('a network failure is an error too', () async {
    final api = apiWith((_) async => throw http.ClientException('down'));

    expect(api.poll(settings, after: 0), throwsA(isA<TourApiException>()));
  });

  test('an unconfigured host is an error', () async {
    final api = apiWith((_) async => http.Response('{}', 200));

    expect(
      api.end(const HostSettings(url: '', token: '')),
      throwsA(isA<TourApiException>()),
    );
  });
}
