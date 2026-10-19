"""為一個位置準備介紹：找景點 → 排序 → 抓摘要 → Claude 寫稿 → 合成驗收 → 存進快取。"""

import asyncio
import hashlib
import json
import logging
import re
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


SNAP_DECIMALS = 3  # 約 110 公尺；相近的位置共用同一份 Overpass／Wikipedia 查詢與快取
SNAP_MARGIN_M = 150.0  # 吸附造成的位移上限（約 80 公尺）再留餘裕


def _fingerprint(persona: str, told_before: tuple[str, ...], traveler_key: str) -> str:
    # 個性檔、「講過什麼」或使用者的狀態變了，舊稿就不能再用（設計文件 6.2：改了下次呼叫就生效）
    payload = json.dumps([persona, list(told_before), traveler_key], ensure_ascii=False)
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
    ):
        self._overpass = overpass
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
        snapped = (round(location.lat, SNAP_DECIMALS), round(location.lon, SNAP_DECIMALS))
        query_radius = self._radius_m + SNAP_MARGIN_M
        merged = await gather_candidates(self._overpass, self._wiki, *snapped, query_radius)
        ranked = rank(
            merged,
            location,
            limit=self._limit,
            radius_m=self._radius_m,
            exclude_ids=exclude_ids,
            recent_themes=recent_themes,
        )

        told = told_before or {}
        persona = load_persona(self._persona_path)
        prints = {
            item.candidate.id: _fingerprint(
                persona, told.get(item.candidate.id, ()), traveler.key() if traveler else ""
            )
            for item in ranked
        }
        # 已有快取的直接用；其餘的稿子同時開寫，合成（只有一個模型）再依序進行
        cached = {
            item.candidate.id: self._load_cached(item.candidate, prints[item.candidate.id])
            for item in ranked
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
            if cached[item.candidate.id] is None
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
                    script, issues = await scripts[item.candidate.id]
                except (ForbiddenModelError, QuotaExceededError):
                    raise  # 政策違規與額度用盡不是單段失敗，要讓呼叫端知道
                except Exception:  # 一段寫稿失敗（逾時、格式…）不要拖垮其他段
                    logger.exception("寫稿失敗：%s", item.candidate.name)
                    continue
                made = (
                    await self._synthesize(item, script, prints[item.candidate.id], issues)
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

    def _paths(self, candidate: Candidate) -> tuple[Path, Path]:
        base = self._out_dir / _safe(candidate.id)
        return base.with_suffix(".wav"), base.with_suffix(".meta.json")

    def _load_cached(self, candidate: Candidate, fingerprint: str) -> PreparedNarration | None:
        wav, meta_path = self._paths(candidate)
        if not (wav.exists() and meta_path.exists()):
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("fingerprint") != fingerprint:
            return None
        return PreparedNarration(
            candidate.id, meta["name"], meta["script"], wav, meta_path,
            meta["audio_seconds"], meta["distance_m"], candidate.lat, candidate.lon,
        )  # fmt: skip

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
        self, item: Ranked, script: str, fingerprint: str, issues: list[Finding]
    ) -> PreparedNarration | None:
        candidate = item.candidate
        speech = await asyncio.to_thread(self._speech.run, script)
        if speech.audio_seconds <= 0:
            return None

        wav, meta_path = self._paths(candidate)
        write_speech(speech, wav.parent, wav.stem)
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
            "audio_seconds": round(speech.audio_seconds, 2),
            "speech": speech.to_log(),
            "prepared_at": datetime.now(UTC).isoformat(),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
        return PreparedNarration(
            candidate.id, candidate.name, script, wav, meta_path,
            meta["audio_seconds"], meta["distance_m"], candidate.lat, candidate.lon,
        )  # fmt: skip
