/**
 * M11 fee measurement: real per-circuit costs from the NATIVE proof server
 * (9.0.0-rc.7, :6301) via the official v9 wire format.
 *
 * Method (same as verified M1/probe-m4/probe-m16/probe-m17 runs):
 *  1. execute the full escrow lifecycle locally with the compact runtime
 *     (real ProofData captured per circuit from callProofDataTrace,
 *      relabeled by position - trace entries carry the context label);
 *  2. serialize each real preimage with ledger-v9's own
 *     proofDataIntoSerializedPreimage + tagged .bzkir IR;
 *  3. POST /check, parse costs, time the call.
 *
 * The cost matrix is what the DUST pricing model charges on.
 * Run from contract/: node measure-costs.mjs
 */
import { readFileSync, writeFileSync } from 'node:fs';

const { Contract, pureCircuits } = await import('./managed/contract/index.js');
const cr = await import('@midnight-ntwrk/compact-runtime');
const { dummyContractAddress } = await import('@midnightntwrk/onchain-runtime-v4');
const l9 = await import('/tmp/ledger-v9-rc4/package/midnight_ledger_wasm_v9_fs.js');

const b32 = (s) => {
  const a = new Uint8Array(32);
  a.set(new TextEncoder().encode(s).slice(0, 32));
  return a;
};
const AGENT_SK = new Uint8Array(32).fill(1);
const ORG_SK = new Uint8Array(32).fill(2);
const AGENT_PK = { bytes: new Uint8Array(32).fill(11) };
const ORG_PK = { bytes: new Uint8Array(32).fill(12) };
const COIN_PK = '0'.repeat(64);
const ADDRESS = dummyContractAddress();
const COLOR = b32('tDUST');

let nonceCounter = 0;
const mkCoin = (value) => {
  const nonce = new Uint8Array(32);
  nonce.set([++nonceCounter & 0xff]);
  return { nonce, color: COLOR, value };
};
const nextMt = (ctx) => BigInt(ctx.callContext.currentQueryContext.comIndices.size);

const witnesses = {
  agentSecretKey: (c) => [c.privateState, AGENT_SK],
  organizerSecretKey: (c) => [c.privateState, ORG_SK],

  arbiterSecretKey: (c) => [c.privateState, new Uint8Array(32).fill(5)], // W3.1 junk arbiter (unused in legacy flows)
};
const honest = new Contract(witnesses);
const attacker = new Contract({
  agentSecretKey: (c) => [c.privateState, new Uint8Array(32).fill(9)],
  organizerSecretKey: (c) => [c.privateState, new Uint8Array(32).fill(9)],
});
const ps = null;

const ctor = await honest.initialState(cr.createConstructorContext(ps, COIN_PK));
let ctx = cr.createCircuitContext('createEscrow', ADDRESS, COIN_PK, ctor.currentContractState, ps);

const captures = [];
const call = async (contract, name, ...args) => {
  const before = ctx.callProofDataTrace.length;
  const r = await contract.impureCircuits[name](ctx, ...args);
  if (r && r.context) ctx = r.context;
  if (ctx.callProofDataTrace.length === before) throw new Error(name + ' produced no proof data');
  captures.push({ name, pd: ctx.callProofDataTrace[ctx.callProofDataTrace.length - 1] });
  return r;
};


// escrow 1: deadlines past -> permissionless timeoutRefund by ATTACKER
const dep1 = mkCoin(75n); const mt1 = nextMt(ctx);
await call(honest, 'createEscrow', 75n, pureCircuits.organizerCommitment(ORG_SK, b32('m11-a')), b32('m11-a'), 1000n, 99999999999n, dep1, AGENT_PK, ORG_PK);
console.log('escrow 1 HELD (deadlines past)');
await call(attacker, 'timeoutRefund', 1n, { nonce: dep1.nonce, color: dep1.color, value: 75n, mt_index: mt1 });
console.log('escrow 1 REFUNDED via timeoutRefund (attacker-triggered)');

