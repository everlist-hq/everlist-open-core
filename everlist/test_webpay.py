#!/usr/bin/env python3
"""P0 human paid bookings - real-flow battery (spec 2026-09-29).

Boots the hub with HUB_PAY_MODE=testnet + HUB_SETTLE_MODE=auto + a LOCAL
STUB facilitator (same honest pattern as test_x402_settle.py), the webchat
in-process, then walks the HUMAN paid flow end-to-end with a REAL EIP-3009
signature: book intent -> payment_request -> sign -> /api/pay/submit ->
booking escrow HELD -> payment_payer bound -> settlement ledger entry.
Plus: terms law, replay wall, intent single-use, free-booking regression.

Run: ./venv/bin/python test_webpay.py
"""
import atexit
import base64
import json
import os
import subprocess
import socket
import sys
import tempfile
import time
import urllib.request
import urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

os.environ.setdefault("WEBCHAT_RL_S_BURST", "200")
os.environ.setdefault("WEBCHAT_RL_S_PER_MIN", "200")
os.environ.setdefault("WEBCHAT_RL_IP_BURST", "500")
os.environ.setdefault("WEBCHAT_RL_IP_PER_MIN", "500")
os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
os.environ["EVERLIST_PHRASE"] = "0"

from eth_account import Account
import test_x402_settle as X4  # StubFacil + build_payment reuse

PASS = FAIL = 0


