/**
 * EverList milestone escrow - OFFLINE tests (techmining P1 #3 + P2 #5).
 *
 * Runs the REAL compiled circuits (managed-milestone/contract) against a
 * simulated ledger via compact-runtime. No proof server, no network.
 *
 * Party-accurate instances (role-wall pattern):
 *   agent   - the buyer's machine: knows ONLY its own secret
 *   org     - the organizer's machine: knows ONLY its own secret
 *   arbiter - the hub-as-arbiter: knows ONLY the arbiter secret
 *   anyone  - attacker/neutral caller: knows nothing real (liveness paths)
 *
 * Milestone states: 1 HELD, 2 DISPUTED, 3 RELEASED, 4 REFUNDED,
 * 5 ARB_RELEASED, 6 ARB_REFUNDED (finals >= 3 are contiguous).
 *
 * Run: npx tsx --test test/milestone.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed-milestone/contract/index.js';

const b32 = (s) => {
  const a = new Uint8Array(32);
  a.set(new TextEncoder().encode(s).slice(0, 32));
  return a;
};

// witnesses: per-role machines (each holds ONLY its own real secret)
const mkWitnesses = (agentSk, orgSk, arbSk) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
  arbiterSecretKey: (ctxt) => [ctxt.privateState, arbSk],
});

const AGENT_SK = new Uint8Array(32).fill(1);
const ORG_SK = new Uint8Array(32).fill(2);
const ARB_SK = new Uint8Array(32).fill(3);
const AGENT2_SK = new Uint8Array(32).fill(4);   // second agent (isolation)
const ORG2_SK = new Uint8Array(32).fill(5);
const ATTACKER_SK = new Uint8Array(32).fill(9);

// coin public keys (payout destinations): {bytes} struct form
const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };

// block-time deadlines: default-time contexts sit at now ~ 1.78e9
const FAR = 99999999999n;
const PAST = 1000n;

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);
const COLOR = b32('tDUST');

let ctx;      // evolving context: carries the mutated ledger
let agent;    // agent's machine
let org;      // organizer's machine
let arbiter;  // arbiter's machine (pilot: the hub)
let anyone;   // attacker / neutral liveness caller
let agent2;   // second agent (cross-deal isolation)

let nonceCounter = 0;
const mkCoin = (value) => {
  const nonce = new Uint8Array(32);
  nonce.set([++nonceCounter & 0xff]);
  return { nonce, color: COLOR, value };
};

/** Spend coin for (dealId, idx): deposit + mt_index captured BEFORE create. */
const SPEND = {};

const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);
const mkey = (dealId, idx) => BigInt(dealId) * 100n + BigInt(idx);

const orgComm = (sk, ref) => pureCircuits.organizerCommitment(sk, ref);
const arbComm = (sk, ref) => pureCircuits.arbiterCommitment(sk, ref);

let dealCounter = 0;

/**
 * Open a deal and optionally fund its milestones. Returns the deal id;
 * stores each spend coin in SPEND[dealKey].
 */
const newDeal = async (opts = {}) => {
  const {
    agentInst = agent,
    orgSk = ORG_SK,
    count = 3,
    ref = b32('deal-' + (++dealCounter)),
    milestones = [], // [{amount, deadline, claimDeadline}]
    arbDeadline = FAR,
  } = opts;

  await call(agentInst, 'createDeal', ref, BigInt(count), orgComm(orgSk, ref), arbComm(ARB_SK, ref), arbDeadline, AGENT_PK, ORG_PK);
  const dealId = readLedger().deals.size();

  for (let i = 0; i < milestones.length; i++) {
    const { amount, deadline = FAR, claimDeadline = FAR + 1n } = milestones[i];
    const deposit = mkCoin(amount);
    const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
    await call(agentInst, 'createMilestone', dealId, amount, deadline, claimDeadline, deposit);
    SPEND[mkey(dealId, i)] = { nonce: deposit.nonce, color: deposit.color, value: amount, mt_index: mt };
  }

  return dealId;
};

const mstate = (dealId, idx) =>
  readLedger().milestones.lookup(mkey(dealId, idx)).state;

