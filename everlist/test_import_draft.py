"""Import ladder v1 (owner GO 2026-11-12, docs/spec-import-and-badges-2026-11-12.md):
POST /listing/draft {url} — SSRF-walled fetch, JSON-LD -> meta -> text ladder,
DRAFT only (advice, never authority), needs_confirm [date,price], per-source
rate wall; chatlib 'import <url>' seeds the guided wizard; prod mode blocks
loopback. Run: python test_import_draft.py
"""
import atexit
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
from http.server import BaseHTTPRequestHandler, HTTPServer

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


JSONLD_PAGE = """<html><head>
<script type="application/ld+json">
{"@type":"Event","name":"ImportLadder Ceramics Evening",
 "description":"Two hours of clay, glaze and wine.",
 "startDate":"2026-12-05T18:30:00","location":{"@type":"Place","name":"Keramikstudio Wien"},
 "offers":{"@type":"Offer","price":"38.50","priceCurrency":"EUR"}}
</script></head><body><p>filler</p></body></html>"""
META_PAGE = ('<html><head><meta property="og:title" content="ImportLadder Paint Friday">'
             '<meta name="description" content="Bring wine, leave with art.">'
             '</head><body>minimal</body></html>')
TEXTY_PAGE = "<html><body>\nImportLadder Repair Cafe\n2026-12-06 14:00\n\u20ac5\n</body></html>"


class Fixture(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path.startswith("/jsonld"):
            body, ctype = JSONLD_PAGE.encode(), "text/html; charset=utf-8"
        elif self.path.startswith("/meta"):
            body, ctype = META_PAGE.encode(), "text/html; charset=utf-8"
        elif self.path.startswith("/texty"):
            body, ctype = TEXTY_PAGE.encode(), "text/html; charset=utf-8"
        elif self.path.startswith("/huge"):
            body = b"<html>" + b"x" * 1_100_000 + b"</html>"
            ctype = "text/html"
        elif self.path.startswith("/pdfish"):
            body, ctype = b"%PDF-1.4 nope", "application/pdf"
        else:
            body, ctype = b"nope", "text/plain"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


fx_port = free_port()
_fx = HTTPServer(("127.0.0.1", fx_port), Fixture)
threading.Thread(target=_fx.serve_forever, daemon=True).start()
FX = f"http://127.0.0.1:{fx_port}"


def spawn(extra_env=None):
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="hub-import-")
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(tmp, "state.json"),
           "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1",
           "EVERLIST_IMPORT_ALLOW_PRIVATE": "1",
           "HUB_LIMIT_DRAFT": "8",
           "EVERLIST_ENRICH": "off",
           **(extra_env or {})}
    logf = open(os.path.join(tmp, "hub.log"), "w")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), "hub did not start"
    return f"http://127.0.0.1:{port}", p, logf