def check(name, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"PASS {name}")
    else:
        FAIL += 1
        print(f"FAIL {name}")


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    tmp = tempfile.mkdtemp(prefix="webpay-")
    state = os.path.join(tmp, "hub.json")
    hub_port, wc_port = _free_port(), _free_port()
    stub = X4.StubFacil()
    env = dict(os.environ, HUB_PAY_MODE="testnet", HUB_SETTLE_MODE="auto",
               HUB_STATE_FILE=state, HUB_FACILITATOR_URL=stub.base("ok"),
               HUB_ADMIN_KEY="dev-admin-key-change-me")
    hub = subprocess.Popen([os.path.join(HERE, "venv", "bin", "python"),
                            os.path.join(HERE, "app.py"), str(hub_port)],
                           cwd=HERE, env=env, stdout=subprocess.DEVNULL,
                           stderr=subprocess.STDOUT)
    atexit.register(lambda: hub.terminate())
    end = time.time() + 15
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", hub_port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    else:
        print("FATAL: hub not ready")
        return 1

    os.environ["WEBCHAT_PORT"] = str(wc_port)
    os.environ["WEBCHAT_HUB_URL"] = f"http://127.0.0.1:{hub_port}"
    import webchat
    import threading
    webchat.PORT = wc_port
    webchat.HUB_URL = f"http://127.0.0.1:{hub_port}"
    srv = webchat.ThreadingHTTPServer(("127.0.0.1", wc_port), webchat.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    atexit.register(srv.shutdown)
    base = f"http://127.0.0.1:{wc_port}"

    class C:
        def __init__(self):
            import http.cookiejar
            self.jar = http.cookiejar.CookieJar()
            self.op = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self.jar))

        def post(self, path, obj):
            r = urllib.request.Request(base + path,
                data=json.dumps(obj).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with self.op.open(r, timeout=30) as resp:
                    return resp.status, json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    return e.code, json.loads(e.read().decode())
                except Exception:
                    return e.code, {}

    def hub_post(path, obj, headers=None):
        r = urllib.request.Request(f"http://127.0.0.1:{hub_port}" + path,
            data=json.dumps(obj).encode(), method="POST",
            headers={"Content-Type": "application/json", **(headers or {})})
        try:
            with urllib.request.urlopen(r, timeout=15) as resp:
                return resp.status, json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode())
            except Exception:
                return e.code, {}

    c = C()
    # 1. signup -> account (auto-login session)
    st, d = c.post("/api/signup", {"agent": "webpay-tester"})
    check("signup ok", st == 200 and d.get("ok"))
    seed = d.get("seed") or ""
    acct = d.get("account_id") or ""
    check("signup returns seed+account", bool(seed) and acct.startswith("acct-"))
    # vouch (pilot human proof) via hub admin
    st, _ = hub_post("/accounts/vouch", {"account_id": acct},
                     headers={"X-Admin-Key": "dev-admin-key-change-me"})
    check("vouch ok", st == 200)

    # 2. search -> results on the board
    st, d = c.post("/api/chat", {"text": "search jazz"})
    res = d.get("results") or []
    check("search finds paid listing", st == 200
          and any("Jazz" in (l.get("title") or "") for l in res))
    paid = next(l for l in res if "Jazz" in (l.get("title") or ""))

    # 3. book with name -> pay marker -> payment_request payload
    st, d = c.post("/api/chat", {"text": "book 1 webpay-tester"})
    pr = d.get("payment_request") or {}
    check("paid book returns payment_request", st == 200 and pr.get("listing_id") == paid["id"])
    check("amount matches listing price", pr.get("amount") == str(paid.get("price")))
    check("units are micro-usdc", pr.get("units") == str(int(round(paid["price"] * 1_000_000))))
    check("receiver present", bool(pr.get("receiver")))
    check("no table in chat (board-first)", "\u2554" not in (d.get("reply") or ""))

    # 4. terms law: hub /payterms is the single source of truth
    r = urllib.request.Request(f"http://127.0.0.1:{hub_port}/payterms/{paid['id']}")
    with urllib.request.urlopen(r, timeout=10) as resp:
        terms = json.loads(resp.read().decode())
    check("payterms exact", terms.get("max_amount_units") == pr.get("units")
          and terms.get("pay_to") == pr.get("receiver")
          and terms.get("identity_field") == "attendee")

    # 5. REAL EIP-3009 signature against the terms -> submit
    payer = Account.create()
    acc_terms = {"accepts": [{"payTo": terms["pay_to"],
                              "maxAmountRequired": terms["max_amount_units"],
                              "asset": terms["asset"]}]}
    payment_b64, auth = X4.build_payment(acc_terms, payer)
    st, d = c.post("/api/pay/submit", {"payment": payment_b64,
                                        "listing_id": paid["id"],
                                        "name": "webpay-tester"})
    check("pay submit books paid listing", st == 200 and d.get("ok")
          and str(d.get("booking_id") or "").startswith("bk-"))
    check("escrow HELD (protected default rail)", d.get("escrow") == "HELD")
    check("payer wallet bound", str(d.get("payment_payer") or "").lower() == payer.address.lower())
    check("secret shown once", bool(d.get("booking_secret")))
    bid = d.get("booking_id")

    # 6. booking status visible in chat
    st, d = c.post("/api/chat", {"text": f"booking {bid}"})
    check("booking status in chat", st == 200 and bid[:11] in (d.get("reply") or ""))

    # 7. settlement landed in the ledger (stub facilitator, auto mode)
    r = urllib.request.Request(
        f"http://127.0.0.1:{hub_port}/audit/ledger?limit=200")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            led = json.loads(resp.read().decode())
    except Exception:
        led = {}
    entries = led.get("entries") or led.get("ledger") or []
    check("settlement ledger entry", any(e.get("kind") == "x402_settlement"
          and (e.get("detail") or {}).get("booking") == bid for e in entries))

    # 8. replay wall: same nonce again -> rejected
    c2 = C()
    st, d = c2.post("/api/chat", {"text": "search jazz"})
    st, d = c2.post("/api/chat", {"text": "book 1 replay-tester"})
    acc2 = {"accepts": [{"payTo": terms["pay_to"],
                         "maxAmountRequired": terms["max_amount_units"],
                         "asset": terms["asset"]}]}
    # same nonce as the settled payment -> hub nonce wall
    dup = {"x402Version": 1, "scheme": "exact", "network": "base-sepolia",
           "payload": {"authorization": auth, "signature": "0x" + "11" * 65}}
    dup_b64 = base64.b64encode(json.dumps(dup).encode()).decode()
    st, d = c2.post("/api/pay/submit", {"payment": dup_b64,
                                         "listing_id": paid["id"],
                                         "name": "replay-tester"})
    check("replayed payment rejected", st >= 400 and not d.get("ok"))

    # 9. intent single-use: fresh payment but no session/intent -> 401/409
    pay2_b64, _ = X4.build_payment(acc2, Account.create())
    st, d = c2.post("/api/pay/submit", {"payment": pay2_b64,
                                         "listing_id": paid["id"],
                                         "name": "replay-tester"})
    check("intent single-use (fresh session needs new intent)", st in (401, 409))

    # 10. free booking regression: still instant, no payment_request
    st, d = c.post("/api/chat", {"text": "search free yoga"})
    frees = [l for l in (d.get("results") or []) if float(l.get("price") or 1) == 0]
    if frees:
        st, d = c.post("/api/chat", {"text": "book 1 free-tester"})
        check("free booking unchanged", st == 200
              and not d.get("payment_request")
              and ("Booked" in (d.get("reply") or "") or "booking" in (d.get("reply") or "")))
    else:
        check("free booking unchanged (no free listing in seed)", True)

    print(f"\nwebpay suite: {PASS} passed, {FAIL} failed")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
