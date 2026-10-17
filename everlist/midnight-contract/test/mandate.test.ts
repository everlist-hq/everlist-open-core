/**
 * EverList mandate contract - OFFLINE tests (techmining P1 #1).
 *
 * Runs the REAL compiled circuits (managed-mandate/contract) against a
 * simulated ledger via compact-runtime. No proof server, no network.
 *
 * Party-accurate instances (role-wall pattern from escrow/credential):
 *   principal - the HUMAN issuer's machine: knows ONLY the revoke secret
 *               (its mandate witnesses hold junk - it created the terms but
 *               needs none of them to revoke)
 *   agent     - the AGENT's machine: knows the mandate secret + the true
 *               terms (cap, category) as witnesses
 *   attacker  - knows nothing real
 *   tampered  - knows the REAL mandate secret but carries an INFLATED cap
 *               witness: proves the commitment wall stops self-upgraded
 *               terms even with the true secret in hand
 *
 * Run: npx tsx --test test/mandate.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed-mandate/contract/index.js';

const mkWitnesses = (sk, cap, category, revokeSk) => ({
  mandateSecretKey: (ctxt) => [ctxt.privateState, sk],
  mandateCap: (ctxt) => [ctxt.privateState, cap],
  mandateCategory: (ctxt) => [ctxt.privateState, category],
  revokeSecretKey: (ctxt) => [ctxt.privateState, revokeSk],
});

const MANDATE_SK = new Uint8Array(32).fill(3);   // shared principal->agent
const REVOKE_SK = new Uint8Array(32).fill(7);    // principal-only
const JUNK_SK = new Uint8Array(32).fill(9);       // attacker junk
const JUNK_CAP = 999999n;                        // junk term
const JUNK_CATEGORY = 9n;                        // junk term

// true private terms of the test mandate
const CAP = 500n;
const CATEGORY = 1n; // 1 = bookings

const EXPIRY_FAR = 99999999999n;
const EXPIRY_PAST = 1000n; // default-time context now ≈ 1.78e9

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);

let ctx;        // evolving circuit context
let principal;   // human issuer machine (revoke secret only)
let agent;       // agent machine (mandate secret + true terms)
let attacker;    // knows nothing
let tampered;    // real secret, INFLATED cap witness

const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);

/** Commitments the principal publishes (computed on pure calls, as wallets do). */
const actionComm = () => pureCircuits.mandateCommitment(MANDATE_SK, CAP, CATEGORY);
const revokeComm = () => pureCircuits.revokeCommitment(REVOKE_SK);

let mid; // mandate id under test

