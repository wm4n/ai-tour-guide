"""FastAPI application factory with full dependency injection wiring."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from tour_guide.api import health, narration, poi, qa
from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.google_places import FakeGooglePlacesClient, RealGooglePlacesClient
from tour_guide.clients.nominatim import NominatimClient
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.config import AppConfig
from tour_guide.logging_config import setup_logging
from tour_guide.prompts.loader import PersonaLoader
from tour_guide.providers.llm import LiteLLMAdapter
from tour_guide.providers.stt import GeminiSttAdapter
from tour_guide.providers.tts import EdgeTtsAdapter
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_selector import POISelectorService
from tour_guide.services.poi_service import POIService
from tour_guide.services.qa_service import QAService
from tour_guide.services.wikipedia_resolver import WikipediaResolver


def create_app(config: AppConfig) -> FastAPI:
    setup_logging(level=config.log_level, fmt=config.log_format)
    http_client = httpx.AsyncClient(headers={"User-Agent": "ai-tour-guide/1.0 (https://github.com/ai-tour-guide)"})

    overpass_client = OverpassClient(client=http_client)
    wikipedia_client = WikipediaClient(client=http_client)
    nominatim_client = NominatimClient(client=http_client)
    wikipedia_resolver = WikipediaResolver(wikipedia=wikipedia_client, nominatim=nominatim_client)
    poi_cache = POICache(config.poi_cache_dir)
    narration_cache = NarrationCache(config.narration_cache_dir)

    llm_provider = LiteLLMAdapter(api_key=config.gemini_api_key)
    tts_provider = EdgeTtsAdapter()
    stt_provider = GeminiSttAdapter(api_key=config.gemini_api_key)

    if config.google_places_api_key:
        google_places_client = RealGooglePlacesClient(api_key=config.google_places_api_key)
    else:
        google_places_client = FakeGooglePlacesClient(scripted_places=[])

    poi_service = POIService(
        overpass=overpass_client,
        wikipedia=wikipedia_client,
        cache=poi_cache,
        google_places=google_places_client,
        resolver=wikipedia_resolver,
    )
    narration_service = NarrationService(
        llm=llm_provider,
        tts=tts_provider,
        cache=narration_cache,
    )
    poi_selector_service = POISelectorService(llm=llm_provider)
    qa_service = QAService(
        stt=stt_provider,
        llm=llm_provider,
        tts=tts_provider,
    )
    persona_registry = PersonaLoader.load_all()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await http_client.aclose()

    app = FastAPI(title="AI Tour Guide", lifespan=lifespan)

    configured_api_key = config.api_key

    class ApiKeyMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            if not configured_api_key:
                return await call_next(request)
            provided_key = request.headers.get("X-Api-Key", "")
            if provided_key != configured_api_key:
                return JSONResponse(
                    status_code=401,
                    content={"detail": "Invalid or missing X-Api-Key"},
                )
            return await call_next(request)

    app.add_middleware(ApiKeyMiddleware)

    app.dependency_overrides[poi.get_poi_service] = lambda: poi_service
    app.dependency_overrides[narration.get_narration_service] = lambda: narration_service
    app.dependency_overrides[narration.get_poi_selector_service] = lambda: poi_selector_service
    app.dependency_overrides[narration.get_persona_registry] = lambda: persona_registry
    app.dependency_overrides[qa.get_qa_service] = lambda: qa_service
    app.dependency_overrides[qa.get_persona_registry] = lambda: persona_registry

    app.include_router(health.router)
    app.include_router(poi.router)
    app.include_router(narration.router)
    app.include_router(qa.router)

    return app


try:
    app = create_app(AppConfig())
except Exception:
    app = None  # type: ignore
