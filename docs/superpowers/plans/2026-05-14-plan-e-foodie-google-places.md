# Plan E — 食家 persona + Google Places 實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將食家 persona 從 osm_wikipedia 佔位切換為 Google Places 真實餐廳資料，並讓 Flutter TriggerNotifier 依 persona 讀取正確觸發半徑（foodie = 50m）。

**Architecture:** 後端新增 `GooglePlacesClient`（Protocol + Real + Fake）和 `FoodieFilter` 純函式；`POIService` 依 persona 路由到 Google Places 或現有 Overpass pipeline。Flutter `POI` model 加 nullable foodie 欄位；`TriggerNotifier` 從 `kPersonas` 讀 `defaultTriggerRadiusM` 傳入 `TriggerEngine.evaluate()`。

**Tech Stack:** Python 3.12 / FastAPI / httpx / pytest（後端）；Flutter 3.x / Dart 3.x / Riverpod（前端）

---

## 檔案索引

### 後端（新增）
| 檔案 | 用途 |
|---|---|
| `backend/src/tour_guide/clients/google_places.py` | `GooglePlacesClient` Protocol + `RealGooglePlacesClient` + `FakeGooglePlacesClient` |
| `backend/src/tour_guide/services/foodie_filter.py` | 純函式 `filter_places(places, current_hour)` |
| `backend/tests/unit/test_foodie_filter.py` | FoodieFilter 單元測試 |
| `backend/tests/unit/test_google_places_client.py` | FakeGooglePlacesClient 單元測試 |

### 後端（修改）
| 檔案 | 變動 |
|---|---|
| `backend/src/tour_guide/models/poi.py` | 加 `Place` dataclass；`POI` 加 foodie nullable 欄位 |
| `backend/src/tour_guide/models/persona.py` | `PersonaConfig` 加 `default_trigger_radius_m: int = 100` |
| `backend/src/tour_guide/prompts/loader.py` | `_parse()` 解析 `default_trigger_radius_m` |
| `backend/prompts/personas/foodie.yaml` | `poi_source: google_places`；加 `default_trigger_radius_m: 50` |
| `backend/src/tour_guide/config.py` | 加 `GOOGLE_PLACES_API_KEY`（空字串 default） |
| `backend/src/tour_guide/services/confidence.py` | 加 `classify_place(place: Place)` static method |
| `backend/src/tour_guide/services/poi_service.py` | 加 `google_places` 可選參數；persona routing；`_place_to_poi` helper |
| `backend/src/tour_guide/api/poi.py` | POI 回應條件性包含 foodie 欄位 |
| `backend/src/tour_guide/main.py` | wiring `GooglePlacesClient` |
| `backend/tests/unit/test_confidence.py` | 加 `classify_place` 測試 |
| `backend/tests/integration/test_poi_service.py` | 加 foodie routing 測試 |
| `backend/tests/integration/test_poi_api.py` | 加 foodie response 測試 |

### Flutter（修改）
| 檔案 | 變動 |
|---|---|
| `flutter_app/lib/shared/backend/models/poi.dart` | 加 nullable foodie 欄位 |
| `flutter_app/lib/features/session/persona_data.dart` | `PersonaInfo` 加 `defaultTriggerRadiusM`；`kPersonas` 更新 |
| `flutter_app/lib/features/narration/providers/trigger_provider.dart` | 讀 persona `defaultTriggerRadiusM` 傳入 `TriggerEngine` |
| `flutter_app/lib/features/narration/widgets/narration_sheet.dart` | 加 `_FoodieRatingBar` private widget |
| `flutter_app/test/unit/models_test.dart` | 加 foodie POI 解析測試 |
| `flutter_app/test/unit/trigger_engine_test.dart` | 加 custom radiusM 測試 |
| `flutter_app/test/widget/narration_sheet_test.dart` | 加 NarrationSheet 星評列測試 |

---

## Task 1：後端 — 模型擴充（Place + POI foodie 欄位 + PersonaConfig）

**Files:**
- Modify: `backend/src/tour_guide/models/poi.py`
- Modify: `backend/src/tour_guide/models/persona.py`
- Test: `backend/tests/unit/test_poi_models.py` (新增測試，若無此檔則建立)

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/unit/test_poi_models.py` 末尾加入（若檔案不存在則建立）：

```python
"""Tests for POI and Place models."""

from tour_guide.models.poi import Place


class TestPlaceModel:
    def test_place_has_required_fields(self):
        place = Place(
            id="gplace:ChIJ123",
            name="鼎泰豐",
            lat=25.033,
            lon=121.564,
            rating=4.6,
            user_ratings_total=328,
            price_level=2,
            types=["restaurant", "food"],
            vicinity="信義區松高路12號",
        )
        assert place.id == "gplace:ChIJ123"
        assert place.rating == 4.6
        assert place.price_level == 2

    def test_place_nullable_fields(self):
        place = Place(
            id="gplace:abc",
            name="無評分餐廳",
            lat=25.0,
            lon=121.0,
            rating=None,
            user_ratings_total=None,
            price_level=None,
            types=["restaurant"],
            vicinity="台北市",
        )
        assert place.rating is None
        assert place.user_ratings_total is None
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_poi_models.py -v
```

預期：`ImportError: cannot import name 'Place' from 'tour_guide.models.poi'`

- [ ] **Step 3: 實作 Place dataclass + POI foodie 欄位**

編輯 `backend/src/tour_guide/models/poi.py`，完整內容替換為：

```python
from dataclasses import dataclass, field


@dataclass
class OsmNode:
    id: str  # e.g. "osm:node:12345"
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class WikiArticle:
    title: str
    extract: str  # intro text
    url: str
    lang: str


@dataclass
class POIContext:
    osm: OsmNode
    wiki: WikiArticle | None = None


@dataclass
class Place:
    id: str                          # "gplace:{place_id}"
    name: str
    lat: float
    lon: float
    rating: float | None
    user_ratings_total: int | None
    price_level: int | None          # 1-4, None if unknown
    types: list[str]
    vicinity: str


@dataclass
class POI:
    id: str
    name: str
    lat: float
    lon: float
    tags: dict[str, str] = field(default_factory=dict)
    wiki: WikiArticle | None = None
    distance_m: float = 0.0
    confidence: str = "low"          # "high" | "medium" | "low"
    # foodie-only fields (None for non-foodie POIs)
    rating: float | None = None
    user_ratings_total: int | None = None
    price_level: int | None = None
    place_types: list[str] | None = None
    vicinity: str | None = None


@dataclass
class BBox:
    min_lat: float
    min_lon: float
    max_lat: float
    max_lon: float


@dataclass
class TagFilter:
    key: str
    values: list[str] = field(default_factory=list)  # empty = any value
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_poi_models.py -v
```

預期：全部 PASS

- [ ] **Step 5: 加 PersonaConfig.default_trigger_radius_m**

編輯 `backend/src/tour_guide/models/persona.py`，在 `PersonaConfig` dataclass 末尾加欄位：

```python
@dataclass
class PersonaConfig:
    id: str
    display_name: dict[str, str]
    voice: dict[str, str]
    voice_style: VoiceStyle
    style_profile: StyleProfile
    poi_source: str
    system_prompt: dict[str, str]
    narration_template: dict[str, str]
    qa_template: dict[str, str]
    system_messages: dict[str, Any] = field(default_factory=dict)
    confidence_labels: dict[str, Any] = field(default_factory=dict)
    default_trigger_radius_m: int = 100  # foodie: 50, others: 100
```

- [ ] **Step 6: 跑全後端測試確認未破壞**

```bash
cd backend && .venv/bin/pytest -v
```

預期：全部 PASS（現有測試不應受影響）

- [ ] **Step 7: Commit**

```bash
git add backend/src/tour_guide/models/poi.py \
        backend/src/tour_guide/models/persona.py \
        backend/tests/unit/test_poi_models.py
