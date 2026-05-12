# Plan C — Persona 系統擴充 + 雙語旁白 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 AI Tour Guide 的 persona 從 1 個靜態「歷史大叔」擴充為 5 個可選角色，並支援旁白語言切換（zh-TW / en）。

**Architecture:** 後端新增 4 個 persona YAML 檔，透過既有 `PersonaLoader` 統一載入並在 startup 預載成 registry，`/narration` endpoint 改從 registry 取 persona 而非 inline hardcode。Flutter 端新增 `PersonaSelector` 垂直卡片 UI 和語言切換 SegmentedButton，`SessionNotifier` 新增 `setPersona`/`setLang`，`NarrationNotifier.narrate()` 改為接收 persona/lang 參數。

**Tech Stack:** Python/FastAPI/YAML (backend), Flutter/Riverpod/Dart (frontend)

---

## 檔案索引

| 動作 | 路徑 |
|---|---|
| 修改 | `backend/src/tour_guide/prompts/loader.py` |
| 修改 | `backend/src/tour_guide/api/narration.py` |
| 修改 | `backend/src/tour_guide/main.py` |
| 新增 | `backend/prompts/personas/story_brother.yaml` |
| 新增 | `backend/prompts/personas/gossip_auntie.yaml` |
| 新增 | `backend/prompts/personas/kid_sister.yaml` |
| 新增 | `backend/prompts/personas/foodie.yaml` |
| 修改 | `backend/tests/unit/test_persona_loader.py` |
| 修改 | `backend/tests/integration/test_narration_api.py` |
| 新增 | `flutter_app/lib/features/session/persona_data.dart` |
| 修改 | `flutter_app/lib/features/session/providers/session_provider.dart` |
| 新增 | `flutter_app/lib/features/session/widgets/persona_selector.dart` |
| 修改 | `flutter_app/lib/features/session/screens/home_screen.dart` |
| 修改 | `flutter_app/lib/features/narration/providers/narration_provider.dart` |
| 修改 | `flutter_app/lib/features/narration/providers/trigger_provider.dart` |
| 修改 | `flutter_app/test/unit/session_provider_test.dart` |
| 新增 | `flutter_app/test/widget/persona_selector_test.dart` |
| 修改 | `flutter_app/test/widget/home_screen_test.dart` |
| 修改 | `flutter_app/test/integration/narration_flow_test.dart` |
| 修改 | `flutter_app/test/unit/trigger_provider_test.dart` |

---

## Task 1: PersonaLoader.load_all() + 測試

**Files:**
- Modify: `backend/src/tour_guide/prompts/loader.py`
- Modify: `backend/tests/unit/test_persona_loader.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/unit/test_persona_loader.py` 末尾加入新的測試 class（保留既有測試不動）：

```python
class TestPersonaLoaderLoadAll:
    """Tests for PersonaLoader.load_all()."""

    def test_load_all_returns_dict_with_history_uncle(self):
        """load_all() should include history_uncle (the only YAML that exists so far)."""
        registry = PersonaLoader.load_all()
        assert "history_uncle" in registry
        assert isinstance(registry["history_uncle"], PersonaConfig)

    def test_load_all_returns_dict_keyed_by_id(self):
        """load_all() should key each persona by its id field."""
        registry = PersonaLoader.load_all()
        for persona_id, config in registry.items():
            assert config.id == persona_id

    def test_load_all_custom_dir_empty(self, tmp_path):
        """load_all() on empty directory returns empty dict."""
        registry = PersonaLoader.load_all(base_dir=tmp_path)
        assert registry == {}

    def test_load_all_custom_dir_with_yaml(self, tmp_path):
        """load_all() loads all YAML files from given directory."""
        yaml_content = """
id: test_persona
display_name:
  zh-TW: 測試
  en: Test
voice:
  zh-TW: Charon
  en: Charon
voice_style:
  speaking_rate: 1.0
  emotion: neutral
style_profile:
  embellishment: 0.0
  preferred_topics: []
poi_source: osm_wikipedia
system_prompt:
  zh-TW: 測試 prompt
  en: Test prompt
narration_template:
  zh-TW: "narrate {poi_name}"
  en: "narrate {poi_name}"
qa_template:
  zh-TW: "answer {question}"
  en: "answer {question}"
"""
        (tmp_path / "test_persona.yaml").write_text(yaml_content)
        registry = PersonaLoader.load_all(base_dir=tmp_path)
        assert "test_persona" in registry
        assert len(registry) == 1
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestPersonaLoaderLoadAll -v
```

Expected: `AttributeError: type object 'PersonaLoader' has no attribute 'load_all'`

- [ ] **Step 3: 實作 load_all()**

在 `backend/src/tour_guide/prompts/loader.py` 的 `PersonaLoader` class 末尾加入：

```python
    @classmethod
    def load_all(
        cls,
        base_dir: Path = _DEFAULT_PERSONAS_DIR,
    ) -> dict[str, "PersonaConfig"]:
        """Load all persona YAML files from base_dir.

        Returns:
            Dict mapping persona_id -> PersonaConfig for every .yaml file found.
            Skips non-YAML files. Empty dict if directory has no YAML files.
        """
        registry: dict[str, PersonaConfig] = {}
        for yaml_file in sorted(base_dir.glob("*.yaml")):
            config = cls.load_from_path(yaml_file)
            registry[config.id] = config
        return registry
```

- [ ] **Step 4: 確認測試通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py -v
```

Expected: 全部通過（含原有測試）

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/prompts/loader.py backend/tests/unit/test_persona_loader.py
git commit -m "feat(backend): add PersonaLoader.load_all() to load all persona YAMLs"
```

---

## Task 2: story_brother.yaml

