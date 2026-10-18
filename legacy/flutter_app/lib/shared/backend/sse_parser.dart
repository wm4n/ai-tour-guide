import 'dart:convert';

class SseEvent {
  final String type;
  final Map<String, dynamic> data;

  const SseEvent({required this.type, required this.data});
}

class SseParser {
  static Stream<SseEvent> parse(Stream<List<int>> byteStream) async* {
    var buffer = '';
    await for (final chunk in byteStream) {
      buffer += utf8.decode(chunk, allowMalformed: true);
      while (buffer.contains('\n\n')) {
        final idx = buffer.indexOf('\n\n');
        final block = buffer.substring(0, idx);
        buffer = buffer.substring(idx + 2);
        final event = _parseBlock(block);
        if (event != null) yield event;
      }
    }
  }

  static SseEvent? _parseBlock(String block) {
    String? type;
    String? dataLine;
    for (final line in block.split('\n')) {
      if (line.startsWith('event: ')) {
        type = line.substring(7);
      } else if (line.startsWith('data: ')) {
        dataLine = line.substring(6);
      }
    }
    if (type == null || dataLine == null) return null;
    try {
      final data = jsonDecode(dataLine) as Map<String, dynamic>;
      return SseEvent(type: type, data: data);
    } catch (_) {
      return null;
    }
  }
}
