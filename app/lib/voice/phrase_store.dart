import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../audio/fixed_phrase.dart';

/// 從主機下載、存在手機裡的固定短句，依聲音鍵（`名稱@語速`）分資料夾。
///
/// 連不上主機時也要念得出目前聲音的短句，所以要存在手機裡。
abstract class PhraseStore {
  /// 這個聲音的每一句短句都在手機裡。
  Future<bool> has(String voiceKey);

  /// 一次存入一個聲音的全部短句（先全部下載好才存，存好的就一定是完整的一組）。
  Future<void> save(String voiceKey, Map<FixedPhrase, Uint8List> wavs);

  /// 某一句的檔案位置；沒有（或沒有聲音鍵）是 null，這時播 App 內建的。
  String? pathFor(String? voiceKey, FixedPhrase phrase);
}

/// 在 main() 以 App 文件目錄底下的 [FilePhraseStore] 覆寫。
final phraseStoreProvider = Provider<PhraseStore>(
  (ref) => throw UnimplementedError('phraseStoreProvider must be overridden'),
);

class FilePhraseStore implements PhraseStore {
  FilePhraseStore(this.root);

  final Directory root;

  File _file(String voiceKey, FixedPhrase phrase) =>
      File('${root.path}/$voiceKey/${phrase.number}.wav');

  @override
  Future<bool> has(String voiceKey) async {
    for (final phrase in FixedPhrase.values) {
      if (!await _file(voiceKey, phrase).exists()) return false;
    }
    return true;
  }

  @override
  Future<void> save(String voiceKey, Map<FixedPhrase, Uint8List> wavs) async {
    await Directory('${root.path}/$voiceKey').create(recursive: true);
    for (final MapEntry(key: phrase, value: wav) in wavs.entries) {
      // 先寫暫存檔再換上：寫到一半被關掉，不會留下半個音檔被當成完整的
      final file = _file(voiceKey, phrase);
      final partial = File('${file.path}.tmp');
      await partial.writeAsBytes(wav, flush: true);
      await partial.rename(file.path);
    }
  }

  @override
  String? pathFor(String? voiceKey, FixedPhrase phrase) {
    if (voiceKey == null) return null;
    final file = _file(voiceKey, phrase);
    return file.existsSync() ? file.path : null;
  }
}
