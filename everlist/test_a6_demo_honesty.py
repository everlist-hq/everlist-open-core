#!/usr/bin/env python3
"""A6: launch honesty — demo/example supply is labeled everywhere (2026-11-04).
Owner call that settled it: "Sandra is not real!" — seed/curated boards must
never read as live organizers on ANY surface.

Proven:
  1. Server predicate walls: _is_demo_listing matches demo-seed sources and
     demo-*/everlist-org-*/escrow-sandbox owners; NEVER real organizer owners
     (acct-*, plain names). Client-claimed demo on a real listing is ignored.
  2. _pub_listing exposes demo:true ONLY on demo supply (server-derived, not
     client-suppliable — a real organizer cannot fake it either way).
  3. SPA cards render a visible chip (app.js) for demo listings.
  4. SSR detail pages render the curated-example banner EN + DE (i18n parity).
  5. Real listings carry NO banner/chip; the investor-era small print is gone.
  6. Legal drop-ins (WEBCHAT_LEGAL_FILE): routes 404 without a file; footer
     links appear only with real data; imprint/summary rows esc() input.
  7. OpenAPI Listing schema documents the demo flag.
Run: python test_a6_demo_honesty.py
"""
import io
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
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


# ---------- 1+2: predicate + pub flag (in-process) ----------
sys.path.insert(0, HERE)
import app  # noqa: E402

for l in app.LISTINGS:
    check(f"builtin seed {l['id']} flagged demo", app._is_demo_listing(l))

for own, want in [("demo-x", True), ("everlist-org-vienna", True),
                  ("escrow-sandbox", True), ("acct-demo", False),
                  ("julian-kutos", False), ("real-organizer", False),
                  ("demo", False)]:
    got = app._is_demo_listing({"owner": own})
    check(f"predicate owner {own!r} -> {want}", got == want)

check("predicate source demo-seed", app._is_demo_listing({"source": "demo-seed"}))
check("predicate client demo flag ignored",
      not app._is_demo_listing({"owner": "julian-kutos", "demo": True}))

pub = app._pub_listing({"id": "x", "owner": "demo-x", "manage_code_hash": "h"})
check("pub demo:true on demo supply", pub.get("demo") is True)
check("pub still hides server-only fields", "manage_code_hash" not in pub)
check("pub no demo key on real supply",
      "demo" not in app._pub_listing({"id": "y", "owner": "julian-kutos"}))

# ---------- live hub: API + SSR + legal gating ----------
def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


TMP = tempfile.mkdtemp(prefix="hub-a6-")
PORT = free_port()
env = {**os.environ,
       "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_EMAIL_MODE": "log",
       "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "w")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            raw = resp.read()
            try:
                return resp.status, json.loads(raw.decode())
            except Exception:
                return resp.status, raw.decode()
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


end = time.time() + 20
ready = False
while time.time() < end and not ready:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5):
            ready = True
    except OSError:
        time.sleep(0.2)
check("test hub up", ready)