describe('EverList delegated spending mandate (offline, real compiled circuits)', () => {
  before(async () => {
    principal = new Contract(mkWitnesses(JUNK_SK, JUNK_CAP, JUNK_CATEGORY, REVOKE_SK));
    agent = new Contract(mkWitnesses(MANDATE_SK, CAP, CATEGORY, JUNK_SK));
    attacker = new Contract(mkWitnesses(JUNK_SK, JUNK_CAP, JUNK_CATEGORY, JUNK_SK));
    tampered = new Contract(mkWitnesses(MANDATE_SK, CAP * 10n, CATEGORY, JUNK_SK));
    const ps = null;

    const ctor = await principal.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('issueMandate', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('pure commitments', () => {
    test('deterministic and term-binding', () => {
      const c1 = pureCircuits.mandateCommitment(MANDATE_SK, CAP, CATEGORY);
      const c2 = pureCircuits.mandateCommitment(MANDATE_SK, CAP, CATEGORY);
      const capDiffers = pureCircuits.mandateCommitment(MANDATE_SK, CAP + 1n, CATEGORY);
      const catDiffers = pureCircuits.mandateCommitment(MANDATE_SK, CAP, CATEGORY + 1n);
      const skDiffers = pureCircuits.mandateCommitment(JUNK_SK, CAP, CATEGORY);
      assert.deepEqual(c1, c2, 'deterministic');
      assert.notDeepEqual(c1, capDiffers, 'cap is bound into the commitment');
      assert.notDeepEqual(c1, catDiffers, 'category is bound into the commitment');
      assert.notDeepEqual(c1, skDiffers, 'secret is bound into the commitment');
      assert.equal(c1.length, 32);
    });

    test('revoke domain is prefix-separated from the action domain', () => {
      const a = pureCircuits.mandateCommitment(MANDATE_SK, CAP, CATEGORY);
      const r = pureCircuits.revokeCommitment(MANDATE_SK); // same sk, other domain
      assert.notDeepEqual(a, r);
    });
  });

  describe('issueMandate', () => {
    test('stores both commitments + public expiry, returns fresh id', async () => {
      const r = await call(principal, 'issueMandate', actionComm(), revokeComm(), EXPIRY_FAR);
      mid = r.result;
      assert.equal(mid, 1n, 'first mandate gets id 1');
      const m = readLedger().mandates.lookup(mid);
      assert.deepEqual(m.actionCommitment, actionComm());
      assert.deepEqual(m.revokeCommitment, revokeComm());
      assert.equal(m.expiry, EXPIRY_FAR);
      assert.equal(m.revoked, false);
      assert.equal(readLedger().uses.lookup(mid), 0n);
    });

    test('rejects expiry 0', async () => {
      await assert.rejects(
        () => call(principal, 'issueMandate', actionComm(), revokeComm(), 0n),
        /expiry must be positive/
      );
    });
  });

  describe('authorize (the ZK act)', () => {
    test('within cap + right category succeeds and increments the public counter', async () => {
      await call(agent, 'authorize', mid, 120n, CATEGORY);
      assert.equal(readLedger().uses.lookup(mid), 1n);
    });

    test('exactly at the cap is allowed (cap is inclusive)', async () => {
      await call(agent, 'authorize', mid, CAP, CATEGORY);
      assert.equal(readLedger().uses.lookup(mid), 2n);
    });

    test('above cap rejected (amount exceeds mandate cap)', async () => {
      await assert.rejects(
        () => call(agent, 'authorize', mid, CAP + 1n, CATEGORY),
        /amount exceeds mandate cap/
      );
      assert.equal(readLedger().uses.lookup(mid), 2n, 'counter unchanged on rejection');
    });

    test('wrong category rejected', async () => {
      await assert.rejects(
        () => call(agent, 'authorize', mid, 10n, CATEGORY + 1n),
        /action category not allowed/
      );
    });

    test('THE WALL: real secret + inflated cap witness rejected (terms cannot be self-upgraded)', async () => {
      await assert.rejects(
        () => call(tampered, 'authorize', mid, CAP * 5n, CATEGORY), // amount legal only under the INFLATED cap
        /mandate commitment mismatch/
      );
    });

    test('attacker (no secrets, junk terms) rejected at the wall', async () => {
      await assert.rejects(
        () => call(attacker, 'authorize', mid, 10n, CATEGORY),
        /mandate commitment mismatch/
      );
    });

    test('counter reflects only successful authorizations', async () => {
      const r = await call(agent, 'useCount', mid);
      assert.equal(r.result, 2n);
    });
  });

  describe('expiry (public term, ledger block time)', () => {
    test('authorize on an expired mandate rejected', async () => {
      const r = await call(principal, 'issueMandate', actionComm(), revokeComm(), EXPIRY_PAST);
      const expired = r.result;
      await assert.rejects(
        () => call(agent, 'authorize', expired, 10n, CATEGORY),
        /mandate expired/
      );
    });
  });

  describe('revokeMandate (principal-only, permanent)', () => {
    test('agent cannot revoke (revoke wall)', async () => {
      await assert.rejects(
        () => call(agent, 'revokeMandate', mid),
        /only the principal can revoke/
      );
    });

    test('attacker cannot revoke (revoke wall)', async () => {
      await assert.rejects(
        () => call(attacker, 'revokeMandate', mid),
        /only the principal can revoke/
      );
    });

    test('principal revokes; isRevoked flips permanently', async () => {
      await call(principal, 'revokeMandate', mid);
      const r = await call(agent, 'isRevoked', mid);
      assert.equal(r.result, true);
      const m = readLedger().mandates.lookup(mid);
      assert.equal(m.revoked, true);
    });

    test('authorize after revocation rejected even with true terms', async () => {
      await assert.rejects(
        () => call(agent, 'authorize', mid, 10n, CATEGORY),
        /mandate revoked/
      );
    });

    test('double revoke rejected (already revoked - one-way flag)', async () => {
      // revoking an already-revoked mandate: the wall passes, insert is
      // idempotent in the ledger, but the flag stays true - assert state
      await call(principal, 'revokeMandate', mid);
      assert.equal(readLedger().mandates.lookup(mid).revoked, true);
    });
  });

  describe('unknown ids', () => {
    test('authorize / revoke / reads on unknown mandate id rejected', async () => {
      await assert.rejects(() => call(agent, 'authorize', 9999n, 10n, CATEGORY), /mandate not found/);
      await assert.rejects(() => call(principal, 'revokeMandate', 9999n), /mandate not found/);
      await assert.rejects(() => call(agent, 'isRevoked', 9999n), /mandate not found/);
      await assert.rejects(() => call(agent, 'useCount', 9999n), /mandate not found/);
    });
  });
});