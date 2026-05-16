# Auto Narration & POI Improvement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove map markers, broaden POI discovery via relaxed OSM filter + Wikipedia fallback chain (poi_name → suburb → city → verbal fallback), and add persona-specific scene-opening instructions to narration prompts.

**Architecture:** A new `WikipediaResolver` service encapsulates the multi-level Wikipedia lookup, backed by a lightweight `NominatimClient` for reverse geocoding. `POIService` injects `WikipediaResolver` and limits Wikipedia lookups to the 20 nearest nodes. `NarrationService` short-circuits before the LLM call when no wiki data is found, TTS-ing a pre-written fallback phrase instead.

**Tech Stack:** Python/FastAPI (backend), Flutter/Dart (app), httpx (HTTP), pytest + AsyncMock (tests), Nominatim OSM API (reverse geocoding), Wikipedia opensearch API

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `flutter_app/lib/features/map/screens/map_screen.dart` | Modify | Remove markers building block |
| `flutter_app/lib/features/map/widgets/poi_marker.dart` | Delete | Marker color helper — no longer used |
| `backend/src/tour_guide/services/poi_filter.py` | Modify | Relax filter: only require tourism/historic + name |
| `backend/tests/unit/test_poi_filter.py` | Modify | Update tests for new filter rules |
| `backend/src/tour_guide/clients/wikipedia.py` | Modify | Add `search(query, lang)` method |
| `backend/tests/unit/test_wikipedia_client.py` | Create | Tests for `search()` method |
| `backend/src/tour_guide/clients/nominatim.py` | Create | `NominatimClient.reverse(lat, lon)` |
| `backend/tests/unit/test_nominatim_client.py` | Create | Tests for `NominatimClient` |
| `backend/src/tour_guide/services/wikipedia_resolver.py` | Create | `WikipediaResolver` with 4-level fallback |
| `backend/tests/unit/test_wikipedia_resolver.py` | Create | Tests for fallback chain |
| `backend/src/tour_guide/models/persona.py` | Modify | Add `no_data_context: dict[str, str]` field |
| `backend/src/tour_guide/prompts/loader.py` | Modify | Parse `no_data_context` from YAML |
| `backend/tests/unit/test_persona_loader.py` | Modify | Add tests for `no_data_context` |
| `backend/prompts/personas/history_uncle.yaml` | Modify | Add opening hint + `no_data_context` |
| `backend/prompts/personas/story_brother.yaml` | Modify | Add opening hint + `no_data_context` |
| `backend/prompts/personas/gossip_auntie.yaml` | Modify | Add opening hint + `no_data_context` |
| `backend/prompts/personas/kid_sister.yaml` | Modify | Add opening hint + `no_data_context` |
| `backend/prompts/personas/foodie.yaml` | Modify | Add opening hint + `no_data_context` |
| `backend/src/tour_guide/services/narration_service.py` | Modify | No-data short-circuit before LLM |
| `backend/tests/unit/test_narration_service.py` | Create | Tests for no-data short-circuit |
| `backend/src/tour_guide/services/poi_service.py` | Modify | Inject resolver, limit to 20 nodes, use resolver |
| `backend/src/tour_guide/main.py` | Modify | Wire `NominatimClient` + `WikipediaResolver` into DI |

---

## Task 1: Remove Flutter Map Markers

**Files:**
- Modify: `flutter_app/lib/features/map/screens/map_screen.dart`
- Delete: `flutter_app/lib/features/map/widgets/poi_marker.dart`

- [ ] **Step 1: Delete `poi_marker.dart`**

```bash
rm flutter_app/lib/features/map/widgets/poi_marker.dart
```

- [ ] **Step 2: Update `map_screen.dart`**

Remove lines 44–87 and replace with just the position watch. Also remove the import for `poi_marker.dart` and `poi_provider`'s `poiProvider` usage (keep `effectivePositionStreamProvider`).

Replace the entire `build()` method content with:

```dart
@override
Widget build(BuildContext context) {
  final position = ref.watch(
    effectivePositionStreamProvider.select((v) => v.valueOrNull),
  );

  ref.listen<AsyncValue<Position>>(
    effectivePositionStreamProvider,
    (_, next) => next.whenData(_centerOnPosition),
  );

  if (position != null) _centerOnPosition(position);

  final initialTarget = position != null
      ? LatLng(position.latitude, position.longitude)
      : const LatLng(0, 0);

  return Scaffold(
    appBar: AppBar(
      backgroundColor: const Color(0xFF0F3460),
      title: const Row(
        children: [
          Icon(Icons.circle, color: Color(0xFF4A9EFF), size: 12),
          SizedBox(width: 8),
          Text('旅程進行中', style: TextStyle(color: Colors.white)),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () async {
            await ref.read(sessionProvider.notifier).stop();
            if (context.mounted) context.pop();
          },
          child: const Text('結束', style: TextStyle(color: Colors.red)),
        ),
      ],
    ),
    body: Stack(
      children: [
        GoogleMap(
          initialCameraPosition: CameraPosition(
            target: initialTarget,
            zoom: 16,
          ),
          myLocationEnabled: true,
          myLocationButtonEnabled: true,
          onMapCreated: (c) {
            _mapController = c;
            if (position != null) _centerOnPosition(position);
          },
        ),
        const Align(
          alignment: Alignment.bottomCenter,
          child: NarrationSheet(),
        ),
        const Positioned(
          bottom: 100,
          left: 0,
          right: 0,
          child: Center(child: PushToTalkButton()),
        ),
      ],
    ),
  );
}
```

Also remove the import line for `poi_marker.dart`:
```dart
// Remove this line:
import 'package:flutter_app/features/map/widgets/poi_marker.dart';
```

And remove the import for `poi_provider.dart`'s unused `poiProvider` reference (keep the import since `effectivePositionStreamProvider` still comes from there).

