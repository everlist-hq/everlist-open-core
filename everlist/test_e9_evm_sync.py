"""E9: EVM mirror sync - POST /admin/sync-escrow-evm + arbsep-escrow rail.
Done-when (M7 twin, Arbitrum Sepolia rail):
  intake: HELD escrow with exact amount -> 201; wrong contract -> 400 (M14
  pin law); wrong amount -> 409; expired deadline -> 409; NONE escrow ->
  409 (fresh-id squatting refused); malformed shapes -> 400.
  sync: chain RELEASED + hub HELD -> updated (forward, chain wins); chain
  HELD + hub RELEASED -> REFUSED (never downward, C7); chain REFUNDED +
  hub RELEASED -> updated (M16 mutualRefund carve-out); ledger entries
  carry NO amount and are rail-tagged; volume totals unchanged; admin
  gating (403).
Hub runs with Midnight indexer UNSET + EVM pinned: proves the arbsep-escrow
rail gates standalone via the rail-aware _gate_wants_chain law.
Chain side = fixture JSON-RPC server serving escrows(bytes32) struct words
(9-word ABI, Escrow.sol layout) + eth_getLogs lifecycle events.
Run: python test_e9_evm_sync.py
"""
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RESULTS = []

def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

TMP = tempfile.mkdtemp(prefix="hub-e9-")
PORT = free_port(); BASE = "http://127.0.0.1:%d" % PORT; PYEXE = sys.executable
ADMIN = "dev-admin-key-change-me"
PIN = "0x" + "ab" * 20          # pinned escrow contract (fixture)
OTHER = "0x" + "cd" * 20        # a different contract (must be refused)
SELECTOR = "2d83549c"           # escrows(bytes32)
TOPIC = {1: "0x0c90ebc3b5432d9d194c40bee33cc9c11d0d1ed317d52df44bc438860d95c90d",
         2: "0x6eec2dd2382427616d4ea7ef183b16091feac4e2e63c8b55f25215f132df8d14",
         3: "0x193032d8b1ed8d859745ff29f4e02d2d01d4927c8d9018ffc9f828adcccc7ce8",
         4: "0x0ba174eb1c3530da63920b98261208eeb30b48447d1cfcbbdf116fd4ee8c62db"}

def eid(n):
    return "0x" + ("%064d" % n)

# fixture chain state: escrow id(slot hex) -> {state, amount, deadline, block}
NOW = int(time.time())
CHAIN = {}

def set_chain(n, state, amount_micro=50000000, deadline=None, arbiter_word="0" * 64,
              organizer_word=None):
    CHAIN[eid(n)[2:]] = {"state": state, "amount": amount_micro,
                         "deadline": NOW + 86400 if deadline is None else deadline,
                         "block": len(CHAIN) + 1, "arbiter_word": arbiter_word,
                         "organizer_word": organizer_word or ("0" * 24 + "22" * 20)}

def struct_hex(st):
    w = []
    # Real Solidity ABI right-aligns address fields (low 20 bytes of the word):
    # fixed 2026-11-18 when F2a exposed the words — the left-aligned encoding
    # was never readable by a correct ABI decoder (reader output proved it).
    w.append("0" * 24 + "11" * 20)          # buyer
    w.append(st.get("organizer_word", "0" * 24 + "22" * 20))  # organizer (F2c: per-escrow)
    w.append(st.get("arbiter_word", "0" * 64))  # arbiter (F2b: nonzero for wall tests)
    w.append("%064x" % st["amount"])
    w.append("%064x" % st["deadline"])
    w.append("%064x" % (st["deadline"] + 604800))
    w.append("%064x" % st["state"])
    w.append("0" * 64)
    w.append("0" * 64)
    return "0x" + "".join(w)

class ChainHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(n).decode())
        except ValueError:
            req = {}
        m = req.get("method")
        if m == "eth_chainId":
            result = "0x66eee"              # 421614
        elif m == "eth_call":
            data = (req["params"][0].get("data") or "")
            slot = data[2 + len(SELECTOR):2 + len(SELECTOR) + 64]
            st = CHAIN.get(slot)
            result = struct_hex(st) if st else "0x" + "0" * 576
        elif m == "eth_getLogs":
            topics = req["params"][0].get("topics") or [None]
            slot = (topics[1] if len(topics) > 1 and topics[1] else "")[2:]
            st = CHAIN.get(slot)
            logs = []
            if st and st["state"] in TOPIC:
                logs = [{"blockNumber": "%064x" % st["block"],
                         "topics": [TOPIC[st["state"]], "0x" + slot],
                         "transactionHash": "0x" + "bb" * 32, "data": "0x"}]
            result = logs
        else:
            result = None
        out = json.dumps({"jsonrpc": "2.0", "id": req.get("id", 1), "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass

CPORT = free_port()
cserver = ThreadingHTTPServer(("127.0.0.1", CPORT), ChainHandler)
threading.Thread(target=cserver.serve_forever, daemon=True).start()
EVMPIN = "http://127.0.0.1:%d" % CPORT

def req(method, path, body=None, headers=None):
    r = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception as e: return -1, {"error": str(e)}

# four fixture escrows: 1 intake-ok, 2 wrong-amount, 3 expired, 4 reserved
for n in (1, 2, 3, 4):
    set_chain(n, 1, amount_micro=50000000 if n != 2 else 1000000,
              deadline=None if n != 3 else NOW - 3600)

env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_POW_SIGNUP_BITS": "8", "HUB_RATE_BOOKS_PER_MIN": "1000",
       "HUB_EVM_ESCROW_ADDRESS": PIN, "HUB_EVM_RPC_URL": EVMPIN}
logf = open(os.path.join(TMP, "hub.log"), "a")
proc = subprocess.Popen([PYEXE, os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
end = time.time() + 15; ready = False
while time.time() < end:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5): ready = True; break
    except OSError: time.sleep(0.2)
assert ready, "test hub did not start"
EXTRA_PROCS = []  # F2b/F4 wall-test hubs; cleaned up in finally

try:
    print("== E9 setup: owner, paid listing, buyer ==")
    def solve_pow(kind):
        _, ch = req("GET", "/auth/challenge?kind=" + kind)
        n = 0
        while True:
            d = hashlib.sha256((ch["challenge"] + str(n)).encode()).digest()
            bits = 0
            for b in d:
                if b == 0: bits += 8; continue
                bits += 8 - b.bit_length(); break
            if bits >= ch["difficulty"]: return {"challenge": ch["challenge"], "nonce": n}
            n += 1
    c, a = req("POST", "/accounts/signup", {"agent": "e9-owner", "pow": solve_pow("signup")})
    assert c == 201, a
    c, l = req("POST", "/accounts/login", {"account_code": a["account_code"], "agent": "e9-owner"})
    assert c == 200, l
    OTOK = l["tokens"]["list"]
    c, r = req("POST", "/listings", {"vertical": "events", "title": "E9 Paid",
               "date": "2026-12-10", "location": "X", "price": 50, "capacity": 10,
               "receive_addr": "0x" + "22" * 20},
               {"X-Hub-Token": OTOK})
    assert c == 201, r
    PAID = r["id"]
    BUYER = "agent1qe9buyer"
    c, bt = req("POST", "/access", {"agent": BUYER, "acts": ["book"]})
    assert c == 201, bt
    B = {"X-Hub-Token": bt["tokens"]["book"]}

    print("== E9 intake: shape walls + M14 pin law + amount/deadline walls ==")
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN}}, B)
    check("missing escrow_id -> 400", c == 400, "%s %s" % (c, e))
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": OTHER,
                              "escrow_id": eid(1)}}, B)
    check("wrong contract -> 400 (M14 pin law)", c == 400, "%s %s" % (c, e))
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": "0x1234"}}, B)
    check("short escrow_id -> 400", c == 400, "%s %s" % (c, e))
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"contract": "c", "escrow_id": 1, "tx": "t"}}, B)
    check("midnight-shape ref without gating stored verbatim (legacy M5 law) -> 201",
          c == 201, "%s %s" % (c, e))
    if c == 201:
        check("legacy ref kept Midnight keys untouched",
              (e.get("escrow_ref") or {}).get("contract") == "c" and
              "escrow" not in (e.get("escrow_ref") or {}), str(e.get("escrow_ref")))
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(2)}}, B)
    check("wrong amount -> 409", c == 409, "%s %s" % (c, e))
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(3)}}, B)
    check("expired deadline -> 409", c == 409, "%s %s" % (c, e))
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "A", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(99)}}, B)
    check("NONE escrow -> refused (squatting wall)", c in (409, 503), "%s %s" % (c, e))
    c, ok = req("POST", "/book", {"listing_id": PAID, "attendee": "E9 Buyer", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(1)}}, B)
    check("HELD exact-amount escrow books -> 201", c == 201, "%s %s" % (c, ok))
    BID1 = ok.get("id") if c == 201 else None
    check("booking echoes normalized escrow_ref",
          (ok.get("escrow_ref") or {}).get("escrow") == PIN and
          (ok.get("escrow_ref") or {}).get("type") == "arbsep-escrow", str(ok.get("escrow_ref")))

    print("== E9 sync: gating ==")
    c, e = req("POST", "/admin/sync-escrow-evm", {}, {})
    check("no admin key -> 403", c == 403, "%s %s" % (c, e))
    c, e = req("POST", "/admin/sync-escrow-evm", {}, {"X-Admin-Key": "wrong"})
    check("wrong admin key -> 403", c == 403, str(c))

    print("== E9 sync: forward law ==")
    set_chain(1, 2)                       # chain RELEASED, hub HELD
    c, s = req("POST", "/admin/sync-escrow-evm", {}, {"X-Admin-Key": ADMIN})
    check("sync 200", c == 200, "%s %s" % (c, s))
    res = {r.get("booking_id"): r for r in s.get("results", [])}
    r1 = res.get(BID1, {})
    check("chain RELEASED + hub HELD -> updated", r1.get("action") == "updated",
          str(r1))
    check("updated carries chain_tx", len(r1.get("chain_tx", "")) == 64, str(r1))

    print("== E9 sync: downward + carve-out ==")
    # book 2: hub must stay HELD while chain HELD (in-sync) then refuse downward
    c, b2 = req("POST", "/book", {"listing_id": PAID, "attendee": "B2", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(2)}}, B)
    # booking 2 has wrong chain amount -> refused at intake; use fresh escrow 5
    set_chain(5, 1)
    c, b5 = req("POST", "/book", {"listing_id": PAID, "attendee": "B5", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(5)}}, B)
    assert c == 201, b5
    BID5 = b5["id"]
    _, led0 = req("GET", "/ledger")
    vol0 = led0["totals"]["total_volume"]
    # hub RELEASED without chain: confirm via admin token is chain-gated, so
    # stage divergence by hub-side flip through the dispute+sync pair instead:
    # chain 5 -> DISPUTED first (legal forward), sync mirrors DISPUTED, then
    # chain RELEASED (legal from DISPUTED), sync mirrors - forward-only proof.
    set_chain(5, 4)
    c, s = req("POST", "/admin/sync-escrow-evm", {}, {"X-Admin-Key": ADMIN})
    res = {r.get("booking_id"): r for r in s.get("results", [])}
    check("chain DISPUTED + hub HELD -> updated (forward)",
          res.get(BID5, {}).get("action") == "updated", str(res.get(BID5)))
    set_chain(5, 2)
    c, s = req("POST", "/admin/sync-escrow-evm", {}, {"X-Admin-Key": ADMIN})
    res = {r.get("booking_id"): r for r in s.get("results", [])}
    check("chain RELEASED from DISPUTED -> updated",
          res.get(BID5, {}).get("action") == "updated", str(res.get(BID5)))
    # downward: hub RELEASED, chain back to HELD - impossible on real chain,
    # fixture simulates operator-error divergence -> must REFUSE
    set_chain(5, 1)
    c, s = req("POST", "/admin/sync-escrow-evm", {}, {"X-Admin-Key": ADMIN})
    res = {r.get("booking_id"): r for r in s.get("results", [])}
    check("chain HELD + hub RELEASED -> refused (C7)",
          res.get(BID5, {}).get("action") == "refused" and
          "downward" in res.get(BID5, {}).get("reason", ""), str(res.get(BID5)))
    # M16 carve-out: chain REFUNDED while hub RELEASED (mutualRefund pre-withdraw)
    set_chain(5, 3)
    c, s = req("POST", "/admin/sync-escrow-evm", {}, {"X-Admin-Key": ADMIN})
    res = {r.get("booking_id"): r for r in s.get("results", [])}
    check("chain REFUNDED + hub RELEASED -> updated (M16 carve-out)",
          res.get(BID5, {}).get("action") == "updated", str(res.get(BID5)))
    c, s = req("POST", "/admin/sync-escrow-evm", {"booking_ids": ["bk-nope"]},
               {"X-Admin-Key": ADMIN})
    check("unknown booking id -> not-found",
          s.get("results", [{}])[0].get("action") == "not-found", str(s.get("results")))

    print("== E9 ledger laws ==")
    _, led1 = req("GET", "/ledger")
    sync_entries = [t for t in led1["ledger"] if t.get("kind") == "escrow_sync"
                    and t.get("rail") == "arbsep-escrow"]
    check("ledger has rail-tagged escrow_sync entries", len(sync_entries) >= 3,
          str(len(sync_entries)))
    check("sync entries carry NO amount key",
          all("amount" not in t for t in sync_entries), str(sync_entries[:1]))
    check("volume unchanged by sync (no double-count)",
          led1["totals"]["total_volume"] == vol0,
          "%s vs %s" % (led1["totals"]["total_volume"], vol0))

    print("== E9 dedupe across rails ==")
    c, e = req("POST", "/book", {"listing_id": PAID, "attendee": "Dup", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(1)}}, B)
    check("re-claiming booked escrow -> 409", c == 409, "%s %s" % (c, e))

    # ═══ review-wall proofs (2026-11-18 adversarial review F2b/F4/F8) ═══
    def mkreq(base):
        def _r(method, path, body=None, headers=None):
            r = urllib.request.Request(base + path, method=method,
                data=json.dumps(body).encode() if body is not None else None,
                headers={"Content-Type": "application/json", **(headers or {})})
            try:
                with urllib.request.urlopen(r, timeout=10) as resp:
                    return resp.status, json.loads(resp.read().decode())
            except urllib.error.HTTPError as ex:
                try: return ex.code, json.loads(ex.read().decode())
                except Exception: return ex.code, {}
            except Exception as ex: return -1, {"error": str(ex)}
        return _r

    def spawn_hub(extra_env, tag):
        p2 = free_port(); b2 = "http://127.0.0.1:%d" % p2
        e2 = {**env, "HUB_STATE_FILE": os.path.join(TMP, "state-%s.json" % tag), **extra_env}
        lg2 = open(os.path.join(TMP, "hub-%s.log" % tag), "a")
        pr2 = subprocess.Popen([PYEXE, os.path.join(HERE, "app.py"), str(p2)],
                               stdout=lg2, stderr=subprocess.STDOUT, env=e2)
        EXTRA_PROCS.append((pr2, lg2))
        rd2 = False; en2 = time.time() + 15
        while time.time() < en2:
            try:
                with socket.create_connection(("127.0.0.1", p2), timeout=0.5): rd2 = True; break
            except OSError: time.sleep(0.2)
        assert rd2, "%s test hub did not start" % tag
        return b2, mkreq(b2)

    def mini_flow(rq, tag):
        def _pow(kind):
            _, ch = rq("GET", "/auth/challenge?kind=" + kind)
            n = 0
            while True:
                d = hashlib.sha256((ch["challenge"] + str(n)).encode()).digest()
                bits = 0
                for b in d:
                    if b == 0: bits += 8; continue
                    bits += 8 - b.bit_length(); break
                if bits >= ch["difficulty"]: return {"challenge": ch["challenge"], "nonce": n}
                n += 1
        c, a2 = rq("POST", "/accounts/signup", {"agent": "e9-%s-owner" % tag, "pow": _pow("signup")})
        assert c == 201, a2
        c, l2 = rq("POST", "/accounts/login", {"account_code": a2["account_code"], "agent": "e9-%s-owner" % tag})
        assert c == 200, l2
        T2 = l2["tokens"]["list"]
        c, r2 = rq("POST", "/listings", {"vertical": "events", "title": "E9 %s" % tag,
                   "date": "2026-12-10", "location": "X", "price": 50, "capacity": 5,
                   "receive_addr": "0x" + "22" * 20},
                   {"X-Hub-Token": T2})
        assert c == 201, r2
        c, bt2 = rq("POST", "/access", {"agent": "agent1qe9%s" % tag, "acts": ["book"]})
        assert c == 201, bt2
        return r2["id"], {"X-Hub-Token": bt2["tokens"]["book"]}

    print("== E9 F4: RPC chain-id pin (fail-closed on mismatch) ==")
    _, rq4 = spawn_hub({"HUB_EVM_CHAIN_ID": "999"}, "f4")
    PAID4, B4 = mini_flow(rq4, "f4buyer")
    c, e4 = rq4("POST", "/book", {"listing_id": PAID4, "attendee": "F4", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(1)}}, B4)
    check("F4: RPC chain-id mismatch -> honest 503 (fail-closed)", c == 503, "%s %s" % (c, e4))

    print("== E9 F2b: hub-arbiter wall (sect 7.1.6 opt-in), both directions ==")
    ARB = "0x" + "44" * 20
    set_chain(6, 1, arbiter_word="0" * 24 + "44" * 20)
    _, rq6 = spawn_hub({"HUB_EVM_ARBITER": ARB}, "f2b")
    PAID6, B6 = mini_flow(rq6, "f2b")
    c, ok6 = rq6("POST", "/book", {"listing_id": PAID6, "attendee": "F2B", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(6)}}, B6)
    check("F2b: matching hub arbiter -> books 201", c == 201, "%s %s" % (c, ok6))
    c, e6 = rq6("POST", "/book", {"listing_id": PAID6, "attendee": "F2B", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(1)}}, B6)
    check("F2b: foreign/zero arbiter -> 409", c == 409, "%s %s" % (c, e6))

    print("== E9 F2c: payout-destination binding walls ==")
    # hub WITHOUT a payout address on the listing: fail-closed refusal
    _, rq7 = spawn_hub({"HUB_EVM_ESCROW_ADDRESS": PIN, "HUB_EVM_RPC_URL": EVMPIN}, "f2c")
    PAID7, B7 = mini_flow(rq7, "f2c")  # listing has receive_addr (fixture default)
    # a hub whose listing DECLARES the payout but chain organizer differs:
    set_chain(7, 1, organizer_word="0" * 24 + "99" * 20)  # attacker organizer
    c, e7 = rq7("POST", "/book", {"listing_id": PAID7, "attendee": "F2C", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(7)}}, B7)
    check("F2c: organizer != listing payout -> 409", c == 409, "%s %s" % (c, e7))
    # the matching-organizer escrow books normally (positive control on the same hub)
    set_chain(8, 1)  # fresh HELD escrow with the default organizer word (0x22..)
    c, ok7 = rq7("POST", "/book", {"listing_id": PAID7, "attendee": "F2C ok", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(8)}}, B7)
    check("F2c: organizer == listing payout -> books 201", c == 201, "%s %s" % (c, ok7))

    print("== E9 F2e: double-pay wall (escrow + x402 payment = 409) ==")
    c, e8 = rq7("POST", "/book", {"listing_id": PAID7, "attendee": "F2E", "human_verified": True,
               "escrow_ref": {"type": "arbsep-escrow", "escrow": PIN,
                              "escrow_id": eid(1)}}, {**B7, "X-PAYMENT": "ZmFrZQ=="})
    check("F2e: escrow_ref + X-PAYMENT together -> 409 (no double pay)", c == 409, "%s %s" % (c, e8))
    # F2e gap fix (strong-model review 2026-11-21): the Midnight-shape legacy
    # ref must ALSO hit the wall - an indexer-verified Midnight escrow holds
    # the money; a concurrent x402 payment would move it twice.
    c, e9 = rq7("POST", "/book", {"listing_id": PAID7, "attendee": "F2E-M", "human_verified": True,
               "escrow_ref": {"contract": "c", "escrow_id": 1, "tx": "t"}},
               {**B7, "X-PAYMENT": "ZmFrZQ=="})
    check("F2e: Midnight-shape escrow_ref + X-PAYMENT -> 409 (all rails)", c == 409, "%s %s" % (c, e9))

    print("== E9 in-process: F8 gate truth + F2a party words + F4 pin pass ==")
    os.environ["HUB_EVM_ESCROW_ADDRESS"] = PIN
    os.environ["HUB_EVM_RPC_URL"] = EVMPIN
    import app as _app
    check("F8: EVM ref gates unconditionally (even pre-pin)",
          _app._gate_wants_chain({"type": "arbsep-escrow"}) is True)
    check("F8: Midnight ref keeps legacy CHAIN_GATE behavior",
          _app._gate_wants_chain({"contract": "c", "escrow_id": 1, "tx": "t"}) == _app.CHAIN_GATE)
    _cv, _err = _app._evm_chain_gate_read({"type": "arbsep-escrow", "escrow": PIN,
                                           "escrow_id": eid(1)})
    check("F2a: reader exposes buyer/organizer/arbiter words",
          _cv is not None and _cv.get("buyer") == "0x" + "11" * 20
          and _cv.get("organizer") == "0x" + "22" * 20
          and _cv.get("arbiter") == "0x" + "0" * 40, str(_cv))
    # Owner decision 2026-11-21: escrow ids are INDEPENDENT random bytes32 -
    # never derived from hub objects (M7/M14: chain is truth, hub mirrors).
    # The derivation API must be GONE and the binding machinery id-agnostic.
    import evm_relay as _er
    import secrets as _esec
    check("independent ids: derivation API removed from the module",
          not hasattr(_er, "booking_escrow_id"), "booking_escrow_id still present")
    _d1 = _er.new_escrow_id()
    _d3 = _er.new_escrow_id()
    check("independent ids: fresh ids are bytes32 + distinct (256-bit random)",
          len(_d1) == 66 and _d1 != _d3 and _d1.startswith("0x"), "%s %s" % (_d1, _d3))
    try:
        _er.normalize_escrow_id("0x1234")
        check("independent ids: normalize rejects malformed ids", False, "accepted 0x1234")
    except ValueError:
        check("independent ids: normalize rejects malformed ids", True)
    # F1 binding signature round-trip: sign -> verify TRUE; tamper -> FALSE.
    # The signer address is DERIVED from the key (eth_account needs 32 bytes):
    # verify against the recovered address, then prove tampering breaks it.
    _msg = _er.binding_message(_d1, "0x" + "22" * 20, "0x" + "44" * 20,
                               50_000_000, NOW + 86400, NOW + 9 * 86400)
    _pk = ("0x" + "3c" * 31 + "a1")
    from eth_account import Account as _Acct
    _buyer_addr = _Acct.from_key(_pk).address.lower()
    _sig = _er.sign_binding(_pk, 421614, PIN, _msg)
    check("F1 wiring: binding sig verifies for the buyer",
          _er.verify_binding(_buyer_addr, 421614, PIN, _msg, _sig) is True)
    check("F1 wiring: binding sig REJECTED for tampered terms",
          _er.verify_binding(_buyer_addr, 421614, PIN,
                             dict(_msg, amount=1), _sig) is False)
    _cd = _er.build_hold_calldata(_d1, "0x" + "11" * 20, "0x" + "22" * 20, "0x" + "44" * 20,
                                  50_000_000, NOW + 86400, NOW + 9 * 86400,
                                  NOW - 60, NOW + 600, "0x" + "aa" * 32,
                                  27, "0x" + "bb" * 32, "0x" + "cc" * 32, _sig)
    check("F1 wiring: hold() calldata selector matches the deployed ABI",
          _cd[:10] == "0x" + _er.HOLD_SELECTOR.hex(), _cd[:10])
    try:
        _app._EVM_CHAIN_VERIFIED = False
        _app._evm_assert_chain_id()
        check("F4: chain-id pin passes on true Sepolia fixture", True)
        os.environ["HUB_EVM_CHAIN_ID"] = "999"
        _app._EVM_CHAIN_VERIFIED = False
        try:
            _app._evm_assert_chain_id()
            check("F4: pin raises on mismatch", False, "no exception")
        except RuntimeError:
            check("F4: pin raises on mismatch", True)
        finally:
            os.environ.pop("HUB_EVM_CHAIN_ID", None)
    except Exception as ex:
        check("F4: pin proofs", False, repr(ex))

finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    for _p, _lg in EXTRA_PROCS:
        _p.terminate()
        try: _p.wait(timeout=5)
        except Exception: _p.kill()
        _lg.close()
    logf.close()
    cserver.shutdown()

print()
failed = [n for n, okk in RESULTS if not okk]
print("E9 battery: %d/%d passed" % (len(RESULTS) - len(failed), len(RESULTS)))
if failed:
    print("FAILED:", failed)
    sys.exit(1)