git commit -m "feat(backend): add Place model and foodie fields to POI + PersonaConfig"
```

---

## Task 2：後端 — PersonaLoader + foodie.yaml 更新

**Files:**
- Modify: `backend/src/tour_guide/prompts/loader.py`
- Modify: `backend/prompts/personas/foodie.yaml`
- Test: `backend/tests/unit/test_persona_loader.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/unit/test_persona_loader.py` 找到任一現有測試 class，在其後加入：

```python
class TestPersonaLoaderDefaultTriggerRadius:
    def test_foodie_has_50m_trigger_radius(self, tmp_path):
        """foodie persona YAML with default_trigger_radius_m: 50 should parse correctly."""
        yaml_content = """
id: foodie_test
display_name:
  zh-TW: 測試美食家
voice:
  zh-TW: Leda
voice_style:
  speaking_rate: 1.0
  emotion: warm
style_profile:
  embellishment: 0.4
  preferred_topics:
    - food
poi_source: google_places
default_trigger_radius_m: 50
system_prompt:
  zh-TW: 你是美食家
narration_template:
  zh-TW: 介紹 {poi_name}
qa_template:
  zh-TW: 回答問題
"""
        yaml_file = tmp_path / "foodie_test.yaml"
        yaml_file.write_text(yaml_content)
        from tour_guide.prompts.loader import PersonaLoader
        config = PersonaLoader.load_from_path(yaml_file)
        assert config.default_trigger_radius_m == 50

    def test_persona_without_radius_defaults_to_100(self, tmp_path):
        """Persona YAML without default_trigger_radius_m should default to 100."""
        yaml_content = """
id: no_radius_test
display_name:
  zh-TW: 無半徑
voice:
  zh-TW: Charon
voice_style:
  speaking_rate: 1.0
  emotion: neutral
style_profile:
  embellishment: 0.1
  preferred_topics:
    - history
poi_source: osm_wikipedia
system_prompt:
  zh-TW: 你是歷史大叔
narration_template:
  zh-TW: 介紹 {poi_name}
qa_template:
  zh-TW: 回答問題
"""
        yaml_file = tmp_path / "no_radius_test.yaml"
        yaml_file.write_text(yaml_content)
        from tour_guide.prompts.loader import PersonaLoader
        config = PersonaLoader.load_from_path(yaml_file)
        assert config.default_trigger_radius_m == 100
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestPersonaLoaderDefaultTriggerRadius -v
```

預期：FAIL（`config.default_trigger_radius_m` 不存在或值錯誤）

- [ ] **Step 3: 更新 PersonaLoader 解析邏輯**

編輯 `backend/src/tour_guide/prompts/loader.py`，在 `_parse()` 函式的 `return PersonaConfig(...)` 之前加入解析，並在 `return` 中加入新欄位。找到：

```python
    return PersonaConfig(
        id=data["id"],
        display_name=dict(data["display_name"]),
        voice=dict(data["voice"]),
        voice_style=voice_style,
        style_profile=style_profile,
        poi_source=str(data["poi_source"]),
        system_prompt=dict(data["system_prompt"]),
        narration_template=dict(data["narration_template"]),
        qa_template=dict(data["qa_template"]),
        system_messages=dict(data.get("system_messages") or {}),
        confidence_labels=dict(data.get("confidence_labels") or {}),
    )
```

替換為：

```python
    return PersonaConfig(
        id=data["id"],
        display_name=dict(data["display_name"]),
        voice=dict(data["voice"]),
        voice_style=voice_style,
        style_profile=style_profile,
        poi_source=str(data["poi_source"]),
        system_prompt=dict(data["system_prompt"]),
        narration_template=dict(data["narration_template"]),
        qa_template=dict(data["qa_template"]),
        system_messages=dict(data.get("system_messages") or {}),
        confidence_labels=dict(data.get("confidence_labels") or {}),
        default_trigger_radius_m=int(data.get("default_trigger_radius_m", 100)),
    )
```

- [ ] **Step 4: 更新 foodie.yaml**

編輯 `backend/prompts/personas/foodie.yaml`，在 `poi_source:` 行之後加入（並修改 poi_source 值）：

找到：
```yaml
poi_source: osm_wikipedia
```

替換為：
```yaml
poi_source: google_places
default_trigger_radius_m: 50
```

- [ ] **Step 5: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py -v
```

預期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/prompts/loader.py \
        backend/prompts/personas/foodie.yaml \
        backend/tests/unit/test_persona_loader.py
git commit -m "feat(backend): parse default_trigger_radius_m in PersonaLoader; foodie YAML → google_places"
```

---

## Task 3：後端 — AppConfig + GooglePlacesClient（Protocol + Fake）

**Files:**
- Modify: `backend/src/tour_guide/config.py`
- Create: `backend/src/tour_guide/clients/google_places.py`
- Create: `backend/tests/unit/test_google_places_client.py`

- [ ] **Step 1: 寫失敗測試**

建立 `backend/tests/unit/test_google_places_client.py`：

```python
"""Tests for GooglePlacesClient: FakeGooglePlacesClient behaviour."""

import pytest

from tour_guide.clients.google_places import FakeGooglePlacesClient
from tour_guide.models.poi import Place


@pytest.fixture()
def sample_places():
    return [
        Place(
            id="gplace:ChIJ001",
            name="鼎泰豐",
            lat=25.033,
            lon=121.564,
            rating=4.6,
            user_ratings_total=328,
            price_level=2,
            types=["restaurant", "food"],
            vicinity="信義區松高路12號",
        ),
        Place(
            id="gplace:ChIJ002",
            name="阜杭豆漿",
            lat=25.045,
            lon=121.530,
            rating=4.8,
            user_ratings_total=1200,
            price_level=1,
            types=["restaurant", "cafe"],
            vicinity="忠孝東路一段108號",
        ),
    ]


class TestFakeGooglePlacesClient:
    async def test_returns_scripted_places(self, sample_places):
        """FakeGooglePlacesClient returns the scripted list unchanged."""
        client = FakeGooglePlacesClient(scripted_places=sample_places)
        result = await client.nearby_restaurants(25.033, 121.564, 500)
        assert result == sample_places

    async def test_empty_scripted_places(self):
        """FakeGooglePlacesClient with empty list returns empty list."""
        client = FakeGooglePlacesClient(scripted_places=[])
        result = await client.nearby_restaurants(25.0, 121.0, 500)
        assert result == []
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_google_places_client.py -v
```

預期：`ImportError: cannot import name 'FakeGooglePlacesClient'`

- [ ] **Step 3: 建立 GooglePlacesClient**

建立 `backend/src/tour_guide/clients/google_places.py`：

```python
"""Google Places API client: Protocol + Real + Fake implementations."""

from typing import Protocol

from tour_guide.models.poi import Place


class GooglePlacesClient(Protocol):
    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]: ...


class FakeGooglePlacesClient:
    """In-memory fake for tests and no-API-key environments."""

    def __init__(self, scripted_places: list[Place]) -> None:
        self._places = scripted_places

    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]:
        return self._places


_PRICE_LEVEL_MAP: dict[str, int] = {
    "PRICE_LEVEL_INEXPENSIVE": 1,
    "PRICE_LEVEL_MODERATE": 2,
    "PRICE_LEVEL_EXPENSIVE": 3,
    "PRICE_LEVEL_VERY_EXPENSIVE": 4,
}

_NEARBY_SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
_FIELD_MASK = (
    "places.id,places.displayName,places.location,"
    "places.rating,places.userRatingCount,places.priceLevel,"
    "places.types,places.formattedAddress"
)


