## Context

Plan A–E 已完成 AI 導覽 App 的核心功能（地圖、POI 觸發、Gemini 旁白、Persona 切換、Foodie 評分）。目前的限制：

1. **背景定位缺失**：App 離開前景後 geolocator 停止更新，使用者鎖屏時無法收到景點觸發通知。
2. **後端僅限本機**：`backend/` 尚未容器化，無法部署給真機測試或公開展示。
3. **API 無保護**：後端 endpoint 無任何認證機制，部署後等同公開接口。
4. **API Key 安全性**：Google Maps API Key 目前 hardcode 於 `AppDelegate.swift`，不符合安全規範。

Plan F 的目標是補足這四個缺口，使 App 達到可公開展示的完整程度。

**技術現況：**
- Flutter 3.x + Riverpod StateNotifier 架構
- `geolocator` 套件處理定位，`TriggerNotifier` 監聽位置並觸發旁白
- 後端為 Python FastAPI，使用 pydantic-settings 管理環境變數
- `BackendClient` 使用 Dio 發送 HTTP 請求

## Goals / Non-Goals

**Goals:**
- App 鎖屏/背景狀態時，geolocator 持續回報位置，`TriggerNotifier` 改呼叫 `NotificationService` 推送本地通知
- 後端新增 `X-Api-Key` header middleware，`API_KEY` 為空時開發模式自動放行
- 後端容器化（`Dockerfile` + `.dockerignore`），支援 `gcloud builds submit` 部署至 Cloud Run asia-east1
- Google Maps API Key 透過 Android `local.properties` + iOS `xcconfig` 安全注入，不進 git
- `HomeScreen._start()` 在 `whileInUse` 權限時顯示引導 SnackBar
- TDD：先寫測試再實作；後端 195→199+ tests，Flutter 77→79+ tests

**Non-Goals:**
- Push notification（FCM/APNs 遠端推播）：本期僅實作本地通知
- 多使用者認證（JWT/OAuth）：`X-Api-Key` 為單一 shared secret
- 後端水平擴展或 Load Balancer 設定
- iOS App Store 上架流程

## Decisions

### D1：背景定位策略 — geolocator 平台原生設定

**決策：** 依 `Platform.isIOS` 在 `RealLocationService.start()` 注入不同的 `LocationSettings`：
- Android → `AndroidSettings` + `ForegroundNotificationConfig`（前景服務通知）
- iOS → `AppleSettings`（`allowBackgroundLocationUpdates: true`, `activityType: ActivityType.fitness`）

**理由：** geolocator 套件已封裝平台差異；`ForegroundNotificationConfig` 是 Android 背景定位的必要條件（否則系統會終止服務）；`AppleSettings` 讓 iOS 在 `WhenInUse` 授權下仍可背景更新。

**替代方案考慮：**
- `background_location` 套件：API 較簡單但維護不活躍，且需額外 Android service 宣告
- WorkManager（Android）：適合定期批次任務，不適合持續追蹤

---

### D2：前景/背景路由 — `appLifecycleStateProvider`

**決策：** `App` widget 實作 `WidgetsBindingObserver`，將 `AppLifecycleState` 寫入 Riverpod `StateProvider<AppLifecycleState>`。`TriggerNotifier` 讀取此 provider：
- `resumed` → 呼叫 `NarrationNotifier.narrate()`（旁白）
- 其他（`paused`, `inactive`, `detached`, `hidden`）→ 呼叫 `NotificationService.showPoiTrigger(poi)`（本地通知）

**理由：**
- 集中 lifecycle 管理，`TriggerNotifier` 不需直接依賴 `WidgetsBinding`，方便測試（mock provider 即可）
- Riverpod provider 天然具有響應式語義，lifecycle 變化自動觸發相關邏輯

**替代方案考慮：**
- 在 `TriggerNotifier` 內直接呼叫 `WidgetsBinding.instance.lifecycleState`：不可測試，違反 DI 原則

---

### D3：`NotificationService` — Abstract + Fake + Real

**決策：** 定義 `abstract class NotificationService`，提供 `init()` 和 `showPoiTrigger(Poi)` 介面。`RealNotificationService` 封裝 `flutter_local_notifications`；`FakeNotificationService` 用於測試（記錄呼叫）。透過 `notificationServiceProvider` 注入。

**理由：**
- 保持與既有架構一致（`LocationService`, `TtsService`, `BackendClient` 皆為 abstract + Fake + Real）
- 測試不需要實際通知 API，`FakeNotificationService` 讓 widget test 可驗證通知是否觸發

---

### D4：API Key 認證 — Starlette Middleware

**決策：** 在 `main.py` 新增 `@app.middleware("http")` 攔截所有請求，讀取 `X-Api-Key` header。`config.py` 新增 `api_key: str = Field("", alias="API_KEY")`；當 `api_key` 為空字串時，middleware 直接放行（開發模式）。