**Files:**
- Create: `backend/prompts/personas/story_brother.yaml`
- Modify: `backend/tests/unit/test_persona_loader.py` (加 smoke test)

- [ ] **Step 1: 寫失敗 smoke test**

在 `TestPersonaLoaderLoadAll` 下方新增（保留既有 class，加新 class）：

```python
class TestAllPersonaYamls:
    """Smoke tests: each persona YAML loads without error."""

    @pytest.mark.parametrize("persona_id", [
        "history_uncle",
        "story_brother",
        "gossip_auntie",
        "kid_sister",
        "foodie",
    ])
    def test_persona_yaml_loads_successfully(self, persona_id):
        """Each persona YAML file should load without raising."""
        config = PersonaLoader.load(persona_id)
        assert config.id == persona_id
        assert "zh-TW" in config.system_prompt
        assert "en" in config.system_prompt
        assert "zh-TW" in config.narration_template
        assert "en" in config.narration_template
```

- [ ] **Step 2: 確認 story_brother 測試失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[story_brother] -v
```

Expected: `FileNotFoundError: Persona 'story_brother' not found`

- [ ] **Step 3: 建立 story_brother.yaml**

建立 `backend/prompts/personas/story_brother.yaml`：

```yaml
id: story_brother
display_name:
  zh-TW: 故事大哥哥
  en: The Storyteller
voice:
  zh-TW: Puck
  en: Puck
voice_style:
  speaking_rate: 1.05
  emotion: enthusiastic
style_profile:
  embellishment: 0.6
  preferred_topics:
    - folklore
    - local_legends
    - human_stories
poi_source: osm_wikipedia
system_prompt:
  zh-TW: |
    你是「故事大哥哥」，一位充滿活力的年輕導遊，擅長把歷史化成生動有趣的民間故事。
    你說話語速略快，充滿感情，喜歡用比喻和誇張讓景點活靈活現，偶爾帶點幽默。
    請用繁體中文進行旁白，語氣親切熱情，像在跟老朋友說故事。
  en: |
    You are "The Storyteller," an energetic young tour guide who brings history to life through vivid folk stories.
    You speak with enthusiasm, using metaphors and colorful descriptions to make every place come alive.
    Please narrate in English with a warm, lively tone, as if telling stories to a friend.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用故事大哥哥的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    語氣活潑熱情，可以加入想像的細節讓故事更生動，但主要事實需符合資料。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Storyteller.
    Be lively and enthusiastic, adding vivid details to bring the story to life.
qa_template:
  zh-TW: "請用故事大哥哥的風格，以繁體中文回答：{question}"
  en: "Please answer in the style of The Storyteller: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "哎呀，網路不給力，等我一下！"
    rate_limit:
      - "大哥哥說話太起勁，要稍微喘口氣，30 秒後繼續！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "關於這個地方，大哥哥知道的故事是這樣的..."
    low:
      - "這裡的史料不多，但大哥哥幫你腦補一下！"
```

- [ ] **Step 4: 確認測試通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[story_brother] -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add backend/prompts/personas/story_brother.yaml backend/tests/unit/test_persona_loader.py
git commit -m "feat(backend): add story_brother persona YAML"
```

---

## Task 3: gossip_auntie.yaml

**Files:**
- Create: `backend/prompts/personas/gossip_auntie.yaml`

- [ ] **Step 1: 確認測試失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[gossip_auntie] -v
```

Expected: `FileNotFoundError`

- [ ] **Step 2: 建立 gossip_auntie.yaml**

建立 `backend/prompts/personas/gossip_auntie.yaml`：

```yaml
id: gossip_auntie
display_name:
  zh-TW: 八卦阿姨
  en: The Gossip Auntie
voice:
  zh-TW: Aoede
  en: Aoede
voice_style:
  speaking_rate: 1.0
  emotion: conspiratorial
style_profile:
  embellishment: 0.5
  preferred_topics:
    - celebrity_stories
    - social_history
    - behind_the_scenes
poi_source: osm_wikipedia
system_prompt:
  zh-TW: |
    你是「八卦阿姨」，一位熱衷於分享名人軼事和背後秘辛的資深導遊。
    你說話生動有趣，語氣像是在分享獨家消息，讓人覺得自己知道了別人不知道的秘密。
    請用繁體中文進行旁白，語氣輕鬆活潑，像是在跟鄰居聊天。
  en: |
    You are "The Gossip Auntie," a well-connected tour guide who loves sharing stories about famous people and behind-the-scenes secrets.
    You speak as if sharing exclusive insider knowledge, making people feel they're learning secrets others don't know.
    Please narrate in English with a lively, conspiratorial tone.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用八卦阿姨的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    著重挖掘人物故事、社會脈絡，語氣輕鬆，讓人覺得在聽獨家八卦。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Gossip Auntie.
    Focus on personal stories, social dynamics, and insider details.
qa_template:
  zh-TW: "請用八卦阿姨的風格，以繁體中文回答：{question}"
  en: "Please answer in the style of The Gossip Auntie: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "哎，網路不給力，等阿姨一下，有更多八卦要跟你說！"
    rate_limit:
      - "說太多了要稍微停一停，30 秒後阿姨繼續跟你爆料！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "關於這個，阿姨聽說是這樣..."
    low:
      - "這個嘛，真實情況不太確定，但阿姨猜..."
```

- [ ] **Step 3: 確認測試通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[gossip_auntie] -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/prompts/personas/gossip_auntie.yaml
git commit -m "feat(backend): add gossip_auntie persona YAML"
```

---

## Task 4: kid_sister.yaml

**Files:**
- Create: `backend/prompts/personas/kid_sister.yaml`

- [ ] **Step 1: 確認測試失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[kid_sister] -v
```

Expected: `FileNotFoundError`

- [ ] **Step 2: 建立 kid_sister.yaml**

建立 `backend/prompts/personas/kid_sister.yaml`：

```yaml
id: kid_sister
display_name:
  zh-TW: 童趣小妹
  en: The Kid Sister