- [ ] **Step 3: Verify Flutter build**

```bash
cd flutter_app && flutter analyze lib/features/map/
```

Expected: No errors referencing `poi_marker` or `poisAsync`.

- [ ] **Step 4: Commit**

```bash
git add flutter_app/lib/features/map/screens/map_screen.dart
git commit -m "feat: remove map markers — narration is auto-trigger only"
```

---

## Task 2: Relax POI Filter

**Files:**
- Modify: `backend/src/tour_guide/services/poi_filter.py`
- Modify: `backend/tests/unit/test_poi_filter.py`

**New rule:** Keep node if it has (`tourism` or `historic`) AND a non-empty `name` tag.

- [ ] **Step 1: Write failing tests for the new behavior**

In `backend/tests/unit/test_poi_filter.py`, add these new test cases to the existing `TestFilterPOINodes` class:

```python
def test_node_with_tourism_and_name_but_no_wiki_now_passes(self):
    """After relaxation: tourism+name node WITHOUT wiki tag should pass."""
    node = OsmNode(
        id="osm:node:99",
        lat=25.0,
        lon=121.5,
        tags={"name": "Local Museum", "tourism": "museum"},
    )
    result = filter_poi_nodes([node])
    assert len(result) == 1

def test_node_with_tourism_but_no_name_excluded(self):
    """Node with tourism but no name tag should be excluded."""
    node = OsmNode(
        id="osm:node:100",
        lat=25.0,
        lon=121.5,
        tags={"tourism": "museum"},
    )
    result = filter_poi_nodes([node])
    assert len(result) == 0
```

- [ ] **Step 2: Run to verify new tests fail**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_poi_filter.py::TestFilterPOINodes::test_node_with_tourism_and_name_but_no_wiki_now_passes -v
```

Expected: FAIL — `assert len(result) == 1` fails (currently 0)

- [ ] **Step 3: Update `poi_filter.py`**

Replace the entire file content:

```python
"""POI filter service for filtering nodes based on taxonomy and metadata."""

from tour_guide.models.poi import OsmNode

_ALLOWED_KEYS = {"tourism", "historic"}


def filter_poi_nodes(nodes: list[OsmNode]) -> list[OsmNode]:
    """Keep nodes that have an allowed tourism/historic tag AND a non-empty name.

    Args:
        nodes: List of OSM nodes to filter.

    Returns:
        List of nodes that have both:
        - At least one allowed key (tourism or historic)
        - A non-empty 'name' tag
    """
    result = []
    for node in nodes:
        has_allowed = any(k in _ALLOWED_KEYS for k in node.tags)
        has_name = bool(node.tags.get("name", "").strip())
        if has_allowed and has_name:
            result.append(node)
    return result
```

- [ ] **Step 4: Update stale tests that described the OLD wikidata requirement**

In `test_poi_filter.py`, update `test_node_with_tourism_but_no_wiki_excluded` — this test described old behavior. Replace it:

```python
def test_node_with_tourism_but_no_wiki_excluded(self):
    """Node with tourism=museum but NO name tag should be excluded (no wiki needed)."""
    node = OsmNode(
        id="osm:node:2",
        lat=25.0455,
        lon=121.5681,
        tags={"tourism": "museum"},  # no name tag
    )
    result = filter_poi_nodes([node])
    assert len(result) == 0
```

Also update `test_mixed_nodes_filtering` — the `invalid_no_wiki` node now has a `tourism` tag but no `name`, and `invalid_no_category` is still excluded. Update to:

```python
def test_mixed_nodes_filtering(self):
    """Test filtering with a mix of valid and invalid nodes."""
    valid_museum = OsmNode(
        id="osm:node:10",
        lat=25.0,
        lon=121.5,
        tags={"name": "Some Museum", "tourism": "museum"},
    )
    invalid_no_name = OsmNode(
        id="osm:node:11",
        lat=25.0,
        lon=121.5,
        tags={"tourism": "cafe"},  # no name tag
    )
    invalid_no_category = OsmNode(
        id="osm:node:12",
        lat=25.0,
        lon=121.5,
        tags={"name": "Bookstore", "shop": "book"},  # no tourism/historic
    )
    valid_historic = OsmNode(
        id="osm:node:13",
        lat=25.0,
        lon=121.5,
        tags={"name": "Old Castle", "historic": "castle"},
    )

    result = filter_poi_nodes([valid_museum, invalid_no_name, invalid_no_category, valid_historic])

    assert len(result) == 2
    assert valid_museum in result
    assert valid_historic in result
    assert invalid_no_name not in result
    assert invalid_no_category not in result
```

- [ ] **Step 5: Run all filter tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_poi_filter.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/services/poi_filter.py backend/tests/unit/test_poi_filter.py
git commit -m "feat: relax POI filter — require name tag instead of wikidata"
```

---

## Task 3: Add `WikipediaClient.search()` Method

**Files:**
- Modify: `backend/src/tour_guide/clients/wikipedia.py`
- Create: `backend/tests/unit/test_wikipedia_client.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/test_wikipedia_client.py`:

