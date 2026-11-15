# EverList Merchant Agent (PA-11)

Self-hosted Claude merchant agent (Anthropic commerce-agents blueprint,
`MerchantBackend` contract) fronting one EverList organizer account.

## Laws carried

- **Every write is staged** — listing edits, price moves, availability, and
  promotions are `StagedChange` objects; only the human operator's explicit
  `/api/apply` call (or blueprint `apply_change` with the operator stamp)
  mutates the hub. `applied_by` is always the operator — the model cannot apply.
- **Honest limits** — no analytics history (traffic/conversion = None with a
  note, never zero); no ad campaigns (`ChangeNotApplicable`); promotions map to
  the hub's real promo system (`promo: {code, pct, uses}`, paid listings only).
- **Token secrecy** — the organizer list token is held server-side
  (`EVERLIST_HUB_TOKEN`); the model never sees it (tested).
- **Escrow visibility** — `get_order_issues` surfaces bookings whose service
  date passed while escrow is still HELD (release-or-refund pending).

## Files

| File | Role |
| --- | --- |
| `everlist_merchant_backend.py` | `MerchantBackend` over hub organizer wire (`/listings/{id}/manage`, `/orders`, public listing reads) |
| `agent_config.py` | EverList-branded config with honesty laws verbatim |
| `server.py` | FastAPI host: `/api/chat` (staged only), `/api/pending`, `/api/apply` (operator-only) |
| `test_pa11_merchant_agent.py` | 23-check suite over an isolated real hub |

## Run

```bash
export EVERLIST_HUB_URL=http://127.0.0.1:8951
export EVERLIST_HUB_TOKEN=<organizer list token>   # server-side only
../claude-shopping-agent/.venv/bin/python -m uvicorn server:app --port 8971
```

## Test

```bash
../claude-shopping-agent/.venv/bin/python test_pa11_merchant_agent.py
```