voice:
  zh-TW: Kore
  en: Kore
voice_style:
  speaking_rate: 1.0
  emotion: excited
style_profile:
  embellishment: 0.3
  preferred_topics:
    - fun_facts
    - sensory_details
    - nature
poi_source: osm_wikipedia
system_prompt:
  zh-TW: |
    你是「童趣小妹」，一位用孩子眼光看世界的年輕導遊，對任何事都充滿好奇和驚嘆。
    你說話簡單易懂，充滿童趣，喜歡問「你知道嗎？」然後分享驚奇的小知識。
    請用繁體中文進行旁白，語氣活潑可愛，讓人感受到探索的樂趣。
  en: |
    You are "The Kid Sister," a young guide who sees the world through curious, wide-eyed wonder.
    You speak simply and excitedly, always sharing surprising fun facts and asking "Did you know?"
    Please narrate in English with a lively, delightful tone that makes exploration feel magical.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用童趣小妹的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    語氣充滿好奇和驚嘆，分享有趣的小知識，讓人感受到探索的樂趣。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Kid Sister.
    Be curious and excited, sharing fun facts and making discovery feel magical.
qa_template:
  zh-TW: "請用童趣小妹的風格，以繁體中文回答：{question}"
  en: "Please answer in the style of The Kid Sister: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "等一下，網路不見了！我去找它回來！"
    rate_limit:
      - "哇，我說話說太快了，喘口氣，30 秒後繼續！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "我不是很確定，但我覺得應該是..."
    low:
      - "這個我也不太懂，但我們可以一起猜猜看！"
```

- [ ] **Step 3: 確認測試通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[kid_sister] -v
```

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add backend/prompts/personas/kid_sister.yaml
git commit -m "feat(backend): add kid_sister persona YAML"
```

---

## Task 5: foodie.yaml

**Files:**
- Create: `backend/prompts/personas/foodie.yaml`

- [ ] **Step 1: 確認測試失敗**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py::TestAllPersonaYamls::test_persona_yaml_loads_successfully[foodie] -v
```

Expected: `FileNotFoundError`

- [ ] **Step 2: 建立 foodie.yaml**

建立 `backend/prompts/personas/foodie.yaml`：

```yaml
id: foodie
display_name:
  zh-TW: 美食家
  en: The Foodie
voice:
  zh-TW: Leda
  en: Leda
voice_style:
  speaking_rate: 1.0
  emotion: warm
style_profile:
  embellishment: 0.4
  preferred_topics:
    - food_culture
    - local_cuisine
    - culinary_history
poi_source: osm_wikipedia
system_prompt:
  zh-TW: |
    你是「美食家」，一位以美食視角看世界的資深導遊，擅長發掘景點附近的飲食文化與在地美味。
    你說話溫暖熱情，喜歡用感官描述（味道、香氣、口感）讓旅程充滿味覺記憶。
    請用繁體中文進行旁白，語氣溫暖親切，讓人垂涎三尺。
  en: |
    You are "The Foodie," a seasoned guide who sees the world through the lens of food and culinary culture.
    You speak warmly and passionately, using sensory descriptions (taste, aroma, texture) to make journeys memorable.
    Please narrate in English with a warm, appetizing tone that makes people hungry for more.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點資訊：
    {poi_context}

    請用美食家的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    著重挖掘這個地方的飲食文化、歷史與在地特色，語氣溫暖熱情。
  en: |
    You are now narrating for "{poi_name}".

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in the style of The Foodie.
    Focus on the culinary culture, food history, and local flavors of this place.
qa_template:
  zh-TW: "請用美食家的風格，以繁體中文回答：{question}"
  en: "Please answer in the style of The Foodie: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "網路暫時斷了，就像等菜一樣，稍等片刻！"
    rate_limit:
      - "嘴巴說太多了，休息 30 秒消化一下！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "這個地方的資料不多，但美食家認為..."
    low:
      - "史料有限，純粹以美食家的直覺推測..."
```

- [ ] **Step 3: 確認所有 5 個 YAML 測試通過**

```bash
cd backend && .venv/bin/pytest tests/unit/test_persona_loader.py -v
```

Expected: 全部通過

- [ ] **Step 4: Commit**

```bash
git add backend/prompts/personas/foodie.yaml
git commit -m "feat(backend): add foodie persona YAML — all 5 personas complete"
```

---

## Task 6: 將 PersonaRegistry 接入 `/narration` endpoint + startup 預載

**Files:**
- Modify: `backend/src/tour_guide/api/narration.py`
- Modify: `backend/src/tour_guide/main.py`
- Modify: `backend/tests/integration/test_narration_api.py`

- [ ] **Step 1: 寫失敗測試**

在 `backend/tests/integration/test_narration_api.py` 的 `TestNarrationAPIValidation` class 末尾加入：

```python
    def test_unknown_persona_returns_400(self, client):
        """POST /narration with an unknown persona returns HTTP 400."""
        response = client.post(
            "/narration",
            json={
                "poi_id": "osm:node:123",
                "persona": "unknown_persona",
                "lang": "zh-TW",
                "length": "medium",
                "force_regenerate": False,
            },
        )
        assert response.status_code == 400
```

- [ ] **Step 2: 更新 test fixture 以注入 persona_registry**

在 `test_narration_api.py` 頂部的 imports 加入：

```python
from tour_guide.api.narration import get_narration_service, get_persona_registry, router
from tour_guide.models.persona import PersonaConfig, StyleProfile, VoiceStyle
```

（原本只有 `get_narration_service, router`，加入 `get_persona_registry`）

