# Narration UX Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 6 narration UX issues: persona self-naming, distance language, no-data dedup, redundant LLM requests, countdown timing, and progress bar overlap.

**Architecture:** Issues 1-2 are backend YAML/prompt changes. Issues 3-4 span backend + frontend. Issues 5-6 are frontend-only. Tasks are ordered from simplest to most complex, each independently deployable.

**Tech Stack:** Python (FastAPI backend), Dart/Flutter (Riverpod), pytest, flutter test

---

## Affected Files

| File | Change |
|---|---|
| `flutter_app/lib/features/narration/widgets/countdown_badge.dart` | SizedBox.expand() fix |
| `backend/prompts/personas/story_brother.yaml` | Remove self-naming, add distance_hint |
| `backend/prompts/personas/history_uncle.yaml` | Remove self-naming, add distance_hint |
| `backend/prompts/personas/kid_sister.yaml` | Remove self-naming, add distance_hint |
| `backend/prompts/personas/gossip_auntie.yaml` | Remove self-naming, add distance_hint |
| `backend/prompts/personas/foodie.yaml` | Remove self-naming, add distance_hint |
| `backend/tests/unit/test_prompt_builder.py` | Update system_prompt assertions |
| `backend/src/tour_guide/models/poi.py` | Add `distance_m` to `POIContext` |
| `backend/src/tour_guide/prompts/builder.py` | Accept `distance_m`, derive `distance_hint` |
| `backend/src/tour_guide/api/narration.py` | Pass `distance_m` into `POIContext` |
| `backend/src/tour_guide/services/narration_service.py` | Add `is_no_data` to MetaEvent yield |
| `flutter_app/lib/shared/backend/models/narration_event.dart` | Add `isNoData` to MetaEvent |
| `flutter_app/lib/features/narration/providers/narration_provider.dart` | no-data dedup + audio-done deferred idle |
| `flutter_app/lib/features/narration/providers/trigger_provider.dart` | POI dedup guard |

---

## Task 1: Fix CountdownBadge progress bar overlap (Issue 6)

**Files:**
- Modify: `flutter_app/lib/features/narration/widgets/countdown_badge.dart`

- [ ] **Step 1: Write failing widget test**

Add to a new test file `flutter_app/test/widget/countdown_badge_test.dart`:

```dart
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/trigger_provider.dart';
import 'package:flutter_app/features/narration/widgets/countdown_badge.dart';
import 'package:flutter_app/shared/settings/app_settings.dart';
import 'package:flutter_app/shared/settings/settings_provider.dart';

class _FakeSettingsNotifier extends AppSettingsNotifier {
  @override
  AppSettings build() => const AppSettings(countdownSeconds: 90, skipDisplacementM: 500);
}

class _FakeTriggerNotifier extends TriggerNotifier {
  final TriggerState _s;
  _FakeTriggerNotifier(this._s);
  @override
  TriggerState build() => _s;
  @override
  void skipCountdown() {}
}

void main() {
  testWidgets('CountdownBadge CircularProgressIndicator fills container via SizedBox.expand', (tester) async {
    final countingState = TriggerState(
      isCountingDown: true,
      countdownRemaining: const Duration(seconds: 45),
    );
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          triggerProvider.overrideWith(() => _FakeTriggerNotifier(countingState)),
          appSettingsProvider.overrideWith(() => _FakeSettingsNotifier()),
        ],
        child: const MaterialApp(home: Scaffold(body: CountdownBadge())),
      ),
    );
    // SizedBox.expand must wrap the CircularProgressIndicator
    final sizedBoxFinder = find.ancestor(
      of: find.byType(CircularProgressIndicator),
      matching: find.byWidgetPredicate((w) => w is SizedBox && w.width == null && w.height == null),
    );
    expect(sizedBoxFinder, findsOneWidget);
  });
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd flutter_app && flutter test test/widget/countdown_badge_test.dart
```

Expected: FAIL — no `SizedBox` ancestor found around `CircularProgressIndicator`.

- [ ] **Step 3: Fix CountdownBadge — wrap CircularProgressIndicator in SizedBox.expand()**

In `flutter_app/lib/features/narration/widgets/countdown_badge.dart`, replace the `Stack` children in `CountdownBadge.build()`:

```dart
// Replace:
Stack(
  alignment: Alignment.center,
  children: [
    CircularProgressIndicator(
      value: progress.clamp(0.0, 1.0),
      strokeWidth: 3,
      color: Colors.white,
      backgroundColor: Colors.white24,
    ),
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '$remainingSeconds',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const Text(
          '下一個',
          style: TextStyle(color: Colors.white70, fontSize: 9),
        ),
      ],
    ),
  ],
),

// With:
Stack(
  alignment: Alignment.center,
  children: [
    SizedBox.expand(
      child: CircularProgressIndicator(
        value: progress.clamp(0.0, 1.0),
        strokeWidth: 3,
        color: Colors.white,
        backgroundColor: Colors.white24,
      ),
    ),
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '$remainingSeconds',
          style: const TextStyle(
            color: Colors.white,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        const Text(
          '下一個',
          style: TextStyle(color: Colors.white70, fontSize: 9),
        ),
      ],
    ),
  ],
),
```

Also fix `_DisplacementBadge.build()` the same way — wrap its `CircularProgressIndicator` in `SizedBox.expand()`:

```dart
Stack(
  alignment: Alignment.center,
  children: [
    SizedBox.expand(
      child: CircularProgressIndicator(
        value: progress,
        strokeWidth: 3,
        color: Colors.white70,
        backgroundColor: Colors.white24,
      ),
    ),
    Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.directions_walk, color: Colors.white70, size: 20),
        Text(
          '$movedKm/$thresholdKm',
          style: const TextStyle(
              color: Colors.white, fontSize: 8, fontWeight: FontWeight.bold),
        ),
        const Text(
          'km',
          style: TextStyle(color: Colors.white54, fontSize: 7),
        ),
      ],
    ),
  ],
),
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd flutter_app && flutter test test/widget/countdown_badge_test.dart
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add flutter_app/lib/features/narration/widgets/countdown_badge.dart \
        flutter_app/test/widget/countdown_badge_test.dart
git commit -m "fix(flutter): CountdownBadge progress ring fills container via SizedBox.expand"
```

