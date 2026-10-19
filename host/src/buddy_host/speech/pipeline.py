"""文字進、驗收過的語音出：前處理 → 合成 → Whisper 轉寫比對 → 換 seed → 拆句 → 跳過。

合成與轉寫都是注入的介面，管線本身不依賴 torch／whisper，可以用假引擎測試。
"""

import re
import time
import wave
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Protocol

import numpy as np

from buddy_host.speech.cer import cer as compute_cer
from buddy_host.speech.cer import normalize
from buddy_host.speech.preroll import WordTiming, analyze_preroll
from buddy_host.speech.text_prep import chunk_sentences, prepare_sentences, split_sentences

_PIECE_RE = re.compile(r"[^，、；：]+[，、；：]?")


class Synthesizer(Protocol):
    sample_rate: int

    def synthesize(self, text: str, seed: int) -> np.ndarray: ...


class Recognizer(Protocol):
    def transcribe(self, audio: np.ndarray, sample_rate: int) -> str: ...


@dataclass(frozen=True)
class PipelineConfig:
    seeds: tuple[int, ...] = (1234, 7, 42, 2026)
    cer_threshold: float = 0.20
    split_on_failure: bool = True
    gap_seconds: float = 0.3
    chunk_chars: int = 90
    # 短句只要錯一個字就聽得出來（真實案例：「額度」被念成「眾珠」仍過 0.2 門檻）
    short_text_chars: int = 20
    short_cer_threshold: float = 0.05


@dataclass
class Attempt:
    seed: int
    cer: float
    hypothesis: str
    synth_seconds: float
    check_seconds: float
    audio_seconds: float
    trimmed_seconds: float = 0.0
    rejected: str | None = None  # 句首檢查不過的原因；有值就不採用，即使 CER 很低


Status = Literal["ok", "split", "skipped"]


@dataclass
class ChunkResult:
    text: str
    status: Status
    attempts: list[Attempt] = field(default_factory=list)
    pieces: list["ChunkResult"] = field(default_factory=list)
    audio: np.ndarray | None = field(default=None, repr=False)


@dataclass
class SpeechResult:
    audio: np.ndarray
    sample_rate: int
    chunks: list[ChunkResult]
    wall_seconds: float

    @property
    def audio_seconds(self) -> float:
        return len(self.audio) / self.sample_rate

    def to_log(self) -> dict:
        def chunk(s: ChunkResult) -> dict:
            return {
                "text": s.text,
                "status": s.status,
                "attempts": [
                    {
                        "seed": a.seed,
                        "cer": round(a.cer, 3),
                        "hypothesis": a.hypothesis,
                        "synth_seconds": round(a.synth_seconds, 2),
                        "check_seconds": round(a.check_seconds, 2),
                        "audio_seconds": round(a.audio_seconds, 2),
                        "trimmed_seconds": round(a.trimmed_seconds, 2),
                        "rejected": a.rejected,
                    }
                    for a in s.attempts
                ],
                "pieces": [chunk(p) for p in s.pieces],
            }

        return {
            "audio_seconds": round(self.audio_seconds, 2),
            "wall_seconds": round(self.wall_seconds, 2),
            "rtf": round(self.wall_seconds / self.audio_seconds, 2) if self.audio_seconds else None,
            "chunks": [chunk(c) for c in self.chunks],
        }


