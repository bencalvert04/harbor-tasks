#!/usr/bin/env python3
"""Metered proxy for author probe budget enforcement (spec §9).

Started by steps/step-2/workdir/setup.sh on localhost:8080.
PROXY_API_KEY env var = the real Anthropic key used for upstream forwarding.

Endpoints:
  GET  /health          → 200 {"status":"ok","budget":{...}}
  POST /lease           → {"model":"..."} → 200 {"token":"...","remaining":N} or 429
  ANY  /v1/{path}       → forward to api.anthropic.com if token valid, else 403

Budget (reset to {opus:1, haiku:3} on each startup):
  Determined by model name: "opus" → opus bucket, "haiku" → haiku bucket.

Token lifecycle: one UUID per /lease call; valid for all /v1/ forwarding until
the proxy restarts. One harbor run = one lease (the run makes many /v1/messages
calls but uses the same token).
"""

import json
import os
import threading
import uuid

import httpx
from fastapi import FastAPI, Request, Response

app = FastAPI()

UPSTREAM = "https://api.anthropic.com"
PROXY_API_KEY = os.environ.get("PROXY_API_KEY", "")

_lock = threading.Lock()
_budget: dict[str, int] = {"opus": 1, "haiku": 3}
_tokens: dict[str, str] = {}  # token → model_key ("opus"|"haiku")


def _model_key(model: str) -> str:
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "haiku" in m:
        return "haiku"
    return "unknown"


@app.get("/health")
def health():
    with _lock:
        return {"status": "ok", "budget": dict(_budget)}


@app.post("/lease")
async def lease(request: Request):
    body = await request.json()
    model = body.get("model", "")
    key = _model_key(model)
    with _lock:
        remaining = _budget.get(key, 0)
        if remaining <= 0:
            return Response(
                content=json.dumps({"error": f"Probe budget exhausted for {key}"}),
                status_code=429,
                media_type="application/json",
            )
        _budget[key] -= 1
        token = str(uuid.uuid4())
        _tokens[token] = key
        remaining_after = _budget[key]
    return {"token": token, "model_key": key, "remaining": remaining_after}


@app.api_route("/v1/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
async def proxy(request: Request, path: str):
    # Validate probe token (sent as Bearer API key by claude-code).
    auth = request.headers.get("Authorization", "")
    token = auth.removeprefix("Bearer ").strip()
    if token not in _tokens:
        return Response(
            content=json.dumps({"error": "Invalid or missing probe token — use `probe` to run"}),
            status_code=403,
            media_type="application/json",
        )

    # Forward to Anthropic with the real key.
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()
               if k.lower() not in ("host", "content-length", "authorization")}
    headers["authorization"] = f"Bearer {PROXY_API_KEY}"

    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.request(
            method=request.method,
            url=f"{UPSTREAM}/v1/{path}",
            headers=headers,
            content=body,
        )

    # Strip hop-by-hop headers that can't be forwarded.
    exclude = {"transfer-encoding", "connection", "keep-alive"}
    resp_headers = {k: v for k, v in resp.headers.items() if k.lower() not in exclude}

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=resp_headers,
        media_type=resp.headers.get("content-type"),
    )