加入 `_FAKE_REGISTRY` 常數（在 `FakeNarrationService` 定義之前）：

```python
_FAKE_REGISTRY: dict = {
    "history_uncle": PersonaConfig(
        id="history_uncle",
        display_name={"zh-TW": "歷史大叔", "en": "The History Uncle"},
        voice={"zh-TW": "Charon", "en": "Charon"},
        voice_style=VoiceStyle(speaking_rate=0.95, emotion="contemplative"),
        style_profile=StyleProfile(embellishment=0.1, preferred_topics=["history"]),
        poi_source="osm_wikipedia",
        system_prompt={"zh-TW": "你是歷史大叔。", "en": "You are The History Uncle."},
        narration_template={"zh-TW": "narrate {poi_name}", "en": "narrate {poi_name}"},
        qa_template={"zh-TW": "answer {question}", "en": "answer {question}"},
    ),
}
```

更新 `app` fixture，加入 `get_persona_registry` override：

```python
@pytest.fixture
def app():
    """Minimal FastAPI app with narration router and fake service + registry injected."""
    application = FastAPI()
    application.include_router(router)

    fake_service = FakeNarrationService()
    application.dependency_overrides[get_narration_service] = lambda: fake_service
    application.dependency_overrides[get_persona_registry] = lambda: _FAKE_REGISTRY

    return application
```

- [ ] **Step 3: 確認測試失敗**

```bash
cd backend && .venv/bin/pytest tests/integration/test_narration_api.py::TestNarrationAPIValidation::test_unknown_persona_returns_400 -v
```

Expected: `ImportError: cannot import name 'get_persona_registry'`（因為還沒加到 narration.py）

- [ ] **Step 4: 修改 narration.py**

完整替換 `backend/src/tour_guide/api/narration.py`：

```python
"""POST /narration — SSE streaming endpoint for tour guide narration."""

import dataclasses

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from tour_guide.api.sse import encode_event
from tour_guide.models.persona import PersonaConfig
from tour_guide.models.poi import OsmNode, POIContext
from tour_guide.services.narration_service import NarrationService

router = APIRouter()


class NarrationRequest(BaseModel):
    poi_id: str
    persona: str = "history_uncle"
    lang: str = "zh-TW"
    length: str = "medium"
    force_regenerate: bool = False


def get_narration_service() -> NarrationService:
    raise NotImplementedError("Override with dependency")


def get_persona_registry() -> dict[str, PersonaConfig]:
    raise NotImplementedError("Override with dependency")


def _event_to_dict(event) -> dict:
    d = dataclasses.asdict(event)
    d.pop("type", None)
    return d


@router.post("/narration")
async def narrate(
    request: NarrationRequest,
    narration_service: NarrationService = Depends(get_narration_service),  # noqa: B008
    persona_registry: dict = Depends(get_persona_registry),  # noqa: B008
):
    if request.persona not in persona_registry:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown persona: '{request.persona}'. "
            f"Valid options: {sorted(persona_registry.keys())}",
        )
    persona: PersonaConfig = persona_registry[request.persona]
    poi_context = POIContext(osm=OsmNode(id=request.poi_id, lat=0.0, lon=0.0, tags={}))

    async def generate():
        try:
            async for event in narration_service.narrate(
                poi=poi_context,
                persona=persona,
                lang=request.lang,
                length=request.length,
                force_regenerate=request.force_regenerate,
            ):
                event_type = event.type
                data = _event_to_dict(event)
                yield encode_event(event_type, data)
        except Exception as e:
            yield encode_event(
                "error",
                {"code": "internal_error", "message": str(e), "retry_after_s": 0},
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 5: 修改 main.py 加入 startup 預載**

在 `main.py` 的 imports 區塊加入：

```python
from tour_guide.prompts.loader import PersonaLoader
```

在 `create_app()` 函式中，在 `narration_service = ...` 之後加入：

```python
    persona_registry = PersonaLoader.load_all()
```

在 `app.dependency_overrides` 區塊加入：

```python
    app.dependency_overrides[narration.get_persona_registry] = lambda: persona_registry
