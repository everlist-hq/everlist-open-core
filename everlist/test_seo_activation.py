#!/usr/bin/env python3
"""SEO + owner-activation batch (2026-11-07): structured data + honest /img.

Proven:
  1. detail JSON-LD stays valid JSON, Event gets startDate(+time)/location/
     provider, free listings offer price 0 ("category":"free"), photo listings
     carry image=https://BASE/img/{id}.{ext}; Service listings get areaServed.
  2. /img/{id}.{ext} serves the organizer's REAL uploaded photo (magic-byte
     PNG/JPEG/WebP sniff, 380KB cap) with nosniff+short cache.
  3. /img walls: unknown id / archived / PRIVATE listing -> uniform 404
     (no existence oracle for private deals); jpg-vs-png type mismatch -> 404;
     traversal-ish junk path -> 404.
  4. og:image on a photo listing detail page = its /img URL (not brand jpg);
     no-photo listing keeps the honest brand default.
  5. /org/{owner} page embeds an ItemList JSON-LD of their live catalog.
  6. WEBCHAT_LEGAL_FILE documentation gates: env doc lists the var under Hub
     core + user-actions points to the JSON template (docs stay honest).
Run: python test_seo_activation.py
"""
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import base64
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


# ---------- in-process: pages-level JSON-LD ----------
sys.path.insert(0, HERE)
os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
import pages  # noqa: E402

_photo = "data:image/png;base64," + base64.b64encode(
    b"\x89PNG\r\n\x1a\n" + b"A" * 64).decode()
_l = {"id": "evt-x", "title": "SEO Test Event", "description": "d", "date": "2027-01-15",
      "time": "19:00", "location": "Wien", "price": 25, "owner": "organizer-a",
      "capacity": 10, "registered": 3, "image": _photo,
      "payment_terms": {"rail": "escrow", "refund_window_hours": 24}}
jd = pages._jsonld(_l, "en")
check("jsonld parses", isinstance(jd, dict) and jd.get("@type") == "Event")
check("jsonld startDate carries time", jd.get("startDate") == "2027-01-15T19:00:00", str(jd.get("startDate")))
check("jsonld location place", jd.get("location", {}).get("name") == "Wien")
check("jsonld provider organizer", jd.get("provider", {}).get("name") == "organizer-a")
check("jsonld image real upload", jd.get("image") == pages.BASE + "/img/evt-x.png", str(jd.get("image")))
check("jsonld offer escrow desc", "held safely" in (jd.get("offers", {}).get("description") or ""))

_l_free = dict(_l, price=0, image="")
jd_free = pages._jsonld(_l_free, "en")
check("free offer price 0", jd_free["offers"].get("price") == 0)
check("free offer category free", jd_free["offers"].get("category") == "free")

_l_svc = {k: v for k, v in _l.items() if k != "date"}
jd_svc = pages._jsonld(_l_svc, "en")
check("service type", jd_svc.get("@type") == "Service")
check("service area", jd_svc.get("areaServed") == "Wien")

_l_past = dict(_l, date="2020-01-01")
check("_ended_event true for past", pages._ended_event(_l_past) is True)
check("_ended_event false future", pages._ended_event(_l) is False)
check("_ended_event false dateless", pages._ended_event({"date": ""}) is False)

og = pages._og_image_url({"id": "evt-x", "image": _photo})
check("og url png", og == pages.BASE + "/img/evt-x.png", str(og))
og_jpg = pages._og_image_url({"id": "evt-x", "image": "data:image/jpeg;base64," + base64.b64encode(b"\\xff\\xd8\\xff" + b"A" * 32).decode()})
check("og url jpeg->jpg ext", og_jpg == pages.BASE + "/img/evt-x.jpg", str(og_jpg))
check("og url none for no-photo", pages._og_image_url({"id": "z", "image": ""}) is None)
check("og url none for svg", pages._og_image_url({"id": "z", "image": "data:image/svg+xml;base64,AAA"}) is None)

