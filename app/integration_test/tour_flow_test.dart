// 在 iOS 模擬器上跑整條流程：出發 → 回報位置 → 主機準備好 → App 下載並自動播放。
//
// 需要先備妥（見 app/README.md「模擬器端到端測試」）：
// - 主機以重播模式或真實模式在跑，位址用 `--dart-define=HOST_URL=…` 帶入
// - 模擬器已授權定位，並正在播放 GPX（scripts/play-gpx.sh）
// - 想快一點看到第二段：`--dart-define=MIN_GAP_SECONDS=20`
//
// 這個測試只確認「有自動播出」；duck 其他 App 與耳機暫停鍵要實機或手動確認。
import 'package:buddy_tour/main.dart' as app;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

const expectedNarrations = int.fromEnvironment(
  'EXPECTED_NARRATIONS',
  defaultValue: 1,
);
const waitMinutes = int.fromEnvironment('WAIT_MINUTES', defaultValue: 10);

Future<bool> pumpUntil(
  WidgetTester tester,
  bool Function() done, {
  required Duration timeout,
}) async {
  final deadline = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 500));
    if (done()) return true;
  }
  return false;
}

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('出發後自動播出主機準備好的介紹', (tester) async {
    app.main();
    await tester.pump(const Duration(seconds: 2));

    expect(
      await pumpUntil(
        tester,
        () => find.text('主機已連線').evaluate().isNotEmpty,
        timeout: const Duration(seconds: 30),
      ),
      isTrue,
      reason: '連不上主機（HOST_URL 與主機是否在跑？）',
    );

    await tester.tap(find.byKey(const Key('tour-toggle')));
    final started = await pumpUntil(
      tester,
      () =>
          find.text('結束').evaluate().isNotEmpty ||
          find.byKey(const Key('tour-error')).evaluate().isNotEmpty,
      timeout: const Duration(seconds: 20),
    );
    final error = find.byKey(const Key('tour-error')).evaluate();
    expect(
      started && error.isEmpty,
      isTrue,
      reason: error.isEmpty
          ? '出發沒有反應（定位權限對話框？）'
          : '出發失敗：${(error.first.widget as Text).data}',
    );

    final heard = <String>{};
    final deadline = DateTime.now().add(Duration(minutes: waitMinutes));
    while (heard.length < expectedNarrations &&
        DateTime.now().isBefore(deadline)) {
      await tester.pump(const Duration(seconds: 1));
      for (final element in find.textContaining('正在介紹：').evaluate()) {
        final text = (element.widget as Text).data ?? '';
        if (heard.add(text)) debugPrint('播出：$text');
      }
    }

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pump(const Duration(seconds: 1));

    expect(
      heard.length,
      greaterThanOrEqualTo(expectedNarrations),
      reason: '$waitMinutes 分鐘內只播出 ${heard.length} 段：$heard',
    );
  });
}