// escrow 2: live deadlines -> isHeld read -> agent self-refund
const dep2 = mkCoin(120n); const mt2 = nextMt(ctx);
await call(honest, 'createEscrow', 120n, pureCircuits.organizerCommitment(ORG_SK, b32('m11-b')), b32('m11-b'), 99999999999n, 100000000000n, dep2, AGENT_PK, ORG_PK);
console.log('escrow 2 HELD (live deadlines)');
await call(honest, 'isHeld', 2n);
console.log('isHeld read done');
await call(honest, 'refundEscrow', 2n, { nonce: dep2.nonce, color: dep2.color, value: 120n, mt_index: mt2 });
console.log('escrow 2 REFUNDED by agent');

// escrow 3: release (organizer paid) then mutualRefund (both consent, fresh return coin)
const dep3 = mkCoin(250n); const mt3 = nextMt(ctx);
await call(honest, 'createEscrow', 250n, pureCircuits.organizerCommitment(ORG_SK, b32('m11-c')), b32('m11-c'), 99999999999n, 100000000000n, dep3, AGENT_PK, ORG_PK);
console.log('escrow 3 HELD');
await call(honest, 'releaseEscrow', 3n, { nonce: dep3.nonce, color: dep3.color, value: 250n, mt_index: mt3 });
console.log('escrow 3 RELEASED (organizer paid)');
const ret = mkCoin(250n);
ret.mt_index = nextMt(ctx);
await call(honest, 'mutualRefund', 3n, ret);
console.log('escrow 3 REFUNDED via mutualRefund (dual consent)');

// escrow 4: claim deadline passed quietly -> autoRelease by ATTACKER (pays organizer)
const dep4 = mkCoin(60n); const mt4 = nextMt(ctx);
await call(honest, 'createEscrow', 60n, pureCircuits.organizerCommitment(ORG_SK, b32('m11-d')), b32('m11-d'), 1000n, 1001n, dep4, AGENT_PK, ORG_PK);
console.log('escrow 4 HELD (claim deadline passed)');
await call(attacker, 'autoRelease', 4n, { nonce: dep4.nonce, color: dep4.color, value: 60n, mt_index: mt4 });
console.log('escrow 4 RELEASED via autoRelease (attacker-triggered, organizer paid)');

// --- /check each captured circuit against the native proof server ---
const results = [];
for (const { name, pd } of captures) {
  const preimage = l9.proofDataIntoSerializedPreimage(
    pd.input, pd.output, pd.publicTranscript, pd.privateTranscriptOutputs, name
  );
  const ir = readFileSync(`managed/zkir/${name}.bzkir`);
  const payload = l9.createCheckPayload(preimage, ir);
  const t0 = Date.now();
  const res = await fetch('http://127.0.0.1:6301/check', {
    method: 'POST', body: payload,
    headers: { 'Content-Type': 'application/octet-stream' },
    signal: AbortSignal.timeout(60000),
  });
  const ms = Date.now() - t0;
  const body = new Uint8Array(await res.arrayBuffer());
  if (!res.ok) {
    console.log(`${name}: /check ${res.status} - ${new TextDecoder().decode(body.slice(0, 150))}`);
    results.push({ circuit: name, error: res.status });
    continue;
  }
  const costs = l9.parseCheckResult(body);
  const printable = JSON.parse(JSON.stringify(costs, (k, v) => (typeof v === 'bigint' ? v.toString() : v)));
  console.log(`=== ${name} === (${ms} ms)`);
  console.log(JSON.stringify(printable));
  results.push({ circuit: name, check_ms: ms, costs: printable });
}

writeFileSync('/tmp/m11/circuit-costs.json', JSON.stringify(results, null, 1));
console.log('\nsaved /tmp/m11/circuit-costs.json (' + results.length + ' circuits)');
