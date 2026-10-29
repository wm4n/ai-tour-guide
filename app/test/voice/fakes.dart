import 'dart:async';
import 'dart:typed_data';

import 'package:buddy_tour/audio/fixed_phrase.dart';
import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/voice/phrase_store.dart';
import 'package:buddy_tour/voice/voice_api.dart';

import '../tour/fakes.dart';

VoiceInfo voice(
  String name, {
  String? displayName,
  String description = '',
  bool phrasesReady = true,
}) => VoiceInfo(
  name: name,
  displayName: displayName ?? name,
  description: description,
  key: '$name@1.2',
  phrasesReady: phrasesReady,
);

class FakeVoiceApi implements VoiceApi {
  VoiceCatalog catalog = VoiceCatalog(
    current: 'F2',
    voices: [
      voice('F2', displayName: '示範女聲', description: '女聲・溫暖'),
      voice('M1', displayName: '示範男聲', description: '男聲・沉穩'),
    ],
  );
  Object? listError;
  Object? phraseError;
  Completer<void>? phraseGate;

  /// 某個聲音的短句下載卡在這裡（測試「先點的很慢、後點的很快」）。
  final phraseGates = <String, Completer<void>>{};
  final phrases = <(String, int)>[];
  var lists = 0;

  Object? chooseError;
  Completer<void>? chooseGate;

  /// 主機依序收到的切換。
  final chosen = <String>[];

  @override
  Future<VoiceCatalog> list(HostSettings settings) async {
    lists++;
    if (listError != null) throw listError!;
    return catalog;
  }

  @override
  Future<Uint8List> phrase(
    HostSettings settings,
    String name,
    int number,
  ) async {
    phrases.add((name, number));
    await phraseGate?.future;
    await phraseGates[name]?.future;
    if (phraseError != null) throw phraseError!;
    return Uint8List.fromList('$name#$number'.codeUnits);
  }

  @override
  Future<String> choose(HostSettings settings, String name) async {
    chosen.add(name);
    await chooseGate?.future;
    if (chooseError != null) throw chooseError!;
    return name;
  }
}

/// 記憶體裡的短句存放處（widget 測試的 fake async 等不到真的檔案 IO）。
class FakePhraseStore implements PhraseStore {
  final saved = <String, Map<FixedPhrase, Uint8List>>{};

  @override
  Future<bool> has(String voiceKey) async =>
      saved[voiceKey]?.length == FixedPhrase.values.length;

  @override
  Future<void> save(String voiceKey, Map<FixedPhrase, Uint8List> wavs) async {
    saved[voiceKey] = {...wavs};
  }

  @override
  String? pathFor(String? voiceKey, FixedPhrase phrase) =>
      saved[voiceKey]?.containsKey(phrase) == true
      ? '/phrases/$voiceKey/${phrase.number}.wav'
      : null;
}

/// 播不出來的播放器（例如主機回了壞掉的 wav）。
class BrokenPlayer extends FakePlayer {
  @override
  Future<bool> play(
    Uint8List wav, {
    required String title,
    Duration start = Duration.zero,
    bool releaseFocus = true,
  }) async {
    super.play(wav, title: title, start: start, releaseFocus: releaseFocus);
    throw Exception('Source error');
  }
}
