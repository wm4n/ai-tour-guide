## Context

Plan D（Push-to-talk Q&A）已完成。食家（foodie）persona 目前使用 `osm_wikipedia` 作為 POI 來源，僅回傳通用景點資料，無法提供餐廳評分、價位等食家所需資訊。

本 change 目標是將食家 persona 切換到 Google Places 真實餐廳資料：

- **後端現況**：`POIService.nearby()` 無 persona routing，所有 persona 都走 Overpass + Wikipedia pipeline
- **Flutter 現況**：`TriggerNotifier` 寫死 100m 觸發半徑；`NarrationSheet` 無食家專屬 UI；`PersonaInfo` 無觸發半徑欄位
- **限制**：Google Places API Key 為可選（空值時使用 Fake client），不影響其他 persona 的功能

## Goals / Non-Goals

**Goals:**
- 後端新增 `GooglePlacesClient`（Protocol + Real + Fake），依 `GOOGLE_PLACES_API_KEY` 切換
- 後端新增 `FoodieFilter` 純函式，依用餐時段套用不同評分門檻
- `POIService` 加入 persona routing：`foodie` → Google Places；其他 → Overpass pipeline（不動）
- `POI` dataclass（後端 + Flutter）加入 nullable foodie 欄位（`rating`、`user_ratings_total`、`price_level`、`place_types`、`vicinity`）
- `api/poi.py` 條件性輸出 foodie 欄位（非食家 POI 不輸出多餘欄位）
- `ConfidenceClassifier` 新增 `classify_place()` 分支
- `foodie.yaml` 更新 `poi_source`、新增 `default_trigger_radius_m: 50`
- Flutter `TriggerNotifier` 從 `kPersonas` 讀 per-persona 觸發半徑
- Flutter `NarrationSheet` 顯示食家星評列（`_FoodieRatingBar` widget）

**Non-Goals:**
- Places Photos 圖片顯示（Plan F）
- Settings UI per-persona 半徑覆蓋（Plan F，需 Drift schema 修改）
- 食家 narration prompt 優化（現有 prompt 已可用）
- 部署 / Cloud Run（Plan F）

## Decisions

### 決策一：GooglePlacesClient 採 Protocol + Real + Fake 三層架構

**選擇**：定義 `GooglePlacesClient` Protocol，搭配 `RealGooglePlacesClient` 和 `FakeGooglePlacesClient`。

**理由**：
- 與現有 `OverpassClient`、`WikipediaClient` 一致，維持架構慣例
- 測試完全離線，`FakeGooglePlacesClient` 接受 `scripted_places` 注入
- `main.py` 依 `config.google_places_api_key` 非空與否決定使用哪個實作

**棄選方案**：直接 mock httpx — 測試耦合到 HTTP 層，難以維護。

---

### 決策二：FoodieFilter 為獨立純函式，非 POIService 方法

**選擇**：`filter_places(places, current_hour)` 放在獨立的 `foodie_filter.py` 模組。

**理由**：
- 與現有 `filter_poi_nodes()` 純函式設計一致
- `current_hour` 參數注入便於 TDD，不依賴系統時間
- 易於單獨測試，不需建立完整 `POIService`

---

### 決策三：foodie 欄位加在 POI 作為 nullable fields，而非子類別

**選擇**：`POI` dataclass 直接加 `rating: float | None`、`price_level: int | None` 等欄位（預設 None）。

**理由**：
- Dart 沒有 sealed class，子類別模式複雜度高
- Python dataclass 不鼓勵繼承，nullable fields 更簡單
- API 序列化只需判斷 `if p.rating is not None` 條件性輸出

**棄選方案**：`FoodiePOI` 子類別 — 兩端都需要 type narrowing，增加複雜度。

---

### 決策四：觸發半徑來源為 persona YAML + Flutter kPersonas 常數

**選擇**：YAML 存 `default_trigger_radius_m`（後端 source of truth）；Flutter `kPersonas` 同步硬碼對應值。

**理由**：
- 避免 Flutter 在 session 啟動時額外 API call 取半徑
- `kPersonas` 已是 persona 相關 UI 資料的集中地，加欄位自然
- 設計上 Flutter 為 offline-first，半徑寫死在 client 可接受

**棄選方案**：`/persona/list` API 回傳半徑 — 增加 API 複雜度且 session 啟動多一次 RTT。

---

### 決策五：foodie cache key 與一般 POI 分開

**選擇**：`region:foodie:{lat:.3f}:{lon:.3f}:{radius}` vs 一般的 `region:{lat:.3f}:{lon:.3f}:{radius}:{lang}`。

**理由**：
- 避免食家和非食家 POI 互相污染 cache
- 食家 POI 不含 `wiki` 欄位，cache 格式不同

## Risks / Trade-offs

- **[風險] Google Places API 費用** → Mitigation：`FakeGooglePlacesClient` 為預設（API Key 不存在時），開發和測試不產生費用；生產環境依實際流量評估
- **[風險] Places API 回傳格式變動** → Mitigation：`_parse_place()` 集中在 `google_places.py`，修改面積小
- **[風險] Flutter kPersonas 與 YAML 不同步** → Mitigation：`defaultTriggerRadiusM` 為 Plan F 的 Settings 覆蓋前的預設值，兩邊設定一致且簡單；可在 CI 加 snapshot test 驗證
- **[Trade-off] POI nullable fields 增加 None 檢查** → 接受：比子類別方案簡單；現有 code 處理 `wiki: WikiArticle | None` 已有先例
- **[Trade-off] 用餐時段降低評分門檻（4.0/30）** → 接受：鼓勵使用者在用餐時探索，若評分偏低可在 Plan F 調整

## Migration Plan

1. **後端**：照 Task 1–8 順序依序 commit，每個 task 有獨立 commit，CI 綠燈才合併
2. **Flutter**：Task 9–12 依序，每個 task 有 test 先行
3. **無需 DB migration**：foodie 欄位為可選，不影響現有 Drift schema
4. **Rollback**：feature flag 不在此 plan 範圍；若問題嚴重，`git revert` 對應 commit 即可（foodie routing 為 `if persona == "foodie"` 條件，影響範圍明確）
5. **環境變數**：`GOOGLE_PLACES_API_KEY` 新增為可選，現有部署不需立即設定

## Open Questions

- （已解決）Places Photos：確認 Plan F 處理，此 plan 不做
- （已解決）Settings 半徑覆蓋：確認 Plan F 處理，Drift schema 修改留後
- （開放）foodie 過濾門檻是否需要 A/B testing？→ 目前先用設計文件的固定值，待上線後看資料
