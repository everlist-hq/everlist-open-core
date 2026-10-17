/**
 * EverList reputation contract - OFFLINE tests (techmining P1 #2).
 *
 * Runs the REAL compiled circuits (managed-reputation/contract) against a
 * simulated ledger via compact-runtime. No proof server, no network.
 *
 * Party-accurate instances (role-wall pattern):
 *   hub      - the settlement RECORDER: knows the issuer secret, NOT any
 *              agent secret (its agent witness holds attacker junk — any
 *              accidental agent-side success would be caught)
 *   agent    - the agent's machine: knows ONLY its own pseudonym secret
 *   attacker - knows nothing real
 *
 * Run: npx tsx --test test/reputation.test.ts
 */
import { test, describe, before } from 'node:test';
import assert from 'node:assert/strict';
import {
  createCircuitContext,
  createConstructorContext,
} from '@midnight-ntwrk/compact-runtime';
import { dummyContractAddress } from '@midnightntwrk/onchain-runtime-v4';
import { Contract, pureCircuits, ledger } from '../managed-reputation/contract/index.js';

const mkWitnesses = (agentSk, issuerSk) => ({
  agentSecretKey: (ctxt) => [ctxt.privateState, agentSk],
  issuerSecretKey: (ctxt) => [ctxt.privateState, issuerSk],
});

const HUB_SK = new Uint8Array(32).fill(1);      // hub issuer secret
const AGENT_SK = new Uint8Array(32).fill(2);    // agent #1 pseudonym secret
const AGENT2_SK = new Uint8Array(32).fill(5);    // agent #2 pseudonym secret
const ATTACKER_SK = new Uint8Array(32).fill(9);  // attacker junk

const ADDRESS = dummyContractAddress();
const COIN_PK = '0'.repeat(64);

let ctx;      // evolving circuit context
let hub;      // issuer machine (no agent secret)
let agent;    // agent machine (only its own secret)
let attacker; // knows nothing

const call = async (instance, name, ...args) => {
  const r = await instance.impureCircuits[name](ctx, ...args);
  ctx = r.context;
  return r;
};

const readLedger = () => ledger(ctx.callContext.currentQueryContext.state);

/** The agent's public pseudonym commitment (computable by anyone). */
const agentComm = () => pureCircuits.agentReputationCommitment(AGENT_SK);
const agent2Comm = () => pureCircuits.agentReputationCommitment(AGENT2_SK);

/** Record a settlement like the hub would after an on-chain RELEASED check. */
const record = async (comm, volume, rating) =>
  call(hub, 'recordSettlement', comm, volume, rating);

