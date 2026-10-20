import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:speech_to_text/speech_recognition_result.dart';
import 'package:speech_to_text/speech_to_text.dart';

/// 裝置不支援本機 zh-TW 辨識（設計文件第 8 節：這時改用 Apple 線上辨識）。
class OnDeviceUnavailable implements Exception {}

/// 沒有麥克風或語音辨識的權限。
class SpeechPermissionDenied implements Exception {}

class RecognitionFailed implements Exception {
  RecognitionFailed(this.message);

  final String message;

  @override
  String toString() => 'RecognitionFailed: $message';
}

/// 一次「按住說話」的辨識。
abstract class RecognitionSession {
  /// 放開：停止收音，回傳最終辨識文字（沒聽到時是空字串）。
  Future<String> finish();

  /// 放棄這次辨識（例如旅程結束）。
  Future<void> cancel();
}

/// 語音辨識引擎。本機辨識裝置不支援時 [listen] 要丟 [OnDeviceUnavailable]。
abstract class SpeechRecognizer {
  Future<RecognitionSession> listen({required bool onDevice});
}

enum RecognitionMode { onDevice, online }

/// 依能力自動選擇辨識方式：先試 iOS 本機 zh-TW（語音不離開手機），不支援就改用 Apple 線上辨識，
/// 並記住結果，之後不再白試。
class QuestionListener {
  QuestionListener(this._engine);

  final SpeechRecognizer _engine;
  bool? _onDeviceWorks;

  /// 最近一次實際採用的方式；還沒成功過是 null。
  RecognitionMode? mode;

  Future<RecognitionSession> start() async {
    if (_onDeviceWorks != false) {
      try {
        final session = await _engine.listen(onDevice: true);
        _onDeviceWorks = true;
        mode = RecognitionMode.onDevice;
        return session;
      } on OnDeviceUnavailable {
        _onDeviceWorks = false;
        debugPrint('這台裝置不支援本機 zh-TW 辨識，改用線上辨識');
      }
    }
    final session = await _engine.listen(onDevice: false);
    mode = RecognitionMode.online;
    return session;
  }
}

/// 以 `speech_to_text`（iOS 的 SFSpeechRecognizer）實作的引擎。
///
/// 實機行為（本機 zh-TW 是否可用、放開後多久拿到最終結果）模擬器驗不到，見 #10／#8。
class SpeechToTextRecognizer implements SpeechRecognizer {
  SpeechToTextRecognizer({SpeechToText? engine})
    : _speech = engine ?? SpeechToText();

  final SpeechToText _speech;
  String? _localeId;

  static const _listenFor = Duration(seconds: 30);

  Future<void> _ensureReady() async {
    final ready = await _speech.initialize(
      onError: (error) => debugPrint('語音辨識錯誤：${error.errorMsg}'),
    );
    if (!ready) throw SpeechPermissionDenied();
    _localeId ??= await _findTraditionalChinese();
  }

  Future<String> _findTraditionalChinese() async {
    final locales = await _speech.locales();
    for (final locale in locales) {
      if (locale.localeId.replaceAll('_', '-') == 'zh-TW') {
        return locale.localeId;
      }
    }
    throw RecognitionFailed('這台裝置沒有繁體中文（zh-TW）語音辨識');
  }

  @override
  Future<RecognitionSession> listen({required bool onDevice}) async {
    await _ensureReady();
    final session = _SpeechToTextSession(_speech);
    try {
      await _speech.listen(
        onResult: session.onResult,
        listenOptions: SpeechListenOptions(
          listenFor: _listenFor,
          localeId: _localeId,
          onDevice: onDevice,
          partialResults: true,
          listenMode: ListenMode.dictation,
          cancelOnError: true,
        ),
      );
    } on ListenFailedException catch (error) {
      await _speech.cancel();
      final message = error.message ?? '';
      if (onDevice &&
          message.contains('on device recognition is not supported')) {
        throw OnDeviceUnavailable();
      }
      throw RecognitionFailed(message);
    }
    return session;
  }
}

class _SpeechToTextSession implements RecognitionSession {
  _SpeechToTextSession(this._speech);

  final SpeechToText _speech;
  final _final = Completer<String>();
  String _last = '';

  void onResult(SpeechRecognitionResult result) {
    _last = result.recognizedWords;
    if (result.finalResult && !_final.isCompleted) _final.complete(_last);
  }

  @override
  Future<String> finish() async {
    await _speech.stop();
    // 套件會在 finalTimeout 內補上最終結果；沒等到就用最後一次的部分結果
    return _final.future.timeout(
      const Duration(seconds: 3),
      onTimeout: () => _last,
    );
  }

  @override
  Future<void> cancel() => _speech.cancel();
}
