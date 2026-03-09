import os
import re

import requests

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def query_groq(messages, tools=None):
    """Call Groq chat completions and return message payload."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {GROQ_API_KEY}",
    }
    payload = {
        "model": "meta-llama/llama-4-scout-17b-16e-instruct",
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


def clean_content(text):
    """Remove malformed function-call tags from assistant messages."""
    return re.sub(r"<function=.*?>", "", text or "").strip()
