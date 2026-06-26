"""
Verifier for the scheduler task.

Runs in the agent's container (shared verifier mode) and grades against the
tool service's request log, which is mounted read-only at
/srv/tool-log/requests.ndjson. The agent cannot write to that mount, so the
only way an entry appears is by calling the tool service's HTTP API.

Checks:
  * a Google Calendar events.insert request creating "Deep Work Block"
    tomorrow at 09:00 America/Los_Angeles, lasting 90 minutes, with a
    non-empty description.
  * a Gmail messages.send request whose decoded MIME message is addressed to
    GMAIL_USER, has a subject containing the event title, and a body that
    mentions the event date and start time.
"""

import base64
import json
import os
from datetime import datetime, timedelta
from email import message_from_bytes
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

LOG_PATH = Path("/srv/tool-log/requests.ndjson")
TITLE = "Deep Work Block"
TZ = ZoneInfo("America/Los_Angeles")
RECIPIENT = os.environ.get("GMAIL_USER", "user@example.com")


def _load_entries():
    assert LOG_PATH.exists(), f"tool service log not found at {LOG_PATH}"
    entries = []
    for line in LOG_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            entries.append(json.loads(line))
    return entries


def _entries_for(endpoint):
    return [e for e in _load_entries() if e.get("endpoint") == endpoint]


def _expected_dates():
    """Tomorrow (relative to now in LA) as a date object."""
    return (datetime.now(TZ) + timedelta(days=1)).date()


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------

def _matching_calendar_event():
    tomorrow = _expected_dates()
    for entry in _entries_for("calendar.events.insert"):
        body = entry.get("body", {})
        if body.get("summary") != TITLE:
            continue
        start_raw = body.get("start", {}).get("dateTime")
        end_raw = body.get("end", {}).get("dateTime")
        if not start_raw or not end_raw:
            continue
        try:
            start = datetime.fromisoformat(start_raw)
            end = datetime.fromisoformat(end_raw)
        except ValueError:
            continue
        if start.tzinfo is None or end.tzinfo is None:
            continue
        start_la = start.astimezone(TZ)
        if start_la.date() != tomorrow:
            continue
        if (start_la.hour, start_la.minute) != (9, 0):
            continue
        if (end - start) != timedelta(minutes=90):
            continue
        if not str(body.get("description", "")).strip():
            continue
        return entry
    return None


def test_calendar_event_created():
    events = _entries_for("calendar.events.insert")
    assert events, "no calendar events.insert request was logged"


def test_calendar_event_correct():
    assert _matching_calendar_event() is not None, (
        "no calendar event matched: expected summary 'Deep Work Block', start "
        f"{_expected_dates()} 09:00 America/Los_Angeles, 90 min duration, and a "
        "non-empty description"
    )


# ---------------------------------------------------------------------------
# Gmail
# ---------------------------------------------------------------------------

def _decode_raw(raw):
    # Gmail uses base64url; tolerate missing padding.
    padded = raw + "=" * (-len(raw) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def _email_body_text(msg):
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    parts.append(payload.decode("utf-8", errors="replace"))
        return "\n".join(parts)
    payload = msg.get_payload(decode=True)
    if payload is None:
        return str(msg.get_payload())
    return payload.decode("utf-8", errors="replace")


def _matching_email():
    tomorrow = _expected_dates()
    date_iso = tomorrow.isoformat()
    for entry in _entries_for("gmail.messages.send"):
        raw = entry.get("body", {}).get("raw")
        if not raw:
            continue
        try:
            msg = message_from_bytes(_decode_raw(raw))
        except Exception:
            continue
        to = (msg.get("To") or "").strip()
        subject = msg.get("Subject") or ""
        body = _email_body_text(msg)
        if RECIPIENT not in to:
            continue
        if TITLE not in subject:
            continue
        if date_iso not in body:
            continue
        if "09:00" not in body:
            continue
        return entry
    return None


def test_email_sent():
    sends = _entries_for("gmail.messages.send")
    assert sends, "no gmail messages.send request was logged"


def test_email_correct():
    assert _matching_email() is not None, (
        f"no email matched: expected recipient '{RECIPIENT}', subject containing "
        f"'{TITLE}', and a body mentioning the date {_expected_dates().isoformat()} "
        "and start time 09:00"
    )
