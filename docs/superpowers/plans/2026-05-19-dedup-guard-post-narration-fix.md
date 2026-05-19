# Dedup Guard Post-Narration Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修復 `TriggerNotifier` 中 dedup guard 的漏洞：後端播了景點後，下一次倒數結束時應該繼續送出 LLM 請求，而非被誤判為「沒有變化」而跳過。

**Architecture:** 當 `narrationProvider` 通知景點開始播放時（`prev.currentPoi == null && next.currentPoi != null`），清空 `_lastCandidateIds`，使 dedup guard 的歷史比較基準失效。後端 SKIP 的路徑不受影響（沒有景點播放 → `_lastCandidateIds` 不清空 → 下次仍然 SKIP）。

**Tech Stack:** Flutter / Dart 3.x, Riverpod, flutter_test

---

## File Map

| 動作 | 路徑 |
|---|---|
| 修改 | `flutter_app/lib/features/narration/providers/trigger_provider.dart` |
| 修改 | `flutter_app/test/unit/trigger_provider_test.dart` |

---

### Task 1: 寫失敗測試（TDD Red）

**Files:**
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: 在測試檔最後 `}` 之前新增以下測試**

在 `flutter_app/test/unit/trigger_provider_test.dart` 第 356 行（`});` 即 dedup guard 測試結尾）之後、最後一個 `}` 之前，插入：

```dart
  test('narrate() fires again after narration even if stationary', () async {
    const pois = [
      POI(id: 'osm:node:1', name: 'POI 1', lat: 25.10, lon: 121.54, tags: {}, distanceM: 50, confidence: 'high'),
      POI(id: 'osm:node:2', name: 'POI 2', lat: 25.10, lon: 121.54, tags: {}, distanceM: 60, confidence: 'high'),
      POI(id: 'osm:node:3', name: 'POI 3', lat: 25.10, lon: 121.54, tags: {}, distanceM: 70, confidence: 'high'),
      POI(id: 'osm:node:4', name: 'POI 4', lat: 25.10, lon: 121.54, tags: {}, distanceM: 80, confidence: 'high'),
      POI(id: 'osm:node:5', name: 'POI 5', lat: 25.10, lon: 121.54, tags: {}, distanceM: 90, confidence: 'high'),
    ];
    const firstNarrationEvents = [
      MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'high'),
      EndEvent(),
    ];
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final trackingClient = _CountingBackendClient(
      nearbyPois: pois,
      firstEvents: firstNarrationEvents,
      subsequentEvents: firstNarrationEvents,
    );
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(trackingClient),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(
            const AppSettings(skipDisplacementM: 500, countdownSeconds: 1),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);
    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});
    fakeLocation.emit(fakePosition(25.10, 121.54));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    expect(trackingClient.callCount, 1);
    // After 1s countdown, dedup guard should be cleared because a narration played.
    // Second call must fire even though user hasn't moved and POI list is 80% similar.
    await Future<void>.delayed(const Duration(seconds: 2));
    expect(
      trackingClient.callCount,
      2,
      reason: 'after narration plays, _lastCandidateIds is cleared so second call must fire',
    );
  });
```

- [ ] **Step 2: 執行新測試確認它失敗**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart --name "narrate\(\) fires again" -v
```

預期：**FAIL** — `Expected: <2>  Actual: <1>`

---

### Task 2: 實作修復（TDD Green）

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart:74-77`

- [ ] **Step 1: 在 narrationProvider listener 中加入一行**

開啟 `flutter_app/lib/features/narration/providers/trigger_provider.dart`，找到第 74-77 行：

```dart
        if (prev?.currentPoi == null && next.currentPoi != null) {
          _sessionPlayedIds.add(next.currentPoi!.id);
          _hasEverFired = true;
        }
```

修改為：

```dart
        if (prev?.currentPoi == null && next.currentPoi != null) {
          _sessionPlayedIds.add(next.currentPoi!.id);
          _hasEverFired = true;
          _lastCandidateIds = {};
        }
```