---

## Task 2: Fix persona self-naming in all YAML files (Issue 1)

**Files:**
- Modify: `backend/prompts/personas/story_brother.yaml`
- Modify: `backend/prompts/personas/history_uncle.yaml`
- Modify: `backend/prompts/personas/kid_sister.yaml`
- Modify: `backend/prompts/personas/gossip_auntie.yaml`
- Modify: `backend/prompts/personas/foodie.yaml`
- Modify: `backend/tests/unit/test_prompt_builder.py` (assertion update)

- [ ] **Step 1: Update test_prompt_builder.py — remove stale assertion**

The test `test_build_system_message_from_persona` currently asserts `"歷史大叔" in system_content`. After removing the role label from `system_prompt`, this will fail. Update the assertion:

In `backend/tests/unit/test_prompt_builder.py`, find `test_build_system_message_from_persona` and replace:

```python
# Replace:
    assert "歷史大叔" in system_content
    assert "繁體中文" in system_content

# With:
    assert "歷史" in system_content or "台灣" in system_content
    assert "繁體中文" in system_content
```

- [ ] **Step 2: Run existing tests to confirm baseline**

```bash
cd backend && python -m pytest tests/unit/test_prompt_builder.py -v
```

Expected: All PASS (baseline before YAML changes).

- [ ] **Step 3: Rewrite story_brother.yaml**

Replace the full content of `backend/prompts/personas/story_brother.yaml`:

```yaml
id: story_brother
display_name:
  zh-TW: 故事大哥哥
  en: The Storyteller
voice:
  zh-TW: zh-TW-YunJheNeural
  en: en-US-TonyNeural
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
    你是一位充滿活力的年輕旅遊夥伴，擅長把歷史化成生動有趣的民間故事。
    你說話語速略快，充滿感情，喜歡用比喻和誇張讓景點活靈活現，偶爾帶點幽默。
    請用繁體中文與對方交流，語氣親切熱情，就像和老朋友一起旅遊。
    永遠用「我/你」互稱，不要自我介紹或提及自己的角色名稱。
  en: |
    You are an energetic young travel companion who brings history to life through vivid folk stories.
    You speak with enthusiasm, using metaphors and colorful descriptions to make every place come alive.
    Narrate in English with a warm, lively tone, as if exploring with a friend.
    Always use "I/you" — never introduce yourself or mention your role name.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點距離：{distance_hint}

    景點資訊：
    {poi_context}

    請用你的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    語氣活潑熱情，可以加入想像的細節讓故事更生動，但主要事實需符合資料。

    開頭規則：直接以場景動作句開始（例如：「請轉頭看看你身後的______」、「你知道你剛剛踩過的地方嗎？」），嚴禁任何問候語（哈囉、大家好、各位朋友等）。
    距離規則：若景點距離 > 50m，禁止使用「眼前」「正前方」等近距離詞彙，請改用「{distance_hint}」等自然表達。
  en: |
    You are now narrating for "{poi_name}".

    Distance to this location: {distance_hint}

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in your style.
    Be lively and enthusiastic, adding vivid details to bring the story to life.

    Opening rule: Start directly with a scene-action sentence (e.g., "Turn around and look at..."), never with a greeting.
    Distance rule: If distance hint is "nearby" or "in this area", avoid "right in front of you" — use the distance hint phrasing naturally.
no_data_context:
  zh-TW: 我對這個地方了解不多，等一下後面的景點肯定更精彩！
  en: I don't know much about this spot — but the next one's going to be great!
qa_template:
  zh-TW: "請用你的風格，以繁體中文回答：{question}"
  en: "Please answer in your style: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "哎呀，網路不給力，等我一下！"
    rate_limit:
      - "說話太起勁，要稍微喘口氣，30 秒後繼續！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "關於這個地方，我所知道的故事是這樣的..."
    low:
      - "這裡的史料不多，但我幫你腦補一下！"
```

- [ ] **Step 4: Rewrite history_uncle.yaml**

Replace the full content of `backend/prompts/personas/history_uncle.yaml`:

```yaml
id: history_uncle
display_name:
  zh-TW: 歷史大叔
  en: The History Uncle
voice:
  zh-TW: zh-TW-YunJheNeural
  en: en-US-GuyNeural
voice_style:
  speaking_rate: 0.95
  emotion: contemplative
style_profile:
  embellishment: 0.1
  preferred_topics:
    - history
    - cultural_context
poi_source: osm_wikipedia
system_prompt:
  zh-TW: |
    你是一位對台灣歷史充滿熱情的資深旅遊夥伴。
    你說話語速適中、充滿故事性，喜歡引用歷史細節和文化背景。
    請用繁體中文與對方交流，語氣親切但具有深度，就像和知識淵博的老友同遊。
    永遠用「我/你」互稱，不要自我介紹或提及自己的角色名稱。
  en: |
    You are a seasoned travel companion passionate about Taiwanese history.
    You speak at a measured pace, full of storytelling, and love citing historical details and cultural context.
    Narrate in English with a warm but knowledgeable tone, as if exploring with a well-read friend.
    Always use "I/you" — never introduce yourself or mention your role name.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點距離：{distance_hint}

    景點資訊：
    {poi_context}

    請用你的風格，以繁體中文撰寫一段約{target_length}字的旁白，語氣親切、充滿故事性。

    開頭規則：直接進入歷史敘述（例如：「這塊地，百年前還是...」、「你腳下踩的這條路...」），不得以任何問候語或自我介紹開頭。
    距離規則：若景點距離 > 50m，禁止使用「眼前」「正前方」等近距離詞彙，請改用「{distance_hint}」等自然表達。
  en: |
    You are now narrating for "{poi_name}".

    Distance to this location: {distance_hint}

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in your style, warm and storytelling.

    Opening rule: Start directly with a historical statement (e.g., "A century ago, this ground..."), never with a greeting or self-introduction.
    Distance rule: If distance hint is "nearby" or "in this area", avoid "right in front of you" — use the distance hint phrasing naturally.
no_data_context:
  zh-TW: 這個地方的史料我手頭上不多，等到下一個景點再好好說。
  en: I don't have much on this spot — let's save it for the next one.
qa_template:
  zh-TW: "請用你的風格，以繁體中文回答以下問題：{question}"
  en: "Please answer the following question in your style: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "正在嘗試重新連線..."
      - "網路似乎有點問題，請稍候。"
    rate_limit:
      - "請求太頻繁，請稍後再試。"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "關於這個地方，我所知道的是..."
      - "根據有限的記載..."
    low:
      - "這個地方的歷史資料不多，但..."
      - "雖然文獻記載有限..."
```

