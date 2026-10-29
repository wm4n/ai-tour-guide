import 'dart:convert';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import '../host/host_http.dart';
import '../host/host_settings.dart';

export '../host/host_http.dart' show TourApiException;

/// 主機上的一個聲音（主機的 `voice/<name>/`，有 `voice.toml` 的才算）。
class VoiceInfo {
  const VoiceInfo({
    required this.name,
    required this.displayName,
    required this.description,
    required this.key,
    required this.phrasesReady,
  });

  /// 資料夾名稱，切換與下載短句用。
  final String name;
  final String displayName;
  final String description;

  /// 聲音鍵（`名稱@語速`），語速改了就不同。
  final String key;

  /// 目前語速的固定短句是否都已在主機上產生。
  final bool phrasesReady;

  factory VoiceInfo.fromJson(Map<String, dynamic> json) => VoiceInfo(
    name: json['name'] as String,
    displayName: json['display_name'] as String,
    description: json['description'] as String,
    key: json['key'] as String,
    phrasesReady: json['phrases_ready'] as bool,
  );
}

/// `GET /v1/voices`：所有聲音與目前使用中的聲音。
class VoiceCatalog {
  const VoiceCatalog({required this.current, required this.voices});

  final String current;
  final List<VoiceInfo> voices;

  /// 目前的聲音；它的 `voice.toml` 被移走或寫壞時不在清單上，這時是 null。
  VoiceInfo? get currentVoice =>
      voices.where((voice) => voice.name == current).firstOrNull;

  factory VoiceCatalog.fromJson(Map<String, dynamic> json) => VoiceCatalog(
    current: json['current'] as String,
    voices: [
      for (final voice in json['voices'] as List)
        VoiceInfo.fromJson(voice as Map<String, dynamic>),
    ],
  );
}

abstract class VoiceApi {
  Future<VoiceCatalog> list(HostSettings settings);

  /// 某個聲音（目前語速）的第 [number] 句固定短句。
  Future<Uint8List> phrase(HostSettings settings, String name, int number);

  /// 請主機改用這個聲音；回傳主機的目前聲音。不存在是 404、短句沒準備好是 409。
  Future<String> choose(HostSettings settings, String name);
}

class HttpVoiceApi implements VoiceApi {
  HttpVoiceApi(http.Client client) : _host = HostHttp(client);

  final HostHttp _host;

  @override
  Future<VoiceCatalog> list(HostSettings settings) async {
    final response = await _host.get(settings, '/v1/voices');
    try {
      return VoiceCatalog.fromJson(
        jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>,
      );
    } on FormatException catch (error) {
      throw TourApiException('/v1/voices answered unexpected JSON: $error');
    } on TypeError catch (error) {
      throw TourApiException('/v1/voices answered unexpected JSON: $error');
    }
  }

  @override
  Future<String> choose(HostSettings settings, String name) async {
    final response = await _host.post(
      settings,
      '/v1/voice',
      body: {'name': name},
    );
    try {
      final json = jsonDecode(utf8.decode(response.bodyBytes));
      return (json as Map<String, dynamic>)['current'] as String;
    } on FormatException catch (error) {
      throw TourApiException('/v1/voice answered unexpected JSON: $error');
    } on TypeError catch (error) {
      throw TourApiException('/v1/voice answered unexpected JSON: $error');
    }
  }

  @override
  Future<Uint8List> phrase(
    HostSettings settings,
    String name,
    int number,
  ) async {
    final response = await _host.get(
      settings,
      '/v1/voices/${Uri.encodeComponent(name)}/phrases/$number',
    );
    return response.bodyBytes;
  }
}
