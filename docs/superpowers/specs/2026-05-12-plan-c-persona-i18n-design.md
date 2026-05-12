# Plan C — Persona 系統擴充 + 雙語設計文件

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-05-12 |
| 適用範圍 | Plan C（接續 Plan B Flutter App MVP） |
| 前置文件 | `docs/superpowers/specs/2026-05-08-ai-tour-guide-design.md` |
| 實作計畫 | 待 `writing-plans` skill 產生 |

---

## 1. 目標

在 Plan B MVP 基礎上，擴充 persona 系統從 1 個（靜態）到 5 個（可選擇），並支援旁白雙語切換（zh-TW / en）。UI 文字維持中文，語言切換僅影響旁白播放語言（lang 參數傳後端）。

---

## 2. 決策摘要

| 決策項 | 選擇 | 理由 |
|---|---|---|
| Persona 定義方式 | Backend YAML + Flutter hardcode 展示資訊 | 職責清晰：AI 行為在後端 YAML，UI 展示在 Flutter |
| Persona 清單 | 5 個（設計文件 §8.2） | 延用原始設計，含完整 voice/style 規格 |
| Persona 選擇 UI | 垂直卡片（5 張）| 一次性選角體驗，卡片資訊量足以做出有意義的選擇 |
| 語言切換 UI | HomeScreen SegmentedButton | 出發前一次設定完，不需獨立設定頁 |
| UI 文字 i18n | 暫不處理，維持中文 | Plan C 核心是旁白語言 + persona，UI i18n 留 Plan F |
| Backend persona 載入 | PersonaLoader（已有）+ startup 預載 | 避免每次 request 讀檔 |

---

## 3. Persona 清單

以設計文件 §8.2 為準：

| ID | 中文名 | Emoji | 風格 | embellishment | zh-TW voice | en voice | speaking_rate | poi_source |
|---|---|---|---|---|---|---|---|---|
| `history_uncle` | 歷史大叔 | 🏛️ | 嚴謹考據派 | 0.1 | Charon | Charon | 0.95 | osm_wikipedia |
| `story_brother` | 故事大哥哥 | 📖 | 鄉間軼事派 | 0.6 | Puck | Puck | 1.05 | osm_wikipedia |
| `gossip_auntie` | 八卦阿姨 | 🗣️ | 名人八卦派 | 0.5 | Aoede | Aoede | 1.0 | osm_wikipedia |
| `kid_sister` | 童趣小妹 | 🌟 | 好奇驚嘆派 | 0.3 | Kore | Kore | 1.0 | osm_wikipedia |
| `foodie` | 美食家 | 🍜 | 食物推薦派 | 0.4 | Leda | Leda | 1.0 | google_places（Plan E 才啟用，Plan C 先用 osm_wikipedia） |

---

## 4. Backend 架構變更

### 4.1 新增 YAML 檔案

路徑：`backend/prompts/personas/{id}.yaml`

需新增 4 個（`history_uncle.yaml` 已存在且含 zh-TW + en）：
- `story_brother.yaml`
- `gossip_auntie.yaml`
- `kid_sister.yaml`
- `foodie.yaml`

每個 YAML 必須包含：
```yaml
id: <persona_id>
display_name:
  zh-TW: <中文名>
  en: <英文名>
voice:
  zh-TW: <Gemini voice name>
  en: <Gemini voice name>
voice_style:
  speaking_rate: <float>
  emotion: <str>
style_profile:
  embellishment: <float>
  preferred_topics: [...]
poi_source: osm_wikipedia
system_prompt:
  zh-TW: |
    <中文 system prompt>
  en: |
    <English system prompt>
narration_template:
  zh-TW: |
    <含 {poi_name}, {poi_context}, {target_length} 的中文模板>
  en: |
    <English template>
qa_template:
  zh-TW: <中文 QA 模板>
  en: <English QA template>
system_messages:
  zh-TW:
    network_offline: [...]
    rate_limit: [...]
confidence_labels:
  zh-TW:
    high: null
    medium: [...]
    low: [...]
```