```python
"""Tests for WikipediaClient.search() method."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tour_guide.clients.wikipedia import WikipediaClient


class TestWikipediaClientSearch:
    """Tests for WikipediaClient.search()."""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_search_returns_first_title_on_match(self, mock_client):
        """search() returns the first title from opensearch results."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            "故宮博物院",
            ["國立故宮博物院", "故宮博物院 (北京)"],
            ["", ""],
            ["https://zh.wikipedia.org/...", "https://zh.wikipedia.org/..."],
        ]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        result = await client.search("故宮博物院", "zh-TW")

        assert result == "國立故宮博物院"

    @pytest.mark.asyncio
    async def test_search_returns_none_when_no_results(self, mock_client):
        """search() returns None when opensearch returns no titles."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["xyz", [], [], []]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        result = await client.search("NoSuchPlace", "zh-TW")

        assert result is None

    @pytest.mark.asyncio
    async def test_search_maps_zh_tw_to_zh_subdomain(self, mock_client):
        """search() maps zh-TW to zh subdomain."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["q", ["Title"], [""], [""]]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        await client.search("query", "zh-TW")

        call_url = mock_client.get.call_args[0][0]
        assert "zh.wikipedia.org" in call_url

    @pytest.mark.asyncio
    async def test_search_uses_opensearch_action(self, mock_client):
        """search() calls the opensearch API action."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = ["q", [], [], []]
        mock_client.get.return_value = mock_response

        client = WikipediaClient(client=mock_client)
        await client.search("query", "en")

        params = mock_client.get.call_args[1]["params"]
        assert params["action"] == "opensearch"
        assert params["search"] == "query"
        assert params["limit"] == "1"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_wikipedia_client.py -v
```

Expected: `AttributeError: 'WikipediaClient' object has no attribute 'search'`

- [ ] **Step 3: Add `search()` to `WikipediaClient`**

In `backend/src/tour_guide/clients/wikipedia.py`, add this method to the `WikipediaClient` class (after the `geosearch` method):

```python
async def search(self, query: str, lang: str) -> str | None:
    """Search Wikipedia by query string, return the first matching article title.

    Uses the Wikipedia opensearch API to find article titles matching the query.

    Args:
        query: Search term (e.g. "故宮博物院" or "故宮博物院，大安區")
        lang: Language code (e.g. "zh-TW", "en")

    Returns:
        First matching article title, or None if no results found.
    """
    wiki_lang = _LANG_MAP.get(lang, lang)
    url = f"https://{wiki_lang}.wikipedia.org/w/api.php"
    resp = await self._client.get(url, params={
        "action": "opensearch",
        "search": query,
        "limit": "1",
        "redirects": "resolve",
        "format": "json",
    })
    resp.raise_for_status()
    data = resp.json()
    titles = data[1] if len(data) > 1 else []
    return titles[0] if titles else None
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_wikipedia_client.py -v
```

