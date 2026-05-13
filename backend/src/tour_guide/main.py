"""FastAPI application factory with full dependency injection wiring."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from tour_guide.api import health, narration, poi
from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.config import AppConfig
from tour_guide.prompts.loader import PersonaLoader
from tour_guide.providers.llm import LiteLLMAdapter
from tour_guide.providers.tts import GeminiTtsAdapter
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_service import POIService


def create_app(config: AppConfig) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        config: Application configuration with API keys and settings.

    Returns:
        Configured FastAPI application instance.
    """
    http_client = httpx.AsyncClient()

    overpass_client = OverpassClient(client=http_client)
    wikipedia_client = WikipediaClient(client=http_client)
    poi_cache = POICache(config.poi_cache_dir)
    narration_cache = NarrationCache(config.narration_cache_dir)

    llm_provider = LiteLLMAdapter(api_key=config.gemini_api_key)
    tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)

    poi_service = POIService(
        overpass=overpass_client,
        wikipedia=wikipedia_client,
        cache=poi_cache,
    )
    narration_service = NarrationService(
        llm=llm_provider,
        tts=tts_provider,
        cache=narration_cache,
    )
    persona_registry = PersonaLoader.load_all()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await http_client.aclose()

    app = FastAPI(title="AI Tour Guide", lifespan=lifespan)

    # Override dependency functions using FastAPI's dependency_overrides pattern
    app.dependency_overrides[poi.get_poi_service] = lambda: poi_service
    app.dependency_overrides[narration.get_narration_service] = lambda: narration_service
    app.dependency_overrides[narration.get_persona_registry] = lambda: persona_registry

    app.include_router(health.router)
    app.include_router(poi.router)
    app.include_router(narration.router)

    return app


# Module-level app for uvicorn: `uvicorn tour_guide.main:app`
# Requires GEMINI_API_KEY env var. For dev: GEMINI_API_KEY=anything uvicorn tour_guide.main:app
try:
    app = create_app(AppConfig())
except Exception:
    # Allow import without GEMINI_API_KEY set (e.g., during test collection)
    # Tests should call create_app(config) directly with monkeypatched env vars
    app = None  # type: ignore
