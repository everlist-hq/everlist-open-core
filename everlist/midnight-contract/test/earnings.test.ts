/**
 * EverList organizer earnings floor - OFFLINE tests (W3.4, 2026-10-20).
 *
 * Runs the REAL compiled circuits (managed-earnings/contract) against a
 * simulated ledger via compact-runtime. No proof server, no network.
 *
 * Party-accurate instances (role-wall pattern):
 *   hub        - the earnings RECORDER: knows the issuer secret, NOT any
 *               organizer secret (its organizer witness holds attacker junk)
 *   organizer  - the organizer's machine: knows ONLY their own secret
 *   attacker   - knows nothing real
 *
 * Run: npx tsx --test test/earnings.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed-earnings/contract/index.js';

const mkWitnesses = (orgSk, issuerSk) => ({
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
  earningsIssuerSecretKey: (ctxt) => [ctxt.privateState, issuerSk],
});

const HUB_SK = new Uint8Array(32).fill(1);      // hub issuer secret
const ORG_SK = new Uint8Array(32).fill(2);       // organizer #1 secret
const ORG2_SK = new Uint8Array(32).fill(5);      // organizer #2 secret
const ATTACKER_SK = new Uint8Array(32).fill(9);  // attacker junk

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);

let ctx;      // evolving circuit context
let hub;      // issuer machine (no organizer secret)
let org;      // organizer machine (only their own secret)
let attacker; // knows nothing

const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);

/** The organizer's public earnings pseudonym commitment (computable by anyone). */
const orgComm = () => pureCircuits.organizerEarningsCommitment(ORG_SK);
const org2Comm = () => pureCircuits.organizerEarningsCommitment(ORG2_SK);

/** Record an earnings event like the hub would after an on-chain RELEASED check. */
const record = async (comm, volume) =>
  call(hub, 'recordEarnings', comm, volume);

