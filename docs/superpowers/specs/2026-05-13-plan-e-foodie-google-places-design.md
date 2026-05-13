# Plan E — 食家 persona + Google Places 設計文件

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-05-13 |
| 適用範圍 | Plan E：食家 persona 接 Google Places，Flutter 觸發半徑 per-persona |
| 前置計畫 | Plan D（Push-to-talk Q&A，已完成） |
| 後續計畫 | Plan F（背景定位 + 部署上線） |

---

## 1. 目標

將食家（foodie）persona 從 Plan C 的 osm_wikipedia 佔位，切換為真正的 Google Places 餐廳資料來源：

1. **後端**：新增 `GooglePlacesClient`（真實 + Fake）、`FoodieFilter` 純函式、`POIService` persona routing
2. **Flutter**：`POI` model 擴充食家欄位、`TriggerNotifier` 讀 per-persona 觸發半徑、`NarrationSheet` 顯示星評列

---

## 2. 範圍

### In Scope
- 後端 GooglePlacesClient（Protocol + Real + Fake 三層）
- 後端 FoodieFilter（評分過濾 + 用餐時段加權）
- POIService persona routing（foodie → Google Places，其他不動）
- POI model 擴充（後端 + Flutter）
- Flutter TriggerNotifier 讀 persona default_trigger_radius_m
- Flutter NarrationSheet 食家星評資訊列
- foodie.yaml 更新（poi_source + default_trigger_radius_m）
- PersonaConfig / PersonaInfo 加 default_trigger_radius_m

### Out of Scope（留 Plan F）
- Places Photos 圖片顯示
- Settings UI per-persona 半徑覆蓋（settings_persona_overrides）
- 食家 narration prompt 優化（現有 prompt 已可用）
- 部署 / Cloud Run

---

## 3. 後端架構

### 3.1 新增 / 修改模組

```
backend/src/tour_guide/
├── clients/
│   └── google_places.py          ← 新增
├── services/
│   ├── poi_service.py            ← 修改：加 persona routing
│   └── foodie_filter.py          ← 新增
├── models/
│   └── poi.py                    ← 修改：加 Place dataclass
└── config.py                     ← 修改：加 GOOGLE_PLACES_API_KEY（optional）
backend/prompts/personas/
└── foodie.yaml                   ← 修改：poi_source + default_trigger_radius_m
backend/src/tour_guide/models/
└── persona.py                    ← 修改：PersonaConfig 加 default_trigger_radius_m
backend/src/tour_guide/prompts/
└── loader.py                     ← 修改：解析 default_trigger_radius_m
backend/src/tour_guide/main.py    ← 修改：wiring GooglePlacesClient
```

### 3.2 GooglePlacesClient

**Protocol**：
```python
class GooglePlacesClient(Protocol):
    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]: ...
```

**RealGooglePlacesClient**：
- 呼叫 Places API (New) Nearby Search
- `includedTypes: ["restaurant", "cafe", "bakery"]`
- 回傳欄位：`id`, `displayName`, `location`, `rating`, `userRatingCount`, `priceLevel`, `types`, `formattedAddress`
- Retry：指數退避 1s/2s/4s，429 → 拋 `GooglePlacesRateLimitError`

**FakeGooglePlacesClient**：
- 建構子接收 `scripted_places: list[Place]`
- `nearby_restaurants()` 直接回傳，不打網路

**AppConfig**：
```python
google_places_api_key: str = Field("", alias="GOOGLE_PLACES_API_KEY")
```
`main.py` 判斷：`config.google_places_api_key` 非空 → `RealGooglePlacesClient`；空 → `FakeGooglePlacesClient`（回傳空列表）。

### 3.3 Place model

```python
@dataclass
class Place:
    id: str                          # "gplace:{place_id}"
    name: str
    lat: float
    lon: float
    rating: float | None
    user_ratings_total: int | None
    price_level: int | None          # 1-4，null 表示無資訊
    types: list[str]                 # e.g. ["restaurant", "food"]
    vicinity: str                    # 地址
```