const zswapOutputs = () => ctx.callContext.currentZswapLocalState.outputs;

/** The latest payout: who was paid and how much. */
const lastPayout = () => {
  const o = zswapOutputs().at(-1);
  return { toUser: o.recipient.is_left, pk: o.recipient.left?.bytes, value: o.coinInfo.value };
};

/** Total value paid to a specific pk so far. */
const paidTo = (pk) =>
  zswapOutputs()
    .filter((o) => o.recipient.is_left)
    .filter((o) => {
      const b = o.recipient.left.bytes;
      return b.length === pk.bytes.length && b.every((v, i) => v === pk.bytes[i]);
    })
    .reduce((s, o) => s + o.coinInfo.value, 0n);

describe('EverList milestone escrow + dispute path (offline, real compiled circuits)', () => {
  before(async () => {
    agent = new Contract(mkWitnesses(AGENT_SK, ATTACKER_SK, ATTACKER_SK));
    org = new Contract(mkWitnesses(ATTACKER_SK, ORG_SK, ATTACKER_SK));
    arbiter = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK, ARB_SK));
    anyone = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK, ATTACKER_SK));
    agent2 = new Contract(mkWitnesses(AGENT2_SK, ORG2_SK, ATTACKER_SK));
    const ps = null;

    const ctor = await agent.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('createDeal', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('createDeal validation', () => {
    test('zero milestones rejected', async () => {
      const ref = b32('d-zero');
      await assert.rejects(
        () => call(agent, 'createDeal', ref, 0n, orgComm(ORG_SK, ref), arbComm(ARB_SK, ref), FAR, AGENT_PK, ORG_PK),
        /at least one milestone/
      );
    });

    test('13 milestones rejected (max 12)', async () => {
      const ref = b32('d-thirteen');
      await assert.rejects(
        () => call(agent, 'createDeal', ref, 13n, orgComm(ORG_SK, ref), arbComm(ARB_SK, ref), FAR, AGENT_PK, ORG_PK),
        /at most 12 milestones/
      );
    });

    test('12 milestones accepted', async () => {
      const ref = b32('d-twelve');
      await call(agent, 'createDeal', ref, 12n, orgComm(ORG_SK, ref), arbComm(ARB_SK, ref), FAR, AGENT_PK, ORG_PK);
      const d = readLedger().deals.lookup(readLedger().deals.size());
      assert.equal(d.count, 12n);
      assert.equal(d.created, 0n);
    });

    test('deal stores per-party commitments and arbiter', async () => {
      const ref = b32('d-store');
      await call(agent, 'createDeal', ref, 2n, orgComm(ORG_SK, ref), arbComm(ARB_SK, ref), FAR, AGENT_PK, ORG_PK);
      const d = readLedger().deals.lookup(readLedger().deals.size());
      assert.deepEqual(d.agentCommitment, pureCircuits.agentCommitment(AGENT_SK, ref));
      assert.deepEqual(d.organizerCommitment, orgComm(ORG_SK, ref));
      assert.deepEqual(d.arbiterCommitment, arbComm(ARB_SK, ref));
    });
  });

  describe('createMilestone (funding)', () => {
    test('funds milestone 0 (HELD) with exact-value deposit', async () => {
      const dealId = await newDeal({ count: 2, milestones: [{ amount: 100n }] });
      assert.equal(mstate(dealId, 0), 1n);
      const m = readLedger().milestones.lookup(mkey(dealId, 0));
      assert.equal(m.amount, 100n);
    });

    test('deposit value mismatch rejected', async () => {
      const dealId = await newDeal({ count: 2 });
      const deposit = mkCoin(55n);
      await assert.rejects(
        () => call(agent, 'createMilestone', dealId, 100n, FAR, FAR + 1n, deposit),
        /deposit must equal/
      );
    });

    test('claim deadline must be after refund deadline', async () => {
      const dealId = await newDeal({ count: 2 });
      const deposit = mkCoin(50n);
      await assert.rejects(
        () => call(agent, 'createMilestone', dealId, 50n, FAR + 2n, FAR + 1n, deposit),
        /claim deadline must be after/
      );
    });

    test('SEQUENTIAL GATE: milestone 1 blocked while milestone 0 HELD', async () => {
      const dealId = await newDeal({ count: 2, milestones: [{ amount: 100n }] });
      const deposit = mkCoin(50n);
      await assert.rejects(
        () => call(agent, 'createMilestone', dealId, 50n, FAR, FAR + 1n, deposit),
        /previous milestone not settled/
      );
    });

    test('SEQUENTIAL GATE: milestone 1 blocked while milestone 0 DISPUTED', async () => {
      const dealId = await newDeal({ count: 2, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      const deposit = mkCoin(50n);
      await assert.rejects(
        () => call(agent, 'createMilestone', dealId, 50n, FAR, FAR + 1n, deposit),
        /previous milestone not settled/
      );
    });

    test('SEQUENTIAL GATE: settled milestone 0 unblocks milestone 1', async () => {
      const dealId = await newDeal({ count: 2, milestones: [{ amount: 100n }] });
      await call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      const deposit = mkCoin(50n);
      const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      await call(agent, 'createMilestone', dealId, 50n, FAR, FAR + 1n, deposit);
      SPEND[mkey(dealId, 1)] = { nonce: deposit.nonce, color: deposit.color, value: 50n, mt_index: mt };
      assert.equal(mstate(dealId, 1), 1n);
    });

    test('funding beyond count rejected', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      const deposit = mkCoin(50n);
      await assert.rejects(
        () => call(agent, 'createMilestone', dealId, 50n, FAR, FAR + 1n, deposit),
        /all milestones already funded/
      );
    });

    test('ORGANIZER WALL: organizer cannot fund (agent-only funding)', async () => {
      const dealId = await newDeal({ count: 2 });
      const deposit = mkCoin(50n);
      await assert.rejects(
        () => call(org, 'createMilestone', dealId, 50n, FAR, FAR + 1n, deposit),
        /only agent can fund/
      );
    });

    test('attacker cannot fund', async () => {
      const dealId = await newDeal({ count: 2 });
      const deposit = mkCoin(50n);
      await assert.rejects(
        () => call(anyone, 'createMilestone', dealId, 50n, FAR, FAR + 1n, deposit),
        /only agent can fund/
      );
    });
  });

  describe('happy path: sequential 3-milestone deal', () => {
    test('fund-release-fund-release-fund-refund with correct payouts', async () => {
      // the sequential gate REQUIRES one funded milestone at a time —
      // funding all three up front would (correctly) be rejected.
      // payout baseline: zswap outputs accumulate across the WHOLE suite,
      // so this test asserts deltas from its own baseline.
      const orgBefore = paidTo(ORG_PK);
      const agentBefore = paidTo(AGENT_PK);
      const dealId = await newDeal({ count: 3, milestones: [{ amount: 10n }] });

      // m0: release (organizer confirms) -> organizer paid 10
      await call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      assert.equal(mstate(dealId, 0), 3n);
      let p = lastPayout();
      assert.equal(p.toUser, true);
      assert.deepEqual(p.pk, ORG_PK.bytes);
      assert.equal(p.value, 10n);

      // m1: fund -> release -> organizer paid 20 more
      const d1 = mkCoin(20n);
      const mt1 = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      await call(agent, 'createMilestone', dealId, 20n, FAR, FAR + 1n, d1);
      SPEND[mkey(dealId, 1)] = { nonce: d1.nonce, color: d1.color, value: 20n, mt_index: mt1 };
      await call(org, 'releaseMilestone', dealId, 1n, SPEND[mkey(dealId, 1)]);
      assert.equal(mstate(dealId, 1), 3n);

      // m2: fund -> refund (agent cancels) -> agent paid back 30
      const d2 = mkCoin(30n);
      const mt2 = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      await call(agent, 'createMilestone', dealId, 30n, FAR, FAR + 1n, d2);
      SPEND[mkey(dealId, 2)] = { nonce: d2.nonce, color: d2.color, value: 30n, mt_index: mt2 };
      await call(agent, 'refundMilestone', dealId, 2n, SPEND[mkey(dealId, 2)]);
      assert.equal(mstate(dealId, 2), 4n);
      p = lastPayout();
      assert.deepEqual(p.pk, AGENT_PK.bytes);
      assert.equal(p.value, 30n);

      // totals (deltas): organizer 10+20=30, agent 30 back
      assert.equal(paidTo(ORG_PK) - orgBefore, 30n);
      assert.equal(paidTo(AGENT_PK) - agentBefore, 30n);
    });
  });

  describe('releaseMilestone walls', () => {
    test('AGENT WALL: agent cannot release (organizer-only)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(agent, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only organizer can release/
      );
    });

    test('attacker cannot release', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(anyone, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only organizer can release/
      );
    });

    test('wrong coin rejected (nonce swap attack)', async () => {
      const dealId = await newDeal({ count: 2, milestones: [{ amount: 100n }] });
      await call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      // try acting on m1 with m0's (already spent) coin
      const d1 = mkCoin(50n);
      const mt1 = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      await call(agent, 'createMilestone', dealId, 50n, FAR, FAR + 1n, d1);
      SPEND[mkey(dealId, 1)] = { nonce: d1.nonce, color: d1.color, value: 50n, mt_index: mt1 };
      await assert.rejects(
        () => call(org, 'releaseMilestone', dealId, 1n, SPEND[mkey(dealId, 0)]),
        /coin does not match custody/
      );
    });

    test('final milestone blocks release (no double release)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      await assert.rejects(
        () => call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in HELD/
      );
    });

    test('DISPUTED blocks release', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in HELD/
      );
    });
  });

  describe('refundMilestone walls', () => {
    test('ORGANIZER WALL: organizer cannot refund', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(org, 'refundMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only agent can refund/
      );
    });

    test('claim deadline passed blocks agent refund (auto-release applies)', async () => {
      // deadline AND claimDeadline both in the past (claim > deadline holds)
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: PAST, claimDeadline: PAST + 1n }] });
      await assert.rejects(
        () => call(agent, 'refundMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /auto-release applies/
      );
    });

    test('refund pays the agent key', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'refundMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      const p = lastPayout();
      assert.equal(p.toUser, true);
      assert.deepEqual(p.pk, AGENT_PK.bytes);
      assert.equal(p.value, 100n);
    });
  });

  describe('timeout + autoRelease liveness', () => {
    test('timeoutRefund before deadline rejected', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: FAR }] });
      await assert.rejects(
        () => call(anyone, 'timeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /refund deadline not yet passed/
      );
    });

    test('timeoutRefund after deadline by ANYONE pays agent key', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: PAST }] });
      await call(anyone, 'timeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]);
      assert.equal(mstate(dealId, 0), 4n);
      const p = lastPayout();
      assert.deepEqual(p.pk, AGENT_PK.bytes, 'anyone triggers, agent is paid');
      assert.equal(p.value, 100n);
    });

    test('autoRelease after claim deadline by ANYONE pays organizer key', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: PAST, claimDeadline: PAST + 1n }] });
      await call(anyone, 'autoRelease', dealId, 0n, SPEND[mkey(dealId, 0)]);
      assert.equal(mstate(dealId, 0), 3n);
      const p = lastPayout();
      assert.deepEqual(p.pk, ORG_PK.bytes);
      assert.equal(p.value, 100n);
    });

    test('autoRelease before claim deadline rejected', async () => {
      // default deadlines (FAR / FAR+1): claim deadline not yet passed
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(anyone, 'autoRelease', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /claim deadline not yet passed/
      );
    });

    test('RELEASED blocks timeoutRefund (no double spend)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: PAST }] });
      await call(org, 'releaseMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]);
      await assert.rejects(
        () => call(anyone, 'timeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in HELD/
      );
    });
  });

  describe('dispute path', () => {
    test('agent opens dispute (HELD -> DISPUTED)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      assert.equal(mstate(dealId, 0), 2n);
    });

    test('organizer opens dispute (HELD -> DISPUTED)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(org, 'organizerOpenDispute', dealId, 0n);
      assert.equal(mstate(dealId, 0), 2n);
    });

    test('ORGANIZER WALL: organizer cannot open a dispute as the agent', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(org, 'agentOpenDispute', dealId, 0n),
        /only agent can open this dispute/
      );
    });

    test('AGENT WALL: agent cannot open a dispute as the organizer', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(agent, 'organizerOpenDispute', dealId, 0n),
        /only organizer can open this dispute/
      );
    });

    test('non-party cannot open either dispute', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(anyone, 'agentOpenDispute', dealId, 0n),
        /only agent can open this dispute/
      );
      await assert.rejects(
        () => call(anyone, 'organizerOpenDispute', dealId, 0n),
        /only organizer can open this dispute/
      );
    });

    test('timeout refund blocked while DISPUTED', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: PAST }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(anyone, 'timeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in HELD/
      );
    });

    test('autoRelease blocked while DISPUTED', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n, deadline: PAST, claimDeadline: PAST + 1n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(anyone, 'autoRelease', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in HELD/
      );
    });

    test('agent refund blocked while DISPUTED', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(agent, 'refundMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in HELD/
      );
    });

    test('arbiter rules for organizer (DISPUTED -> ARB_RELEASED, organizer paid)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await call(arbiter, 'arbiterRelease', dealId, 0n, SPEND[mkey(dealId, 0)]);
      assert.equal(mstate(dealId, 0), 5n);
      const p = lastPayout();
      assert.deepEqual(p.pk, ORG_PK.bytes);
      assert.equal(p.value, 100n);
    });

    test('arbiter rules for agent (DISPUTED -> ARB_REFUNDED, agent paid)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(org, 'organizerOpenDispute', dealId, 0n);
      await call(arbiter, 'arbiterRefund', dealId, 0n, SPEND[mkey(dealId, 0)]);
      assert.equal(mstate(dealId, 0), 6n);
      const p = lastPayout();
      assert.deepEqual(p.pk, AGENT_PK.bytes);
      assert.equal(p.value, 100n);
    });

    test('ARBITER WALL: agent cannot rule', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(agent, 'arbiterRelease', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only arbiter can rule/
      );
    });

    test('ARBITER WALL: organizer cannot rule', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(org, 'organizerOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(org, 'arbiterRelease', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only arbiter can rule/
      );
    });

    test('ARBITER WALL: attacker cannot rule', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(anyone, 'arbiterRefund', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only arbiter can rule/
      );
    });

    test('arbiter ruling blocked while HELD (must dispute first)', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(arbiter, 'arbiterRelease', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in DISPUTED/
      );
    });

    test('arbiterTimeoutRefund: vanished arbiter cannot freeze funds (ANYONE pays agent)', async () => {
      // arbDeadline = PAST forces the hatch open
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }], arbDeadline: PAST });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await call(anyone, 'arbiterTimeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]);
      assert.equal(mstate(dealId, 0), 6n);
      const p = lastPayout();
      assert.deepEqual(p.pk, AGENT_PK.bytes);
      assert.equal(p.value, 100n);
    });

    test('arbiterTimeoutRefund before arbiter deadline rejected', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }], arbDeadline: FAR });
      await call(agent, 'agentOpenDispute', dealId, 0n);
      await assert.rejects(
        () => call(anyone, 'arbiterTimeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /arbiter deadline not yet passed/
      );
    });

    test('arbiterTimeoutRefund blocked while HELD', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 100n }] });
      await assert.rejects(
        () => call(anyone, 'arbiterTimeoutRefund', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /milestone not in DISPUTED/
      );
    });
  });

  describe('cross-deal isolation', () => {
    test('agent2 cannot act on agent1\'s deal', async () => {
      const dealId = await newDeal({ count: 1, milestones: [{ amount: 50n }] });
      await assert.rejects(
        () => call(agent2, 'refundMilestone', dealId, 0n, SPEND[mkey(dealId, 0)]),
        /only agent can refund/
      );
    });
  });
});