**理由：**
- FastAPI/Starlette middleware 是最輕量的全局攔截點，無需修改每個路由
- 空字串放行讓本機開發無需設定 `API_KEY`，CI/CD 環境亦可選擇性啟用
- 避免引入 `python-jose` 或 OAuth2 依賴（overkill for shared secret）

---

### D5：容器化策略 — 單一 Dockerfile，多 stage 非必要

**決策：** 使用單一 `FROM python:3.12-slim` 映像，不採用 multi-stage build。`CMD ["uvicorn", ...]` 直接啟動；Cloud Run 透過 `PORT` 環境變數接管 port。

**理由：**
- 後端無需編譯步驟，multi-stage 不帶來顯著收益
- `python:3.12-slim` 比 `alpine` 有更好的套件相容性，減少 build 失敗風險
- Cloud Run 自動注入 `PORT` 環境變數，`uvicorn --host 0.0.0.0 --port $PORT` 即可

---

### D6：Maps API Key 注入策略

**決策：**
- **Android**：`local.properties` 儲存 `MAPS_API_KEY=xxx`，`build.gradle.kts` 讀取後透過 `manifestPlaceholders` 注入 `AndroidManifest.xml`
- **iOS**：`LocalConfig.xcconfig`（不進 git）透過 `#include?` 被 `Debug.xcconfig` / `Release.xcconfig` 引入，`AppDelegate.swift` 改從 `Bundle.main.infoDictionary["MAPS_API_KEY"]` 讀取

**理由：** 符合各平台慣例；`local.properties` 和 `LocalConfig.xcconfig` 是業界標準的本機私密設定檔，`.gitignore` 已有相關規範。

## Risks / Trade-offs

| 風險 | 說明 | 緩解措施 |
|------|------|----------|
| iOS 背景定位電池消耗 | `allowBackgroundLocationUpdates: true` 持續接收 GPS 更新 | 使用 `distanceFilter` 限制更新頻率，目前為 10m |
| Android 前景服務通知無法關閉 | `ForegroundNotificationConfig` 會常駐通知列 | 通知說明清楚用途；未來版本可改用 `priority: min` 隱藏 |
| Cloud Run cold start | 首次請求約 2–5 秒延遲 | 設定 `--min-instances=1`（`deploy-backend.sh` 可選參數） |
| `X-Api-Key` shared secret 洩漏 | 單一 key 一旦外洩需立即輪換 | 透過 GCP Secret Manager 管理，`deploy-backend.sh` 從 secret 注入 |
| `flutter_local_notifications` v17 API 變動 | 版本升級可能有 breaking change | Pin 至 `^17.2.4`，並建立完整測試覆蓋 |
| iOS 模擬器無法測試背景通知 | 模擬器不支援真實 lifecycle 背景 | 於實體機驗證；`FakeNotificationService` 覆蓋單元測試 |

## Migration Plan

### 部署步驟

1. **本機準備**
   - `flutter_app/android/local.properties` 新增 `MAPS_API_KEY=<key>`
   - `flutter_app/ios/Flutter/LocalConfig.xcconfig` 新增 `MAPS_API_KEY_IOS=<key>`

2. **後端部署**
   ```bash
   ./scripts/setup-gcp.sh   # 首次：建立 GCP 專案、啟用 API、建立 Secret
   ./scripts/deploy-backend.sh  # 建置 Docker 映像並部署至 Cloud Run
   ```

3. **Flutter 設定**
   - `flutter_app/dart_defines/prod.json` 新增 `BACKEND_URL` 和 `API_KEY`
   - 建置：`flutter run --dart-define-from-file=dart_defines/prod.json`

4. **驗證**
   - 後端：`curl -H "X-Api-Key: <key>" <cloud-run-url>/healthz`
   - Flutter：背景狀態下走近 POI，確認收到本地通知

### Rollback 策略

- Cloud Run 自動保留前一版本，執行 `gcloud run services update-traffic` 可立即切回
- `API_KEY` 空字串即可停用 middleware，不影響現有流程

## Open Questions

1. **Android 前景服務通知 icon**：`ForegroundNotificationConfig` 需要指定 notificationIcon，目前計畫用 App icon (`@mipmap/ic_launcher`)，是否需要另外設計專用小圖示？（預計實作時決定）
2. **Cloud Run region**：目前設定 `asia-east1`（台灣最近），如有其他使用者分布需求，是否要調整？（目前 OK）
3. **`--min-instances` 預設值**：`deploy-backend.sh` 預設 `0`（省錢），展示時需手動設 `1`，是否加進 script 參數？（預計加入 `--min-instances` flag）
