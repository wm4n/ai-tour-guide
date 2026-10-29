import 'dart:convert';
import 'dart:io';

import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/voice/voice_api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const settings = HostSettings(url: 'http://100.64.0.1:8765', token: 's3cret');

void main() {
  test('the host\'s voice list is understood (contract)', () async {
    final body = File('../contract/voices.json').readAsStringSync();
    late http.Request sent;
    final api = HttpVoiceApi(
      MockClient((request) async {
        sent = request;
        return http.Response.bytes(utf8.encode(body), 200);
      }),
    );

    final catalog = await api.list(settings);

    expect(sent.method, 'GET');
    expect(sent.url.path, '/v1/voices');
    expect(sent.headers['X-Buddy-Token'], 's3cret');
    expect(catalog.current, 'F2');
    expect(catalog.voices.map((v) => v.name), ['F2', 'M1']);
    final first = catalog.voices.first;
    expect(first.displayName, '示範女聲');
    expect(first.description, '女聲・溫暖');
    expect(first.key, 'F2@1.2');
    expect(first.phrasesReady, isTrue);
    expect(catalog.voices.last.phrasesReady, isFalse);
    expect(catalog.currentVoice?.name, 'F2');
  });

  test('a current voice missing from the list has no details', () {
    final catalog = VoiceCatalog.fromJson({
      'current': 'X9',
      'voices': <Object>[],
    });

    expect(catalog.current, 'X9');
    expect(catalog.currentVoice, isNull);
  });

  test('downloads one phrase of a voice', () async {
    late Uri asked;
    final api = HttpVoiceApi(
      MockClient((request) async {
        asked = request.url;
        return http.Response.bytes([82, 73, 70, 70], 200);
      }),
    );

    final bytes = await api.phrase(settings, 'M 1/x', 7);

    expect(bytes, [82, 73, 70, 70]);
    // 聲音名稱一定只占路徑的一節
    expect(asked.pathSegments, ['v1', 'voices', 'M 1/x', 'phrases', '7']);
  });

  test('a missing phrase is an error', () async {
    final api = HttpVoiceApi(
      MockClient((_) async => http.Response('not found', 404)),
    );

    expect(
      () => api.phrase(settings, 'M1', 7),
      throwsA(
        isA<TourApiException>().having((e) => e.statusCode, 'status', 404),
      ),
    );
  });
}