```

完整修改後的 `create_app()` 如下：

```python
def create_app(config: AppConfig) -> FastAPI:
    http_client = httpx.AsyncClient()

    overpass_client = OverpassClient(client=http_client)
    wikipedia_client = WikipediaClient(client=http_client)
    poi_cache = POICache(config.poi_cache_dir)
    narration_cache = NarrationCache(config.narration_cache_dir)

    llm_provider = LiteLLMAdapter(api_key=config.gemini_api_key)
    tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)

    poi_service = POIService(
        overpass=overpass_client,
        wikipedia=wikipedia_client,
        cache=poi_cache,
    )
    narration_service = NarrationService(
        llm=llm_provider,
        tts=tts_provider,
        cache=narration_cache,
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

    app.include_router(health.router)
    app.include_router(poi.router)
    app.include_router(narration.router)

    return app
```

- [ ] **Step 6: 確認所有後端測試通過**

```bash
cd backend && .venv/bin/pytest -v
```

Expected: 全部通過（原有測試 + 新測試）

- [ ] **Step 7: Commit**

```bash
git add backend/src/tour_guide/api/narration.py backend/src/tour_guide/main.py backend/tests/integration/test_narration_api.py
git commit -m "feat(backend): wire PersonaLoader into /narration endpoint, unknown persona → 400"
```

---

## Task 7: Flutter PersonaData 常數

**Files:**
- Create: `flutter_app/lib/features/session/persona_data.dart`

- [ ] **Step 1: 建立 persona_data.dart**

建立 `flutter_app/lib/features/session/persona_data.dart`：

```dart
class PersonaInfo {
  final String id;
  final String emoji;
  final String displayName;
  final String description;

  const PersonaInfo({
    required this.id,
    required this.emoji,
    required this.displayName,
    required this.description,
  });
}

const kPersonas = [
  PersonaInfo(
    id: 'history_uncle',
    emoji: '🏛️',
    displayName: '歷史大叔',
    description: '嚴謹考據，帶你穿越時代脈絡',
  ),
  PersonaInfo(
    id: 'story_brother',
    emoji: '📖',
    displayName: '故事大哥哥',
    description: '鄉野軼事，讓景點活靈活現',
  ),
  PersonaInfo(
    id: 'gossip_auntie',
    emoji: '🗣️',
    displayName: '八卦阿姨',
    description: '名人八卦，讓歷史不再無聊',
  ),
  PersonaInfo(
    id: 'kid_sister',
    emoji: '🌟',
    displayName: '童趣小妹',
    description: '好奇驚嘆，用孩子的眼睛看世界',
  ),
  PersonaInfo(
    id: 'foodie',
    emoji: '🍜',
    displayName: '美食家',
    description: '饕客視角，發掘在地好滋味',
  ),
];
```

- [ ] **Step 2: 確認編譯通過**

```bash
cd flutter_app && flutter analyze lib/features/session/persona_data.dart
```

Expected: `No issues found!`

- [ ] **Step 3: Commit**

```bash
git add flutter_app/lib/features/session/persona_data.dart
git commit -m "feat(flutter): add PersonaInfo model and kPersonas constants"
```

---

## Task 8: SessionState.copyWith() + setPersona / setLang + 測試

**Files:**
- Modify: `flutter_app/lib/features/session/providers/session_provider.dart`
- Modify: `flutter_app/test/unit/session_provider_test.dart`

- [ ] **Step 1: 寫失敗測試**

在 `session_provider_test.dart` 的 `group('SessionProvider', ...)` 末尾加入：

```dart
    test('setPersona() updates persona when idle', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      container.read(sessionProvider.notifier).setPersona('story_brother');
      expect(container.read(sessionProvider).persona, 'story_brother');
    });

    test('setPersona() is no-op when not idle', () async {
      final container = makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      container.read(sessionProvider.notifier).setPersona('story_brother');
      expect(container.read(sessionProvider).persona, 'history_uncle');
    });

    test('setLang() updates lang when idle', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      container.read(sessionProvider.notifier).setLang('en');
      expect(container.read(sessionProvider).lang, 'en');
    });

    test('setLang() is no-op when not idle', () async {
      final container = makeContainer();
      addTearDown(container.dispose);
      await container.read(sessionProvider.notifier).start();
      container.read(sessionProvider.notifier).setLang('en');
      expect(container.read(sessionProvider).lang, 'zh-TW');
    });

    test('default lang is zh-TW', () {
      final container = makeContainer();
      addTearDown(container.dispose);
      expect(container.read(sessionProvider).lang, 'zh-TW');
    });
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd flutter_app && flutter test test/unit/session_provider_test.dart
```

Expected: `The method 'setPersona' isn't defined for the class 'SessionNotifier'`

- [ ] **Step 3: 修改 session_provider.dart**

完整替換 `flutter_app/lib/features/session/providers/session_provider.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

enum SessionStatus { idle, starting, active, ending }

class SessionState {
  final SessionStatus status;
  final String persona;
  final String lang;
  final int? currentSessionId;

  const SessionState({
    required this.status,
    this.persona = 'history_uncle',
    this.lang = 'zh-TW',
    this.currentSessionId,
  });

  SessionState copyWith({
    SessionStatus? status,
    String? persona,
    String? lang,
    int? currentSessionId,
  }) =>
      SessionState(
        status: status ?? this.status,
        persona: persona ?? this.persona,
        lang: lang ?? this.lang,
        currentSessionId: currentSessionId ?? this.currentSessionId,
      );
}

class SessionNotifier extends StateNotifier<SessionState> {
  SessionNotifier(this._location, this._db)
      : super(const SessionState(status: SessionStatus.idle));

  final LocationService _location;
  final LocalDb _db;

  void setPersona(String persona) {
    if (state.status != SessionStatus.idle) return;
    state = state.copyWith(persona: persona);
  }

  void setLang(String lang) {
    if (state.status != SessionStatus.idle) return;
    state = state.copyWith(lang: lang);
  }

  Future<void> start() async {
    state = state.copyWith(status: SessionStatus.starting);
    final granted = await _location.requestPermission();
    if (!granted) {
      state = state.copyWith(status: SessionStatus.idle);
      return;
    }
    final sessionId = await _db.startSession(state.persona, state.lang);
    _location.start();
    state = state.copyWith(
      status: SessionStatus.active,
      currentSessionId: sessionId,
    );
  }

  Future<void> stop() async {
    state = state.copyWith(status: SessionStatus.ending);
    _location.stop();
    if (state.currentSessionId != null) {
      await _db.endSession(state.currentSessionId!);
    }
    state = state.copyWith(status: SessionStatus.idle);
  }
}

final sessionProvider =
    StateNotifierProvider<SessionNotifier, SessionState>((ref) {
  return SessionNotifier(
    ref.watch(locationServiceProvider),
    ref.watch(localDbProvider),
  );
});
```

- [ ] **Step 4: 確認測試通過**

```bash
cd flutter_app && flutter test test/unit/session_provider_test.dart
```

Expected: 全部通過

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/session/providers/session_provider.dart flutter_app/test/unit/session_provider_test.dart
git commit -m "feat(flutter): expose persona/lang in SessionState.copyWith, add setPersona/setLang"
```

---

## Task 9: PersonaSelector widget + widget test

**Files:**
- Create: `flutter_app/lib/features/session/widgets/persona_selector.dart`
- Create: `flutter_app/test/widget/persona_selector_test.dart`

- [ ] **Step 1: 寫失敗測試**

建立 `flutter_app/test/widget/persona_selector_test.dart`：

```dart
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/session/widgets/persona_selector.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

