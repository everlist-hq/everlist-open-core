'''EverList shopping-agent host (PA-10, self-hosted Agent SDK deployment).

Minimal FastAPI surface over ShoppingAgent.stream_turn: JSON in, event list out.
Sessions are in-memory (messages + provenance state), mirroring the PA-9 cart law:
ephemeral, never persisted, TTL-pruned.

Run:  EVERLIST_HUB_URL=http://127.0.0.1:8951 uvicorn server:app --port 8962
Auth: none for reads; order-status tokens are never handled by the model (the
      backend holds them server-side).
'''
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from commerce_common.memory import InMemoryMemoryStore
from shopping_agent import ShoppingSessionContext, ShoppingSessionState
from shopping_agent_runtime import ShoppingAgent

from agent_config import build_config
from everlist_backend import EverlistStorefrontBackend, PUBLIC_URL

BLUEPRINT_SKILLS = os.environ.get(
    "COMMERCE_AGENTS_SKILLS_DIR", "/tmp/commerce-agents/shopping-agent/skills"
)

backend = EverlistStorefrontBackend()
agent = ShoppingAgent(
    backend=backend,
    skills_dir=Path(BLUEPRINT_SKILLS) if Path(BLUEPRINT_SKILLS).is_dir() else None,
    config=build_config(),
    memory_store=InMemoryMemoryStore(),
)

_SESSIONS: dict[str, dict[str, Any]] = {}
_TTL = 3600.0

app = FastAPI(title="EverList shopping agent (PA-10)", version="0.1.0")


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@app.get("/health")
async def health() -> dict:
    return {"ok": True, "agent": "everlist-shopping", "public_url": PUBLIC_URL}


@app.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    now = time.time()
    for k in [k for k, v in _SESSIONS.items() if now - v["ts"] > _TTL]:
        _SESSIONS.pop(k, None)
    sid = req.session_id or ("sas-" + uuid.uuid4().hex)
    rec = _SESSIONS.setdefault(sid, {"messages": [], "state": ShoppingSessionState(), "ts": now})
    rec["ts"] = now
    session = ShoppingSessionContext(session_id=sid, user_id="guest-" + sid[:8])
    rec["messages"].append({"role": "user", "content": req.message})
    events: list[dict] = []
    try:
        async for ev in agent.stream_turn(rec["messages"], session, rec["state"]):
            events.append(ev.model_dump())
    except Exception as e:  # surfaced honestly, never swallowed
        raise HTTPException(status_code=502, detail=f"agent turn failed: {e}") from e
    # stream_turn extends rec["messages"] in place; persist whatever is new
    return {"session_id": sid, "events": events,
            "reply": "".join(e["data"].get("text", "") for e in events
                             if e["type"] == "text_delta")}


@app.get("/api/session/{sid}")
async def session_view(sid: str) -> dict:
    rec = _SESSIONS.get(sid)
    if not rec:
        raise HTTPException(status_code=404, detail="no such session")
    cart = await backend.get_cart(ShoppingSessionContext(session_id=sid, user_id="x"))
    return {"session_id": sid, "cart": cart.model_dump(),
            "turns": len(rec["messages"])}
