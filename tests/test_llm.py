"""Tests for the LLM wrapper + extract pipeline. No network calls —
the Anthropic client is mocked throughout."""

import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from anthropic import RateLimitError

from scrapers.base import Listing
from llm.client import call_with_retry
from llm.extract import classify_and_extract
from llm.prompts import SYSTEM_PROMPT, TOOL_SCHEMA


FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "mocked_llm_responses")
SNAPSHOTS_DIR = os.path.join(os.path.dirname(__file__), "snapshots")


def _load_fixture(name: str) -> dict:
    with open(os.path.join(FIXTURES_DIR, name)) as f:
        return json.load(f)


TOOL_NAME = TOOL_SCHEMA["name"]


# ─── prompt snapshot ─────────────────────────────────────────────────────


def test_system_prompt_snapshot():
    """The system prompt is committed; changes must be reviewed intentionally.
    Set UPDATE_SNAPSHOTS=1 to regenerate after an intended change."""
    path = os.path.join(SNAPSHOTS_DIR, "system_prompt.txt")
    if os.environ.get("UPDATE_SNAPSHOTS") == "1":
        with open(path, "w") as f:
            f.write(SYSTEM_PROMPT)
    with open(path) as f:
        expected = f.read()
    assert SYSTEM_PROMPT == expected, (
        "SYSTEM_PROMPT has drifted from tests/snapshots/system_prompt.txt. "
        "Review the diff; if intended, regenerate with UPDATE_SNAPSHOTS=1 pytest."
    )


def _mock_tool_use_response(input_data: dict) -> SimpleNamespace:
    """Shape of response.content that call_with_retry expects."""
    tool_block = SimpleNamespace(type="tool_use", name=TOOL_NAME, input=input_data)
    return SimpleNamespace(content=[tool_block])


def _make_rate_limit_error() -> RateLimitError:
    response = httpx.Response(status_code=429, request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))
    return RateLimitError("rate limited", response=response, body=None)


def test_cache_control_1h_on_system_block():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response({"is_posting": True})

    call_with_retry("test message", client=mock_client)

    kwargs = mock_client.messages.create.call_args.kwargs
    system = kwargs["system"]
    assert isinstance(system, list) and len(system) == 1
    assert system[0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_forced_tool_choice_and_model():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response({"is_posting": False})

    call_with_retry("test message", client=mock_client)

    kwargs = mock_client.messages.create.call_args.kwargs
    assert kwargs["model"] == "claude-haiku-4-5-20251001"
    assert kwargs["tool_choice"] == {"type": "tool", "name": TOOL_NAME}


def test_returns_tool_use_input_on_success():
    expected = {"is_posting": True, "confidence": 0.9, "title": "Test"}
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(expected)

    result = call_with_retry("x", client=mock_client)
    assert result == expected


def test_retries_on_rate_limit_then_succeeds():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _make_rate_limit_error(),
        _make_rate_limit_error(),
        _mock_tool_use_response({"is_posting": True, "confidence": 0.8}),
    ]

    with patch("llm.client.time.sleep") as sleep_mock:
        result = call_with_retry("x", client=mock_client, max_retries=3)

    assert result == {"is_posting": True, "confidence": 0.8}
    assert mock_client.messages.create.call_count == 3
    assert sleep_mock.call_count == 2  # two backoffs before the successful call


def test_raises_after_max_retries_exceeded():
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _make_rate_limit_error()

    with patch("llm.client.time.sleep"):
        with pytest.raises(RateLimitError):
            call_with_retry("x", client=mock_client, max_retries=2)

    # Initial attempt + 2 retries = 3 total calls before giving up
    assert mock_client.messages.create.call_count == 3


def test_corrective_retry_when_tool_use_missing():
    """If the model returns no tool_use block, one corrective retry is attempted."""
    empty_response = SimpleNamespace(content=[SimpleNamespace(type="text", text="(text response)")])
    good_response = _mock_tool_use_response({"is_posting": True, "confidence": 0.7})

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [empty_response, good_response]

    result = call_with_retry("x", client=mock_client)

    assert result == {"is_posting": True, "confidence": 0.7}
    assert mock_client.messages.create.call_count == 2
    # Second call should have the corrective hint appended
    second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
    assert len(second_call_messages) == 3  # original user + assistant response + corrective user
    assert "record_listing_classification" in second_call_messages[-1]["content"]


# ─── classify_and_extract ────────────────────────────────────────────────


def _make_listing(**overrides) -> Listing:
    defaults = dict(
        title="raw scraped title",
        institution="raw scraped institution",
        url="https://example.org/p1",
        source="test",
        description="Two-year postdoc at the Royal Society. Deadline 25 March 2026.",
    )
    defaults.update(overrides)
    return Listing(**defaults)


def test_classify_positive_maps_all_fields():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(_load_fixture("newton_positive.json"))

    listing = _make_listing()
    result = classify_and_extract(listing, client=mock_client)

    assert result.active is True
    assert result.confidence == pytest.approx(0.95)
    assert result.title == "Newton International Fellowship 2026"
    assert result.institution == "Royal Society"
    assert result.deadline == "2026-03-25"
    assert result.location == "United Kingdom"
    assert result.duration == "2 years"
    assert result.aos == ["philosophy-of-physics", "philosophy-of-science"]
    assert result.listing_type == "fellowship"
    assert "postdoctoral fellowship" in result.summary


def test_classify_negative_marks_inactive_and_preserves_scraper_fields():
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(_load_fixture("blog_negative.json"))

    listing = _make_listing(title="A blog post", description="Joe Bloggs won the X prize last year.")
    result = classify_and_extract(listing, client=mock_client)

    assert result.active is False
    assert result.confidence == pytest.approx(0.91)
    # Scraper fields preserved — the reject row is only useful for URL caching
    assert result.title == "A blog post"
    assert result.institution == "raw scraped institution"
    assert result.summary == ""
    assert result.aos == []


def test_classify_falls_back_to_scraper_when_llm_returns_empty():
    """If the LLM positively classifies but returns an empty title/institution,
    keep the scraper's values instead of overwriting with empty strings."""
    stripped_positive = _load_fixture("newton_positive.json") | {"title": "", "institution": ""}
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _mock_tool_use_response(stripped_positive)

    listing = _make_listing(title="Scraper Title", institution="Scraper Institution")
    result = classify_and_extract(listing, client=mock_client)

    assert result.active is True
    assert result.title == "Scraper Title"
    assert result.institution == "Scraper Institution"
