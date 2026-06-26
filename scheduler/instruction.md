# Scheduler

Write a Python program at `/app/solution.py` that triages an incoming
scheduling request and responds appropriately. Your program talks to a Google
API-compatible service instead of the real Google APIs. The base URL is in the
`TOOL_SERVICE_URL` environment variable. The service exposes the same endpoint
paths and request/response shapes as the real Google Calendar and Gmail REST
APIs, so you can write your requests exactly as you would against Google — just
point them at `TOOL_SERVICE_URL`.

The mailbox owner's address is in the `GMAIL_USER` environment variable.

## Authentication

All Calendar and Gmail endpoints require a valid OAuth2 bearer token; requests
without one are rejected with `401`. You are provisioned with long-lived
credentials in the environment:

- `OAUTH_CLIENT_ID`
- `OAUTH_CLIENT_SECRET`
- `OAUTH_REFRESH_TOKEN`

Exchange them for a short-lived access token exactly as you would with Google's
token endpoint — send a `POST` to `{TOOL_SERVICE_URL}/oauth2/token` with a
form-encoded body:

```
grant_type=refresh_token
client_id=$OAUTH_CLIENT_ID
client_secret=$OAUTH_CLIENT_SECRET
refresh_token=$OAUTH_REFRESH_TOKEN
```

The JSON response contains an `access_token` (valid for `expires_in` seconds).
Send it as an `Authorization: Bearer <access_token>` header on every Calendar
and Gmail request below.

## The task

In a single run of `/app/solution.py`:

### 1. Read the incoming request

The mailbox has one unread message asking you to schedule a **Deep Work Block**
for **tomorrow, 09:00–10:30 America/Los_Angeles**.

List the messages:

```
GET {TOOL_SERVICE_URL}/gmail/v1/users/me/messages
```

then fetch the message by id:

```
GET {TOOL_SERVICE_URL}/gmail/v1/users/me/messages/{id}
```

The message resource follows the Gmail shape: `payload.headers` is a list of
`{name, value}` (including `From`, `To`, `Subject`) and `payload.body.data` is
the **base64url-encoded** body. You will reply to the address in the `From`
header.

### 2. Check the calendar for a conflict

List the existing events on the `primary` calendar:

```
GET {TOOL_SERVICE_URL}/calendar/v3/calendars/primary/events
```

The response has an `items` array of events in the Google Calendar
[events](https://developers.google.com/calendar/api/v3/reference/events)
shape (`summary`, `start.dateTime`, `end.dateTime`, …). Determine whether any
existing event **overlaps** the requested window (tomorrow 09:00–10:30
America/Los_Angeles). Two intervals overlap when one starts before the other
ends.

### 3. Act on the result

**If there is an overlapping event** — do **not** create anything. Send a reply
to the requester whose body contains the exact phrase **`I cannot.`** and
mentions the requested **date** and **start time** (`09:00`).

**If there is no conflict** — first create the event, then send a reply
**confirming** it (the body must read as a confirmation — e.g. contain
`confirmed` or `scheduled` — and mention the **date** and `09:00`).

#### Creating the event

```
POST {TOOL_SERVICE_URL}/calendar/v3/calendars/primary/events
```

with a body following the Calendar
[events.insert](https://developers.google.com/calendar/api/v3/reference/events/insert)
schema:

- **summary**: `Deep Work Block`
- **description**: a non-empty description of the session.
- **start**: tomorrow at **09:00**, **America/Los_Angeles**, using the
  `dateTime` + `timeZone` form.
- **end**: **90 minutes** after the start (10:30 the same day).

#### Sending the reply

```
POST {TOOL_SERVICE_URL}/gmail/v1/users/me/messages/send
```

with a JSON body whose single field `raw` is a **base64url-encoded** RFC 2822
message. The reply must be addressed (`To`) to the **requester** (the `From` of
the incoming message).

## Requirements

- Everything happens in a single execution of `/app/solution.py`.
- "Tomorrow" is relative to the day your program runs — compute it dynamically.
- On success, exit with status code `0`; on failure, exit non-zero and print a
  useful message to stderr.
