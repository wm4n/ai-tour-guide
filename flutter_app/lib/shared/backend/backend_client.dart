import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:http_parser/http_parser.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/backend/sse_parser.dart';

class PreviousSelection {
  final String poiId;
  final String poiName;
  final String script;

  const PreviousSelection({
    required this.poiId,
    required this.poiName,
    required this.script,
  });
}

abstract class BackendClient {
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  });

  Stream<NarrationEvent> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    required String length,
    PreviousSelection? previousSelection,
    bool forceRegenerate = false,
  });

  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  });
}

class RealBackendClient implements BackendClient {
  final String baseUrl;
  final String apiKey;
  final http.Client _http;

  RealBackendClient({required this.baseUrl, this.apiKey = ''})
      : _http = http.Client();

  Map<String, String> get _authHeaders =>
      apiKey.isNotEmpty ? {'X-Api-Key': apiKey} : {};

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async {
    final uri = Uri.parse('$baseUrl/poi/nearby').replace(
      queryParameters: {
        'lat': lat.toString(),
        'lon': lon.toString(),
        'radius': radius.toString(),
        'lang': lang,
        'persona': persona,
      },
    );
    final response = await _http.get(uri, headers: _authHeaders);
    if (response.statusCode != 200) {
      throw Exception('fetchNearby failed: HTTP ${response.statusCode}');
    }
    final json = jsonDecode(response.body) as Map<String, dynamic>;
    return (json['pois'] as List)
        .map((e) => POI.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  @override
  Stream<NarrationEvent> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    required String length,
    PreviousSelection? previousSelection,
    bool forceRegenerate = false,
  }) async* {
    final candidatesJson = candidates.map((poi) => <String, dynamic>{
      'poi_id': poi.id,
      'poi_name': poi.name,
      'poi_lat': poi.lat,
      'poi_lon': poi.lon,
      'distance_m': poi.distanceM,
      'poi_tags': poi.tags,
      if (poi.wiki != null) ...{
        'wiki_title': poi.wiki!.title,
        'wiki_extract': poi.wiki!.extract,
      },
    }).toList();

    final body = <String, dynamic>{
      'candidates': candidatesJson,
      'persona': persona,
      'lang': lang,
      'length': length,
      'force_regenerate': forceRegenerate,
      if (previousSelection != null) 'previous_selection': {
        'poi_id': previousSelection.poiId,
        'poi_name': previousSelection.poiName,
        'script': previousSelection.script,
      },
    };

    debugPrint(
      '[LLM Input] candidates=${candidates.length} | persona=$persona | lang=$lang'
      '${previousSelection != null ? " | has_previous=true" : ""}',
    );

    final request = http.Request('POST', Uri.parse('$baseUrl/narration'));
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.headers.addAll(_authHeaders);
    request.body = jsonEncode(body);
    final response = await _http.send(request);
    if (response.statusCode != 200) {
      throw Exception('narrate failed: HTTP ${response.statusCode}');
    }
    await for (final sseEvent in SseParser.parse(response.stream)) {
      final event = _toNarrationEvent(sseEvent);
      if (event != null) yield event;
    }
  }

  @override
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async* {
    final request = http.MultipartRequest('POST', Uri.parse('$baseUrl/qa'));
    request.headers['Accept'] = 'text/event-stream';
    request.headers.addAll(_authHeaders);
    request.files.add(http.MultipartFile.fromBytes(
      'audio',
      audioBytes,
      filename: 'recording.wav',
      contentType: MediaType('audio', 'wav'),
    ));
    request.fields['context'] = jsonEncode({
      'current_poi_id': currentPoiId,
      'persona': persona,
      'lang': lang,
      'narration_so_far': narrationSoFar,
    });

    final response = await _http.send(request);
    if (response.statusCode != 200) {
      throw Exception('qa failed: HTTP ${response.statusCode}');
    }
    await for (final sseEvent in SseParser.parse(response.stream)) {
      final event = _toQaEvent(sseEvent);
      if (event != null) yield event;
    }
  }

  NarrationEvent? _toNarrationEvent(SseEvent sse) => switch (sse.type) {
        'meta' => MetaEvent.fromJson(sse.data),
        'text' => TextEvent.fromJson(sse.data),
        'audio' => AudioEvent.fromJson(sse.data),
        'end' => const EndEvent(),
        'error' => ErrorEvent.fromJson(sse.data),
        'skip' => SkipEvent.fromJson(sse.data),
        _ => null,
      };

  QaEvent? _toQaEvent(SseEvent sse) => switch (sse.type) {
        'transcript' => TranscriptQaEvent.fromJson(sse.data),
        'text' => TextQaEvent.fromJson(sse.data),
        'audio' => AudioQaEvent.fromJson(sse.data),
        'end' => EndQaEvent(),
        'error' => ErrorQaEvent.fromJson(sse.data),
        _ => ErrorQaEvent(code: 'unknown', message: 'unknown event: ${sse.type}'),
      };
}

class FakeBackendClient implements BackendClient {
  final List<POI> nearbyPois;
  final List<NarrationEvent> scriptedEvents;
  final List<QaEvent> scriptedQaEvents;

  const FakeBackendClient({
    this.nearbyPois = const [],
    this.scriptedEvents = const [],
    this.scriptedQaEvents = const [],
  });

  @override
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  }) async =>
      nearbyPois;

  @override
  Stream<NarrationEvent> narrate({
    required List<POI> candidates,
    required String persona,
    required String lang,
    required String length,
    PreviousSelection? previousSelection,
    bool forceRegenerate = false,
  }) async* {
    for (final event in scriptedEvents) {
      yield event;
    }
  }

  @override
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar = '',
  }) async* {
    for (final event in scriptedQaEvents) {
      yield event;
    }
  }
}
