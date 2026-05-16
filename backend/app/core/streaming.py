# app/core/streaming.py
import json
from typing import Any

class SSEFormatter:
    """Formats events for Server-Sent Events streaming."""

    @staticmethod
    def format_event(event_type: str, data: Any) -> str:
        # Inject the type into the JSON payload so the frontend can route it
        if isinstance(data, dict):
            data["type"] = event_type
        
        json_data = json.dumps(data, default=str)
        return f"event: {event_type}\ndata: {json_data}\n\n"

    @staticmethod
    def chunk(delta: str, citations: list = None) -> str:
        return SSEFormatter.format_event("chunk", {
            "delta": delta,
            "citations": citations or []
        })

    @staticmethod
    def retrieval_debug(chunks: list) -> str:
        return SSEFormatter.format_event("retrieval_debug", {"chunks": chunks})

    @staticmethod
    def ui_component(component: str, data: dict) -> str:
        return SSEFormatter.format_event("ui_component", {
            "component": component, "data": data
        })

    @staticmethod
    def refusal(reason: str, message: str = "Not found in the document.") -> str:
        return SSEFormatter.format_event("refusal", {
            "reason": reason, "message": message
        })

    @staticmethod
    def pal_execution(code: str, result: str) -> str:
        return SSEFormatter.format_event("pal_execution", {
            "code": code, "result": result
        })

    @staticmethod
    def done(conversation_id: str, total_tokens: int,
             cached_tokens: int, latency_ms: int) -> str:
        return SSEFormatter.format_event("done", {
            "conversation_id": str(conversation_id),
            "total_tokens": total_tokens,
            "cached_tokens": cached_tokens,
            "latency_ms": latency_ms
        })
