"""Health check API endpoint."""

import time

from fastapi import APIRouter

router = APIRouter()
_start_time = time.time()


@router.get("/health")
async def health():
    """Health check endpoint.

    Returns:
        A JSON response with status and uptime in seconds.
    """
    return {"status": "ok", "uptime_s": int(time.time() - _start_time)}