### 3.4 FoodieFilter（純函式）

```python
def filter_places(
    places: list[Place],
    current_hour: int,               # 0-23，注入便於測試
) -> list[Place]:
```

**過濾規則**：
- `rating` 或 `user_ratings_total` 為 None → 排除
- 用餐時段（11 ≤ hour < 14 或 17 ≤ hour < 21）：`rating ≥ 4.0` AND `user_ratings_total ≥ 30`
- 其他時段：`rating ≥ 4.3` AND `user_ratings_total ≥ 50`

### 3.5 POIService persona routing

```python
async def nearby(self, lat, lon, radius, persona, lang) -> list[POI]:
    if persona == "foodie":
        import datetime
        hour = datetime.datetime.now().hour
        places = await self._google_places.nearby_restaurants(lat, lon, radius)
        filtered = filter_places(places, hour)
        pois = [_place_to_poi(p, lat, lon) for p in filtered]
        pois.sort(key=lambda p: p.distance_m)
        return pois
    else:
        # 現有 Overpass + Wikipedia 路徑（不動）
        ...
```

Cache key 食家用 `region:foodie:{lat:.3f}:{lon:.3f}:{radius}`，與一般 POI cache 分開。

### 3.6 /poi/nearby 回應格式（食家）

```json
{
  "id": "gplace:ChIJ...",
  "name": "鼎泰豐（信義店）",
  "lat": 25.033,
  "lon": 121.564,
  "tags": {},
  "wiki": null,
  "distance_m": 47.3,
  "confidence": "high",
  "rating": 4.6,
  "user_ratings_total": 328,
  "price_level": 2,
  "place_types": ["restaurant", "food"],
  "vicinity": "信義區松高路12號"
}
```

非食家 POI 不含上述 foodie-specific 欄位（後端不輸出）。

### 3.7 Confidence 判定（食家）

| 等級 | 規則 |
|---|---|
| `high` | rating ≥ 4.5 AND user_ratings_total ≥ 100 |
| `medium` | rating 4.3–4.5 OR user_ratings_total 50–100 |
| `low` | 通過 FoodieFilter 但剛好邊界（理論上不應出現） |

`ConfidenceClassifier.classify()` 新增食家分支（依 `Place` 欄位判斷）。

---

## 4. Flutter 端

### 4.1 修改 / 新增模組

```
flutter_app/lib/
├── shared/backend/models/
│   └── poi.dart                          ← 修改：加 foodie nullable 欄位
├── features/session/
│   └── persona_data.dart                 ← 修改：PersonaInfo 加 defaultTriggerRadiusM
├── features/narration/
│   ├── providers/trigger_provider.dart   ← 修改：讀 persona 觸發半徑
│   └── widgets/narration_sheet.dart      ← 修改：加星評列
```

### 4.2 POI model 擴充

```dart
class POI {
  // 現有欄位不動

  // foodie only — null for non-foodie POIs
  final double? rating;
  final int? userRatingsTotal;
  final int? priceLevel;
  final List<String>? placeTypes;
  final String? vicinity;
}
```

`fromJson` 新增：
```dart
rating: (json['rating'] as num?)?.toDouble(),
userRatingsTotal: json['user_ratings_total'] as int?,
priceLevel: json['price_level'] as int?,
placeTypes: (json['place_types'] as List<dynamic>?)?.cast<String>(),
vicinity: json['vicinity'] as String?,
```

### 4.3 PersonaInfo 觸發半徑

`persona_data.dart` 的 `PersonaInfo` 加欄位：
```dart
final int defaultTriggerRadiusM;
```

`kPersonas` 常數更新：
- `foodie`：`defaultTriggerRadiusM: 50`
- 其他 4 個 persona：`defaultTriggerRadiusM: 100`

### 4.4 TriggerNotifier 半徑讀取

`trigger_provider.dart` 中，現有寫死的 `100` 改為讀 session 的 persona：

```dart
final persona = ref.watch(sessionProvider).persona;  // PersonaInfo
final triggerRadiusM = persona.defaultTriggerRadiusM;
```

