# Plan D — Push-to-talk Q&A 設計文件

| 欄位 | 內容 |
|---|---|
| 文件版本 | v1.0 |
| 撰寫日期 | 2026-05-13 |
| 適用範圍 | Plan D：Push-to-talk Q&A |
| 前置條件 | Plan C（Persona 系統 + 雙語）已完成 |

---

## 1. 目標

在 AI Tour Guide App 新增 Push-to-talk Q&A 功能：

1. 使用者在 MapScreen 長按麥克風按鈕開始錄音
2. 放開後錄音送後端：STT → LLM（同 persona context）→ TTS 串流
3. 旁白音量降至 50%（ducking）不暫停，Q&A 音訊另起播放
4. Q&A 播完後旁白恢復正常音量
5. Q&A 不快取、不寫 cooldown/history

---

## 2. 整體架構

```
MapScreen (session active)
 └── PushToTalkButton (底部固定, GestureDetector)
      onLongPressStart → QaNotifier.startRecording()
                          └─ narrationAudioPlayer.duck()   ← 旁白降 50%
                          └─ MicRecorderService.start()
      onLongPressEnd   → QaNotifier.stopAndSend()
                          └─ MicRecorderService.stop() → audioBytes
                          └─ BackendClient.qa(audio, ctx) → Stream<QaEvent>
                          └─ qaAudioPlayerService.enqueueBytes(chunk)
                          └─ [EndQaEvent] → narrationAudioPlayer.unduck()
```

### 新增元件

**Backend：**
- `SttProvider`（abstract + `GeminiSttProvider` + `FakeSttProvider`）
- `QAService`：audio → STT → PromptBuilder.qa() → LLM → SentenceSplitter → TTS → SSE events
- `/qa` endpoint（multipart POST + SSE 回應）
- `PromptBuilder.build_qa()`：組裝 Q&A prompt（system + narration summary + user question）

**Flutter：**
- `MicRecorderService`（abstract + `RealMicRecorderService` + `FakeMicRecorderService`）
- `BackendClient.qa()` 方法 + `QaEvent` sealed class
- `AudioPlayerService.duck() / unduck()` 新方法
- `qaAudioPlayerProvider`（獨立於旁白的第二個 AudioPlayer 實例）
- `QaNotifier` + `qaProvider`（Q&A 狀態機）
- `PushToTalkButton` widget

---

## 3. Backend 設計

### 3.1 SttProvider

```python
class SttProvider(Protocol):
    async def transcribe(self, audio_bytes: bytes, lang: str) -> str: ...

class GeminiSttProvider:
    """Sends audio to Gemini multimodal API for transcription."""

class FakeSttProvider:
    def __init__(self, scripted_text: str): ...
```

### 3.2 QAService

```python
class QAService:
    def __init__(self, stt: SttProvider, llm: LlmProvider, tts: TtsProvider) -> None: ...

    async def answer(
        self,
        audio_bytes: bytes,
        persona: PersonaConfig,
        lang: str,
        current_poi_id: str | None,
        narration_so_far: str,
    ) -> AsyncIterator[QAEvent]: ...
```

**SSE 事件序列（/qa 獨有 transcript + 共用 text/audio/end/error）：**

```
TranscriptEvent → {"text": "這個館為什麼這麼重要？"}
TextEvent       → {"chunk": "啊，這問得好...", "sentence_idx": 0}
AudioEvent      → {"chunk_b64": "...", "sentence_idx": 0}
...（更多 text + audio pairs）...
EndEvent        → {}
```

**QAEvent 型別：**

```python
@dataclass
class TranscriptEvent:
    type: Literal["transcript"] = "transcript"
    text: str = ""

# 重用 TextEvent / AudioEvent / EndEvent / ErrorEvent（與 NarrationService 共用）
QAEvent = TranscriptEvent | TextEvent | AudioEvent | EndEvent | ErrorEvent
```

### 3.3 /qa Endpoint