### 4.2 PersonaLoader startup 預載

`PersonaLoader` 已完整實作（`backend/src/tour_guide/prompts/loader.py`）。

新增 `load_all(base_dir)` classmethod，在 FastAPI `lifespan` 啟動時預載所有 YAML 到 dict，request 時直接取：

```python
# main.py lifespan
_PERSONAS: dict[str, PersonaConfig] = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    _PERSONAS.update(PersonaLoader.load_all())
    yield

def get_persona(persona_id: str) -> PersonaConfig:
    if persona_id not in _PERSONAS:
        raise HTTPException(status_code=400, detail=f"Unknown persona: {persona_id}")
    return _PERSONAS[persona_id]
```

### 4.3 `/narration` endpoint 替換 inline hardcode

```python
# 現在（Plan B）
persona = PersonaConfig(
    id=request.persona,
    display_name={"zh-TW": request.persona},
    system_prompt={"zh-TW": "You are a tour guide."},
    ...
)

# Plan C 後
persona = get_persona(request.persona)  # 從預載 dict 取，未知 persona_id → 400
```

### 4.4 測試新增

| 測試 | 類型 | 內容 |
|---|---|---|
| `test_load_all_personas` | unit | 5 個 YAML 全部能載入，無缺漏欄位 |
| `test_narration_unknown_persona` | integration | POST /narration with `persona="unknown"` → 400 |
| `test_narration_all_personas` | integration | 5 個 persona id 各發一次 → 200，meta event 正確 |

---

## 5. Flutter 架構變更

### 5.1 Persona 展示資料（Flutter 端常數）

新增 `lib/features/session/persona_data.dart`：

```dart
class PersonaInfo {
  final String id;
  final String emoji;
  final String displayName;   // 中文名（UI 維持中文）
  final String description;   // 一行中文描述
  const PersonaInfo({...});
}

const kPersonas = [
  PersonaInfo(id: 'history_uncle', emoji: '🏛️', displayName: '歷史大叔',
      description: '嚴謹考據，帶你穿越時代脈絡'),
  PersonaInfo(id: 'story_brother', emoji: '📖', displayName: '故事大哥哥',
      description: '鄉野軼事，讓景點活靈活現'),
  PersonaInfo(id: 'gossip_auntie', emoji: '🗣️', displayName: '八卦阿姨',
      description: '名人八卦，讓歷史不再無聊'),
  PersonaInfo(id: 'kid_sister', emoji: '🌟', displayName: '童趣小妹',
      description: '好奇驚嘆，用孩子的眼睛看世界'),
  PersonaInfo(id: 'foodie', emoji: '🍜', displayName: '美食家',
      description: '饕客視角，發掘在地好滋味'),
];
```

### 5.2 `SessionState` / `SessionNotifier` 變更

**`SessionState.copyWith()`** 加入 `persona` / `lang`：
```dart
SessionState copyWith({
  SessionStatus? status,
  String? persona,
  String? lang,
  int? currentSessionId,
})
```

**`SessionNotifier`** 新增兩個方法，僅在 `idle` 狀態允許修改：
```dart
void setPersona(String persona) {
  if (state.status != SessionStatus.idle) return;
  state = state.copyWith(persona: persona);
}

void setLang(String lang) {
  if (state.status != SessionStatus.idle) return;
  state = state.copyWith(lang: lang);
}
```

### 5.3 `PersonaSelector` widget

取代 `PersonaChip`，新增 `lib/features/session/widgets/persona_selector.dart`：

- 5 張垂直卡片，每張含 emoji + 中文名 + 描述
- 選取卡片：border 改為主題藍色（`Color(0xFF4A9EFF)`），背景略深
- tap → `ref.read(sessionProvider.notifier).setPersona(persona.id)`
- 預設選取 `'history_uncle'`（`SessionState` 初始值）

### 5.4 語言切換

