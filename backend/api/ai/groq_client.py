"""Groq chat-completions client (007 Plan): 10 s timeout, one retry on 5xx, token counts logged, key never logged.

Any failure (no key, timeout, HTTP error, bad response) raises Unavailable, so callers fall back (AI-FR-06).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
from dotenv import load_dotenv

from api.settings import ROOT
from tripwise import config

log = logging.getLogger("tripwise.ai")


class Unavailable(Exception):
    """The LLM could not be used for this call."""


def _key() -> str:
    load_dotenv(ROOT / ".env")
    k = os.environ.get("GROQ_API_KEY", "")
    if not k:
        raise Unavailable("GROQ_API_KEY is not set")
    return k


def _retry_after(r: httpx.Response) -> float | None:
    try:
        return float(r.headers.get("retry-after", ""))
    except ValueError:
        return None


def chat(messages: list[dict], *, temperature: float, tools: list[dict] | None = None,
         tool_choice: Any = None, json_mode: bool = False, max_tokens: int | None = None) -> dict:
    """One chat completion; returns the assistant message dict (content and/or tool_calls)."""
    g = config.default().groq
    body: dict[str, Any] = {"model": g["model"], "messages": messages, "temperature": temperature,
                            "max_tokens": max_tokens or g["max_tokens"]}
    if tools:
        body["tools"] = tools
        body["tool_choice"] = tool_choice or "auto"
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if g.get("reasoning_effort"):
        body["reasoning_effort"] = g["reasoning_effort"]
    headers = {"Authorization": f"Bearer {_key()}", "Content-Type": "application/json"}
    for attempt in range(2):
        t0 = time.perf_counter()
        try:
            r = httpx.post(f"{g['base_url']}/chat/completions", json=body, headers=headers, timeout=g["timeout_s"])
        except httpx.HTTPError as exc:
            log.warning("groq call failed: %s", type(exc).__name__)
            raise Unavailable(type(exc).__name__) from None
        if r.status_code >= 500 and attempt == 0:
            log.warning("groq %s, retrying once", r.status_code)
            continue
        if r.status_code == 429 and attempt == 0:      # rate limited: wait once if Groq asks for a short pause
            wait = _retry_after(r)
            if wait is not None and wait <= g["rate_limit_wait_s"]:
                log.warning("groq 429, retrying in %.1f s", wait)
                time.sleep(wait)
                continue
        if r.status_code != 200:
            log.warning("groq HTTP %s", r.status_code)
            raise Unavailable(f"HTTP {r.status_code}")
        data = r.json()
        usage = data.get("usage") or {}
        log.info("groq %s: %s prompt + %s completion tokens in %.0f ms", g["model"], usage.get("prompt_tokens"),
                 usage.get("completion_tokens"), (time.perf_counter() - t0) * 1000)
        try:
            return data["choices"][0]["message"]
        except (KeyError, IndexError):
            raise Unavailable("malformed response") from None
    raise Unavailable("server error")
