# EverList Midnight Contracts (Compact)

Escrow and credential contracts for the EverList marketplace, written in
Midnight's Compact language. These are the contracts behind EverList's
escrow-backed bookings: payment is provably HELD in a smart contract before
the human starts work, released only on confirmation, refund or timeout.

## Contents

| Path | What it is |
| --- | --- |
| `src/escrow.compact` | Escrow contract: create (funded, exact-value shielded coin), release, refund, timeout refund, auto-release, mutual refund |
| `src/credential.compact` | ZK personhood credential: issue / proveHolder / revoke on commitments (one-human-one-account) |
| `managed/`, `managed-credential/` | Compiled artifacts produced by `compactc` 0.34.0 (LFDT-Minokawa/compact) incl. ZK prover/verifier keys and ZKIR |
| `test/` | Offline state-machine tests running the REAL compiled circuits against a simulated ledger (`@midnight-ntwrk/compact-runtime`) — no network, no proof server |

## How to test (offline, no network)

```bash
cd midnight-contract
npm ci                       # compact-runtime + onchain-runtime-v4
npx tsx --test test/escrow.test.ts       # escrow state machine (funded flows)
npx tsx --test test/credential.test.ts   # credential lifecycle
```

All circuits run against the compiled artifacts in `managed*/` via a simulated
ledger — the same tests gate EverList's CI (`make test` in the hub repo).

## Design notes

- Escrow holds an exact-value shielded coin at creation (funded escrow, M3):
  release/refund/timeout spend to payout keys fixed at creation, so even the
  permissionless timeout cannot redirect funds.
- Parties are persistent commitments (hashes of secrets), never addresses.
- No admin key, no upgrade path: the contract is immutable by design.

## License

Contract sources are pre-existing EverList M1-M17 work (MIT, see `../LICENSE`).
Wave-2 additions are Apache-2.0 — see `../NOTICE`.
