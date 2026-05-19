## 1. TDD Red — 新增失敗測試

- [x] 1.1 在 `flutter_app/test/unit/trigger_provider_test.dart` 最後一個 `}` 前新增測試：「narrate() fires again after narration even if stationary」（5 POI，播了 node:1 後倒數結束驗證第二次 callCount == 2）
- [x] 1.2 執行 `flutter test test/unit/trigger_provider_test.dart --name "narrate\(\) fires again" -v` 確認測試**失敗**（Expected: 2, Actual: 1）

## 2. TDD Green — 實作修復

- [x] 2.1 在 `flutter_app/lib/features/narration/providers/trigger_provider.dart` 的 `narrationProvider` listener 中，`if (prev?.currentPoi == null && next.currentPoi != null)` 區塊加入 `_lastCandidateIds = {};`
- [x] 2.2 執行 `flutter test test/unit/trigger_provider_test.dart --name "narrate\(\) fires again" -v` 確認新測試**通過**

## 3. 更新語意改變的既有測試

- [x] 3.1 將 `trigger_provider_test.dart` 中「countdown restarts when dedup guard blocks (stationary, similar POIs)」測試重命名為「dedup guard blocks second narrate() after backend SKIP with unchanged POIs」，並將 `firstNarrationEvents`/`subsequentEvents` 改為 `[SkipEvent()]`
- [x] 3.2 執行 `flutter test test/unit/trigger_provider_test.dart -v` 確認所有測試**全部通過**（共 8 個）

## 4. 回歸驗證與提交

- [x] 4.1 執行 `flutter test`（完整套件）確認無回歸
- [x] 4.2 提交：`git add trigger_provider.dart trigger_provider_test.dart && git commit -m "fix(flutter): clear dedup guard after narration so remaining POIs get narrated"`