describe('EverList organizer earnings floor (offline, real compiled circuits)', () => {
  before(async () => {
    hub = new Contract(mkWitnesses(ATTACKER_SK, HUB_SK));
    org = new Contract(mkWitnesses(ORG_SK, ATTACKER_SK));
    attacker = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK));
    const ps = null;

    const ctor = await hub.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('initializeEarningsIssuer', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('commitment hygiene', () => {
    test('deterministic: same secret -> same commitment', () => {
      assert.deepEqual(orgComm(), pureCircuits.organizerEarningsCommitment(ORG_SK));
    });

    test('DOMAIN SEPARATION: organizer vs issuer prefixes differ', () => {
      const c1 = pureCircuits.organizerEarningsCommitment(ORG_SK);
      const c2 = pureCircuits.earningsIssuerCommitment(ORG_SK);
      assert.notDeepEqual(c1, c2);
    });

    test('different secrets -> different commitments', () => {
      assert.notDeepEqual(orgComm(), org2Comm());
    });
  });

  describe('issuer lifecycle', () => {
    test('recording before initialization rejected', async () => {
      await assert.rejects(
        () => record(orgComm(), 100n),
        /issuer not initialized/
      );
    });

    test('first caller becomes THE earnings recorder', async () => {
      await call(hub, 'initializeEarningsIssuer');
      assert.ok(readLedger().earningsIssuer.member(0n));
    });

    test('issuer takeover impossible (second init rejected forever)', async () => {
      await assert.rejects(() => call(attacker, 'initializeEarningsIssuer'), /issuer already initialized/);
      await assert.rejects(() => call(hub, 'initializeEarningsIssuer'), /issuer already initialized/);
    });
  });

  describe('registerOrganizer (witness-walled)', () => {
    test('secret holder registers their pseudonym with zero totals', async () => {
      await call(org, 'registerOrganizer', orgComm());
      const led = readLedger();
      assert.ok(led.organizerEarnings.member(orgComm()));
      const earned = led.organizerEarnings.lookup(orgComm());
      assert.equal(earned.settledCount, 0n);
      assert.equal(earned.totalVolume, 0n);
    });

    test('FRONT-RUNNING WALL: attacker cannot register someone else\'s commitment', async () => {
      await assert.rejects(
        () => call(attacker, 'registerOrganizer', org2Comm()),
        /only the secret holder can register this commitment/
      );
    });

    test('double registration rejected', async () => {
      await assert.rejects(
        () => call(org, 'registerOrganizer', orgComm()),
        /organizer already registered/
      );
    });
  });

  describe('recordEarnings (issuer-walled)', () => {
    test('ISSUER WALL: organizer cannot record their own earnings', async () => {
      await assert.rejects(
        () => call(org, 'recordEarnings', orgComm(), 100n),
        /only the issuer can record earnings/
      );
    });

    test('ISSUER WALL: attacker cannot record earnings', async () => {
      await assert.rejects(
        () => call(attacker, 'recordEarnings', orgComm(), 100n),
        /only the issuer can record earnings/
      );
    });

    test('unregistered pseudonym rejected', async () => {
      await assert.rejects(
        () => record(org2Comm(), 100n),
        /organizer not registered/
      );
    });

    test('zero volume rejected', async () => {
      await assert.rejects(() => record(orgComm(), 0n), /volume must be positive/);
    });

    test('hub records earnings: count and volume accumulate', async () => {
      await record(orgComm(), 120n);  // released booking #1
      await record(orgComm(), 30n);   // released booking #2
      await record(orgComm(), 50n);   // released booking #3
      const earned = readLedger().organizerEarnings.lookup(orgComm());
      assert.equal(earned.settledCount, 3n);
      assert.equal(earned.totalVolume, 200n);
      assert.equal(readLedger().earningsCount, 3n);
    });
  });

  describe('proveEarningsFloor (the ZK act)', () => {
    test('meets both thresholds: succeeds (3 settlements, 200 volume)', async () => {
      await call(org, 'proveEarningsFloor', 2n, 150n);
    });

    test('EXACT BOUNDARY: floor equal to actuals passes (>=, not >)', async () => {
      await call(org, 'proveEarningsFloor', 3n, 200n);
    });

    test('insufficient settlements rejected', async () => {
      await assert.rejects(
        () => call(org, 'proveEarningsFloor', 4n, 200n),
        /insufficient settlements/
      );
    });

    test('insufficient volume rejected (X+1 must fail)', async () => {
      await assert.rejects(
        () => call(org, 'proveEarningsFloor', 3n, 201n),
        /insufficient volume/
      );
    });

    test('unregistered organizer rejected', async () => {
      await assert.rejects(
        () => call(attacker, 'proveEarningsFloor', 1n, 1n),
        /organizer not registered/
      );
    });

    test('VACUOUS THRESHOLD: minSettlements=0 rejected by design', async () => {
      await assert.rejects(
        () => call(org, 'proveEarningsFloor', 0n, 0n),
        /must demand at least one settlement/
      );
    });

    test('NO SECRET DISCLOSED: floor proof returns no totals and writes no ledger state', async () => {
      const before = readLedger();
      const r = await call(org, 'proveEarningsFloor', 1n, 1n);
      assert.ok(r.result == null || (Array.isArray(r.result) && r.result.length === 0)); // [] circuit: pass/fail only, no totals ever returned
      const after = readLedger();
      assert.equal(after.earningsCount, before.earningsCount); // no side effect
      // totals unchanged, no new pseudonym entries
      assert.deepEqual(
        after.organizerEarnings.lookup(orgComm()),
        before.organizerEarnings.lookup(orgComm())
      );
    });

    test('organizer #2 (unregistered) is isolated from organizer #1', async () => {
      await assert.rejects(
        () => call(attacker, 'proveEarningsFloor', 99n, 99n),
        /organizer not registered/
      );
    });
  });

  describe('getEarnings (public read)', () => {
    test('returns the pseudonym\'s totals', async () => {
      const r = await call(org, 'getEarnings', orgComm());
      assert.equal(r.result.settledCount, 3n);
      assert.equal(r.result.totalVolume, 200n);
    });

    test('unknown pseudonym rejected', async () => {
      await assert.rejects(
        () => call(org, 'getEarnings', org2Comm()),
        /organizer not registered/
      );
    });
  });
});
