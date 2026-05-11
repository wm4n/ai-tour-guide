import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/shared/backend/sse_parser.dart';

Stream<List<int>> _bytesFrom(String s) =>
    Stream.value(utf8.encode(s));

void main() {
  group('SseParser.parse', () {
    test('parses single meta event', () async {
      const raw = 'event: meta\ndata: {"poi_id":"abc","cache_hit":false,"confidence":"high"}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 1);
      expect(events[0].type, 'meta');
      expect(events[0].data['confidence'], 'high');
    });

    test('parses multiple events in one chunk', () async {
      const raw =
          'event: text\ndata: {"chunk":"hello","sentence_idx":0}\n\n'
          'event: audio\ndata: {"chunk_b64":"abc","sentence_idx":0}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 2);
      expect(events[0].type, 'text');
      expect(events[1].type, 'audio');
      expect(events[1].data['sentence_idx'], 0);
    });

    test('parses end event', () async {
      const raw = 'event: end\ndata: {}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 1);
      expect(events[0].type, 'end');
    });

    test('handles events split across two chunks', () async {
      final chunk1 = utf8.encode('event: text\ndata: {"chu');
      final chunk2 = utf8.encode('nk":"hi","sentence_idx":0}\n\n');
      final stream = Stream.fromIterable([chunk1, chunk2]);
      final events = await SseParser.parse(stream).toList();
      expect(events.length, 1);
      expect(events[0].data['chunk'], 'hi');
    });

    test('ignores blocks without event or data lines', () async {
      const raw = ': keep-alive\n\nevent: end\ndata: {}\n\n';
      final events = await SseParser.parse(_bytesFrom(raw)).toList();
      expect(events.length, 1);
      expect(events[0].type, 'end');
    });
  });
}
