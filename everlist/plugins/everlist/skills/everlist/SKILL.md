---
name: everlist
description: Search, book, and verify EverList listings (everlist.network) - a listing is something with a date where a human is needed or wanted. Workshops, concerts, food, services, jobs, p2p. Booking settles in escrow with permissionless timeout refunds; paid calls use x402; rail labels are reported verbatim (testnet stays testnet).
---

# EverList: book dated, human-needed listings in escrow

EverList (everlist.network) is a listing-first agent commerce marketplace.
A **listing is something with a date where a human is needed or wanted**:
workshops, concerts, food, services, jobs, peer-to-peer help.

## Endpoints (zero setup)

| Surface | URL |
| --- | --- |
| REST API (OpenAPI 3.1) | https://everlist.network/openapi.json |
| MCP server (15 tools) | https://everlist.network/mcp |
| Agent explainer | https://everlist.network/agents |
| Payment discovery (x402) | https://everlist.network/.well-known/x402.json |
| UCP profile | https://everlist.network/.well-known/ucp |

Read `/.well-known/agent-hub.json` first: it declares payment mode, fees,
identity requirements, and the endpoint map. Terms are declared, never hidden.

## The booking flow

1. **Search**: `GET /search?q=...` (free text, optional `vertical`, `from`/`to`
   dates, price bounds). Verticals: events, food, services, jobs, classes, p2p.
2. **Inspect**: `GET /listings/{id}` - date, place, price, capacity left,
   and the listing's escrow terms.
3. **Terms echo**: the booking must echo the listing's `payment_terms` hash
   (booking = agreement to exactly those terms).
4. **Book**: `POST /book` with a hub token in the `X-Hub-Token` header
   (header-only auth; get one via `POST /accounts/signup` + `/accounts/login`,
   keypair stays client-side; `human_verified: true` is the interim credential).
   The booking id is returned with its escrow state (`HELD`, `WAIVED`, `DIRECT`).
5. **Settle**: wallet rail pays per call via **x402** on the deployed network
   (testnet today - say testnet when you say money); the hosted checkout path
   (`/checkout?sid=...`) handles card-shaped flows for free listings now.
6. **Verify**: escrow state is publicly checkable at
   `https://everlist.network/verify?contract=...&escrow=...` - no wallet needed.

## Laws you never break

- **Report rail labels verbatim** (`demo`, `wallet-testnet`, `provider-pending`).
  If it says testnet, say testnet. Never embellish payment reality.
- **Checkout never moves money in-conversation.** The hosted page completes
  booking and payment; the escrow state is displayed there.
- **Never claim a booking that did not happen.** A booking exists only when
  the hub returned one (id + escrow state).
- **Escrow is the promise:** funds are held until the organizer confirms the
  service happened, with a permissionless timeout refund if they never do.
  After the claim deadline the booking auto-releases to the organizer.

## Self-hosting

The hub is a self-hostable Python service (public repo:
github.com/everlist-hq/everlist-open-core). Run your own instance; the same
contract applies.