**Request（multipart/form-data）：**
```
POST /qa
Content-Type: multipart/form-data

audio:   <wav binary>
context: {
  "current_poi_id": "osm:way:12345",   # nullable（無旁白時為 null）
  "persona": "history_uncle",
  "lang": "zh-TW",
  "narration_so_far": "..."            # 旁白已播出的字幕文字
}
```

**Response（text/event-stream）：**
```
event: transcript
data: {"text":"這個館為什麼這麼重要？"}

event: text
data: {"chunk":"啊，這問得好...", "sentence_idx":0}

event: audio
data: {"chunk_b64":"<base64-wav>","sentence_idx":0}

event: end
data: {}
```

**錯誤：**
- `400`：persona 不存在
- SSE `error` event：STT 失敗、LLM rate limit 等

**無快取、無 cooldown/history 寫入。**

### 3.4 PromptBuilder.build_qa()

```python
@staticmethod
def build_qa(
    persona: PersonaConfig,
    lang: str,
    current_poi_id: str | None,
    narration_so_far: str,
    user_question: str,
) -> list[dict]:
    """Build QA messages using persona's qa_template."""
```

- 有 POI context：用 `qa_template` 填入 poi_name、narration_summary、user_question
- 無 POI context（`current_poi_id=None`）：prompt 改為「使用者主動提問，請以 persona 口吻自然回答」

### 3.5 main.py DI 更新

```python
qa_service = QAService(
    stt=GeminiSttProvider(api_key=config.gemini_api_key),
    llm=llm_provider,
    tts=tts_provider,
)
app.dependency_overrides[get_qa_service] = lambda: qa_service
```

---

## 4. Flutter 設計

### 4.1 MicRecorderService

```dart
abstract class MicRecorderService {
  Future<void> startRecording();
  Future<Uint8List> stopAndGetBytes();  // 停止錄音並回傳 WAV bytes
  Future<void> cancelRecording();
  Future<void> dispose();
}

class RealMicRecorderService implements MicRecorderService {
  // 使用 record ^5.0 套件
  // 錄音格式：AudioEncoder.wav（通用、後端解析簡單）
  // 錄到暫存檔，stopAndGetBytes() 讀取後刪除
}

class FakeMicRecorderService implements MicRecorderService {
  final Uint8List fakeAudio;
  // startRecording/cancelRecording: no-op
  // stopAndGetBytes: 回傳 fakeAudio
}
```

**pubspec.yaml 新增：**
```yaml
record: ^5.0.0
```

### 4.2 AudioPlayerService 擴充

```dart
abstract class AudioPlayerService {
  // 現有方法不變
  Future<void> enqueueBytes(Uint8List bytes);
  Future<void> pause();
  Future<void> resume();
  Future<void> skip();
  Stream<bool> get isPlayingStream;
  Future<void> dispose();

  // 新增
  Future<void> duck();    // setVolume(0.5)
  Future<void> unduck();  // setVolume(1.0)
}

// RealAudioPlayerService 實作：
// duck()   → _player.setVolume(0.5)
// unduck() → _player.setVolume(1.0)

// FakeAudioPlayerService 實作：
// 記錄 isDucked 狀態供 test 驗證
```

### 4.3 BackendClient.qa() 與 QaEvent

```dart
// QaEvent sealed class
sealed class QaEvent {}
class TranscriptQaEvent extends QaEvent { final String text; ... }
class TextQaEvent       extends QaEvent { final String chunk; final int sentenceIdx; ... }
class AudioQaEvent      extends QaEvent { final String chunkB64; final int sentenceIdx; ... }
class EndQaEvent        extends QaEvent { const EndQaEvent(); }
class ErrorQaEvent      extends QaEvent { final String code; final String message; ... }

// BackendClient 新增
abstract class BackendClient {
  // ... 現有方法 ...
  Stream<QaEvent> qa({
    required Uint8List audioBytes,
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar,
  });
}
```

**RealBackendClient.qa() 實作：**
- `multipart/form-data` POST：`audio` 欄位（bytes）+ `context` 欄位（JSON string）
- SSE 解析沿用現有 `SseParser`
- `transcript` event → `TranscriptQaEvent`；其餘與 narration 共用解析邏輯

