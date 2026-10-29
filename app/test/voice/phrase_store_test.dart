import 'dart:io';
import 'dart:typed_data';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/voice/phrase_store.dart';
import 'package:flutter_test/flutter_test.dart';

Map<FixedPhrase, Uint8List> allPhrases(String tag) => {
  for (final phrase in FixedPhrase.values)
    phrase: Uint8List.fromList('$tag#${phrase.number}'.codeUnits),
};

void main() {
  late Directory root;
  late FilePhraseStore store;

  setUp(() {
    root = Directory.systemTemp.createTempSync('phrases');
    store = FilePhraseStore(root);
  });

  tearDown(() => root.deleteSync(recursive: true));

  test('a voice it never saved has no phrases', () async {
    expect(await store.has('M1@1.2'), isFalse);
    expect(store.pathFor('M1@1.2', FixedPhrase.startTour), isNull);
    expect(store.pathFor(null, FixedPhrase.startTour), isNull);
  });

  test('saves every phrase of a voice under its key', () async {
    await store.save('M1@1.2', allPhrases('M1'));

    expect(await store.has('M1@1.2'), isTrue);
    expect(await store.has('M1@1.5'), isFalse); // 語速不同就是別的聲音鍵
    final path = store.pathFor('M1@1.2', FixedPhrase.hostUnreachable)!;
    expect(File(path).readAsStringSync(), 'M1#6');
    // 只留下成品，沒有寫到一半的暫存檔
    expect(
      Directory(
        '${root.path}/M1@1.2',
      ).listSync().map((e) => e.uri.pathSegments.last).toSet(),
      {for (final phrase in FixedPhrase.values) '${phrase.number}.wav'},
    );
  });

  test('a voice missing any phrase is not complete', () async {
    await store.save('M1@1.2', allPhrases('M1'));
    File(store.pathFor('M1@1.2', FixedPhrase.thinkingWeb)!).deleteSync();

    expect(await store.has('M1@1.2'), isFalse);
    expect(store.pathFor('M1@1.2', FixedPhrase.thinkingWeb), isNull);
    expect(store.pathFor('M1@1.2', FixedPhrase.startTour), isNotNull);
  });

  test('saving again replaces the old files', () async {
    await store.save('M1@1.2', allPhrases('old'));
    await store.save('M1@1.2', allPhrases('new'));

    expect(
      File(store.pathFor('M1@1.2', FixedPhrase.startTour)!).readAsStringSync(),
      'new#7',
    );
  });
}
