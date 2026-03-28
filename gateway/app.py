"""
AI Platform API Gateway
~~~~~~~~~~~~~~~~~~~~~~~
Lightweight FastAPI gateway that provides:
- API key authentication (Bearer token)
- Per-key rate limiting (RPM + daily quota)
- Request routing to backend services
- JSONL audit logging
- Usage statistics
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

LLM_API_URL = os.getenv("LLM_API_URL", "http://host.docker.internal:8000/v1")
SOCIAL_BOT_URL = os.getenv("SOCIAL_BOT_URL", "http://social-bot:8010")
WEBSITE_BACKEND_URL = os.getenv("WEBSITE_BACKEND_URL", "http://website-backend:4000")
TRADING_URL = os.getenv("TRADING_URL", "http://trading:8020")

LOG_DIR = Path(os.getenv("LOG_DIR", "/var/log/ai-gateway"))
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Parse API keys from env: "key:name:rpm:daily_quota,..."
_raw_keys = os.getenv(
    "API_KEYS",
    "sk-admin-001:admin:120:50000",
)


def _parse_api_keys(raw: str) -> dict[str, dict[str, Any]]:
    keys: dict[str, dict[str, Any]] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) < 4:
            continue
        key, name, rpm, daily = parts[0], parts[1], int(parts[2]), int(parts[3])
        keys[key] = {"name": name, "rpm": rpm, "daily_quota": daily}
    return keys


API_KEYS: dict[str, dict[str, Any]] = _parse_api_keys(_raw_keys)

# ---------------------------------------------------------------------------
# Rate-limiter state (in-memory, resets on restart)
# ---------------------------------------------------------------------------

_minute_counters: dict[str, list[float]] = defaultdict(list)
_daily_counters: dict[str, int] = defaultdict(int)
_daily_reset: str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
_stats_lock = asyncio.Lock()

# Cumulative stats
_total_requests: dict[str, int] = defaultdict(int)
_total_errors: dict[str, int] = defaultdict(int)

# ---------------------------------------------------------------------------
# Audit logger
# ---------------------------------------------------------------------------

_log_file = LOG_DIR / f"audit-{datetime.now(timezone.utc).strftime('%Y%m%d')}.jsonl"


def _audit_log(entry: dict[str, Any]) -> None:
    entry["ts"] = datetime.now(timezone.utc).isoformat()
    with open(_log_file, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# HTTP client (shared)
# ---------------------------------------------------------------------------

_client: httpx.AsyncClient | None = None


@asynccontextmanager
async def lifespan(_app: FastAPI):
    global _client
    _client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    yield
    await _client.aclose()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="AI Platform Gateway",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Auth + rate-limit helpers
# ---------------------------------------------------------------------------


def _extract_key(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:].strip()
    return request.query_params.get("api_key")


async def _check_rate_limit(key: str) -> None:
    global _daily_reset, _daily_counters

    meta = API_KEYS[key]
    now = time.time()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with _stats_lock:
        # Reset daily counters at midnight UTC
        if today != _daily_reset:
            _daily_counters.clear()
            _daily_reset = today

        # RPM check - remove timestamps older than 60s
        timestamps = _minute_counters[key]
        _minute_counters[key] = [t for t in timestamps if now - t < 60]
        if len(_minute_counters[key]) >= meta["rpm"]:
            raise HTTPException(429, detail="Rate limit exceeded (requests per minute)")

        # Daily quota check
        if _daily_counters[key] >= meta["daily_quota"]:
            raise HTTPException(429, detail="Daily quota exceeded")

        _minute_counters[key].append(now)
        _daily_counters[key] += 1


# ---------------------------------------------------------------------------
# Proxy helper
# ---------------------------------------------------------------------------

_ROUTE_MAP = {
    "/v1": LLM_API_URL,
    "/social": SOCIAL_BOT_URL,
    "/website": WEBSITE_BACKEND_URL,
    "/trading": TRADING_URL,
}


def _resolve_upstream(path: str) -> tuple[str, str]:
    """Return (upstream_base_url, remaining_path)."""
    for prefix, upstream in _ROUTE_MAP.items():
        if path == prefix or path.startswith(prefix + "/"):
            remaining = path[len(prefix):] or "/"
            return upstream, remaining
    raise HTTPException(404, detail="Unknown route")


async def _proxy(request: Request, upstream: str, path: str) -> Response:
    url = f"{upstream}{path}"
    headers = dict(request.headers)
    headers.pop("host", None)

    body = await request.body()

    try:
        resp = await _client.request(
            method=request.method,
            url=url,
            headers=headers,
            content=body,
            params=dict(request.query_params),
        )
    except httpx.RequestError as exc:
        raise HTTPException(502, detail=f"Upstream error: {exc}")

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=dict(resp.headers),
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/stats")
async def stats(request: Request):
    key = _extract_key(request)
    if not key or key not in API_KEYS:
        raise HTTPException(401, detail="Valid API key required for stats")

    async with _stats_lock:
        per_key = {}
        for k, meta in API_KEYS.items():
            per_key[meta["name"]] = {
                "total_requests": _total_requests.get(k, 0),
                "total_errors": _total_errors.get(k, 0),
                "rpm_used": len([t for t in _minute_counters.get(k, []) if time.time() - t < 60]),
                "rpm_limit": meta["rpm"],
                "daily_used": _daily_counters.get(k, 0),
                "daily_limit": meta["daily_quota"],
            }

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "keys": per_key,
    }


@app.api_route(
    "/{path:path}",
    methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
)
async def gateway_proxy(request: Request, path: str):
    full_path = f"/{path}"

    # Auth
    key = _extract_key(request)
    if not key or key not in API_KEYS:
        _audit_log({"event": "auth_fail", "path": full_path, "ip": request.client.host})
        raise HTTPException(401, detail="Invalid or missing API key")

    # Rate limit
    await _check_rate_limit(key)

    # Resolve upstream
    upstream, remaining = _resolve_upstream(full_path)

    # Track
    _total_requests[key] += 1

    start = time.time()
    try:
        response = await _proxy(request, upstream, remaining)
    except HTTPException:
        _total_errors[key] += 1
        raise

    elapsed = round(time.time() - start, 3)

    _audit_log({
        "event": "request",
        "key_name": API_KEYS[key]["name"],
        "method": request.method,
        "path": full_path,
        "upstream": upstream + remaining,
        "status": response.status_code,
        "elapsed_s": elapsed,
        "ip": request.client.host,
    })

    if response.status_code >= 400:
        _total_errors[key] += 1

    return response