try:
    st, lst = req("GET", "/listings")
    check("GET /listings 200", st == 200)
    items = lst.get("listings", []) if isinstance(lst, dict) else lst
    seeded = [x for x in items if x.get("id") in ("evt-1", "evt-2", "food-1", "food-2")]
    check("builtin seeds served", len(seeded) == 4, str(len(seeded)))
    check("all builtin seeds carry demo:true", all(x.get("demo") is True for x in seeded))

    # real organizer listing via the documented H16 path: /access list token
    st, acc = req("POST", "/access", {"agent": "julian-kutos-test", "acts": ["list"]})
    check("access token for real organizer", st in (200, 201), f"st={st} {acc}")
    tok = (acc.get("token") if isinstance(acc, dict) else None) or (acc or {}).get("tokens", {}).get("list")
    check("list token minted", bool(tok), str(acc)[:120])
    st, created = req("POST", "/listings", {
        "vertical": "events", "title": "Real Organizer Workshop",
        "date": "2027-01-15", "location": "Wien", "price": 25, "capacity": 10,
    }, {"X-Hub-Token": tok or ""})
    check("organizer listing created", st in (200, 201), f"st={st} {created}")
    lid = created.get("id") if isinstance(created, dict) else None
    check("created listing has id", bool(lid))

    st, lst2 = req("GET", "/listings")
    items2 = lst2.get("listings", []) if isinstance(lst2, dict) else lst2
    mine = [x for x in items2 if x.get("id") == lid]
    check("real listing served", len(mine) == 1)
    check("real listing has NO demo flag", mine and "demo" not in mine[0])

    import pages
    demo_l = {"id": "evt-1", "title": "Demo Thing", "demo": True,
              "date": "2027-01-15", "price": 10}
    en = pages.detail_html(demo_l, None, "en").decode()
    de = pages.detail_html(demo_l, None, "de").decode()
    check("SSR demo banner EN", "ldemo" in en and "Curated example" in en)
    check("SSR demo banner DE", "Kuratiertes Beispiel" in de and "kein aktiver Veranstalter" in de)
    real_en = pages.detail_html({"id": "r1", "title": "Real", "date": "2027-01-15"}, None, "en").decode()
    check("SSR real: no banner + small print gone",
          "ldemo" not in real_en and "test listing" not in real_en)

    # SPA chip law (source level — app.js renders server flag)
    js = io.open(os.path.join(HERE, "static", "app.js"), encoding="utf-8").read()
    check("SPA chip law present", "demochip" in js and "Curated example" in js)
    css = io.open(os.path.join(HERE, "static", "style.css"), encoding="utf-8").read()
    check("chip CSS present", ".demochip" in css and ".ldemo" in css)
    check("small print removed from pages.py",
          "test/demo flag is small print ONLY" not in io.open(os.path.join(HERE, "pages.py"), encoding="utf-8").read())

    # legal drop-ins are a WEBCCHAT concern (the human face). Phase 1: no file.
    def start_webchat(port, extra=None):
        wenv = {**env, "WEBCHAT_PORT": str(port), "WEBCHAT_HUB_URL": "http://127.0.0.1:" + str(PORT)}
        if extra:
            wenv.update(extra)
        wlog = open(os.path.join(TMP, "webchat-" + str(port) + ".log"), "w")
        wproc = subprocess.Popen([sys.executable, os.path.join(HERE, "webchat.py")],
                                 stdout=wlog, stderr=subprocess.STDOUT, env=wenv)
        wend = time.time() + 20
        wready = False
        while wend > time.time() and not wready:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    wready = True
            except OSError:
                time.sleep(0.2)
        return wproc, wready

    wport0 = free_port()
    wproc0, wready0 = start_webchat(wport0)
    check("webchat up (no legal file)", wready0)
    try:
        for path0 in ("/imprint", "/terms", "/support"):
            try:
                r0 = urllib.request.urlopen("http://127.0.0.1:" + str(wport0) + path0, timeout=10)
                st0, b0 = r0.status, r0.read().decode()
            except urllib.error.HTTPError as e0:
                st0, b0 = e0.code, ""
            check(path0 + " 404 without legal file", st0 == 404, "st=" + str(st0))
        h0 = urllib.request.urlopen("http://127.0.0.1:" + str(wport0) + "/", timeout=10).read().decode()
        check("footer has no legal links without file",
              'href="/imprint"' not in h0 and 'href="/support"' not in h0)
        # live SSR through webchat: a REAL organizer listing never renders the
        # curated-example banner (hub API flag absence -> detail_html path)
        rl = urllib.request.urlopen("http://127.0.0.1:" + str(wport0) + "/l/" + lid, timeout=10)
        rbody = rl.read().decode()
        check("SSR real listing: no banner",
              rl.status == 200 and "ldemo" not in rbody and "Curated example" not in rbody)
    finally:
        wproc0.terminate()
        try:
            wproc0.wait(5)
        except Exception:
            wproc0.kill()

    # with file: pages render from owner data only; values esc()d
    legal = {"imprint": {"name": "Owner <script>", "address": "Wien", "email": "o@x.at"},
             "terms": {"sections": [{"h": "S1", "body": "B1"}, "junk", {"h": "S2", "body": "B2"}]},
             "support": {"email": "help@x.at", "hours": "Mo-Fr"}}
    lf = os.path.join(TMP, "legal.json")
    io.open(lf, "w", encoding="utf-8").write(json.dumps(legal))
    # imprint rows escape input
    im = pages.imprint_html(legal, "en").decode()
    check("imprint escapes owner data", "&lt;script&gt;" in im and "<script>" not in im)
    check("imprint EN has ECG line", " 5 ECG" in im)
    imde = pages.imprint_html(legal, "de").decode()
    check("imprint DE parity", "Impressum" in imde and "Diensteanbieter" in imde)
    tm = pages.terms_html(legal, "en").decode()
    check("terms skips junk rows", "<b>S1</b>" in tm and "junk" not in tm and "<b>S2</b>" in tm)
    sup = pages.support_html(legal, "en").decode()
    check("support mailto", "mailto:help@x.at" in sup)
    check("support DE parity", "Streitf" in pages.support_html(legal, "de").decode())
    # with file: fresh webchat renders pages from the owner file
    wport = free_port()
    wproc, wready = start_webchat(wport, {"WEBCHAT_LEGAL_FILE": lf})
    check("webchat up (legal file)", wready)
    try:
        r = urllib.request.urlopen(f"http://127.0.0.1:{wport}/imprint", timeout=10)
        wbody = r.read().decode()
        check("/imprint 200 with legal file", r.status == 200 and "Diensteanbieter" not in wbody)
        check("/imprint shows escaped owner", "Owner &lt;script&gt;" in wbody)
        check("/imprint footer link present", "/support" in wbody)
        rr = urllib.request.urlopen(f"http://127.0.0.1:{wport}/support", timeout=10)
        check("/support 200 with legal file", rr.status == 200)
        r2 = urllib.request.urlopen(f"http://127.0.0.1:{wport}/terms", timeout=10)
        check("/terms 200 with legal file", r2.status == 200)
        # home footnav carries the legal links now
        rh = urllib.request.urlopen(f"http://127.0.0.1:{wport}/", timeout=10)
        check("footer legal links with file", "href=\"/imprint\"" in rh.read().decode())
    finally:
        wproc.terminate()
        try:
            wproc.wait(5)
        except Exception:
            wproc.kill()

    # OpenAPI documents the flag
    st, api = req("GET", "/openapi.json")
    check("openapi served", st == 200)
    check("openapi documents demo flag",
          "demo" in ((api.get("components") or {}).get("schemas") or {}).get("Listing", {}).get("properties", {}))

finally:
    proc.terminate()
    try:
        proc.wait(5)
    except Exception:
        proc.kill()

fails = [n for n, ok in RESULTS if not ok]
print(f"=== a6-demo-honesty: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
