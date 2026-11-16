"""Tier-1 partner kit (2026-11-16): security.txt, disclosure/DPA/SLA/
changelog faces, /status + /status.html.
Honesty contracts tested: security.txt is RFC 9116 text/plain; JSON faces
are valid JSON; /status carries the SAME PAY_MODE label as the live 402
(parity law), process-only uptime with an explicit no-history note; the
strict-allowlist asset server keeps the traversal wall; unknown assets 404.
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

def req(base, method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, dict(resp.headers), resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), (e.read().decode("utf-8", "replace") if e.fp else "")
    except Exception as e:
        return -1, {}, str(e)

TMP = tempfile.mkdtemp(prefix="hub-partnerkit-")
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
    print("== partner kit: security.txt (RFC 9116) ==")
    st, hd, body = req(BASE, "GET", "/.well-known/security.txt")
    check("GET /.well-known/security.txt -> 200", st == 200, str(st))
    check("content-type text/plain", "text/plain" in hd.get("Content-Type", ""), str(hd.get("Content-Type")))
    check("has Contact field", "Contact:" in body)
    check("has Expires field", "Expires:" in body)
    check("has Policy link", "Policy:" in body and "/partner/disclosure.json" in body)
    check("no PGP promise (no published key)", "Encryption:" not in body)

    print("== partner kit: JSON faces ==")
    for path in ("/partner/disclosure.json", "/partner/dpa.json",
                 "/partner/sla.json", "/partner/changelog.json",
                 "/partner/security-selfcheck.json"):
        st, hd, body = req(BASE, "GET", path)
        ok = st == 200 and "application/json" in hd.get("Content-Type", "")
        doc = {}
        try: doc = json.loads(body)
        except Exception: pass
        check(f"GET {path} -> 200 JSON", ok, f"{st} {hd.get('Content-Type')}")
        check(f"{path} has title+updated", bool(doc.get("title")) and bool(doc.get("updated")))
    st, hd, body = req(BASE, "GET", "/partner/dpa.json")
    dpa = json.loads(body)
    check("DPA carries subprocessor honesty note",
          bool(dpa.get("subprocessors", {}).get("current"))
          and "invented" in dpa.get("subprocessor_list_honesty", "")
          and "finalized per-partner" in dpa.get("subprocessor_list_honesty", ""))
    st, hd, body = req(BASE, "GET", "/partner/sla.json")
    sla = json.loads(body)
    check("SLA states no-credits honestly", "credits" in sla and "None" in str(sla["credits"]))
    st, hd, body = req(BASE, "GET", "/partner/security-selfcheck.json")
    sc = json.loads(body)
    check("self-check is honest (not a pentest)", "not a penetration test" in sc.get("honesty_note", ""))
    check("self-check lists what was NOT run", bool(sc.get("not_run_yet")))
    check("self-check dependency findings carry mitigations",
          all(f.get("mitigation") for f in sc.get("results", {}).get("dependencies", {}).get("findings", [])))

    print("== partner kit: /status honesty ==")
    st, hd, body = req(BASE, "GET", "/status")
    check("GET /status -> 200", st == 200, str(st))
    stt = json.loads(body)
    check("status operational", stt.get("status") == "operational")
    check("has payment_rail", bool(stt.get("payment_rail")))
    up = stt.get("uptime_process_seconds")
    check("process uptime is a small fresh number", isinstance(up, int) and 0 <= up < 120, str(up))
    check("no-history note present", "reset" in str(stt.get("uptime_note", "")))
    # parity law: rail label matches the x402 face mode
    st, _, body = req(BASE, "GET", "/.well-known/x402.json")
    x402 = json.loads(body)
    mode = x402.get("mode", "")
    if mode == "testnet":
        check("rail parity (TESTNET label)", "TESTNET" in stt["payment_rail"])
    else:
        check("rail parity (SIMULATED label)", "SIMULATED" in stt["payment_rail"])

    print("== partner kit: human face + walls ==")
    st, hd, body = req(BASE, "GET", "/status.html")
    check("GET /status.html -> 200 HTML", st == 200 and "text/html" in hd.get("Content-Type", ""),
          f"{st} {hd.get('Content-Type')}")
    check("status.html is noindex", 'noindex' in body)
    st, _, _ = req(BASE, "GET", "/partner/../../app.py")
    check("traversal wall: /partner/../ -> not 200", st != 200, str(st))
    st, _, _ = req(BASE, "GET", "/partner/nonexistent.json")
    check("unknown partner asset -> 404", st == 404, str(st))
    st, _, _ = req(BASE, "GET", "/partner/")
    check("directory itself -> not 200", st != 200, str(st))

    print("== partner kit: contract honesty ==")
    st, _, body = req(BASE, "GET", "/openapi.json")
    spec = json.loads(body)
    for p in ("/.well-known/security.txt", "/status", "/status.html",
              "/partner/disclosure.json", "/partner/dpa.json",
              "/partner/sla.json", "/partner/changelog.json",
              "/partner/security-selfcheck.json"):
        check(f"openapi documents {p}", p in spec.get("paths", {}))
    check("PartnerStatus schema exists",
          "PartnerStatus" in spec.get("components", {}).get("schemas", {}))
    # llms.txt is served by the webchat face (pages.py llms_txt), not the hub
    # port - check the generator directly (the webchat e2e covers the wire).
    import pages
    check("llms.txt carries Partner section", "## Partner" in pages.llms_txt().decode())
finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()

fails = [n for n, ok in RESULTS if not ok]
print(f"=== test_partner_kit: {'ALL PASSED' if not fails else str(len(fails)) + ' FAILED'} ===")
sys.exit(1 if fails else 0)
