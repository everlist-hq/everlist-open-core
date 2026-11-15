#!/usr/bin/env python3
'''EverList merchant-agent host (PA-11, self-hosted Agent SDK deployment).

Minimal FastAPI surface over the blueprint's merchant runtime: make_options ->
ClaudeSDKClient -> run_turn (the documented host pattern). The chat turn can
ONLY stage changes; approval happens exclusively via the operator's explicit
/api/apply call (human-only law: applied_by is the operator, never the model).
The organizer token stays server-side; the model never sees it.

Run:  EVERLIST_HUB_URL=... EVERLIST_HUB_TOKEN=<organizer list token> \
      ../claude-shopping-agent/.venv/bin/python -m uvicorn server:app --port 8971
'''
from __future__ import annotations

import os
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

from claude_agent_sdk import ClaudeSDKClient
from merchant_agent import MerchantSessionContext
from merchant_agent_sdk.agent import make_options, run_turn

from agent_config import build_config
from everlist_merchant_backend import EverlistMerchantBackend

backend = EverlistMerchantBackend(
    hub_url=os.environ.get("EVERLIST_HUB_URL"),
    token=os.environ.get("EVERLIST_HUB_TOKEN"),
)
config = build_config()

app = FastAPI(title="EverList merchant agent (PA-11)", version="0.1.0")

class ChatRequest(BaseModel):
    message: str

class ApplyRequest(BaseModel):
    change_id: str

def _operator(authorization: str | None) -> str:
    """Operator identity derives from HOST auth, never from the model. The hub
    list token doubles as the operator credential in this self-hosted demo."""
    tok = (authorization or "").replace("Bearer ", "").strip()
    if not tok:
        raise HTTPException(status_code=401, detail="operator token required")
    return "operator-" + uuid.uuid5(uuid.NAMESPACE_URL, tok[:16]).hex[:8]

@app.get("/health")
async def health() -> dict:
    return {"ok": True, "agent": "everlist-merchant", "pa": "PA-11"}

@app.post("/api/chat")
async def chat(req: ChatRequest, authorization: str | None = Header(default=None)) -> dict:
    operator = _operator(authorization)
    options, toolset = make_options(
        backend=backend,
        config=config,
        session_id="m-" + uuid.uuid4().hex[:12],
        merchant_id=operator,
        operator=operator,
    )
    async with ClaudeSDKClient(options=options) as client:
        result = await run_turn(client, req.message, toolset=toolset)
    return {
        "operator": operator,
        "reply": result.final_message if hasattr(result, "final_message") else str(result)[:4000],
        "staged": [c.change_id for c in await backend.get_pending_changes(
            MerchantSessionContext(session_id="api", merchant_id=operator, operator=operator))],
    }

@app.get("/api/pending")
async def pending(authorization: str | None = Header(default=None)) -> dict:
    operator = _operator(authorization)
    ctx = MerchantSessionContext(session_id="api", merchant_id=operator, operator=operator)
    pend = await backend.get_pending_changes(ctx)
    return {"pending": [c.model_dump(mode="json") for c in pend]}

@app.post("/api/apply")
async def apply(req: ApplyRequest, authorization: str | None = Header(default=None)) -> dict:
    """EXPLICIT operator approval - the only path that applies a staged change."""
    operator = _operator(authorization)
    ctx = MerchantSessionContext(session_id="api", merchant_id=operator, operator=operator)
    try:
        ch = await backend.apply_change(ctx, req.change_id)
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e)[:200])
    return {"applied": ch.change_id, "applied_by": ch.applied_by,
            "status": ch.status.value if hasattr(ch.status, "value") else str(ch.status)}
