"""
Fastmail SMTP delivery — digest + per-listing emails in one connection,
plus a minimal failure-notice path.

Environment variables (read at call time):
  FASTMAIL_USERNAME       — Fastmail login username
  FASTMAIL_APP_PASSWORD   — Fastmail app password (NOT main account password)
  DIGEST_RECIPIENT        — usually your own Fastmail address
  DIGEST_SENDER           — e.g. you+philtracker-digest@fastmail.com (Inbox)
  LISTING_SENDER          — e.g. you+philtracker-listing@fastmail.com
                            (Sieve rule routes to PhilTracker/Listings)

The failure-notice path deliberately imports only `smtplib` and
`email.message` so it still works when jinja/anthropic fail.
"""

import os
import smtplib
import sys
from email.message import EmailMessage
from typing import Iterable


SMTP_HOST = "smtp.fastmail.com"
SMTP_PORT = 465


def _env_required(*names: str) -> dict[str, str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise RuntimeError(f"missing env vars: {', '.join(missing)}")
    return {n: os.environ[n] for n in names}


def _build_html_message(subject: str, html_body: str, sender: str, recipient: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content("This email requires an HTML-capable client.")
    msg.add_alternative(html_body, subtype="html")
    return msg


def _build_plaintext_message(subject: str, body: str, sender: str, recipient: str) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = sender
    msg["To"] = recipient
    msg.set_content(body)
    return msg


def _dry_run_print(msg: EmailMessage) -> None:
    print(f"--- DRY-RUN: {msg['From']} → {msg['To']}")
    print(f"Subject: {msg['Subject']}")
    print()
    # For multipart messages, print the HTML alternative; otherwise the plaintext body.
    if msg.is_multipart():
        for part in msg.iter_parts():
            if part.get_content_type() == "text/html":
                print(part.get_content())
                break
    else:
        print(msg.get_content())
    print("--- END DRY-RUN\n")


def send_run(
    digest_subject: str,
    digest_html: str,
    per_listing_emails: Iterable[tuple[str, str]],
    *,
    dry_run: bool = False,
) -> None:
    """Send the digest plus N per-listing emails over a single SMTP connection.

    `per_listing_emails` is an iterable of `(subject, html_body)` tuples.
    """
    per_listing_list = list(per_listing_emails)

    if dry_run:
        dry_recipient = os.environ.get("DIGEST_RECIPIENT", "dry-run@example.com")
        dry_digest_sender = os.environ.get("DIGEST_SENDER", "dry-digest@example.com")
        dry_listing_sender = os.environ.get("LISTING_SENDER", "dry-listing@example.com")

        _dry_run_print(_build_html_message(digest_subject, digest_html, dry_digest_sender, dry_recipient))
        for subject, html in per_listing_list:
            _dry_run_print(_build_html_message(subject, html, dry_listing_sender, dry_recipient))
        return

    env = _env_required(
        "FASTMAIL_USERNAME", "FASTMAIL_APP_PASSWORD",
        "DIGEST_RECIPIENT", "DIGEST_SENDER", "LISTING_SENDER",
    )

    digest_msg = _build_html_message(
        digest_subject, digest_html,
        sender=env["DIGEST_SENDER"], recipient=env["DIGEST_RECIPIENT"],
    )

    per_listing_msgs = [
        _build_html_message(
            subject, html,
            sender=env["LISTING_SENDER"], recipient=env["DIGEST_RECIPIENT"],
        )
        for subject, html in per_listing_list
    ]

    with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
        smtp.login(env["FASTMAIL_USERNAME"], env["FASTMAIL_APP_PASSWORD"])
        smtp.send_message(digest_msg)
        for msg in per_listing_msgs:
            smtp.send_message(msg)


def send_failure_notice(reason: str, *, dry_run: bool = False) -> None:
    """Deliver a plaintext failure notice. Survives jinja/anthropic import
    failures. Wrapped in its own try/except so a failure here never swallows
    the original exception — the caller re-raises after calling this.
    """
    try:
        subject = f"[PhilTracker] FAILED — {reason[:120]}"
        body = (
            "The nightly PhilTracker run did not complete.\n\n"
            f"Reason: {reason}\n\n"
            "Check the launchd logs for the full traceback.\n"
        )

        if dry_run:
            sender = os.environ.get("DIGEST_SENDER", "dry-digest@example.com")
            recipient = os.environ.get("DIGEST_RECIPIENT", "dry-run@example.com")
            _dry_run_print(_build_plaintext_message(subject, body, sender, recipient))
            return

        env = _env_required(
            "FASTMAIL_USERNAME", "FASTMAIL_APP_PASSWORD",
            "DIGEST_RECIPIENT", "DIGEST_SENDER",
        )
        msg = _build_plaintext_message(
            subject, body,
            sender=env["DIGEST_SENDER"], recipient=env["DIGEST_RECIPIENT"],
        )
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) as smtp:
            smtp.login(env["FASTMAIL_USERNAME"], env["FASTMAIL_APP_PASSWORD"])
            smtp.send_message(msg)
    except Exception as inner:
        sys.stderr.write(
            f"[PhilTracker] send_failure_notice itself failed: {inner!r}\n"
            f"Original reason: {reason}\n"
        )
