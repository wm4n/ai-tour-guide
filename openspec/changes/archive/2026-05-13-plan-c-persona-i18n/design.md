## Context

Plan B MVP 已完成單一靜態 persona（歷史大叔）的旁白功能。目前後端 `/narration` endpoint 直接 inline hardcode persona 設定（`PersonaConfig`），Flutter HomeScreen 只有一個靜態 `PersonaChip`，`NarrationNotifier.narrate()` 不接受 persona/lang 參數（皆 hardcode）。

Plan C 目標是讓使用者在出發前能選擇 5 種導遊風格（persona）並切換旁白語言（zh-TW / en），後端從 YAML registry 動態載入 persona，Flutter 透過 `SessionState` 傳遞選擇給旁白引擎。

**現有基礎設施：**
- 後端已有 `PersonaLoader.load(id)` 從單一 YAML 檔載入，`history_uncle.yaml` 已存在且含雙語欄位
- Flutter 已有 `SessionState`（含 `status`）、`SessionNotifier`、`NarrationNotifier`、`TriggerNotifier`
- Flutter Riverpod provider 架構已建立，`sessionProvider` → `narrationProvider` → `triggerProvider` 的依賴關係清晰

---

## Goals / Non-Goals

**Goals:**
- 後端新增 4 個 persona YAML（`story_brother`、`gossip_auntie`、`kid_sister`、`foodie`），含雙語 system prompt / narration template / voice 設定
- 後端 `PersonaLoader` 新增 `load_all()` classmethod，在 FastAPI startup 預載所有 persona 成 registry dict
- 後端 `/narration` endpoint 改從 registry 取 persona，未知 persona_id 回傳 HTTP 400
- Flutter `SessionState` 新增 `persona`、`lang` 欄位，`SessionNotifier` 新增 `setPersona()` / `setLang()`（僅 idle 狀態可修改）
- Flutter 新增 `PersonaSelector` widget（5 張垂直卡片），HomeScreen 新增語言切換 `SegmentedButton`
- Flutter `NarrationNotifier.narrate()` 改為接收 `{required String persona, required String lang}` 具名參數
- Flutter `TriggerNotifier` 觸發旁白前從 `sessionProvider` 讀取 persona/lang

**Non-Goals:**
- `foodie` persona 的 Google Places 路由（Plan E）
- Flutter UI 文字 i18n / ARB 檔（Plan F）
- Persona 觸發半徑 per-persona override（Plan F）
- `POST /admin/reload-prompts` endpoint（Plan F）
- `confidence_labels` 的 en 版本（YAML 先只寫 zh-TW）

---

## Decisions

### D1：Persona 定義方式 — Backend YAML + Flutter hardcode 展示資訊

**選擇：** 後端 YAML 負責 AI 行為（prompt、voice、style），Flutter 端用 `const kPersonas` 常數定義 UI 展示資訊（emoji、中文名、描述）。

**理由：** 職責清晰。AI 行為參數（speaking_rate、system_prompt、voice）屬後端責任，UI 展示（emoji、描述文案）屬前端責任。若兩者都放 YAML，Flutter 需要 API 呼叫才能渲染 HomeScreen，增加啟動複雜度。若都放 Flutter，後端 AI 行為難以獨立調整。

**替代方案：** 全放後端 API（`GET /personas`）→ 需要新 endpoint，HomeScreen 需要 loading state，複雜度高且 Plan C 時程緊。全放 Flutter → 後端 AI 行為調整需重新 release App，不適合快速迭代。

---

### D2：PersonaLoader.load_all() 在 startup 預載

**選擇：** 在 FastAPI `create_app()` 時呼叫 `PersonaLoader.load_all()`，將結果以 `dict[str, PersonaConfig]` 形式存於 closure，透過 `get_persona_registry` dependency injector 注入 endpoint。

**理由：** 避免每次 request 讀檔（I/O）。YAML 數量固定（5 個），記憶體佔用極小。Dependency injection 讓測試可 override registry，不需 mock 檔案系統。

