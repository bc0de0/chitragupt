"""SSE stream reader for E2E tests.

Collects 'token' and 'complete' events from a Server-Sent Events response.
Used in E2E tests to assert first-token latency, token count, and final payload.

Usage:
    reader = SSEReader(url, payload)
    events = await reader.collect(timeout_s=30)
    token_events = [e for e in events if e.type == "token"]
    complete_event = next((e for e in events if e.type == "complete"), None)
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SSEEvent:
    type: str
    data: dict = field(default_factory=dict)
    received_at: float = field(default_factory=time.monotonic)


class SSEReader:
    """Reads SSE events from a streaming HTTP response."""

    def __init__(self, base_url: str, endpoint: str = "/turn") -> None:
        self.base_url = base_url.rstrip("/")
        self.endpoint = endpoint

    async def collect(
        self,
        payload: dict,
        timeout_s: float = 30.0,
    ) -> list[SSEEvent]:
        """
        POST to the endpoint, stream SSE response, and return all events.

        Requires: httpx with HTTP/1.1 streaming support.
        Install: pip install httpx

        This is a test helper — it is NOT production code.
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx required for SSE E2E tests: pip install httpx")

        events: list[SSEEvent] = []
        url = f"{self.base_url}{self.endpoint}"

        async with httpx.AsyncClient(timeout=timeout_s) as client:
            async with client.stream("POST", url, json=payload) as response:
                response.raise_for_status()
                buffer = ""
                async for line in response.aiter_lines():
                    if line.startswith("event: "):
                        event_type = line[len("event: "):].strip()
                    elif line.startswith("data: "):
                        raw = line[len("data: "):].strip()
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            data = {"raw": raw}
                        events.append(SSEEvent(type=event_type, data=data))
                        event_type = ""
                    elif not line:
                        pass  # blank line separates events

        return events

    def first_token_latency(self, events: list[SSEEvent]) -> float | None:
        """Return time from first event received to first token event (seconds)."""
        if not events:
            return None
        first = events[0].received_at
        for event in events:
            if event.type == "token":
                return event.received_at - first
        return None
