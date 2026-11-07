#!/usr/bin/env python3
"""Phase 2 enrichment + paste-a-flyer (owner GO 2026-11-07): AI write-side compression.

Covers:
- EVERLIST_ENRICH=off (default): zero behavior change, no enrich fields
- stub mode: deterministic extraction lands in server-owned fields; sqlite FTS
  tags-cell merge makes the listing findable; public projection NEVER leaks
  _enrich_kw/_enrich; public tags untouched
- live mode (mocked local chat-completions server): keywords the AI adds that
  appear NOWHERE in title/desc/tags still make the listing findable in sqlite
  (the whole point of write-side compression) — and file-mode too (raw scan)
- fail-open law: live mode with dead URL or missing key NEVER fails a create;
  listing indexes on raw text exactly as before
- spoofing: client-supplied _enrich_kw/_enrich are stripped (unknown-field law)
- POST /listing/draft: token-gated, deterministic prefill (date/time/price/
  Ort:), NEVER creates anything, honest 400s, OpenAPI documents it
Run: ./venv/bin/python test_enrich.py
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
sys.path.insert(0, os.path.join(HERE, "sdk"))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "" if cond else detail)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


def _kill(p):
    if p:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()


_ACTIVE = []
atexit.register(lambda: [_kill(p) for p in _ACTIVE])


def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def spawn(env_extra=None):
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="hub-enrich-")
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(tmp, "state.json"),
           "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
    env.update(env_extra or {})
    logf = open(os.path.join(tmp, "hub.log"), "w")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), "hub did not start"
    return f"http://127.0.0.1:{port}", p, tmp


def req(method, path, body=None, headers=None, base=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    r = urllib.request.Request((base or HUB) + path,
                               data=(json.dumps(body).encode() if body is not None else None),
                               method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception:
        return -1, {}


HUB = ""


class _MockAI(BaseHTTPRequestHandler):
    """Deterministic OpenAI-compatible stub: always answers the same keywords."""

    def log_message(self, *a):
        pass

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        body = json.dumps({"choices": [{"message": {"content":
            "{\"kw\": [\"vegan-recipes\", \"cooking-course\", \"kochkurs\"]}"}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    global HUB

    # ---------- 1) OFF mode (default): zero behavior change ----------
    HUB, p, tmp = spawn()
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    st, l = req("POST", "/listings", {"vertical": "events", "title": "Off Mode Probe",
        "price": 5, "capacity": 5, "date": "2099-01-01", "location": "Vienna",
        "category": "meetup"}, headers={"X-Hub-Token": OWN})
    check("E1 off-mode create unchanged (201)", st == 201, f"{st} {str(l)[:120]}")
    st, det = req("GET", f"/listings/{l['id']}")
    check("E1 off-mode no enrich fields public",
          st == 200 and "_enrich_kw" not in det and "_enrich" not in det,
          str(list(det.keys()))[:160])
    p.terminate()

    # ---------- 2) STUB mode (file): server-owned + leak-free ----------
    HUB, p, tmp = spawn({"EVERLIST_ENRICH": "stub"})
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    st, l = req("POST", "/listings", {"vertical": "events", "title": "Permaculture Intro",
        "description": "Hands-on permaculture design intro for beginners.",
        "price": 5, "capacity": 5, "date": "2099-01-01", "location": "Vienna",
        "category": "workshop", "_enrich_kw": "spoofed-injection",
        "_enrich": {"mode": "fake"}}, headers={"X-Hub-Token": OWN})
    check("E2 stub create 201 (spoof fields in body tolerated)", st == 201, f"{st} {str(l)[:140]}")
    LID = l["id"]
    st, det = req("GET", f"/listings/{LID}")
    pub = det.get("listing", det)
    check("E2 projection leaks NO enrich fields",
          st == 200 and "_enrich_kw" not in str(pub) and "_enrich" not in str(pub),
          str(pub)[:200])
    check("E2 spoofed kw NOT effective (server-owned)",
          "spoofed-injection" not in str(pub), str(pub)[:160])
    st, s = req("GET", "/search?q=permaculture")
    check("E2 raw-text search still works (file mode)",
          st == 200 and s.get("count", 0) >= 1, f"{st} {s.get('count')}")
    p.terminate()

    # ---------- 3) STUB mode (sqlite): FTS tags-cell merge ----------
    HUB, p, tmp = spawn({"EVERLIST_ENRICH": "stub", "HUB_STORAGE_MODE": "sqlite"})
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    st, l = req("POST", "/listings", {"vertical": "events", "title": "Stadtgarten Workshop",
        "description": "Einfuehrung in Permakultur fuer Anfaenger.",
        "price": 5, "capacity": 5, "date": "2099-01-01", "location": "Vienna",
        "category": "workshop", "tags": ["gardening"]}, headers={"X-Hub-Token": OWN})
    check("E3 stub sqlite create 201", st == 201, f"{st} {str(l)[:140]}")
    LID = l["id"]
    st, s = req("GET", "/search?q=permakultur")
    ok = st == 200 and any(x["id"] == LID for x in s.get("listings", []))
    check("E3 stub kw findable via FTS merge (sqlite)", ok,
          f"{st} count={s.get('count')}")
    st, det = req("GET", f"/listings/{LID}")
    det.get("listing", det).get("tags", [])
    check("E3 public tags list untouched by AI",
          det.get("listing", det).get("tags") == ["gardening"],
          str(det.get("listing", det).get("tags")))
    p.terminate()

    # ---------- 4) LIVE mode (mocked AI): semantic keyword add ----------
    mock_port = free_port()
    mock = HTTPServer(("127.0.0.1", mock_port), _MockAI)
    threading.Thread(target=mock.serve_forever, daemon=True).start()
    HUB, p, tmp = spawn({"EVERLIST_ENRICH": "live",
                         "EVERLIST_ENRICH_URL": f"http://127.0.0.1:{mock_port}/v1/chat/completions",
                         "EVERLIST_ENRICH_API_KEY": "test-key",
                         "HUB_STORAGE_MODE": "sqlite"})
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    st, l = req("POST", "/listings", {"vertical": "events", "title": "Plant-based Cooking Class",
        "description": "Learn plant-based cooking basics, hands-on, small group.",
        "price": 18, "capacity": 8, "date": "2099-02-02", "location": "Vienna",
        "category": "workshop", "tags": ["cooking"]}, headers={"X-Hub-Token": OWN})
    check("E4 live create 201 (mocked AI)", st == 201, f"{st} {str(l)[:140]}")
    LID = l["id"]
    # 'vegan-recipes' appears NOWHERE in title/desc/tags — only the AI added it
    st, s = req("GET", "/search?q=vegan-recipes")
    ok = st == 200 and any(x["id"] == LID for x in s.get("listings", []))
    check("E4 AI-added synonym findable in sqlite (core value)", ok,
          f"{st} count={s.get('count')}")
    st, det = req("GET", f"/listings/{LID}")
    pub = det.get("listing", det)
    check("E4 leak-free despite live enrichment",
          "vegan-recipes" not in str(pub) and "_enrich" not in str(pub), str(pub)[:200])
    p.terminate()

    # ---------- 5) FAIL-OPEN: dead URL / missing key never fail a create ----------
    dead = free_port()  # nothing listens here
    HUB, p, tmp = spawn({"EVERLIST_ENRICH": "live",
                         "EVERLIST_ENRICH_URL": f"http://127.0.0.1:{dead}/v1/chat/completions",
                         "EVERLIST_ENRICH_API_KEY": "k", "EVERLIST_ENRICH_TIMEOUT_S": "0.2"})
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    t0 = time.time()
    st, l = req("POST", "/listings", {"vertical": "events", "title": "Dead URL Probe",
        "price": 5, "capacity": 5, "date": "2099-01-01", "location": "Vienna",
        "category": "meetup"}, headers={"X-Hub-Token": OWN})
    dt = time.time() - t0
    check("E5 dead AI URL -> create STILL 201 (fail-open)", st == 201, f"{st} {str(l)[:140]}")
    check("E5 fail-open bounded (~timeout, not hang)", dt < 8, f"{dt:.1f}s")
    st, s = req("GET", "/search?q=dead%20url%20probe")
    check("E5 fallback: raw text still findable",
          st == 200 and s.get("count", 0) >= 1, f"{st} {s.get('count')}")
    p.terminate()
    HUB, p, tmp = spawn({"EVERLIST_ENRICH": "live"})  # no key -> never calls
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    st, l = req("POST", "/listings", {"vertical": "events", "title": "No Key Probe",
        "price": 5, "capacity": 5, "date": "2099-01-01", "location": "Vienna",
        "category": "meetup"}, headers={"X-Hub-Token": OWN})
    check("E5 live-no-key -> create 201 (fail-open)", st == 201, f"{st} {str(l)[:140]}")
    p.terminate()
    mock.shutdown()

    # ---------- 6) POST /listing/draft: paste-a-flyer ----------
    HUB, p, tmp = spawn()
    st, res = req("POST", "/access", {"agent": "enr-owner", "acts": ["list"]})
    OWN = res["tokens"]["list"]
    flyer = ("Yoga am Morgen\nStartet den Tag mit sanftem Flow.\n"
             "2026-12-20 um 09:30\nOrt: Marktplatz Vienna\nBeitrag: €12,50")
    st, d = req("POST", "/listing/draft", {"text": flyer}, headers={"X-Hub-Token": OWN})
    dr = d.get("draft", {})
    check("E6 draft 200 token-gated", st == 200, f"{st} {str(d)[:140]}")
    check("E6 draft extracts title/date/time",
          dr.get("title") == "Yoga am Morgen" and dr.get("date") == "2026-12-20"
          and dr.get("time") == "09:30", str(dr)[:200])
    check("E6 draft extracts Ort + Euro price",
          dr.get("location") == "Marktplatz Vienna" and dr.get("price") == 12.5,
          str(dr)[:200])
    check("E6 draft includes description remainder", "sanftem Flow" in str(dr.get("description", "")),
          str(dr.get("description", ""))[:120])
    st, s = req("GET", "/search?q=Yoga%20am%20Morgen")
    seed_hits = s.get("count", 0)
    st, d2 = req("POST", "/listing/draft", {"text": "No Token Here"})
    check("E6 draft 401 without token", st == 401, f"{st}")
    st, d3 = req("POST", "/listing/draft", {"text": "   "}, headers={"X-Hub-Token": OWN})
    check("E6 draft 400 empty text", st == 400, f"{st}")
    st, d4 = req("POST", "/listing/draft", {"text": "x" * 20001}, headers={"X-Hub-Token": OWN})
    check("E6 draft 400 oversize text", st == 400, f"{st}")
    st, d5 = req("POST", "/listing/draft", {"text": flyer, "evil": 1}, headers={"X-Hub-Token": OWN})
    check("E6 draft ignores unknown body keys", st == 200, f"{st}")
    st, s2 = req("GET", "/search?q=Yoga%20am%20Morgen")
    check("E6 draft NEVER creates (count unchanged)",
          s2.get("count") == seed_hits, f"{seed_hits} -> {s2.get('count')}")
    st, oa = req("GET", "/openapi.json")
    check("E6 openapi documents /listing/draft",
          st == 200 and "/listing/draft" in oa.get("paths", {}),
          str(list(oa.get("paths", {}).keys()))[:200])
    p.terminate()

    failed = [n for n, ok in RESULTS if not ok]
    print(f"\nEnrichment: {len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:")
        for n in failed:
            print(f"  - {n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
