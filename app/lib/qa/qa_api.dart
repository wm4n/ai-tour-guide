import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../host/host_http.dart';
import '../host/host_settings.dart';
import '../tour/playback_policy.dart';
import '../tour/traveler_state.dart';

enum AnswerStatus { answering, done, failed }

/// 主機已經做好、可以下載的一段答案語音。
class AnswerSegmentInfo {
  const AnswerSegmentInfo({required this.index, required this.audioSeconds});

  factory AnswerSegmentInfo.fromJson(Map<String, dynamic> json) =>
      AnswerSegmentInfo(
        index: json['index'] as int,
        audioSeconds: (json['audio_seconds'] as num).toDouble(),
      );

  final int index;
  final double audioSeconds;
}

/// 輪詢一個問題的答案：文字寫完且每段都做完才是 [AnswerStatus.done]。
class AnswerPoll {
  const AnswerPoll({
    required this.status,
    required this.segments,
    required this.searchingWeb,
    this.reason,
    this.text = '',
    this.firstSegmentSeconds,
  });

  final AnswerStatus status;

  /// 已經可以下載的段落，依序、編號連續。
  final List<AnswerSegmentInfo> segments;

  /// Claude 動用了上網工具：這時 App 可以說「我上網查一下」。
  final bool searchingWeb;

  /// 失敗時的原因：`quota`（額度用完）、`llm_budget`、`forbidden_model`、`no_audio`、`error`。
  final String? reason;
  final String text;
  final double? firstSegmentSeconds;
}

abstract class QaApi {
  /// 送出問題，回傳答案的 id。[more]＝「再多說一點」。
  Future<String> ask(
    HostSettings settings,
    String question,
    PositionFix fix,
    TravelerState traveler, {
    bool more = false,
  });

  /// 拍照提問：[compassHeading] 是拍照時手機（鏡頭）對著的方向；讀不到就不帶方向，
  /// 不拿走路的方向冒充。
  Future<String> askPhoto(
    HostSettings settings,
    String question,
    PositionFix fix,
    TravelerState traveler,
    Uint8List image, {
    double? compassHeading,
  });

  Future<AnswerPoll> answer(HostSettings settings, String id);

  Future<Uint8List> downloadSegment(
    HostSettings settings,
    String id,
    int index,
  );
}

class HttpQaApi implements QaApi {
  HttpQaApi(
    http.Client client, {
    Duration timeout = const Duration(seconds: 10),
    this.offset,
  }) : _host = HostHttp(client, timeout: timeout);

  final HostHttp _host;

  /// 回報當地時間用的時區偏移；測試時固定，平常用裝置的時區。
  final Duration? offset;

  @override
  Future<String> ask(
    HostSettings settings,
    String question,
    PositionFix fix,
    TravelerState traveler, {
    bool more = false,
  }) async {
    final response = await _host.post(
      settings,
      '/v1/qa/ask',
      body: {
        'question': question,
        ...locationBody(fix, traveler, offset: offset),
        'more': more,
      },
    );
    final json = _json(response);
    final id = json['id'];
    if (id is! String) throw TourApiException('unexpected ask response');
    return id;
  }

  /// 照片上傳比一般請求慢（幾百 KB，走 Tailscale）。
  static const _photoTimeout = Duration(seconds: 30);

  @override
  Future<String> askPhoto(
    HostSettings settings,
    String question,
    PositionFix fix,
    TravelerState traveler,
    Uint8List image, {
    double? compassHeading,
  }) async {
    final response = await _host.post(
      settings,
      '/v1/qa/ask-photo',
      timeout: _photoTimeout,
      body: {
        'question': question,
        ...locationBody(
          fix.withHeading(compassHeading),
          traveler,
          offset: offset,
        ),
        'image_base64': base64Encode(image),
      },
    );
    final id = _json(response)['id'];
    if (id is! String) throw TourApiException('unexpected ask response');
    return id;
  }

  @override
  Future<AnswerPoll> answer(HostSettings settings, String id) async {
    final response = await _host.get(
      settings,
      '/v1/qa/answer',
      query: {'id': id},
    );
    final json = _json(response);
    final status = AnswerStatus.values.asNameMap()[json['status']];
    if (status == null) {
      throw TourApiException('unexpected answer status: ${json['status']}');
    }
    try {
      return AnswerPoll(
        status: status,
        segments: [
          for (final item in json['segments'] as List)
            AnswerSegmentInfo.fromJson(item as Map<String, dynamic>),
        ],
        searchingWeb: json['searching_web'] as bool,
        reason: json['reason'] as String?,
        text: json['text'] as String? ?? '',
        firstSegmentSeconds: (json['first_segment_seconds'] as num?)
            ?.toDouble(),
      );
    } on TypeError {
      throw TourApiException('unexpected answer response');
    }
  }

  @override
  Future<Uint8List> downloadSegment(
    HostSettings settings,
    String id,
    int index,
  ) async {
    final response = await _host.get(
      settings,
      '/v1/qa/audio',
      query: {'id': id, 'index': '$index'},
    );
    return response.bodyBytes;
  }

  Map<String, dynamic> _json(http.Response response) {
    try {
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      if (json is Map<String, dynamic>) return json;
    } on FormatException {
      // 落到下面統一丟例外
    }
    throw TourApiException('unexpected response');
  }
}
