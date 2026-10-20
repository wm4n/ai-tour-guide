import asyncio
import hmac
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, StringConstraints

from buddy_host import __version__
from buddy_host.config import HostConfig
from buddy_host.llm.quota import QuotaGate
from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode
from buddy_host.places.models import Location
from buddy_host.qa.service import QaService
from buddy_host.tour.journey import JourneyMemory
from buddy_host.tour.session import PreparerLike, TourFix, TourNotActiveError, TourSession
from buddy_host.tour.usage_report import finish_tour


def _require_token(config: HostConfig) -> Callable[..., None]:
    def dependency(x_buddy_token: str | None = Header(default=None)) -> None:
        if config.token is None:
            return
        if x_buddy_token is None or not hmac.compare_digest(x_buddy_token, config.token):
            raise HTTPException(status_code=401, detail="invalid token")

    return dependency


class PlayedBody(BaseModel):
    id: str


class FixBody(BaseModel):
    """App 的一次回報：位置、行進方向，加上當下的旅人狀態（設計文件第 7 節步驟 1）。"""

    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    heading_deg: float | None = Field(default=None, ge=0, le=360)
    mode: TravelMode | None = None
    companions: Companions | None = None
    with_children: bool = False
    local_time: datetime | None = None  # 帶時區偏移的 ISO 字串

    def to_fix(self) -> TourFix:
        heading = None if self.heading_deg is None else self.heading_deg % 360
        return TourFix(
            Location(self.lat, self.lon, heading),
            TravelerContext(self.mode, self.companions, self.with_children, self.local_time),
        )


class AskBody(FixBody):
    """一個問題，連同提問當下的位置與旅人狀態。`more`＝「再多說一點」：接著剛播完的那段講。"""

    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
    more: bool = False


AnswererFactory = Callable[[QuotaGate, JourneyMemory], QaService]


def create_app(
    config: HostConfig,
    preparer: PreparerLike | None = None,
    *,
    usage_log_path: Path | None = None,
    reports_dir: Path | None = None,
    journey_path: Path | None = None,
    answerer_factory: AnswererFactory | None = None,
) -> FastAPI:
    """`answerer_factory` 拿到與旅程共用的額度閘門和旅程記憶，回傳問答服務；沒給就不開問答。"""
    app = FastAPI(title="Buddy Host", version=__version__)
    authed = Depends(_require_token(config))
    journey = JourneyMemory(journey_path)
    quota = QuotaGate()  # 旅程準備與問答共用：任一邊撞到額度，兩邊一起停
    session = TourSession(preparer, journey=journey, quota=quota) if preparer is not None else None
    answerer = answerer_factory(quota, journey) if answerer_factory is not None else None

    def tour() -> TourSession:
        if session is None:
            raise HTTPException(status_code=503, detail="介紹準備尚未啟用")
        return session

    def qa() -> QaService:
        if answerer is None:
            raise HTTPException(status_code=503, detail="問答尚未啟用")
        return answerer

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/status", dependencies=[authed])
    def status() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/tour/start", dependencies=[authed])
    async def tour_start(body: FixBody) -> dict:
        outcome = tour().start(body.to_fix())
        if outcome.abandoned is not None:  # 上一趟沒按結束就被丟下：替它收尾
            # 報告要讀整份 usage.jsonl（只會越來越大），不在事件迴圈上做
            await asyncio.to_thread(finish_tour, outcome.abandoned, usage_log_path, reports_dir)
        return {"status": "started", "resumed": outcome.resumed}

    @app.post("/v1/tour/location", dependencies=[authed])
    async def tour_location(body: FixBody) -> dict[str, str]:
        try:
            tour().report(body.to_fix())
        except TourNotActiveError:
            raise HTTPException(status_code=409, detail="還沒有出發") from None
        return {"status": "ok"}

    @app.post("/v1/tour/played", dependencies=[authed])
    async def tour_played(body: PlayedBody) -> dict[str, str]:
        tour().mark_played(body.id)  # 不認得的（重啟、重新出發之前的）直接忽略，App 才不會一直重送
        return {"status": "ok"}

    @app.post("/v1/tour/end", dependencies=[authed])
    async def tour_end() -> dict:
        recap = tour().end()
        if recap is None:
            return {"status": "ended", "summary": None}
        summary = await asyncio.to_thread(finish_tour, recap, usage_log_path, reports_dir)
        return {"status": "ended", "summary": summary}

    @app.get("/v1/tour/narrations", dependencies=[authed])
    async def tour_narrations(after: int = 0) -> dict:
        current = tour()
        return {
            "active": current.active,
            "preparing": current.preparing,
            "stopped_reason": current.stopped_reason,
            "narrations": [asdict(event) for event in current.narrations_after(after)],
        }

    @app.get("/v1/tour/audio", dependencies=[authed])
    async def tour_audio(id: str) -> FileResponse:
        path = tour().audio_path(id)
        if path is None or not path.exists():
            raise HTTPException(status_code=404, detail="找不到這段介紹")
        return FileResponse(path, media_type="audio/wav")

    @app.post("/v1/qa/ask", dependencies=[authed])
    async def qa_ask(body: AskBody) -> dict[str, str]:
        return {"id": qa().ask(body.question, body.to_fix(), more=body.more)}

    @app.get("/v1/qa/answer", dependencies=[authed])
    async def qa_answer(id: str) -> dict:
        answer = qa().answer(id)
        if answer is None:
            raise HTTPException(status_code=404, detail="找不到這個問題的答案")
        return asdict(answer)

    return app
