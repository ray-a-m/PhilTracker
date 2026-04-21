"""
Anthropic client wrapper for the classifier call.

- Prompt caching: the system prompt is marked with a 1-hour ephemeral cache
  breakpoint, so every call within a run (and across consecutive nightly
  runs within an hour) pays only for the per-listing user message.
- Retries: exponential backoff on transient failures (429, 5xx,
  connection errors). One corrective retry if the model somehow
  returns no tool_use block despite forced tool_choice.
"""

import os
import random
import time
from typing import Any

import anthropic
from anthropic import APIConnectionError, APIStatusError, RateLimitError

from llm.prompts import SYSTEM_PROMPT, TOOL_SCHEMA


MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024


def get_client() -> anthropic.Anthropic:
    """Return an Anthropic client using ANTHROPIC_API_KEY from the environment."""
    return anthropic.Anthropic()


def _should_retry(exc: Exception) -> bool:
    if isinstance(exc, (RateLimitError, APIConnectionError)):
        return True
    if isinstance(exc, APIStatusError):
        return getattr(exc, "status_code", 0) >= 500
    return False


def call_with_retry(
    user_message: str,
    *,
    client: anthropic.Anthropic | None = None,
    max_retries: int = 3,
) -> dict[str, Any]:
    """
    Send a classification call. Returns the parsed tool_use.input dict.

    Transient failures retry up to `max_retries` times with exponential backoff.
    A missing tool_use block triggers one corrective retry with a direct hint.
    """
    client = client or get_client()

    messages: list[dict[str, Any]] = [{"role": "user", "content": user_message}]
    system = [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral", "ttl": "1h"},
        }
    ]
    tools = [TOOL_SCHEMA]
    tool_choice = {"type": "tool", "name": TOOL_SCHEMA["name"]}

    transient_retries = 0
    corrective_retries = 0

    while True:
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                tools=tools,
                tool_choice=tool_choice,
                messages=messages,
            )
        except Exception as exc:
            if _should_retry(exc) and transient_retries < max_retries:
                backoff = (2 ** transient_retries) + random.random()
                time.sleep(backoff)
                transient_retries += 1
                continue
            raise

        tool_use = next(
            (
                b for b in response.content
                if getattr(b, "type", None) == "tool_use"
                and getattr(b, "name", None) == TOOL_SCHEMA["name"]
            ),
            None,
        )
        if tool_use is not None:
            return tool_use.input

        # Defensive: forced tool_choice should make this unreachable, but
        # give the model one chance to correct itself before failing loudly.
        if corrective_retries == 0:
            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You must call the record_listing_classification tool "
                        "to record your classification. Call it now."
                    ),
                }
            )
            corrective_retries += 1
            continue
        raise RuntimeError(
            "LLM returned no tool_use block even after corrective retry."
        )