Expected: All 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/clients/wikipedia.py backend/tests/unit/test_wikipedia_client.py
git commit -m "feat: add WikipediaClient.search() for opensearch-based lookup"
```

---

## Task 4: Create `NominatimClient`

**Files:**
- Create: `backend/src/tour_guide/clients/nominatim.py`
- Create: `backend/tests/unit/test_nominatim_client.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_nominatim_client.py`:

```python
"""Tests for NominatimClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from tour_guide.clients.nominatim import NominatimAddress, NominatimClient


class TestNominatimClientReverse:
    """Tests for NominatimClient.reverse()."""

    @pytest.fixture
    def mock_http(self):
        return AsyncMock()

    @pytest.mark.asyncio
    async def test_reverse_parses_suburb_and_city(self, mock_http):
        """reverse() parses suburb and city from Nominatim response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "address": {"suburb": "大安區", "city": "台北市"}
        }
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(25.04, 121.53)

        assert result is not None
        assert result.suburb == "大安區"
        assert result.city == "台北市"

    @pytest.mark.asyncio
    async def test_reverse_uses_borough_as_suburb_fallback(self, mock_http):
        """reverse() falls back to borough when suburb is absent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "address": {"borough": "Brooklyn", "city": "New York City"}
        }
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(40.65, -73.95)

        assert result is not None
        assert result.suburb == "Brooklyn"
        assert result.city == "New York City"

    @pytest.mark.asyncio
    async def test_reverse_uses_town_as_city_fallback(self, mock_http):
        """reverse() falls back to town when city is absent."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "address": {"suburb": "West End", "town": "Small Town"}
        }
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(51.5, -1.8)

        assert result is not None
        assert result.city == "Small Town"

    @pytest.mark.asyncio
    async def test_reverse_returns_none_on_http_error(self, mock_http):
        """reverse() returns None when HTTP call raises an exception."""
        mock_http.get.side_effect = Exception("Network error")

        client = NominatimClient(client=mock_http)
        result = await client.reverse(25.04, 121.53)

        assert result is None

    @pytest.mark.asyncio
    async def test_reverse_returns_none_on_non_200(self, mock_http):
        """reverse() returns None when status code is not 200."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_http.get.return_value = mock_response

        client = NominatimClient(client=mock_http)
        result = await client.reverse(25.04, 121.53)

        assert result is None
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_nominatim_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'tour_guide.clients.nominatim'`

- [ ] **Step 3: Create `backend/src/tour_guide/clients/nominatim.py`**

```python
"""Nominatim reverse geocoding client for OSM address lookup."""

from dataclasses import dataclass

import httpx


@dataclass
class NominatimAddress:
    suburb: str | None
    city_district: str | None
    city: str | None
    town: str | None
    village: str | None


class NominatimClient:
    BASE_URL = "https://nominatim.openstreetmap.org/reverse"

    def __init__(self, client: httpx.AsyncClient | None = None):
        self._client = client or httpx.AsyncClient(
            headers={"User-Agent": "ai-tour-guide/1.0"}
        )

    async def reverse(self, lat: float, lon: float) -> NominatimAddress | None:
        """Reverse geocode lat/lon to an address.

        Args:
            lat: Latitude
            lon: Longitude

        Returns:
            NominatimAddress with suburb and city fields, or None on any error.
        """
        try:
            resp = await self._client.get(
                self.BASE_URL,
                params={"lat": lat, "lon": lon, "format": "json", "zoom": 14},
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            address = data.get("address", {})
            return NominatimAddress(
                suburb=address.get("suburb") or address.get("borough"),
                city_district=address.get("city_district"),
                city=address.get("city") or address.get("town") or address.get("village"),
                town=address.get("town"),
                village=address.get("village"),
            )
        except Exception:
            return None
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_nominatim_client.py -v
```

Expected: All 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/clients/nominatim.py backend/tests/unit/test_nominatim_client.py
git commit -m "feat: add NominatimClient for reverse geocoding"
```

---

## Task 5: Create `WikipediaResolver`

**Files:**
- Create: `backend/src/tour_guide/services/wikipedia_resolver.py`
- Create: `backend/tests/unit/test_wikipedia_resolver.py`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/unit/test_wikipedia_resolver.py`:

```python
"""Tests for WikipediaResolver fallback chain."""

import pytest
from unittest.mock import AsyncMock

from tour_guide.clients.nominatim import NominatimAddress, NominatimClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import WikiArticle
from tour_guide.services.wikipedia_resolver import WikipediaResolver


@pytest.fixture
def mock_wikipedia():
    return AsyncMock(spec=WikipediaClient)


@pytest.fixture
def mock_nominatim():
    return AsyncMock(spec=NominatimClient)


@pytest.fixture
def resolver(mock_wikipedia, mock_nominatim):
    return WikipediaResolver(wikipedia=mock_wikipedia, nominatim=mock_nominatim)


_SAMPLE_ARTICLE = WikiArticle(title="故宮", extract="故宮的歷史...", url="", lang="zh-TW")


class TestWikipediaResolverDirectSearch:
    @pytest.mark.asyncio
    async def test_direct_name_match_returns_article(self, resolver, mock_wikipedia, mock_nominatim):
        """If direct poi_name search succeeds, return the article without calling Nominatim."""
        mock_wikipedia.search.return_value = "國立故宮博物院"
        mock_wikipedia.summary.return_value = _SAMPLE_ARTICLE

        result = await resolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")

        assert result == _SAMPLE_ARTICLE
        mock_nominatim.reverse.assert_not_called()

    @pytest.mark.asyncio
    async def test_direct_search_with_no_title_moves_to_next_level(self, resolver, mock_wikipedia, mock_nominatim):
        """If poi_name search returns no title, call Nominatim and continue."""
        mock_wikipedia.search.return_value = None
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb=None, city_district=None, city=None, town=None, village=None
        )

        result = await resolver.resolve("Unknown Place", 25.04, 121.56, "zh-TW")

        assert result is None
        mock_nominatim.reverse.assert_called_once()


class TestWikipediaResolverSuburbFallback:
    @pytest.mark.asyncio
    async def test_suburb_fallback_used_when_direct_fails(self, resolver, mock_wikipedia, mock_nominatim):
        """Falls back to 'poi_name，suburb' when direct search fails."""
        mock_wikipedia.search.side_effect = [None, "故宮博物院"]
        mock_wikipedia.summary.return_value = _SAMPLE_ARTICLE
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb="大安區", city_district=None, city="台北市", town=None, village=None
        )

        result = await resolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")

        assert result == _SAMPLE_ARTICLE
        assert mock_wikipedia.search.call_count == 2
        second_query = mock_wikipedia.search.call_args_list[1][0][0]
        assert "大安區" in second_query

    @pytest.mark.asyncio
    async def test_suburb_skipped_when_none(self, resolver, mock_wikipedia, mock_nominatim):
        """If suburb is None, skip suburb search and try city."""
        mock_wikipedia.search.side_effect = [None, "故宮，台北市"]
        mock_wikipedia.summary.return_value = _SAMPLE_ARTICLE
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb=None, city_district=None, city="台北市", town=None, village=None
        )

        result = await resolver.resolve("故宮博物院", 25.04, 121.56, "zh-TW")

        assert result == _SAMPLE_ARTICLE
        second_query = mock_wikipedia.search.call_args_list[1][0][0]
        assert "台北市" in second_query


class TestWikipediaResolverCityFallback:
    @pytest.mark.asyncio
    async def test_city_fallback_used_when_suburb_fails(self, resolver, mock_wikipedia, mock_nominatim):
        """Falls back to 'poi_name，city' when suburb search also fails."""
        mock_wikipedia.search.side_effect = [None, None, "Brooklyn Bridge"]
        mock_wikipedia.summary.return_value = WikiArticle(
            title="Brooklyn Bridge", extract="...", url="", lang="en"
        )
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb="Brooklyn", city_district=None, city="New York City", town=None, village=None
        )

        result = await resolver.resolve("Brooklyn Bridge", 40.71, -73.99, "en")

        assert result is not None
        assert mock_wikipedia.search.call_count == 3
        city_query = mock_wikipedia.search.call_args_list[2][0][0]
        assert "New York City" in city_query


class TestWikipediaResolverAllFail:
    @pytest.mark.asyncio
    async def test_returns_none_when_all_levels_fail(self, resolver, mock_wikipedia, mock_nominatim):
        """Returns None when all fallback levels fail."""
        mock_wikipedia.search.return_value = None
        mock_nominatim.reverse.return_value = NominatimAddress(
            suburb="大安區", city_district=None, city="台北市", town=None, village=None
        )

        result = await resolver.resolve("Unknown Place", 25.04, 121.56, "zh-TW")

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_when_nominatim_fails(self, resolver, mock_wikipedia, mock_nominatim):
        """Returns None when Nominatim returns None (network error)."""
        mock_wikipedia.search.return_value = None
        mock_nominatim.reverse.return_value = None

        result = await resolver.resolve("Some Place", 25.04, 121.56, "zh-TW")

        assert result is None
        assert mock_wikipedia.search.call_count == 1
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_wikipedia_resolver.py -v
```

Expected: `ModuleNotFoundError: No module named 'tour_guide.services.wikipedia_resolver'`

- [ ] **Step 3: Create `backend/src/tour_guide/services/wikipedia_resolver.py`**

```python
"""WikipediaResolver: multi-level fallback chain for Wikipedia article lookup."""

from tour_guide.clients.nominatim import NominatimClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.models.poi import WikiArticle


class WikipediaResolver:
    """Resolve a POI name to a Wikipedia article via a 4-level fallback chain.

    Fallback order:
    1. Direct search by poi_name
    2. Search by "poi_name，suburb" (via Nominatim reverse geocoding)
    3. Search by "poi_name，city" (via Nominatim reverse geocoding)
    4. Return None — caller handles the no-data case
    """

    def __init__(self, wikipedia: WikipediaClient, nominatim: NominatimClient) -> None:
        self._wikipedia = wikipedia
        self._nominatim = nominatim

    async def resolve(
        self, poi_name: str, lat: float, lon: float, lang: str
    ) -> WikiArticle | None:
        """Find a Wikipedia article for the given POI, using progressively broader search terms.

        Args:
            poi_name: The landmark name to look up.
            lat: Latitude of the POI (used for reverse geocoding).
            lon: Longitude of the POI (used for reverse geocoding).
            lang: Language code (e.g. "zh-TW", "en").

        Returns:
            WikiArticle if any level finds a result, otherwise None.
        """
        # Level 1: direct POI name
        article = await self._fetch(poi_name, lang)
        if article:
            return article

        # Reverse geocode once for levels 2 and 3
        address = await self._nominatim.reverse(lat, lon)
        if address is None:
            return None

        suburb = address.suburb or address.city_district
        city = address.city or address.town or address.village

        # Level 2: poi_name + suburb/district
        if suburb:
            article = await self._fetch(f"{poi_name}，{suburb}", lang)
            if article:
                return article

        # Level 3: poi_name + city
        if city:
            article = await self._fetch(f"{poi_name}，{city}", lang)
            if article:
                return article

        return None

    async def _fetch(self, query: str, lang: str) -> WikiArticle | None:
        title = await self._wikipedia.search(query, lang)
        if not title:
            return None
        return await self._wikipedia.summary(title, lang)
```

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_wikipedia_resolver.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/wikipedia_resolver.py backend/tests/unit/test_wikipedia_resolver.py
git commit -m "feat: add WikipediaResolver with 4-level Wikipedia fallback chain"
```

---

## Task 6: Add `no_data_context` to `PersonaConfig`

**Files:**
- Modify: `backend/src/tour_guide/models/persona.py`
- Modify: `backend/src/tour_guide/prompts/loader.py`
- Modify: `backend/tests/unit/test_persona_loader.py`

- [ ] **Step 1: Write failing test**

Add to `backend/tests/unit/test_persona_loader.py` (in the `TestPersonaLoaderLoad` class or as a new class):

```python
class TestPersonaLoaderNoDataContext:
    """Tests for no_data_context field parsing."""

    def test_persona_without_no_data_context_defaults_to_empty_dict(self, tmp_path):
        """YAML without no_data_context should default to empty dict."""
        yaml_content = """
