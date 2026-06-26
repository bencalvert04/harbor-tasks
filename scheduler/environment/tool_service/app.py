"""
Mock Google Calendar + Gmail API service.

Mirrors real Google API endpoint paths and response shapes so the agent
can write code identical to what it would use against the real APIs.
Every incoming request is appended as an NDJSON line to REQUEST_LOG for
tamper-resistant grading.
"""

import json
import os
import secrets
import time
import uuid
from datetime import datetime, timezone

from flask import Flask, request, jsonify

app = Flask(__name__)

REQUEST_LOG = "/var/log/api/requests.ndjson"

os.makedirs(os.path.dirname(REQUEST_LOG), exist_ok=True)


# ---------------------------------------------------------------------------
# OAuth2 (mirrors Google's refresh-token flow)
#
# A real headless integration is provisioned with a long-lived refresh token
# plus client credentials; it exchanges them for short-lived access tokens and
# attaches them as `Authorization: Bearer` on every API call. We model exactly
# that. Interactive consent is intentionally NOT modelled -- an agent cannot
# click a browser consent screen. Secrets are never written to REQUEST_LOG.
# ---------------------------------------------------------------------------

CLIENT_ID = os.environ.get("OAUTH_CLIENT_ID", "scheduler-agent")
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "scheduler-secret")
REFRESH_TOKEN = os.environ.get("OAUTH_REFRESH_TOKEN", "seed-refresh-token")
ACCESS_TOKEN_TTL = int(os.environ.get("OAUTH_ACCESS_TOKEN_TTL", "60"))

# In-memory store of issued access tokens -> expiry (epoch seconds).
_access_tokens: dict[str, float] = {}


def _issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _access_tokens[token] = time.time() + ACCESS_TOKEN_TTL
    return token


def _auth_error():
    """Return a (response, status) tuple if unauthenticated, else None."""
    header = request.headers.get("Authorization", "")
    if not header.startswith("Bearer "):
        return jsonify({"error": {"code": 401, "message": "Missing bearer token"}}), 401
    token = header[len("Bearer "):].strip()
    expiry = _access_tokens.get(token)
    if expiry is None:
        return jsonify({"error": {"code": 401, "message": "Invalid credentials"}}), 401
    if time.time() > expiry:
        _access_tokens.pop(token, None)
        return jsonify({"error": {"code": 401, "message": "Access token expired"}}), 401
    return None


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
# OAuth2 token endpoint
# https://developers.google.com/identity/protocols/oauth2/web-server#offline
# ---------------------------------------------------------------------------

@app.post("/oauth2/token")
def oauth_token():
    # Google accepts form-encoded bodies; tolerate JSON too.
    data = request.form.to_dict() or (request.get_json(force=True, silent=True) or {})
    if data.get("grant_type") != "refresh_token":
        return jsonify({"error": "unsupported_grant_type"}), 400
    if (
        data.get("client_id") != CLIENT_ID
        or data.get("client_secret") != CLIENT_SECRET
        or data.get("refresh_token") != REFRESH_TOKEN
    ):
        return jsonify({"error": "invalid_grant"}), 401
    return jsonify(
        {
            "access_token": _issue_token(),
            "expires_in": ACCESS_TOKEN_TTL,
            "token_type": "Bearer",
            "scope": "https://www.googleapis.com/auth/calendar "
            "https://www.googleapis.com/auth/gmail.send",
        }
    ), 200


# ---------------------------------------------------------------------------
# Google Calendar Events: insert
# https://developers.google.com/calendar/api/v3/reference/events/insert
# ---------------------------------------------------------------------------

@app.post("/calendar/v3/calendars/<calendar_id>/events")
def calendar_events_insert(calendar_id: str):
    err = _auth_error()
    if err:
        return err
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
    err = _auth_error()
    if err:
        return err
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