- [ ] **Step 2: 執行新測試確認通過**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart --name "narrate\(\) fires again" -v
```

預期：**PASS**

- [ ] **Step 3: 執行全部測試，確認哪些測試失敗**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart -v
```

預期：「countdown restarts when dedup guard blocks (stationary, similar POIs)」這個測試會 **FAIL**，原因是它的情境（後端返回 MetaEvent + EndEvent → 景點播完 → `_lastCandidateIds` 清空）現在不再觸發 dedup guard，`callCount` 會變成 2 而非 1。

---

### Task 3: 更新因修復而語意改變的既有測試

**Files:**
- Modify: `flutter_app/test/unit/trigger_provider_test.dart:309-356`

- [ ] **Step 1: 將「dedup guard blocks」測試的情境改為 SkipEvent**

該測試的目的是驗證：後端 SKIP 且 POI 沒變時，dedup guard 正確阻擋下一次請求。修改方式：將 `firstNarrationEvents` 改為 `[SkipEvent()]`，這樣不會有景點播放，`_lastCandidateIds` 不會被清空，dedup guard 仍正確阻擋。

找到第 309-356 行的測試，將整個測試替換為：

```dart
  test('dedup guard blocks second narrate() after backend SKIP with unchanged POIs', () async {
    const pois = [
      POI(id: 'osm:node:1', name: 'POI 1', lat: 25.10, lon: 121.54, tags: {}, distanceM: 50, confidence: 'high'),
      POI(id: 'osm:node:2', name: 'POI 2', lat: 25.10, lon: 121.54, tags: {}, distanceM: 60, confidence: 'high'),
      POI(id: 'osm:node:3', name: 'POI 3', lat: 25.10, lon: 121.54, tags: {}, distanceM: 70, confidence: 'high'),
      POI(id: 'osm:node:4', name: 'POI 4', lat: 25.10, lon: 121.54, tags: {}, distanceM: 80, confidence: 'high'),
      POI(id: 'osm:node:5', name: 'POI 5', lat: 25.10, lon: 121.54, tags: {}, distanceM: 90, confidence: 'high'),
    ];
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final trackingClient = _CountingBackendClient(
      nearbyPois: pois,
      firstEvents: const [SkipEvent()],
      subsequentEvents: const [SkipEvent()],
    );
    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(trackingClient),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(
            const AppSettings(skipDisplacementM: 500, countdownSeconds: 1),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);
    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});
    fakeLocation.emit(fakePosition(25.10, 121.54));
    await Future<void>.delayed(const Duration(milliseconds: 200));
    expect(trackingClient.callCount, 1);
    await Future<void>.delayed(const Duration(seconds: 2));
    expect(
      trackingClient.callCount,
      1,
      reason: 'after backend SKIP with unchanged POIs, dedup guard must block second call',
    );
    final state = container.read(triggerProvider);
    expect(state.isCountingDown, isTrue,
        reason: 'countdown should restart after dedup guard blocks');
  });
```

- [ ] **Step 2: 執行全部 trigger_provider 測試確認全部通過**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart -v
```

預期：**全部 PASS**，共 8 個測試（原 7 個 + 新增 1 個）

- [ ] **Step 3: 執行完整 Flutter 測試套件確認無回歸**

```bash
cd flutter_app && flutter test
```

預期：全部 PASS

- [ ] **Step 4: 提交**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "fix(flutter): clear dedup guard after narration so remaining POIs get narrated"
```

---

## 驗證摘要

| 情境 | 預期行為 | 測試覆蓋 |
|---|---|---|
| 後端播了景點 → 倒數結束，未移動 | 第二次 narrate() 送出 | 新增測試 |
| 後端 SKIP → 倒數結束，POI 未變 | dedup 阻擋，不重送 | 更新後的既有測試 |
| 全部 POI 已播完 | available 空 → countdown 重啟 | 既有測試（不變） |
| 使用者移動 > 30m | dedup 不觸發，正常送出 | 既有測試（不變） |
