// 在 iOS 模擬器上跑拍照提問：出發 → 按「拍照問」→ 主機回答 → App 下載並播出答案。
//
// 模擬器沒有相機與指南針，所以用 `--dart-define=FAKE_PHOTO=true`（固定「拍到」一張小圖、朝向西方）；
// 主機用重播模式（固定的假答案，不呼叫 Claude）：
//
//   cd host && uv run python -m buddy_host --replay-dir <任何資料夾>
//   cd app && flutter test integration_test/photo_flow_test.dart -d <模擬器 UDID> \
//     --dart-define=HOST_URL=http://127.0.0.1:8765 --dart-define=FAKE_PHOTO=true
//
// 要先授權定位並設起點（見 app/README.md「模擬器端到端測試」）。
// 真的相機、指南針的讀數與 Claude 看圖的結果要實機＋真實 Claude 驗證（須先取得使用者同意呼叫次數）。
import 'package:buddy_tour/main.dart' as app;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

Future<bool> pumpUntil(
  WidgetTester tester,
  bool Function() done, {
  required Duration timeout,
}) async {
  final deadline = DateTime.now().add(timeout);
  while (DateTime.now().isBefore(deadline)) {
    await tester.pump(const Duration(milliseconds: 200));
    if (done()) return true;
  }
  return false;
}

bool shows(String text) => find.text(text).evaluate().isNotEmpty;

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('拍照提問，答案一段段播出來', (tester) async {
    app.main();
    await tester.pump(const Duration(seconds: 2));

    expect(
      await pumpUntil(
        tester,
        () => shows('主機已連線'),
        timeout: const Duration(seconds: 30),
      ),
      isTrue,
      reason: '連不上主機（HOST_URL 與主機是否在跑？）',
    );

    await tester.tap(find.byKey(const Key('tour-toggle')));
    expect(
      await pumpUntil(
        tester,
        () => find.byKey(const Key('photo-button')).evaluate().isNotEmpty,
        timeout: const Duration(seconds: 20),
      ),
      isTrue,
      reason: '出發沒有反應（定位權限？）',
    );

    await tester.tap(find.byKey(const Key('photo-button')));

    final seen = <String>{};
    final finished = await pumpUntil(tester, () {
      for (final label in ['想一想…', '回答中…']) {
        if (shows(label)) seen.add(label);
      }
      return seen.contains('回答中…') && shows('按住說話');
    }, timeout: const Duration(seconds: 60));

    final errors = find
        .byKey(const Key('qa-error'))
        .evaluate()
        .map((e) => (e.widget as Text).data)
        .toList();
    expect(errors, isEmpty, reason: '拍照提問失敗：$errors');
    expect(finished, isTrue, reason: '60 秒內沒有走完流程，看過的畫面：$seen');

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pump(const Duration(seconds: 1));
  });
}