class RealGooglePlacesClient:
    """Calls the Google Places API (New) Nearby Search."""

    def __init__(self, api_key: str) -> None:
        import httpx
        self._api_key = api_key
        self._client = httpx.AsyncClient()

    async def nearby_restaurants(
        self, lat: float, lon: float, radius_m: int
    ) -> list[Place]:
        import asyncio

        payload = {
            "includedTypes": ["restaurant", "cafe", "bakery"],
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lon},
                    "radius": float(radius_m),
                }
            },
        }
        headers = {
            "X-Goog-Api-Key": self._api_key,
            "X-Goog-FieldMask": _FIELD_MASK,
            "Content-Type": "application/json",
        }

        backoff = [1, 2, 4]
        last_exc: Exception | None = None

        for wait in [*backoff, None]:
            try:
                resp = await self._client.post(
                    _NEARBY_SEARCH_URL, json=payload, headers=headers
                )
                if resp.status_code == 429:
                    raise GooglePlacesRateLimitError()
                resp.raise_for_status()
                data = resp.json()
                return [_parse_place(p) for p in data.get("places", [])]
            except GooglePlacesRateLimitError:
                raise
            except Exception as e:
                last_exc = e
                if wait is not None:
                    await asyncio.sleep(wait)

        raise last_exc  # type: ignore[misc]


class GooglePlacesRateLimitError(Exception):
    pass


def _parse_place(data: dict) -> Place:
    price_str = data.get("priceLevel", "")
    return Place(
        id=f"gplace:{data['id']}",
        name=data.get("displayName", {}).get("text", ""),
        lat=data["location"]["latitude"],
        lon=data["location"]["longitude"],
        rating=data.get("rating"),
        user_ratings_total=data.get("userRatingCount"),
        price_level=_PRICE_LEVEL_MAP.get(price_str),
        types=data.get("types", []),
        vicinity=data.get("formattedAddress", ""),
    )
```

- [ ] **Step 4: 更新 AppConfig 加 GOOGLE_PLACES_API_KEY**

編輯 `backend/src/tour_guide/config.py`，加入新欄位（在 `log_level` 之前）：

```python
    google_places_api_key: str = Field("", alias="GOOGLE_PLACES_API_KEY")
```

完整 config.py：

```python
"""Configuration for the Tour Guide backend."""

from pydantic import Field
from pydantic_settings import BaseSettings


class AppConfig(BaseSettings):
    """Application configuration loaded from environment variables."""

    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    host: str = Field("0.0.0.0", alias="HOST")  # noqa: S104
    port: int = Field(8000, alias="PORT")
    poi_cache_dir: str = Field(
        "/tmp/tour_guide_cache",  # noqa: S108
        alias="POI_CACHE_DIR",
    )
    narration_cache_dir: str = Field(
        "/tmp/tour_guide_narration_cache",  # noqa: S108
        alias="NARRATION_CACHE_DIR",
    )
    google_places_api_key: str = Field("", alias="GOOGLE_PLACES_API_KEY")
    log_level: str = Field("INFO", alias="LOG_LEVEL")

    model_config = {"populate_by_name": True, "env_prefix": ""}
```

- [ ] **Step 5: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_google_places_client.py tests/unit/test_config.py -v
```

預期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/clients/google_places.py \
        backend/src/tour_guide/config.py \
        backend/tests/unit/test_google_places_client.py
git commit -m "feat(backend): add GooglePlacesClient (Protocol + Fake + Real) and GOOGLE_PLACES_API_KEY config"
```

---

## Task 4：後端 — FoodieFilter（TDD）

**Files:**
- Create: `backend/src/tour_guide/services/foodie_filter.py`
- Create: `backend/tests/unit/test_foodie_filter.py`

- [ ] **Step 1: 寫失敗測試**

建立 `backend/tests/unit/test_foodie_filter.py`：

```python
"""Unit tests for FoodieFilter pure function."""

import pytest

from tour_guide.models.poi import Place
from tour_guide.services.foodie_filter import filter_places


def _place(rating: float | None, count: int | None, *, name: str = "餐廳") -> Place:
    return Place(
        id=f"gplace:{name}",
        name=name,
        lat=25.0,
        lon=121.0,
        rating=rating,
        user_ratings_total=count,
        price_level=2,
        types=["restaurant"],
        vicinity="台北市",
    )


class TestFoodieFilterNormalHours:
    """Outside meal hours: rating >= 4.3 AND count >= 50."""

    def test_passes_when_above_threshold(self):
        place = _place(4.3, 50)
        assert filter_places([place], current_hour=10) == [place]

    def test_passes_high_rating(self):
        place = _place(4.8, 200)
        assert filter_places([place], current_hour=8) == [place]

    def test_excluded_rating_below_threshold(self):
        place = _place(4.2, 100)
        assert filter_places([place], current_hour=10) == []

    def test_excluded_count_below_threshold(self):
        place = _place(4.5, 49)
        assert filter_places([place], current_hour=9) == []

    def test_excluded_both_below(self):
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=16) == []


class TestFoodieFilterMealHours:
    """During meal hours (11-13 / 17-20): rating >= 4.0 AND count >= 30."""

    @pytest.mark.parametrize("hour", [11, 12, 13, 17, 18, 19, 20])
    def test_lower_threshold_applies_during_meal_hours(self, hour):
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=hour) == [place]

    def test_excluded_at_boundary_hour_10(self):
        """Hour 10 is NOT meal time — normal threshold applies."""
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=10) == []

    def test_excluded_at_boundary_hour_14(self):
        """Hour 14 is NOT meal time — normal threshold applies."""
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=14) == []

    def test_excluded_at_boundary_hour_21(self):
        """Hour 21 is NOT meal time — normal threshold applies."""
        place = _place(4.0, 30)
        assert filter_places([place], current_hour=21) == []


class TestFoodieFilterNoneValues:
    def test_excluded_when_rating_none(self):
        place = _place(None, 100)
        assert filter_places([place], current_hour=12) == []

    def test_excluded_when_count_none(self):
        place = _place(4.5, None)
        assert filter_places([place], current_hour=12) == []

    def test_excluded_when_both_none(self):
        place = _place(None, None)
        assert filter_places([place], current_hour=12) == []


class TestFoodieFilterMixed:
    def test_mixed_list_returns_only_qualifying(self):
        good = _place(4.5, 100, name="好店")
        low_rating = _place(3.9, 200, name="低評")
        no_rating = _place(None, 50, name="無評")
        result = filter_places([good, low_rating, no_rating], current_hour=10)
        assert result == [good]

    def test_empty_list(self):
        assert filter_places([], current_hour=12) == []
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_foodie_filter.py -v
```

預期：`ImportError: cannot import name 'filter_places'`

- [ ] **Step 3: 實作 FoodieFilter**

建立 `backend/src/tour_guide/services/foodie_filter.py`：

```python
"""Foodie filter: rating + meal-time threshold filtering for Google Places results."""

from tour_guide.models.poi import Place

_NORMAL_MIN_RATING = 4.3
_NORMAL_MIN_COUNT = 50

_MEAL_MIN_RATING = 4.0
_MEAL_MIN_COUNT = 30

_MEAL_HOURS = frozenset(range(11, 14)) | frozenset(range(17, 21))


def filter_places(places: list[Place], current_hour: int) -> list[Place]:
    """Filter restaurant places by rating threshold (meal-time aware).

    Args:
        places: List of Place objects from Google Places API.
        current_hour: Current hour (0-23), injected for testability.

    Returns:
        Filtered list keeping only places above threshold.
    """
    is_meal_time = current_hour in _MEAL_HOURS
    min_rating = _MEAL_MIN_RATING if is_meal_time else _NORMAL_MIN_RATING
    min_count = _MEAL_MIN_COUNT if is_meal_time else _NORMAL_MIN_COUNT

    return [
        p for p in places
        if p.rating is not None
        and p.user_ratings_total is not None
        and p.rating >= min_rating
        and p.user_ratings_total >= min_count
    ]
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_foodie_filter.py -v
```

預期：全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/foodie_filter.py \
        backend/tests/unit/test_foodie_filter.py
git commit -m "feat(backend): add FoodieFilter with meal-time threshold (TDD)"
```

