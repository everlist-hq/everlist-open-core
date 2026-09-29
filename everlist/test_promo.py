#!/usr/bin/env python3
"""Promo codes battery (owner-approved 2026-09-30).

Laws:
  P1 organizer sets promo via manage edit (code echoed ONCE, hash stored)
  P1b validation walls (short code, pct>50)
  P2 public listing NEVER leaks promo_code_hash (H9)
  P3 redemption: price discounted, hub fee follows the DISCOUNTED price
n  P4 booking records promo_applied (server-derived)
  P5 uses decrement; exhausted -> 409
  P6 invalid code -> 403 (after auth passes)
  P7 free listing: promo setup refused
  P8 clearing promo (promo: null) works
  P9 chat 'book <id> <name> promo CODE' stashes promo on the pay intent
  P10 capability answer flips (discount questions -> CAN answer)

Run: ./venv/bin/python test_promo.py
"""
import atexit, json, os, re, socket, subprocess, sys, tempfile, time
import urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

ADMIN_KEY = "dev-admin-key-change-me"


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
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
        PASS += 1; print(f"PASS {name}")
    else:
        FAIL += 1; print(f"FAIL {name} {str(detail)[:160]}")


def main():
    tmp = tempfile.mkdtemp(prefix="promo-")
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

    import chatlib

    # --- buyer FIRST: vouched chat account (verified-human gate needs it) ---
    bs = "web-promo-buyer"
    r = chatlib.handle_text(hub, "signup", sender=bs)
    check("buyer signup", "Account created" in r, r[:80])
    w = chatlib.handle_text(hub, "whoami", sender=bs)
    ma = re.search(r"acct-[0-9a-f]+", w or "")
    assert ma, f"no acct in whoami: {w[:80]}"
    code, _ = call("POST", hub + "/accounts/vouch", {"account_id": ma.group(0)}, admin=True)
    check("buyer vouched", code == 200, code)
    btok = ((chatlib._session(bs) or {}).get("tokens") or {}).get("book")
    assert btok, "no book token in buyer session"

    # --- organizer: list token + PAID listing ($10) ---
    code, acc = call("POST", hub + "/access", {"agent": "promo-org", "acts": ["list"]})
    assert code in (200, 201), f"access {code} {acc}"
    ltok = acc.get("tokens", {}).get("list")
    code, res = call("POST", hub + "/listings",
        {"vertical": "events", "title": "Promo Test Night", "category": "meetup",
         "date": "2026-10-20", "price": 10, "location": "Berlin", "capacity": 20,
         "description": "battery paid listing", "tags": ["test"], "source": "battery"},
        token=ltok)
    assert code == 201, f"listing {code} {res}"
    lid = res.get("id"); manage = res.get("manage_code", "")
    check("paid listing created", bool(lid), str(res)[:100])

    # --- P1: set promo via manage edit (list token + manage code) ---
    code, res = call("POST", hub + f"/listings/{lid}/manage",
        {"action": "edit", "manage_code": manage,
         "promo": {"code": "SAVE20", "pct": 20, "uses": 2}}, token=ltok)
    check("P1 promo set", code == 200 and res.get("promo", {}).get("code") == "SAVE20", f"{code} {res}")
    code, _ = call("POST", hub + f"/listings/{lid}/manage",
        {"action": "edit", "manage_code": manage,
         "promo": {"code": "X", "pct": 20, "uses": 2}}, token=ltok)
    check("P1b short code refused", code == 400, code)
    code, _ = call("POST", hub + f"/listings/{lid}/manage",
        {"action": "edit", "manage_code": manage,
         "promo": {"code": "TOOBIG", "pct": 90, "uses": 2}}, token=ltok)
    check("P1b pct>50 refused", code == 400, code)

    # --- P2: public listing leaks no hash ---
    code, pub = call("GET", hub + f"/listings/{lid}")
    check("P2 no promo_code_hash in public", "promo_code_hash" not in json.dumps(pub), pub)
    check("P2 pct visible", pub.get("promo_pct") == 20, pub.get("promo_pct"))

    # --- P3: redemption (lowercase code); fee follows discounted price ---
    code, b1 = call("POST", hub + "/book",
        {"listing_id": lid, "attendee": "Alice", "promo_code": "save20"}, token=btok)
    check("P3 booked with promo (lowercase)", code == 201, f"{code} {b1}")
    check("P3 amount discounted 10->8", code == 201 and abs(float(b1.get("amount", 0)) - 8.0) < 0.001, b1.get("amount"))
    check("P3 fee 2% of 8 = 0.16", code == 201 and abs(float(b1.get("hub_fee", 0)) - 0.16) < 0.001, b1.get("hub_fee"))

    # --- P4: promo_applied recorded ---
    check("P4 promo_applied pct", (b1.get("promo_applied") or {}).get("pct") == 20, b1.get("promo_applied"))

    # --- P5: uses decrement 2->1->0; exhausted 409 ---
    code, pub = call("GET", hub + f"/listings/{lid}")
    check("P5 uses_left 2->1", pub.get("promo_uses_left") == 1, pub.get("promo_uses_left"))
    code, b2 = call("POST", hub + "/book",
        {"listing_id": lid, "attendee": "Bob", "promo_code": "SAVE20"}, token=btok)
    check("P5 second redemption ok", code == 201, f"{code} {b2}")
    code, pub = call("GET", hub + f"/listings/{lid}")
    check("P5 uses_left 0", pub.get("promo_uses_left") == 0, pub.get("promo_uses_left"))
    code, _ = call("POST", hub + "/book",
        {"listing_id": lid, "attendee": "Carol", "promo_code": "SAVE20"}, token=btok)
    check("P5 exhausted 409", code == 409, code)

    # --- P6: invalid code -> 403 (auth passes now) ---
    code, res6 = call("POST", hub + "/book",
        {"listing_id": lid, "attendee": "Dan", "promo_code": "WRONG1"}, token=btok)
    check("P6 invalid 403 invalid-promo", code == 403 and "promo" in str(res6.get("error", "")).lower(), f"{code} {res6}")

    # --- P7: free listing refuses promo setup ---
    code, res = call("POST", hub + "/listings",
        {"vertical": "events", "title": "Free Promo Refusal", "category": "workshop",
         "date": "2026-10-21", "price": 0, "location": "Berlin", "capacity": 10,
         "description": "battery free listing", "tags": ["test"], "source": "battery"},
        token=ltok)
    flid, fmanage = res.get("id"), res.get("manage_code", "")
    code, _ = call("POST", hub + f"/listings/{flid}/manage",
        {"action": "edit", "manage_code": fmanage,
         "promo": {"code": "FREE1", "pct": 10, "uses": 1}}, token=ltok)
    check("P7 free listing promo refused", code == 400, code)

    # --- P8: clear promo ---
    code, res = call("POST", hub + f"/listings/{lid}/manage",
        {"action": "edit", "manage_code": manage, "promo": None}, token=ltok)
    check("P8 promo cleared", code == 200 and res.get("promo") is None, f"{code} {res}")
    code, pub = call("GET", hub + f"/listings/{lid}")
    check("P8 public shows no promo", "promo_pct" not in pub and "promo_uses_left" not in pub, "")

    # --- P9: chat 'book <id> <name> promo CODE' stashes promo on pay intent ---
    code, res = call("POST", hub + f"/listings/{lid}/manage",
        {"action": "edit", "manage_code": manage,
         "promo": {"code": "CHAT10", "pct": 10, "uses": 5}}, token=ltok)
    check("P9 promo re-set", code == 200, f"{code} {res}")
    r = chatlib.handle_text(hub, f"book {lid} Zoe promo CHAT10", sender=bs)
    _int = chatlib._PAY_INTENTS.get(bs) or {}
    check("P9 chat stashes promo on pay intent", _int.get("promo_code") == "CHAT10", str(_int))
    check("P9 chat kept the name", _int.get("who") == "Zoe", str(_int))

    # --- P10: capability answer ---
    ans = chatlib.handle_text(hub, "do you have discount codes?", sender="promo-cap-1")
    check("P10 capability CAN answer", "promo" in ans.lower() and "book" in ans.lower(), ans[:120])


if __name__ == "__main__":
    try:
        main()
    finally:
        print(f"\n=== promo: {PASS} passed, {FAIL} failed ===")
        sys.exit(1 if FAIL else 0)