HomeScreen 新增 `SegmentedButton<String>`，options: `['zh-TW', 'EN']`（UI label）：
- 實際 lang 值為 `'zh-TW'` 或 `'en'`（小寫，與後端 API 對齊）
- tap → `ref.read(sessionProvider.notifier).setLang('zh-TW')` 或 `setLang('en')`
- 顯示目前選取的語言

### 5.5 `HomeScreen` 結構調整

```
SafeArea
  Column
    Text('AI Tour Guide')          ← 標題
    SegmentedButton(zh-TW / EN)    ← 語言切換（新增）
    PersonaSelector(5 張卡片)      ← 取代 PersonaChip（新增）
    ElevatedButton('開始旅程')      ← 不變
```

### 5.6 `NarrationNotifier` 讀取 session 狀態

`NarrationNotifier` 改為依賴 `sessionProvider`：

```dart
// narrate() 內
final session = ref.read(sessionProvider);
_sub = _client.narrate(
  poiId: poi.id,
  persona: session.persona,   // 不再 hardcode
  lang: session.lang,         // 不再 hardcode
  length: 'medium',
).listen(...);

// _recordNarration() 內
_db.recordNarration(
  ...
  persona: session.persona,
  lang: session.lang,
  ...
);
```

因此 `NarrationNotifier` 的 constructor 需加入 `Ref` 或直接接受 `String persona, String lang`（推薦後者，保持 constructor 可測試）。

實際做法：`narrate(POI poi)` 改為 `narrate(POI poi, {required String persona, required String lang})`，由 `TriggerNotifier` 呼叫時從 session 讀取後傳入。

**`TriggerNotifier` 對應改動**（`lib/features/narration/providers/trigger_provider.dart`）：

```dart
// 觸發旁白時，讀取當前 session 的 persona/lang
final session = ref.read(sessionProvider);
ref.read(narrationProvider.notifier).narrate(
  poi,
  persona: session.persona,
  lang: session.lang,
);
```

### 5.7 測試新增

| 測試 | 類型 | 內容 |
|---|---|---|
| `session_notifier_test` | unit | setPersona/setLang 在 idle 生效；在 active 時 no-op |
| `persona_selector_test` | widget | tap 切換選取狀態，驗證 highlight |
| `narration_notifier_test` | unit | narrate() 傳入 persona/lang 正確帶入 FakeBackendClient |

---

## 6. 資料流變化

```
HomeScreen
  使用者 tap PersonaSelector → sessionNotifier.setPersona('gossip_auntie')
  使用者 tap 語言 → sessionNotifier.setLang('en')
  使用者 tap 開始旅程 → sessionNotifier.start()
  → GoRouter push /map

TriggerNotifier（進入 /map 後）
  偵測到 POI 進入範圍
  final session = ref.read(sessionProvider)
  narrationNotifier.narrate(poi, persona: session.persona, lang: session.lang)

NarrationNotifier
  _client.narrate(poiId, persona, lang, ...)  ← 動態值，非 hardcode
  後端用對應 YAML prompt + voice 生成旁白
```

---

## 7. 不在 Plan C 範圍內

- `foodie` persona 的 Google Places 路由（Plan E）
- Flutter UI 文字 i18n / ARB 檔（Plan F）
- Persona 觸發半徑 per-persona override（設計文件 §8.5，Plan F）
- `POST /admin/reload-prompts` endpoint（設計文件 §8.6，Plan F）
- confidence_labels 的 en 版本（YAML 可先只寫 zh-TW）

---

## 8. 驗收標準

1. 後端：5 個 YAML 全部能被 `PersonaLoader.load_all()` 載入，無 error
2. 後端：`POST /narration` with `persona="story_brother"` + `lang="en"` → 200 + SSE stream 正常
3. 後端：`POST /narration` with `persona="unknown"` → 400
4. Flutter：HomeScreen 顯示 5 張 persona 卡片，可點選切換
5. Flutter：語言切換後，後端收到正確 `lang` 參數（log 或測試驗證）
6. Flutter：所有既有 42 tests 仍通過
7. Flutter：新增 tests 通過，`flutter analyze` 無 error

---

## 文件結束
