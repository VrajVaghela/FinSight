"""Groq/LangChain helpers for low-latency structured RAG calls."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel

SchemaT = TypeVar("SchemaT", bound=BaseModel)


def _load_project_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env", override=False)


def _resolve_groq_api_key(api_key: str | None = None) -> str:
    _load_project_env()
    resolved = api_key or os.getenv("GROQ_API_KEY")
    if not resolved:
        raise RuntimeError(
            "Groq API key not found. Set GROQ_API_KEY in conversationalai/.env "
            "or in the process environment."
        )
    return resolved


def _resolve_model_name(model: str | None = None) -> str:
    _load_project_env()
    return (
        model
        or os.getenv("GROQ_MODEL")
        or os.getenv("LLM_MODEL")
        or "llama-3.3-70b-versatile"
    )


def _resolve_temperature(temperature: float | None = None) -> float:
    _load_project_env()
    if temperature is not None:
        return temperature
    raw = os.getenv("GROQ_TEMPERATURE") or os.getenv("LLM_TEMPERATURE") or "0"
    try:
        return float(raw)
    except ValueError:
        return 0.0


def build_groq_llm(
    api_key: str | None = None,
    model: str | None = None,
    temperature: float | None = None,
):
    """Create the project-standard Groq chat model."""
    from langchain_groq import ChatGroq

    return ChatGroq(
        groq_api_key=_resolve_groq_api_key(api_key),
        model_name=_resolve_model_name(model),
        temperature=_resolve_temperature(temperature),
    )


def get_llm(llm: Any | None = None):
    """Return an injected LLM or construct the default Groq LLM."""
    return llm if llm is not None else build_groq_llm()


def response_text(response: Any) -> str:
    if isinstance(response, str):
        return response

    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict) and "text" in item:
                parts.append(str(item["text"]))
        return "".join(parts)
    return str(content)


def parse_json_object(text: str) -> dict:
    cleaned = text.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            raise
        return json.loads(match.group(0))


async def ainvoke_text(llm: Any, prompt: str) -> str:
    if hasattr(llm, "ainvoke"):
        return response_text(await llm.ainvoke(prompt))
    return response_text(llm.invoke(prompt))


async def ainvoke_structured(
    llm: Any,
    prompt_template: Any,
    schema: type[SchemaT],
    variables: dict[str, Any],
) -> SchemaT:
    """Invoke ChatGroq.with_structured_output, with a test-double fallback."""
    llm = get_llm(llm)
    if hasattr(llm, "with_structured_output"):
        chain = prompt_template | llm.with_structured_output(schema)
        result = await chain.ainvoke(variables)
        if isinstance(result, schema):
            return result
        if isinstance(result, dict):
            return schema.model_validate(result)
        return schema.model_validate(parse_json_object(response_text(result)))

    prompt = prompt_template.format(**variables)
    text = await ainvoke_text(llm, prompt)
    try:
        data = parse_json_object(text)
        data = _normalize_legacy_payload(schema, data)
        return schema.model_validate(data)
    except Exception:
        fields = getattr(schema, "model_fields", {})
        if len(fields) == 1:
            field_name = next(iter(fields))
            return schema.model_validate({field_name: text})
        if {"answer_text", "ui_component_hint"}.issubset(fields):
            return schema.model_validate(
                {"answer_text": text, "ui_component_hint": "Paragraph"}
            )
        raise


def _normalize_legacy_payload(schema: type[SchemaT], data: dict) -> dict:
    fields = getattr(schema, "model_fields", {})
    if {"is_relevant", "requires_pal"}.issubset(fields) and "relevant" in data:
        return {
            "is_relevant": bool(data.get("relevant")),
            "refusal_reason": str(data.get("reason", "")),
            "requires_pal": bool(data.get("requires_pal", False)),
        }
    if {"is_safe", "audit_failure_reason"}.issubset(fields):
        if "passed" in data:
            return {
                "is_safe": bool(data.get("passed")),
                "audit_failure_reason": "; ".join(
                    str(item) for item in data.get("violations", [])
                ),
            }
        if "violated" in data:
            return {
                "is_safe": not bool(data.get("violated")),
                "audit_failure_reason": str(data.get("detail", "")),
            }
    return data
