"""Thin wrapper around the Groq chat completions API.

No tool-calling needed here, unlike the root-cause investigator — the
agentic behavior in this project comes from the generate -> validate ->
execute -> self-correct loop in query_agent.py, not from function calling.
"""
from __future__ import annotations

import json
from typing import Any

import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


def chat(api_key: str, model: str, messages: list[dict[str, Any]], temperature: float = 0.1) -> str:
    """Call Groq and return the assistant's text content."""
    response = requests.post(
        GROQ_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
            }
        ),
        timeout=30,
    )
    if response.status_code == 401 or response.status_code == 403:
        raise GroqAuthError(
            f"Groq API returned {response.status_code}: check that GROQ_API_KEY is valid "
            f"and not expired. Get a new key at https://console.groq.com/keys"
        )
    if response.status_code == 429:
        raise GroqRateLimitError("Groq API rate limit reached. Wait a moment and retry.")
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]


class GroqAuthError(RuntimeError):
    """Raised when the Groq API rejects the API key."""


class GroqRateLimitError(RuntimeError):
    """Raised when Groq rate-limits the request."""
