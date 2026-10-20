import 'dart:async';
import 'dart:convert';

import 'package:buddy_tour/host/host_client.dart';
import 'package:buddy_tour/host/host_settings.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

const settings = HostSettings(url: 'http://100.64.0.1:8765', token: 's3cret');

void main() {
  test('200 with matching token → connected, sends token header', () async {
    late http.Request seen;
    final client = HostClient(
      MockClient((request) async {
        seen = request;
        return http.Response(
          jsonEncode({'status': 'ok', 'version': '0.1.0'}),
          200,
        );
      }),
    );

    final status = await client.check(settings);

    expect(status, ConnectionStatus.connected);
    expect(seen.url.toString(), 'http://100.64.0.1:8765/v1/status');
    expect(seen.headers['X-Buddy-Token'], 's3cret');
  });

  test('no token configured → no token header is sent', () async {
    late http.Request seen;
    final client = HostClient(
      MockClient((request) async {
        seen = request;
        return http.Response('{}', 200);
      }),
    );

    await client.check(const HostSettings(url: 'http://h:1', token: ''));

    expect(seen.headers.containsKey('X-Buddy-Token'), isFalse);
  });

  test('401 → unauthorized', () async {
    final client = HostClient(MockClient((_) async => http.Response('', 401)));

    expect(await client.check(settings), ConnectionStatus.unauthorized);
  });

  test('5xx → unreachable', () async {
    final client = HostClient(MockClient((_) async => http.Response('', 502)));

    expect(await client.check(settings), ConnectionStatus.unreachable);
  });

  test('network error → unreachable', () async {
    final client = HostClient(
      MockClient((_) async => throw http.ClientException('boom')),
    );

    expect(await client.check(settings), ConnectionStatus.unreachable);
  });

  test('timeout → unreachable', () async {
    final client = HostClient(
      MockClient((_) => Completer<http.Response>().future),
      timeout: const Duration(milliseconds: 10),
    );

    expect(await client.check(settings), ConnectionStatus.unreachable);
  });

  test('empty url → notConfigured without any request', () async {
    var called = false;
    final client = HostClient(
      MockClient((_) async {
        called = true;
        return http.Response('', 200);
      }),
    );

    final status = await client.check(const HostSettings(url: '  ', token: ''));

    expect(status, ConnectionStatus.notConfigured);
    expect(called, isFalse);
  });

  test('malformed url → notConfigured', () async {
    final client = HostClient(MockClient((_) async => http.Response('', 200)));

    expect(
      await client.check(const HostSettings(url: 'http://', token: '')),
      ConnectionStatus.notConfigured,
    );
  });

  test(
    'url without scheme gets http:// and trailing slash is tolerated',
    () async {
      late Uri seen;
      final client = HostClient(
        MockClient((request) async {
          seen = request.url;
          return http.Response('{}', 200);
        }),
      );

      await client.check(
        const HostSettings(url: '100.64.0.1:8765/', token: ''),
      );

      expect(seen.toString(), 'http://100.64.0.1:8765/v1/status');
    },
  );
}
