## Context

目前 Flutter app 和 Python backend 各自零散地使用 `print()` 和 `logger.warning()`，缺乏一致的事件追蹤結構。問題發生時難以從 log 中快速定位是 POI 載入、語音觸發、還是上游 API 失敗所導致。

本 change 在兩端引入統一的結構化 logging 架構：Flutter 採用 `AppLogger` singleton 搭配可插拔的 `LogTransport` 介面；Python backend 採用 stdlib `logging` 搭配自訂 formatter 和 `log_event()` helper。

兩端共享相同的事件名稱字串（如 `"POI_LOADED"`），分別以各自語言的常規命名（Dart: camelCase、Python: UPPER_SNAKE_CASE）定義在 `LogEvents` 類別中。

## Goals / Non-Goals

**Goals:**
- 在 Flutter 和 Python backend 引入統一的結構化事件 logging
- 開發期人類可讀（emoji / 文字格式），生產環境（Cloud Run）輸出 JSON 供 GCP Cloud Logging 收集
- 設計可插拔的 transport 層，讓未來 Firebase Crashlytics / Analytics 整合無需重構 call sites
- 不引入任何新依賴（Flutter 使用 `dart:developer`，Python 使用 stdlib `logging`）

**Non-Goals:**
- Firebase Crashlytics / Analytics 的實際整合（本 change 只預留 stub）
- 跨服務的 distributed tracing（如 trace ID 傳遞）
- Log 的集中儲存或查詢介面（依賴 GCP Cloud Logging 的既有能力）
- 修改現有功能行為（所有 log call 為純 additive）

## Decisions

### Decision 1：Flutter 採用 singleton + transport 列表，而非全域 logger

**選擇：** `AppLogger.init(transports: [...])` 在 `main.dart` 初始化，所有 call site 呼叫靜態方法（`AppLogger.info()` 等）。

**理由：** Flutter 沒有依賴注入容器，static singleton 是最低摩擦的方案。Transport 列表使測試可注入 `_CaptureTransport` 而不依賴輸出副作用；將來加入 `FirebaseTransport()` 只需改 `main.dart` 一行。

**替代方案考慮：**
- Provider/Riverpod 注入 logger：需要每個 widget/notifier 攜帶 ref，對 logging 這種橫切關注點過重
- 直接呼叫 `dart:developer`：無法在測試中截獲，也難以切換格式

### Decision 2：Python 採用 `log_event()` helper 包裝 stdlib `logging`，而非第三方 structlog

**選擇：** 自訂 `_HumanFormatter` 和 `_JsonFormatter`，`log_event()` 透過 `extra={"event": ..., "params": ...}` 傳遞結構化資料。

**理由：** 不引入 `structlog` 等外部依賴；stdlib `logging` 已有完整的 handler/formatter 架構，`extra` 欄位可讓 formatter 讀取結構化資料而不影響 `record.getMessage()`。

**替代方案考慮：**
- `structlog`：功能更完整但增加依賴，且 Cloud Run 部署需要確認套件可用性
- 直接 `logger.info(json.dumps({...}))`：缺乏格式切換能力，測試時難以驗證欄位

### Decision 3：ConsoleTransport 以 `kDebugMode` 切換 emoji/plain 格式

**選擇：** `formatDebug()`（emoji + HH:MM:SS）用於 `kDebugMode`，`formatRelease()`（ISO 8601 + level name）用於 release/CI。

**理由：** Flutter 測試預設 `kDebugMode = false`，實際裝置 debug build 才有 emoji。這符合目標：開發者快速掃描 vs 機器可讀輸出。

### Decision 4：事件名稱以字串常數管理，兩端字串值完全相同

**選擇：** Dart `LogEvents.poiLoaded = "POI_LOADED"`，Python `LogEvents.POI_LOADED = "POI_LOADED"`，字串值一致。

**理由：** 未來若要對 log 做跨端分析（例如在 BigQuery 中 JOIN Flutter 和 backend 的事件），相同的字串值可直接 match，不需額外映射表。

## Risks / Trade-offs

- **[Risk] `AppLogger.init()` 未呼叫時所有 log 靜默丟失** → Mitigation：`_transports` 初始為空列表，呼叫前不會 crash；在 `main.dart` 的初始化是唯一必要的 wiring point，文件清楚說明
- **[Risk] `log_event()` 的 `extra` 欄位若遇到不支援 `extra` 的第三方 handler 可能產生警告** → Mitigation：`setup_logging()` 會 `handlers.clear()` 並只掛自訂 handler，避免衝突
- **[Risk] `_HumanFormatter` 使用 `datetime.now()` 而非 `record.created`，時間戳可能有微小漂移** → Mitigation：精度需求為人類可讀，毫秒級漂移可接受；JSON formatter 同樣行為，一致性高
- **[Risk] Flutter `_CaptureTransport` 在 widget test 環境下若 `AppLogger` 狀態未重置可能跨測試洩漏** → Mitigation：每個測試的 `setUp` 呼叫 `AppLogger.init()` 重置 transport 列表

## Migration Plan

1. **合併後立即生效**：所有 log call 為 additive，不改變現有行為，無需 feature flag
2. **Cloud Run 啟用 JSON 格式**：在 Cloud Run 環境設定 `LOG_FORMAT=json`（已更新 `.env.example` 和部署文件）
3. **Firebase 整合（未來）**：在 `main.dart` 的 `AppLogger.init()` 加入 `FirebaseTransport()`，stub 已就位
4. **Rollback**：移除 `AppLogger.init()` 呼叫即可靜默所有 log，不影響功能

## Open Questions

（無。設計已通過 docs/superpowers/specs/2026-05-14-logging-design.md 審核，所有關鍵決策已確定。）
