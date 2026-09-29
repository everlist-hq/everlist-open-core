/**
 * EverList credential contract - OFFLINE tests (M13 personhood issuer).
 *
 * Runs the REAL compiled circuits (managed-credential/contract) against a
 * simulated ledger via compact-runtime. No proof server, no network.
 *
 * Done-when (backlog M13): issue -> verify -> revoke -> verify-fails.
 *
 * Party-accurate instances (role-wall proof pattern from escrow tests):
 *   hub      - the pilot ISSUER machine: knows the issuer secret, NOT any
 *              holder secret (its holder witness holds attacker junk, so any
 *              accidental holder-side success would be caught)
 *   holder   - the holder's wallet: knows ONLY the holder secret (its issuer
 *              witness returns the holder secret - wrong by construction)
 *   attacker - knows neither secret
 *
 * Run: npx tsx --test test/credential.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed-credential/contract/index.js';

const mkWitnesses = (issuerSk, holderSk) => ({
  issuerSecretKey: (ctxt) => [ctxt.privateState, issuerSk],
  holderSecretKey: (ctxt) => [ctxt.privateState, holderSk],
});

const ISSUER_SK = new Uint8Array(32).fill(1);   // hub's issuer secret
const HOLDER_SK = new Uint8Array(32).fill(2);   // holder's wallet secret
const ATTACKER_SK = new Uint8Array(32).fill(9); // attacker knows nothing real

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64); // dummy CoinPublicKey (string form, context ctor)

let ctx;      // evolving circuit context: carries the mutated ledger
let hub;      // issuer machine
let holder;   // holder's machine (no issuer secret)
let attacker; // attacker machine

/** Call an impure circuit on the shared thread; adopt the returned context. */
const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

/** Current ledger view from the evolving context. */
const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);

/** The holder commitment the hub admits (computed publicly from... nothing -
 *  the hub NEVER learns HOLDER_SK; the holder computes its own commitment and
 *  submits it. In tests we compute it on a pure call, like a wallet would). */
const holderComm = () => pureCircuits.holderCommitment(HOLDER_SK);

let credId; // issued credential id used across the revoke legs

describe('EverList personhood credential (offline, real compiled circuits)', () => {
  before(async () => {
    hub = new Contract(mkWitnesses(ISSUER_SK, ATTACKER_SK));
    holder = new Contract(mkWitnesses(HOLDER_SK, HOLDER_SK));
    attacker = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK));
    const ps = null; // circuits declare no private state

    // deploy-time constructor: initializes Counter/Map cells in the ledger
    const ctor = await hub.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('initializeIssuer', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('pure commitments', () => {
    test('P1: commitments deterministic + prefix-separated', () => {
      const i1 = pureCircuits.issuerCommitment(ISSUER_SK);
      const i2 = pureCircuits.issuerCommitment(ISSUER_SK);
      const h1 = pureCircuits.holderCommitment(ISSUER_SK); // same sk, other domain
      assert.deepEqual(i1, i2);
      assert.notDeepEqual(i1, h1, 'issuer/holder domains must differ');
    });
  });

  describe('issuer lifecycle', () => {
    test('P2: issuing BEFORE initialization rejected', async () => {
      await assert.rejects(() => call(hub, 'issueCredential', holderComm()),
        /issuer not initialized/);
    });

    test('P3: first caller becomes THE issuer', async () => {
      await call(hub, 'initializeIssuer');
      assert.ok(readLedger().issuer.member(0n), 'issuer commitment stored at key 0');
    });

    test('P4: issuer takeover impossible (second init rejected forever)', async () => {
      await assert.rejects(() => call(attacker, 'initializeIssuer'),
        /issuer already initialized/);
      await assert.rejects(() => call(hub, 'initializeIssuer'),
        /issuer already initialized/);
    });

    test('P5: issuer admits a holder -> fresh credential id', async () => {
      const r = await call(hub, 'issueCredential', holderComm());
      credId = r.result;
      assert.equal(credId, 1n, 'first credential gets id 1');
      const led = readLedger();
      assert.ok(led.holders.member(credId));
      assert.deepEqual(led.holders.lookup(credId), holderComm());
      assert.equal(led.revoked.lookup(credId), false);
    });

    test('P6: holder machine CANNOT admit (issuer wall)', async () => {
      await assert.rejects(() => call(holder, 'issueCredential', holderComm()),
        /only the issuer can admit holders/);
    });

    test('P7: attacker CANNOT admit (issuer wall)', async () => {
      await assert.rejects(() => call(attacker, 'issueCredential', holderComm()),
        /only the issuer can admit holders/);
    });
  });

  describe('ZK sign-in (proveHolder) - the M14 surface', () => {
    test('P8: honest holder sign-in SUCCEEDS (proof of admitted commitment)', async () => {
      await call(holder, 'proveHolder', credId);
    });

    test('P9: wrong secret rejected (attacker cannot sign in as holder)', async () => {
      await assert.rejects(() => call(attacker, 'proveHolder', credId),
        /holder commitment mismatch/);
    });

    test('P10: unknown credential id rejected', async () => {
      await assert.rejects(() => call(holder, 'proveHolder', 999n),
        /credential not found/);
    });

    test('P11: isRevoked false while active (query circuit)', async () => {
      const r = await holder.impureCircuits.isRevoked(ctx, credId);
      assert.equal(r.result, false);
    });
  });

  describe('revocation registry', () => {
    test('P12: attacker CANNOT revoke', async () => {
      await assert.rejects(() => call(attacker, 'revokeCredential', credId),
        /only the issuer can revoke/);
    });

    test('P13: revoking an unknown credential rejected', async () => {
      await assert.rejects(() => call(hub, 'revokeCredential', 999n),
        /credential not found/);
    });

    test('P14: issuer revokes the credential', async () => {
      await call(hub, 'revokeCredential', credId);
      assert.equal(readLedger().revoked.lookup(credId), true);
    });

    test('P15: VERIFY-FAILS after revocation (done-when)', async () => {
      await assert.rejects(() => call(holder, 'proveHolder', credId),
        /credential revoked/);
    });

    test('P16: revocation is one-way (re-revoke still fine, sign-in still dead)', async () => {
      await call(hub, 'revokeCredential', credId); // idempotent revoke allowed
      await assert.rejects(() => call(holder, 'proveHolder', credId),
        /credential revoked/);
    });
  });
});
