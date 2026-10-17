# agent-hub-v2 — open agent commerce hub

Open-source (MIT), community-driven hub core proving the universal booking pattern:

discover → search → register & pay (escrow) → confirm/cancel → transparent ledger

## Fairness by design (enforced in protocol, not promises)

- **declared fee policy** — each hub declares its fee in the manifest; agents verify
  declared vs public ledger and choose (no protocol cap; transparency is the enforcement)
- **tiered registry** — open self-registration; `verified` requires operator review
  (authoritative registry service: `../registry/`)
- **open ledger** — every transaction + fee publicly queryable and independently
  cross-checkable (`../registry/check_hub.py`)
- **pseudonymous bookings** — public ledger shows pseudonyms only; real identity only
  via per-booking secret; we never store who you are
- **exact privacy docs** — what the hub stores, never stores, retention and deletion,
  code-mapped: see [PRIVACY.md](PRIVACY.md)
- **schemas are versioned + community-extensible** (verticals via schema files)

## Components

| File | Purpose |
| --- | --- |
| `app.py` | hub core: manifest, search, escrow bookings, ledger, x402 rails |
| `hublib.py` | versioned, domain-separated HMAC action tokens |
| `x402verify.py` | REAL EIP-3009 signed-payment verification (eth-account) |
| `x402facilitate.py` | idempotent settlement client with honest UNKNOWN semantics |
| `wrapper.py` | uAgents wrapper (Fetch/Agentverse ecosystem) |
| `sdk/agenthub/` | stdlib-only Python merchant/agent SDK (+ `examples/pizzeria.py`) |
| `SPEC.md` | normative protocol spec (endpoints, auth matrix, escrow state machine) |
| `/openapi.json` (served by the hub) | machine-readable API contract (OpenAPI 3.1) — agents read it natively; linked from the discovery manifest |
| `payments_x402.md` | x402 payment design + mode documentation |

## Payment modes

| Mode | Env | Meaning |
| --- | --- | --- |
| simulated | `HUB_PAY_MODE=simulated` | honestly labeled demo flow (default) |
| testnet | `HUB_PAY_MODE=testnet` | real signed EIP-3009 verification vs official USDC domains |
| settlement | `HUB_SETTLE_MODE=off\|auto` | off: verify only · auto: settle via facilitator (idempotent, `HUB_FACILITATOR_URL`) |

## Quickstart (10 minutes, SDK)

```bash
# 1. start a hub (or point at any running one)
make up                       # http://localhost:8802

# 2. run the quickstart example — the full agent journey:
#    manifest -> keypair account -> search -> book (escrow HELD) -> cancel
python3 sdk/examples/quickstart.py http://localhost:8802
```

The example prints the seed ONCE (it never leaves your machine — the hub stores
only your public key), books a listing (payment held in escrow until the
merchant confirms), and cancels with the one-time cancel token. For a merchant
view (publish listings, poll incoming orders), see `sdk/examples/pizzeria.py`.

Key SDK calls:

```python
from agenthub import AgentHub
hub = AgentHub("http://localhost:8802")
hub.manifest()                      # discover: name, fee %, escrow mode
acct = hub.signup_keypair("me")     # Tier-1 account; store the seed locally
hits = hub.search("yoga")           # or hub.listings()
b    = hub.book(hits[0].id, quantity=1, attendee="demo")  # escrow holds payment
hub.cancel(b.id, b.cancel_token)     # one-time token, buyer-side refund
```

The booking gate (`human_verified`) is an interim stub for demo/testnet runs;
production replaces it with a Midnight ZK personhood credential (SPEC section 22).

## Run

```bash
python3 app.py [port]        # default 8802
make test                    # full suite (unit + E2E + security)
```

See `SPEC.md` for the protocol contract and `../registry/` for the hub-of-hubs
registry + conformance checker.

## Midnight integration (ZK escrow, live)

**Live deployment:** [everlist.network](https://everlist.network) — chat-first booking
board; ask in plain language, book, and payment is provably held in escrow until
the event has happened (auto-refund included).

| Piece | Where | What it does |
| --- | --- | --- |
| `midnight-contract/src/escrow.compact` | Compact | Escrow state machine: funded create (exact-value shielded coin), conditional release, refund, timeout refund, auto-release, mutual refund |
| `midnight-contract/src/credential.compact` | Compact | ZK personhood credential (one-human-one-account) on commitments: issue / proveHolder / revoke |
| `midnight-contract/managed*/` | compiled | Artifacts from `compactc` 0.34.0 incl. ZK prover/verifier keys + ZKIR |
| `midnight-contract/test/` | offline tests | State-machine tests running the REAL compiled circuits against a simulated ledger — no network, no proof server |
| `sponsorship.py` | Wave-2 delta | Abuse-resistant DUST sponsorship: per-organizer window limits, pool budget cap, stake threshold — zero-DUST organizers and workers can transact |
| `app.py` escrow events + `GET /escrow/{id}/proof` | Wave-2 delta | Real-time escrow state events (released/refunded/timed-out) + fail-closed proof endpoint |
| `tools/cost_matrix.py` | Wave-2 delta | One-command cost matrix (recorded + live) for per-operation escrow costs |

**Test the contracts offline (no network, ~10s):**

```bash
cd midnight-contract
npm ci
npx tsx --test test/escrow.test.ts              # escrow state machine: 40/40
npx tsx --test test/credential.test.ts          # personhood credential: 16/16
npx tsx --test test/mandate.test.ts             # delegated spending mandate: 18/18
npx tsx --test test/indistinguishability.test.ts # privacy indistinguishability: 7/7
npx tsx --test test/reputation.test.ts          # reputation from settled escrows: 22/22
npx tsx --test test/milestone.test.ts           # milestone escrow + dispute path: 45/45
```

**Privacy audit (Tell, 2026-10-16/17):** all five contracts scanned with the
[Tell](https://github.com/RohanGlitched/tell) Compact privacy scanner — all
**Grade A, 0 findings above info**. `escrow.compact` was originally Grade C
(one medium finding: per-holder commitments made an organizer's escrows
publicly linkable), fixed by binding commitments to the booking reference,
recompiled, regression-tested and re-scanned. Since then, `credential`, and
the three new contracts (`mandate`, `reputation`, `milestone`), have been
scanned **at birth** — clean before first ship, by policy.

**5-minute judge path (no wallet, live):** discover → listings → agent token
→ book (escrow HELD/WAIVED) → cancel (REFUNDED) → public ledger — the exact
curl commands, plus evidence & receipts and the honest-limits statement, are
in [`midnight-contract/README.md`](midnight-contract/README.md). Every step
was verified end-to-end against production on 2026-10-16.

Licensing for the Wave-2 Midnight code: Apache License 2.0 — see `NOTICE` and
`LICENSE-APACHE-2.0.txt` in the repo root; the pre-existing core stays MIT.
