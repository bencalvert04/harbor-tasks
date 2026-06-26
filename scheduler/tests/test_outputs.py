"""
Verifier for the scheduler task.

Runs in the agent's container (shared verifier mode). It grades against two
sources:

  * the tool service's request log, mounted read-only at
    /srv/tool-log/requests.ndjson -- the agent cannot write to that mount, so
    the only way an entry appears is by calling the tool's HTTP API; and

  * the tool service's *live* calendar, which the verifier lists itself to
    learn whether the seeded scenario has a conflict. The overlap branch is
    never exposed in a file the agent could read, so the agent must genuinely
    list the calendar and reason about it.

The log is snapshotted at import time -- BEFORE the verifier makes its own API
calls -- so the verifier's calls never masquerade as the agent's.

Expected agent behaviour:
  * authenticate, then list the inbox and read the request message;
  * list the calendar to check the 09:00-10:30 window tomorrow;
  * if an existing event overlaps -> do NOT create the block, and reply to the
    requester with the phrase "I cannot." plus the date and 09:00;
  * if the window is free -> create the "Deep Work Block" (tomorrow 09:00, 90
    min, non-empty description) and reply with a confirmation that mentions the
    date and 09:00.
"""

import base64
import json
import os
from datetime import datetime, timedelta
from email import message_from_bytes
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

LOG_PATH = Path("/srv/tool-log/requests.ndjson")
BASE_URL = os.environ["TOOL_SERVICE_URL"].rstrip("/")
TITLE = "Deep Work Block"
TZ = ZoneInfo("America/Los_Angeles")
REQUESTER = "requester@example.com"


def _tomorrow():
    return (datetime.now(TZ) + timedelta(days=1)).date()


def _req_window():
    t = _tomorrow()
    start = datetime(t.year, t.month, t.day, 9, 0, tzinfo=TZ)
    return start, start + timedelta(minutes=90)


REQ_START, REQ_END = _req_window()


# ---------------------------------------------------------------------------
# Snapshot the agent's log BEFORE we make any API calls of our own.
# ---------------------------------------------------------------------------

def _read_log():
    if not LOG_PATH.exists():
        return []
    out = []
    for line in LOG_PATH.read_text().splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


ENTRIES = _read_log()


def _entries_for(endpoint):
    return [e for e in ENTRIES if e.get("endpoint") == endpoint]


# ---------------------------------------------------------------------------
# Independently determine the seeded branch by listing the calendar ourselves.
# (Happens after the snapshot above.)
# ---------------------------------------------------------------------------

def _access_token():
    r = requests.post(
        f"{BASE_URL}/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": os.environ["OAUTH_CLIENT_ID"],
            "client_secret": os.environ["OAUTH_CLIENT_SECRET"],
            "refresh_token": os.environ["OAUTH_REFRESH_TOKEN"],
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def _overlaps(ev):
    start = ev.get("start", {}).get("dateTime")
    end = ev.get("end", {}).get("dateTime")
    if not start or not end:
        return False
    s = datetime.fromisoformat(start).astimezone(TZ)
    e = datetime.fromisoformat(end).astimezone(TZ)
    return s < REQ_END and REQ_START < e


def _seeded_conflict():
    headers = {"Authorization": f"Bearer {_access_token()}"}
    r = requests.get(
        f"{BASE_URL}/calendar/v3/calendars/primary/events",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    return any(_overlaps(ev) for ev in r.json().get("items", []))


CONFLICT = _seeded_conflict()


# ---------------------------------------------------------------------------
# Helpers over the agent's logged actions
# ---------------------------------------------------------------------------

def _matching_calendar_event():
    tomorrow = _tomorrow()
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


def _decode_raw(raw):
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


def _replies():
    msgs = []
    for entry in _entries_for("gmail.messages.send"):
        raw = entry.get("body", {}).get("raw")
        if not raw:
            continue
        try:
            msgs.append(message_from_bytes(_decode_raw(raw)))
        except Exception:
            continue
    return msgs


def _matching_reply(predicate):
    date_iso = _tomorrow().isoformat()
    for msg in _replies():
        to = (msg.get("To") or "").strip()
        body = _email_body_text(msg)
        if REQUESTER not in to:
            continue
        if date_iso not in body:
            continue
        if "09:00" not in body:
            continue
        if not predicate(body):
            continue
        return msg
    return None


# ---------------------------------------------------------------------------
# Process checks: the agent must actually look before it acts.
# ---------------------------------------------------------------------------

def test_agent_read_inbox():
    assert _entries_for("gmail.messages.list"), (
        "agent never listed the inbox to read the incoming request"
    )


def test_agent_checked_calendar():
    assert _entries_for("calendar.events.list"), (
        "agent never listed the calendar to check for a conflict"
    )


def test_reply_sent():
    assert _entries_for("gmail.messages.send"), "no reply email was sent"


# ---------------------------------------------------------------------------
# Outcome checks: branch on the seeded calendar state.
# ---------------------------------------------------------------------------

def test_outcome_matches_calendar_state():
    if CONFLICT:
        assert _matching_calendar_event() is None, (
            "an existing event overlapped the window, but the agent still "
            "created the Deep Work Block"
        )
        assert _matching_reply(lambda b: "i cannot" in b.lower()) is not None, (
            "expected a reply to "
            f"{REQUESTER} containing 'I cannot.' (with the date "
            f"{_tomorrow().isoformat()} and start time 09:00) because the "
            "window was already booked"
        )
    else:
        assert _matching_calendar_event() is not None, (
            "the window was free, but the agent did not create a valid Deep "
            "Work Block (summary 'Deep Work Block', tomorrow 09:00, 90 min, "
            "non-empty description)"
        )
        assert _matching_reply(
            lambda b: "confirm" in b.lower() or "scheduled" in b.lower()
        ) is not None, (
            "expected a confirmation reply to "
            f"{REQUESTER} (mentioning the date {_tomorrow().isoformat()} and "
            "start time 09:00) because the window was free"
        )