Widget _makeWidget() {
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        FakeLocationService(hasPermission: true),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
    child: const MaterialApp(home: Scaffold(body: PersonaSelector())),
  );
}

void main() {
  testWidgets('shows all 5 persona names', (tester) async {
    await tester.pumpWidget(_makeWidget());
    for (final persona in kPersonas) {
      expect(find.text(persona.displayName), findsOneWidget);
    }
  });

  testWidgets('history_uncle is selected by default', (tester) async {
    await tester.pumpWidget(_makeWidget());
    // The default selected persona card should show a check icon
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });

  testWidgets('tapping a different persona updates selection', (tester) async {
    await tester.pumpWidget(_makeWidget());
    // Tap story_brother card
    await tester.tap(find.text('故事大哥哥'));
    await tester.pump();
    // Now check_circle should still be exactly one (moved to story_brother)
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
    // Verify sessionProvider updated
    final container = ProviderScope.containerOf(
      tester.element(find.byType(PersonaSelector)),
    );
    expect(container.read(sessionProvider).persona, 'story_brother');
  });

  testWidgets('shows emoji for each persona', (tester) async {
    await tester.pumpWidget(_makeWidget());
    for (final persona in kPersonas) {
      expect(find.text(persona.emoji), findsOneWidget);
    }
  });
}
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd flutter_app && flutter test test/widget/persona_selector_test.dart
```

Expected: `Error: Could not find package 'flutter_app/features/session/widgets/persona_selector.dart'`

- [ ] **Step 3: 建立 PersonaSelector widget**

建立 `flutter_app/lib/features/session/widgets/persona_selector.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/features/session/persona_data.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';

class PersonaSelector extends ConsumerWidget {
  const PersonaSelector({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final selectedId = ref.watch(sessionProvider).persona;

    return Column(
      children: kPersonas.map((persona) {
        final isSelected = persona.id == selectedId;
        return GestureDetector(
          onTap: () => ref.read(sessionProvider.notifier).setPersona(persona.id),
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 24, vertical: 6),
            padding: const EdgeInsets.all(16),
            decoration: BoxDecoration(
              color: const Color(0xFF0F3460),
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: isSelected
                    ? const Color(0xFF4A9EFF)
                    : Colors.transparent,
                width: 2,
              ),
            ),
            child: Row(
              children: [
                Text(persona.emoji, style: const TextStyle(fontSize: 24)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        persona.displayName,
                        style: TextStyle(
                          color: isSelected
                              ? const Color(0xFF4A9EFF)
                              : Colors.white,
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      const SizedBox(height: 2),
                      Text(
                        persona.description,
                        style: const TextStyle(
                          color: Colors.white60,
                          fontSize: 13,
                        ),
                      ),
                    ],
                  ),
                ),
                if (isSelected)
                  const Icon(Icons.check_circle, color: Color(0xFF4A9EFF)),
              ],
            ),
          ),
        );
      }).toList(),
    );
  }
}
```

- [ ] **Step 4: 確認測試通過**

```bash
cd flutter_app && flutter test test/widget/persona_selector_test.dart
```

Expected: 全部通過

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/session/widgets/persona_selector.dart flutter_app/test/widget/persona_selector_test.dart
git commit -m "feat(flutter): add PersonaSelector vertical card widget with selection state"
```

---

## Task 10: NarrationNotifier.narrate() 改為接收 persona/lang 參數

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/narration_provider.dart`
- Modify: `flutter_app/test/integration/narration_flow_test.dart`

- [ ] **Step 1: 先更新測試（讓既有測試失敗在正確位置）**

在 `narration_flow_test.dart` 中，將所有 `narrate(_testPoi)` 呼叫改為：
- `narrate(_testPoi, persona: 'history_uncle', lang: 'zh-TW')`

共 3 處（`narrate() transitions...`、`audio chunks...`、`subtitle...` 這三個 test 各一處）：

```dart
// 改前
await container.read(narrationProvider.notifier).narrate(_testPoi);

// 改後
await container.read(narrationProvider.notifier).narrate(
  _testPoi,
  persona: 'history_uncle',
  lang: 'zh-TW',
);
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd flutter_app && flutter test test/integration/narration_flow_test.dart
```

Expected: `Too many positional arguments` 或 `The named parameter 'persona' isn't defined`

- [ ] **Step 3: 修改 narration_provider.dart**

完整替換 `flutter_app/lib/features/narration/providers/narration_provider.dart`：