### 4.4 Providers 更新

```dart
// shared/providers.dart 新增
final micRecorderProvider = Provider<MicRecorderService>((ref) => RealMicRecorderService());
final qaAudioPlayerProvider = Provider<AudioPlayerService>((ref) => RealAudioPlayerService());
```

### 4.5 QaNotifier

```dart
enum QaStatus { idle, recording, processing, answering, error }

class QaState {
  final QaStatus status;
  final String transcript;    // "你說：這個館為什麼..."
  final String responseText;  // 累積 Q&A 回覆字幕
  final String? errorMessage;
}

class QaNotifier extends StateNotifier<QaState> {
  // 依賴注入
  final BackendClient _client;
  final AudioPlayerService _narrationAudio;  // 旁白 AudioPlayer（duck/unduck 用）
  final AudioPlayerService _qaAudio;         // Q&A 專用 AudioPlayer
  final MicRecorderService _mic;

  Future<void> startRecording() async { ... }
  // 1. _narrationAudio.duck()
  // 2. _mic.startRecording()
  // 3. state = recording

  Future<void> stopAndSend({
    required String persona,
    required String lang,
    String? currentPoiId,
    String narrationSoFar,
  }) async { ... }
  // 1. 計算錄音時長（_recordingStartedAt 在 startRecording() 記錄）
  // 2. guard: 時長 < 500ms → cancelRecording()，直接 return
  // 3. audioBytes = await _mic.stopAndGetBytes()
  // 4. state = processing
  // 5. stream = _client.qa(...)
  // 6. handle events → state transitions

  Future<void> cancelRecording() async { ... }
  // 1. _mic.cancelRecording()
  // 2. _narrationAudio.unduck()
  // 3. state = idle
}

final qaProvider = StateNotifierProvider<QaNotifier, QaState>((ref) {
  return QaNotifier(
    client:         ref.watch(backendClientProvider),
    narrationAudio: ref.watch(audioPlayerServiceProvider),
    qaAudio:        ref.watch(qaAudioPlayerProvider),
    mic:            ref.watch(micRecorderProvider),
  );
});
```

**QaNotifier._handle() 事件處理：**

| Event | 行為 |
|---|---|
| `TranscriptQaEvent` | state = answering；transcript = "你說：${event.text}" |
| `TextQaEvent` | responseText += chunk |
| `AudioQaEvent` | `_qaAudio.enqueueBytes(base64.decode(chunkB64))` |
| `EndQaEvent` | `_narrationAudio.unduck()`；state = idle；clear text |
| `ErrorQaEvent` | `_narrationAudio.unduck()`；state = error |

### 4.6 PushToTalkButton Widget

```dart
// lib/features/qa/widgets/push_to_talk_button.dart

class PushToTalkButton extends ConsumerWidget {
  // 僅在 session active 時顯示（ref.watch(sessionProvider).isActive）
  // GestureDetector:
  //   onLongPressStart → qaNotifier.startRecording()
  //   onLongPressEnd   → qaNotifier.stopAndSend(...)
  //   onLongPressCancel → qaNotifier.cancelRecording()
}
```

**視覺狀態：**
| QaStatus | 按鈕外觀 |
|---|---|
| `idle` | 白色麥克風圖示（🎤） |
| `recording` | 紅色 + 脈衝動畫（AnimatedContainer） |
| `processing` | CircularProgressIndicator |
| `answering` | 藍色喇叭圖示（▶） |
| `error` | 橘色警告圖示，點擊重置 |

**MapScreen 整合：** PushToTalkButton 固定在地圖底部中央（SafeArea 內，疊在 NarrationSheet 上方）

**stopAndSend 的 context 參數來源（PushToTalkButton 內讀取）：**
```dart
final narrationState = ref.read(narrationProvider);
final sessionState   = ref.read(sessionProvider);
ref.read(qaProvider.notifier).stopAndSend(
  persona:        sessionState.persona,
  lang:           sessionState.lang,
  currentPoiId:   narrationState.currentPoi?.id,
  narrationSoFar: narrationState.subtitle,
);
```

