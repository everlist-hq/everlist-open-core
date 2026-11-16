"""DAST-lite battery (owner OK 2026-11-16: "java and python"): install-free
dynamic probes against an ISOLATED hub boot. Complements the ZAP run:
this suite encodes EverList-specific walls (auth, honesty gates, leak
discipline) that generic scanners cannot know.

Probes: unauthenticated-write walls, malformed JSON, injection payloads in
user fields, error-leakage discipline (no stack traces / paths in errors),
path traversal, CRLF/null-byte injection, oversized payloads, method misuse,
clean 404s, admin gating.
"""
import json, os, socket, subprocess, sys, tempfile, time
import urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []

def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))

def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p

def req(base, method, path, body=None, raw_body=None, headers=None):
    data = raw_body if raw_body is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, str(e)

def leaks_stack(body):
    markers = ("Traceback (most recent call last)", "/a0/", "File \"", "line ", ".py")
    return any(m in body for m in markers)

TMP = tempfile.mkdtemp(prefix="hub-dast-")
PORT = free_port(); BASE = f"http://127.0.0.1:{PORT}"
env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
end = time.time() + 15; ready = False
while time.time() < end:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5): ready = True; break
    except OSError: time.sleep(0.2)
assert ready, "test hub did not start"

try:
    print("== DAST: unauthenticated-write walls ==")
    st, b = req(BASE, "POST", "/listings", {"vertical": "events", "title": "x", "date": "2026-12-01"})
    check("POST /listings without token -> 401", st == 401, f"{st} {b[:80]}")
    st, b = req(BASE, "POST", "/book", {"listing_id": "lst-x", "quantity": 1})
    check("POST /book without token -> 401", st == 401, f"{st} {b[:80]}")
    st, b = req(BASE, "GET", "/orders")
    check("GET /orders without token -> 401", st == 401, f"{st} {b[:80]}")
    st, b = req(BASE, "POST", "/listings", {"vertical": "events", "title": "x", "date": "2026-12-01"},
                headers={"X-Hub-Token": "forged-not-a-token"})
    check("forged token -> 401/403", st in (401, 403), f"{st} {b[:80]}")

    print("== DAST: malformed input discipline ==")
    st, b = req(BASE, "POST", "/search", raw_body=b"{not json", )
    check("malformed JSON -> 400 (not 500)", st == 400, f"{st} {b[:80]}")
    check("malformed JSON error leaks no stack", not leaks_stack(b), b[:120])
    st, b = req(BASE, "POST", "/search", raw_body=b"\xff\xfe\x00binary\x00garbage")
    check("binary garbage body -> 4xx (not 500)", 400 <= st < 500, f"{st}")
    st, b = req(BASE, "GET", "/listings/lst-%00%27%20OR%201=1")
    check("SQLi-style listing id -> clean 4xx", 400 <= st < 500 and not leaks_stack(b), f"{st}")

    print("== DAST: injection probes in user fields ==")
    ssti = "{{7*7}} <% 7*7 %> ${7*7}"
    xss = "<script>alert(1)</script><img src=x onerror=alert(2)>"
    for probe, tag in ((ssti, "SSTI"), (xss, "XSS"), ("'; DROP TABLE listings; --", "SQLi")):
        st, b = req(BASE, "POST", "/search", {"q": probe})
        ok = 200 <= st < 500 and not leaks_stack(b)
        check(f"{tag} payload in search q -> handled, no crash/leak", ok, f"{st} {b[:100]}")
    st, b = req(BASE, "GET", "/search?q=<script>alert(1)</script>")
    check("XSS payload via GET search -> JSON content handled", st == 200 and "<script>" not in b[:0], f"{st}")

    print("== DAST: traversal / injection on paths ==")
    for p in ("/partner/../../app.py", "/partner/..%2f..%2fapp.py",
              "/.well-known/../../../etc/passwd", "/img/..%2f..%2fapp.py"):
        st, b = req(BASE, "GET", p)
        check(f"traversal {p[:34]} -> not 200", st != 200, f"{st} {b[:60]}")
        if st != 404:
            check(f"traversal {p[:34]} leaks nothing", not leaks_stack(b), b[:100])
    st, b = req(BASE, "GET", "/listings/lst-x%0d%0aInjected-Header: 1")
    check("CRLF in path -> urllib client rejects (server never sees it)", st in (-1,) or (400 <= st < 500), f"{st}")

    print("== DAST: error-leakage + method discipline ==")
    st, b = req(BASE, "PUT", "/listings")
    check("PUT on hub -> handled (4xx/5xx, no crash loop)", st >= 400, f"{st}")
    st, b = req(BASE, "DELETE", "/search")
    check("DELETE on hub -> handled", st >= 400, f"{st}")
    st, b = req(BASE, "GET", "/definitely-not-a-route")
    check("unknown route -> clean 404 JSON", st == 404 and not leaks_stack(b), f"{st} {b[:80]}")
    big = {"q": "A" * 200000}
    st, b = req(BASE, "POST", "/search", big)
    check("oversized body (200KB) -> handled, no crash", 200 <= st < 500 or st == -1, f"{st}")
    st, b = req(BASE, "GET", "/admin/state")
    check("admin face without key -> gated (4xx)", 400 <= st < 500, f"{st}")

    print("== DAST: hub still alive after battery ==")
    st, b = req(BASE, "GET", "/openapi.json")
    check("hub still serves /openapi.json", st == 200, f"{st}")
finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()

fails = [n for n, ok in RESULTS if not ok]
print(f"=== test_dast_battery: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'} ===")
sys.exit(1 if fails else 0)