---

## Task 5：後端 — ConfidenceClassifier 食家分支（TDD）

**Files:**
- Modify: `backend/src/tour_guide/services/confidence.py`
- Modify: `backend/tests/unit/test_confidence.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/unit/test_confidence.py` 末尾加入：

```python
class TestConfidenceClassifierPlace:
    """Tests for ConfidenceClassifier.classify_place()."""

    def test_high_when_above_both_thresholds(self):
        place = Place(
            id="gplace:001", name="名店", lat=25.0, lon=121.0,
            rating=4.5, user_ratings_total=100, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "high"

    def test_high_boundary_exactly_45_and_100(self):
        place = Place(
            id="gplace:002", name="名店", lat=25.0, lon=121.0,
            rating=4.5, user_ratings_total=100, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "high"

    def test_medium_when_rating_below_45(self):
        place = Place(
            id="gplace:003", name="中等", lat=25.0, lon=121.0,
            rating=4.3, user_ratings_total=200, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "medium"

    def test_medium_when_count_below_100(self):
        place = Place(
            id="gplace:004", name="中等", lat=25.0, lon=121.0,
            rating=4.8, user_ratings_total=50, price_level=2,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "medium"

    def test_low_when_rating_none(self):
        place = Place(
            id="gplace:005", name="無評", lat=25.0, lon=121.0,
            rating=None, user_ratings_total=None, price_level=None,
            types=["restaurant"], vicinity="台北",
        )
        assert ConfidenceClassifier.classify_place(place) == "low"
```

也要在檔案頂部 import 中加入 `Place`（確認現有 import 後加入）：

```python
from tour_guide.models.poi import Place, POIContext
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_confidence.py::TestConfidenceClassifierPlace -v
```

預期：`AttributeError: type object 'ConfidenceClassifier' has no attribute 'classify_place'`

- [ ] **Step 3: 實作 classify_place**

編輯 `backend/src/tour_guide/services/confidence.py`，完整替換為：

```python
from typing import Literal

from tour_guide.models.poi import Place, POIContext


class ConfidenceClassifier:
    """Classifier for POI confidence levels."""

    @staticmethod
    def classify(poi_context: POIContext) -> Literal["high", "medium", "low"]:
        """Classify confidence based on Wikipedia extract length."""
        if poi_context.wiki is None or not poi_context.wiki.extract:
            return "low"
        if len(poi_context.wiki.extract) >= 200:
            return "high"
        return "medium"

    @staticmethod
    def classify_place(place: Place) -> Literal["high", "medium", "low"]:
        """Classify confidence for a Google Places result.

        high   → rating >= 4.5 AND user_ratings_total >= 100
        medium → passes FoodieFilter but below high threshold
        low    → missing rating data
        """
        if place.rating is None or place.user_ratings_total is None:
            return "low"
        if place.rating >= 4.5 and place.user_ratings_total >= 100:
            return "high"
        return "medium"
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_confidence.py -v
```

預期：全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/confidence.py \
        backend/tests/unit/test_confidence.py
git commit -m "feat(backend): add ConfidenceClassifier.classify_place() for Google Places results"
```

---

## Task 6：後端 — POIService persona routing（TDD）

**Files:**
- Modify: `backend/src/tour_guide/services/poi_service.py`
- Modify: `backend/tests/integration/test_poi_service.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/integration/test_poi_service.py` 末尾加入（在現有 imports 後補上需要的 import）：

先確認頂部有：
```python
from tour_guide.clients.google_places import FakeGooglePlacesClient
from tour_guide.models.poi import OsmNode, Place, WikiArticle
```

再加入測試 class：

```python
class TestPOIServiceFoodieRouting:
    """Tests for POIService persona-aware routing."""

    @pytest.fixture()
    def sample_place(self):
        return Place(
            id="gplace:ChIJ001",
            name="鼎泰豐",
            lat=25.033,
            lon=121.564,
            rating=4.6,
            user_ratings_total=328,
            price_level=2,
            types=["restaurant"],
            vicinity="信義區",
        )

    async def test_foodie_persona_uses_google_places(self, tmp_path, sample_place):
        """persona='foodie' → GooglePlacesClient called, not Overpass."""
        fake_gp = FakeGooglePlacesClient(scripted_places=[sample_place])
        fake_overpass = FakeOverpassClient([])  # should NOT be called
        fake_wiki = FakeWikiClient(None)
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(
            overpass=fake_overpass,
            wikipedia=fake_wiki,
            cache=cache,
            google_places=fake_gp,
        )
        pois = await service.nearby(25.033, 121.564, 500, "foodie", "zh-TW")

        assert fake_overpass.call_count == 0
        assert len(pois) == 1
        assert pois[0].id == "gplace:ChIJ001"
        assert pois[0].rating == 4.6
        assert pois[0].user_ratings_total == 328

    async def test_non_foodie_persona_uses_overpass(self, tmp_path, sample_node, sample_article):
        """persona='history_uncle' → OverpassClient called, not GooglePlaces."""
        fake_gp = FakeGooglePlacesClient(scripted_places=[])
        fake_overpass = FakeOverpassClient([sample_node])
        fake_wiki = FakeWikiClient(sample_article)
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(
            overpass=fake_overpass,
            wikipedia=fake_wiki,
            cache=cache,
            google_places=fake_gp,
        )
        pois = await service.nearby(25.1023, 121.5482, 500, "history_uncle", "zh-TW")

        assert fake_overpass.call_count == 1
        assert pois[0].rating is None  # non-foodie POI has no rating

    async def test_foodie_poi_has_no_wiki(self, tmp_path, sample_place):
        """Foodie POIs converted from Place have wiki=None."""
        fake_gp = FakeGooglePlacesClient(scripted_places=[sample_place])
        cache = POICache(cache_dir=tmp_path / "cache")

        service = POIService(
            overpass=FakeOverpassClient([]),
            wikipedia=FakeWikiClient(None),
            cache=cache,
            google_places=fake_gp,
        )
        pois = await service.nearby(25.033, 121.564, 500, "foodie", "zh-TW")

        assert pois[0].wiki is None
        assert pois[0].place_types == ["restaurant"]
        assert pois[0].vicinity == "信義區"
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/integration/test_poi_service.py::TestPOIServiceFoodieRouting -v
```

預期：`TypeError: POIService.__init__() got an unexpected keyword argument 'google_places'`

- [ ] **Step 3: 更新 POIService**

完整替換 `backend/src/tour_guide/services/poi_service.py`：

```python
"""POI Service: combines Overpass, Wikipedia, filter, confidence, and cache."""

import datetime
import math

from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import POI, BBox, Place, POIContext, TagFilter, WikiArticle
from tour_guide.services.confidence import ConfidenceClassifier
from tour_guide.services.foodie_filter import filter_places
from tour_guide.services.poi_filter import filter_poi_nodes

_DEFAULT_TAG_FILTERS = [
    TagFilter(key="tourism"),
    TagFilter(key="historic"),
]


