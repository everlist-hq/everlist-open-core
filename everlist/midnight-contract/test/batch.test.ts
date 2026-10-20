/**
 * W3.3 batch settlement - OFFLINE tests (batchRelease2).
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

const mkWitnesses = (agentSk, orgSk, arbSk = new Uint8Array(32).fill(5)) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  organizerSecretKey: (ctxt) => [ctxt.privateState, orgSk],
  arbiterSecretKey: (ctxt) => [ctxt.privateState, arbSk],
});

const AGENT_SK = new Uint8Array(32).fill(1);
const ORG_SK = new Uint8Array(32).fill(2);
const ATTACKER_SK = new Uint8Array(32).fill(9);

const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };

const DEADLINE_FAR = 99999999999n;
const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);
const COLOR = b32('tDUST');

let ctx;
let honest;
let attacker;
let organizerOnly;

let nonceCounter = 0;
const mkCoin = (value) => {
  const nonce = new Uint8Array(32);
  nonce.set([++nonceCounter & 0xff]);
  return { nonce, color: COLOR, value };
};

const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);

const orgComm = (sk, bookingRef) => pureCircuits.organizerCommitment(sk, bookingRef);

const createEscrow = async (instance, amount, bookingRef, orgCommIn) => {
  const id = readLedger().escrows.size();
  await call(instance, 'createEscrow', amount, orgCommIn, bookingRef,
    DEADLINE_FAR, DEADLINE_FAR + 1000n, mkCoin(amount), AGENT_PK, ORG_PK);
  const e = readLedger().escrows.lookup(id + 1n);
  const spend = {
    nonce: e.coinNonce,
    color: e.coinColor,
    value: e.amount,
    mt_index: BigInt(ctx.callContext.currentQueryContext.comIndices.size),
  };
  return [id + 1n, spend];
};

describe('W3.3 batchRelease2 (offline, real compiled circuits)', () => {
  before(async () => {
    honest = new Contract(mkWitnesses(AGENT_SK, ORG_SK));
    attacker = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK));
    organizerOnly = new Contract(mkWitnesses(ATTACKER_SK, ORG_SK));
    const ps = null;
    const ctor = await honest.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('createEscrow', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('happy path + walls', () => {
    test('two HELD escrows, same organizer -> ONE call releases BOTH', async () => {
      const ref1 = b32('batch-ref-1');
      const ref2 = b32('batch-ref-2');
      const [id1, spend1] = await createEscrow(honest, 100n, ref1, orgComm(ORG_SK, ref1));
      const [id2, spend2] = await createEscrow(honest, 200n, ref2, orgComm(ORG_SK, ref2));

      await call(organizerOnly, 'batchRelease2', id1, id2, spend1, spend2);

      const led = readLedger();
      assert.equal(led.escrows.lookup(id1).state, 2n); // RELEASED
      assert.equal(led.escrows.lookup(id2).state, 2n); // RELEASED
    });

    test('double batch-release rejected (both now RELEASED)', async () => {
      const ref3 = b32('batch-ref-3');
      const ref4 = b32('batch-ref-4');
      const [id3, spend3] = await createEscrow(honest, 50n, ref3, orgComm(ORG_SK, ref3));
      const [id4, spend4] = await createEscrow(honest, 60n, ref4, orgComm(ORG_SK, ref4));
      await call(organizerOnly, 'batchRelease2', id3, id4, spend3, spend4);
      await assert.rejects(
        () => call(organizerOnly, 'batchRelease2', id3, id4, spend3, spend4),
        /not in HELD/
      );
    });

    test('same escrow id twice rejected', async () => {
      const ref = b32('batch-ref-5');
      const [id, spend] = await createEscrow(honest, 70n, ref, orgComm(ORG_SK, ref));
      await assert.rejects(
        () => call(organizerOnly, 'batchRelease2', id, id, spend, spend),
        /ids must differ/
      );
    });

    test('different organizers -> rejected', async () => {
      const refA = b32('batch-ref-6a');
      const refB = b32('batch-ref-6b');
      const [idA, spendA] = await createEscrow(honest, 80n, refA, orgComm(ORG_SK, refA));
      const [idB, spendB] = await createEscrow(honest, 90n, refB, orgComm(ORG_SK, refB));
      await assert.rejects(
        () => call(organizerOnly, 'batchRelease2', idA, idB, spendA, spendB),
        /only organizer can release escrow 2/
      );
    });

    test('ATTACKER wall: wrong secret cannot batch-release', async () => {
      const refA = b32('batch-ref-7a');
      const refB = b32('batch-ref-7b');
      const [idA, spendA] = await createEscrow(honest, 30n, refA, orgComm(ORG_SK, refA));
      const [idB, spendB] = await createEscrow(honest, 40n, refB, orgComm(ORG_SK, refB));
      await assert.rejects(
        () => call(attacker, 'batchRelease2', idA, idB, spendA, spendB),
        /only organizer can release escrow 1/
      );
      assert.equal(readLedger().escrows.lookup(idA).state, 1n); // still HELD
    });
  });
});