**替代方案：** `@lru_cache` 懶載入 → 第一次 request 會有延遲，且 cache invalidation 複雜。每次 request 讀 YAML → I/O overhead，線上環境不適合。

---

### D3：未知 persona_id 回傳 HTTP 400（Breaking behavior 強化）

**選擇：** `/narration` endpoint 收到 registry 中不存在的 `persona_id` 時，立即回傳 `HTTP 400 Bad Request`，detail 包含合法 persona 清單。

**理由：** Plan B 對任何 persona_id 都不驗證（直接 inline 建立），有安全隱患（可傳入任意字串影響 prompt）。Plan C 引入 registry 後，驗證是天然的防護。400 比 500 更明確告知呼叫端是請求錯誤。

**替代方案：** 回傳 default persona（history_uncle）→ 靜默失敗，測試難以發現錯誤呼叫。

---

### D4：NarrationNotifier.narrate() 接收 persona/lang 具名參數

**選擇：** `narrate(POI poi, {required String persona, required String lang})` — 參數由 `TriggerNotifier` 從 `sessionProvider` 讀取後傳入，而非 `NarrationNotifier` 內部讀取 `sessionProvider`。

**理由：** 保持 `NarrationNotifier` 可測試性。若 `NarrationNotifier` 直接 watch `sessionProvider`，單元測試需要 setup session state，耦合度高。由 `TriggerNotifier` 在觸發點讀取 session 再傳入，職責清晰，各 notifier 測試互相獨立。

**替代方案：** `NarrationNotifier` 依賴 `sessionProvider` → 耦合度高。`narrate()` 維持無參數、由 constructor 注入 persona/lang → 無法在 session 期間動態改變（雖然 Plan C 不需要，但設計不夠彈性）。

---

## Risks / Trade-offs

**[Risk] Flutter kPersonas 常數與後端 YAML 不同步**
→ Mitigation：設計文件 §3 Persona 清單即為單一真相來源，plan 文件明確列出 5 個 persona 的 id / emoji / 中文名。PR review 時需比對。未來 Plan F 可考慮 `GET /personas` API 消除此同步需求。

**[Risk] NarrationNotifier.narrate() 簽章變更是 breaking change，可能漏改呼叫端**
→ Mitigation：Flutter 強型別，漏改呼叫端會直接 compile error，無法靜默失敗。Tasks 明確列出所有需更新的呼叫點（`TriggerNotifier`、integration tests）。

**[Risk] YAML 欄位缺漏（narration_template 少 en 版本等）導致 runtime KeyError**
→ Mitigation：`TestAllPersonaYamls` smoke test 在 CI 驗證每個 YAML 有 zh-TW + en 版本的 system_prompt 和 narration_template。

**[Risk] PersonaSelector 在 HomeScreen 上 5 張卡片過長，超出螢幕**
→ Mitigation：HomeScreen 改為 `SingleChildScrollView` 包覆，卡片內 margin 控制，實機測試確認 iPhone SE (4" 螢幕) 可正常捲動。

---

## Migration Plan

1. 後端先行：新增 4 個 YAML + `load_all()` + endpoint 驗證，全部後端測試通過後 commit
2. Flutter 後跟：新增 `persona_data.dart` → 修改 `session_provider.dart` → 新增 `PersonaSelector` → 修改 `narration_provider.dart` → 修改 `trigger_provider.dart` → 修改 `home_screen.dart`，每步驟確認測試通過後 commit
3. 無資料庫 schema 變更，無 migration script 需要
4. 無 rollback 需求（功能新增，不改現有資料格式）

---

## Open Questions

- （已決策）`foodie` persona 的 poi_source 在 Plan C 先用 `osm_wikipedia`，Plan E 才切換 Google Places
- （已決策）UI 文字維持中文，不做 ARB i18n，Plan F 才處理
- `SegmentedButton` 在 Flutter 3.x 版本相容性是否需要確認？（專案目前使用版本待確認，tasks 執行時應先跑 `flutter --version`）