### 4.7 NarrationSheet 擴充

當 `qaProvider.state.status != idle` 時，NarrationSheet 頂部顯示 Q&A 字幕區塊：

```
┌─────────────────────────────────┐
│ 🎤 你說：這個館為什麼這麼重要？   │  ← transcript
│ 啊，這問得好...                 │  ← responseText（累積）
├─────────────────────────────────┤
│ [現有旁白內容]                   │
└─────────────────────────────────┘
```

---

## 5. 檔案結構（Plan D 新增）

```
backend/src/tour_guide/
├── api/
│   └── qa.py                         ← POST /qa endpoint（新增）
├── providers/
│   └── stt.py                        ← SttProvider abstract + GeminiSttProvider（新增）
├── services/
│   └── qa_service.py                 ← QAService（新增）
└── prompts/
    └── builder.py                    ← 新增 build_qa() method

flutter_app/lib/
└── features/
    └── qa/                           ← 新 feature 目錄（新增）
        ├── providers/
        │   └── qa_provider.dart      ← QaNotifier + qaProvider
        └── widgets/
            └── push_to_talk_button.dart

flutter_app/lib/shared/
├── audio/
│   └── audio_player_service.dart     ← 新增 duck/unduck
├── backend/
│   ├── backend_client.dart           ← 新增 qa() method
│   └── models/
│       └── qa_event.dart             ← 新增 QaEvent sealed class
├── mic/
│   └── mic_recorder_service.dart     ← 新增（MicRecorderService）
└── providers.dart                    ← 新增 micRecorderProvider + qaAudioPlayerProvider
```

---

## 6. 錯誤處理

| 情境 | 行為 |
|---|---|
| 按住 < 0.5s 立刻放開 | 靜默取消（cancelRecording），不送出請求 |
| STT 轉錄失敗 | ErrorQaEvent → UI 顯示「聽不清楚，請再試一次」；unduck 旁白 |
| /qa 5xx / timeout | BackendClient 重試 1 次；失敗 → error state + unduck |
| Q&A 播放中再按 PTT | cancel stream + `_qaAudio.skip()` + unduck → 重新 startRecording |
| 無旁白時提問（poi_id=null） | 後端 prompt 切換為通用問答；Flutter 邏輯不變 |
| Session 結束時 Q&A 仍進行中 | `MapScreen` 在 `sessionProvider.isActive` 變 false 時呼叫 `ref.read(qaProvider.notifier).cancelRecording()` |

---

## 7. 測試策略

### Backend
| 測試 | 說明 |
|---|---|
| `QAService` unit | `FakeSttProvider` + `FakeLlmProvider` + `FakeTtsProvider`；驗證 TranscriptEvent 先到、audio/text 交錯、EndEvent 最後 |
| `PromptBuilder.build_qa()` unit | poi_id=有值 vs null 兩個分支 |
| `POST /qa` integration | `TestClient` + multipart 上傳；驗證 SSE 事件順序 |

### Flutter
| 測試 | 說明 |
|---|---|
| `QaNotifier` unit | `FakeMicRecorderService` + `FakeBackendClient`；完整走 idle→recording→processing→answering→idle |
| `AudioPlayerService.duck/unduck` unit | `FakeAudioPlayerService` 驗證 isDucked 狀態 |
| `PushToTalkButton` widget | 長按 → startRecording called；放開 → stopAndSend called |

---

## 8. 依賴套件

**Flutter（新增）：**
```yaml
record: ^5.0.0    # 麥克風錄音
```

**Backend（無新增）：** Gemini STT 走現有 `google-genai` SDK

---

## 9. Plan D 範圍外（明確不做）

- 語音活動偵測（VAD）自動停止錄音 → Plan D 用 push-to-talk 明確邊界
- 問答歷史記錄（LocalDB）→ Plan F
- Q&A 旁白字幕時間對齊 → v1 無此需求
- 背景錄音 → 不需要，push-to-talk 只在前景

---

## 文件結束