def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return distance in meters between two lat/lon points."""
    R = 6_371_000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _lat_lon_to_bbox(lat: float, lon: float, radius_m: int) -> BBox:
    delta_lat = radius_m / 111_320
    delta_lon = radius_m / (111_320 * math.cos(math.radians(lat)))
    return BBox(lat - delta_lat, lon - delta_lon, lat + delta_lat, lon + delta_lon)


def _place_to_poi(place: Place, user_lat: float, user_lon: float) -> POI:
    """Convert a Google Places Place to a POI dataclass."""
    confidence = ConfidenceClassifier.classify_place(place)
    distance = _haversine(user_lat, user_lon, place.lat, place.lon)
    return POI(
        id=place.id,
        name=place.name,
        lat=place.lat,
        lon=place.lon,
        tags={},
        wiki=None,
        distance_m=distance,
        confidence=confidence,
        rating=place.rating,
        user_ratings_total=place.user_ratings_total,
        price_level=place.price_level,
        place_types=place.types,
        vicinity=place.vicinity,
    )


class POIService:
    def __init__(
        self,
        overpass: OverpassClient,
        wikipedia: WikipediaClient,
        cache: POICache,
        google_places=None,
    ):
        self._overpass = overpass
        self._wikipedia = wikipedia
        self._cache = cache
        self._google_places = google_places

    async def nearby(
        self,
        lat: float,
        lon: float,
        radius: int,
        persona: str,
        lang: str,
    ) -> list[POI]:
        if persona == "foodie":
            return await self._nearby_foodie(lat, lon, radius)
        return await self._nearby_osm(lat, lon, radius, lang)

    async def _nearby_foodie(self, lat: float, lon: float, radius: int) -> list[POI]:
        if self._google_places is None:
            return []

        region_key = f"region:foodie:{lat:.3f}:{lon:.3f}:{radius}"
        cached = self._cache.get(region_key)
        if cached is not None:
            return [
                POI(
                    id=p["id"], name=p["name"], lat=p["lat"], lon=p["lon"],
                    tags=p["tags"], wiki=None,
                    distance_m=p["distance_m"], confidence=p["confidence"],
                    rating=p.get("rating"), user_ratings_total=p.get("user_ratings_total"),
                    price_level=p.get("price_level"), place_types=p.get("place_types"),
                    vicinity=p.get("vicinity"),
                )
                for p in cached
            ]

        current_hour = datetime.datetime.now().hour
        places = await self._google_places.nearby_restaurants(lat, lon, radius)
        filtered = filter_places(places, current_hour)
        pois = [_place_to_poi(p, lat, lon) for p in filtered]
        pois.sort(key=lambda p: p.distance_m)

        self._cache.put(
            region_key,
            [
                {
                    "id": p.id, "name": p.name, "lat": p.lat, "lon": p.lon,
                    "tags": p.tags, "distance_m": p.distance_m, "confidence": p.confidence,
                    "rating": p.rating, "user_ratings_total": p.user_ratings_total,
                    "price_level": p.price_level, "place_types": p.place_types,
                    "vicinity": p.vicinity,
                }
                for p in pois
            ],
        )
        return pois

    async def _nearby_osm(self, lat: float, lon: float, radius: int, lang: str) -> list[POI]:
        region_key = f"region:{lat:.3f}:{lon:.3f}:{radius}:{lang}"
        cached = self._cache.get(region_key)
        if cached is not None:
            return [
                POI(
                    id=p["id"], name=p["name"], lat=p["lat"], lon=p["lon"],
                    tags=p["tags"],
                    wiki=WikiArticle(**p["wiki"]) if p["wiki"] else None,
                    distance_m=p["distance_m"], confidence=p["confidence"],
                )
                for p in cached
            ]

        bbox = _lat_lon_to_bbox(lat, lon, radius)
        raw_nodes = await self._overpass.query(bbox, _DEFAULT_TAG_FILTERS)
        filtered = filter_poi_nodes(raw_nodes)

        pois: list[POI] = []
        for node in filtered:
            wiki_key = node.tags.get("wikipedia", "")
            wiki_title = wiki_key.split(":", 1)[-1] if ":" in wiki_key else wiki_key
            wiki_lang = wiki_key.split(":")[0] if ":" in wiki_key else lang

            wiki = None
            if wiki_title:
                wiki = await self._wikipedia.summary(wiki_title, wiki_lang)

            poi_context = POIContext(osm=node, wiki=wiki)
            confidence = ConfidenceClassifier.classify(poi_context)
            distance = _haversine(lat, lon, node.lat, node.lon)

            pois.append(
                POI(
                    id=node.id,
                    name=node.tags.get("name", node.id),
                    lat=node.lat,
                    lon=node.lon,
                    tags=node.tags,
                    wiki=wiki,
                    distance_m=distance,
                    confidence=confidence,
                )
            )

        pois.sort(key=lambda p: p.distance_m)

        self._cache.put(
            region_key,
            [
                {
                    "id": p.id, "name": p.name, "lat": p.lat, "lon": p.lon,
                    "tags": p.tags,
                    "wiki": vars(p.wiki) if p.wiki else None,
                    "distance_m": p.distance_m, "confidence": p.confidence,
                }
                for p in pois
            ],
        )
        return pois
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/integration/test_poi_service.py -v
```

預期：全部 PASS（含原有測試 + 新 foodie routing 測試）

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/poi_service.py \
        backend/tests/integration/test_poi_service.py
git commit -m "feat(backend): add POIService persona routing — foodie → Google Places, others → Overpass"
```

---

## Task 7：後端 — api/poi.py 輸出 foodie 欄位 + integration test

**Files:**
- Modify: `backend/src/tour_guide/api/poi.py`
- Modify: `backend/tests/integration/test_poi_api.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/integration/test_poi_api.py` 的 `TestPOINearbyAPI` class 末尾加入：

先在頂部 imports 確認有 `from tour_guide.models.poi import POI, WikiArticle`（已有），再加入 fixture 和測試：

```python
@pytest.fixture
def sample_foodie_poi():
    """Create a sample foodie POI with Google Places fields."""
    return POI(
        id="gplace:ChIJ001",
        name="鼎泰豐",
        lat=25.033,
        lon=121.564,
        tags={},
        wiki=None,
        distance_m=47.3,
        confidence="high",
        rating=4.6,
        user_ratings_total=328,
        price_level=2,
        place_types=["restaurant", "food"],
        vicinity="信義區松高路12號",
    )
```

在 `TestPOINearbyAPI` 中加入：

```python
    def test_foodie_poi_response_includes_rating_fields(self, app, client, sample_foodie_poi):
        """GET /poi/nearby with foodie POI returns rating, user_ratings_total etc."""
        fake_service = FakePOIService(pois=[sample_foodie_poi])

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=25.033&lon=121.564&radius=500&lang=zh-TW&persona=foodie"
        )

        assert response.status_code == 200
        poi = response.json()["pois"][0]
        assert poi["rating"] == 4.6
        assert poi["user_ratings_total"] == 328
        assert poi["price_level"] == 2
        assert poi["place_types"] == ["restaurant", "food"]
        assert poi["vicinity"] == "信義區松高路12號"

    def test_non_foodie_poi_response_excludes_rating_fields(self, app, client, sample_poi):
        """GET /poi/nearby with regular POI does NOT include rating fields."""
        fake_service = FakePOIService(pois=[sample_poi])

        def override_poi_service():
            return fake_service

        app.dependency_overrides[get_poi_service] = override_poi_service

        response = client.get(
            "/poi/nearby?lat=25.1023&lon=121.5482&radius=500&lang=zh-TW&persona=history_uncle"
        )

        assert response.status_code == 200
        poi = response.json()["pois"][0]
        assert "rating" not in poi
        assert "user_ratings_total" not in poi
        assert "place_types" not in poi
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd backend && .venv/bin/pytest tests/integration/test_poi_api.py::TestPOINearbyAPI::test_foodie_poi_response_includes_rating_fields -v
```

預期：FAIL（回應中找不到 `rating` 欄位）

- [ ] **Step 3: 更新 api/poi.py**

完整替換 `backend/src/tour_guide/api/poi.py`：

```python
"""POI API endpoint for querying nearby points of interest."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse

from tour_guide.clients.overpass import OverpassRateLimitError
from tour_guide.services.poi_service import POIService

router = APIRouter()


