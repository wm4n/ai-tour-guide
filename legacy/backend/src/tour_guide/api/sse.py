"""Server-Sent Events (SSE) encoding utilities."""

import json


def encode_event(event_type: str, data: dict) -> str:
    """Encode an event as SSE format.

    Args:
        event_type: The type of the event (e.g., "text", "meta").
        data: The event data as a dictionary.

    Returns:
        The event encoded in SSE format with exactly 2 trailing newlines.
    """
    return f"event: {event_type}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