id: minimal_test
display_name:
  zh-TW: 測試
  en: Test
voice:
  zh-TW: zh-TW-YunJheNeural
  en: en-US-GuyNeural
voice_style:
  speaking_rate: 1.0
  emotion: neutral
style_profile:
  embellishment: 0.0
  preferred_topics: []
poi_source: osm_wikipedia
system_prompt:
  zh-TW: 你是測試
  en: You are test
narration_template:
  zh-TW: "narrate {poi_name} {poi_context} {target_length}"
  en: "narrate {poi_name} {poi_context} {target_length}"
qa_template:
  zh-TW: "answer"
  en: "answer"
"""
        yaml_file = tmp_path / "minimal_test.yaml"
        yaml_file.write_text(yaml_content)
        from tour_guide.prompts.loader import PersonaLoader
        config = PersonaLoader.load_from_path(yaml_file)
        assert config.no_data_context == {}

    def test_persona_with_no_data_context_loaded_correctly(self, tmp_path):
        """YAML with no_data_context should parse zh-TW and en values."""
        yaml_content = """
id: context_test
display_name:
  zh-TW: 測試
  en: Test
voice:
  zh-TW: zh-TW-YunJheNeural
  en: en-US-GuyNeural
voice_style:
  speaking_rate: 1.0
  emotion: neutral
style_profile:
  embellishment: 0.0
  preferred_topics: []
poi_source: osm_wikipedia
system_prompt:
  zh-TW: 你是測試
  en: You are test
narration_template:
  zh-TW: "narrate {poi_name} {poi_context} {target_length}"
  en: "narrate {poi_name} {poi_context} {target_length}"
qa_template:
  zh-TW: "answer"
  en: "answer"
no_data_context:
  zh-TW: "這附近我也不太熟！"
  en: "I don't know this area well!"
