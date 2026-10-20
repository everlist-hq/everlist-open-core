"""W3.1: dispute path on the hub (POST /book/{id}/dispute).

Covered here:
- buyer (cancel_token) opens dispute on a HELD booking -> 200, DISPUTED
- owner (manage_code) opens dispute -> 200, DISPUTED
- unauthenticated / wrong token -> 401
- non-existent booking -> 404
- dispute on a RELEASED booking -> 409 (only HELD can be disputed)
- double dispute -> 409
- cancel after dispute -> 409 (refund blocked while DISPUTED)
- booking status shows DISPUTED after opening
- WAIVED (free) bookings cannot be disputed (no money held)

Run: python test_dispute_hub.py
"""
import atexit
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _kill(p):
    if p:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()


_ACTIVE = []
atexit.register(lambda: [_kill(p) for p in _ACTIVE])


def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5): return True
        except OSError: time.sleep(0.2)
    return False


def post(base, path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Hub-Token"] = token
    rq = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                method="POST", headers=headers)
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception:
        return -1, {}


def get(base, path, token=None):
    headers = {}
    if token:
        headers["X-Hub-Token"] = token
    rq = urllib.request.Request(base + path, headers=headers)
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception:
        return -1, {}


def spawn(state_file, extra_env=None):
    port = free_port()
    logdir = os.path.dirname(state_file)
    env = {**os.environ, "HUB_STATE_FILE": state_file,
           "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1", **(extra_env or {})}
    logf = open(os.path.join(logdir, "hub-dispute.log"), "a")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), "hub did not start"
    return f"http://127.0.0.1:{port}", p, logf


def tokens(base, agent, acts):
    _, r = post(base, "/access", {"agent": agent, "acts": acts})
    return r.get("tokens", {})


TMP = tempfile.mkdtemp(prefix="hub-dispute-")
STATE = os.path.join(TMP, "state.json")
HUB, _p, _log = spawn(STATE)
LT = tokens(HUB, "dispute-merchant", ["list"])["list"]
BT = tokens(HUB, "dispute-buyer", ["book"])["book"]


def mk(price, vert="events"):
    body = {"vertical": vert, "title": f"W3 dispute {time.time()} {price}", "price": price,
            "location": "Vienna", "capacity": 10, "date": "2026-12-01"}
    st, r = post(HUB, "/listings", body, token=LT)
    assert st == 201, f"seed failed: {r}"
    return r["id"], r.get("manage_code", "")


def book(lid, token=BT, extra=None):
    body = {"listing_id": lid, "attendee": "W3 Buyer",
            "human_verified": True}
    body.update(extra or {})
    return post(HUB, "/book", body, token=token)


# --- T1: buyer opens dispute on a HELD booking ----------------------------
LID1, MC1 = mk(10)
st, r = book(LID1)
check("T1 booking created (HELD)", st == 201 and r.get("escrow") == "HELD", f"got {st}: {r}")
BID1, CT1 = r.get("id", ""), r.get("cancel_token", "")
st, r = post(HUB, f"/book/{BID1}/dispute", {}, token=CT1)
check("T1 buyer dispute -> 200 DISPUTED",
      st == 200 and r.get("escrow") == "DISPUTED", f"got {st}: {r}")
check("T1 response mentions frozen + arbiter timeout liveness",
      "frozen" in str(r.get("note", "")) and "arbiterTimeoutRefund" in str(r.get("liveness", "")),
      f"note={r.get('note')!r} liveness={r.get('liveness')!r}")

# --- T2: booking status now shows DISPUTED --------------------------------
st, r = get(HUB, f"/bookings/{BID1}", token=BT)
check("T2 status endpoint shows DISPUTED",
      st == 200 and r.get("escrow") == "DISPUTED", f"got {st}: {r}")

# --- T3: cancel after dispute -> 409 (refund blocked while DISPUTED) -----
st, r = post(HUB, f"/book/{BID1}/cancel", {}, token=CT1)
check("T3 cancel while DISPUTED -> 409",
      st == 409 and "DISPUTED" in str(r.get("error", "")), f"got {st}: {r}")

