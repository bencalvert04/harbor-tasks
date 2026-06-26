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
RECIPIENT = os.environ["GMAIL_USER"]
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


def main() -> int:
    headers = {"Authorization": f"Bearer {get_access_token()}"}

    # Tomorrow at 09:00 America/Los_Angeles, 90 minutes long.
    now = datetime.now(TZ)
    start = (now + timedelta(days=1)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    end = start + timedelta(minutes=90)

    # 1. Create the calendar event.
    event = {
        "summary": TITLE,
        "description": "Focused, uninterrupted deep work session.",
        "start": {"dateTime": start.isoformat(), "timeZone": "America/Los_Angeles"},
        "end": {"dateTime": end.isoformat(), "timeZone": "America/Los_Angeles"},
    }
    r = requests.post(
        f"{BASE_URL}/calendar/v3/calendars/primary/events",
        json=event,
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()

    # 2. Send the notification email.
    date_str = start.strftime("%Y-%m-%d")
    time_str = start.strftime("%H:%M")
    msg = EmailMessage()
    msg["To"] = RECIPIENT
    msg["Subject"] = f"Scheduled: {TITLE}"
    msg.set_content(
        f"Your '{TITLE}' event is scheduled for {date_str} starting at {time_str} "
        f"(America/Los_Angeles)."
    )
    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("ascii")

    r = requests.post(
        f"{BASE_URL}/gmail/v1/users/me/messages/send",
        json={"raw": raw},
        headers=headers,
        timeout=30,
    )
    r.raise_for_status()

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"solution failed: {exc}", file=sys.stderr)
        sys.exit(1)
PY

python /app/solution.py