"""
        yaml_file = tmp_path / "context_test.yaml"
        yaml_file.write_text(yaml_content)
        from tour_guide.prompts.loader import PersonaLoader
        config = PersonaLoader.load_from_path(yaml_file)
        assert config.no_data_context["zh-TW"] == "這附近我也不太熟！"
        assert config.no_data_context["en"] == "I don't know this area well!"
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_persona_loader.py::TestPersonaLoaderNoDataContext -v
```

Expected: `AttributeError: 'PersonaConfig' object has no attribute 'no_data_context'`

- [ ] **Step 3: Add `no_data_context` to `PersonaConfig`**

In `backend/src/tour_guide/models/persona.py`, add the field to `PersonaConfig`:

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
    default_trigger_radius_m: int = 100
    no_data_context: dict[str, str] = field(default_factory=dict)
```

- [ ] **Step 4: Update `loader.py` to parse `no_data_context`**

In `backend/src/tour_guide/prompts/loader.py`, update the `_parse()` function to pass `no_data_context` to the `PersonaConfig` constructor. Change the `return PersonaConfig(...)` block:

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
    no_data_context=dict(data.get("no_data_context") or {}),
)
```

- [ ] **Step 5: Run all persona loader tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_persona_loader.py -v
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/models/persona.py backend/src/tour_guide/prompts/loader.py backend/tests/unit/test_persona_loader.py
git commit -m "feat: add no_data_context field to PersonaConfig"
```

---

## Task 7: Update All 5 Persona YAMLs

**Files:**
- Modify: `backend/prompts/personas/history_uncle.yaml`
- Modify: `backend/prompts/personas/story_brother.yaml`
- Modify: `backend/prompts/personas/gossip_auntie.yaml`
- Modify: `backend/prompts/personas/kid_sister.yaml`
- Modify: `backend/prompts/personas/foodie.yaml`

- [ ] **Step 1: Update `history_uncle.yaml`**

Append to the `narration_template.zh-TW` value (inside the existing YAML block) and add `no_data_context`:

```yaml
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用歷史大叔的風格，以繁體中文撰寫一段約{target_length}字的旁白，語氣親切、充滿故事性。

    開頭規則：直接進入歷史敘述（例如：「這塊地，百年前還是...」、「你腳下踩的這條路...」），不得以任何問候語（哈囉、歡迎、大家好）或自我介紹開頭。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The History Uncle, warm and storytelling.

    Opening rule: Start directly with a historical statement (e.g., "A century ago, this ground..."), never with a greeting or self-introduction.
no_data_context:
  zh-TW: 這個地方的史料我手頭上不多，等到下一個景點再好好說。
  en: I don't have much on this spot — let's save it for the next one.
```

- [ ] **Step 2: Update `story_brother.yaml`**

```yaml
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用故事大哥哥的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    語氣活潑熱情，可以加入想像的細節讓故事更生動，但主要事實需符合資料。

    開頭規則：直接以場景動作句開始（例如：「請轉頭看看你身後的______」、「你知道你剛剛踩過的地方嗎？」），嚴禁任何問候語（哈囉、大家好、各位朋友等）。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Storyteller.
    Be lively and enthusiastic, adding vivid details to bring the story to life.

    Opening rule: Start directly with a scene-action sentence (e.g., "Turn around and look at..."), never with a greeting.
no_data_context:
  zh-TW: 這附近大哥哥也不太熟，不過等一下後面的景點肯定更精彩！
  en: Hmm, I don't know much about this spot — but the next one's going to be great!
```

- [ ] **Step 3: Update `gossip_auntie.yaml`**

```yaml
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用八卦阿姨的風格，以繁體中文撰寫一段約{target_length}字的旁白。語氣神秘，偏好人物軼事、背後秘辛。

    開頭規則：直接以小聲透露的語氣開始（例如：「欸，你知道這裡背後...」、「靠過來一點，阿姨偷偷告訴你...」），不得打招呼或自我介紹。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Gossip Auntie. Keep the mysterious, whispered tone and focus on behind-the-scenes stories.

    Opening rule: Start directly with a conspiratorial whisper (e.g., "Psst, come closer..."), never with a greeting.
no_data_context:
  zh-TW: 欸，這個地方阿姨打聽不到什麼八卦，等等再說！
  en: Hmm, I couldn't dig up any gossip here — let's move on and see what's next!
```

- [ ] **Step 4: Update `kid_sister.yaml`**

```yaml
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用童趣小妹的風格，以繁體中文撰寫一段約{target_length}字的旁白。語氣簡單易懂、充滿好奇心，適合大小朋友。

    開頭規則：直接以好奇的觀察句開始（例如：「哇，你有沒有注意到______？」、「你看你看！這裡有個很特別的______！」），不得打招呼。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of Kid Sister. Keep it simple, curious, and fun for all ages.

    Opening rule: Start directly with a curious observation (e.g., "Hey, did you notice...?"), never with a greeting.
no_data_context:
  zh-TW: 咦，這裡小妹妹也沒查到什麼資料耶，繼續往前走吧！
  en: Hmm, I couldn't find anything about this place — let's keep walking!
```

- [ ] **Step 5: Update `foodie.yaml`**

```yaml
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用美食家的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    著重挖掘這個地方的飲食文化、歷史與在地特色，語氣溫暖熱情。

    開頭規則：直接從感官描述開始（例如：「聞到了嗎？這附近的空氣飄著______的香氣」、「你看這家店的招牌...」），不得打招呼。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Foodie.
    Focus on the food culture, history, and local character. Keep the tone warm and enthusiastic.

    Opening rule: Start directly with sensory description (e.g., "Can you smell that?"), never with a greeting.
no_data_context:
  zh-TW: 這裡好像沒什麼值得特別介紹的，等等前面有好料！
  en: Nothing much to say about this spot — better things ahead, I promise!
```

- [ ] **Step 6: Verify all persona YAMLs load without errors**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls -v
```

Expected: All 5 parametrized tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/prompts/personas/
git commit -m "feat: add opening rules and no_data_context to all persona YAMLs"
```

---

## Task 8: Add No-Data Short-Circuit to `NarrationService`

**Files:**
- Modify: `backend/src/tour_guide/services/narration_service.py`
- Create: `backend/tests/unit/test_narration_service.py`

- [ ] **Step 1: Write failing test**

Create `backend/tests/unit/test_narration_service.py`:

```python
"""Tests for NarrationService no-data short-circuit."""

import pytest
from dataclasses import field
from unittest.mock import AsyncMock, patch

from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
from tour_guide.models.poi import OsmNode, POIContext
from tour_guide.services.narration_service import (
    AudioEvent,
    EndEvent,
    MetaEvent,
    NarrationService,
    TextEvent,
)


@pytest.fixture
def fake_persona():
    return PersonaConfig(
        id="test_persona",
        display_name={"zh-TW": "測試"},
        voice={"zh-TW": "zh-TW-YunJheNeural"},
        voice_style=VoiceStyle(speaking_rate=1.0, emotion="neutral"),
        style_profile=StyleProfile(embellishment=0.0, preferred_topics=[]),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是測試"},
        narration_template={"zh-TW": "narrate {poi_name} {poi_context} {target_length}"},
        qa_template={"zh-TW": "answer"},
        no_data_context={"zh-TW": "這附近大哥哥也不太熟！"},
    )


@pytest.fixture
def poi_no_wiki():
    osm = OsmNode(
        id="osm:node:1",
        lat=25.04,
        lon=121.53,
        tags={"name": "Unknown Place", "tourism": "attraction"},
    )
    return POIContext(osm=osm, wiki=None)


@pytest.mark.asyncio
async def test_no_data_short_circuit_skips_llm(fake_persona, poi_no_wiki):
    """When wiki is None and no_data_context exists, LLM is not called."""
    fake_llm = AsyncMock()
    fake_tts = AsyncMock()
    fake_tts.synthesize.return_value = aiter_bytes(b"audio_data")

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi_no_wiki, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    fake_llm.chat_stream.assert_not_called()
    assert any(isinstance(e, TextEvent) for e in events)
    assert any(isinstance(e, AudioEvent) for e in events)
    assert any(isinstance(e, EndEvent) for e in events)


@pytest.mark.asyncio
async def test_no_data_short_circuit_uses_no_data_text(fake_persona, poi_no_wiki):
    """The TextEvent chunk should be the no_data_context text."""
    fake_llm = AsyncMock()
    fake_tts = AsyncMock()
    fake_tts.synthesize.return_value = aiter_bytes(b"audio_data")

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi_no_wiki, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    text_events = [e for e in events if isinstance(e, TextEvent)]
    assert len(text_events) == 1
    assert text_events[0].chunk == "這附近大哥哥也不太熟！"


@pytest.mark.asyncio
async def test_no_data_fallback_not_triggered_when_wiki_exists(fake_persona):
    """When wiki is present, normal LLM path is used (LLM is called)."""
    from tour_guide.models.poi import WikiArticle
    osm = OsmNode(id="osm:node:2", lat=25.0, lon=121.5, tags={"name": "故宮", "tourism": "museum"})
    wiki = WikiArticle(title="故宮", extract="故宮是...", url="", lang="zh-TW")
    poi = POIContext(osm=osm, wiki=wiki)

    fake_llm = AsyncMock()
    fake_llm.chat_stream.return_value = aiter_str(["故宮", "是一個", "博物館。"])
    fake_tts = AsyncMock()
    fake_tts.synthesize.return_value = aiter_bytes(b"audio_data")

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    fake_llm.chat_stream.assert_called_once()


# Helpers to create async iterators for mocking
async def aiter_bytes(data: bytes):
    yield data


async def aiter_str(chunks: list[str]):
    for chunk in chunks:
        yield chunk
```

- [ ] **Step 2: Run to verify it fails**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_narration_service.py -v
```

Expected: `TypeError` or assertion errors — `no_data_context` not yet used.

- [ ] **Step 3: Update `narration_service.py`**

In `backend/src/tour_guide/services/narration_service.py`, make these two changes:

**Change A:** Move `voice_id` assignment from inside step 4 to right after the MetaEvent yield (step 2). In the existing code around line 128–145, change:

```python
# 2. Cache miss (or no cache / force_regenerate): run full pipeline
log_event(logger, LogEvents.NARRATION_START, poi_id=poi.osm.id, cache_hit=False)
yield MetaEvent(
    poi_id=poi.osm.id,
    cache_hit=False,
    confidence=confidence,
)

# 3. Build prompt messages
raw_messages = PromptBuilder.build(persona, poi, lang, length)
```

Replace with:

```python
# 2. Cache miss (or no cache / force_regenerate): run full pipeline
log_event(logger, LogEvents.NARRATION_START, poi_id=poi.osm.id, cache_hit=False)
yield MetaEvent(
    poi_id=poi.osm.id,
    cache_hit=False,
    confidence=confidence,
)

voice_id = persona.voice.get(lang, "Charon")

# 2b. No-data short-circuit: poi has no Wikipedia data — skip LLM entirely
if poi.wiki is None:
    no_data = persona.no_data_context.get(lang, "")
    if no_data:
        yield TextEvent(chunk=no_data, sentence_idx=0)
        audio_bytes = await self._synthesize_all(no_data, voice_id)
        yield AudioEvent(
            chunk_b64=base64.b64encode(audio_bytes).decode(),
            sentence_idx=0,
        )
        yield EndEvent()
        return

# 3. Build prompt messages
raw_messages = PromptBuilder.build(persona, poi, lang, length)
```

**Change B:** Remove the now-duplicate `voice_id` assignment inside step 4. Find and delete this line (around line 145 in the original):

```python
voice_id = persona.voice.get(lang, "Charon")
```

(It is inside the block that begins `# 4. Stream LLM → split sentences → TTS → yield events`)

- [ ] **Step 4: Run tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/test_narration_service.py -v
```

Expected: All 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/narration_service.py backend/tests/unit/test_narration_service.py
git commit -m "feat: skip LLM when no wiki data — TTS persona no_data_context directly"
```

---

## Task 9: Update `POIService` to Use `WikipediaResolver`

**Files:**
- Modify: `backend/src/tour_guide/services/poi_service.py`

- [ ] **Step 1: Add `resolver` parameter to `POIService.__init__()`**

In `backend/src/tour_guide/services/poi_service.py`, update the import and `__init__`:

Add import at the top:
```python
from tour_guide.services.wikipedia_resolver import WikipediaResolver
```

Update `__init__`:
```python
def __init__(
    self,
    overpass: OverpassClient,
    wikipedia: WikipediaClient,
    cache: POICache,
    google_places=None,
    resolver: WikipediaResolver | None = None,
):
    self._overpass = overpass
    self._wikipedia = wikipedia
    self._cache = cache
    self._google_places = google_places
    self._resolver = resolver
```

- [ ] **Step 2: Update `_nearby_osm()` to limit nodes and use resolver**

Replace the entire `_nearby_osm` method body after `filtered = filter_poi_nodes(raw_nodes)`:

```python
async def _nearby_osm(self, lat: float, lon: float, radius: int, lang: str) -> list[POI]:
    region_key = f"region:{lat:.3f}:{lon:.3f}:{radius}:{lang}"
    cached = self._cache.get(region_key)
    if cached is not None:
        log_event(logger, LogEvents.POI_CACHE_HIT, level="debug", key=region_key)
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
    try:
        raw_nodes = await self._overpass.query(bbox, _DEFAULT_TAG_FILTERS)
    except Exception as e:
        log_event(
            logger, LogEvents.UPSTREAM_FAIL,
            level="warning", service="overpass", error=type(e).__name__,
        )
        raw_nodes = await self._wikipedia.geosearch(lat, lon, radius, lang)
    filtered = filter_poi_nodes(raw_nodes)

    # Sort by distance and limit to 20 to avoid Wikipedia API floods
    filtered.sort(key=lambda n: _haversine(lat, lon, n.lat, n.lon))
    nearest = filtered[:20]

    pois: list[POI] = []
    for node in nearest:
        wiki_key = node.tags.get("wikipedia", "")
        wiki_title = wiki_key.split(":", 1)[-1] if ":" in wiki_key else wiki_key
        wiki_lang = wiki_key.split(":")[0] if ":" in wiki_key else lang

        wiki = None
        if wiki_title:
            try:
                wiki = await self._wikipedia.summary(wiki_title, wiki_lang)
            except Exception:
                log_event(
                    logger, LogEvents.UPSTREAM_FAIL,
                    level="warning", service="wiki", title=wiki_title, lang=wiki_lang,
                )

        if wiki is None and self._resolver is not None:
            poi_name = node.tags.get("name", "")
            if poi_name:
                try:
                    wiki = await self._resolver.resolve(poi_name, node.lat, node.lon, lang)
                except Exception:
                    log_event(
                        logger, LogEvents.UPSTREAM_FAIL,
                        level="warning", service="wiki_resolver", poi_name=poi_name,
                    )

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

    if pois:
        log_event(logger, LogEvents.POI_LOADED, count=len(pois), source="osm")
    else:
        log_event(logger, LogEvents.POI_EMPTY, level="warning", lat=lat, lon=lon, radius=radius)

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

- [ ] **Step 3: Run integration tests to verify `_nearby_osm` is not broken**

```bash
cd backend && .venv/bin/python -m pytest tests/integration/test_poi_service.py -v 2>&1 | head -30
```

(Integration tests hit real APIs — check they still collect/run without import errors at minimum.)

- [ ] **Step 4: Commit**

```bash
git add backend/src/tour_guide/services/poi_service.py
git commit -m "feat: inject WikipediaResolver into POIService, limit to 20 nodes"
```

---

## Task 10: Wire Up DI in `main.py`

**Files:**
- Modify: `backend/src/tour_guide/main.py`

- [ ] **Step 1: Add imports**

In `backend/src/tour_guide/main.py`, add two imports after the existing client imports:

```python
from tour_guide.clients.nominatim import NominatimClient
from tour_guide.services.wikipedia_resolver import WikipediaResolver
```

- [ ] **Step 2: Instantiate `NominatimClient` and `WikipediaResolver` in `create_app()`**

After `wikipedia_client = WikipediaClient(client=http_client)`, add:

```python
nominatim_client = NominatimClient(client=http_client)
wikipedia_resolver = WikipediaResolver(wikipedia=wikipedia_client, nominatim=nominatim_client)
```

- [ ] **Step 3: Pass `resolver` to `POIService`**

Update the `POIService(...)` constructor call:

```python
poi_service = POIService(
    overpass=overpass_client,
    wikipedia=wikipedia_client,
    cache=poi_cache,
    google_places=google_places_client,
    resolver=wikipedia_resolver,
)
```

- [ ] **Step 4: Verify the app starts**

```bash
cd backend && .venv/bin/python -c "from tour_guide.main import create_app; from tour_guide.config import AppConfig; app = create_app(AppConfig())"
```

Expected: No errors (may warn about missing env vars — that's OK).

- [ ] **Step 5: Run all unit tests**

```bash
cd backend && .venv/bin/python -m pytest tests/unit/ -q --ignore=tests/unit/test_sse.py --ignore=tests/unit/test_stt_provider.py --ignore=tests/unit/test_tts_provider.py
```

Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/src/tour_guide/main.py
git commit -m "feat: wire NominatimClient + WikipediaResolver into app DI"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered in task |
|-----------------|-----------------|
| Remove map markers from Flutter | Task 1 |
| Remove marker tap handler | Task 1 (markers removed entirely) |
| Relax OSM filter (no wikidata requirement) | Task 2 |
| Wikipedia search by POI name | Task 3 + Task 5 (level 1) |
| Wikipedia search by suburb | Task 5 (level 2) |
| Wikipedia search by city | Task 5 (level 3) |
| Verbal fallback when all levels fail | Task 6 + Task 7 + Task 8 |
| Persona-specific opening instruction in prompt | Task 7 |
| no_data_context per persona | Task 7 |
| No-data short-circuit in narration (skip LLM) | Task 8 |
| Limit to 20 nearest nodes | Task 9 |
| DI wiring | Task 10 |

**Placeholder scan:** No TBD, TODO, or incomplete steps found.

**Type consistency:**
- `WikipediaResolver.resolve()` defined in Task 5, used in Task 9 ✓
- `NominatimClient.reverse()` defined in Task 4, used in Task 5 ✓
- `WikipediaClient.search()` defined in Task 3, used in Task 5 ✓
- `PersonaConfig.no_data_context` defined in Task 6, used in Task 8 ✓
- `POIService(resolver=...)` defined in Task 9, wired in Task 10 ✓
