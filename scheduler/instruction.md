# Scheduler

Write a Python program at `/app/solution.py` that schedules a focused work
session and notifies the user about it. In a single run it must:

1. **Create a Google Calendar event**, then
2. **Send a Gmail message** announcing that event.

Your program talks to a Google API-compatible service instead of the real
Google APIs. The base URL is provided in the `TOOL_SERVICE_URL` environment
variable. The service exposes the same endpoint paths and request/response
shapes as the real Google Calendar and Gmail REST APIs, so you can write your
requests exactly as you would against Google — just point them at
`TOOL_SERVICE_URL`. No authentication is required.

The recipient's email address is provided in the `GMAIL_USER` environment
variable.

## 1. Calendar event

Send a `POST` to:

```
{TOOL_SERVICE_URL}/calendar/v3/calendars/primary/events
```

with a JSON body following the Google Calendar
[events.insert](https://developers.google.com/calendar/api/v3/reference/events/insert)
schema. The event must have:

- **summary**: `Deep Work Block`
- **description**: a non-empty description of the session.
- **start**: **tomorrow** at **09:00** in the **America/Los_Angeles** timezone.
- **end**: **90 minutes** after the start (i.e. 10:30 the same day).

Use the `dateTime` + `timeZone` form for `start` and `end`, e.g.:

```json
{
  "summary": "Deep Work Block",
  "description": "Focused, uninterrupted work session.",
  "start": { "dateTime": "2026-06-27T09:00:00-07:00", "timeZone": "America/Los_Angeles" },
  "end":   { "dateTime": "2026-06-27T10:30:00-07:00", "timeZone": "America/Los_Angeles" }
}
```

("Tomorrow" is relative to the day your program runs — compute it dynamically.)

## 2. Gmail notification

After the event is created, send a `POST` to:

```
{TOOL_SERVICE_URL}/gmail/v1/users/me/messages/send
```

with a JSON body following the Google Gmail
[messages.send](https://developers.google.com/gmail/api/reference/rest/v1/users.messages/send)
schema. The body must contain a single field `raw`: a **base64url-encoded**
RFC 2822 email message. The email must have:

- **To**: the address in `GMAIL_USER`.
- **Subject**: must contain the event title `Deep Work Block`.
- **Body**: must mention the event, the **date** of the event, and the
  **start time** (09:00).

## Requirements

- Both actions must happen in a single execution of `/app/solution.py`.
- On success, exit with status code `0`.
- On failure, exit with a non-zero status code and print a useful message to
  stderr.
