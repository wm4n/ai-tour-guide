import 'dart:async';
import 'dart:convert';

import 'package:http/http.dart' as http;

import '../tour/playback_policy.dart';
import '../tour/traveler_state.dart';
import 'host_settings.dart';

class TourApiException implements Exception {
  TourApiException(this.message, {this.statusCode});

  final String message;

  /// 主機有回應但拒絕時的 HTTP 狀態碼；連不上、逾時等沒有回應的情況是 null。
  final int? statusCode;

  @override
  String toString() => 'TourApiException: $message';
}

/// 對主機送出請求：位址正規化、帶 token、逾時，以及把所有失敗統一成 [TourApiException]。
class HostHttp {
  HostHttp(this._http, {this.timeout = const Duration(seconds: 10)});

  final http.Client _http;
  final Duration timeout;

  Future<http.Response> send(
    HostSettings settings,
    Future<http.Response> Function(Uri uri, Map<String, String> headers) call,
    String path, {
    Map<String, String>? query,
    Duration? timeout,
  }) async {
    final base = Uri.tryParse(_normalise(settings.url));
    if (base == null || base.host.isEmpty) {
      throw TourApiException('host is not configured');
    }
    try {
      final response = await call(
        base.replace(path: path, queryParameters: query),
        {if (settings.token.isNotEmpty) 'X-Buddy-Token': settings.token},
      ).timeout(timeout ?? this.timeout);
      if (response.statusCode != 200) {
        throw TourApiException(
          '$path answered ${response.statusCode}',
          statusCode: response.statusCode,
        );
      }
      return response;
    } on TourApiException {
      rethrow;
    } on Exception catch (error) {
      throw TourApiException('$path failed: $error');
    }
  }

  Future<http.Response> get(
    HostSettings settings,
    String path, {
    Map<String, String>? query,
  }) => send(
    settings,
    (uri, headers) => _http.get(uri, headers: headers),
    path,
    query: query,
  );

  Future<http.Response> post(
    HostSettings settings,
    String path, {
    Map<String, Object>? body,
    Map<String, String>? query,
    Duration? timeout,
  }) => send(
    settings,
    (uri, headers) => _http.post(
      uri,
      headers: {
        ...headers,
        if (body != null) 'Content-Type': 'application/json',
      },
      body: body == null ? null : jsonEncode(body),
    ),
    path,
    query: query,
    timeout: timeout,
  );

  static String _normalise(String raw) {
    var text = raw.trim();
    if (text.isEmpty) return '';
    if (!text.contains('://')) text = 'http://$text';
    return text.replaceFirst(RegExp(r'/+$'), '');
  }
}

/// 位置、行進方向、旅人狀態與當地時間：旅程回報與提問共用的欄位（主機的 `FixBody`）。
Map<String, Object> locationBody(
  PositionFix fix,
  TravelerState traveler, {
  Duration? offset,
}) => {
  'lat': fix.lat,
  'lon': fix.lon,
  if (fix.heading != null) 'heading_deg': fix.heading!,
  ...traveler.toJson(),
  'local_time': isoWithOffset(fix.time, offset: offset),
};