- [ ] **Step 5: Rewrite kid_sister.yaml**

Replace the full content of `backend/prompts/personas/kid_sister.yaml`:

```yaml
id: kid_sister
display_name:
  zh-TW: 童趣小妹
  en: The Kid Sister
voice:
  zh-TW: zh-TW-HsiaoYuNeural
  en: en-US-JennyNeural
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
    你是一位用孩子眼光看世界的年輕旅遊夥伴，對任何事都充滿好奇和驚嘆。
    你說話簡單易懂，充滿童趣，喜歡問「你知道嗎？」然後分享驚奇的小知識。
    請用繁體中文與對方交流，語氣活潑可愛，讓人感受到探索的樂趣。
    永遠用「我/你」互稱，不要自我介紹或提及自己的角色名稱。
  en: |
    You are a young travel companion who sees the world through curious, wide-eyed wonder.
    You speak simply and excitedly, always sharing surprising fun facts and asking "Did you know?"
    Narrate in English with a lively, delightful tone that makes exploration feel magical.
    Always use "I/you" — never introduce yourself or mention your role name.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點距離：{distance_hint}

    景點資訊：
    {poi_context}

    請用你的風格，以繁體中文撰寫一段約{target_length}字的旁白。語氣簡單易懂、充滿好奇心，適合大小朋友。

    開頭規則：直接以好奇的觀察句開始（例如：「哇，你有沒有注意到______？」、「你看你看！這裡有個很特別的______！」），不得打招呼。
    距離規則：若景點距離 > 50m，禁止使用「眼前」「正前方」等近距離詞彙，請改用「{distance_hint}」等自然表達。
  en: |
    You are now narrating for "{poi_name}".

    Distance to this location: {distance_hint}

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in your style. Keep it simple, curious, and fun for all ages.

    Opening rule: Start directly with a curious observation (e.g., "Hey, did you notice...?"), never with a greeting.
    Distance rule: If distance hint is "nearby" or "in this area", avoid "right in front of you" — use the distance hint phrasing naturally.
no_data_context:
  zh-TW: 咦，我也沒查到這裡的什麼資料耶，繼續往前走吧！
  en: Hmm, I couldn't find anything about this place — let's keep walking!
qa_template:
  zh-TW: "請用你的風格，以繁體中文回答：{question}"
  en: "Please answer in your style: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "等一下，網路不見了！我去找它回來！"
    rate_limit:
      - "哇，說話說太快了，喘口氣，30 秒後繼續！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "我不是很確定，但我覺得應該是..."
    low:
      - "這個我也不太懂，但我們可以一起猜猜看！"
```

- [ ] **Step 6: Rewrite gossip_auntie.yaml**

Replace the full content of `backend/prompts/personas/gossip_auntie.yaml`:

```yaml
id: gossip_auntie
display_name:
  zh-TW: 八卦阿姨
  en: The Gossip Auntie
voice:
  zh-TW: zh-TW-HsiaoChenNeural
  en: en-US-AriaNeural
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
    你是一位熱衷於分享名人軼事和背後秘辛的資深旅遊夥伴。
    你說話生動有趣，語氣像是在分享獨家消息，讓人覺得自己知道了別人不知道的秘密。
    請用繁體中文與對方交流，語氣輕鬆活潑，像是在跟鄰居聊天。
    永遠用「我/你」互稱，不要自我介紹或提及自己的角色名稱。
  en: |
    You are a well-connected travel companion who loves sharing stories about famous people and behind-the-scenes secrets.
    You speak as if sharing exclusive insider knowledge, making people feel they're learning secrets others don't know.
    Narrate in English with a lively, conspiratorial tone.
    Always use "I/you" — never introduce yourself or mention your role name.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點距離：{distance_hint}

    景點資訊：
    {poi_context}

    請用你的風格，以繁體中文撰寫一段約{target_length}字的旁白。語氣神秘，偏好人物軼事、背後秘辛。

    開頭規則：直接以小聲透露的語氣開始（例如：「欸，你知道這裡背後...」、「靠過來一點，我偷偷告訴你...」），不得打招呼或自我介紹。
    距離規則：若景點距離 > 50m，禁止使用「眼前」「正前方」等近距離詞彙，請改用「{distance_hint}」等自然表達。
  en: |
    You are now narrating for "{poi_name}".

    Distance to this location: {distance_hint}

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in your style. Keep the mysterious, whispered tone and focus on behind-the-scenes stories.

    Opening rule: Start directly with a conspiratorial whisper (e.g., "Psst, come closer..."), never with a greeting.
    Distance rule: If distance hint is "nearby" or "in this area", avoid "right in front of you" — use the distance hint phrasing naturally.
no_data_context:
  zh-TW: 欸，這個地方我打聽不到什麼八卦，等等再說！
  en: Hmm, I couldn't dig up any gossip here — let's move on and see what's next!
qa_template:
  zh-TW: "請用你的風格，以繁體中文回答：{question}"
  en: "Please answer in your style: {question}"
system_messages:
  zh-TW:
    network_offline:
      - "哎，網路不給力，等我一下，有更多秘辛要跟你說！"
    rate_limit:
      - "說太多了要稍微停一停，30 秒後我繼續跟你爆料！"
confidence_labels:
  zh-TW:
    high: null
    medium:
      - "關於這個，我聽說是這樣..."
    low:
      - "這個嘛，真實情況不太確定，但我猜..."
```

- [ ] **Step 7: Rewrite foodie.yaml**

Replace the full content of `backend/prompts/personas/foodie.yaml`:

