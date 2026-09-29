/**
 * EverList escrow contract - OFFLINE state-machine tests (M3 funded increment).
 *
 * Runs the REAL compiled circuits (managed/contract) against a simulated
 * ledger via compact-runtime. No proof server, no network.
 *
 * M3: escrows are FUNDED — createEscrow deposits an exact-value shielded
 * coin into contract custody (receiveShielded); release/refund/timeout spend
 * it to payout keys stored at creation (sendShielded), so even the
 * permissionless timeout cannot redirect funds.
 *
 * Runtime semantics: circuit calls do NOT mutate the shared ContractState
 * in place - each call returns a NEW context holding the mutated ledger.
 * The harness threads ONE evolving context through every call. Coin facts
 * learned by probe-m3-coins.mjs: pk args are {bytes: Uint8Array(32)}, spend
 * coins carry mt_index (snake_case), and a deposit's merkle index equals
 * comIndices.size captured immediately BEFORE the create call.
 *
 * Run: npx tsx --test test/escrow.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed/contract/index.js';

const b32 = (s) => {
  const a = new Uint8Array(32);
  a.set(new TextEncoder().encode(s).slice(0, 32));
  return a;
};

// witness sets: honest parties + attacker (different secrets)
const mkWitnesses = (agentSk, orgSk) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
});

const AGENT_SK = new Uint8Array(32).fill(1);
const ORG_SK = new Uint8Array(32).fill(2);
const ATTACKER_SK = new Uint8Array(32).fill(9);

// coin public keys (payout destinations) — struct {bytes} per generated bindings
const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };

// block-time deadlines (seconds): 'far future' is always before deadline in a
// default-time context (now ≈ 1.78e9), 'past' is always after it
const DEADLINE_FAR = 99999999999n;
const DEADLINE_PAST = 1000n;

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64); // dummy CoinPublicKey (string form, context ctor)
const COLOR = b32('tDUST');

let ctx;        // evolving circuit context: carries the mutated ledger
let honest;     // honest parties' contract handle
let attacker;   // attacker's contract handle (same ledger thread)
let organizerOnly; // organizer's machine: holds ONLY their own secret

let nonceCounter = 0;

/** Fresh deposit coin (unique nonce per coin). */
const mkCoin = (value) => {
  const nonce = new Uint8Array(32);
  nonce.set([++nonceCounter & 0xff]);
  return { nonce, color: COLOR, value };
};

/** Spend coin per escrow id (the deposited coin + its merkle index). */
const SPEND = {};

/** Call a circuit on the shared context thread; adopt the returned context. */
const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

/** Current ledger view from the evolving context. */
const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);

/** Cumulative zswap outputs of the thread (deposits + payouts). */
const zswapOutputs = () => ctx.callContext.currentZswapLocalState.outputs;

const newEscrow = async (amount, bookingRef, deadline = DEADLINE_FAR, claimDeadline = DEADLINE_FAR + 1n) => {
  const orgComm = pureCircuits.organizerCommitment(ORG_SK);
  const deposit = mkCoin(amount);
  // the deposit's commitment occupies the next free merkle index
  const mt = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
  await call(honest, 'createEscrow', amount, orgComm, bookingRef, deadline, claimDeadline, deposit, AGENT_PK, ORG_PK);
  const id = readLedger().escrows.size();
  SPEND[id] = { nonce: deposit.nonce, color: deposit.color, value: amount, mt_index: mt };
  return id;
};

