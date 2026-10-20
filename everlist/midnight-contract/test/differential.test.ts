/**
 * EverList escrow — DIFFERENTIAL FUZZING (W3.5, techmining idea #14,
 * "€15 vs €1500 must look identical", 2026-10-21).
 *
 * Extends the fixed two-world indistinguishability proof (test/
 * indistinguishability.test.ts) with a SEEDED RANDOM differential sweep:
 *
 *   1. Random two-world structural sweep: random amount pairs (budget tier
 *      vs premium tier), unique booking refs, random second-agent secret —
 *      the public ledger snapshots must differ in EXACTLY one field
 *      (escrow #2 agentCommitment) every round; chain-observer zswap
 *      outputs identical every round.
 *   2. Random-identity PRF statistics: same-agent vs two-agent commitment
 *      classes stay ~128-bit Hamming apart and ~1/256 byte-collision
 *      across RANDOM secret draws (the fixed-identity version can miss
 *      unlucky identities; this sweep cannot).
 *   3. Batch-vs-singles differential (W3.3 x W3.5): releasing two escrows
 *      with ONE batchRelease2 call vs TWO releaseEscrow calls must end in
 *      BYTE-IDENTICAL public escrow state. Grouping (one tx vs two) is
 *      public by design; the RECORD CONTENT must not betray which path
 *      was used.
 *   4. Adversarial positive controls: rounds where the worlds DIFFER in a
 *      planted public field (e.g. amount) — the detector MUST flag it.
 *      A differential harness that cannot fail proves nothing.
 *
 * Deterministic: fixed seed -> fixed rounds -> CI-stable.
 * Run: npx tsx --test test/differential.test.ts
 */
import { test, describe } from 'node:test';
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

const hex = (b: Uint8Array) => Array.from(b).map((x) => x.toString(16).padStart(2, '0')).join('');

const mkWitnesses = (agentSk: Uint8Array, orgSk: Uint8Array) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
  arbiterSecretKey: (ctxt) => [ctxt.privateState, new Uint8Array(32).fill(5)],
});

const AGENT_SK = new Uint8Array(32).fill(1);
const ORG_SK = new Uint8Array(32).fill(2);

const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };

const DEADLINE_FAR = 99999999999n;
const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);
const COLOR = b32('tDUST');

// --- deterministic PRNG (fixed seed -> CI-stable rounds) ---
const SEED = 20261021;
let prngState = SEED >>> 0;
const rnd = () => {
  prngState = (Math.imul(prngState, 1664525) + 1013904223) >>> 0;
  return prngState / 2 ** 32;
};
const rndAmountBudget = () => BigInt(15 + Math.floor(rnd() * 486));    // 15..500
const rndAmountPremium = () => BigInt(1000 + Math.floor(rnd() * 4000)); // 1000..4999
const rndSk = (tag: string, i: number) => {
  const sk = new Uint8Array(32);
  sk.set(new TextEncoder().encode(`${tag}:${i}`).slice(0, 32));
  sk[31] = (prngState & 0xff) ^ (i & 0xff); // spread identities
  return sk;
};
const rndRef = (tag: string, i: number) => {
  const r = new Uint8Array(32);
  r.set(new TextEncoder().encode(`${tag}-${i}`).slice(0, 32));
  r[30] = (prngState >>> 8) & 0xff;
  return r;
};

/** One independent world (fresh contract + ledger thread). */
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
    const id = readLedger().escrows.size();
    const e = readLedger().escrows.lookup(id);
    const spend = { nonce: e.coinNonce, color: e.coinColor, value: e.amount, mt_index: mt };
    return { id, spend };
  };

  return { first, second, newEscrow, call, readLedger, zswapOutputs };
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

