import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../host/host_settings.dart';
import 'playback_policy.dart';
import 'traveler_state.dart';

class TourApiException implements Exception {
  TourApiException(this.message);

  final String message;

  @override
  String toString() => 'TourApiException: $message';
}

class NarrationPoll {
  const NarrationPoll({
    required this.active,
    required this.preparing,
    required this.stoppedReason,
    required this.narrations,
  });

  final bool active;
  final bool preparing;

  /// 主機停止準備的原因：`quota`（Claude 額度用完）、`llm_budget`（呼叫上限）、`forbidden_model`。
  final String? stoppedReason;
  final List<NarrationInfo> narrations;
}

/// 本趟某個額度視窗（5 小時、7 天）的用量：結束時用了幾成、本趟增加幾成。
class WindowUse {
  const WindowUse({required this.last, required this.change});

  final double last;
  final double change;

  factory WindowUse.fromJson(Map<String, dynamic> json) => WindowUse(
    last: (json['last'] as num).toDouble(),
    change: (json['change'] as num).toDouble(),
  );
}

/// 主機在一趟結束時回報的用量摘要（完整報告留在主機上）。
class TourSummary {
  const TourSummary({
    required this.calls,
    required this.narrations,
    required this.durationSeconds,
    required this.hitLimit,
    required this.utilization,
  });

  final int calls;
  final int narrations;
  final int durationSeconds;
  final bool hitLimit;

  /// 視窗名稱（`five_hour`、`seven_day`）對應用量，順序照主機給的。
  final Map<String, WindowUse> utilization;

  factory TourSummary.fromJson(Map<String, dynamic> json) => TourSummary(
    calls: json['calls'] as int,
    narrations: json['narrations'] as int,
    durationSeconds: json['duration_seconds'] as int,
    hitLimit: json['hit_limit'] as bool,
    utilization: {
      for (final entry in (json['utilization'] as Map<String, dynamic>).entries)
        entry.key: WindowUse.fromJson(entry.value as Map<String, dynamic>),
    },
  );
}

abstract class TourApi {
  Future<void> start(
    HostSettings settings,
    PositionFix fix,
    TravelerState traveler,
  );
  Future<void> reportLocation(
    HostSettings settings,
    PositionFix fix,
    TravelerState traveler,
  );
  Future<TourSummary?> end(HostSettings settings);

  /// 這段介紹播完了，主機才把它記成「講過」。
  Future<void> markPlayed(HostSettings settings, String id);
  Future<NarrationPoll> poll(HostSettings settings, {required int after});
  Future<Uint8List> downloadAudio(HostSettings settings, String id);
}

class HttpTourApi implements TourApi {
  HttpTourApi(
    this._http, {
    this.timeout = const Duration(seconds: 10),
    this.offset,
  });

  final http.Client _http;
  final Duration timeout;

  /// 回報當地時間用的時區偏移；測試時固定，平常用裝置的時區。
  final Duration? offset;

  @override
  Future<void> start(
    HostSettings settings,
    PositionFix fix,
    TravelerState traveler,
  ) => _post(settings, '/v1/tour/start', body: _body(fix, traveler));

  @override
  Future<void> reportLocation(
    HostSettings settings,
    PositionFix fix,
    TravelerState traveler,
  ) => _post(settings, '/v1/tour/location', body: _body(fix, traveler));

  @override
  Future<void> markPlayed(HostSettings settings, String id) =>
      _post(settings, '/v1/tour/played', body: {'id': id});

  /// 摘要只是附帶的：主機沒給或格式不對時回傳 null，不讓它擋住結束。
  @override
  Future<TourSummary?> end(HostSettings settings) async {
    final response = await _send(
      settings,
      (uri, headers) => _http.post(uri, headers: headers),
      '/v1/tour/end',
    );
    try {
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      final summary = json is Map<String, dynamic> ? json['summary'] : null;
      return summary is Map<String, dynamic>
          ? TourSummary.fromJson(summary)
          : null;
    } on FormatException {
      return null;
    } on TypeError {
      return null;
    }
  }

  @override
  Future<NarrationPoll> poll(
    HostSettings settings, {
    required int after,
  }) async {
    final response = await _send(
      settings,
      (uri, headers) => _http.get(uri, headers: headers),
      '/v1/tour/narrations',
      query: {'after': '$after'},
    );
    final json = jsonDecode(utf8.decode(response.bodyBytes));
    if (json is! Map<String, dynamic>) {
      throw TourApiException('unexpected narrations response');
    }
    return NarrationPoll(
      active: json['active'] as bool,
      preparing: json['preparing'] as bool,
      stoppedReason: json['stopped_reason'] as String?,
      narrations: [
        for (final item in json['narrations'] as List)
          NarrationInfo.fromJson(item as Map<String, dynamic>),
      ],
    );
  }

  @override
  Future<Uint8List> downloadAudio(HostSettings settings, String id) async {
    final response = await _send(
      settings,
      (uri, headers) => _http.get(uri, headers: headers),
      '/v1/tour/audio',
      query: {'id': id},
    );
    return response.bodyBytes;
  }

  Map<String, Object> _body(PositionFix fix, TravelerState traveler) => {
    'lat': fix.lat,
    'lon': fix.lon,
    if (fix.heading != null) 'heading_deg': fix.heading!,
    ...traveler.toJson(),
    'local_time': isoWithOffset(fix.time, offset: offset),
  };

  Future<void> _post(
    HostSettings settings,
    String path, {
    Map<String, Object>? body,
  }) async {
    await _send(
      settings,
      (uri, headers) => _http.post(
        uri,
        headers: {...headers, 'Content-Type': 'application/json'},
        body: body == null ? null : jsonEncode(body),
      ),
      path,
    );
  }

  Future<http.Response> _send(
    HostSettings settings,
    Future<http.Response> Function(Uri uri, Map<String, String> headers) call,
    String path, {
    Map<String, String>? query,
  }) async {
    final base = Uri.tryParse(_normalise(settings.url));
    if (base == null || base.host.isEmpty) {
      throw TourApiException('host is not configured');
    }
    try {
      final response = await call(
        base.replace(path: path, queryParameters: query),
        {if (settings.token.isNotEmpty) 'X-Buddy-Token': settings.token},
      ).timeout(timeout);
      if (response.statusCode != 200) {
        throw TourApiException('$path answered ${response.statusCode}');
      }
      return response;
    } on TourApiException {
      rethrow;
    } on Exception catch (error) {
      throw TourApiException('$path failed: $error');
    }
  }

  static String _normalise(String raw) {
    var text = raw.trim();
    if (text.isEmpty) return '';
    if (!text.contains('://')) text = 'http://$text';
    return text.replaceFirst(RegExp(r'/+$'), '');
  }
}