class SpeechPipeline:
    def __init__(
        self,
        synthesizer: Synthesizer,
        recognizer: Recognizer,
        config: PipelineConfig | None = None,
        clock: Callable[[], float] = time.perf_counter,
        progress: Callable[[int, int, "ChunkResult"], None] | None = None,
    ):
        self._synth = synthesizer
        self._asr = recognizer
        self._config = config or PipelineConfig()
        self._clock = clock
        self._progress = progress

    def run(self, text: str) -> SpeechResult:
        started = self._clock()
        texts = chunk_sentences(prepare_sentences(text), self._config.chunk_chars)
        chunks: list[ChunkResult] = []
        for index, chunk_text in enumerate(texts, start=1):
            chunk = self._speak(chunk_text)
            chunks.append(chunk)
            if self._progress:
                self._progress(index, len(texts), chunk)
        rate = self._synth.sample_rate
        audio = self._join([c.audio for c in chunks if c.audio is not None])
        return SpeechResult(audio, rate, chunks, self._clock() - started)

    def _gap(self) -> np.ndarray:
        return np.zeros(int(self._synth.sample_rate * self._config.gap_seconds), dtype=np.float32)

    def _join(self, parts: list[np.ndarray]) -> np.ndarray:
        if not parts:
            return np.zeros(0, dtype=np.float32)
        out = [parts[0]]
        for part in parts[1:]:
            out += [self._gap(), part]
        return np.concatenate(out)

    def _speak(self, text: str) -> ChunkResult:
        """換 seed 重試 → 全失敗就往下拆（段→句→分句）→ 還是不行就跳過。"""
        attempts: list[Attempt] = []
        for seed in self._config.seeds:
            attempt, audio = self.attempt(text, seed)
            attempts.append(attempt)
            if attempt.rejected is None and attempt.cer <= self.threshold_for(text):
                return ChunkResult(text, "ok", attempts, audio=audio)

        split = _split_once(text) if self._config.split_on_failure else None
        if split is None:
            return ChunkResult(text, "skipped", attempts)

        kind, pieces = split
        results = [self._speak(piece) for piece in pieces]
        good = [r.audio for r in results if r.audio is not None]
        # 拆成句子：只丟掉失敗的那句；拆成分句：少一個分句句子就不完整，整句跳過
        if not good or (kind == "clause" and len(good) < len(results)):
            return ChunkResult(text, "skipped", attempts, results)
        audio = self._join(good) if kind == "sentence" else np.concatenate(good)
        return ChunkResult(text, "split", attempts, results, audio)

    def threshold_for(self, text: str) -> float:
        if len(normalize(text)) <= self._config.short_text_chars:
            return min(self._config.cer_threshold, self._config.short_cer_threshold)
        return self._config.cer_threshold

    def attempt(self, text: str, seed: int) -> tuple[Attempt, np.ndarray]:
        t0 = self._clock()
        audio = np.asarray(self._synth.synthesize(text, seed), dtype=np.float32)
        return self.review(text, audio, seed=seed, synth_seconds=self._clock() - t0)

    def review(
        self, text: str, audio: np.ndarray, *, seed: int = 0, synth_seconds: float = 0.0
    ) -> tuple[Attempt, np.ndarray]:
        """轉寫、檢查句首、必要時裁掉多餘的開頭並再驗一次。"""
        rate = self._synth.sample_rate
        t0 = self._clock()
        hypothesis, words = self._transcribe(audio)
        rejected: str | None = None
        trimmed = 0.0
        if words is not None:
            verdict = analyze_preroll(text, words)
            if not verdict.ok:
                rejected = verdict.reason
            elif verdict.trim_to:
                trimmed_audio = audio[int(round(verdict.trim_to * rate)) :]
                hypothesis, words = self._transcribe(trimmed_audio)
                again = analyze_preroll(text, words or [])
                if again.ok and not again.trim_to:
                    audio, trimmed = trimmed_audio, verdict.trim_to
                else:
                    rejected = f"{verdict.reason}; still bad after trim: {again.reason}"
        attempt = Attempt(
            seed=seed,
            cer=compute_cer(text, hypothesis),
            hypothesis=hypothesis,
            synth_seconds=synth_seconds,
            check_seconds=self._clock() - t0,
            audio_seconds=len(audio) / rate,
            trimmed_seconds=trimmed,
            rejected=rejected,
        )
        return attempt, audio

    def _transcribe(self, audio: np.ndarray) -> tuple[str, list[WordTiming] | None]:
        rate = self._synth.sample_rate
        with_words = getattr(self._asr, "transcribe_words", None)
        if with_words is None:
            return self._asr.transcribe(audio, rate), None
        text, words = with_words(audio, rate)
        return text, words


def _split_once(text: str) -> tuple[Literal["sentence", "clause"], list[str]] | None:
    sentences = split_sentences(text)
    if len(sentences) > 1:
        return "sentence", sentences
    clauses = [p.strip() for p in _PIECE_RE.findall(text) if p.strip()]
    if len(clauses) > 1:
        return "clause", clauses
    return None


def write_outputs(result: SpeechResult, out_dir: Path, name: str) -> tuple[Path, Path]:
    import json

    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / f"{name}.wav"
    pcm = (np.clip(result.audio, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(wav_path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(result.sample_rate)
        wav.writeframes(pcm.tobytes())
    log_path = out_dir / f"{name}.log.json"
    log_path.write_text(json.dumps(result.to_log(), ensure_ascii=False, indent=1), encoding="utf-8")
    return wav_path, log_path
