# Auto Narration & POI Improvement Design

**Date:** 2026-05-16
**Branch:** feat/plan-b-flutter-app-mvp

## Overview

Three targeted improvements to the narration and POI discovery experience:

1. **Remove map markers** — Narration is auto-triggered only; no tap interaction needed.
2. **Relax POI selection** — More landmarks become POIs by removing the OSM wikidata tag requirement.
3. **Wikipedia fallback chain** — When a landmark has no Wikipedia data, try progressively broader search terms before falling back to a persona-specific verbal response.
4. **Prompt opening style** — Each persona gets an instruction to open narrations with a scene-action sentence instead of a greeting.

---

## Problem Statement

- **Marker locations are wrong:** The OSM filter (`poi_filter.py`) requires nodes to have both a `tourism`/`historic` tag AND a `wikipedia`/`wikidata` tag. Many notable landmarks have the tourism tag but no `wikidata` tag in OSM, so they are silently dropped.
- **Marker tap is confusing:** Having both auto-trigger and tap-trigger creates inconsistency. The product direction is auto-trigger only.
- **Greeting openings:** The LLM sometimes opens narrations with "哈囉！各位大朋友小朋友" style greetings. We want it to jump straight into scene-action sentences.
- **Missing Wikipedia data is wasted:** When a POI name search returns nothing, the system gives up immediately instead of trying the landmark's district or city as a broader search context.

---

## Design

### 1. Remove Map Markers (Flutter)

**Files changed:**
- `flutter_app/lib/features/map/screens/map_screen.dart` — Remove the `markers` set building block (lines 58–87). Pass an empty `markers` set (or remove the parameter) to `GoogleMap`.
- `flutter_app/lib/features/map/widgets/poi_marker.dart` — Delete the file entirely (only contains marker color helpers, unused after this change).

`trigger_provider.dart` is untouched. Auto-trigger via distance + cooldown continues as before.

---

### 2. Relax OSM POI Filter (Backend)

**File changed:** `backend/src/tour_guide/services/poi_filter.py`

**Current rule:** Node must have (`tourism` or `historic`) AND (`wikipedia` or `wikidata`).

**New rule:** Node must have (`tourism` or `historic`) AND a non-empty `name` tag.

This allows landmarks with no OSM wikidata annotation to enter the pipeline. Wikipedia data is then fetched by name via the fallback chain (see §3).

---

### 3. Wikipedia Fallback Chain (Backend)

#### 3a. `WikipediaClient.search()` — New method

**File:** `backend/src/tour_guide/clients/wikipedia.py`

New method `search(query: str, lang: str) -> str | None`:
- Calls the Wikipedia opensearch API: `w/api.php?action=opensearch&search={query}&limit=1`
- Returns the first matching article title, or `None` if no results.

#### 3b. `NominatimClient` — New file

**File:** `backend/src/tour_guide/clients/nominatim.py`

```python
@dataclass
class NominatimAddress:
    suburb: str | None       # e.g. "大安區"
    city_district: str | None
    city: str | None          # e.g. "台北市"
    town: str | None
    village: str | None

class NominatimClient:
    async def reverse(self, lat: float, lon: float) -> NominatimAddress | None
```

- Calls: `https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&zoom=14`
- Returns a `NominatimAddress` with suburb and city fields populated from the response.
- Returns `None` on any network error.
- Uses `User-Agent: ai-tour-guide/1.0` header as required by Nominatim policy.

#### 3c. `WikipediaResolver` — New file

**File:** `backend/src/tour_guide/services/wikipedia_resolver.py`

```python
class WikipediaResolver:
    def __init__(self, wikipedia: WikipediaClient, nominatim: NominatimClient): ...

    async def resolve(self, poi_name: str, lat: float, lon: float, lang: str) -> WikiArticle | None:
```

Fallback order:
1. Search Wikipedia for `poi_name` → if title found, fetch summary
2. Reverse geocode (Nominatim) to get `suburb` / `city_district`
3. Search Wikipedia for `"{poi_name}，{suburb}"` (if suburb available)
4. Search Wikipedia for `"{poi_name}，{city}"` (if city available)
5. Return `None`

Each step calls `WikipediaClient.search()` to find a title, then `WikipediaClient.summary()` to fetch content. A step is skipped if the search term has no results.

#### 3d. `POIService._nearby_osm()` — Updated

**File:** `backend/src/tour_guide/services/poi_service.py`

Changes:
- Inject `WikipediaResolver` into `POIService.__init__()`.
- After filtering, sort by distance and take the **nearest 20 nodes** before Wikipedia lookups (prevents API flood on dense areas).
- Replace the direct `wikipedia.summary(wiki_tag_title)` call with:
  1. Try OSM `wikipedia` tag directly (existing behavior, if tag is present).
  2. If `wiki` is still `None`, call `WikipediaResolver.resolve(name, lat, lon, lang)`.

---

### 4. Prompt Opening Style + No-Data Fallback (Personas)

#### 4a. Each persona YAML — Two new fields

