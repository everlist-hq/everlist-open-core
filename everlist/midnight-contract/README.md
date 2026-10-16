# EverList Midnight Contracts (Compact)

Escrow and credential contracts for the EverList marketplace, written in
Midnight's Compact language. These are the contracts behind EverList's
escrow-backed bookings: payment is provably HELD in a smart contract before
the human starts work, released only on confirmation, refund or timeout.

Live marketplace: [everlist.network](https://everlist.network)

## Contents

| Path | What it is |
| --- | --- |
| `src/escrow.compact` | Escrow contract: create (funded, exact-value shielded coin), release, refund, timeout refund, auto-release, mutual refund |
| `src/credential.compact` | ZK personhood credential: issue / proveHolder / revoke on commitments (one-human-one-account) |
| `managed/`, `managed-credential/` | Compiled artifacts produced by `compactc` 0.34.0 (LFDT-Minokawa/compact) incl. ZK prover/verifier keys and ZKIR |
| `test/` | Offline state-machine tests running the REAL compiled circuits against a simulated ledger (`@midnight-ntwrk/compact-runtime`) — no network, no proof server |
| `circuit-costs-20260913.json` | Recorded per-circuit cost matrix from the native proof-server run (2026-09-13); replayed by the hub's `tools/cost_matrix.py` |

## How to test (offline, no network, ~10s)

```bash
cd midnight-contract
npm ci                       # compact-runtime + onchain-runtime-v4
npx tsx --test test/escrow.test.ts       # escrow state machine: 40/40
npx tsx --test test/credential.test.ts   # credential lifecycle: 16/16
```

The circuits executed by these tests are the same compiled artifacts in
`managed*/` that the hub's M-series battery exercises (via recorded fixtures
in `test_m5`–`test_m10`), and the hub's full gate (`make test`) runs green on
every ship.

## Privacy audit: found and fixed (2026-10-16)

Both contracts were scanned with [Tell](https://github.com/RohanGlitched/tell)
(the Compact privacy scanner from the Midnight Buildathon) against the exact
toolchain (`compactc` 0.34.0, language 0.26):

| Contract | Before | Finding | After fix |
| --- | --- | --- | --- |
| `credential.compact` | Grade A | — | Grade A (clean) |
| `escrow.compact` | **Grade C** | 1 medium: one commitment tag per holder meant all of an organizer's escrows were publicly linkable — identifying one booking identified all of them | **Grade A — 0 findings** |

**The fix (Tell's own suggested remediation):** organizer commitments are now
bound to the `bookingRef` — a per-booking tag instead of a per-holder tag.
All four authorization call sites (`createEscrow`, `releaseEscrow`,
`refundEscrow`, `mutualRefund`) were updated, the contract was recompiled with
the pinned toolchain, and a regression test now asserts that the same secret
on two different bookings yields two unlinkable tags
(`test/escrow.test.ts`, "cross-escrow linkability, Tell 2026-10-16").

## Evidence & receipts (what is real today)

| Claim | Evidence |
| --- | --- |
| Compiled circuits execute the full escrow lifecycle | 40/40 + 16/16 offline tests against `managed*/` artifacts (command above, ~10s) |
| Per-circuit costs measured, not estimated | `circuit-costs-20260913.json` recorded from the native proof server; replay: `tools/cost_matrix.py` in the hub repo |
| Hub integration tested end-to-end | hub gate `make test` ALL PASSED (2,000+ checks incl. M5 escrow_ref, M6 indexer client, M7 escrow mirror sync, M8 chain-booking E2E, M9 payout keys, M10 secret hygiene) |
| Live marketplace with real booking flows | [everlist.network](https://everlist.network) — judge path below |
| Testnet wallet funded | Midnight Preprod faucet: 5,000 tNIGHT received at block 2652879 (2026-09-21) |

## Honest limits (read before trusting)

- **The contract is not yet deployed on-chain.** Deployment is blocked by an
  upstream toolchain issue (SDK estimate hang during the M18 deploy attempt,
  documented in the repo worklog), not by contract logic. Until deployment
  lands, the live hub's escrow accounting runs in its honestly-labeled demo
  rail (manifest declares the mode), while the contract logic itself is proven
  by the offline circuit tests above.
- **No fabricated txids.** On-chain transaction receipts will be published
  here after the funded deploy succeeds. The circuit-cost half of the cost
  matrix is real and recorded; per-transaction DUST costs land with the same
  deploy.
- **The hub operator sees what it must to run a marketplace** (pseudonymous
  booking records, listing content) — the hub's own data policy is documented
  in the hub repo's `PRIVACY.md`. What Midnight protects here is the payment
  layer: amounts, parties and note contents are shielded; public ledger
  entries are commitment tags only, and since the Tell fix those tags are
  per-booking, not per-person.
- **No Blockfrost/indexer dependency.** After the Preprod indexer change the
  hub has no third-party indexer dependency; chain-state reads are dual-source
  and fail closed (no proof, no claim).

## 5-minute judge path (no wallet, no setup)

Against the live hub:

```bash
# 1. discover
curl -s https://everlist.network/.well-known/agent-hub.json
# 2. browse listings (55+ live)
curl -s https://everlist.network/listings | head -40
# 3. get an agent token (no wallet; interim open bootstrap)
curl -s -X POST https://everlist.network/access \
   -H 'Content-Type: application/json' \
   -d '{"agent":"judge-demo","acts":["book"]}'
# 4. book a listing -> escrow HELD (paid) or WAIVED (free)
curl -s -X POST https://everlist.network/book \
   -H 'Content-Type: application/json' -H "X-Hub-Token: $TOKEN" \
   -d '{"listing_id":"<id-from-step-2>","attendee":"Judge","human_verified":true}'
# 5. cancel with the one-time cancel_token from step 4 -> full refund
curl -s -X POST https://everlist.network/book/<booking-id>/cancel \
   -H "X-Hub-Token: $CANCEL_TOKEN"
# 6. verify the public ledger + sponsorship pool transparency
curl -s https://everlist.network/ledger | head -20
curl -s https://everlist.network/sponsorship/stats
```

Every step above was verified end-to-end against production on 2026-10-16,
including both rails: a free booking (`WAIVED`) and a paid booking (`HELD` ->
cancel -> `REFUNDED`).

## Design notes

- Escrow holds an exact-value shielded coin at creation (funded escrow, M3):
  release/refund/timeout spend to payout keys fixed at creation, so even the
  permissionless timeout cannot redirect funds.
- Parties are persistent commitments (hashes of secrets), never addresses —
  and since the Tell fix, per-booking commitments: two bookings by the same
  organizer cannot be linked from public data.
- No admin key, no upgrade path: the contract is immutable by design.

## License

Contract sources are pre-existing EverList M1-M17 work (MIT, see `../LICENSE`).
Wave-2 additions are Apache-2.0 — see `../NOTICE`.