describe('EverList escrow state machine (offline, real compiled circuits)', () => {
  before(async () => {
    honest = new Contract(mkWitnesses(AGENT_SK, ORG_SK));
    attacker = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK));
    // organizer's real machine: knows ONLY its own secret - any agent-role
    // witness it supplies can only return that same secret
    organizerOnly = new Contract(mkWitnesses(ORG_SK, ORG_SK));
    const ps = null; // circuits declare no private state

    // deploy-time constructor: initializes Counter/Map cells in the ledger
    const ctor = await honest.initialState(createConstructorContext(ps, COIN_PK));

    // seed the context thread from the constructor's state
    ctx = createCircuitContext('createEscrow', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('pure commitments', () => {
    test('commitments are deterministic and prefix-separated', () => {
      const a1 = pureCircuits.agentCommitment(AGENT_SK);
      const a2 = pureCircuits.agentCommitment(AGENT_SK);
      const o1 = pureCircuits.organizerCommitment(AGENT_SK);
      assert.deepEqual(a1, a2);
      assert.notDeepEqual(a1, o1, 'same secret must give different commitments per role');
      assert.equal(a1.length, 32);
    });
  });

  describe('createEscrow', () => {
    test('creates FUNDED escrow #1 in HELD state with custody + payout keys', async () => {
      const orgComm = pureCircuits.organizerCommitment(ORG_SK);
      const deposit = mkCoin(250n);
      await call(honest, 'createEscrow', 250n, orgComm, b32('even-13'), DEADLINE_FAR, DEADLINE_FAR + 1n, deposit, AGENT_PK, ORG_PK);
      const l = readLedger();
      assert.equal(l.nextId, 1n);
      const e = l.escrows.lookup(1n);
      assert.equal(e.amount, 250n);
      assert.equal(e.state, 1n); // HELD
      assert.deepEqual(e.bookingRef, b32('even-13'));
      assert.deepEqual(e.coinNonce, deposit.nonce); // custody recorded
      assert.deepEqual(e.coinColor, COLOR);
      assert.deepEqual(l.agentPks.lookup(1n), AGENT_PK); // payout destinations fixed
      assert.deepEqual(l.organizerPks.lookup(1n), ORG_PK);
      const aComm = pureCircuits.agentCommitment(AGENT_SK);
      assert.deepEqual(e.agentCommitment, aComm);
    });

    test('rejects amount 0', async () => {
      const orgComm = pureCircuits.organizerCommitment(ORG_SK);
      await assert.rejects(
        () => call(honest, 'createEscrow', 0n, orgComm, b32('x'), DEADLINE_FAR, DEADLINE_FAR + 1n, mkCoin(250n), AGENT_PK, ORG_PK),
        /amount must be positive/
      );
    });
  });

  describe('funded flows (M3: coin balances move)', () => {
    test('deposit value must equal escrow amount', async () => {
      const orgComm = pureCircuits.organizerCommitment(ORG_SK);
      await assert.rejects(
        () => call(honest, 'createEscrow', 9n, orgComm, b32('even-31'), DEADLINE_FAR, DEADLINE_FAR + 1n, mkCoin(8n), AGENT_PK, ORG_PK),
        /deposit must equal escrow amount/
      );
    });

    test('deposit lands in contract custody (zswap output to the contract)', async () => {
      await newEscrow(5n, b32('even-30'));
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, false, 'custody coin goes to the contract address');
      assert.equal(o.coinInfo.value, 5n);
    });

    test('release pays the organizer (zswap output to ORG_PK)', async () => {
      const id = await newEscrow(6n, b32('even-32'));
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, true, 'payout goes to a user coin key');
      assert.deepEqual(o.recipient.left.bytes, ORG_PK.bytes);
      assert.equal(o.coinInfo.value, 6n);
    });

    test('refund pays the agent (zswap output to AGENT_PK)', async () => {
      const id = await newEscrow(7n, b32('even-33'));
      await call(honest, 'refundEscrow', id, SPEND[id]);
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, true);
      assert.deepEqual(o.recipient.left.bytes, AGENT_PK.bytes);
      assert.equal(o.coinInfo.value, 7n);
    });

    test('permissionless timeout pays the AGENT (destination not choosable by caller)', async () => {
      const id = await newEscrow(8n, b32('even-34'), DEADLINE_PAST);
      await call(attacker, 'timeoutRefund', id, SPEND[id]); // anyone triggers...
      const o = zswapOutputs().at(-1);
      assert.deepEqual(o.recipient.left.bytes, AGENT_PK.bytes); // ...but agent is paid
      assert.equal(o.coinInfo.value, 8n);
    });

    test('spend with forged coin nonce rejected (custody wall)', async () => {
      const id = await newEscrow(9n, b32('even-35'));
      const forged = { ...SPEND[id], nonce: new Uint8Array(32).fill(99) };
      await assert.rejects(
        () => call(honest, 'releaseEscrow', id, forged),
        (err) => /custody|commitment|coin/i.test(err.message)
      );
    });
  });

  describe('isHeld', () => {
    test('true while HELD, false afterwards', async () => {
      const id = await newEscrow(10n, b32('even-2'));
      const r1 = await call(honest, 'isHeld', id);
      assert.equal(r1.result, true);
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      const r2 = await call(honest, 'isHeld', id);
      assert.equal(r2.result, false);
    });
  });

  describe('releaseEscrow', () => {
    test('organizer releases HELD -> RELEASED', async () => {
      const id = await newEscrow(50n, b32('even-3'));
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 2n); // RELEASED
    });

    test('attacker (wrong secrets) cannot release', async () => {
      const id = await newEscrow(60n, b32('even-4'));
      await assert.rejects(
        () => call(attacker, 'releaseEscrow', id, SPEND[id]),
        /only organizer can release/
      );
    });

    test('double-release rejected (not HELD)', async () => {
      const id = await newEscrow(70n, b32('even-5'));
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      await assert.rejects(
        () => call(honest, 'releaseEscrow', id, SPEND[id]),
        /not in HELD state/
      );
    });
  });

  describe('refundEscrow', () => {
    test('agent refunds HELD -> REFUNDED', async () => {
      const id = await newEscrow(80n, b32('even-6'));
      await call(honest, 'refundEscrow', id, SPEND[id]);
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 3n); // REFUNDED
    });

    test('attacker (wrong secrets) cannot refund', async () => {
      const id = await newEscrow(90n, b32('even-7'));
      await assert.rejects(
        () => call(attacker, 'refundEscrow', id, SPEND[id]),
        /only agent can refund/
      );
    });

    test('organizer cannot refund (role wall)', async () => {
      const id = await newEscrow(100n, b32('even-8'));
      // organizer's machine supplies ORG_SK as the agent secret -> commitment mismatch
      await assert.rejects(
        () => call(organizerOnly, 'refundEscrow', id, SPEND[id]),
        /only agent can refund/
      );
    });

    test('refund after release rejected (not HELD)', async () => {
      const id = await newEscrow(110n, b32('even-9'));
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      await assert.rejects(
        () => call(honest, 'refundEscrow', id, SPEND[id]),
        /not in HELD state/
      );
    });
  });

  describe('timeoutRefund (M4: permissionless liveness)', () => {
    test('deadline is stored at creation', async () => {
      const id = await newEscrow(15n, b32('even-15'), DEADLINE_PAST);
      assert.equal(readLedger().escrows.lookup(id).deadline, DEADLINE_PAST);
    });

    test('before deadline rejects', async () => {
      const id = await newEscrow(20n, b32('even-16'), DEADLINE_FAR);
      await assert.rejects(
        () => call(honest, 'timeoutRefund', id, SPEND[id]),
        /deadline not reached yet/
      );
    });

    test('after deadline refunds — and the ATTACKER can trigger it (permissionless)', async () => {
      const id = await newEscrow(30n, b32('even-17'), DEADLINE_PAST);
      await call(attacker, 'timeoutRefund', id, SPEND[id]); // anyone, no secrets needed
      assert.equal(readLedger().escrows.lookup(id).state, 3n); // REFUNDED
    });

    test('timeout after release rejected (not HELD)', async () => {
      const id = await newEscrow(40n, b32('even-18'), DEADLINE_PAST);
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      await assert.rejects(
        () => call(honest, 'timeoutRefund', id, SPEND[id]),
        /not in HELD state/
      );
    });

    test('timeout after agent refund rejected (not HELD)', async () => {
      const id = await newEscrow(50n, b32('even-19'), DEADLINE_PAST);
      await call(honest, 'refundEscrow', id, SPEND[id]);
      await assert.rejects(
        () => call(honest, 'timeoutRefund', id, SPEND[id]),
        /not in HELD state/
      );
    });
  });

  describe('ledger invariants', () => {
    test('ids are monotonic; unknown id rejected', async () => {
      const before = readLedger().nextId;
      await newEscrow(1n, b32('even-10'));
      assert.equal(readLedger().nextId, before + 1n);
      await assert.rejects(
        () => call(honest, 'isHeld', 9999n),
        /escrow not found/
      );
    });
  });

  describe('mutualRefund (M16: mutual refund after settlement)', () => {
    /** Release an escrow, then mint the organizer's equivalent return coin. */
    const releaseAndReturn = async (amount, ref) => {
      const id = await newEscrow(amount, ref);
      await call(honest, 'releaseEscrow', id, SPEND[id]); // organizer paid; original coin gone
      const ret = mkCoin(amount); // fresh coin, same asset + amount
      ret.mt_index = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      return { id, ret };
    };

    test('BOTH parties consent: RELEASED -> REFUNDED, agent paid at stored key', async () => {
      const { id, ret } = await releaseAndReturn(300n, b32('m16-1'));
      await call(honest, 'mutualRefund', id, ret); // honest machine proves BOTH commitments
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 3n); // REFUNDED
      const o = zswapOutputs().at(-1);
      assert.equal(o.recipient.is_left, true);
      assert.deepEqual(o.recipient.left.bytes, AGENT_PK.bytes, 'payout locked to agent key');
      assert.equal(o.coinInfo.value, 300n);
    });

    test('buyer alone (no organizer consent) rejected', async () => {
      const { id, ret } = await releaseAndReturn(310n, b32('m16-2'));
      const agentOnly = new Contract(mkWitnesses(AGENT_SK, AGENT_SK)); // agent machine: only its own secret
      await assert.rejects(
        () => call(agentOnly, 'mutualRefund', id, ret),
        /organizer consent missing/
      );
    });

    test('merchant alone (no buyer consent) rejected', async () => {
      const { id, ret } = await releaseAndReturn(320n, b32('m16-3'));
      await assert.rejects(
        () => call(organizerOnly, 'mutualRefund', id, ret),
        /agent consent missing/
      );
    });

    test('attacker (neither secret) rejected', async () => {
      const { id, ret } = await releaseAndReturn(330n, b32('m16-4'));
      await assert.rejects(
        () => call(attacker, 'mutualRefund', id, ret),
        /consent missing/
      );
    });

    test('wrong state: HELD escrow rejected', async () => {
      const id = await newEscrow(340n, b32('m16-5'));
      const ret = mkCoin(340n);
      ret.mt_index = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      await assert.rejects(
        () => call(honest, 'mutualRefund', id, ret),
        /not in RELEASED state/
      );
    });

    test('replay: second mutual refund on REFUNDED escrow rejected', async () => {
      const { id, ret } = await releaseAndReturn(350n, b32('m16-6'));
      await call(honest, 'mutualRefund', id, ret);
      const ret2 = mkCoin(350n);
      ret2.mt_index = BigInt(ctx.callContext.currentQueryContext.comIndices.size);
      await assert.rejects(
        () => call(honest, 'mutualRefund', id, ret2),
        /not in RELEASED state/
      );
    });

    test('underpaying return coin rejected (organizer keeps nothing back)', async () => {
      const { id, ret } = await releaseAndReturn(360n, b32('m16-7'));
      const short = mkCoin(359n);
      short.mt_index = ret.mt_index;
      await assert.rejects(
        () => call(honest, 'mutualRefund', id, short),
        /return coin wrong amount/
      );
    });

    test('wrong-asset return coin rejected', async () => {
      const { id, ret } = await releaseAndReturn(370n, b32('m16-8'));
      const other = { nonce: ret.nonce, color: b32('other-coin'), value: 370n, mt_index: ret.mt_index };
      await assert.rejects(
        () => call(honest, 'mutualRefund', id, other),
        /return coin wrong asset/
      );
    });

    test('unknown escrow id rejected', async () => {
      const ret = mkCoin(1n);
      ret.mt_index = 0n;
      await assert.rejects(
        () => call(honest, 'mutualRefund', 9999n, ret),
        /escrow not found/
      );
    });
  });


  describe('autoRelease (M17: merchant auto-release after quiet claim deadline)', () => {
    test('claim deadline stored at creation, strictly after refund deadline', async () => {
      const id = await newEscrow(11n, b32('m17-0'));
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.claimDeadline, DEADLINE_FAR + 1n);
    });

    test('create rejects claimDeadline <= refund deadline', async () => {
      const orgComm = pureCircuits.organizerCommitment(ORG_SK);
      await assert.rejects(
        () => call(honest, 'createEscrow', 1n, orgComm, b32('m17-bad'), DEADLINE_FAR, DEADLINE_FAR, mkCoin(1n), AGENT_PK, ORG_PK),
        /claim deadline must be after refund deadline/
      );
    });

    test('BEFORE claim deadline: autoRelease rejected (buyer window still open)', async () => {
      const id = await newEscrow(12n, b32('m17-1'));
      await assert.rejects(
        () => call(attacker, 'autoRelease', id, SPEND[id]),
        /claim deadline not reached yet/
      );
    });

    test('AFTER claim deadline: autoRelease pays the ORGANIZER — even from the ATTACKER (permissionless)', async () => {
      const id = await newEscrow(13n, b32('m17-2'), DEADLINE_PAST, DEADLINE_PAST + 1n);
      await call(attacker, 'autoRelease', id, SPEND[id]); // anyone triggers...
      const e = readLedger().escrows.lookup(id);
      assert.equal(e.state, 2n); // RELEASED
      const o = zswapOutputs().at(-1);
      assert.deepEqual(o.recipient.left.bytes, ORG_PK.bytes, 'payout locked to organizer key');
      assert.equal(o.coinInfo.value, 13n);
    });

    test('AFTER claim deadline: buyer refundEscrow walled (no eternal clawback)', async () => {
      const id = await newEscrow(14n, b32('m17-3'), DEADLINE_PAST, DEADLINE_PAST + 1n);
      await assert.rejects(
        () => call(honest, 'refundEscrow', id, SPEND[id]),
        /claim deadline passed - merchant auto-release applies/
      );
    });

    test('AFTER claim deadline: timeoutRefund walled too', async () => {
      const id = await newEscrow(15n, b32('m17-4'), DEADLINE_PAST, DEADLINE_PAST + 1n);
      await assert.rejects(
        () => call(attacker, 'timeoutRefund', id, SPEND[id]),
        /claim deadline passed - merchant auto-release applies/
      );
    });

    test('autoRelease after release rejected (not HELD)', async () => {
      const id = await newEscrow(16n, b32('m17-5'), DEADLINE_PAST, DEADLINE_PAST + 1n);
      await call(honest, 'releaseEscrow', id, SPEND[id]);
      await assert.rejects(
        () => call(honest, 'autoRelease', id, SPEND[id]),
        /not in HELD state/
      );
    });

    test('autoRelease after agent refund rejected (not HELD)', async () => {
      const id = await newEscrow(17n, b32('m17-6'), DEADLINE_PAST, DEADLINE_PAST + 1n);
      await assert.rejects(
        () => call(honest, 'refundEscrow', id, SPEND[id]),
        /claim deadline passed/
      );
    });
  });

});
