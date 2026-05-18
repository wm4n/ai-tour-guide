## Why

目前 Flutter app 和 Python backend 都缺乏結構化的事件日誌，問題發生時難以追蹤 POI 載入、語音導覽觸發、QA 流程等關鍵里程碑的執行狀況。導入一套統一的結構化日誌系統，讓開發期可以用 emoji 格式快速掃描，生產環境（Cloud Run）可以輸出 JSON 讓 GCP Cloud Logging 自動收集。

## What Changes

- **新增 Flutter 日誌核心模組**：`AppLogger` singleton、`LogEntry` 資料類別、`LogTransport` 抽象介面，以及 `ConsoleTransport`（支援 debug emoji / release 純文字格式切換）
- **新增 Flutter FirebaseTransport stub**：預留 Firebase Crashlytics / Analytics 整合點，今日為 no-op
- **Flutter call sites 埋點**：在 `main.dart`、`session_provider`、`poi_provider`、`trigger_provider`、`narration_provider`、`qa_provider` 加入對應的 log 呼叫
- **新增 Backend log_events.py**：定義全棧共用的事件名稱常數（UPPER_SNAKE_CASE）
- **新增 Backend logging_config.py**：`setup_logging()`、`_HumanFormatter`（text 格式）、`_JsonFormatter`（json 格式）、`log_event()` helper
- **Backend AppConfig 擴充**：加入 `LOG_FORMAT` env var，預設 `text`，Cloud Run 設為 `json`
- **Backend call sites 埋點**：在 `overpass.py`、`wikipedia.py`、`poi_service.py`、`api/poi.py`、`narration_service.py`、`qa_service.py` 加入對應的 log 呼叫
- **無新增套件依賴**：Flutter 使用 `dart:developer`，backend 使用 Python stdlib `logging`

## Capabilities

### New Capabilities

- `flutter-app-logger`: Flutter 結構化日誌核心，包含 `AppLogger` singleton、`LogEntry`、`LogTransport` 介面、`ConsoleTransport`（emoji/plain）、`FirebaseTransport` stub，以及所有 provider 的 log call sites
- `backend-structured-logging`: Python backend 結構化日誌，包含 `log_events.py` 常數、`logging_config.py`（formatters + `log_event()` helper）、`AppConfig.log_format` 欄位，以及所有 service/client 的 log call sites

### Modified Capabilities

（無現有 spec 層級的需求變更）

## Impact

- **Flutter**：新增 `flutter_app/lib/shared/logging/` 模組；修改 `main.dart` 及 5 個 provider 檔案（additive，不改變現有行為）；新增 2 個 unit test 檔案
- **Backend**：新增 `backend/src/tour_guide/log_events.py` 和 `logging_config.py`；修改 `config.py`、`main.py`、2 個 client 檔案、4 個 service/api 檔案；新增 `tests/unit/test_logging_config.py`
- **環境變數**：新增 `LOG_FORMAT=text|json`（backend），已更新 `.env.example`
- **依賴項**：無新增 pip 套件或 Flutter package
