"""LEVEL-1 chain gating regression (owner-approved 2026-09-20): the hub never
claims a money state the chain does not back.

Covers (HUB_INDEXER_URL + HUB_INDEXER_URL_2 set = gating ON):
- intake: escrow_ref REQUIRED for paid escrow-rail bookings (E3 - no
  zero-money HELD->RELEASED farming), chain state must be HELD, amount must
  cover the booking exactly, chain claim deadline must not have passed
- terminal flips: /confirm and /cancel are verify-then-flip with dual-source
  reads that must agree; hub-first flips refused with sync hints (D1);
  chain claim deadline enforced on cancel (D2 anchored to the CHAIN)
- fail-closed: indexer unreachable or sources disagree -> 503, state intact
- unaffected rails: WAIVED (free) and DIRECT (instant) bookings need no chain
- other suites cover gating-OFF legacy behavior (unset env = unchanged)

Run: python test_chain_gate.py
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


TMP = tempfile.mkdtemp(prefix="hub-gate-")
PORT = free_port(); BASE = "http://127.0.0.1:%d" % PORT; PYEXE = sys.executable
ADMIN = "dev-admin-key-change-me"


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


# --- two INDEPENDENT chain sources (dual-source reads must agree) ---
CONTRACT = "gate-escrow-contract"


def make_gate_chain(state, mode):
    """Minimal Midnight-indexer GraphQL stub (m8 shape). Serves the CURRENT
    escrows map as the latest action state; mode['down'] simulates outage."""
    class H(BaseHTTPRequestHandler):
        def do_POST(self):
            if mode["down"]:
                self.send_response(503)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            n = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(n).decode())
            except ValueError:
                body = {}
            addr = (body.get("variables") or {}).get("addr", "")
            if addr != CONTRACT:
                edges = []
            else:
                shex = json.dumps({"escrows": state["escrows"]}).encode().hex()
                edges = [{"node": {"__typename": "ContractCall", "entryPoint": "create",
                                   "state": shex, "transaction": {"id": "tx-gate"}}}]
            out = json.dumps({"data": {"contractActions": {"edges": edges,
                    "pageInfo": {"hasNextPage": False, "endCursor": None}}}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(out)))
            self.end_headers()
            self.wfile.write(out)

        def log_message(self, *a):
            pass
    port = free_port()
    srv = ThreadingHTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d" % port


S1 = {"escrows": {}}
S2 = {"escrows": {}}
M1 = {"down": False}
M2 = {"down": False}
_, URL1 = make_gate_chain(S1, M1)
_, URL2 = make_gate_chain(S2, M2)

HELD, RELEASED, REFUNDED = 1, 2, 3


def chain_set(eid, st=None, amount=None, deadline=None, only=None):
    """Mutate escrow entry on both sources (default) or only one (divergence)."""
    def _upd(S):
        e = S["escrows"].setdefault(str(eid),
                                     {"state": HELD, "amount": "5", "deadline": "99999999999"})
        if st is not None: e["state"] = st
        if amount is not None: e["amount"] = amount
        if deadline is not None: e["deadline"] = deadline
    if only == "s1": _upd(S1)
    elif only == "s2": _upd(S2)
    else: _upd(S1); _upd(S2)


env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_POW_SIGNUP_BITS": "8", "HUB_RATE_BOOKS_PER_MIN": "1000",
       "HUB_INDEXER_URL": URL1, "HUB_INDEXER_URL_2": URL2,
       "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
proc = subprocess.Popen([PYEXE, os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
end = time.time() + 15; ready = False
while time.time() < end:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5): ready = True; break
    except OSError: time.sleep(0.2)
assert ready, "test hub did not start"


def book(lid, extra=None):
    return req("POST", "/book", {"listing_id": lid, "attendee": "Gate Buyer",
               "human_verified": True, **(extra or {})}, {"X-Hub-Token": BTOK})


def confirm(bid):
    c, t = req("POST", "/admin/tokens", {"act": "confirm", "booking_id": bid},
               {"X-Hub-Token": ADMIN})
    assert c == 201, t
    return req("POST", "/book/%s/confirm" % bid, {}, {"X-Hub-Token": t["token"]})


def hub_state(bid):
    _, bl = req("GET", "/bookings", headers={"X-Hub-Token": BTOK})
    x = next((x for x in bl["bookings"] if x["id"] == bid), None)
    return x["escrow"] if x else None


def escrow_ref(eid):
    return {"contract": CONTRACT, "escrow_id": eid, "tx": "gate-tx-%d" % eid}


try:
    print("== setup: owner + paid/free/instant listings + buyer ==")
    c, a = req("POST", "/accounts/signup", {"agent": "gate-owner", "pow": solve_pow("signup")})
    assert c == 201, a
    c, l = req("POST", "/accounts/login", {"account_code": a["account_code"], "agent": "gate-owner"})
    assert c == 200, l
    OTOK = l["tokens"]["list"]
    c, r = req("POST", "/listings", {"vertical": "events", "title": "Gate Gig",
               "date": "2026-10-10", "location": "X", "price": 5, "capacity": 50},
               {"X-Hub-Token": OTOK})
    assert c == 201, r
    LID = r["id"]
    c, r = req("POST", "/listings", {"vertical": "events", "title": "Gate Free",
               "date": "2026-10-11", "location": "Y", "price": 0, "capacity": 10},
               {"X-Hub-Token": OTOK})
    assert c == 201, r
    FREE_LID = r["id"]
    c, r = req("POST", "/listings", {"vertical": "events", "title": "Gate Instant",
               "date": "2026-10-12", "location": "Z", "price": 5, "capacity": 10,
               "payment_terms": {"rail": "instant"}},
               {"X-Hub-Token": OTOK})
    assert c == 201, r
    INSTANT_LID = r["id"]
    c, bt = req("POST", "/access", {"agent": "agentq_gatebuyer", "acts": ["book"]})
    assert c == 201, bt
    BTOK = bt["tokens"]["book"]

    print("== G1: intake - paid escrow-rail booking without escrow_ref is refused (E3) ==")
    c, r = book(LID)
    check("G1: no escrow_ref -> 400 required", c == 400 and "escrow_ref required" in r.get("error", ""), (c, r))

    print("== G2: intake - a RELEASED chain escrow cannot back a booking ==")
    chain_set(1, st=RELEASED)
    c, r = book(LID, {"escrow_ref": escrow_ref(1)})
    check("G2: RELEASED escrow_ref -> 409", c == 409 and "RELEASED" in r.get("error", ""), (c, r))

    print("== G2b: intake - unknown escrow id fails closed ==")
    c, r = book(LID, {"escrow_ref": escrow_ref(99)})
    check("G2b: unknown escrow -> 503 fail-closed", c == 503 and "fail-closed" in json.dumps(r), (c, r))

    print("== G3: intake - amount must cover the booking exactly ==")
    chain_set(2, st=HELD, amount="4")
    c, r = book(LID, {"escrow_ref": escrow_ref(2)})
    check("G3: amount mismatch -> 409", c == 409 and "amount" in r.get("error", ""), (c, r))

    print("== G3b: intake - chain claim deadline must not have passed ==")
    chain_set(3, st=HELD, amount="5", deadline="1")
    c, r = book(LID, {"escrow_ref": escrow_ref(3)})
    check("G3b: past chain deadline -> 409", c == 409 and "deadline" in r.get("error", ""), (c, r))

    print("== G4: intake - a valid HELD escrow books ==")
    chain_set(4, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(4)})
    A = r.get("id")
    check("G4: HELD + exact amount -> 201 HELD", c == 201 and r.get("escrow") == "HELD", (c, r))

    print("== G5: intake - indexer unreachable fails closed (503, no booking) ==")
    chain_set(5, st=HELD, amount="5")
    M1["down"] = True; M2["down"] = True
    c, r = book(LID, {"escrow_ref": escrow_ref(5)})
    check("G5: indexer down -> 503 fail-closed", c == 503 and "fail-closed" in json.dumps(r), (c, r))
    M1["down"] = False; M2["down"] = False

    print("== G6: confirm - chain HELD -> hub may flip to RELEASED ==")
    c, r = confirm(A)
    check("G6: verify-then-flip confirm -> 200 RELEASED", c == 200 and r.get("escrow") == "RELEASED", (c, r))
    check("G6b: hub state RELEASED", hub_state(A) == "RELEASED", hub_state(A))

    print("== G7: confirm - chain already RELEASED refuses the hub-first flip (D1) ==")
    chain_set(6, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(6)})
    B = r.get("id"); assert c == 201, r
    chain_set(6, st=RELEASED)
    c, r = confirm(B)
    check("G7: chain RELEASED -> 409 hub-first refused", c == 409 and "hub-first" in r.get("error", ""), (c, r))
    check("G7b: hub stays HELD", hub_state(B) == "HELD", hub_state(B))

    print("== G8: confirm - chain REFUNDED also refuses with a sync hint ==")
    chain_set(7, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(7)})
    C = r.get("id"); assert c == 201, r
    chain_set(7, st=REFUNDED)
    c, r = confirm(C)
    check("G8: chain REFUNDED -> 409", c == 409, (c, r))
    check("G8b: hub stays HELD", hub_state(C) == "HELD", hub_state(C))

    print("== G9: cancel - chain HELD inside deadline -> 200 REFUNDED ==")
    chain_set(8, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(8)})
    D = r.get("id"); CT8 = r.get("cancel_token"); assert c == 201, r
    c, r = req("POST", "/book/%s/cancel" % D, {}, {"X-Hub-Token": CT8})
    check("G9: verify-then-flip cancel -> 200 REFUNDED", c == 200 and r.get("escrow") == "REFUNDED", (c, r))

    print("== G10: cancel - chain already REFUNDED refuses the hub-first flip ==")
    chain_set(9, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(9)})
    E = r.get("id"); CT9 = r.get("cancel_token"); assert c == 201, r
    chain_set(9, st=REFUNDED)
    c, r = req("POST", "/book/%s/cancel" % E, {}, {"X-Hub-Token": CT9})
    check("G10: chain REFUNDED -> 409 hub-first refused", c == 409 and "hub-first" in r.get("error", ""), (c, r))
    check("G10b: hub stays HELD", hub_state(E) == "HELD", hub_state(E))

    print("== G11: cancel - past chain claim deadline refuses (D2, chain-authoritative) ==")
    chain_set(10, st=HELD, amount="5", deadline="99999999999")
    c, r = book(LID, {"escrow_ref": escrow_ref(10)})
    F = r.get("id"); CT10 = r.get("cancel_token"); assert c == 201, r
    chain_set(10, st=HELD, amount="5", deadline="1")  # deadline passes AFTER booking
    c, r = req("POST", "/book/%s/cancel" % F, {}, {"X-Hub-Token": CT10})
    check("G11: past chain deadline -> 409", c == 409 and "deadline" in r.get("error", ""), (c, r))

    print("== G12: terminal flips fail closed while both indexers are down ==")
    chain_set(11, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(11)})
    Gb = r.get("id"); CT11 = r.get("cancel_token"); assert c == 201, r
    M1["down"] = True; M2["down"] = True
    c1, r1 = confirm(Gb)
    c2, r2 = req("POST", "/book/%s/cancel" % Gb, {}, {"X-Hub-Token": CT11})
    check("G12: confirm with indexer down -> 503", c1 == 503, (c1, r1))
    check("G12b: cancel with indexer down -> 503", c2 == 503, (c2, r2))
    check("G12c: hub stays HELD", hub_state(Gb) == "HELD", hub_state(Gb))
    M1["down"] = False; M2["down"] = False

    print("== G13: dual-source disagreement fails closed ==")
    chain_set(12, st=HELD, amount="5")
    c, r = book(LID, {"escrow_ref": escrow_ref(12)})
    Hb = r.get("id"); CT12 = r.get("cancel_token"); assert c == 201, r
    chain_set(12, st=RELEASED, only="s2")  # sources now disagree
    c1, r1 = confirm(Hb)
    c2, r2 = req("POST", "/book/%s/cancel" % Hb, {}, {"X-Hub-Token": CT12})
    check("G13: confirm with disagreement -> 503", c1 == 503 and "disagree" in json.dumps(r1), (c1, r1))
    check("G13b: cancel with disagreement -> 503", c2 == 503 and "disagree" in json.dumps(r2), (c2, r2))
    check("G13c: hub stays HELD", hub_state(Hb) == "HELD", hub_state(Hb))
    chain_set(12, st=HELD)  # re-agree

    print("== G14: WAIVED (free) and DIRECT (instant) rails need no chain ==")
    c, r = book(FREE_LID)
    W = r.get("id"); CTW = r.get("cancel_token")
    check("G14: free booking -> 201 WAIVED", c == 201 and r.get("escrow") == "WAIVED", (c, r))
    cw, rw = confirm(W)
    check("G14b: WAIVED confirm -> 200 (no chain read)", cw == 200, (cw, rw))
    c, r = book(FREE_LID)
    W2 = r.get("id"); CTW2 = r.get("cancel_token")
    c, r = req("POST", "/book/%s/cancel" % W2, {}, {"X-Hub-Token": CTW2})
    check("G14c: WAIVED cancel -> 200 (no chain read)", c == 200, (c, r))
    c, r = book(INSTANT_LID, {"accepted_payment_terms": {"rail": "instant",
               "refund_window_hours": 0, "deposit_required": 0.0}})
    I = r.get("id")
    check("G14d: instant booking -> 201 DIRECT", c == 201 and r.get("escrow") == "DIRECT", (c, r))
    ci, ri = confirm(I)
    check("G14e: DIRECT confirm -> 409 instant rail (settled at booking)", ci == 409, (ci, ri))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    logf.close()

print()
ok = sum(1 for _, v in RESULTS if v)
print("=== chain-gate: %d/%d passed ===" % (ok, len(RESULTS)))
print("CHAIN_GATE_ALL_PASSED" if ok == len(RESULTS) else "CHAIN_GATE_FAILED")
sys.exit(0 if ok == len(RESULTS) else 1)
