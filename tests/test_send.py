"""Tests for mailer.send — SMTP is mocked, no real network calls."""

import io
import sys
from contextlib import redirect_stdout
from unittest.mock import MagicMock, patch

import pytest

from mailer.send import send_run, send_failure_notice


FAKE_ENV = {
    "FASTMAIL_USERNAME": "you@fastmail.com",
    "FASTMAIL_APP_PASSWORD": "fake-app-pw",
    "DIGEST_RECIPIENT": "you@fastmail.com",
    "DIGEST_SENDER": "you+philtracker-digest@fastmail.com",
    "LISTING_SENDER": "you+philtracker-listing@fastmail.com",
}


# ─── send_run ────────────────────────────────────────────────────────────


def test_send_run_one_connection_digest_plus_per_listing(monkeypatch):
    for k, v in FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    mock_smtp_instance = MagicMock()
    mock_smtp_cls = MagicMock(return_value=mock_smtp_instance)
    # Support `with smtplib.SMTP_SSL(...) as smtp` → __enter__ returns the instance
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance

    with patch("mailer.send.smtplib.SMTP_SSL", mock_smtp_cls):
        send_run(
            digest_subject="[PhilTracker] 2099-04-21 — 2 new listings (1 matching your interests)",
            digest_html="<html>digest</html>",
            per_listing_emails=[
                ("[PhilTracker] A — Somewhere (2099-06-01)", "<html>a</html>"),
                ("[PhilTracker] B — Elsewhere (no deadline)", "<html>b</html>"),
            ],
        )

    # Single SMTP_SSL call → single connection
    assert mock_smtp_cls.call_count == 1
    assert mock_smtp_cls.call_args.args[:2] == ("smtp.fastmail.com", 465)

    mock_smtp_instance.login.assert_called_once_with("you@fastmail.com", "fake-app-pw")

    # 1 digest + 2 per-listing = 3 send_message calls
    assert mock_smtp_instance.send_message.call_count == 3

    sent_messages = [call.args[0] for call in mock_smtp_instance.send_message.call_args_list]
    assert sent_messages[0]["From"] == FAKE_ENV["DIGEST_SENDER"]
    assert sent_messages[1]["From"] == FAKE_ENV["LISTING_SENDER"]
    assert sent_messages[2]["From"] == FAKE_ENV["LISTING_SENDER"]
    assert all(m["To"] == FAKE_ENV["DIGEST_RECIPIENT"] for m in sent_messages)


def test_send_run_raises_without_env_vars(monkeypatch):
    for k in FAKE_ENV:
        monkeypatch.delenv(k, raising=False)

    with pytest.raises(RuntimeError, match="missing env vars"):
        send_run(
            digest_subject="x", digest_html="<p>x</p>",
            per_listing_emails=[],
        )


def test_send_run_dry_run_prints_and_does_not_connect(monkeypatch):
    # No env vars required for dry-run.
    for k in FAKE_ENV:
        monkeypatch.delenv(k, raising=False)

    mock_smtp_cls = MagicMock()
    buf = io.StringIO()
    with patch("mailer.send.smtplib.SMTP_SSL", mock_smtp_cls), redirect_stdout(buf):
        send_run(
            digest_subject="[PhilTracker] 2099-04-21 — 1 new listing (0 matching your interests)",
            digest_html="<html><body>digest body</body></html>",
            per_listing_emails=[("[PhilTracker] A — X (2099-06-01)", "<html><body>listing a</body></html>")],
            dry_run=True,
        )

    mock_smtp_cls.assert_not_called()
    out = buf.getvalue()
    assert "DRY-RUN" in out
    assert "digest body" in out
    assert "listing a" in out
    assert "Subject: [PhilTracker] 2099-04-21 — 1 new listing (0 matching your interests)" in out
    assert "Subject: [PhilTracker] A — X (2099-06-01)" in out


# ─── send_failure_notice ─────────────────────────────────────────────────


def test_failure_notice_plaintext_subject_and_body(monkeypatch):
    for k, v in FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    mock_smtp_instance = MagicMock()
    mock_smtp_instance.__enter__.return_value = mock_smtp_instance
    mock_smtp_cls = MagicMock(return_value=mock_smtp_instance)

    with patch("mailer.send.smtplib.SMTP_SSL", mock_smtp_cls):
        send_failure_notice("AnthropicError: rate limit hit")

    assert mock_smtp_instance.send_message.call_count == 1
    sent = mock_smtp_instance.send_message.call_args.args[0]
    assert sent["Subject"].startswith("[PhilTracker] FAILED")
    assert "AnthropicError" in sent["Subject"]
    # Single-part plaintext — no HTML alternative
    assert not sent.is_multipart()
    body_text = sent.get_content()
    assert "Reason: AnthropicError: rate limit hit" in body_text


def test_failure_notice_swallows_own_failure_and_writes_stderr(monkeypatch):
    """If SMTP itself fails, the notice emits to stderr instead of raising."""
    for k, v in FAKE_ENV.items():
        monkeypatch.setenv(k, v)

    broken_smtp = MagicMock(side_effect=OSError("connection refused"))

    stderr_buf = io.StringIO()
    with patch("mailer.send.smtplib.SMTP_SSL", broken_smtp), patch.object(sys, "stderr", stderr_buf):
        # Should not raise
        send_failure_notice("Original: scraper died mid-run")

    err = stderr_buf.getvalue()
    assert "send_failure_notice itself failed" in err
    assert "Original: scraper died mid-run" in err


def test_failure_notice_dry_run(monkeypatch):
    for k in FAKE_ENV:
        monkeypatch.delenv(k, raising=False)

    mock_smtp_cls = MagicMock()
    buf = io.StringIO()
    with patch("mailer.send.smtplib.SMTP_SSL", mock_smtp_cls), redirect_stdout(buf):
        send_failure_notice("test failure reason", dry_run=True)

    mock_smtp_cls.assert_not_called()
    out = buf.getvalue()
    assert "DRY-RUN" in out
    assert "Subject: [PhilTracker] FAILED — test failure reason" in out
    assert "Reason: test failure reason" in out
