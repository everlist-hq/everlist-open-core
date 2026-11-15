/**
 * EverList escrow contract - HARDENING suite (bulletproof pass 2026-11-15).
 * Offline, real compiled circuits, simulated ledger — same harness as escrow.test.ts.
 * Focus: domain separation, custody walls, payout-key fixation, time-gate structure,
 * dispute freeze, batch integrity, money conservation.
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import { createCircuitContext, createConstructorContext } from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed/contract/index.js';

const b32 = (s) => { const a = new Uint8Array(32); a.set(new TextEncoder().encode(s).slice(0,32)); return a; };
const mkW = (aSk, oSk, rSk) => ({
  agentSecretKey: (c) => [c.privateState, aSk],
  organizerSecretKey: (c) => [c.privateState, oSk],
  arbiterSecretKey: (c) => [c.privateState, rSk],
});
const A_SK = new Uint8Array(32).fill(1), O_SK = new Uint8Array(32).fill(2), R_SK = new Uint8Array(32).fill(3), X_SK = new Uint8Array(32).fill(9);
const A_PK = { bytes: new Uint8Array(32).fill(11) }, O_PK = { bytes: new Uint8Array(32).fill(12) }, X_PK = { bytes: new Uint8Array(32).fill(77) };
const FAR = 99999999999n, PAST = 1000n;
const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);
const COLOR = b32('tDUST');

let ctx, honest, attacker, agentOnly, orgOnly, arbOnly;
let nonceCounter = 0;
const mkCoin = (v) => { const n = new Uint8Array(32); n.set([++nonceCounter & 0xff]); return { nonce: n, color: COLOR, value: v }; };
const SPEND = {};
const call = async (inst, name, ...args) => { const r = await inst.impureCircuits[name](ctx, ...args); ctx = r.context; return r; };
const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);
const escrowOf = (id) => readLedger().escrows.lookup(id);

/** Deploy-time constructor + fresh circuit context threaded on the shared ledger. */
const freshCtx = async () => {
  const ps = null;
  const ctor = await honest.initialState(createConstructorContext(ps, COIN_PK));
  ctx = createCircuitContext('createEscrow', ADDRESS, COIN_PK, ctor.currentContractState, ps);
};

const newEscrow = async (amount, ref, deadline = FAR, claim = FAR + 1n, pkAgent = A_PK, pkOrg = O_PK) => {
  const oc = pureCircuits.organizerCommitment(O_SK, ref);
  const dep = mkCoin(amount);
  const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
  await call(honest, 'createEscrow', amount, oc, ref, deadline, claim, dep, pkAgent, pkOrg);
  const id = readLedger().escrows.size();
  SPEND[id] = { nonce: dep.nonce, color: dep.color, value: amount, mt_index: mt };
  return id;
};

describe('HARDENING: commitment domain separation', () => {
  before(async () => {
    honest = new Contract(mkW(A_SK, O_SK, R_SK));
    attacker = new Contract(mkW(X_SK, X_SK, X_SK));
    agentOnly = new Contract(mkW(A_SK, X_SK, X_SK));
    orgOnly = new Contract(mkW(X_SK, O_SK, X_SK));
    arbOnly = new Contract(mkW(X_SK, X_SK, R_SK));
    await freshCtx();
  });

  test('agent/organizer/arbiter commitments differ for same inputs', () => {
    const ref = b32('ref');
    const a = pureCircuits.agentCommitment(A_SK, ref);
    const o = pureCircuits.organizerCommitment(O_SK, ref);
    const r = pureCircuits.arbiterCommitment(R_SK, ref);
    assert.notDeepEqual(a, o); assert.notDeepEqual(a, r); assert.notDeepEqual(o, r);
  });

  test('same sk, different role domain -> different tag (no cross-role impersonation)', () => {
    const ref = b32('ref');
    const sk = new Uint8Array(32).fill(7);
    const a = pureCircuits.agentCommitment(sk, ref);
    const o = pureCircuits.organizerCommitment(sk, ref);
    const r = pureCircuits.arbiterCommitment(sk, ref);
    assert.notDeepEqual(a, o); assert.notDeepEqual(a, r); assert.notDeepEqual(o, r);
  });

  test('per-booking binding: same sk, different bookingRef -> different tags', () => {
    assert.notDeepEqual(pureCircuits.agentCommitment(A_SK, b32('bkA')), pureCircuits.agentCommitment(A_SK, b32('bkB')));
  });

  test('deterministic commitments', () => {
    const ref = b32('det');
    assert.deepEqual(pureCircuits.agentCommitment(A_SK, ref), pureCircuits.agentCommitment(A_SK, ref));
  });
});