# --- T4: double dispute -> 409 --------------------------------------------
st, r = post(HUB, f"/book/{BID1}/dispute", {}, token=CT1)
check("T4 double dispute -> 409",
      st == 409 and "only HELD" in str(r.get("error", "")), f"got {st}: {r}")

# --- T5: owner opens dispute via manage_code -----------------------------
LID5, MC5 = mk(20)
st, r = book(LID5)
BID5, CT5 = r.get("id", ""), r.get("cancel_token", "")
st, r = post(HUB, f"/book/{BID5}/dispute", {"manage_code": MC5})
check("T5 owner dispute via manage_code -> 200 DISPUTED",
      st == 200 and r.get("escrow") == "DISPUTED", f"got {st}: {r}")

# --- T6: unauthenticated -> 401 -------------------------------------------
LID6, MC6 = mk(30)
st, r = book(LID6)
BID6 = r.get("id", "")
st, r = post(HUB, f"/book/{BID6}/dispute", {})
check("T6 no credentials -> 401",
      st == 401 and "credentials" in str(r.get("error", "")), f"got {st}: {r}")
st, r = post(HUB, f"/book/{BID6}/dispute", {}, token="not-a-token")
check("T6 wrong token -> 401",
      st == 401, f"got {st}: {r}")

# --- T7: dispute on a RELEASED booking -> 409 -----------------------------
LID7, MC7 = mk(40)
st, r = book(LID7)
BID7, CT7 = r.get("id", ""), r.get("cancel_token", "")
st, r = post(HUB, f"/book/{BID7}/confirm", {"manage_code": MC7})
check("T7 confirm setup ok", st == 200 and r.get("escrow") == "RELEASED", f"got {st}: {r}")
st, r = post(HUB, f"/book/{BID7}/dispute", {}, token=CT7)
check("T7 dispute on RELEASED -> 409",
      st == 409 and "only HELD" in str(r.get("error", "")), f"got {st}: {r}")

# --- T8: dispute on a REFUNDED booking -> 409 -----------------------------
LID8, MC8 = mk(50)
st, r = book(LID8)
BID8, CT8 = r.get("id", ""), r.get("cancel_token", "")
post(HUB, f"/book/{BID8}/cancel", {}, token=CT8)
st, r = post(HUB, f"/book/{BID8}/dispute", {}, token=BT)
check("T8 dispute on REFUNDED -> 409",
      st == 409 and "only HELD" in str(r.get("error", "")), f"got {st}: {r}")

# --- T9: WAIVED (free) bookings cannot be disputed ------------------------
LID9, MC9 = mk(0)
st, r = book(LID9)
BID9, CT9 = r.get("id", ""), r.get("cancel_token", "")
check("T9 free booking is WAIVED", r.get("escrow") == "WAIVED", f"got {st}: {r}")
st, r = post(HUB, f"/book/{BID9}/dispute", {}, token=CT9)
check("T9 dispute on WAIVED -> 409 (no money held)",
      st == 409, f"got {st}: {r}")

# --- T10: non-existent booking -> 404 -------------------------------------
st, r = post(HUB, "/book/bk-does-not-exist/dispute", {}, token=BT)
check("T10 unknown booking -> 404", st == 404, f"got {st}: {r}")

# --- T11: ledger carries the dispute transition ----------------------------
st, r = get(HUB, "/ledger")
dispute_rows = [t for t in r.get("ledger", []) if t.get("to") == "DISPUTED"]
check("T11 ledger has escrow_sync rows to DISPUTED",
      len(dispute_rows) >= 2, f"rows={len(dispute_rows)}")


fails = [n for n, ok in RESULTS if not ok]
print()
print(f"== W3.1 hub dispute battery: {len(RESULTS) - len(fails)}/{len(RESULTS)} PASSED ==")
if fails:
    print("FAILED:", *fails, sep="\n  - ")
    sys.exit(1)