**Files:** `backend/prompts/personas/*.yaml`

**Field 1: Opening instruction added to `narration_template`**

Append to the zh-TW and en narration_template for each persona:

| Persona | Opening hint (zh-TW) |
|---------|----------------------|
| 故事大哥哥 | 開頭規則：直接以場景動作句開始（例如：「請轉頭看看你身後的______」、「你知道你剛剛踩過的地方...」），嚴禁任何問候語（哈囉、大家好等）。 |
| 歷史大叔 | 開頭規則：直接進入歷史敘述（例如：「這塊地，百年前還是...」），不得以問候語或自我介紹開頭。 |
| 童趣小妹 | 開頭規則：直接以好奇的觀察句開始（例如：「哇，你有沒有注意到______？」），不得打招呼。 |
| 八卦阿姨 | 開頭規則：直接以小聲透露的語氣開始（例如：「psst，靠過來一點...」或「欸，你知道這裡背後...」），不得打招呼。 |
| 美食家 | 開頭規則：直接從感官描述開始（例如：「聞到了嗎？」或「這裡的空氣裡飄著...」），不得打招呼。 |

**Field 2: `no_data_context`** — Pre-written verbal fallback when WikipediaResolver returns `None`

```yaml
no_data_context:
  zh-TW: "<persona-specific phrase>"
  en: "<persona-specific phrase>"
```

| Persona | no_data_context (zh-TW) |
|---------|--------------------------|
| 故事大哥哥 | 這附近大哥哥也不太熟，不過等一下後面的景點肯定更精彩！ |
| 歷史大叔 | 這個地方的史料我手頭上不多，等到下一個景點再好好說。 |
| 童趣小妹 | 咦，這裡小妹妹也沒查到什麼資料耶，繼續往前走吧！ |
| 八卦阿姨 | 欸，這個地方阿姨打聽不到什麼八卦，等等再說！ |
| 美食家 | 這裡好像沒什麼值得特別介紹的，等等前面有好料！ |

#### 4b. `PersonaConfig` — New field

**File:** `backend/src/tour_guide/models/persona.py`

Add `no_data_context: dict[str, str] = field(default_factory=dict)`.

#### 4c. `NarrationService.narrate()` — No-data short-circuit

**File:** `backend/src/tour_guide/services/narration_service.py`

After the cache check (step 1) and before building the LLM prompt (step 3), add:

```python
if poi.wiki is None:
    no_data = persona.no_data_context.get(lang, "")
    if no_data:
        voice_id = persona.voice.get(lang, "Charon")
        yield TextEvent(chunk=no_data, sentence_idx=0)
        audio_bytes = await self._synthesize_all(no_data, voice_id)
        yield AudioEvent(chunk_b64=base64.b64encode(audio_bytes).decode(), sentence_idx=0)
        yield EndEvent()
        return
```

This skips the LLM entirely when no Wikipedia data was found at any fallback level, playing the pre-written phrase directly.

---

## Data Flow (Updated)

```
User enters radius
  → Overpass: query tourism/historic nodes
  → poi_filter: keep nodes with name tag (relaxed)
  → Sort by distance, take top 20
  → For each node:
      Try OSM wikipedia tag → WikipediaClient.summary()
      If no wiki → WikipediaResolver.resolve():
          1. Search by poi_name
          2. Search by "poi_name，suburb" (Nominatim)
          3. Search by "poi_name，city"  (Nominatim)
          4. → None
  → POI list cached

Auto-trigger fires (user within 100m)
  → NarrationService.narrate():
      If wiki is None and no_data_context exists:
          → TTS(no_data_context) → stream events → done
      Else:
          → PromptBuilder (with opening_hint in template)
          → LLM stream → sentence split → TTS → events
```

---

## Files Changed Summary

| File | Change |
|------|--------|
| `flutter_app/lib/features/map/screens/map_screen.dart` | Remove markers building code |
| `flutter_app/lib/features/map/widgets/poi_marker.dart` | Delete |
| `backend/src/tour_guide/services/poi_filter.py` | Relax filter: remove wikidata requirement |
| `backend/src/tour_guide/clients/wikipedia.py` | Add `search()` method |
| `backend/src/tour_guide/clients/nominatim.py` | New: NominatimClient |
| `backend/src/tour_guide/services/wikipedia_resolver.py` | New: WikipediaResolver |
| `backend/src/tour_guide/services/poi_service.py` | Inject resolver, limit 20 nodes, use resolver |
| `backend/src/tour_guide/models/persona.py` | Add `no_data_context` field |
| `backend/src/tour_guide/services/narration_service.py` | No-data short-circuit before LLM |
| `backend/prompts/personas/*.yaml` (×5) | Add opening hint to template + `no_data_context` |

---

## Out of Scope

- Confidence scoring changes (still based on wiki extract length)
- Changing which OSM tag categories are included (still `tourism` + `historic` only)
- Foodie persona POI selection (unchanged, uses Google Places)
- Background narration / notification flow (unchanged)
