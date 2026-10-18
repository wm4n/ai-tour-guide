import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('main Android manifest declares WAKE_LOCK', () {
    const wakeLockPermission =
        '<uses-permission android:name="android.permission.WAKE_LOCK"/>';
    final manifest =
        File('android/app/src/main/AndroidManifest.xml').readAsStringSync();

    expect(manifest, contains(wakeLockPermission));
  });
}
