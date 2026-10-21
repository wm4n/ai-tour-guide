"""為一個位置準備介紹：找景點 → 排序 → 抓摘要 → Claude 寫稿 → 合成驗收 → 存進快取。"""

import asyncio
import hashlib
import json
import logging
import re
import wave
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from buddy_host.llm.claude_cli import QuotaExceededError
from buddy_host.llm.models import ForbiddenModelError, LlmRequest, LlmResult
from buddy_host.narration.prompt import ScriptContext, build_script_request, load_persona
from buddy_host.narration.traveler import TravelerContext
from buddy_host.narration.wording import DEFAULT_TERMS_FILE, Finding, find_issues, load_terms
from buddy_host.places.gather import gather_candidates
from buddy_host.places.merge import names_match
from buddy_host.places.models import BBox, Candidate, Location
from buddy_host.places.ranking import DEFAULT_RADIUS_M, Ranked, rank
from buddy_host.places.wikipedia import WikiHit, WikiSummary
from buddy_host.speech.pipeline import SpeechResult
from buddy_host.speech.pipeline import write_outputs as write_speech

logger = logging.getLogger(__name__)


class OverpassLike(Protocol):
    async def nearby(self, box: BBox) -> list[Candidate]: ...


class WikipediaLike(Protocol):
    async def geosearch(self, lat: float, lon: float, radius_m: int) -> list[WikiHit]: ...
    async def search(self, query: str) -> str | None: ...
    async def summary(self, title: str) -> WikiSummary | None: ...


class LlmLike(Protocol):
    async def run(self, request: LlmRequest, on_text=None) -> LlmResult: ...


class SpeechLike(Protocol):
    def run(self, text: str) -> SpeechResult: ...


@dataclass(frozen=True)
class PreparedNarration:
    candidate_id: str
    name: str
    script: str
    wav_path: Path
    meta_path: Path
    audio_seconds: float
    distance_m: float
    lat: float
    lon: float


def _safe(candidate_id: str) -> str:
    return re.sub(r"[^\w\-]+", "_", candidate_id)


def wav_seconds(path: Path) -> float:
    with wave.open(str(path)) as wav:
        return round(wav.getnframes() / wav.getframerate(), 2)


# 沒指定聲音時用的聲音鍵（`名稱@語速`，同 `ReferenceVoice.key`）
DEFAULT_VOICE_KEY = "F2@1"

SNAP_DECIMALS = 3  # 約 110 公尺；相近的位置共用同一份 Overpass／Wikipedia 查詢與快取
SNAP_MARGIN_M = 150.0  # 吸附造成的位移上限（約 80 公尺）再留餘裕


