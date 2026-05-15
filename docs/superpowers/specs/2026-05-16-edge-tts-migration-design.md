# Edge TTS Migration Design

**Date:** 2026-05-16
**Status:** Approved

## Problem

Gemini TTS (`gemini-2.5-flash-preview-tts`) free quota is insufficient even for development testing. The app needs a free, high-quality TTS engine with Traditional Chinese support for both development and production.

## Decision

Replace `GeminiTtsAdapter` with `EdgeTtsAdapter` using Microsoft's Edge TTS engine via the `edge-tts` Python package.

**Why edge-tts:**
- Free, no quota limits
- Neural TTS quality (comparable to Gemini TTS)
- Native zh-TW support with dedicated Taiwan Mandarin voices
- Async streaming API — fits the existing `TtsProvider` Protocol directly
- No API key required — reduces secrets management overhead
- Bandwidth is not a concern: 4G downloads 48kbps audio at 200x playback speed; current sentence-by-sentence streaming (~40KB/sentence) already handles this

## Architecture

No structural changes. The `TtsProvider` Protocol interface is unchanged. Only the concrete adapter and its wiring are swapped.

```
NarrationService → TtsProvider (Protocol) → EdgeTtsAdapter → Microsoft Edge TTS
```

## Changes

### 1. Backend: Add `edge-tts` dependency

`backend/pyproject.toml`:
```
"edge-tts>=7.0.0"
```

Remove `google-genai` only if it is unused by other providers (STT also uses it — keep it).

### 2. Backend: Add `EdgeTtsAdapter`

`backend/src/tour_guide/providers/tts.py` — add alongside existing `GeminiTtsAdapter`:

```python
import edge_tts

class EdgeTtsAdapter:
    async def synthesize(
        self,
        text: str,
        voice_id: str,
        opts: TtsOpts,
    ) -> AsyncIterator[bytes]:
        communicate = edge_tts.Communicate(text, voice_id)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
```

- No constructor arguments (no API key needed)
- Outputs MP3 chunks directly; no WAV conversion required
- Satisfies `TtsProvider` Protocol unchanged

### 3. Backend: Wire `EdgeTtsAdapter` in `main.py`

```python
# Before
tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)

# After
tts_provider = EdgeTtsAdapter()
```

### 4. Persona YAMLs: Update voice IDs

All 5 personas updated from Gemini voice names to edge-tts voice IDs:

| Persona | zh-TW | en |
|---------|-------|----|
| history_uncle | `zh-TW-YunJheNeural` | `en-US-GuyNeural` |
| story_brother | `zh-TW-YunJheNeural` | `en-US-TonyNeural` |
| kid_sister | `zh-TW-HsiaoYuNeural` | `en-US-JennyNeural` |
| gossip_auntie | `zh-TW-HsiaoChenNeural` | `en-US-AriaNeural` |
| foodie | `zh-TW-HsiaoChenNeural` | `en-US-AriaNeural` |

**Note:** edge-tts only provides 3 zh-TW voices (1 male, 2 female), so story_brother shares `zh-TW-YunJheNeural` with history_uncle, and foodie shares `zh-TW-HsiaoChenNeural` with gossip_auntie.

### 5. Flutter: Update audio file extension

`flutter_app/lib/shared/audio/audio_player_service.dart:37`

```dart
// Before
final file = File('${_tempDir.path}/narration_${_chunkIndex++}.wav');

// After
final file = File('${_tempDir.path}/narration_${_chunkIndex++}.mp3');
```

`just_audio` detects format from file content (not extension) so playback is unaffected, but the extension should match the actual MP3 content.

## Trade-offs

| | edge-tts | Gemini TTS |
|-|---------|-----------|
| Cost | Free, unlimited | Free tier quota (insufficient) |
| zh-TW voice count | 3 | 30+ |
| Voice quality | Neural, high | Neural, high |
| Requires internet | Yes | Yes |
| API stability | Unofficial (Microsoft Edge) | Official |
| API key | None | Required |

**Stability risk:** edge-tts uses a reverse-engineered connection to Microsoft's Edge speech service. Microsoft could block it without notice. This is acceptable for the current stage; if stability becomes a concern, Azure Cognitive Services TTS (official, 500k chars/month free) uses the same Neural voices and is a direct upgrade path.

## Out of Scope

- On-device TTS fallback (deferred — can be added later as offline mode)
- STT provider (unchanged, still uses Gemini)
- Narration caching logic (unchanged)
- Flutter audio playback logic (unchanged except file extension)