describe('HARDENING: custody + payout fixation', () => {
  before(async () => {
    honest = new Contract(mkW(A_SK, O_SK, R_SK));
    attacker = new Contract(mkW(X_SK, X_SK, X_SK));
    agentOnly = new Contract(mkW(A_SK, X_SK, X_SK));
    orgOnly = new Contract(mkW(X_SK, O_SK, X_SK));
    await freshCtx();
  });

  test('deposit less than amount rejected', async () => {
    const ref = b32('short');
    await assert.rejects(() => call(honest, 'createEscrow', 1000n, pureCircuits.organizerCommitment(O_SK, ref), ref, FAR, FAR + 1n, mkCoin(999n), A_PK, O_PK), /deposit must equal/);
  });

  test('deposit more than amount rejected (no overfunding)', async () => {
    const ref = b32('over');
    await assert.rejects(() => call(honest, 'createEscrow', 1000n, pureCircuits.organizerCommitment(O_SK, ref), ref, FAR, FAR + 1n, mkCoin(1001n), A_PK, O_PK), /deposit must equal/);
  });

  test('zero amount rejected', async () => {
    const ref = b32('zero');
    await assert.rejects(() => call(honest, 'createEscrow', 0n, pureCircuits.organizerCommitment(O_SK, ref), ref, FAR, FAR + 1n, mkCoin(0n), A_PK, O_PK), /amount must be positive/);
  });

  test('attacker cannot release (commitment wall; payout key is fixed at creation)', async () => {
    const id = await newEscrow(1000n, b32('fix-release'));
    await assert.rejects(() => call(attacker, 'releaseEscrow', id, SPEND[id]), /only organizer/);
    assert.equal(escrowOf(id).state, 1n);
  });

  test('attacker cannot refund', async () => {
    const id = await newEscrow(1000n, b32('fix-refund'));
    await assert.rejects(() => call(attacker, 'refundEscrow', id, SPEND[id]), /only agent/);
    assert.equal(escrowOf(id).state, 1n);
  });

  test('timeoutRefund is permissionless AFTER deadline and pays the stored AGENT key (by design)', async () => {
    const id = await newEscrow(1000n, b32('fix-timeout'), PAST, FAR + 1n);
    await call(attacker, 'timeoutRefund', id, SPEND[id]);
    assert.equal(escrowOf(id).state, 3n);
  });

  test('forged custody nonce rejected', async () => {
    const id = await newEscrow(1000n, b32('forge-nonce'));
    await assert.rejects(() => call(orgOnly, 'releaseEscrow', id, { ...SPEND[id], nonce: new Uint8Array(32).fill(99) }), /custody/);
  });

  test('forged custody color rejected (wrong asset)', async () => {
    const id = await newEscrow(1000n, b32('forge-color'));
    await assert.rejects(() => call(orgOnly, 'releaseEscrow', id, { ...SPEND[id], color: b32('EVIL') }), /custody/);
  });

  test('forged custody value rejected (partial sweep impossible)', async () => {
    const id = await newEscrow(1000n, b32('forge-value'));
    await assert.rejects(() => call(orgOnly, 'releaseEscrow', id, { ...SPEND[id], value: 999n }), /custody/);
  });

  test('double payout: released escrow cannot spend custody again (REPLAY wall)', async () => {
    const id = await newEscrow(1000n, b32('replay')); 
    await call(orgOnly, 'releaseEscrow', id, SPEND[id]);
    assert.equal(escrowOf(id).state, 2n);
    await assert.rejects(() => call(orgOnly, 'releaseEscrow', id, SPEND[id]), /not in HELD/);
    await assert.rejects(() => call(agentOnly, 'refundEscrow', id, SPEND[id]), /not in HELD/);
    await assert.rejects(() => call(attacker, 'timeoutRefund', id, SPEND[id]), /not in HELD/);
  });
});