```dart
import 'dart:async';
import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

enum NarrationStatus { idle, loading, playing, paused, error }

class NarrationState {
  final NarrationStatus status;
  final POI? currentPoi;
  final String subtitle;
  final double progress;
  final String? confidence;
  final String? errorMessage;

  const NarrationState({
    required this.status,
    this.currentPoi,
    this.subtitle = '',
    this.progress = 0,
    this.confidence,
    this.errorMessage,
  });

  NarrationState copyWith({
    NarrationStatus? status,
    POI? currentPoi,
    String? subtitle,
    double? progress,
    String? confidence,
    String? errorMessage,
  }) =>
      NarrationState(
        status: status ?? this.status,
        currentPoi: currentPoi ?? this.currentPoi,
        subtitle: subtitle ?? this.subtitle,
        progress: progress ?? this.progress,
        confidence: confidence ?? this.confidence,
        errorMessage: errorMessage ?? this.errorMessage,
      );
}

class NarrationNotifier extends StateNotifier<NarrationState> {
  NarrationNotifier(this._client, this._audio, this._db)
      : super(const NarrationState(status: NarrationStatus.idle));

  final BackendClient _client;
  final AudioPlayerService _audio;
  final LocalDb _db;
  StreamSubscription<NarrationEvent>? _sub;
  int _audioChunkCount = 0;
  String _currentPersona = 'history_uncle';
  String _currentLang = 'zh-TW';

  Future<void> narrate(
    POI poi, {
    required String persona,
    required String lang,
  }) async {
    _currentPersona = persona;
    _currentLang = lang;
    await _sub?.cancel();
    _audioChunkCount = 0;
    state = NarrationState(
      status: NarrationStatus.loading,
      currentPoi: poi,
    );

    _sub = _client
        .narrate(
          poiId: poi.id,
          persona: persona,
          lang: lang,
          length: 'medium',
        )
        .listen(
          (event) => _handle(event, poi),
          onError: (Object e) => state = state.copyWith(
            status: NarrationStatus.error,
            errorMessage: e.toString(),
          ),
        );
  }

  void _handle(NarrationEvent event, POI poi) {
    switch (event) {
      case MetaEvent(:final confidence):
        state = state.copyWith(
          status: NarrationStatus.playing,
          confidence: confidence,
        );
      case TextEvent(:final chunk):
        state = state.copyWith(subtitle: state.subtitle + chunk);
      case AudioEvent(:final chunkB64):
        _audioChunkCount++;
        final bytes = base64.decode(chunkB64);
        _audio.enqueueBytes(bytes);
        state = state.copyWith(
          progress: (_audioChunkCount * 0.1).clamp(0.0, 0.9),
        );
      case EndEvent():
        _recordNarration(poi);
        state = state.copyWith(
          status: NarrationStatus.idle,
          progress: 1.0,
        );
      case ErrorEvent(:final message):
        state = state.copyWith(
          status: NarrationStatus.error,
          errorMessage: message,
        );
    }
  }

  void _recordNarration(POI poi) {
    _db
        .recordNarration(
          sessionId: 1,
          poiId: poi.id,
          poiName: poi.name,
          poiLat: poi.lat,
          poiLon: poi.lon,
          persona: _currentPersona,
          lang: _currentLang,
          completed: true,
        )
        .catchError((_) {/* ignore FK errors in MVP */});
  }

  Future<void> pause() async {
    await _audio.pause();
    state = state.copyWith(status: NarrationStatus.paused);
  }

  Future<void> resume() async {
    await _audio.resume();
    state = state.copyWith(status: NarrationStatus.playing);
  }

  Future<void> skip() async {
    await _sub?.cancel();
    await _audio.skip();
    state = state.copyWith(status: NarrationStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}

final narrationProvider =
    StateNotifierProvider<NarrationNotifier, NarrationState>((ref) {
  return NarrationNotifier(
    ref.watch(backendClientProvider),
    ref.watch(audioPlayerServiceProvider),
    ref.watch(localDbProvider),
  );
});
```

- [ ] **Step 4: 確認測試通過**

```bash
cd flutter_app && flutter test test/integration/narration_flow_test.dart
```

Expected: 全部通過

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/narration/providers/narration_provider.dart flutter_app/test/integration/narration_flow_test.dart
git commit -m "feat(flutter): narrate() accepts persona/lang params, reads from session state"
```

---

## Task 11: TriggerNotifier 傳遞 persona/lang + 測試

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: 確認現有測試仍通過（確立基線）**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```

Expected: PASS（目前測試只確認 provider 啟動不拋錯）

- [ ] **Step 2: 修改 trigger_provider.dart**

完整替換 `flutter_app/lib/features/narration/providers/trigger_provider.dart`：

```dart
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/map/providers/poi_provider.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/features/narration/trigger_engine.dart';
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

    final triggers = TriggerEngine.evaluate(
      userLat: position.latitude,
      userLon: position.longitude,
      pois: pois.cast(),
      playedPoiIds: _sessionPlayedIds,
      cooldownPoiIds: cooldownIds,
    );

    if (triggers.isNotEmpty) {
      final poi = triggers.first;
      _sessionPlayedIds.add(poi.id);
      final session = ref.read(sessionProvider);
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

- [ ] **Step 3: 確認既有測試通過**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```

Expected: PASS（`sessionProvider` 依賴 `locationServiceProvider` + `localDbProvider`，兩者已在 test container 中 override）

- [ ] **Step 4: 跑全部 Flutter 測試確認無 regression**

```bash
cd flutter_app && flutter test
```

Expected: 全部通過，`flutter analyze` 無 error

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart flutter_app/test/unit/trigger_provider_test.dart
git commit -m "feat(flutter): TriggerNotifier reads persona/lang from sessionProvider before narrating"
```

---

## Task 12: HomeScreen 改版 + 更新 widget test

**Files:**
- Modify: `flutter_app/lib/features/session/screens/home_screen.dart`
- Modify: `flutter_app/test/widget/home_screen_test.dart`

- [ ] **Step 1: 更新 home_screen_test.dart**

完整替換 `flutter_app/test/widget/home_screen_test.dart`：

```dart
import 'dart:async';
import 'package:drift/native.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:geolocator/geolocator.dart';
import 'package:flutter_app/features/session/screens/home_screen.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/location/location_service.dart';
import 'package:flutter_app/shared/providers.dart';

class _FakeLocationService implements LocationService {
  final bool hasPermission;
  _FakeLocationService({this.hasPermission = true});
  @override Future<bool> requestPermission() async => hasPermission;
  @override void start() {}
  @override void stop() {}
  @override Stream<Position> get positionStream => const Stream.empty();
}

Widget _makeWidget({bool hasPermission = true}) {
  return ProviderScope(
    overrides: [
      locationServiceProvider.overrideWithValue(
        _FakeLocationService(hasPermission: hasPermission),
      ),
      localDbProvider.overrideWithValue(
        LocalDb.forTesting(NativeDatabase.memory()),
      ),
    ],
    child: const MaterialApp(home: HomeScreen()),
  );
}

