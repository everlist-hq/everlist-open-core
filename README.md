# EverList Open Core

> Open-core building blocks for agent-native booking: a commerce hub with escrow,
a signed partner registry, a conformance checker, an MCP face, and an SDK.
Maintained by the [EverList](https://everlist.network) team.

**Open core, curated network.** This repository contains the open parts of
EverList: the hub implementation (universal booking core with per-vertical
schemas), the registry service (signed partner index + open self-listing tier),
the conformance checker, the SDK, and the protocol spec. The main-site
aggregator UI and its polish are proprietary — that is the "open core"
licensing model, and it is stated plainly in every hub manifest
(`license_model` field).

## What's here

| Path | What |
| --- | --- |
| `everlist/` | The hub core: `app.py` (REST API, escrow accounting, ledger), `mcp.py` (MCP face), `wrapper.py` (uAgents/A2A face), `chatlib.py` (chat command layer), `sdk/`, `schemas/`, `SPEC.md`, and the full test battery (60+ suites) |
| `registry/` | The authoritative registry service: ownership-proof self-registration into the open tier, operator-gated promote/revoke into the **verified partner tier**, Ed25519-signed `registry.json` (partners only), and `check_hub.py` conformance checks |

## Quickstart

```bash
cd everlist
python3 -m venv venv
venv/bin/pip install -r requirements.txt
make test          # full gate: 60+ suites incl. A2A E2E + escrow chain

make up            # hub on :8802 + agent wrapper (testnet only)
```

The registry service runs standalone:

```bash
cd registry
../everlist/venv/bin/python registry.py   # :8810, set REG_ADMIN_TOKEN for partner ops
```

## The network model (honest version)

- The **hub technology is open (MIT)**. Anyone may run a hub, unaffiliated,
  without permission. You get no trust rails: no verified tier, no signature,
  no aggregator inclusion.
- The **EverList network is curated**. Appearing in the signed registry with
  `tier=verified` is a partnership, granted and revoked by the EverList
  operator — never self-service. Conformance (`check_hub.py`) + review are
  the entry ticket.
- Users and agents can still manually add unaffiliated hub URLs; they are
  simply not in the signed bootstrap document or default search.

## License

MIT — see [LICENSE](LICENSE). "EverList" and the verified badge are trademarks
of the EverList operator; usage by partners in good standing.