describe('HARDENING: time-gate structure', () => {
  before(async () => {
    honest = new Contract(mkW(A_SK, O_SK, R_SK));
    attacker = new Contract(mkW(X_SK, X_SK, X_SK));
    agentOnly = new Contract(mkW(A_SK, X_SK, X_SK));
    await freshCtx();
  });

  test('refund after claim deadline blocked even for the agent (merchant auto-release window)', async () => {
    const id = await newEscrow(1000n, b32('late-refund'), PAST, PAST + 1n);
    await assert.rejects(() => call(agentOnly, 'refundEscrow', id, SPEND[id]), /claim deadline/);
    assert.equal(escrowOf(id).state, 1n);
  });

  test('timeoutRefund before deadline blocked', async () => {
    const id = await newEscrow(1000n, b32('early-timeout'));
    await assert.rejects(() => call(attacker, 'timeoutRefund', id, SPEND[id]), /deadline not reached/);
    assert.equal(escrowOf(id).state, 1n);
  });

  test('autoRelease before claim deadline blocked', async () => {
    const id = await newEscrow(1000n, b32('early-auto'));
    await assert.rejects(() => call(attacker, 'autoRelease', id, SPEND[id]), /claim deadline not reached/);
    assert.equal(escrowOf(id).state, 1n);
  });

  test('autoRelease after claim deadline works permissionlessly to the stored ORGANIZER key', async () => {
    const id = await newEscrow(1000n, b32('ok-auto'), PAST, PAST + 1n);
    await call(attacker, 'autoRelease', id, SPEND[id]);
    assert.equal(escrowOf(id).state, 2n);
  });
});

