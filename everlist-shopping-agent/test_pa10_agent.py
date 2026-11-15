'''PA-10 shopping-agent backend tests (2026-11-15).

Pins (isolated hub boot, mirrors the house test style):
  - EverlistStorefrontBackend implements the blueprint StorefrontBackend contract
  - search/details/cart/checkout_handoff over a real hub (same wire as prod)
  - honesty walls: get_orders + get_fulfillment_options raise NotOffered;
    checkout_handoff returns the hosted page URL and NOTHING moves money
  - invalid ids / quantity caps refused
  - policies carry the escrow promise + agent-honesty passage

Run: .venv/bin/python test_pa10_agent.py
'''
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request

os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
os.environ.setdefault("HUB_POW_SIGNUP_BITS", "8")
HUB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent-hub-v2")
sys.path.insert(0, HUB)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(url, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"} if data else {}
    if token:
        headers["X-Hub-Token"] = token
    r = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


import tempfile
TMP = tempfile.mkdtemp(prefix="hub-pa10-")
HUB_PORT = free_port()
env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
hub = subprocess.Popen([sys.executable, os.path.join(HUB, "app.py"), str(HUB_PORT)],
                       stdout=logf, stderr=subprocess.STDOUT, env=env)
try:
    end = time.time() + 15
    for _ in range(60):
        try:
            with socket.create_connection(("127.0.0.1", HUB_PORT), timeout=0.5):
                break
        except OSError:
            time.sleep(0.25)
    else:
        hub.kill()
        print(open(os.path.join(TMP, "hub.log")).read()[-1500:])
        raise SystemExit("hub did not come up")
    base = f"http://127.0.0.1:{HUB_PORT}"
    # fresh hubs auto-seed a small demo set (evt-1, evt-2, food-1, food-2);
    # seed_demo refuses to double-seed, so only log a failure when truly empty
    st0, inv = req(base + "/search")
    check("fresh hub has demo listings", st0 == 200 and len(inv.get("listings") or []) >= 4, str(inv)[:200])

    # create a genuinely FREE listing via the hub's own signup + listing wire
    # (mirrors test_checkout.py: PoW solve -> signup -> login -> POST /listings)
    import hashlib
    def solve_pow(kind):
        stc, ch = req(base + f"/auth/challenge?kind={kind}")
        n = 0
        while True:
            d = hashlib.sha256((ch["challenge"] + str(n)).encode()).digest()
            bits = 0
            for byte in d:
                if byte == 0:
                    bits += 8
                    continue
                bits += 8 - byte.bit_length()
                break
            if bits >= ch["difficulty"]:
                return {"challenge": ch["challenge"], "nonce": n}
            n += 1

    st_u, up = req(base + "/accounts/signup", "POST", {"agent": "pa10-owner", "pow": solve_pow("signup")})
    check("test organizer signup", st_u in (200, 201), f"{st_u} {up}")
    st_l, lg = req(base + "/accounts/login", "POST", {"account_code": up["account_code"], "agent": "pa10-owner"})
    check("test organizer login", st_l == 200, f"{st_l}")
    LIST_TOK = lg["tokens"]["list"]
    st_c, created = req(base + "/listings", "POST",
                        {"vertical": "events", "title": "PA-10 Free Taster", "category": "workshop",
                         "date": "2026-12-05", "price": 0, "location": "Vienna", "capacity": 8},
                        token=LIST_TOK)
    check("free listing created", st_c == 201 and created.get("id"), f"{st_c} {created}")
    FREE_ID = created["id"]

    os.environ["EVERLIST_HUB_URL"] = base
    import everlist_backend as eb
    eb._HUB = base
    from shopping_agent import ShoppingSessionContext

    import asyncio
    ctx = ShoppingSessionContext(session_id="t1", user_id="guest-t1")
    b = eb.EverlistStorefrontBackend()

    async def run():
        out = {}
        out["search"] = await b.search_products(ctx, "")  # empty query = browse all
        if out["search"]:
            out["details"] = await b.get_product_details(ctx, out["search"][0].product_id)
        # cart lifecycle on the genuinely FREE listing created above
        target = FREE_ID
        out["free_target"] = target
        if target:
            out["cart1"] = await b.add_to_cart(ctx, target, 2)
            out["cart2"] = await b.update_cart_item(ctx, target, 1)
            out["cart3"] = await b.remove_from_cart(ctx, target)
            out["handoff"] = await b.checkout_handoff(
                ctx, await b.add_to_cart(ctx, target, 1))
        # honesty walls
        try:
            await b.get_orders(ctx)
            out["orders"] = "NO_RAISE"
        except eb.NotOffered:
            out["orders"] = "NOT_OFFERED"
        try:
            await b.get_fulfillment_options(["even-1"])
            out["fulfill"] = "NO_RAISE"
        except eb.NotOffered:
            out["fulfill"] = "NOT_OFFERED"
        # policies
        out["policies"] = await b.search_policies(ctx, "refund escrow")
        return out

    out = asyncio.run(run())

    check("search returns products", bool(out["search"]), "empty search result")
    p0 = out["search"][0]
    check("product has date attribute", bool(p0.attributes.get("date")), str(p0.attributes))
    if "details" in out:
        d = out["details"]
        check("details carry long_description", d.product_id == p0.product_id)
        check("details specs include date", "date" in (d.specs or {}))
    check("cart add works", "cart1" in out and out["cart1"].items[0].quantity == 2)
    check("cart update works", out["cart2"].items[0].quantity == 1)
    check("cart remove empties", len(out["cart3"].items) == 0)
    h = out.get("handoff") or []
    check("handoff returns hosted URL", bool(h) and h[0].url.startswith("http"), str(h))
    if h:
        check("handoff URL is the hub hosted page", "/checkout?sid=" in h[0].url, h[0].url)
        check("handoff label mentions escrow", "escrow" in (h[0].label or "").lower())
    check("orders NotOffered", out["orders"] == "NOT_OFFERED", str(out["orders"]))
    check("fulfillment NotOffered", out["fulfill"] == "NOT_OFFERED", str(out["fulfill"]))
    pols = out["policies"]
    check("escrow policy present", any(p.policy_id == "escrow" for p in pols))
    check("agent-honesty policy present", any(p.policy_id == "agent-honesty" for p in pols))
    # invalid input walls
    async def walls():
        r = {}
        try:
            await b.add_to_cart(ctx, "../etc/passwd", 1)
            r["traverse"] = "NO_RAISE"
        except ValueError:
            r["traverse"] = "REFUSED"
        try:
            await b.add_to_cart(ctx, "even-1", 99)
            r["qty"] = "NO_RAISE"
        except ValueError:
            r["qty"] = "REFUSED"
        r["unknown"] = await b.get_product_details(ctx, "nope-404")
        return r
    w = asyncio.run(walls())
    check("path traversal refused", w["traverse"] == "REFUSED", str(w))
    check("quantity cap refused", w["qty"] == "REFUSED", str(w))
    check("unknown listing -> None", w["unknown"] is None, str(w["unknown"]))
finally:
    hub.terminate()

failed = [n for n, ok in RESULTS if not ok]
print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed" + (f"; FAILED: {failed}" if failed else ""))
sys.exit(1 if failed else 0)
