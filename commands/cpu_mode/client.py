from __future__ import annotations

import os
import re
from typing import Any

import requests

GROQ_API_KEY: str | None = os.environ.get("GROQ_API_KEY")
GROQ_ENDPOINT: str = "https://api.groq.com/openai/v1/chat/completions"


def query_groq(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call Groq chat completions and return message payload."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    payload = {
        "model": "openai/gpt-oss-120b",
        "messages": messages,
        "temperature": 0.7,
        "max_tokens": 550,
    }
    if tools is not None:
        payload["tools"] = tools
    resp = requests.post(GROQ_ENDPOINT, json=payload, headers=headers, timeout=15)
    resp.raise_for_status()
    out = resp.json()
    return out["choices"][0]["message"]


def clean_content(text: str | None) -> str:
    """Remove malformed function-call tags from assistant messages."""
    return re.sub(r"<function=.*?>", "", text or "").strip()
