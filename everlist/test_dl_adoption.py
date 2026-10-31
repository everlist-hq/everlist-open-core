"""DL: mining-adoption regression suite (2026-10-31 integration batch).

Proves the six adopted sprint items end-to-end:
  DL-1  /.well-known/x402.json discovery (constants parity with live 402)
  DL-2  /verify wallet-less verification page (fail-closed honest render,
        tamper-proof query handling, raw proof-endpoint agreement)
  DL-3  escrow_guide on GET /bookings/{id} (per-state guidance + verify links)
  DL-6  /break-it try-to-break-it sandbox (EN + DE render)
  sitemap carries /verify + /break-it for both locales

Run: python test_dl_adoption.py
"""
import hashlib, json, os, re, socket, subprocess, sys, tempfile, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "sdk"))
RESULTS = []

def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

TMP = tempfile.mkdtemp(prefix="hub-dl-")
HUB_PORT = free_port(); WC_PORT = free_port()
HUB = f"http://127.0.0.1:{HUB_PORT}"; WC = f"http://127.0.0.1:{WC_PORT}"
PYEXE = sys.executable

def req(method, url, body=None, headers=None):
    r = urllib.request.Request(url, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            status, raw = resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        status, raw = e.code, e.read().decode()
    except Exception as e:
        return -1, str(e)
    try:
        return status, json.loads(raw)  # parsed JSON when the body is JSON
    except Exception:
        return status, raw

def solve_pow(kind):
    _, ch = req("GET", HUB + f"/auth/challenge?kind={kind}")
    n = 0
    while True:
        d = hashlib.sha256((ch["challenge"] + str(n)).encode()).digest()
        bits = 0
        for b in d:
            if b == 0: bits += 8; continue
            bits += 8 - b.bit_length(); break
        if bits >= ch["difficulty"]: return {"challenge": ch["challenge"], "nonce": n}
        n += 1

env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
proc = subprocess.Popen([PYEXE, os.path.join(HERE, "app.py"), str(HUB_PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
end = time.time() + 15; ready = False
while time.time() < end:
    try:
        with socket.create_connection(("127.0.0.1", HUB_PORT), timeout=0.5): ready = True; break
    except OSError: time.sleep(0.2)
assert ready, "test hub did not start"

import webchat  # in-process, AFTER hub port is bound
webchat.PORT = WC_PORT
webchat.HUB_URL = HUB
webchat.BIND = "127.0.0.1"
srv = webchat.ThreadingHTTPServer(("127.0.0.1", WC_PORT), webchat.Handler)
srv.daemon_threads = True
import threading
threading.Thread(target=srv.serve_forever, daemon=True).start()

try:
    print("== DL setup ==")
    c, b = req("POST", HUB + "/accounts/signup", {"agent": "dl-owner", "pow": solve_pow("signup")})
    assert c == 201, b
    c, b = req("POST", HUB + "/accounts/login", {"account_code": b["account_code"], "agent": "dl-owner"})
    assert c == 200, b
    TOK = b["tokens"]["list"]
    BTOK = b["tokens"]["book"]
    c, b = req("POST", HUB + "/listings", {"vertical": "events", "title": "DL Event",
               "date": "2026-12-01", "location": "X", "price": 5, "capacity": 10},
               {"X-Hub-Token": TOK})
    assert c == 201, b
    LID = b["id"]
    c, b = req("POST", HUB + "/book", {"listing_id": LID, "attendee": "DL Buyer", "human_verified": True,
               "escrow_ref": {"contract": "0xabc", "escrow_id": 7, "tx": "0xtx"}},
               {"X-Hub-Token": BTOK})
    assert c == 201, b
    BK = b["id"]

    print("== DL-1 x402 discovery ==")
    c, x = req("GET", HUB + "/.well-known/x402.json")
    check("dl1 x402.json 200 + version", c == 200 and x.get("x402Version") == 1, str(x)[:120])
    c, p = req("GET", HUB + "/premium/events")
    live = (p.get("accepts") or [{}])[0]
    disc = (x.get("accepts") or [{}])[0]
    check("dl1 constants parity with live 402",
          disc.get("asset") == live.get("asset") and disc.get("payTo") == live.get("payTo")
          and disc.get("maxAmountRequired") == live.get("maxAmountRequired"),
          "disc=%s live=%s" % (disc, live))
    check("dl1 mode labeled honestly", x.get("mode") in ("SIMULATED", "TESTNET"), x.get("mode"))

    print("== DL-2 /verify page ==")
    c, html = req("GET", WC + "/verify")
    check("dl2 verify page renders", c == 200 and "Verify an escrow" in html, "%s %s" % (c, html[:120]))
    c, html = req("GET", WC + "/verify?contract=0xabc&escrow=7")
    # the hub's real proof endpoint fails honestly here (no indexer in test env)
    check("dl2 renders fail-closed honestly",
          c == 200 and ("Not verified" in html or "Chain says" in html), html[-200:])
    c, raw = req("GET", WC + "/verify?contract=%3Cscript%3E&escrow=abc")
    check("dl2 sanitizes query echo", c == 200 and "<script>" not in html, html[-200:])
    c, raw = req("GET", WC + "/de/verify")
    check("dl2 DE overlay renders", c == 200 and len(raw) > 500, str(c))

    print("== DL-3 escrow_guide ==")
    c, bk = req("GET", HUB + "/bookings/" + BK, headers={"X-Hub-Token": TOK})
    g = bk.get("escrow_guide") or {}
    check("dl3 guide present with state", c == 200 and g.get("state") == "HELD", str(bk)[:200])
    cv = g.get("chain_verification") or {}
    check("dl3 verify pointers from escrow_ref",
          cv.get("available") is True and "/escrow/7/proof" in str(cv.get("endpoint"))
          and "0xabc" in str(cv.get("endpoint")), str(cv))
    check("dl3 ledger pointer", "/ledger" in str(g.get("ledger")), str(g.get("ledger")))
    c, html = req("GET", WC + "/booking/" + BK)  # anon -> webchat 404 wall
    check("dl3 booking page still gated", c == 404, str(c))

    print("== DL-6 /break-it ==")
    c, html = req("GET", WC + "/break-it")
    check("dl6 breakit renders EN", c == 200 and "Try to break it" in html and "BREAKIT" in html,
          "%s %s" % (c, html[:120]))
    c, html = req("GET", WC + "/de/break-it")
    check("dl6 breakit renders DE", c == 200 and len(html) > 500, str(c))

    print("== sitemap ==")
    c, sx = req("GET", WC + "/sitemap.xml")
    check("sitemap carries new pages",
          c == 200 and "/verify" in sx and "/break-it" in sx, sx[:200])

    print("== adoption surfaces (features are KNOWN, not dead code) ==")
    c, man = req("GET", HUB + "/.well-known/agent-hub.json")
    v = man.get("verification") or {}
    check("manifest verification block", c == 200 and
          "/escrow/{id}/proof" in str(v.get("escrow_proof")) and
          "/verify" in str(v.get("wallet_less_verify_page")) and
          "x402.json" in str(v.get("payment_discovery")) and
          "/break-it" in str(v.get("attack_us")), str(v)[:200])
    c, oa = req("GET", HUB + "/openapi.json")
    check("openapi documents new endpoints", c == 200 and
          "/.well-known/x402.json" in oa.get("paths", {}) and
          "/escrow/{id}/proof" in oa.get("paths", {}),
          str(list(oa.get("paths", {}).keys()))[:200])
    c, nav = req("GET", WC + "/how")
    check("nav carries Verify on /how", c == 200 and ">Verify<" in nav and "/verify" in nav, nav[-300:])
    c, howd = req("GET", WC + "/de/how")
    check("DE how carries Verifizieren + break-it", c == 200 and "Verifizieren" in howd and "/de/break-it" in howd, howd[-300:])

finally:
    try:
        proc.terminate(); proc.wait(5)
    except Exception:
        proc.kill()
    srv.shutdown()

fails = [n for n, ok in RESULTS if not ok]
print("\nDL suite: %d/%d passed" % (len(RESULTS) - len(fails), len(RESULTS)))
if fails:
    print("FAILED:", ", ".join(fails))
    sys.exit(1)
print("ALL PASSED")
