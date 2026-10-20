/**
 * EverList escrow — INDISTINGUISHABILITY tests (techmining idea #6,
 * AVAL-style, 2026-10-17).
 *
 * Privacy claim under test: the PUBLIC ledger cannot distinguish
 * "one loyal customer booking twice" from "two strangers booking once
 * each". Party identity lives only in per-booking commitments
 * (persistentHash of a witness secret bound to the bookingRef — W2 Tell
 * fix); amounts and terms are public BY DESIGN (verifiable stake).
 *
 * Two worlds are built with identical public inputs (same amounts, same
 * booking refs, same deadlines, same payout keys, same deposit coins):
 *   World A (loyal):   agent SK_A books twice
 *   World B (strangers): SK_A books once, SK_B books once
 * Structural: the two full public ledger snapshots must differ in EXACTLY
 *   one field — escrow #2's agentCommitment.
 * Statistical: same-agent commitment pairs are indistinguishable from
 *   two-agent pairs (PRF behaviour of persistentHash): Hamming distances
 *   ~128 bits and byte-collision rates ~1/256 in both classes.
 *
 * Run: npx tsx --test test/indistinguishability.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed/contract/index.js';

const b32 = (s: string) => {
  const a = new Uint8Array(32);
  a.set(new TextEncoder().encode(s).slice(0, 32));
  return a;
};

const mkWitnesses = (agentSk: Uint8Array, orgSk: Uint8Array) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
  arbiterSecretKey: (ctxt) => [ctxt.privateState, new Uint8Array(32).fill(5)], // W3.1 (unused by these flows)
});

const AGENT_SK = new Uint8Array(32).fill(1);   // agent #1 (both worlds)
const AGENT2_SK = new Uint8Array(32).fill(5);  // agent #2 (World B only)
const ORG_SK = new Uint8Array(32).fill(2);

const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };

const DEADLINE_FAR = 99999999999n;
const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);
const COLOR = b32('tDUST');

const hex = (b: Uint8Array) => Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('');

/** Hamming distance in bits between two 32-byte values. */
const hammingBits = (a: Uint8Array, b: Uint8Array) => {
  let d = 0;
  for (let i = 0; i < a.length; i++) {
    let x = a[i] ^ b[i];
    while (x) { d += x & 1; x >>= 1; }
  }
  return d;
};

/** Count equal byte positions between two 32-byte values. */
const equalBytes = (a: Uint8Array, b: Uint8Array) => {
  let d = 0;
  for (let i = 0; i < a.length; i++) if (a[i] === b[i]) d++;
  return d;
};

/**
 * Build one independent world (own ledger thread). `agent2Sk` is the secret
 * behind the SECOND escrow's agent witness — same as agent #1 in the loyal
 * world, different in the strangers world. Everything else is identical.
 */
const buildWorld = async (agent2Sk: Uint8Array) => {
  const first = new Contract(mkWitnesses(AGENT_SK, ORG_SK));
  const second = new Contract(mkWitnesses(agent2Sk, ORG_SK));
  const ps = null;
  const ctor = await first.initialState(createConstructorContext(ps, COIN_PK));
  let ctx = createCircuitContext('createEscrow', ADDRESS, COIN_PK, ctor.currentContractState, ps);

  const call = async (instance, name, ...args) => {
    const r = await instance.impureCircuits[name](ctx, ...args);
    ctx = r.context;
    return r;
  };
  const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);
  const zswapOutputs = () => ctx.callContext.currentZswapLocalState.outputs;

  let coinCtr = 0; // per-world deterministic coin sequence
  const newEscrow = async (who: any, amount: bigint, ref: Uint8Array) => {
    const orgComm = pureCircuits.organizerCommitment(ORG_SK, ref);
    const nonce = new Uint8Array(32);
    nonce.set([++coinCtr & 0xff]);
    const deposit = { nonce, color: COLOR, value: amount };
    const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
    await call(who, 'createEscrow', amount, orgComm, ref, DEADLINE_FAR, DEADLINE_FAR + 1n, deposit, AGENT_PK, ORG_PK);
    return { id: readLedger().escrows.size(), spend: { nonce, color: COLOR, value: amount, mt_index: mt } };
  };

  return { first, second, newEscrow, readLedger, zswapOutputs };
};

/** Serialize the full public ledger state (an observer's complete view). */
const snapshot = (l: any) => {
  const out: any = { nextId: l.nextId, escrows: {}, agentPks: {}, organizerPks: {} };
  for (let id = 1n; id <= l.nextId; id++) {
    const e = l.escrows.lookup(id);
    out.escrows[String(id)] = {
      amount: e.amount,
      agentCommitment: hex(e.agentCommitment),
      organizerCommitment: hex(e.organizerCommitment),
      state: e.state,
      bookingRef: hex(e.bookingRef),
      deadline: e.deadline,
      claimDeadline: e.claimDeadline,
      coinNonce: hex(e.coinNonce),
      coinColor: hex(e.coinColor),
    };
    out.agentPks[String(id)] = hex(l.agentPks.lookup(id).bytes);
    out.organizerPks[String(id)] = hex(l.organizerPks.lookup(id).bytes);
  }
  return out;
};

/** Paths at which two snapshots differ (flat key paths). */
const diffPaths = (a: any, b: any, prefix = '') => {
  const paths: string[] = [];
  for (const k of new Set([...Object.keys(a), ...Object.keys(b)])) {
    const p = prefix ? `${prefix}.${k}` : k;
    const va = a[k], vb = b[k];
    if (va === undefined || vb === undefined) paths.push(p);
    else if (typeof va === 'object' && typeof vb === 'object') paths.push(...diffPaths(va, vb, p));
    else if (va !== vb) paths.push(p);
  }
  return paths;
};

