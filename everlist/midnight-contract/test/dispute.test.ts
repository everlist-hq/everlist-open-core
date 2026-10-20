/**
 * EverList escrow dispute path — OFFLINE tests (W3.1, P2 #5).
 *
 * Runs the REAL compiled circuits (managed/contract) against a simulated
 * ledger via compact-runtime. No proof server, no network.
 *
 * Party-accurate instances (role-wall pattern):
 *   honest    - both party secrets + NO arbiter secret (the parties)
 *   arbiter   - ONLY the arbiter secret (the third-trust machine)
 *   attacker  - nothing real
 *
 * The dispute path adds states 4 (DISPUTED), 5 (ARB_RELEASED), 6
 * (ARB_REFUNDED) to escrow.compact, mirroring milestone.compact.
 *
 * Run: npx tsx --test test/dispute.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed/contract/index.js';

const mkWitnesses = (agentSk, orgSk, arbSk = new Uint8Array(32).fill(5)) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
  arbiterSecretKey: (ctxt) => [ctxt.privateState, arbSk],
});

const AGENT_SK = new Uint8Array(32).fill(1);
const ORG_SK = new Uint8Array(32).fill(2);
const ARB_SK = new Uint8Array(32).fill(3);
const JUNK_SK = new Uint8Array(32).fill(9);

const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);

let ctx;
let honest;
let arbiter;
let attacker;

let nonceCounter = 0;
const mkCoin = (value) => {
  const nonce = new Uint8Array(32);
  nonce.set([++nonceCounter & 0xff]);
  return { nonce, color: new Uint8Array(32).fill(1), value };
};

const SPEND = {};

const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);
const zswapOutputs = () => ctx.callContext.currentZswapLocalState.outputs;

const newEscrow = async (amount, bookingRef, arbiterDeadline = 200000000000n, deadline = 99999999999n, claimDeadline = null) => {
  if (claimDeadline === null) claimDeadline = deadline + 1n;
  const orgComm = pureCircuits.organizerCommitment(ORG_SK, bookingRef);
  const deposit = mkCoin(amount);
  const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
  await call(honest, 'createEscrow', amount, orgComm, bookingRef, deadline, claimDeadline, deposit, AGENT_PK, ORG_PK);
  const id = readLedger().escrows.size();
  SPEND[id] = { nonce: deposit.nonce, color: deposit.color, value: amount, mt_index: mt };
  if (arbiterDeadline !== null) {
    const arbComm = pureCircuits.arbiterCommitment(ARB_SK, bookingRef);
    await call(honest, 'setArbiter', id, arbComm, arbiterDeadline);
  }
  return id;
};

const b32 = (s) => {
  const b = new Uint8Array(32);
  b.set(Buffer.from(s, 'utf8'));
  return b;
};

describe('EverList escrow dispute path (offline, real compiled circuits)', () => {
  before(async () => {
    honest = new Contract(mkWitnesses(AGENT_SK, ORG_SK));
    arbiter = new Contract(mkWitnesses(JUNK_SK, JUNK_SK, ARB_SK));
    attacker = new Contract(mkWitnesses(JUNK_SK, JUNK_SK));
    const ps = null;
    const ctor = await honest.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('createEscrow', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('arbiterCommitment (pure)', () => {
    test('deterministic and domain-separated from party commitments', () => {
      const c1 = pureCircuits.arbiterCommitment(ARB_SK, b32('bk-1'));
      const c2 = pureCircuits.arbiterCommitment(ARB_SK, b32('bk-1'));
      assert.deepEqual(c1, c2, 'deterministic');
      const agentC = pureCircuits.agentCommitment(ARB_SK, b32('bk-1'));
      const orgC = pureCircuits.organizerCommitment(ARB_SK, b32('bk-1'));
      assert.notDeepEqual(c1, agentC, 'agent domain separated');
      assert.notDeepEqual(c1, orgC, 'organizer domain separated');
      assert.notDeepEqual(c1, pureCircuits.arbiterCommitment(ARB_SK, b32('bk-2')), 'bookingRef bound');
      assert.notDeepEqual(c1, pureCircuits.arbiterCommitment(JUNK_SK, b32('bk-1')), 'secret bound');
    });
  });

  describe('setArbiter', () => {
    test('agent sets the arbiter (commitment + deadline on ledger)', async () => {
      const id = await newEscrow(100n, b32('dispute-1'));
      const l = readLedger();
      assert.ok(l.arbiters.member(id), 'arbiter record exists');
    });

    test('organizer cannot set the arbiter', async () => {
      const id = await newEscrow(100n, b32('dispute-2'), null);
      const arbComm = pureCircuits.arbiterCommitment(ARB_SK, b32('dispute-2'));
      const organizerOnly = new Contract(mkWitnesses(ORG_SK, ORG_SK));
      await assert.rejects(
        () => call(organizerOnly, 'setArbiter', id, arbComm, 99999999999n),
        /only agent can set the arbiter/
      );
    });

    test('attacker cannot set the arbiter', async () => {
      const id = await newEscrow(100n, b32('dispute-3'), null);
      const arbComm = pureCircuits.arbiterCommitment(ARB_SK, b32('dispute-3'));
      await assert.rejects(
        () => call(attacker, 'setArbiter', id, arbComm, 99999999999n),
        /only agent can set the arbiter/
      );
    });

    test('arbiter cannot be changed once set', async () => {
      const id = await newEscrow(100n, b32('dispute-4'));
      const arbComm2 = pureCircuits.arbiterCommitment(JUNK_SK, b32('dispute-4'));
      await assert.rejects(
        () => call(honest, 'setArbiter', id, arbComm2, 99999999999n),
        /arbiter already set/
      );
    });

    test('arbiter deadline must be after claim deadline', async () => {
      const id = await newEscrow(100n, b32('dispute-5'), null);
      const arbComm = pureCircuits.arbiterCommitment(ARB_SK, b32('dispute-5'));
      await assert.rejects(
        () => call(honest, 'setArbiter', id, arbComm, 1n),
        /arbiter deadline must be after claim deadline/
      );
    });

    test('cannot set arbiter after dispute opened', async () => {
      const id = await newEscrow(100n, b32('dispute-6'), null);
      await call(honest, 'agentOpenDispute', id).catch(() => {});
      const arbComm = pureCircuits.arbiterCommitment(ARB_SK, b32('dispute-6'));
      // no arbiter set -> openDispute rejects; set arbiter first
      const id2 = await newEscrow(100n, b32('dispute-6b'));
      await call(honest, 'agentOpenDispute', id2);
      const arbComm2 = pureCircuits.arbiterCommitment(ARB_SK, b32('dispute-6b'));
      await assert.rejects(
        () => call(honest, 'setArbiter', id2, arbComm2, 99999999999n),
        /escrow not in HELD state/
      );
    });
  });

  describe('opening disputes', () => {
    test('agent opens dispute (HELD -> DISPUTED)', async () => {
      const id = await newEscrow(100n, b32('dispute-7'));
      await call(honest, 'agentOpenDispute', id);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 4n, 'DISPUTED');
    });

    test('organizer opens dispute (HELD -> DISPUTED)', async () => {
      const id = await newEscrow(100n, b32('dispute-8'));
      await call(honest, 'organizerOpenDispute', id);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 4n, 'DISPUTED');
    });

    test('attacker cannot open dispute', async () => {
      const id = await newEscrow(100n, b32('dispute-9'));
      await assert.rejects(
        () => call(attacker, 'agentOpenDispute', id),
        /only agent can open this dispute/
      );
      await assert.rejects(
        () => call(attacker, 'organizerOpenDispute', id),
        /only organizer can open this dispute/
      );
    });

    test('cannot open without arbiter set', async () => {
      const id = await newEscrow(100n, b32('dispute-10'), null);
      await assert.rejects(
        () => call(honest, 'agentOpenDispute', id),
        /no arbiter set/
      );
    });

    test('double dispute rejected', async () => {
      const id = await newEscrow(100n, b32('dispute-11'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(honest, 'organizerOpenDispute', id),
        /escrow not in HELD state/
      );
    });
  });

  describe('DISPUTED freezes the money', () => {
    test('release blocked while DISPUTED', async () => {
      const id = await newEscrow(100n, b32('dispute-12'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(honest, 'releaseEscrow', id, SPEND[id]),
        /escrow not in HELD state/
      );
    });

    test('refund blocked while DISPUTED', async () => {
      const id = await newEscrow(100n, b32('dispute-13'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(honest, 'refundEscrow', id, SPEND[id]),
        /escrow not in HELD state/
      );
    });

    test('timeout refund blocked while DISPUTED', async () => {
      const id = await newEscrow(100n, b32('dispute-14'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(attacker, 'timeoutRefund', id, SPEND[id]),
        /escrow not in HELD state/
      );
    });

    test('auto-release blocked while DISPUTED', async () => {
      const id = await newEscrow(100n, b32('dispute-15'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(attacker, 'autoRelease', id, SPEND[id]),
        /escrow not in HELD state/
      );
    });
  });

  describe('arbiter rulings', () => {
    test('arbiter rules for organizer (DISPUTED -> ARB_RELEASED, pays organizer)', async () => {
      const id = await newEscrow(100n, b32('dispute-16'));
      await call(honest, 'agentOpenDispute', id);
      await call(arbiter, 'arbiterRelease', id, SPEND[id]);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 5n, 'ARB_RELEASED');
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, true, 'payout goes to a user coin key');
      assert.deepEqual(o.recipient.left.bytes, ORG_PK.bytes, 'organizer paid');
      assert.equal(o.coinInfo.value, 100n);
    });

    test('arbiter rules for agent (DISPUTED -> ARB_REFUNDED, pays agent)', async () => {
      const id = await newEscrow(100n, b32('dispute-17'));
      await call(honest, 'organizerOpenDispute', id);
      await call(arbiter, 'arbiterRefund', id, SPEND[id]);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 6n, 'ARB_REFUNDED');
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, true, 'payout goes to a user coin key');
      assert.deepEqual(o.recipient.left.bytes, AGENT_PK.bytes, 'agent paid');
      assert.equal(o.coinInfo.value, 100n);
    });

    test('attacker cannot rule', async () => {
      const id = await newEscrow(100n, b32('dispute-18'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(attacker, 'arbiterRelease', id, SPEND[id]),
        /only arbiter can rule/
      );
      await assert.rejects(
        () => call(attacker, 'arbiterRefund', id, SPEND[id]),
        /only arbiter can rule/
      );
    });

    test('parties cannot rule (even with their own secrets)', async () => {
      const id = await newEscrow(100n, b32('dispute-19'));
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(honest, 'arbiterRelease', id, SPEND[id]),
        /only arbiter can rule/
      );
      await assert.rejects(
        () => call(honest, 'arbiterRefund', id, SPEND[id]),
        /only arbiter can rule/
      );
    });

    test('ruling only from DISPUTED (HELED rejected)', async () => {
      const id = await newEscrow(100n, b32('dispute-20'));
      await assert.rejects(
        () => call(arbiter, 'arbiterRelease', id, SPEND[id]),
        /escrow not in DISPUTED state/
      );
    });

    test('double ruling rejected (terminal)', async () => {
      const id = await newEscrow(100n, b32('dispute-21'));
      await call(honest, 'agentOpenDispute', id);
      await call(arbiter, 'arbiterRelease', id, SPEND[id]);
      await assert.rejects(
        () => call(arbiter, 'arbiterRefund', id, SPEND[id]),
        /escrow not in DISPUTED state/
      );
    });
  });

  describe('arbiter timeout hatch (liveness)', () => {
    test('anyone can refund agent after arbiter deadline', async () => {
      const id = await newEscrow(100n, b32('dispute-22'), 2000n, 1000n, 1001n);
      await call(honest, 'agentOpenDispute', id);
      await call(attacker, 'arbiterTimeoutRefund', id, SPEND[id]);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 6n, 'ARB_REFUNDED via hatch');
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, true, 'payout goes to a user coin key');
      assert.deepEqual(o.recipient.left.bytes, AGENT_PK.bytes, 'agent paid');
      assert.equal(o.coinInfo.value, 100n);
    });

    test('hatch rejected before arbiter deadline', async () => {
      const id = await newEscrow(100n, b32('dispute-23'), 200000000000n, 1000n, 1001n);
      await call(honest, 'agentOpenDispute', id);
      await assert.rejects(
        () => call(attacker, 'arbiterTimeoutRefund', id, SPEND[id]),
        /arbiter deadline not yet passed/
      );
    });

    test('hatch only from DISPUTED', async () => {
      const id = await newEscrow(100n, b32('dispute-24'), 2000n, 1000n, 1001n);
      await assert.rejects(
        () => call(attacker, 'arbiterTimeoutRefund', id, SPEND[id]),
        /escrow not in DISPUTED state/
      );
    });
  });

  describe('dispute does not affect other escrows', () => {
    test('normal escrow lifecycle unaffected (regression)', async () => {
      const id = await newEscrow(100n, b32('dispute-25'));
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 2n, 'RELEASED (normal)');
    });

    test('two escrows: one disputed, one normal — no cross-contamination', async () => {
      const idA = await newEscrow(100n, b32('dispute-26a'));
      const idB = await newEscrow(100n, b32('dispute-26b'));
      await call(honest, 'agentOpenDispute', idA);
      await call(honest, 'releaseEscrow', idB, SPEND[idB]);
      assert.equal(readLedger().escrows.lookup(idA).state, 4n, 'A DISPUTED');
      assert.equal(readLedger().escrows.lookup(idB).state, 2n, 'B RELEASED');
    });
  });
});
