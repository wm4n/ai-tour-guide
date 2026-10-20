import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

/// 沒有這些設定，鎖定畫面時就收不到位置、也播不出聲音；錯了只有實機或模擬器跑起來才會發現。
void main() {
  final plist = File('ios/Runner/Info.plist').readAsStringSync();

  test('keeps location and audio alive in the background', () {
    final modes = RegExp(
      r'<key>UIBackgroundModes</key>\s*<array>(.*?)</array>',
      dotAll: true,
    ).firstMatch(plist)?.group(1);

    expect(modes, isNotNull);
    expect(modes, contains('<string>location</string>'));
    expect(modes, contains('<string>audio</string>'));
  });

  test('explains why location is needed', () {
    expect(plist, contains('<key>NSLocationWhenInUseUsageDescription</key>'));
    expect(
      plist,
      contains('<key>NSLocationAlwaysAndWhenInUseUsageDescription</key>'),
    );
  });

  test('explains why the microphone and speech recognition are needed', () {
    // 按住說話：沒有這兩項說明，iOS 一要權限就直接讓 App 當掉
    expect(plist, contains('<key>NSMicrophoneUsageDescription</key>'));
    expect(plist, contains('<key>NSSpeechRecognitionUsageDescription</key>'));
  });

  test('explains why the camera is needed', () {
    // 拍照提問：沒有這項說明，iOS 一開相機就直接讓 App 當掉
    expect(plist, contains('<key>NSCameraUsageDescription</key>'));
  });
}