在 `TriggerEngine.evaluate()` 呼叫時傳入此半徑。

### 4.5 NarrationSheet 食家星評列

在旁白 sheet 中，若 `poi.rating != null` 顯示：

```
⭐ 4.6  (328 則評論)  $$
```

`priceLevel` 轉換：`1=$`, `2=$$`, `3=$$$`, `4=$$$$`, null 不顯示。

實作：NarrationSheet 底部加 `_FoodieRatingBar` 私有 widget，null rating 時回傳 `SizedBox.shrink()`。

---

## 5. YAML 更新

### foodie.yaml

```yaml
poi_source: google_places          # 從 osm_wikipedia 改
default_trigger_radius_m: 50       # 新增
```

### PersonaConfig（backend/models/persona.py）

```python
@dataclass
class PersonaConfig:
    # 現有欄位 ...
    default_trigger_radius_m: int = 100  # foodie: 50, others: 100
```

`PersonaLoader._parse()` 解析：
```python
default_trigger_radius_m=int(data.get("default_trigger_radius_m", 100)),
```

---

## 6. 測試策略

### 後端（新增測試）

| 測試 | 內容 |
|---|---|
| `test_foodie_filter_normal_hours` | 一般時段：rating < 4.3 的被排除 |
| `test_foodie_filter_meal_hours` | 11–13 點：rating ≥ 4.0 / 30 評論通過 |
| `test_foodie_filter_none_rating` | rating=None → 排除 |
| `test_fake_google_places_client` | scripted 資料正確回傳 |
| `test_poi_service_routing_foodie` | persona=foodie → 呼叫 GooglePlaces（spy） |
| `test_poi_service_routing_other` | persona=history_uncle → 呼叫 Overpass（spy） |
| `test_poi_nearby_foodie_response` | integration：回應含 rating / user_ratings_total |
| `test_poi_nearby_non_foodie_response` | integration：回應不含 rating 欄位 |

### Flutter（新增測試）

| 測試 | 內容 |
|---|---|
| `poi_fromJson_foodie_fields` | rating/userRatingsTotal 正確解析 |
| `poi_fromJson_non_foodie` | 非食家 POI，foodie 欄位為 null |
| `trigger_notifier_foodie_radius` | persona=foodie → threshold 50m |
| `trigger_notifier_default_radius` | persona=history_uncle → threshold 100m |
| `narration_sheet_shows_rating` | rating != null → 顯示星評列 |
| `narration_sheet_hides_rating` | rating == null → 不顯示 |

---

## 7. 關鍵設計決策

| 決策 | 選擇 | 理由 |
|---|---|---|
| API client 實作 | Protocol + Real + Fake | 測試完全離線；env var 切換 |
| 餐廳過濾位置 | 獨立 FoodieFilter 純函式 | 與現有 filter_poi_nodes 一致；純函式易 TDD |
| foodie 欄位位置 | POI 加 nullable 欄位 | 最簡單；無 Dart 子類別複雜度 |
| 觸發半徑來源 | persona YAML + PersonaInfo 常數 | YAML 是 source of truth；Flutter 常數同步 |
| Places 圖片 | 不做（Plan F） | YAGNI；部署後流量才值得處理 |
| Settings 半徑覆蓋 | 不做（Plan F） | Drift schema 修改工時不符合 MVP 效益 |

---

## 8. 完成條件

- [ ] 後端：`pytest` 全部通過（含新增測試）
- [ ] 後端：`ruff check src/` 乾淨
- [ ] Flutter：`flutter test` 全部通過（含新增測試）
- [ ] Flutter：`flutter analyze` 無 error/warning
- [ ] `persona=foodie` + Fake client：`/poi/nearby` 回應含 rating 欄位
- [ ] `persona=history_uncle`：`/poi/nearby` 回應不含 rating 欄位
- [ ] Flutter foodie persona：TriggerNotifier 使用 50m 閾值
- [ ] NarrationSheet：有 rating 顯示星評列，無 rating 不顯示

---

*— Plan E 設計文件結束 —*
