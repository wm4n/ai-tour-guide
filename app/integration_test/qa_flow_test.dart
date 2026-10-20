// 在 iOS 模擬器上跑問答流程：出發 → 按住說話 → 放開 → 主機回答 → App 下載並播出答案。
//
// 模擬器沒有麥克風，所以辨識用 `--dart-define=FAKE_QUESTION=…`（固定「聽到」那句話）；
// 主機用重播模式（固定的假答案與提示音，不呼叫 Claude）：
//
//   cd host && uv run python -m buddy_host --replay-dir <任何資料夾>
//   cd app && flutter test integration_test/qa_flow_test.dart -d <模擬器 UDID> \
//     --dart-define=HOST_URL=http://127.0.0.1:8765 \
//     --dart-define=FAKE_QUESTION=那間廟拜的是誰
//
// 要先授權定位並設起點（見 app/README.md「模擬器端到端測試」）。
// 這個測試確認「問題送得出去、答案一段段播得出來、畫面回到可以再問」；
// 真人的聲音辨識（本機 zh-TW 是否可用）與實際聽感要實機驗（#10、#8）。
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

  testWidgets('按住說話，放開後答案一段段播出來', (tester) async {
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
        () => find.byKey(const Key('ask-button')).evaluate().isNotEmpty,
        timeout: const Duration(seconds: 20),
      ),
      isTrue,
      reason: '出發沒有反應（定位權限？）',
    );

    final gesture = await tester.startGesture(
      tester.getCenter(find.byKey(const Key('ask-button'))),
    );
    await tester.pump(const Duration(milliseconds: 300));
    expect(shows('聽你說…'), isTrue);
    await gesture.up();

    // 放開之後依序會看到：想一想… → 回答中…（答案開始播）→ 回到「按住說話」
    final seen = <String>{};
    final finished = await pumpUntil(tester, () {
      for (final label in ['想一想…', '回答中…']) {
        if (shows(label)) seen.add(label);
      }
      return seen.contains('回答中…') && shows('按住說話');
    }, timeout: const Duration(seconds: 60));

    expect(
      find.byKey(const Key('qa-error')).evaluate(),
      isEmpty,
      reason:
          '發問失敗：${find.byKey(const Key('qa-error')).evaluate().map((e) => (e.widget as Text).data)}',
    );
    expect(finished, isTrue, reason: '60 秒內沒有走完問答流程，看過的畫面：$seen');
    expect(seen, contains('回答中…'));

    await tester.tap(find.byKey(const Key('tour-toggle')));
    await tester.pump(const Duration(seconds: 1));
  });
}