def get_poi_service() -> POIService:
    raise NotImplementedError("Override with dependency")


@router.get("/poi/nearby")
async def poi_nearby(
    lat: float = Query(..., ge=-90, le=90, description="Latitude (-90 to 90)"),
    lon: float = Query(..., ge=-180, le=180, description="Longitude (-180 to 180)"),
    radius: int = Query(500, ge=1, le=5000, description="Search radius in meters"),
    lang: str = Query("zh-TW", description="Language code"),
    persona: str = Query("history_uncle", description="User persona"),
    poi_service: POIService = Depends(get_poi_service),  # noqa: B008
):
    try:
        pois = await poi_service.nearby(lat, lon, radius, persona, lang)
        return {
            "pois": [_serialize_poi(p) for p in pois],
            "queried_at": datetime.now(timezone.utc).isoformat(),  # noqa: UP017
        }
    except OverpassRateLimitError as e:
        return JSONResponse(
            status_code=429,
            content={"detail": "Overpass rate limit exceeded"},
            headers={"Retry-After": str(e.retry_after_s)},
        )
    except Exception as e:
        raise HTTPException(status_code=503, detail="Upstream service unavailable") from e


def _serialize_poi(p) -> dict:
    result = {
        "id": p.id,
        "name": p.name,
        "lat": p.lat,
        "lon": p.lon,
        "tags": p.tags,
        "wiki": {
            "title": p.wiki.title,
            "extract": p.wiki.extract,
            "url": p.wiki.url,
            "lang": p.wiki.lang,
        } if p.wiki else None,
        "distance_m": p.distance_m,
        "confidence": p.confidence,
    }
    if p.rating is not None:
        result["rating"] = p.rating
        result["user_ratings_total"] = p.user_ratings_total
        result["price_level"] = p.price_level
        result["place_types"] = p.place_types
        result["vicinity"] = p.vicinity
    return result
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd backend && .venv/bin/pytest tests/integration/test_poi_api.py -v
```

預期：全部 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/api/poi.py \
        backend/tests/integration/test_poi_api.py
git commit -m "feat(backend): api/poi.py conditionally includes foodie fields in response"
```

---

## Task 8：後端 — main.py wiring + 全套測試

**Files:**
- Modify: `backend/src/tour_guide/main.py`

- [ ] **Step 1: 更新 main.py**

完整替換 `backend/src/tour_guide/main.py`：

```python
"""FastAPI application factory with full dependency injection wiring."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from tour_guide.api import health, narration, poi, qa
from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.google_places import FakeGooglePlacesClient, RealGooglePlacesClient
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.config import AppConfig
from tour_guide.prompts.loader import PersonaLoader
from tour_guide.providers.llm import LiteLLMAdapter
from tour_guide.providers.stt import GeminiSttAdapter
from tour_guide.providers.tts import GeminiTtsAdapter
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_service import POIService
from tour_guide.services.qa_service import QAService


def create_app(config: AppConfig) -> FastAPI:
    http_client = httpx.AsyncClient()

    overpass_client = OverpassClient(client=http_client)
    wikipedia_client = WikipediaClient(client=http_client)
    poi_cache = POICache(config.poi_cache_dir)
    narration_cache = NarrationCache(config.narration_cache_dir)

    llm_provider = LiteLLMAdapter(api_key=config.gemini_api_key)
    tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)
    stt_provider = GeminiSttAdapter(api_key=config.gemini_api_key)

    if config.google_places_api_key:
        google_places_client = RealGooglePlacesClient(api_key=config.google_places_api_key)
    else:
        google_places_client = FakeGooglePlacesClient(scripted_places=[])

    poi_service = POIService(
        overpass=overpass_client,
        wikipedia=wikipedia_client,
        cache=poi_cache,
        google_places=google_places_client,
    )
    narration_service = NarrationService(
        llm=llm_provider,
        tts=tts_provider,
        cache=narration_cache,
    )
    qa_service = QAService(
        stt=stt_provider,
        llm=llm_provider,
        tts=tts_provider,
    )
    persona_registry = PersonaLoader.load_all()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await http_client.aclose()

    app = FastAPI(title="AI Tour Guide", lifespan=lifespan)

    app.dependency_overrides[poi.get_poi_service] = lambda: poi_service
    app.dependency_overrides[narration.get_narration_service] = lambda: narration_service
    app.dependency_overrides[narration.get_persona_registry] = lambda: persona_registry
    app.dependency_overrides[qa.get_qa_service] = lambda: qa_service
    app.dependency_overrides[qa.get_persona_registry] = lambda: persona_registry

    app.include_router(health.router)
    app.include_router(poi.router)
    app.include_router(narration.router)
    app.include_router(qa.router)

    return app


try:
    app = create_app(AppConfig())
except Exception:
    app = None  # type: ignore
```

- [ ] **Step 2: 跑全套後端測試**

```bash
cd backend && .venv/bin/pytest -v
```

預期：全部 PASS

- [ ] **Step 3: ruff check**

```bash
cd backend && .venv/bin/ruff check src/
```

預期：無 error

- [ ] **Step 4: Commit**

```bash
git add backend/src/tour_guide/main.py
git commit -m "feat(backend): wire GooglePlacesClient in app factory (env-var based Real/Fake switch)"
```

---

## Task 9：Flutter — POI model 擴充（TDD）

**Files:**
- Modify: `flutter_app/lib/shared/backend/models/poi.dart`
- Modify: `flutter_app/test/unit/models_test.dart`

- [ ] **Step 1: 寫失敗測試**

在 `flutter_app/test/unit/models_test.dart` 的 `group('POI.fromJson', ...)` 內，在現有測試後加入：

```dart
    test('parses foodie POI with rating fields', () {
      final json = {
        'id': 'gplace:ChIJ001',
        'name': '鼎泰豐',
        'lat': 25.033,
        'lon': 121.564,
        'tags': <String, dynamic>{},
        'wiki': null,
        'distance_m': 47.3,
        'confidence': 'high',
        'rating': 4.6,
        'user_ratings_total': 328,
        'price_level': 2,
        'place_types': ['restaurant', 'food'],
        'vicinity': '信義區松高路12號',
      };
      final poi = POI.fromJson(json);
      expect(poi.rating, 4.6);
      expect(poi.userRatingsTotal, 328);
      expect(poi.priceLevel, 2);
      expect(poi.placeTypes, ['restaurant', 'food']);
      expect(poi.vicinity, '信義區松高路12號');
    });

    test('non-foodie POI has null foodie fields', () {
      final json = {
        'id': 'osm:way:12345',
        'name': '故宮博物院',
        'lat': 25.1023,
        'lon': 121.5482,
        'tags': <String, dynamic>{},
        'wiki': null,
        'distance_m': 87.5,
        'confidence': 'high',
      };
      final poi = POI.fromJson(json);
      expect(poi.rating, isNull);
      expect(poi.userRatingsTotal, isNull);
      expect(poi.priceLevel, isNull);
      expect(poi.placeTypes, isNull);
      expect(poi.vicinity, isNull);
    });
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd flutter_app && flutter test test/unit/models_test.dart
```

預期：`The getter 'rating' isn't defined for the type 'POI'`

- [ ] **Step 3: 更新 poi.dart**

完整替換 `flutter_app/lib/shared/backend/models/poi.dart`：