```yaml
id: foodie
display_name:
  zh-TW: 美食家
  en: The Foodie
voice:
  zh-TW: zh-TW-HsiaoChenNeural
  en: en-US-AriaNeural
voice_style:
  speaking_rate: 1.0
  emotion: warm
style_profile:
  embellishment: 0.4
  preferred_topics:
    - food_culture
    - local_cuisine
    - culinary_history
poi_source: google_places
default_trigger_radius_m: 50
system_prompt:
  zh-TW: |
    你是一位以美食視角看世界的資深旅遊夥伴，擅長發掘景點附近的飲食文化與在地美味。
    你說話溫暖熱情，喜歡用感官描述（味道、香氣、口感）讓旅程充滿味覺記憶。
    請用繁體中文與對方交流，語氣溫暖親切，讓人垂涎三尺。
    永遠用「我/你」互稱，不要自我介紹或提及自己的角色名稱。
  en: |
    You are a seasoned travel companion who sees the world through the lens of food and culinary culture.
    You speak warmly and passionately, using sensory descriptions (taste, aroma, texture) to make journeys memorable.
    Narrate in English with a warm, appetizing tone that makes people hungry for more.
    Always use "I/you" — never introduce yourself or mention your role name.
narration_template:
  zh-TW: |
    你現在在為「{poi_name}」進行旁白。

    景點距離：{distance_hint}

    景點資訊：
    {poi_context}

    請用你的風格，以繁體中文撰寫一段約{target_length}字的旁白。
    著重挖掘這個地方的飲食文化、歷史與在地特色，語氣溫暖熱情。

    開頭規則：直接從感官描述開始（例如：「聞到了嗎？這附近的空氣飄著______的香氣」、「你看這家店的招牌...」），不得打招呼。
    距離規則：若景點距離 > 50m，禁止使用「眼前」「正前方」等近距離詞彙，請改用「{distance_hint}」等自然表達。
  en: |
    You are now narrating for "{poi_name}".

    Distance to this location: {distance_hint}

    Location information:
    {poi_context}

    Please write a narration of approximately {target_length} words in your style.
    Focus on the food culture, history, and local character. Keep the tone warm and enthusiastic.

    Opening rule: Start directly with sensory description (e.g., "Can you smell that?"), never with a greeting.
    Distance rule: If distance hint is "nearby" or "in this area", avoid "right in front of you" — use the distance hint phrasing naturally.
no_data_context:
  zh-TW: 這裡好像沒什麼值得特別介紹的，等等前面有好料！
  en: Nothing much to say about this spot — better things ahead, I promise!
qa_template:
  zh-TW: "請用你的風格，以繁體中文回答：{question}"
  en: "Please answer in your style: {question}"
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
      - "這個地方的資料不多，但我認為..."
    low:
      - "史料有限，純粹以我的直覺推測..."
```

- [ ] **Step 8: Run existing prompt builder tests to confirm they still pass**

```bash
cd backend && python -m pytest tests/unit/test_prompt_builder.py tests/unit/test_persona_loader.py -v
```

Expected: All PASS (the updated assertion works; `{distance_hint}` in template causes KeyError only when builder runs without it — builder is fixed in Task 3).

Note: `test_build_poi_name_in_user_message` and similar tests will fail after this step because the narration_template now requires `{distance_hint}` which `PromptBuilder.build()` doesn't yet provide. That's expected — it will be fixed in Task 3.

- [ ] **Step 9: Commit YAML and test changes**

```bash
git add backend/prompts/personas/ backend/tests/unit/test_prompt_builder.py
git commit -m "fix(personas): remove third-person self-naming, add distance_hint placeholder"
```

---

## Task 3: Backend — distance_m in POIContext + PromptBuilder (Issue 2)

**Files:**
- Modify: `backend/src/tour_guide/models/poi.py`
- Modify: `backend/src/tour_guide/prompts/builder.py`
- Modify: `backend/src/tour_guide/api/narration.py`
- Modify: `backend/tests/unit/test_prompt_builder.py`

- [ ] **Step 1: Write failing tests for distance_hint in PromptBuilder**

Add to `backend/tests/unit/test_prompt_builder.py` inside `class TestPromptBuilderBuild`:

```python
    def test_build_distance_hint_nearby_when_close(self, history_uncle_persona):
        """distance_m < 30 → '就在你附近' appears in user message."""
        osm = OsmNode(id="osm:node:1", lat=25.0, lon=121.5, tags={"name": "近景點"})
        poi = POIContext(osm=osm, wiki=None, distance_m=15.0)
        messages = PromptBuilder.build(
            persona=history_uncle_persona, poi=poi, lang="zh-TW", length="medium"
        )
        user_content = " ".join(m["content"] for m in messages if m["role"] == "user")
        assert "就在你附近" in user_content

    def test_build_distance_hint_not_far_when_medium(self, history_uncle_persona):
        """distance_m 30–150 → '前方不遠處' appears in user message."""
        osm = OsmNode(id="osm:node:2", lat=25.0, lon=121.5, tags={"name": "中景點"})
        poi = POIContext(osm=osm, wiki=None, distance_m=80.0)
        messages = PromptBuilder.build(
            persona=history_uncle_persona, poi=poi, lang="zh-TW", length="medium"
        )
        user_content = " ".join(m["content"] for m in messages if m["role"] == "user")
        assert "前方不遠處" in user_content

    def test_build_distance_hint_this_area_when_far(self, history_uncle_persona):
        """distance_m 150–500 → '這附近' appears in user message."""
        osm = OsmNode(id="osm:node:3", lat=25.0, lon=121.5, tags={"name": "遠景點"})
        poi = POIContext(osm=osm, wiki=None, distance_m=250.0)
        messages = PromptBuilder.build(
            persona=history_uncle_persona, poi=poi, lang="zh-TW", length="medium"
        )
        user_content = " ".join(m["content"] for m in messages if m["role"] == "user")
        assert "這附近" in user_content

    def test_build_distance_hint_in_this_area_when_very_far(self, history_uncle_persona):
        """distance_m > 500 → '這一帶' appears in user message."""
        osm = OsmNode(id="osm:node:4", lat=25.0, lon=121.5, tags={"name": "超遠景點"})
        poi = POIContext(osm=osm, wiki=None, distance_m=800.0)
        messages = PromptBuilder.build(
            persona=history_uncle_persona, poi=poi, lang="zh-TW", length="medium"
        )
        user_content = " ".join(m["content"] for m in messages if m["role"] == "user")
        assert "這一帶" in user_content
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
cd backend && python -m pytest tests/unit/test_prompt_builder.py::TestPromptBuilderBuild::test_build_distance_hint_nearby_when_close -v
```