describe('EverList agent reputation (offline, real compiled circuits)', () => {
  before(async () => {
    hub = new Contract(mkWitnesses(ATTACKER_SK, HUB_SK));
    agent = new Contract(mkWitnesses(AGENT_SK, ATTACKER_SK));
    attacker = new Contract(mkWitnesses(ATTACKER_SK, ATTACKER_SK));
    const ps = null;

    const ctor = await hub.initialState(createConstructorContext(ps, COIN_PK));
    ctx = createCircuitContext('initializeIssuer', ADDRESS, COIN_PK, ctor.currentContractState, ps);
  });

  describe('issuer lifecycle', () => {
    test('recording before initialization rejected', async () => {
      await assert.rejects(
        () => record(agentComm(), 100n, 5n),
        /issuer not initialized/
      );
    });

    test('first caller becomes THE settlement recorder', async () => {
      await call(hub, 'initializeIssuer');
      assert.ok(readLedger().issuer.member(0n));
    });

    test('issuer takeover impossible (second init rejected forever)', async () => {
      await assert.rejects(() => call(attacker, 'initializeIssuer'), /issuer already initialized/);
      await assert.rejects(() => call(hub, 'initializeIssuer'), /issuer already initialized/);
    });
  });

  describe('registerAgent', () => {
    test('secret holder registers their pseudonym with zero stats', async () => {
      await call(agent, 'registerAgent', agentComm());
      const led = readLedger();
      assert.ok(led.reputation.member(agentComm()));
      const rep = led.reputation.lookup(agentComm());
      assert.equal(rep.settledCount, 0n);
      assert.equal(rep.totalVolume, 0n);
      assert.equal(rep.ratingSum, 0n);
      assert.equal(rep.ratingCount, 0n);
    });

    test('FRONT-RUNNING WALL: attacker cannot register someone else\'s commitment', async () => {
      await assert.rejects(
        () => call(attacker, 'registerAgent', agent2Comm()),
        /only the secret holder can register this commitment/
      );
    });

    test('double registration rejected', async () => {
      await assert.rejects(
        () => call(agent, 'registerAgent', agentComm()),
        /agent already registered/
      );
    });
  });

  describe('recordSettlement (issuer-walled)', () => {
    test('ISSUER WALL: agent cannot record its own settlement', async () => {
      await assert.rejects(
        () => call(agent, 'recordSettlement', agentComm(), 100n, 5n),
        /only the issuer can record settlements/
      );
    });

    test('ISSUER WALL: attacker cannot record settlements', async () => {
      await assert.rejects(
        () => call(attacker, 'recordSettlement', agentComm(), 100n, 5n),
        /only the issuer can record settlements/
      );
    });

    test('unregistered pseudonym rejected', async () => {
      await assert.rejects(
        () => record(agent2Comm(), 100n, 5n),
        /agent not registered/
      );
    });

    test('invalid rating rejected (0 and 6)', async () => {
      await assert.rejects(() => record(agentComm(), 100n, 0n), /rating must be at least 1/);
      await assert.rejects(() => record(agentComm(), 100n, 6n), /rating must be at most 5/);
    });

    test('zero volume rejected', async () => {
      await assert.rejects(() => record(agentComm(), 0n, 5n), /volume must be positive/);
    });

    test('hub records settlements: count, volume and rating aggregates accumulate', async () => {
      await record(agentComm(), 120n, 5n);   // settled escrow #1
      await record(agentComm(), 30n, 3n);    // settled escrow #2
      const rep = readLedger().reputation.lookup(agentComm());
      assert.equal(rep.settledCount, 2n);
      assert.equal(rep.totalVolume, 150n);
      assert.equal(rep.ratingSum, 8n);       // 5 + 3
      assert.equal(rep.ratingCount, 2n);
      assert.equal(readLedger().settlementCount, 2n);
    });
  });

  describe('proveReputation (the ZK act)', () => {
    test('meets all thresholds: succeeds without revealing the secret', async () => {
      // stats: 2 settlements, 150 volume, avg rating 4.0 (8/2)
      await call(agent, 'proveReputation', 2n, 150n, 40n); // 40/10 = 4.0
    });

    test('fractional thresholds work (avg 4.5 with ratings 5,4 = 4.5)', async () => {
      await record(agentComm(), 50n, 4n);   // third settlement: avg = (8+4)/3 = 4.0
      await call(agent, 'proveReputation', 3n, 200n, 40n); // exactly 4.0
    });

    test('insufficient settlements rejected', async () => {
      await assert.rejects(
        () => call(agent, 'proveReputation', 4n, 200n, 40n),
        /insufficient settlements/
      );
    });

    test('insufficient volume rejected', async () => {
      await assert.rejects(
        () => call(agent, 'proveReputation', 3n, 201n, 40n),
        /insufficient volume/
      );
    });

    test('insufficient average rating rejected', async () => {
      // avg is 4.0 (12/3); demanding 4.1 (41) must fail
      await assert.rejects(
        () => call(agent, 'proveReputation', 3n, 200n, 41n),
        /insufficient average rating/
      );
    });

    test('unregistered agent rejected', async () => {
      await assert.rejects(
        () => call(attacker, 'proveReputation', 1n, 1n, 10n),
        /agent not registered/
      );
    });

    test('VACUOUS THRESHOLD: minSettlements=0 rejected by design', async () => {
      await assert.rejects(
        () => call(agent, 'proveReputation', 0n, 0n, 0n),
        /must demand at least one settlement/
      );
    });

    test('agent #2 (different pseudonym) is isolated: agent #1 cannot prove as #2', async () => {
      // agent #2 never registered; agent #1's machine proves only its own stats
      await assert.rejects(
        () => call(agent, 'proveReputation', 99n, 99n, 99n),
        /insufficient settlements/
      );
    });
  });

  describe('getStats (public read)', () => {
    test('anyone can read a pseudonym\'s stats', async () => {
      const r = await call(attacker, 'getStats', agentComm());
      assert.equal(r.result.settledCount, 3n);
      assert.equal(r.result.totalVolume, 200n);
    });

    test('unknown pseudonym rejected', async () => {
      const bogus = new Uint8Array(32).fill(42);
      await assert.rejects(() => call(attacker, 'getStats', bogus), /agent not registered/);
    });
  });
});