```dart
class WikiArticle {
  final String title;
  final String extract;
  final String url;

  const WikiArticle({
    required this.title,
    required this.extract,
    required this.url,
  });

  factory WikiArticle.fromJson(Map<String, dynamic> json) => WikiArticle(
        title: json['title'] as String,
        extract: json['extract'] as String,
        url: json['url'] as String,
      );

  Map<String, dynamic> toJson() => {
        'title': title,
        'extract': extract,
        'url': url,
      };
}

class POI {
  final String id;
  final String name;
  final double lat;
  final double lon;
  final Map<String, String> tags;
  final WikiArticle? wiki;
  final double distanceM;
  final String confidence;

  // foodie only — null for non-foodie POIs
  final double? rating;
  final int? userRatingsTotal;
  final int? priceLevel;
  final List<String>? placeTypes;
  final String? vicinity;

  const POI({
    required this.id,
    required this.name,
    required this.lat,
    required this.lon,
    required this.tags,
    this.wiki,
    required this.distanceM,
    required this.confidence,
    this.rating,
    this.userRatingsTotal,
    this.priceLevel,
    this.placeTypes,
    this.vicinity,
  });

  factory POI.fromJson(Map<String, dynamic> json) => POI(
        id: json['id'] as String,
        name: json['name'] as String,
        lat: (json['lat'] as num).toDouble(),
        lon: (json['lon'] as num).toDouble(),
        tags: (json['tags'] as Map<String, dynamic>? ?? {})
            .cast<String, String>(),
        wiki: json['wiki'] != null
            ? WikiArticle.fromJson(json['wiki'] as Map<String, dynamic>)
            : null,
        distanceM: (json['distance_m'] as num).toDouble(),
        confidence: json['confidence'] as String,
        rating: (json['rating'] as num?)?.toDouble(),
        userRatingsTotal: json['user_ratings_total'] as int?,
        priceLevel: json['price_level'] as int?,
        placeTypes: (json['place_types'] as List<dynamic>?)?.cast<String>(),
        vicinity: json['vicinity'] as String?,
      );
}
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd flutter_app && flutter test test/unit/models_test.dart
```

預期：全部 PASS

- [ ] **Step 5: 跑全套 Flutter 測試確認未破壞**

```bash
cd flutter_app && flutter test
```

預期：全部 PASS

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/shared/backend/models/poi.dart \
        flutter_app/test/unit/models_test.dart
git commit -m "feat(flutter): extend POI model with nullable foodie fields (rating, priceLevel, etc.)"
```

---

## Task 10：Flutter — PersonaInfo + kPersonas 觸發半徑（TDD）

**Files:**
- Modify: `flutter_app/lib/features/session/persona_data.dart`
- Modify: `flutter_app/test/unit/trigger_engine_test.dart`

- [ ] **Step 1: 寫測試（TriggerEngine 已支援 radiusM，補充測試）**

在 `flutter_app/test/unit/trigger_engine_test.dart` 的 `group('TriggerEngine.evaluate', ...)` 末尾加入：

```dart
    test('respects custom radiusM of 50m — excludes POI at 89m', () {
      // ~89m north of user — within 100m but outside 50m
      final poi = _poi('near50', 25.1031, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {},
        radiusM: 50.0,
      );
      expect(triggers, isEmpty);
    });

    test('respects custom radiusM of 50m — includes POI at 40m', () {
      // ~44m north of user — within 50m
      final poi = _poi('within50', 25.1027, 121.5482);
      final triggers = TriggerEngine.evaluate(
        userLat: userLat,
        userLon: userLon,
        pois: [poi],
        playedPoiIds: {},
        cooldownPoiIds: {},
        radiusM: 50.0,
      );
      expect(triggers, [poi]);
    });
```

- [ ] **Step 2: 跑測試確認通過（TriggerEngine 已實作 radiusM）**

```bash
cd flutter_app && flutter test test/unit/trigger_engine_test.dart
```

預期：全部 PASS（TriggerEngine 已有 `radiusM` 參數）

- [ ] **Step 3: 加 defaultTriggerRadiusM 到 PersonaInfo**

完整替換 `flutter_app/lib/features/session/persona_data.dart`：

```dart
class PersonaInfo {
  final String id;
  final String emoji;
  final String displayName;
  final String description;
  final int defaultTriggerRadiusM;

  const PersonaInfo({
    required this.id,
    required this.emoji,
    required this.displayName,
    required this.description,
    required this.defaultTriggerRadiusM,
  });
}

const kPersonas = [
  PersonaInfo(
    id: 'history_uncle',
    emoji: '🏛️',
    displayName: '歷史大叔',
    description: '嚴謹考據，帶你穿越時代脈絡',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'story_brother',
    emoji: '📖',
    displayName: '故事大哥哥',
    description: '鄉野軼事，讓景點活靈活現',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'gossip_auntie',
    emoji: '🗣️',
    displayName: '八卦阿姨',
    description: '名人八卦，讓歷史不再無聊',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'kid_sister',
    emoji: '🌟',
    displayName: '童趣小妹',
    description: '好奇驚嘆，用孩子的眼睛看世界',
    defaultTriggerRadiusM: 100,
  ),
  PersonaInfo(
    id: 'foodie',
    emoji: '🍜',
    displayName: '美食家',
    description: '饕客視角，發掘在地好滋味',
    defaultTriggerRadiusM: 50,
  ),
];
```

- [ ] **Step 4: 跑全套 Flutter 測試**

```bash
cd flutter_app && flutter test
```

預期：全部 PASS

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/session/persona_data.dart \
        flutter_app/test/unit/trigger_engine_test.dart
git commit -m "feat(flutter): add defaultTriggerRadiusM to PersonaInfo; foodie=50m, others=100m"
```

---

## Task 11：Flutter — TriggerNotifier 讀 persona 觸發半徑

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`

- [ ] **Step 1: 更新 TriggerNotifier**

完整替換 `flutter_app/lib/features/narration/providers/trigger_provider.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/shared/providers.dart';

class TriggerNotifier extends Notifier<void> {
  final Set<String> _sessionPlayedIds = {};

  @override
  void build() {
    final positionAsync = ref.watch(positionStreamProvider);
    final poisAsync = ref.watch(poiProvider);

    positionAsync.whenData((position) {
      poisAsync.whenData((pois) {
        _evaluate(position, pois);
      });
    });
  }

  Future<void> _evaluate(Position position, List<dynamic> pois) async {
    final narState = ref.read(narrationProvider);
    if (narState.status == NarrationStatus.playing ||
        narState.status == NarrationStatus.loading) {
      return;
    }

    final db = ref.read(localDbProvider);
    final cooldownIds = <String>{};
    for (final poi in pois) {
      final inCooldown =
          await db.isCooldown(poi.id, const Duration(hours: 24));
      if (inCooldown) cooldownIds.add(poi.id);
    }

    final session = ref.read(sessionProvider);
    final personaInfo = kPersonas.firstWhere(
      (p) => p.id == session.persona,
      orElse: () => kPersonas.first,
    );
    final triggerRadiusM = personaInfo.defaultTriggerRadiusM.toDouble();

    final triggers = TriggerEngine.evaluate(
      userLat: position.latitude,
      userLon: position.longitude,
      pois: pois.cast(),
      playedPoiIds: _sessionPlayedIds,
      cooldownPoiIds: cooldownIds,
      radiusM: triggerRadiusM,
    );

    if (triggers.isNotEmpty) {
      final poi = triggers.first;
      _sessionPlayedIds.add(poi.id);
      ref.read(narrationProvider.notifier).narrate(
        poi,
        persona: session.persona,
        lang: session.lang,
      );
    }
  }
}

final triggerProvider = NotifierProvider<TriggerNotifier, void>(
  TriggerNotifier.new,
);
```

- [ ] **Step 2: 跑全套 Flutter 測試**

```bash
cd flutter_app && flutter test
```

預期：全部 PASS

- [ ] **Step 3: flutter analyze**

```bash
cd flutter_app && flutter analyze
```

預期：無 error/warning（僅允許 info）

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart
git commit -m "feat(flutter): TriggerNotifier reads per-persona trigger radius from kPersonas"
```

---

## Task 12：Flutter — NarrationSheet _FoodieRatingBar（widget test）

