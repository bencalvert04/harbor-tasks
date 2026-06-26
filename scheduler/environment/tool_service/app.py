"""
Mock Google Calendar + Gmail API service.

Mirrors real Google API endpoint paths and response shapes so the agent
can write code identical to what it would use against the real APIs.
Every incoming request is appended as an NDJSON line to REQUEST_LOG for
tamper-resistant grading.
"""

import json
import os
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)

REQUEST_LOG = "/var/log/api/requests.ndjson"

os.makedirs(os.path.dirname(REQUEST_LOG), exist_ok=True)


def _log(endpoint: str, body: dict) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "endpoint": endpoint,
        "body": body,
    }
    with open(REQUEST_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    return jsonify({"status": "ok"})


# ---------------------------------------------------------------------------
# Google Calendar Events: insert
# https://developers.google.com/calendar/api/v3/reference/events/insert
# ---------------------------------------------------------------------------

@app.post("/calendar/v3/calendars/<calendar_id>/events")
def calendar_events_insert(calendar_id: str):
    body = request.get_json(force=True, silent=True) or {}
    _log("calendar.events.insert", body)

    event_id = uuid.uuid4().hex
    summary = body.get("summary", "")
    start = body.get("start", {})
    end = body.get("end", {})

    response = {
        "kind": "calendar#event",
        "etag": f'"{uuid.uuid4().hex}"',
        "id": event_id,
        "status": "confirmed",
        "htmlLink": f"https://www.google.com/calendar/event?eid={event_id}",
        "created": datetime.now(timezone.utc).isoformat(),
        "updated": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "description": body.get("description", ""),
        "creator": {"email": os.environ.get("GMAIL_USER", "user@example.com"), "self": True},
        "organizer": {"email": os.environ.get("GMAIL_USER", "user@example.com"), "self": True},
        "start": start,
        "end": end,
        "iCalUID": f"{event_id}@google.com",
        "sequence": 0,
        "reminders": {"useDefault": True},
    }
    return jsonify(response), 200


# ---------------------------------------------------------------------------
# Gmail Messages: send
# https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send
# ---------------------------------------------------------------------------

@app.post("/gmail/v1/users/<user_id>/messages/send")
def gmail_messages_send(user_id: str):
    body = request.get_json(force=True, silent=True) or {}
    _log("gmail.messages.send", body)

    response = {
        "id": uuid.uuid4().hex,
        "threadId": uuid.uuid4().hex,
        "labelIds": ["SENT"],
    }
    return jsonify(response), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
