# EverList shopping agent (PA-10)

Self-hosted deployment of Anthropic's commerce-agents blueprint (`shopping-agent`)
over the EverList hub REST API. Owner-approved 2026-11-14 (options A+B+C; this is B).

## Honest mapping

- `checkout_handoff` -> hub hosted checkout (`/checkout?sid=...`); the URL is applied
  by the host, never shown to the model; rail label verbatim on the hosted page.
- `get_orders` -> NotOffered (no customer order history without credentials).
- `get_fulfillment_options` -> NotOffered (events have no shipping).
- Config: orders OFF, fulfillment OFF (switches removed the tools entirely - the
  blueprint's honest way to omit a system).
- Demo listings carry the `Curated example listing` attribute.

## Run

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r /tmp/commerce-agents/requirements.txt   # pinned blueprint deps
pip install -e /tmp/commerce-agents/shopping-agent/core
pip install -e /tmp/commerce-agents/shopping-agent/runtime-messages-api
pip install -e /tmp/commerce-agents/commerce-common
EVERLIST_HUB_URL=http://127.0.0.1:8951 ANTHROPIC_API_KEY=... \
  uvicorn server:app --port 8962
curl -s localhost:8962/api/chat -H 'content-type: application/json' \
  -d '{"message":"Find a pottery workshop in Vienna"}'
```

Escrow-care system text lives in `agent_config.py` (brand_voice) so the deployed
agent inherits the same laws as the PA-9 managed agent: rail labels verbatim,
checkout never moves money, bookings are agreements the human confirms.
