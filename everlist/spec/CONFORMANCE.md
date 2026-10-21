# Getting Conformant — EverList API v1

How to prove your hub speaks the EverList API, and what you get for it.
Governance: `docs/api-standard-governance.md` (private docs repo). Spec:
[`everlist-api-v1.md`](everlist-api-v1.md) (generated, normative).

## Quick start

Run the conformance checker against your running hub:

```
python check_hub.py https://your-hub.example.com
```

Exit codes: `0` pass, `1` non-conformant, `2` unreachable.

## What is checked

| Check | Invariant |
| --- | --- |
| C1 | Manifest declares fee policy + public ledger endpoint |
| C2 | Every booking ledger entry: `amount == hub_fee + owner_payout` (within rounding tolerance) |
| C3 | Declared fee consistent: `hub_fee == round(amount * pct/100, 2)` within documented refund tolerance |
| C4 | Escrow states are exactly `HELD` / `RELEASED` / `REFUNDED` / `WAIVED`, reported as a state breakdown; `WAIVED` only at amount 0 |
| C5 | Ledger totals match recomputation from raw entries |
| C6 | Hubs advertising accounts must serve the SPEC 12a auth-challenge contract; signed registry documents verify as Ed25519 over the canonical payload |

Honesty note (from the checker itself): conformance proves **self-reported
consistency**, not fairness. That is what the escrow rails are for.

## Verdicts

| Verdict | Meaning | Exit |
| --- | --- | --- |
| `CONFORMANT` | All checks pass | 0 |
| `NON-CONFORMANT` | Any inconsistency found | 1 |
| `INSUFFICIENT-EVIDENCE` | Reachable but nothing verifiable yet (empty ledger, missing declarations) — an honest zero state | 0 |
| `UNREACHABLE` | Hub/registry/ledger not contactable — a dark trust anchor must never look green | 2 |

## Tiers

| Tier | Requirement | Gets |
| --- | --- | --- |
| Listed | Reachable, `/openapi.json` parses, discovery works | Registry entry |
| Conformant | Full checker pass against the declared spec version | Default-search inclusion, agent bootstrap |
| Verified ("EverList Compatible") | Conformant + ownership proof + operator in good standing | Badge, verified tier, canonical-URL trust |

Badge usage is a **trademark** matter, not a license: the Apache-2.0 code license
does not grant the right to market a hub as "EverList Compatible". Verified status
is granted (and revocable) by EverList; delisting is the enforcement for contract
violations.

## Registry document verification

```
python check_hub.py --registry <registry_url> [--expect-hub <hub_url>] [--pubkey <pinned_hex>]
```

`--pubkey` pins the registry signing key out-of-band; a mismatch is
NON-CONFORMANT by definition.