**Files:**
- Modify: `flutter_app/lib/features/narration/widgets/narration_sheet.dart`
- Modify: `flutter_app/test/widget/narration_sheet_test.dart`

- [ ] **Step 1: 寫失敗測試**

在 `flutter_app/test/widget/narration_sheet_test.dart` 加入以下 imports 和測試：

在現有 import 後加入（若尚未有）：
```dart
import 'package:flutter_app/features/narration/widgets/narration_sheet.dart';
import 'package:flutter_app/features/qa/providers/qa_provider.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/providers.dart';
import 'package:drift/native.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
```

在現有 `main()` 函式末尾加入（在最後一個 `}` 之前）：

```dart
  testWidgets('NarrationSheet shows rating bar for foodie POI', (tester) async {
    final foodiePoi = POI(
      id: 'gplace:001',
      name: '鼎泰豐',
      lat: 25.033,
      lon: 121.564,
      tags: const {},
      distanceM: 47,
      confidence: 'high',
      rating: 4.6,
      userRatingsTotal: 328,
      priceLevel: 2,
    );
    final state = NarrationState(
      status: NarrationStatus.playing,
      currentPoi: foodiePoi,
      subtitle: '美食推薦',
      progress: 0.5,
      confidence: 'high',
    );

    final db = LocalDb.forTesting(NativeDatabase.memory());
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(state),
          ),
          qaProvider.overrideWith((ref) => _FakeQaNotifier()),
          localDbProvider.overrideWithValue(db),
          locationServiceProvider.overrideWithValue(FakeLocationService()),
          audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
          backendClientProvider.overrideWithValue(const FakeBackendClient(nearbyPois: [])),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationSheet()),
        ),
      ),
    );

    expect(find.textContaining('4.6'), findsOneWidget);
    expect(find.textContaining('328'), findsOneWidget);
    expect(find.textContaining('\$\$'), findsOneWidget);
    await db.close();
  });

  testWidgets('NarrationSheet hides rating bar for non-foodie POI', (tester) async {
    final regularPoi = POI(
      id: 'osm:node:1',
      name: '故宮博物院',
      lat: 25.1023,
      lon: 121.5482,
      tags: const {},
      distanceM: 87,
      confidence: 'high',
    );
    final state = NarrationState(
      status: NarrationStatus.playing,
      currentPoi: regularPoi,
      subtitle: '故宮介紹',
      progress: 0.3,
      confidence: 'high',
    );

    final db = LocalDb.forTesting(NativeDatabase.memory());
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          narrationProvider.overrideWith(
            (ref) => _FakeNarrationNotifier(state),
          ),
          qaProvider.overrideWith((ref) => _FakeQaNotifier()),
          localDbProvider.overrideWithValue(db),
          locationServiceProvider.overrideWithValue(FakeLocationService()),
          audioPlayerServiceProvider.overrideWithValue(FakeAudioPlayerService()),
          backendClientProvider.overrideWithValue(const FakeBackendClient(nearbyPois: [])),
        ],
        child: const MaterialApp(
          home: Scaffold(body: NarrationSheet()),
        ),
      ),
    );

    expect(find.byType(NarrationSheet), findsOneWidget);
    // rating text should NOT appear
    expect(find.textContaining('⭐'), findsNothing);
    await db.close();
  });
```

在現有 `_FakeNarrationNotifier` 後加入：

```dart
class _FakeQaNotifier extends StateNotifier<QaState> implements QaNotifier {
  _FakeQaNotifier() : super(const QaState());
  @override
  Future<void> startRecording() async {}
  @override
  Future<void> stopAndSend({required String persona, required String lang, String? currentPoiId, String narrationSoFar = ''}) async {}
  @override
  void reset() {}
}
```

- [ ] **Step 2: 跑測試確認失敗**

```bash
cd flutter_app && flutter test test/widget/narration_sheet_test.dart
```

預期：找不到 `textContaining('4.6')`

- [ ] **Step 3: 加 _FoodieRatingBar 到 NarrationSheet**

在 `flutter_app/lib/features/narration/widgets/narration_sheet.dart` 中，在 `NarrationSheet` class 的 `build` 方法內，找到 `const SizedBox(height: 8),` 之後（Q&A 字幕區塊之前）的位置，加入 rating bar。

找到：
```dart
            const SizedBox(height: 8),
            // Q&A 字幕區塊（僅在 Q&A 進行中時顯示）
```

替換為：
```dart
            const SizedBox(height: 8),
            _FoodieRatingBar(poi: state.currentPoi!),
            // Q&A 字幕區塊（僅在 Q&A 進行中時顯示）
```

然後在 `narration_sheet.dart` 檔案末尾（`NarrationSheet` class 的 `}` 之後）加入：

```dart

class _FoodieRatingBar extends StatelessWidget {
  const _FoodieRatingBar({required this.poi});

  final POI poi;

  @override
  Widget build(BuildContext context) {
    if (poi.rating == null) return const SizedBox.shrink();

    final priceDollars = poi.priceLevel != null
        ? '\$' * poi.priceLevel!
        : '';
    final countText = poi.userRatingsTotal != null
        ? '(${poi.userRatingsTotal} 則評論)'
        : '';

    return Padding(
      padding: const EdgeInsets.only(bottom: 8),
      child: Text(
        '⭐ ${poi.rating!.toStringAsFixed(1)}  $countText${priceDollars.isNotEmpty ? '  $priceDollars' : ''}',
        style: const TextStyle(
          color: Colors.amber,
          fontSize: 12,
        ),
      ),
    );
  }
}
```

並在 `narration_sheet.dart` 頂部確認有 import poi model：
```dart
import 'package:flutter_app/shared/backend/models/poi.dart';
```

- [ ] **Step 4: 跑測試確認通過**

```bash
cd flutter_app && flutter test test/widget/narration_sheet_test.dart
```

預期：全部 PASS

- [ ] **Step 5: 跑全套 Flutter 測試**

```bash
cd flutter_app && flutter test
```

預期：全部 PASS

- [ ] **Step 6: flutter analyze**

```bash
cd flutter_app && flutter analyze
```

預期：無 error/warning

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/narration/widgets/narration_sheet.dart \
        flutter_app/test/widget/narration_sheet_test.dart
git commit -m "feat(flutter): add _FoodieRatingBar to NarrationSheet — shows rating/price for foodie POIs"
```

---

## 最終驗收

- [ ] **後端全套測試通過**

```bash
cd backend && .venv/bin/pytest -v
```

預期：全部 PASS（≥ 159 + 新增約 20 個測試）

- [ ] **後端 lint 乾淨**

```bash
cd backend && .venv/bin/ruff check src/
```

預期：無 output

- [ ] **Flutter 全套測試通過**

```bash
cd flutter_app && flutter test
```

預期：全部 PASS（≥ 71 + 新增約 10 個測試）

- [ ] **Flutter analyze 乾淨**

```bash
cd flutter_app && flutter analyze
```

預期：無 error/warning（僅允許 info）

- [ ] **手動驗證 FoodieFilter 過濾行為**

```bash
cd backend && .venv/bin/python -c "
from tour_guide.services.foodie_filter import filter_places
from tour_guide.models.poi import Place
p = Place('gplace:1','測試餐廳',25.0,121.0,4.3,50,2,['restaurant'],'台北')
print('一般時段:', filter_places([p], current_hour=10))
print('用餐時段:', filter_places([p], current_hour=12))
"
```

預期：一般時段回傳 `[Place(...)]`（4.3 ≥ 4.3），用餐時段也回傳（4.3 ≥ 4.0）

- [ ] **最終 commit message 更新 session-handoff.md**（此步驟在 Plan E 全部完成後）

```bash
# 更新 tasks/session-handoff.md 中 Plan E 狀態為 ✅ 完成
```

---

*— Plan E 實作計畫結束 —*
