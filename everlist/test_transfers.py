#!/usr/bin/env python3
"""Transfers battery (owner-approved 2026-09-30).

Laws under test:
  T1 happy path: transfer 200, secret + cancel token rotate, name updates
  T2 old booking secret dies (GET /book/{id} 401), new one works + shows name
  T3 old cancel token dies (403 superseded); new one cancels (REFUNDED)
  T4 second transfer: gen-2 token works, gen-1 rejected
  T5 transfer after settlement refused (409)
  T6 chat E2E: 'transfer <bid> <name>' -> new secret shown once, re-stashed
  T7 capability flip: 'can I transfer my booking' -> CAN answer, not decline
  T8 usage guards: no args -> usage; bad id -> honest hint

Run: ./venv/bin/python test_transfers.py
"""
import atexit, json, os, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ADMIN_KEY = "dev-admin-key-change-me"


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def call(method, url, body=None, token=None, admin=False):
    req = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"})
    if token:
        req.add_header("X-Hub-Token", token)
    if admin:
        req.add_header("X-Admin-Key", ADMIN_KEY)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


PASS = FAIL = 0
def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name} {detail[:160]}")


def main():
    tmp = tempfile.mkdtemp(prefix="xfer-")
    port = free_port()
    hub = f"http://127.0.0.1:{port}"
    env = dict(os.environ, HUB_STATE_FILE=os.path.join(tmp, "state.json"),
               HUB_ADMIN_KEY=ADMIN_KEY, HUB_POW_SIGNUP_BITS="8", PYTHONUNBUFFERED="1")
    hublog = open(os.path.join(tmp, "hub.log"), "a")
    proc = subprocess.Popen([os.path.join(HERE, "venv/bin/python"), "app.py", str(port)],
                            cwd=HERE, env=env, stdout=hublog, stderr=subprocess.STDOUT)
    atexit.register(lambda: proc.poll() is None and proc.terminate())
    for _ in range(50):
        try:
            urllib.request.urlopen(hub + "/.well-known/agent-hub.json", timeout=2)
            break
        except Exception:
            time.sleep(0.2)

    # --- account: signup via hub, vouch via admin ---
    import chatlib
    sender = "xfer-battery-1"
    r = chatlib.handle_text(hub, "signup", sender=sender)
    check("signup via chat", "Account created" in r, r[:90])
    # find the account id from whoami
    w = chatlib.handle_text(hub, "whoami", sender=sender)
    import re as _re
    m = _re.search(r"acct-[0-9a-f]+", w)
    check("whoami shows account", bool(m), w[:90])
    aid = m.group(0) if m else ""
    code, _ = call("POST", hub + f"/accounts/vouch", {"account_id": aid}, admin=True)
    check("operator vouch", code == 200, str(code))

    # --- book a free listing via chat (stashes cancel token in session) ---
    # self-contained: mint a list token + create our own FREE listing
    code, acc = call("POST", hub + "/access", {"agent": "xfer-battery", "acts": ["list"]})
    assert code in (200, 201), f"access {code} {acc}"
    listing = {"vertical": "events", "title": "Free Transfer Test Class",
               "category": "workshop", "date": "2026-10-05", "price": 0,
               "location": "Berlin", "capacity": 5,
               "description": "Battery-owned free listing for transfer tests.",
               "tags": ["test", "free"], "source": "battery"}
    code, res = call("POST", hub + "/listings", listing, token=acc.get("tokens", {}).get("list"))
    assert code == 201, f"listing {code} {res}"
    lid = res.get("id")
    check("free listing created", bool(lid), str(res)[:100])
    r = chatlib.handle_text(hub, f"book {lid} Anna", sender=sender)
    m = _re.search(r"bk-[0-9a-f]+", r)
    check("chat booking made", bool(m), r[:120])
    bid = m.group(0) if m else ""
    if not bid:
        print("=== transfers: abort (no booking)"); return
    sess = chatlib._session(sender)
    old_cancel = (sess.get("cancel_tokens") or {}).get(bid, "")
    check("cancel token stashed", bool(old_cancel))

    # old secret for T2: fetch via GET /book/{id} needs the secret we only have
    # in the booking reply; grab from r
    m = _re.search(r"([0-9a-f]{32})", r)
    old_secret = m.group(1) if m else ""

    # --- T1 happy path via chat command ---
    r2 = chatlib.handle_text(hub, f"transfer {bid} Bob", sender=sender)
    check("T1 chat transfer ok", "Transferred" in r2 and "Bob" in r2, r2[:120])
    m = _re.search(r"([0-9a-f]{32})", r2)
    new_secret = m.group(1) if m else ""
    check("T1 new secret shown once", bool(new_secret) and new_secret != old_secret)
    new_cancel = (chatlib._session(sender).get("cancel_tokens") or {}).get(bid, "")
    check("T1 cancel token rotated + re-stashed", bool(new_cancel) and new_cancel != old_cancel)

    # --- T2 old secret dies, new works ---
    if old_secret:
        code, _ = call("GET", hub + f"/book/{bid}", token=old_secret)
        check("T2 old secret rejected", code in (401, 403), str(code))
    code, det = call("GET", hub + f"/book/{bid}", token=new_secret)
    check("T2 new secret reveals", code == 200, str(code))
    name_ok = False
    try:
        pv = det.get("private_details") or {}
        vals = [str(v) for v in pv.values()]
        name_ok = any("Bob" in v for v in vals)
    except Exception:
        pass
    check("T2 private shows new name", name_ok, json.dumps(det)[:160])

    # --- T3 old cancel token dies; new cancels ---
    code, res = call("POST", hub + f"/book/{bid}/cancel", {}, token=old_cancel)
    check("T3 old cancel token rejected", code == 403 and ("superseded" in str(res.get("error", "")) or "replayed" in str(res.get("error", ""))), f"{code} {res}")

    # --- T4 second transfer with the gen-2 token ---
    r3 = chatlib.handle_text(hub, f"transfer {bid} Carla", sender=sender)
    check("T4 second transfer ok", "Carla" in r3, r3[:120])
    gen2_cancel = (chatlib._session(sender).get("cancel_tokens") or {}).get(bid, "")
    code, _ = call("POST", hub + f"/book/{bid}/transfer", {"name": "Dan"}, token=new_cancel)
    check("T4 gen-1 token rejected", code == 403, str(code))

    # --- T3b cancel with the newest token -> REFUNDED ---
    code, res = call("POST", hub + f"/book/{bid}/cancel", {}, token=gen2_cancel)
    check("T3b newest token cancels", code == 200 and res.get("escrow") == "REFUNDED", f"{code} {res}")

    # --- T5 transfer after settlement refused ---
    code, res = call("POST", hub + f"/book/{bid}/transfer", {"name": "Eve"}, token=gen2_cancel)
    check("T5 post-settlement transfer refused", 400 <= code < 500, f"{code} {res}")

    # --- T7 capability flip ---
    r7 = chatlib.handle_text(hub, "can I transfer my booking to Anna?", sender="capx-1")
    check("T7 capability CAN answer", "transfer <booking-id>" in r7, r7[:120])

    # --- T8 usage guards ---
    r8 = chatlib.handle_text(hub, "transfer", sender="capx-2")
    check("T8 usage line", "transfer <booking-id>" in r8, r8[:100])
    r9 = chatlib.handle_text(hub, "transfer bk-deadbeef Bob", sender=sender)
    check("T8 booked-here hint", "in this chat" in r9 or "booking id" in r9.lower(), r9[:120])


if __name__ == "__main__":
    try:
        main()
    finally:
        print(f"\n=== transfers: {PASS} passed, {FAIL} failed ===")
        sys.exit(1 if FAIL else 0)