describe('EverList escrow indistinguishability (AVAL-style, techmining #6)', () => {
  let worldA: Awaited<ReturnType<typeof buildWorld>>;
  let worldB: Awaited<ReturnType<typeof buildWorld>>;

  before(async () => {
    // World A (loyal): SK_A books both a €15 and a €1500 event
    worldA = await buildWorld(AGENT_SK);
    await worldA.newEscrow(worldA.first, 15n, b32('ind-evt-a1'));
    await worldA.newEscrow(worldA.first, 1500n, b32('ind-evt-a2'));

    // World B (strangers): SK_A books the €15 event, SK_B books the €1500 one
    worldB = await buildWorld(AGENT2_SK);
    await worldB.newEscrow(worldB.first, 15n, b32('ind-evt-a1'));
    await worldB.newEscrow(worldB.second, 1500n, b32('ind-evt-a2'));
  });

  describe('structural: the public ledger cannot tell loyal from strangers', () => {
    test('the two public ledger snapshots differ in EXACTLY one field: escrow #2 agentCommitment', () => {
      const snapA = snapshot(worldA.readLedger());
      const snapB = snapshot(worldB.readLedger());
      const diffs = diffPaths(snapA, snapB);
      assert.deepEqual(
        diffs,
        ['escrows.2.agentCommitment'],
        `expected exactly one differing field, got: ${JSON.stringify(diffs)}`
      );
    });

    test('the differing commitment is not the loyal agent\'s tag (per-booking binding holds)', () => {
      const e2A = worldA.readLedger().escrows.lookup(2n);
      const e2B = worldB.readLedger().escrows.lookup(2n);
      const loyalTag = pureCircuits.agentCommitment(AGENT_SK, b32('ind-evt-a2'));
      const strangerTag = pureCircuits.agentCommitment(AGENT2_SK, b32('ind-evt-a2'));
      assert.deepEqual(e2A.agentCommitment, loyalTag, 'world A shows the loyal agent tag');
      assert.deepEqual(e2B.agentCommitment, strangerTag, 'world B shows the stranger tag');
    });

    test('chain-observer money view (zswap outputs) is IDENTICAL in both worlds', () => {
      assert.deepEqual(worldA.zswapOutputs(), worldB.zswapOutputs());
    });
  });

  describe('PRF behaviour: same-agent vs two-agent commitment pairs', () => {
    const N = 256;

    const mkRef = (tag: string, i: number) => {
      const r = new Uint8Array(32);
      r.set(new TextEncoder().encode(`${tag}-${i}`).slice(0, 32));
      return r;
    };

    test('determinism control: same inputs give the same commitment', () => {
      const r = mkRef('ctl', 1);
      assert.deepEqual(pureCircuits.agentCommitment(AGENT_SK, r), pureCircuits.agentCommitment(AGENT_SK, r));
    });

    test('distinct-inputs control: different ref or different agent give different tags', () => {
      const c1 = pureCircuits.agentCommitment(AGENT_SK, mkRef('ctl', 1));
      const c2 = pureCircuits.agentCommitment(AGENT_SK, mkRef('ctl', 2));
      const c3 = pureCircuits.agentCommitment(AGENT2_SK, mkRef('ctl', 1));
      assert.notDeepEqual(c1, c2);
      assert.notDeepEqual(c1, c3);
    });

    test('same-agent and two-agent pairs are both ~128-bit Hamming apart (means within 4 bits)', () => {
      let sameD = 0, twoD = 0;
      for (let i = 0; i < N; i++) {
        const rA = mkRef('st', i), rB = mkRef('st', 1000 + i);
        const cs1 = pureCircuits.agentCommitment(AGENT_SK, rA);
        const cs2 = pureCircuits.agentCommitment(AGENT_SK, rB);   // same agent, two bookings
        const ct2 = pureCircuits.agentCommitment(AGENT2_SK, rB);  // two agents
        sameD += hammingBits(cs1, cs2);
        twoD += hammingBits(cs1, ct2);
      }
      const meanSame = sameD / N, meanTwo = twoD / N;
      assert.ok(Math.abs(meanSame - 128) <= 4, `same-agent mean Hamming ${meanSame} not ~128`);
      assert.ok(Math.abs(meanTwo - 128) <= 4, `two-agent mean Hamming ${meanTwo} not ~128`);
      assert.ok(Math.abs(meanSame - meanTwo) <= 4, `classes distinguishable: ${meanSame} vs ${meanTwo}`);
    });

    test('byte-collision rates ~1/256 in BOTH classes (no positional leak)', () => {
      let sameEq = 0, twoEq = 0;
      const total = N * 32;
      for (let i = 0; i < N; i++) {
        const rA = mkRef('bc', i), rB = mkRef('bc', 5000 + i);
        const cs1 = pureCircuits.agentCommitment(AGENT_SK, rA);
        const cs2 = pureCircuits.agentCommitment(AGENT_SK, rB);
        const ct2 = pureCircuits.agentCommitment(AGENT2_SK, rB);
        sameEq += equalBytes(cs1, cs2);
        twoEq += equalBytes(cs1, ct2);
      }
      const exp = total / 256; // expected equal byte positions per class
      assert.ok(Math.abs(sameEq - exp) <= 64, `same-agent byte collisions ${sameEq} vs expected ${exp}`);
      assert.ok(Math.abs(twoEq - exp) <= 64, `two-agent byte collisions ${twoEq} vs expected ${exp}`);
      assert.ok(Math.abs(sameEq - twoEq) <= 64, `positional leak: ${sameEq} vs ${twoEq}`);
    });
  });
});