describe('W3.5 differential fuzzing (seeded random two-world sweeps)', () => {

  describe('random structural sweep: budget-vs-premium loyalty is invisible', () => {
    const ROUNDS = 12;

    for (let i = 0; i < ROUNDS; i++) {
      test(`round ${i}: random amounts, random stranger — public diff is exactly one commitment field`, async () => {
        const amount1 = rndAmountBudget();
        const amount2 = rndAmountPremium();
        const ref1 = rndRef('df-a', i);
        const ref2 = rndRef('df-b', i);
        const strangerSk = rndSk('df-stranger', i);

        const worldA = await buildWorld(AGENT_SK);   // loyal: both bookings
        await worldA.newEscrow(worldA.first, amount1, ref1);
        await worldA.newEscrow(worldA.first, amount2, ref2);

        const worldB = await buildWorld(strangerSk); // strangers: one each
        await worldB.newEscrow(worldB.first, amount1, ref1);
        await worldB.newEscrow(worldB.second, amount2, ref2);

        const diffs = diffPaths(snapshot(worldA.readLedger()), snapshot(worldB.readLedger()));
        assert.deepEqual(
          diffs,
          ['escrows.2.agentCommitment'],
          `round ${i} (€${amount1} + €${amount2}): leak detected: ${JSON.stringify(diffs)}`
        );
        assert.deepEqual(worldA.zswapOutputs(), worldB.zswapOutputs(), `round ${i}: chain-observer money view differs`);
      });
    }
  });

  describe('random-identity PRF sweep (stronger than fixed-identity stats)', () => {
    const N = 128;

    test('same-agent vs two-agent classes stay ~128-bit apart across random secrets', () => {
      let sameD = 0, twoD = 0;
      for (let i = 0; i < N; i++) {
        const skX = rndSk('df-prf-x', i);
        const skY = rndSk('df-prf-y', i);
        const rA = rndRef('df-pa', i);
        const rB = rndRef('df-pb', i);
        const same1 = pureCircuits.agentCommitment(skX, rA);
        const same2 = pureCircuits.agentCommitment(skX, rB);   // same agent, two bookings
        const two2 = pureCircuits.agentCommitment(skY, rB);    // two agents
        sameD += hammingBits(same1, same2);
        twoD += hammingBits(same1, two2);
      }
      const meanSame = sameD / N, meanTwo = twoD / N;
      assert.ok(Math.abs(meanSame - 128) <= 4, `same-agent mean Hamming ${meanSame} not ~128`);
      assert.ok(Math.abs(meanTwo - 128) <= 4, `two-agent mean Hamming ${meanTwo} not ~128`);
      assert.ok(Math.abs(meanSame - meanTwo) <= 4, `classes distinguishable: ${meanSame} vs ${meanTwo}`);
    });

    test('byte-collision rates ~1/256 in both classes across random secrets (no positional leak)', () => {
      let sameEq = 0, twoEq = 0;
      const total = N * 32;
      for (let i = 0; i < N; i++) {
        const skX = rndSk('df-bc-x', i);
        const skY = rndSk('df-bc-y', i);
        const rA = rndRef('df-ca', i);
        const rB = rndRef('df-cb', i);
        sameEq += equalBytes(pureCircuits.agentCommitment(skX, rA), pureCircuits.agentCommitment(skX, rB));
        twoEq += equalBytes(pureCircuits.agentCommitment(skX, rA), pureCircuits.agentCommitment(skY, rB));
      }
      const exp = total / 256;
      assert.ok(Math.abs(sameEq - exp) <= 64, `same-agent byte collisions ${sameEq} vs expected ${exp}`);
      assert.ok(Math.abs(twoEq - exp) <= 64, `two-agent byte collisions ${twoEq} vs expected ${exp}`);
      assert.ok(Math.abs(sameEq - twoEq) <= 64, `positional leak: ${sameEq} vs ${twoEq}`);
    });
  });

  describe('batch-vs-singles differential (W3.3 x W3.5): content is path-independent', () => {
    /** Build BOTH escrows identically; settle via singles or batch; return final public snapshot. */
    const settleWorld = async (mode: 'singles' | 'batch', amount1: bigint, amount2: bigint, ref1: Uint8Array, ref2: Uint8Array) => {
      const w = await buildWorld(ORG_SK); // org witness present for release paths
      const e1 = await w.newEscrow(w.first, amount1, ref1);
      const e2 = await w.newEscrow(w.first, amount2, ref2);
      if (mode === 'singles') {
        await w.call(w.first, 'releaseEscrow', e1.id, e1.spend);
        await w.call(w.first, 'releaseEscrow', e2.id, e2.spend);
      } else {
        await w.call(w.first, 'batchRelease2', e1.id, e2.id, e1.spend, e2.spend);
      }
      const led = w.readLedger();
      return { snap: snapshot(led), led, e1: e1.id, e2: e2.id };
    };

    test('canonical pair: batchRelease2 vs two releaseEscrow — identical public escrow state', async () => {
      const ref1 = b32('bdf-fixed-1');
      const ref2 = b32('bdf-fixed-2');
      const S = await settleWorld('singles', 15n, 1500n, ref1, ref2);
      const B = await settleWorld('batch', 15n, 1500n, ref1, ref2);

      assert.equal(S.led.escrows.lookup(S.e1).state, 2n);
      assert.equal(S.led.escrows.lookup(S.e2).state, 2n);
      assert.equal(B.led.escrows.lookup(B.e1).state, 2n);
      assert.equal(B.led.escrows.lookup(B.e2).state, 2n);

      const diffs = diffPaths(S.snap, B.snap);
      assert.deepEqual(diffs, [], `batch vs singles leaked through public state: ${JSON.stringify(diffs)}`);
    });

    const ROUNDS = 6;
    for (let i = 0; i < ROUNDS; i++) {
      test(`round ${i}: random amounts — batch vs singles content-identical`, async () => {
        const amount1 = rndAmountBudget();
        const amount2 = rndAmountPremium();
        const ref1 = rndRef('bdf-a', i);
        const ref2 = rndRef('bdf-b', i);
        const S = await settleWorld('singles', amount1, amount2, ref1, ref2);
        const B = await settleWorld('batch', amount1, amount2, ref1, ref2);
        const diffs = diffPaths(S.snap, B.snap);
        assert.deepEqual(diffs, [], `round ${i} (€${amount1} + €${amount2}): ${JSON.stringify(diffs)}`);
      });
    }
  });

  describe('adversarial positive controls: the detector MUST catch planted leaks', () => {
    const ROUNDS = 6;

    for (let i = 0; i < ROUNDS; i++) {
      test(`round ${i}: planted amount difference IS flagged (control against vacuous pass)`, async () => {
        const amount1 = rndAmountBudget();
        const amount2 = rndAmountPremium();
        const ref1 = rndRef('adv-a', i);
        const ref2 = rndRef('adv-b', i);
        const strangerSk = rndSk('adv-stranger', i);

        const worldA = await buildWorld(AGENT_SK);
        await worldA.newEscrow(worldA.first, amount1, ref1);
        await worldA.newEscrow(worldA.first, amount2, ref2);

        const worldB = await buildWorld(strangerSk);
        await worldB.newEscrow(worldB.first, amount1, ref1);
        await worldB.newEscrow(worldB.second, amount2 + 1n, ref2); // PLANTED leak

        const diffs = diffPaths(snapshot(worldA.readLedger()), snapshot(worldB.readLedger()));
        assert.ok(
          diffs.includes('escrows.2.amount'),
          `detector missed the planted amount leak: ${JSON.stringify(diffs)}`
        );
      });
    }
  });
});