def _fingerprint(
    persona: str,
    told_before: tuple[str, ...],
    traveler_key: str,
    recent_topics: tuple[str, ...],
) -> str:
    # 個性檔、「講過什麼」、「這趟剛講過什麼」或使用者的狀態變了，舊稿就不能再用
    # （設計文件 6.2：改了下次呼叫就生效；稿子會寫「剛剛的 A」，不能用在沒去過 A 的另一趟）
    payload = json.dumps(
        [persona, list(told_before), traveler_key, list(recent_topics)], ensure_ascii=False
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _relative_bearing(location: Location, bearing: float) -> float | None:
    if location.heading_deg is None:
        return None
    return (bearing - location.heading_deg + 540) % 360 - 180


class AreaPreparer:
    def __init__(
        self,
        overpass: OverpassLike,
        wiki: WikipediaLike,
        llm: LlmLike,
        speech: SpeechLike,
        *,
        persona_path: Path,
        out_dir: Path,
        radius_m: float = DEFAULT_RADIUS_M,
        limit: int = 2,
        max_rewrites: int = 1,
        terms_path: Path = DEFAULT_TERMS_FILE,
        voice_key: str = DEFAULT_VOICE_KEY,
    ):
        self._overpass = overpass
        # 可在執行中改變（換聲音）：快取的稿子與聲音無關，音檔依聲音鍵分開存放，
        # 換了聲音只重新合成（不必再找 Claude 寫）；每次 `prepare` 開始時取用當下的聲音鍵
        self.voice_key = voice_key
        self._wiki = wiki
        self._llm = llm
        self._speech = speech
        self._persona_path = persona_path
        self._out_dir = out_dir
        self._radius_m = radius_m
        self._limit = limit
        self._max_rewrites = max_rewrites  # 每次重寫都是一次額外的 Claude 呼叫
        self._terms = load_terms(terms_path)

    async def prepare(
        self,
        location: Location,
        *,
        exclude_ids: Collection[str] = (),
        recent_themes: Collection[str] = (),
        recent_topics: tuple[str, ...] = (),
        told_before: Mapping[str, tuple[str, ...]] | None = None,
        traveler: TravelerContext | None = None,
        on_ready: Callable[[PreparedNarration], None] | None = None,
    ) -> list[PreparedNarration]:
        """on_ready：每做好一段就呼叫（合成很慢，呼叫端不必等整批）。"""
        voice_key = self.voice_key  # 這一批從頭到尾歸在同一個聲音底下，中途換聲音不會把音檔放錯地方
        ranked = await self._ranked(
            location, self._limit, exclude_ids=exclude_ids, recent_themes=recent_themes
        )

        told = told_before or {}
        persona = load_persona(self._persona_path)
        prints = {
            item.candidate.id: _fingerprint(
                persona,
                told.get(item.candidate.id, ()),
                traveler.key() if traveler else "",
                tuple(recent_topics),
            )
            for item in ranked
        }
        # 已有快取的直接用；只是聲音換了的拿舊稿重新合成；其餘的稿子同時開寫，
        # 合成（只有一個模型）再依序進行
        cached = {
            item.candidate.id: self._load_cached(
                item.candidate, prints[item.candidate.id], voice_key
            )
            for item in ranked
        }
        reusable = {
            item.candidate.id: self._cached_script(item.candidate, prints[item.candidate.id])
            for item in ranked
            if cached[item.candidate.id] is None
        }
        scripts = {
            item.candidate.id: asyncio.create_task(
                self._write_script(
                    item,
                    location,
                    persona,
                    recent_topics,
                    told.get(item.candidate.id, ()),
                    traveler,
                )
            )
            for item in ranked
            if cached[item.candidate.id] is None and reusable[item.candidate.id] is None
        }
        prepared: list[PreparedNarration] = []
        try:
            for item in ranked:
                hit = cached[item.candidate.id]
                if hit:
                    prepared.append(hit)
                    if on_ready:
                        on_ready(hit)
                    continue
                try:
                    script, issues = reusable[item.candidate.id] or await scripts[item.candidate.id]
                except (ForbiddenModelError, QuotaExceededError):
                    raise  # 政策違規與額度用盡不是單段失敗，要讓呼叫端知道
                except Exception:  # 一段寫稿失敗（逾時、格式…）不要拖垮其他段
                    logger.exception("寫稿失敗：%s", item.candidate.name)
                    continue
                made = (
                    await self._synthesize(
                        item, script, prints[item.candidate.id], issues, voice_key
                    )
                    if script
                    else None
                )
                if made:
                    prepared.append(made)
                    if on_ready:
                        on_ready(made)
        finally:
            for task in scripts.values():
                task.cancel()
        return prepared

    async def nearby(self, location: Location, *, limit: int = 5) -> list[ScriptContext]:
        """附近值得一提的地方與它們的維基摘要，給問答用：只查資料，不寫稿也不合成。

        查詢範圍與 `prepare` 相同，Overpass／維基的快取才共用。已經講過的地方不排除：
        使用者問的就是眼前的東西，不管講過沒有。
        """
        ranked = await self._ranked(location, limit)
        extracts = await asyncio.gather(
            *(self._summary(item.candidate) for item in ranked), return_exceptions=True
        )
        return [
            ScriptContext(
                candidate=item.candidate,
                wiki_extract=None if isinstance(extract, BaseException) else extract,
                distance_m=item.distance_m,
                bearing_relative_deg=_relative_bearing(location, item.bearing_deg),
            )
            for item, extract in zip(ranked, extracts, strict=True)
        ]

    async def _ranked(
        self,
        location: Location,
        limit: int,
        *,
        exclude_ids: Collection[str] = (),
        recent_themes: Collection[str] = (),
    ) -> list[Ranked]:
        snapped = (round(location.lat, SNAP_DECIMALS), round(location.lon, SNAP_DECIMALS))
        query_radius = self._radius_m + SNAP_MARGIN_M
        merged = await gather_candidates(self._overpass, self._wiki, *snapped, query_radius)
        return rank(
            merged,
            location,
            limit=limit,
            radius_m=self._radius_m,
            exclude_ids=exclude_ids,
            recent_themes=recent_themes,
        )

    def _meta_path(self, candidate: Candidate) -> Path:
        return self._out_dir / f"{_safe(candidate.id)}.meta.json"

    def _wav_path(self, candidate: Candidate, voice_key: str) -> Path:
        return self._out_dir / voice_key / f"{_safe(candidate.id)}.wav"

    def _cached_meta(self, candidate: Candidate, fingerprint: str) -> dict | None:
        """稿子還能用的快取（指紋相同）；與聲音無關，音檔是否存在另外判斷。"""
        meta_path = self._meta_path(candidate)
        if not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return meta if meta.get("fingerprint") == fingerprint else None

    def _load_cached(
        self, candidate: Candidate, fingerprint: str, voice_key: str
    ) -> PreparedNarration | None:
        meta = self._cached_meta(candidate, fingerprint)
        wav = self._wav_path(candidate, voice_key)
        if meta is None or not wav.exists():
            return None
        return PreparedNarration(
            candidate.id, meta["name"], meta["script"], wav, self._meta_path(candidate),
            wav_seconds(wav), meta["distance_m"], candidate.lat, candidate.lon,
        )  # fmt: skip

    def _cached_script(
        self, candidate: Candidate, fingerprint: str
    ) -> tuple[str, list[Finding]] | None:
        """這個聲音還沒有音檔但稿子還能用：回傳舊稿（與它的用語問題），拿去重新合成。"""
        meta = self._cached_meta(candidate, fingerprint)
        if meta is None or not meta.get("script"):
            return None
        issues = [Finding(i["term"], i["suggestion"]) for i in meta.get("wording_issues", [])]
        return meta["script"], issues

    async def _summary(self, candidate: Candidate) -> str | None:
        title = candidate.wiki_title
        if title is None:
            found = await self._wiki.search(candidate.name)
            title = found if found and names_match(candidate.name, found) else None
        if title is None:
            return None
        summary = await self._wiki.summary(title)
        return summary.extract if summary and summary.extract else None

    async def _write_script(
        self,
        item: Ranked,
        location: Location,
        persona: str,
        recent_topics: tuple[str, ...],
        told_before: tuple[str, ...],
        traveler: TravelerContext | None,
    ) -> tuple[str, list[Finding]]:
        candidate = item.candidate
        context = ScriptContext(
            candidate=candidate,
            wiki_extract=await self._summary(candidate),
            distance_m=item.distance_m,
            bearing_relative_deg=_relative_bearing(location, item.bearing_deg),
            told_before=told_before,
            recent_topics=recent_topics,
            traveler=traveler,
        )
        script = (await self._llm.run(build_script_request(persona, context))).text.strip()
        issues = find_issues(script, self._terms)
        for _ in range(self._max_rewrites):
            if not script or not issues:
                break
            revised = build_script_request(persona, context, revise=(script, issues))
            script = (await self._llm.run(revised)).text.strip()
            issues = find_issues(script, self._terms)
        if issues:
            logger.warning("%s 的稿子仍有非台灣用語：%s", candidate.name, issues)
        return script, issues

    async def _synthesize(
        self, item: Ranked, script: str, fingerprint: str, issues: list[Finding], voice_key: str
    ) -> PreparedNarration | None:
        candidate = item.candidate
        speech = await asyncio.to_thread(self._speech.run, script)
        if speech.audio_seconds <= 0:
            return None

        wav, meta_path = self._wav_path(candidate, voice_key), self._meta_path(candidate)
        write_speech(speech, wav.parent, wav.stem)  # 音檔與合成紀錄依聲音分開
        meta = {
            "candidate_id": candidate.id,
            "name": candidate.name,
            "lat": candidate.lat,
            "lon": candidate.lon,
            "wiki_title": candidate.wiki_title,
            "distance_m": round(item.distance_m, 1),
            "bearing_deg": round(item.bearing_deg, 1),
            "score": round(item.score, 3),
            "script": script,
            "fingerprint": fingerprint,
            "wording_issues": [{"term": f.term, "suggestion": f.suggestion} for f in issues],
            "prepared_at": datetime.now(UTC).isoformat(),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return PreparedNarration(
            candidate.id, candidate.name, script, wav, meta_path,
            round(speech.audio_seconds, 2), meta["distance_m"], candidate.lat, candidate.lon,
        )  # fmt: skip
