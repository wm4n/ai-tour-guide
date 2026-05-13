"""FastAPI application factory with full dependency injection wiring."""

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI

from tour_guide.api import health, narration, poi, qa
from tour_guide.cache.narration_cache import NarrationCache
from tour_guide.cache.poi_cache import POICache
from tour_guide.clients.google_places import FakeGooglePlacesClient, RealGooglePlacesClient
from tour_guide.clients.overpass import OverpassClient
from tour_guide.clients.wikipedia import WikipediaClient
from tour_guide.config import AppConfig
from tour_guide.prompts.loader import PersonaLoader
from tour_guide.providers.llm import LiteLLMAdapter
from tour_guide.providers.stt import GeminiSttAdapter
from tour_guide.providers.tts import GeminiTtsAdapter
from tour_guide.services.narration_service import NarrationService
from tour_guide.services.poi_service import POIService
from tour_guide.services.qa_service import QAService


def create_app(config: AppConfig) -> FastAPI:
    http_client = httpx.AsyncClient()

    overpass_client = OverpassClient(client=http_client)
    wikipedia_client = WikipediaClient(client=http_client)
    poi_cache = POICache(config.poi_cache_dir)
    narration_cache = NarrationCache(config.narration_cache_dir)

    llm_provider = LiteLLMAdapter(api_key=config.gemini_api_key)
    tts_provider = GeminiTtsAdapter(api_key=config.gemini_api_key)
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
    )
    narration_service = NarrationService(
        llm=llm_provider,
        tts=tts_provider,
        cache=narration_cache,
    )
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

    app.dependency_overrides[poi.get_poi_service] = lambda: poi_service
    app.dependency_overrides[narration.get_narration_service] = lambda: narration_service
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
