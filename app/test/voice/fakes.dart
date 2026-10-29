import 'dart:async';
import 'dart:typed_data';

import 'package:buddy_tour/host/host_settings.dart';
import 'package:buddy_tour/voice/voice_api.dart';

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
  final phrases = <(String, int)>[];
  var lists = 0;

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
    if (phraseError != null) throw phraseError!;
    return Uint8List.fromList('$name#$number'.codeUnits);
  }
}