void main() {
  testWidgets('shows Start Journey button when idle', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('開始旅程'), findsOneWidget);
  });

  testWidgets('shows all 5 persona cards', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('歷史大叔'), findsOneWidget);
    expect(find.text('故事大哥哥'), findsOneWidget);
    expect(find.text('八卦阿姨'), findsOneWidget);
    expect(find.text('童趣小妹'), findsOneWidget);
    expect(find.text('美食家'), findsOneWidget);
  });

  testWidgets('shows language segmented button', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.text('中文'), findsOneWidget);
    expect(find.text('EN'), findsOneWidget);
  });

  testWidgets('history_uncle is selected by default', (tester) async {
    await tester.pumpWidget(_makeWidget());
    expect(find.byIcon(Icons.check_circle), findsOneWidget);
  });
}
```

- [ ] **Step 2: 確認測試失敗**

```bash
cd flutter_app && flutter test test/widget/home_screen_test.dart
```

Expected: `故事大哥哥 not found` 或類似（因為 PersonaSelector 還沒進 HomeScreen）

- [ ] **Step 3: 修改 home_screen.dart**

完整替換 `flutter_app/lib/features/session/screens/home_screen.dart`：

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_app/features/session/providers/session_provider.dart';
import 'package:flutter_app/features/session/widgets/persona_selector.dart';

class HomeScreen extends ConsumerWidget {
  const HomeScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(sessionProvider);
    final isStarting = session.status == SessionStatus.starting;

    return Scaffold(
      backgroundColor: const Color(0xFF1A1A2E),
      body: SafeArea(
        child: SingleChildScrollView(
          child: Column(
            children: [
              const SizedBox(height: 32),
              const Text(
                'AI Tour Guide',
                style: TextStyle(
                  color: Color(0xFF4A9EFF),
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(value: 'zh-TW', label: Text('中文')),
                  ButtonSegment(value: 'en', label: Text('EN')),
                ],
                selected: {session.lang},
                onSelectionChanged: isStarting
                    ? null
                    : (s) =>
                        ref.read(sessionProvider.notifier).setLang(s.first),
                style: ButtonStyle(
                  foregroundColor: WidgetStateProperty.resolveWith(
                    (states) => states.contains(WidgetState.selected)
                        ? const Color(0xFF4A9EFF)
                        : Colors.white60,
                  ),
                ),
              ),
              const SizedBox(height: 16),
              const PersonaSelector(),
              const SizedBox(height: 32),
              ElevatedButton(
                onPressed: isStarting ? null : () => _start(context, ref),
                style: ElevatedButton.styleFrom(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 40,
                    vertical: 16,
                  ),
                ),
                child: isStarting
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child:
                            CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('開始旅程', style: TextStyle(fontSize: 18)),
              ),
              const SizedBox(height: 32),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _start(BuildContext context, WidgetRef ref) async {
    await ref.read(sessionProvider.notifier).start();
    if (!context.mounted) return;
    final status = ref.read(sessionProvider).status;
    if (status == SessionStatus.active) {
      context.push('/map');
    } else if (status == SessionStatus.idle) {
      showDialog<void>(
        context: context,
        builder: (_) => AlertDialog(
          title: const Text('需要定位權限'),
          content: const Text('請在設定中允許「使用 App 期間」的定位權限。'),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('確定'),
            ),
          ],
        ),
      );
    }
  }
}
```

- [ ] **Step 4: 確認 HomeScreen 測試通過**

```bash
cd flutter_app && flutter test test/widget/home_screen_test.dart
```

Expected: 全部通過

- [ ] **Step 5: 跑全部測試 + analyze**

```bash
cd flutter_app && flutter test && flutter analyze
```

Expected: 全部通過，無 error

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/features/session/screens/home_screen.dart flutter_app/test/widget/home_screen_test.dart
git commit -m "feat(flutter): restructure HomeScreen with PersonaSelector cards and language toggle"
```

---

## 最終驗收

- [ ] **後端全套測試**

```bash
cd backend && .venv/bin/pytest -v
```

Expected: 全部通過，`ruff check src/` 無 error

- [ ] **Flutter 全套測試**

```bash
cd flutter_app && flutter test && flutter analyze
```

Expected: 全部通過，無 error（info 等級的 `prefer_const_constructors` 可接受）

- [ ] **端對端確認**（需要人工操作）

```bash
# 啟動後端（需真實 GEMINI_API_KEY）
cd backend && GEMINI_API_KEY=<key> .venv/bin/uvicorn tour_guide.main:app --reload

# 測試 5 個 persona 各一次
curl -X POST http://localhost:8000/narration \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"poi_id":"osm:node:123","persona":"story_brother","lang":"zh-TW","length":"short"}'

# 測試英文
curl -X POST http://localhost:8000/narration \
  -H "Content-Type: application/json" \
  -H "Accept: text/event-stream" \
  -d '{"poi_id":"osm:node:123","persona":"history_uncle","lang":"en","length":"short"}'

# 測試未知 persona → 應回 400
curl -X POST http://localhost:8000/narration \
  -H "Content-Type: application/json" \
  -d '{"poi_id":"osm:node:123","persona":"unknown","lang":"zh-TW","length":"short"}'
```

- [ ] **Flutter App 手動確認**

```bash
cd flutter_app && flutter run --dart-define-from-file=dart_defines/dev.json
```

確認：
1. HomeScreen 顯示 5 張 persona 卡片
2. 點選不同卡片 → highlight 正確移動
3. 中文 / EN 切換
4. 點「開始旅程」→ 進入地圖

---

_Plan C Implementation Plan — 2026-05-12_