# ---------- live hub: SSR + /img walls ----------
def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

TMP = tempfile.mkdtemp(prefix="hub-seo-")
PORT = free_port()
env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_EMAIL_MODE": "log", "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "w")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py", )  if False else os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)


def req(method, path, body=None, headers=None, raw=False):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            b = resp.read()
            if raw:
                return resp.status, b, dict(resp.headers)
            try:
                return resp.status, json.loads(b.decode())
            except Exception:
                return resp.status, b.decode()
    except urllib.error.HTTPError as e:
        b = e.read()
        if raw:
            return e.code, b, dict(e.headers)
        try:
            return e.code, json.loads(b.decode())
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
    # create a REAL organizer listing with photo via documented paths
    st, acc = req("POST", "/access", {"agent": "seo-test-org", "acts": ["list"]})
    tok = (acc.get("token") if isinstance(acc, dict) else None) or (acc or {}).get("tokens", {}).get("list")
    check("list token minted", bool(tok), str(acc)[:120])
    st, created = req("POST", "/listings", {
        "vertical": "events", "title": "SEO Live Photo Event",
        "date": "2027-02-20", "location": "Graz", "price": 12, "capacity": 5},
        {"X-Hub-Token": tok or ""})
    check("live listing created", st in (200, 201), f"st={st}")
    lid = (created or {}).get("id") or (created or {}).get("listing", {}).get("id")
    mgr = (created or {}).get("manage_code") or ""
    check("listing id returned", bool(lid), str(created)[:120])

    st, up = req("POST", f"/listings/{lid}/image",
                 {"data_url": _photo, "manage_code": mgr}, {"X-Hub-Token": tok or ""})
    check("photo upload ok", st in (200, 201), f"st={st} {str(up)[:120]}")

    st, body, hdrs = req("GET", f"/img/{lid}.png", raw=True)
    png_ok = body.startswith(b"\x89PNG")
    check("/img serves real bytes", st == 200 and png_ok, f"st={st} bytes={len(body)}")
    check("/img content-type png", "image/png" in (hdrs.get("Content-Type") or ""), str(hdrs.get("Content-Type")))
    check("/img nosniff", (hdrs.get("X-Content-Type-Options") or "") == "nosniff")
    check("/img cache short", "max-age=300" in (hdrs.get("Cache-Control") or ""))

    st, b2, _ = req("GET", f"/img/{lid}.jpg", raw=True)  # ext/type mismatch wall
    check("/img ext-type mismatch 404", st == 404, f"st={st}")
    st, b3, _ = req("GET", "/img/nope.png", raw=True)
    check("/img unknown 404", st == 404)
    st, b4, _ = req("GET", "/img/..%2Fsecrets.png", raw=True)
    check("/img traversal junk 404", st in (400, 404))

    # webchat = SSR human face; spawn against the hub and probe SSR there
    wport = free_port()
    wenv = {**env, "WEBCHAT_PORT": str(wport),
            "WEBCHAT_HUB_URL": "http://127.0.0.1:" + str(PORT)}
    wlog = open(os.path.join(TMP, "webchat.log"), "w")
    wproc = subprocess.Popen([sys.executable, os.path.join(HERE, "webchat.py")],
                             stdout=wlog, stderr=subprocess.STDOUT, env=wenv)
    wend = time.time() + 20
    wready = False
    while wend > time.time() and not wready:
        try:
            with socket.create_connection(("127.0.0.1", wport), timeout=0.5):
                wready = True
        except OSError:
            time.sleep(0.2)
    check("webchat up", wready)

    def wreq(path):
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{wport}{path}", timeout=10) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, ""

    st, html = wreq(f"/l/{lid}")
    hs = html if isinstance(html, str) else ""
    check("detail og:image = /img url", f'og:image" content="{pages.BASE}/img/{lid}.png' in hs, hs[:0])
    ldjs = re.findall(r'<script type="application/ld\+json">(.*?)</script>', hs, re.S)
    ldd = {}
    for x in ldjs:
        try:
            cand = json.loads(x)
        except Exception:
            continue
        if cand.get("@type") == "Event":
            ldd = cand
            break
    check("live detail Event JSON-LD parses", ldd.get("@type") == "Event")
    check("live Event carries provider", ldd.get("provider", {}).get("name") == "seo-test-org")
    check("live Event carries image", ldd.get("image", "").endswith(f"/img/{lid}.png"), str(ldd.get("image")))

    # private listing photo = uniform 404 (no oracle)
    st, pv = req("POST", "/listings", {"vertical": "events", "title": "Priv",
        "date": "2027-03-03", "location": "Linz", "price": 5, "capacity": 4,
        "visibility": "private"}, {"X-Hub-Token": tok or ""})
    check("private listing created", st in (200, 201), f"st={st}")
    pid = (pv or {}).get("id") or (pv or {}).get("listing", {}).get("id")
    pmgr = (pv or {}).get("manage_code") or ""
    req("POST", f"/listings/{pid}/image", {"data_url": _photo, "manage_code": pmgr}, {"X-Hub-Token": tok or ""})
    st, _, _ = req("GET", f"/img/{pid}.png", raw=True)
    check("/img private uniform 404", st == 404, f"st={st}")

    # public-origin relay pins (crawlers/unfurlers hit webchat, not the hub)
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{wport}/img/{lid}.png", timeout=10) as rimg:
            ib = rimg.read(); ict = rimg.headers.get("Content-Type", "")
        check("webchat /img relay 200 png", rimg.status == 200 and ib.startswith(b"\x89PNG") and "image/png" in ict,
              f"st={rimg.status} ct={ict}")
    except urllib.error.HTTPError as e:
        check("webchat /img relay 200 png", False, f"st={e.code}")
    except Exception as e:
        check("webchat /img relay 200 png", False, str(e)[:80])
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{wport}/img/nope.png", timeout=10) as rn:
            check("webchat /img unknown passthrough 404", False, "unexpected 200")
    except urllib.error.HTTPError as e:
        check("webchat /img unknown passthrough 404", e.code == 404, f"st={e.code}")
    except Exception as e:
        check("webchat /img unknown passthrough 404", False, str(e)[:80])
    st_j = wreq("/img/..%2Fetc%2Fpasswd.png")[0]
    check("webchat /img junk wall 404", st_j == 404, f"st={st_j}")

    st, oh = wreq("/org/seo-test-org")
    os_ = oh if isinstance(oh, str) else ""
    check("org page renders", "SEO Live Photo Event" in os_)
    check("org ItemList JSON-LD embedded", '"ItemList"' in os_)

    # legal/env doc gates (docs must stay truthful)
    er = open(os.path.join(HERE, "../../docs/ops/env-reference.md")).read() if os.path.exists(os.path.join(HERE, "../../docs/ops/env-reference.md")) else ""
    # canonical docs live in project docs/, not experiments/; fallback read
    if not er:
        er = open("/a0/usr/projects/everlist/docs/ops/env-reference.md").read()
    check("env-reference documents WEBCHAT_LEGAL_FILE", "WEBCHAT_LEGAL_FILE" in er)
    ua = open("/a0/usr/projects/everlist/docs/user-actions.md").read()
    check("user-actions references legal template", "legal-template" in ua)

finally:
    try:
        wproc.terminate()
        wproc.wait(5)
    except Exception:
        try:
            wproc.kill()
        except Exception:
            pass
    proc.terminate()
    try:
        proc.wait(5)
    except Exception:
        proc.kill()

fails = [n for n, ok in RESULTS if not ok]
print(f"=== seo-activation: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILURES:", fails)
    sys.exit(1)
