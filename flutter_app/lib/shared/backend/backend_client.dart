import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/sse_parser.dart';

abstract class BackendClient {
  Future<List<POI>> fetchNearby({
    required double lat,
    required double lon,
    required int radius,
    required String lang,
    required String persona,
  });

  Stream<NarrationEvent> narrate({
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  });
}

class RealBackendClient implements BackendClient {
  final String baseUrl;
  final http.Client _http;

  RealBackendClient({required this.baseUrl}) : _http = http.Client();

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
    final response = await _http.get(uri);
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
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  }) async* {
    final request =
        http.Request('POST', Uri.parse('$baseUrl/narration'));
    request.headers['Content-Type'] = 'application/json';
    request.headers['Accept'] = 'text/event-stream';
    request.body = jsonEncode({
      'poi_id': poiId,
      'persona': persona,
      'lang': lang,
      'length': length,
      'force_regenerate': forceRegenerate,
    });
    final response = await _http.send(request);
    if (response.statusCode != 200) {
      throw Exception('narrate failed: HTTP ${response.statusCode}');
    }
    await for (final sseEvent in SseParser.parse(response.stream)) {
      final event = _toNarrationEvent(sseEvent);
      if (event != null) yield event;
    }
  }

  NarrationEvent? _toNarrationEvent(SseEvent sse) => switch (sse.type) {
        'meta' => MetaEvent.fromJson(sse.data),
        'text' => TextEvent.fromJson(sse.data),
        'audio' => AudioEvent.fromJson(sse.data),
        'end' => const EndEvent(),
        'error' => ErrorEvent.fromJson(sse.data),
        _ => ErrorEvent(code: 'unknown', message: 'unknown event: ${sse.type}'),
      };
}

class FakeBackendClient implements BackendClient {
  final List<POI> nearbyPois;
  final List<NarrationEvent> scriptedEvents;

  const FakeBackendClient({
    this.nearbyPois = const [],
    this.scriptedEvents = const [],
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
    required String poiId,
    required String persona,
    required String lang,
    required String length,
    bool forceRegenerate = false,
  }) async* {
    for (final event in scriptedEvents) {
      yield event;
    }
  }
}