describe('HARDENING: dispute freeze structure', () => {
  before(async () => {
    honest = new Contract(mkW(A_SK, O_SK, R_SK));
    attacker = new Contract(mkW(X_SK, X_SK, X_SK));
    agentOnly = new Contract(mkW(A_SK, X_SK, X_SK));
    orgOnly = new Contract(mkW(X_SK, O_SK, X_SK));
    arbOnly = new Contract(mkW(X_SK, X_SK, R_SK));
    await freshCtx();
  });

  const toDisputed = async (ref) => {
    const id = await newEscrow(1000n, ref);
    await call(agentOnly, 'setArbiter', id, pureCircuits.arbiterCommitment(R_SK, escrowOf(id).bookingRef), FAR + 10n);
    await call(agentOnly, 'agentOpenDispute', id);
    return id;
  };

  test('agent cannot set arbiter twice', async () => {
    const id = await newEscrow(1000n, b32('arb-once'));
    const ref = escrowOf(id).bookingRef;
    await call(agentOnly, 'setArbiter', id, pureCircuits.arbiterCommitment(R_SK, ref), FAR + 10n);
    await assert.rejects(() => call(agentOnly, 'setArbiter', id, pureCircuits.arbiterCommitment(R_SK, ref), FAR + 10n), /already set/);
  });

  test('organizer cannot set the arbiter (agent-only rail)', async () => {
    const id = await newEscrow(1000n, b32('arb-org-deny'));
    const ref = escrowOf(id).bookingRef;
    await assert.rejects(() => call(orgOnly, 'setArbiter', id, pureCircuits.arbiterCommitment(R_SK, ref), FAR + 10n), /only agent/);
  });

  test('release/refund/timeout/autoRelease all blocked while DISPUTED (structural freeze)', async () => {
    const id = await toDisputed(b32('freeze-all'));
    await assert.rejects(() => call(orgOnly, 'releaseEscrow', id, SPEND[id]), /not in HELD/);
    await assert.rejects(() => call(agentOnly, 'refundEscrow', id, SPEND[id]), /not in HELD/);
    await assert.rejects(() => call(attacker, 'timeoutRefund', id, SPEND[id]), /not in HELD/);
    await assert.rejects(() => call(attacker, 'autoRelease', id, SPEND[id]), /not in HELD/);
  });

  test('non-arbiter cannot rule even with custody coin', async () => {
    const id = await toDisputed(b32('notarb'));
    await assert.rejects(() => call(attacker, 'arbiterRelease', id, SPEND[id]), /only arbiter/);
    await assert.rejects(() => call(attacker, 'arbiterRefund', id, SPEND[id]), /only arbiter/);
  });

  test('agentOpenDispute without arbiter rejected', async () => {
    const id = await newEscrow(1000n, b32('no-arb'));
    await assert.rejects(() => call(agentOnly, 'agentOpenDispute', id), /no arbiter set/);
  });

  test('arbiter deadline must be after claim deadline (no instant-freeze-then-grab)', async () => {
    const id = await newEscrow(1000n, b32('arb-order'));
    const ref = escrowOf(id).bookingRef;
    await assert.rejects(() => call(agentOnly, 'setArbiter', id, pureCircuits.arbiterCommitment(R_SK, ref), PAST), /after claim deadline/);
  });
});

describe('HARDENING: batch integrity + money conservation', () => {
  before(async () => {
    honest = new Contract(mkW(A_SK, O_SK, R_SK));
    attacker = new Contract(mkW(X_SK, X_SK, X_SK));
    orgOnly = new Contract(mkW(X_SK, O_SK, X_SK));
    await freshCtx();
  });

  test('batch with same id twice rejected', async () => {
    const id = await newEscrow(1000n, b32('dup-id'));
    await assert.rejects(() => call(orgOnly, 'batchRelease2', id, id, SPEND[id], SPEND[id]), /must differ/);
  });

  test('batch: only organizer of BOTH escrows can release (two-key wall)', async () => {
    const ref = b32('att-org');
    const ocX = pureCircuits.organizerCommitment(X_SK, ref);
    const dep = mkCoin(1000n);
    const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
    await call(attacker, 'createEscrow', 1000n, ocX, ref, FAR, FAR + 1n, dep, A_PK, X_PK);
    const idX = readLedger().escrows.size();
    SPEND[idX] = { nonce: dep.nonce, color: dep.color, value: 1000n, mt_index: mt };
    const idA = await newEscrow(1000n, b32('honest-org'));
    await assert.rejects(() => call(orgOnly, 'batchRelease2', idA, idX, SPEND[idA], SPEND[idX]), /only organizer/);
  });

  test('batch replay: same coin for both slots rejected by second custody check', async () => {
    const id1 = await newEscrow(1000n, b32('batch-replay-1'));
    const id2 = await newEscrow(1000n, b32('batch-replay-2'));
    await assert.rejects(() => call(orgOnly, 'batchRelease2', id1, id2, SPEND[id1], SPEND[id1]), /custody/);
  });

  test('money conservation: release emits exactly one payout coin and finalizes state', async () => {
    const id = await newEscrow(1000n, b32('conserve'));
    const before = ctx.callContext.currentZswapLocalState.outputs.length;
    await call(orgOnly, 'releaseEscrow', id, SPEND[id]);
    const outs = ctx.callContext.currentZswapLocalState.outputs;
    assert.equal(outs.length, before + 1);
    assert.equal(escrowOf(id).state, 2n);
  });
});
