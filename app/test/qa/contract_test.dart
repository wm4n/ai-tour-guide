import 'dart:convert';
import 'dart:io';

import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/qa/qa_api.dart';
import 'package:buddy_tour/tour/playback_policy.dart';
import 'package:buddy_tour/tour/traveler_state.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

/// 主機實際輸出的回應範例（`contract/`，主機的測試保證它和真的輸出一致）。
String contract(String name) =>
    File('../contract/$name.json').readAsStringSync();

const settings = HostSettings(url: 'http://100.64.0.1:8765', token: 's3cret');

HttpQaApi apiReturning(String body) => HttpQaApi(
  MockClient((_) async => http.Response.bytes(utf8.encode(body), 200)),
  offset: const Duration(hours: 8),
);

void main() {
  test('the host\'s ask response gives the answer id', () async {
    final id = await apiReturning(contract('qa-ask')).ask(
      settings,
      'q',
      PositionFix(lat: 25.0, lon: 121.5, time: DateTime.utc(2026, 10, 20)),
      const TravelerState(
        mode: TravelMode.walking,
        companions: Companions.solo,
      ),
    );

    expect(id, 'a1b2c3d4e5f6');
  });

  test('the host\'s finished answer is understood', () async {
    final poll = await apiReturning(
      contract('qa-answer-done'),
    ).answer(settings, 'a1b2c3d4e5f6');

    expect(poll.status, AnswerStatus.done);
    expect(poll.text, '拜城隍爺。');
    expect(poll.segments.single.index, 0);
    expect(poll.segments.single.audioSeconds, 2.0);
    expect(poll.firstSegmentSeconds, 0.5);
    expect(poll.searchingWeb, isFalse);
    expect(poll.reason, isNull);
  });

  test('the host\'s cancelled answer is a failure with its reason', () async {
    final poll = await apiReturning(
      contract('qa-answer-failed'),
    ).answer(settings, 'a1b2c3d4e5f6');

    expect(poll.status, AnswerStatus.failed);
    expect(poll.reason, 'cancelled');
    expect(poll.segments, isEmpty);
    expect(poll.firstSegmentSeconds, isNull);
  });

  test('the host\'s cancel response is accepted', () async {
    await apiReturning(contract('qa-cancel')).cancel(settings, 'a1b2c3d4e5f6');
  });
}