Expected: FAIL — `KeyError: 'distance_hint'` (template has `{distance_hint}` but builder doesn't provide it yet).

- [ ] **Step 3: Add `distance_m` to `POIContext`**

In `backend/src/tour_guide/models/poi.py`, update `POIContext`:

```python
@dataclass
class POIContext:
    osm: OsmNode
    wiki: WikiArticle | None = None
    distance_m: float = 0.0
```

- [ ] **Step 4: Update `PromptBuilder.build()` to derive and inject `distance_hint`**

In `backend/src/tour_guide/prompts/builder.py`, add a static method and update `build()`:

```python
    DISTANCE_HINTS: ClassVar[dict[str, list[tuple[float, str]]]] = {
        "zh-TW": [
            (30.0, "就在你附近"),
            (150.0, "前方不遠處"),
            (500.0, "這附近"),
            (float("inf"), "這一帶"),
        ],
        "en": [
            (30.0, "right here"),
            (150.0, "not far ahead"),
            (500.0, "nearby"),
            (float("inf"), "in this area"),
        ],
    }

    @staticmethod
    def _distance_hint(distance_m: float, lang: str) -> str:
        bins = PromptBuilder.DISTANCE_HINTS.get(lang, PromptBuilder.DISTANCE_HINTS["en"])
        for threshold, label in bins:
            if distance_m < threshold:
                return label
        return bins[-1][1]
```

Then in `build()`, add `distance_hint` to the template format call:

```python
    @staticmethod
    def build(
        persona: PersonaConfig,
        poi: POIContext,
        lang: str,
        length: str,
    ) -> list[dict]:
        # ... existing code for poi_name, poi_context_str, target_length, templates ...

        distance_hint = PromptBuilder._distance_hint(poi.distance_m, lang)

        user_prompt_text = narration_template_text.format(
            poi_name=poi_name,
            poi_context=poi_context_str,
            target_length=target_length,
            distance_hint=distance_hint,
        )

        messages = [
            {"role": "system", "content": system_prompt_text},
            {"role": "user", "content": user_prompt_text},
        ]

        return messages
```

- [ ] **Step 5: Pass `distance_m` from narration API into `POIContext`**

In `backend/src/tour_guide/api/narration.py`, update the `poi_context` construction:

```python
    poi_context = POIContext(
        osm=OsmNode(id=selected.poi_id, lat=selected.poi_lat, lon=selected.poi_lon, tags=tags),
        wiki=wiki,
        distance_m=selected.distance_m,
    )
```

- [ ] **Step 6: Run all prompt builder tests**

```bash
cd backend && python -m pytest tests/unit/test_prompt_builder.py -v
```

Expected: All PASS

- [ ] **Step 7: Run full backend test suite**

```bash
cd backend && python -m pytest tests/unit/ -v
```

Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add backend/src/tour_guide/models/poi.py \
        backend/src/tour_guide/prompts/builder.py \
        backend/src/tour_guide/api/narration.py \
        backend/tests/unit/test_prompt_builder.py
git commit -m "feat(backend): add distance_hint to prompt via POIContext.distance_m"
```

---

## Task 4: Backend — is_no_data flag on MetaEvent (Issue 3)

**Files:**
- Modify: `backend/src/tour_guide/services/narration_service.py`
- Modify: `backend/tests/unit/test_narration_service.py`

- [ ] **Step 1: Write failing test for is_no_data flag**

Add to `backend/tests/unit/test_narration_service.py`:

```python
@pytest.mark.asyncio
async def test_no_data_meta_event_has_is_no_data_true(fake_persona, poi_no_wiki):
    """MetaEvent yielded for wiki-None POI must have is_no_data=True."""
    fake_llm = make_fake_llm([])
    fake_tts = make_fake_tts()

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi_no_wiki, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    meta_events = [e for e in events if isinstance(e, MetaEvent)]
    assert len(meta_events) == 1
    assert meta_events[0].is_no_data is True


@pytest.mark.asyncio
async def test_normal_meta_event_has_is_no_data_false(fake_persona):
    """MetaEvent yielded for POI with wiki must have is_no_data=False."""
    from tour_guide.models.poi import WikiArticle
    osm = OsmNode(id="osm:node:2", lat=25.0, lon=121.5, tags={"name": "故宮"})
    wiki = WikiArticle(title="故宮", extract="故宮是...", url="", lang="zh-TW")
    poi = POIContext(osm=osm, wiki=wiki)

    fake_llm = make_fake_llm(["故宮是一個博物館。"])
    fake_tts = make_fake_tts()

    service = NarrationService(llm=fake_llm, tts=fake_tts, cache=None)
    events = []
    async for event in service.narrate(poi, fake_persona, lang="zh-TW", length="medium"):
        events.append(event)

    meta_events = [e for e in events if isinstance(e, MetaEvent)]
    assert len(meta_events) == 1
    assert meta_events[0].is_no_data is False
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && python -m pytest tests/unit/test_narration_service.py::test_no_data_meta_event_has_is_no_data_true -v
```

Expected: FAIL — `AttributeError: 'MetaEvent' object has no attribute 'is_no_data'`

- [ ] **Step 3: Add `is_no_data` field to `MetaEvent` and update `narrate()`**

In `backend/src/tour_guide/services/narration_service.py`:

Add field to `MetaEvent`:
```python
@dataclass
class MetaEvent:
    type: Literal["meta"] = "meta"
    poi_id: str = ""
    poi_name: str = ""
    cache_hit: bool = False
    confidence: str = "low"
    estimated_duration_s: int = 0
    is_no_data: bool = False
```

In `NarrationService.narrate()`, determine `is_no_data` before yielding MetaEvent (cache-miss path):

```python
        # 2. Cache miss (or no cache / force_regenerate): run full pipeline
        log_event(logger, LogEvents.NARRATION_START, poi_id=poi.osm.id, cache_hit=False)
        is_no_data = poi.wiki is None
        yield MetaEvent(
            poi_id=poi.osm.id,
            poi_name=poi_name,
            cache_hit=False,
            confidence=confidence,
            is_no_data=is_no_data,
        )
```

Remove the separate `MetaEvent` yield that was originally before the `no_data` check (the code above replaces it). The existing structure already works — you're just adding `is_no_data=is_no_data` to the existing MetaEvent yield.

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd backend && python -m pytest tests/unit/test_narration_service.py -v
```

Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add backend/src/tour_guide/services/narration_service.py \
        backend/tests/unit/test_narration_service.py
git commit -m "feat(backend): add is_no_data flag to MetaEvent for no-wiki POIs"
```

---

## Task 5: Frontend — MetaEvent isNoData + consecutive no-data dedup (Issue 3)

**Files:**
- Modify: `flutter_app/lib/shared/backend/models/narration_event.dart`
- Modify: `flutter_app/lib/features/narration/providers/narration_provider.dart`

- [ ] **Step 1: Add `isNoData` to Flutter `MetaEvent`**

In `flutter_app/lib/shared/backend/models/narration_event.dart`, update `MetaEvent`:

```dart
class MetaEvent extends NarrationEvent {
  final String poiId;
  final String poiName;
  final bool cacheHit;
  final String confidence;
  final int estimatedDurationS;
  final bool isNoData;

  const MetaEvent({
    required this.poiId,
    this.poiName = '',
    required this.cacheHit,
    required this.confidence,
    this.estimatedDurationS = 0,
    this.isNoData = false,
  });

  factory MetaEvent.fromJson(Map<String, dynamic> json) => MetaEvent(
        poiId: json['poi_id'] as String,
        poiName: json['poi_name'] as String? ?? '',
        cacheHit: json['cache_hit'] as bool,
        confidence: json['confidence'] as String,
        estimatedDurationS: (json['estimated_duration_s'] as num? ?? 0).toInt(),
        isNoData: json['is_no_data'] as bool? ?? false,
      );
}
```

- [ ] **Step 2: Write failing test for no-data dedup in NarrationNotifier**

Add a new test file `flutter_app/test/unit/narration_provider_test.dart`:

```dart
import 'dart:async';
import 'dart:typed_data';
import 'package:drift/native.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_app/features/narration/providers/narration_provider.dart';
import 'package:flutter_app/shared/audio/audio_player_service.dart';
import 'package:flutter_app/shared/backend/backend_client.dart';
import 'package:flutter_app/shared/backend/models/narration_event.dart';
import 'package:flutter_app/shared/backend/models/poi.dart';
import 'package:flutter_app/shared/backend/models/qa_event.dart';
import 'package:flutter_app/shared/db/local_db.dart';
import 'package:flutter_app/shared/providers.dart';

const _poi = POI(
  id: 'osm:node:1',
  name: '無名景點',
  lat: 25.0,
  lon: 121.5,
  tags: {},
  distanceM: 80,
  confidence: 'low',
);

class _ScriptedBackendClient implements BackendClient {
  final List<List<NarrationEvent>> _scripts;
  int _callIndex = 0;

  _ScriptedBackendClient(this._scripts);

  @override
  Future<List<POI>> fetchNearby({required double lat, required double lon,
      required int radius, required String lang, required String persona}) async => [];

  @override
  Stream<NarrationEvent> narrate({required List<POI> candidates,
      required String persona, required String lang, required String length,
      PreviousSelection? previousSelection, bool forceRegenerate = false}) async* {
    final events = _scripts[_callIndex % _scripts.length];
    _callIndex++;
    for (final e in events) yield e;
  }

  @override
  Stream<QaEvent> qa({required Uint8List audioBytes, required String persona,
      required String lang, String? currentPoiId, String narrationSoFar = ''}) async* {}
}

void main() {
  test('second consecutive no-data narration is suppressed (goes idle without playing)', () async {
    final noDataEvents = [
      const MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'low', isNoData: true),
      const EndEvent(),
    ];

    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());
    final client = _ScriptedBackendClient([noDataEvents, noDataEvents]);

    final container = ProviderContainer(
      overrides: [
        backendClientProvider.overrideWithValue(client),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    final notifier = container.read(narrationProvider.notifier);
    container.listen(narrationProvider, (_, __) {});

    // First no-data narration — plays normally
    await notifier.narrate(candidates: [_poi], persona: 'history_uncle', lang: 'zh-TW');
    await Future<void>.delayed(const Duration(milliseconds: 50));
    expect(fakeAudio.enqueuedChunks.length, 0); // no_data uses no wiki path, no audio in MetaEvent-only test

    // Second no-data narration — should be suppressed
    await notifier.narrate(candidates: [_poi], persona: 'history_uncle', lang: 'zh-TW');
    await Future<void>.delayed(const Duration(milliseconds: 50));

    final state = container.read(narrationProvider);
    expect(state.status, NarrationStatus.idle);
    // Only 0 audio chunks — second narration was cancelled immediately
    expect(fakeAudio.enqueuedChunks.length, 0);
  });
}
```

- [ ] **Step 3: Run test to verify it fails**

```bash
cd flutter_app && flutter test test/unit/narration_provider_test.dart
```

Expected: FAIL — second narration still plays (not suppressed).

- [ ] **Step 4: Add `_lastWasNoData` dedup logic to `NarrationNotifier`**

In `flutter_app/lib/features/narration/providers/narration_provider.dart`:

Add field:
```dart
  bool _lastWasNoData = false;
```

Update `_handle()` for `MetaEvent` case. Find the existing `case MetaEvent(...)` and add dedup logic at the top:

```dart
      case MetaEvent(:final poiId, :final poiName, :final confidence):
        // Read isNoData from the event (requires pattern matching update)
```

Since the case pattern needs to include `isNoData`, update the pattern:

```dart
      case MetaEvent(:final poiId, :final poiName, :final confidence, :final isNoData):
        if (isNoData && _lastWasNoData) {
          _lastWasNoData = true;
          _sub?.cancel();
          _sub = null;
          state = state.copyWith(
            status: NarrationStatus.idle,
            lastEventWasSkip: false,
          );
          return;
        }
        _lastWasNoData = isNoData;
        final selectedPoi = _candidates.firstWhere(
          (p) => p.id == poiId,
          orElse: () => _candidates.isNotEmpty
              ? _candidates.first
              : POI(
                  id: poiId,
                  name: poiName,
                  lat: 0,
                  lon: 0,
                  tags: {},
                  distanceM: 0,
                  confidence: confidence,
                ),
        );
        AppLogger.info(LogEvents.narrationStart, {'poi_id': poiId, 'poi_name': poiName});
        state = state.copyWith(
          status: NarrationStatus.playing,
          currentPoi: selectedPoi,
          confidence: confidence,
        );
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
cd flutter_app && flutter test test/unit/narration_provider_test.dart
```

Expected: PASS

- [ ] **Step 6: Run full Flutter unit test suite**

```bash
cd flutter_app && flutter test test/unit/
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/shared/backend/models/narration_event.dart \
        flutter_app/lib/features/narration/providers/narration_provider.dart \
        flutter_app/test/unit/narration_provider_test.dart
git commit -m "feat(flutter): suppress consecutive no-data narrations via is_no_data flag"
```

---

## Task 6: Frontend — Defer idle until audio playback completes (Issue 5)

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/narration_provider.dart`

- [ ] **Step 1: Write failing test for audio-deferred idle**

Add to `flutter_app/test/unit/narration_provider_test.dart`:

```dart
  test('NarrationStatus stays playing after EndEvent until audio stops', () async {
    // Simulate: MetaEvent → AudioEvent (not played here) → EndEvent
    // NarrationStatus should NOT go idle immediately after EndEvent
    // It goes idle only when isPlayingStream emits false

    final playingController = StreamController<bool>.broadcast();
    final fakeAudio = _ManualAudioPlayerService(playingController.stream);
    final db = LocalDb.forTesting(NativeDatabase.memory());

    const events = [
      MetaEvent(poiId: 'osm:node:1', cacheHit: false, confidence: 'high', isNoData: false),
      EndEvent(),
    ];
    final client = _ScriptedBackendClient([events]);

    final container = ProviderContainer(
      overrides: [
        backendClientProvider.overrideWithValue(client),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
      ],
    );
    addTearDown(() { container.dispose(); playingController.close(); });
    addTearDown(db.close);

    container.listen(narrationProvider, (_, __) {});
    await container.read(narrationProvider.notifier).narrate(
      candidates: [_poi], persona: 'history_uncle', lang: 'zh-TW',
    );
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // After EndEvent, status should still be playing (audio not done yet)
    expect(container.read(narrationProvider).status, NarrationStatus.playing);

    // Now audio finishes
    playingController.add(false);
    await Future<void>.delayed(const Duration(milliseconds: 50));

    // Now idle
    expect(container.read(narrationProvider).status, NarrationStatus.idle);
  });
```

Add helper class to the same test file:

```dart
class _ManualAudioPlayerService implements AudioPlayerService {
  final Stream<bool> _playingStream;
  _ManualAudioPlayerService(this._playingStream);

  @override Future<void> enqueueBytes(Uint8List bytes) async {}
  @override Future<void> reset() async {}
  @override Future<void> pause() async {}
  @override Future<void> resume() async {}
  @override Future<void> skip() async {}
  @override Future<void> duck() async {}
  @override Future<void> unduck() async {}
  @override Stream<bool> get isPlayingStream => _playingStream;
  @override Future<void> dispose() async {}
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd flutter_app && flutter test test/unit/narration_provider_test.dart
```

Expected: FAIL — status transitions to `idle` immediately after EndEvent.

- [ ] **Step 3: Update `NarrationNotifier` to defer idle until audio stops**

In `flutter_app/lib/features/narration/providers/narration_provider.dart`:

Add fields after the existing fields:
```dart
  StreamSubscription<bool>? _audioSub;
  bool _sseStreamEnded = false;
```

Update `narrate()` to reset them:
```dart
  Future<void> narrate({...}) async {
    _currentPersona = persona;
    _currentLang = lang;
    _candidates = candidates;
    _sseStreamEnded = false;
    _audioSub?.cancel();
    _audioSub = null;
    await _sub?.cancel();
    await _audio.reset();
    // ... rest of existing narrate() body unchanged ...
  }
```

Replace the `EndEvent` case in `_handle()`:
```dart
      case EndEvent():
        final durationMs = _narrationStartedAt != null
            ? DateTime.now().difference(_narrationStartedAt!).inMilliseconds
            : 0;
        final poi = state.currentPoi;
        AppLogger.info(LogEvents.narrationComplete, {
          'poi_id': poi?.id ?? '',
          'duration_ms': durationMs,
          'total_chars': state.subtitle.length,
        });
        _narrationStartedAt = null;
        if (poi != null) _recordNarration(poi);
        _sseStreamEnded = true;
        // Defer idle until audio playback finishes
        _audioSub?.cancel();
        _audioSub = _audio.isPlayingStream.listen((isPlaying) {
          if (!isPlaying && _sseStreamEnded && state.status != NarrationStatus.paused) {
            _audioSub?.cancel();
            _audioSub = null;
            _sseStreamEnded = false;
            state = state.copyWith(
              status: NarrationStatus.idle,
              progress: 1.0,
            );
          }
        });
```

Also cancel `_audioSub` in `skip()` and `dispose()`:

```dart
  Future<void> skip() async {
    _audioSub?.cancel();
    _audioSub = null;
    _sseStreamEnded = false;
    AppLogger.warn(LogEvents.narrationSkip, {
      'poi_id': state.currentPoi?.id ?? '',
      'reason': 'user_skip',
    });
    await _sub?.cancel();
    await _audio.skip();
    state = state.copyWith(status: NarrationStatus.idle);
  }

  @override
  void dispose() {
    _sub?.cancel();
    _audioSub?.cancel();
    super.dispose();
  }
```

Also cancel `_audioSub` in the no-data dedup path (from Task 5):
```dart
        if (isNoData && _lastWasNoData) {
          _lastWasNoData = true;
          _audioSub?.cancel();
          _audioSub = null;
          _sseStreamEnded = false;
          _sub?.cancel();
          _sub = null;
          state = state.copyWith(
            status: NarrationStatus.idle,
            lastEventWasSkip: false,
          );
          return;
        }
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
cd flutter_app && flutter test test/unit/narration_provider_test.dart
```

Expected: All PASS

- [ ] **Step 5: Run full Flutter unit test suite**

```bash
cd flutter_app && flutter test test/unit/
```

Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add flutter_app/lib/features/narration/providers/narration_provider.dart \
        flutter_app/test/unit/narration_provider_test.dart
git commit -m "fix(flutter): countdown deferred until audio playback finishes"
```

---

## Task 7: Frontend — TriggerProvider POI dedup guard (Issue 4)

**Files:**
- Modify: `flutter_app/lib/features/narration/providers/trigger_provider.dart`
- Modify: `flutter_app/test/unit/trigger_provider_test.dart`

- [ ] **Step 1: Write failing test for dedup guard**

Add to `flutter_app/test/unit/trigger_provider_test.dart`:

```dart
  test('TriggerProvider skips narrate() when POIs unchanged and user did not move', () async {
    final fakeLocation = FakeLocationService();
    final fakeAudio = FakeAudioPlayerService();
    final db = LocalDb.forTesting(NativeDatabase.memory());

    // Same POI, same position → second countdown should not call narrate()
    int callCount = 0;
    final trackingClient = _CountingBackendClient(
      nearbyPois: const [_poi],
      firstEvents: const [EndEvent()],
      subsequentEvents: const [EndEvent()],
    );

    final container = ProviderContainer(
      overrides: [
        locationServiceProvider.overrideWithValue(fakeLocation),
        backendClientProvider.overrideWithValue(trackingClient),
        audioPlayerServiceProvider.overrideWithValue(fakeAudio),
        localDbProvider.overrideWithValue(db),
        sessionLangProvider.overrideWithValue('zh-TW'),
        fallbackTimeoutProvider.overrideWithValue(const Duration(seconds: 30)),
        appSettingsProvider.overrideWith(
          () => _FakeSettingsNotifier(
            const AppSettings(skipDisplacementM: 500, countdownSeconds: 1),
          ),
        ),
      ],
    );
    addTearDown(container.dispose);
    addTearDown(db.close);

    container.listen(triggerProvider, (_, __) {});
    container.listen(narrationProvider, (_, __) {});

    // Emit position and let first narration fire
    fakeLocation.emit(fakePosition(25.1023, 121.5482));
    await Future<void>.delayed(const Duration(milliseconds: 200));

    final firstCallCount = trackingClient.callCount;
    expect(firstCallCount, 1); // First trigger always fires

    // Wait for 1-second countdown to expire and check if second call is skipped
    await Future<void>.delayed(const Duration(seconds: 2));

    // No movement emitted — same position, same POIs → guard should skip
    expect(trackingClient.callCount, firstCallCount); // No second call
  });
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart --name "skips narrate"
```

Expected: FAIL — `trackingClient.callCount` is 2 (dedup guard not yet implemented).

- [ ] **Step 3: Add dedup fields and position tracking to `TriggerNotifier`**

In `flutter_app/lib/features/narration/providers/trigger_provider.dart`:

Add fields after existing `_locationSub`:
```dart
  Position? _currentPosition;
  Position? _lastTriggerPosition;
  Set<String> _lastCandidateIds = {};
  StreamSubscription<Position>? _positionTrackSub;
```

In `build()`, add a persistent position tracker before `return const TriggerState()`:
```dart
    _positionTrackSub = ref.read(locationServiceProvider).positionStream.listen((pos) {
      _currentPosition = pos;
    });

    ref.onDispose(() {
      _cooldownTimer?.cancel();
      _locationSub?.cancel();
      _positionTrackSub?.cancel();
    });

    return const TriggerState();
```

- [ ] **Step 4: Add dedup guard to `_doCandidatesRequest()` and update tracking**

In `_doCandidatesRequest()`, add the guard after the `available.isEmpty` check and before the `narrate()` call:

```dart
    // Dedup guard: skip if user hasn't moved AND POI list is nearly identical
    if (_lastTriggerPosition != null &&
        _currentPosition != null &&
        _lastCandidateIds.isNotEmpty) {
      final moved = haversine(
        _lastTriggerPosition!.latitude,
        _lastTriggerPosition!.longitude,
        _currentPosition!.latitude,
        _currentPosition!.longitude,
      );
      final currentIds = available.map((p) => p.id).toSet();
      final intersectionSize =
          currentIds.intersection(_lastCandidateIds).length;
      final unionSize = currentIds.union(_lastCandidateIds).length;
      final jaccard = unionSize > 0 ? intersectionSize / unionSize : 0.0;

      if (moved < 30 && jaccard >= 0.8) {
        AppLogger.info(LogEvents.triggerSkip, {
          'reason': 'poi_unchanged',
          'moved_m': moved,
          'jaccard': jaccard,
        });
        return;
      }
    }

    // Update tracking before calling narrate
    _lastTriggerPosition = _currentPosition;
    _lastCandidateIds = available.map((p) => p.id).toSet();
```

Place this block right before `final session = ref.read(sessionProvider);`.

- [ ] **Step 5: Run all trigger provider tests**

```bash
cd flutter_app && flutter test test/unit/trigger_provider_test.dart
```

Expected: All PASS

- [ ] **Step 6: Run full Flutter test suite**

```bash
cd flutter_app && flutter test test/
```

Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add flutter_app/lib/features/narration/providers/trigger_provider.dart \
        flutter_app/test/unit/trigger_provider_test.dart
git commit -m "fix(flutter): skip LLM request when user hasn't moved and POIs unchanged"
```

---

## Self-Review

**Spec coverage check:**
- ✅ Issue 1 (persona self-naming): Task 2 — all 5 YAMLs rewritten with first-person system_prompt, no role labels
- ✅ Issue 2 (distance language): Task 2 (YAML template) + Task 3 (backend model + builder)
- ✅ Issue 3 (no-data dedup): Task 4 (backend is_no_data) + Task 5 (frontend dedup)
- ✅ Issue 4 (redundant requests): Task 7 (TriggerProvider guard)
- ✅ Issue 5 (countdown timing): Task 6 (NarrationNotifier audio subscription)
- ✅ Issue 6 (progress bar): Task 1 (SizedBox.expand)

**Type consistency:**
- `POIContext.distance_m: float` introduced in Task 3 Step 3, used in Task 3 Step 4 — consistent
- `MetaEvent.is_no_data: bool` added in Task 4, parsed in Task 5 as `isNoData` — consistent naming (snake_case backend, camelCase Dart)
- `_audioSub` introduced in Task 6, also referenced in Task 5 no-data path — consistent

**No placeholders:** All steps contain complete code.
