import hmac
from collections.abc import Callable

from fastapi import Depends, FastAPI, Header, HTTPException

from buddy_host import __version__
from buddy_host.config import HostConfig


def _require_token(config: HostConfig) -> Callable[..., None]:
    def dependency(x_buddy_token: str | None = Header(default=None)) -> None:
        if config.token is None:
            return
        if x_buddy_token is None or not hmac.compare_digest(x_buddy_token, config.token):
            raise HTTPException(status_code=401, detail="invalid token")

    return dependency


def create_app(config: HostConfig) -> FastAPI:
    app = FastAPI(title="Buddy Host", version=__version__)
    authed = Depends(_require_token(config))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/status", dependencies=[authed])
    def status() -> dict[str, str]:
        return {"status": "ok", "version": __version__}

    return app