def post(base, path, payload, token=None):
    r = urllib.request.Request(base + path, data=json.dumps(payload).encode(), method="POST",
                               headers={"Content-Type": "application/json",
                                        **({"X-Hub-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}


HUB, _hp, _hlog = spawn()
_, acc = post(HUB, "/access", {"agent": "import-tester", "acts": ["list"]})
TOK = acc["tokens"]["list"]

# ---- ladder: JSON-LD first ----
st, res = post(HUB, "/listing/draft", {"url": FX + "/jsonld"}, token=TOK)
check("A jsonld 200", st == 200, f"{st} {res}")
check("A engine jsonld", res.get("engine") == "jsonld", f"{res.get('engine')}")
check("A title", res.get("draft", {}).get("title") == "ImportLadder Ceramics Evening")
check("A date+time", res.get("draft", {}).get("date") == "2026-12-05" and
      res.get("draft", {}).get("time") == "18:30")
check("A price", res.get("draft", {}).get("price") == 38.5)
check("A location", res.get("draft", {}).get("location") == "Keramikstudio Wien")
check("A needs_confirm = date+price (advice law)",
      sorted(res.get("needs_confirm") or []) == ["date", "price"], f"{res.get('needs_confirm')}")
check("A import_source=url + source_url", res.get("import_source") == "url" and
      res.get("source_url") == FX + "/jsonld")

# ---- ladder: meta fallback ----
st, res = post(HUB, "/listing/draft", {"url": FX + "/meta"}, token=TOK)
check("B meta 200 + engine", st == 200 and res.get("engine") == "meta", f"{st} {res.get('engine')}")
check("B og:title draft", res.get("draft", {}).get("title") == "ImportLadder Paint Friday")

# ---- ladder: texty fallback ----
st, res = post(HUB, "/listing/draft", {"url": FX + "/texty"}, token=TOK)
check("C texty 200 + engine text", st == 200 and res.get("engine") == "text", f"{st} {res.get('engine')}")

# ---- walls (400s before the rate wall; 422s after a real fetch) ----
st, res = post(HUB, "/listing/draft", {"url": FX + "/jsonld", "text": "x"}, token=TOK)
check("W text+url 400", st == 400, f"{st}")
st, res = post(HUB, "/listing/draft", {"url": "ftp://example.com/x"}, token=TOK)
check("W non-http(s) url 400", st == 400, f"{st}")
st, res = post(HUB, "/listing/draft", {"url": FX + "/huge"}, token=TOK)
check("W oversized page -> 422 (never a fake draft)", st == 422, f"{st}")
st, res = post(HUB, "/listing/draft", {"url": FX + "/pdfish"}, token=TOK)
check("W non-html content-type -> 422", st == 422, f"{st}")
st, res = post(HUB, "/listing/draft", {"url": FX + "/nope"}, token=TOK)
check("W unknown page -> 422 + honest hint", st == 422 and "text" in str(res.get("hint", "")), f"{st} {res}")

# ---- text path regression (test_enrich pins this behaviour) ----
st, res = post(HUB, "/listing/draft", {"text": "Wine Tasting\n2026-12-10 19:00\n\u20ac25\nOrt: Wien"}, token=TOK)
check("R text draft still 200", st == 200 and res.get("draft", {}).get("title") == "Wine Tasting", f"{st} {res}")
check("R text path carries no needs_confirm", "needs_confirm" not in res)

# ---- chat journey: import seeds the wizard, wizard completes to a listing ----
import chatlib
S = "import-journey"
r1 = chatlib.handle_text(HUB, f"import {FX}/jsonld", sender=S)
check("J import reply previews draft", "ImportLadder Ceramics Evening" in r1 and
      "Nothing is published" in r1, r1[:160])
check("J needs-confirm warning shown", "Double-check" in r1)
check("J wizard seeded (category asked)", "[6/7]" in r1, r1[-200:])
r2 = chatlib.handle_text(HUB, "workshop", sender=S)   # category
check("J2 category accepted, capacity asked", "[7/7]" in r2, r2[:200])
r3 = chatlib.handle_text(HUB, "12", sender=S)         # capacity -> preview
check("J3 all filled -> confirm preview", "confirm" in r3.lower(), r3[:200])
r4 = chatlib.handle_text(HUB, "confirm", sender=S)
check("J4 confirm accepted without error", "cancel" not in r4.lower()[:30], r4[:200])
_q = urllib.request.urlopen(HUB + "/search?q=ImportLadder", timeout=10)
_hits = json.loads(_q.read().decode()).get("listings", [])
check("J5 listing PUBLISHED via seeded wizard", any("ImportLadder Ceramics Evening" == l.get("title") for l in _hits),
      f"{[l.get('title') for l in _hits]}")

# ---- mid-wizard break-out: hot intake, then 'import ...' takes over ----
S2 = "import-breakout"
chatlib.handle_text(HUB, "list", sender=S2)
r = chatlib.handle_text(HUB, f"import {FX}/meta", sender=S2)
check("K mid-wizard import breaks out + reseeds", "ImportLadder Paint Friday" in r and "[3/7]" in r, r[:200])

# ---- help row discoverability ----
r = chatlib.handle_text(HUB, "help", sender="import-help-check")
check("H help lists import", "import <link>" in r)

# ---- per-source rate wall LAST (cap 8; exactly 8 url drafts consumed above) ----
st, _ = post(HUB, "/listing/draft", {"url": FX + "/jsonld"}, token=TOK)
check("L rate wall 429 after cap", st == 429, f"{st}")

# ---- PROD mode: no allow-private -> loopback fixture refused (SSRF wall) ----
HUB2, _hp2, _hlog2 = spawn({"EVERLIST_IMPORT_ALLOW_PRIVATE": "0", "HUB_LIMIT_DRAFT": "30"})
_, acc2 = post(HUB2, "/access", {"agent": "import-prod", "acts": ["list"]})
TOK2 = acc2["tokens"]["list"]
st, res = post(HUB2, "/listing/draft", {"url": FX + "/jsonld"}, token=TOK2)
check("S prod mode blocks loopback fetch (422, no draft)", st == 422 and "draft" not in res, f"{st} {res}")

# ---- OpenAPI documents the url branch ----
with urllib.request.urlopen(HUB2 + "/openapi.json", timeout=10) as rr:
    _oa = rr.read().decode()
check("O openapi lists url branch", "share-a-link" in _oa and "SSRF-walled" in _oa)

print()
bad = [n for n, ok in RESULTS if not ok]
print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("ALL IMPORT-LADDER CHECKS PASSED")
