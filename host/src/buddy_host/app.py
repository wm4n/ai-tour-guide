import hmac
from collections.abc import Callable
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from buddy_host import __version__
from buddy_host.config import HostConfig
from buddy_host.narration.traveler import Companions, TravelerContext, TravelMode
from buddy_host.places.models import Location
from buddy_host.tour.session import PreparerLike, TourFix, TourNotActiveError, TourSession
from buddy_host.tour.usage_report import finish_tour


def _require_token(config: HostConfig) -> Callable[..., None]:
    def dependency(x_buddy_token: str | None = Header(default=None)) -> None:
        if config.token is None:
            return
        if x_buddy_token is None or not hmac.compare_digest(x_buddy_token, config.token):
            raise HTTPException(status_code=401, detail="invalid token")

    return dependency


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


def create_app(
    config: HostConfig,
    preparer: PreparerLike | None = None,
    *,
    usage_log_path: Path | None = None,
    reports_dir: Path | None = None,
) -> FastAPI:
    app = FastAPI(title="Buddy Host", version=__version__)
    authed = Depends(_require_token(config))
    session = TourSession(preparer) if preparer is not None else None

    def tour() -> TourSession:
        if session is None:
            raise HTTPException(status_code=503, detail="介紹準備尚未啟用")
        return session

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/status", dependencies=[authed])
    def status() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    @app.post("/v1/tour/start", dependencies=[authed])
    async def tour_start(body: FixBody) -> dict[str, str]:
        tour().start(body.to_fix())
        return {"status": "started"}

    @app.post("/v1/tour/location", dependencies=[authed])
    async def tour_location(body: FixBody) -> dict[str, str]:
        try:
            tour().report(body.to_fix())
        except TourNotActiveError:
            raise HTTPException(status_code=409, detail="還沒有出發") from None
        return {"status": "ok"}

    @app.post("/v1/tour/end", dependencies=[authed])
    async def tour_end() -> dict:
        recap = tour().end()
        if recap is None:
            return {"status": "ended", "summary": None}
        return {"status": "ended", "summary": finish_tour(recap, usage_log_path, reports_dir)}

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

    return app
