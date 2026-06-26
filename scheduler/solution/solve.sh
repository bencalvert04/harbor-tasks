#!/bin/bash
set -euo pipefail

# Oracle solution: writes /app/solution.py and runs it.

cat > /app/solution.py <<'PY'
import base64
import os
import sys
from datetime import datetime, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import requests

BASE_URL = os.environ["TOOL_SERVICE_URL"].rstrip("/")
TITLE = "Deep Work Block"
TZ = ZoneInfo("America/Los_Angeles")


def get_access_token() -> str:
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


def header_value(msg, name):
    for h in msg.get("payload", {}).get("headers", []):
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def overlaps(ev, req_start, req_end):
    start = ev.get("start", {}).get("dateTime")
    end = ev.get("end", {}).get("dateTime")
    if not start or not end:
        return False
    s = datetime.fromisoformat(start).astimezone(TZ)
    e = datetime.fromisoformat(end).astimezone(TZ)
    return s < req_end and req_start < e


def send_reply(headers, to_addr, subject, body):
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")
    r = requests.post(
        f"{BASE_URL}/gmail/v1/users/me/messages/send",
        json={"raw": raw},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()


def main() -> int:
    headers = {"Authorization": f"Bearer {get_access_token()}"}

    # Requested window: tomorrow 09:00-10:30 America/Los_Angeles.
    now = datetime.now(TZ)
    req_start = (now + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    req_end = req_start + timedelta(minutes=90)
    date_str = req_start.strftime("%Y-%m-%d")

    # 1. Read the incoming request and find the sender.
    r = requests.get(
        f"{BASE_URL}/gmail/v1/users/me/messages", headers=headers, timeout=30
    )
    r.raise_for_status()
    message_id = r.json()["messages"][0]["id"]
    r = requests.get(
        f"{BASE_URL}/gmail/v1/users/me/messages/{message_id}",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    requester = header_value(r.json(), "From")

    # 2. Check the calendar for a conflict in the requested window.
    r = requests.get(
        f"{BASE_URL}/calendar/v3/calendars/primary/events",
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()
    items = r.json().get("items", [])
    conflict = any(overlaps(ev, req_start, req_end) for ev in items)

    # 3. Act.
    if conflict:
        send_reply(
            headers,
            requester,
            f"Re: {TITLE}",
            f"I cannot. The requested {TITLE} for {date_str} starting at 09:00 "
            f"(America/Los_Angeles) conflicts with an existing event, so I did "
            f"not create it.",
        )
        return 0

    # No conflict: create the event, then confirm.
    event = {
        "summary": TITLE,
        "description": "Focused, uninterrupted deep work session.",
        "start": {"dateTime": req_start.isoformat(), "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": req_end.isoformat(), "timeZone": "America/Los_Angeles"},
    }
    r = requests.post(
        f"{BASE_URL}/calendar/v3/calendars/primary/events",
        json=event,
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()

    send_reply(
        headers,
        requester,
        f"Re: {TITLE}",
        f"Confirmed. Your {TITLE} is scheduled for {date_str} starting at 09:00 "
        f"(America/Los_Angeles), running 90 minutes until 10:30.",
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"solution failed: {exc}", file=sys.stderr)
        sys.exit(1)
PY

python /app/solution.py
