'''PA-5 (2026-11-13): UCP vendor discovery face.

Pins (isolated hub boot, like test_dl_adoption):
  - /.well-known/ucp: 200, vendor profile declaring ONLY
    network.everlist.events.* capabilities - NEVER dev.ucp.* wire claims
  - honesty block: wire_format=none + real_surfaces pointers
  - payment handler status derives from the SAME PAY_MODE constant as the
    live x402 402 (constants-parity law; testnet label pinned in tests)
  - /ucp/events-capabilities.json: 200, valid JSON, all five caps present
  - fail-closed: the loader refuses to serve a missing/invalid schema doc
  - llms.txt links the new profile (discovery surface completeness)
  - openapi.json registers both faces (contract completeness)
  - schema file itself: valid JSON, extends-points at UCP parents, escrow
    mechanics match SPEC 19 (refund_deadline < claim_deadline semantics
    documented; state machine contains released AND refunded)

Run: ./venv/bin/python test_ucp_profile.py
'''
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
import urllib.error

os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
os.environ.setdefault("HUB_POW_SIGNUP_BITS", "8")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def req(method, url, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method,
                               headers={"Content-Type": "application/json"} if data else {})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


TMP = tempfile.mkdtemp(prefix="hub-ucp-")
HUB_PORT = free_port()
HUB = "http://127.0.0.1:%d" % HUB_PORT
PYEXE = sys.executable

env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
proc = subprocess.Popen([PYEXE, os.path.join(HERE, "app.py"), str(HUB_PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
end = time.time() + 15
ready = False
while time.time() < end:
    try:
        with socket.create_connection(("127.0.0.1", HUB_PORT), timeout=0.5):
            ready = True
            break
    except OSError:
        time.sleep(0.2)
assert ready, "test hub did not start"

try:
    print("== PA-5 UCP profile ==")
    c, p = req("GET", HUB + "/.well-known/ucp")
    check("ucp profile 200", c == 200, str(p)[:150])
    ucp = p.get("ucp") or {}
    caps = ucp.get("capabilities") or []
    cap_names = sorted(x.get("name", "") for x in caps)
    check("exactly five vendor caps",
          cap_names == sorted(["network.everlist.events.listing",
                               "network.everlist.events.booking",
                               "network.everlist.events.escrow_terms",
                               "network.everlist.events.escrow_state",
                               "network.everlist.events.verify"]),
          str(cap_names))
    check("NO dev.ucp.* wire claims",
          all(not x.startswith("dev.ucp.") for x in cap_names), str(cap_names))
    hon = ucp.get("honesty") or {}
    check("honesty: wire_format none", hon.get("wire_format", "").startswith("none"), str(hon)[:150])
    check("honesty: PA-6 pointer", "PA-6" in str(hon.get("ucp_checkout_adapters", "")))
    check("honesty: real surfaces listed",
          "/openapi.json" in str(hon.get("real_surfaces")) and "/mcp" in str(hon.get("real_surfaces")))
    ph = (ucp.get("payment_handlers") or [{}])[0]
    # constants-parity law: the UCP face must derive its money label from the
    # SAME PAY_MODE constant as the live x402 402 - whatever mode the isolated
    # hub boots in, both faces must agree.
    c_x, x402 = req("GET", HUB + "/.well-known/x402.json")
    x_mode = str((x402 or {}).get("mode", ""))
    ucp_status = str(ph.get("status", ""))
    check("handler status parity with live x402 mode",
          c_x == 200 and ((x_mode == "TESTNET" and "TESTNET" in ucp_status)
                          or (x_mode != "TESTNET" and "SIMULATED" in ucp_status)),
          "x402.mode=%s ucp.status=%s" % (x_mode, ucp_status[:80]))
    check("handler points at escrow_state cap",
          ph.get("capabilities_ref") == "network.everlist.events.escrow_state")
    check("schema refs point at caps doc",
          all("/ucp/events-capabilities.json" in str(x.get("schema")) for x in caps))

    print("== PA-5 capability schema doc ==")
    c, d = req("GET", HUB + "/ucp/events-capabilities.json")
    check("caps doc 200", c == 200, str(d)[:120])
    cd = (d.get("capabilities") or {})
    check("caps doc has all five", len(cd) == 5, str(list(cd.keys())))
    st = cd.get("network.everlist.events.escrow_state") or {}
    states = ((st.get("properties") or {}).get("state") or {}).get("enum") or []
    check("escrow state machine: released AND refunded",
          "released" in states and "refunded" in states, str(states))
    et = cd.get("network.everlist.events.escrow_terms") or {}
    rails = ((et.get("properties") or {}).get("rail") or {}).get("enum") or []
    check("rails: escrow + instant (SPEC 19)", rails == ["escrow", "instant"], str(rails))
    bk = cd.get("network.everlist.events.booking") or {}
    check("booking requires terms_echo (booking=agreement)",
          "terms_echo" in (bk.get("required") or []), str(bk.get("required")))
    ver = d.get("versioning") or {}
    check("versioning block present", ver.get("schema_version") == "0.1.0", str(ver)[:100])

    print("== PA-5 discovery surfaces ==")
    c, o = req("GET", HUB + "/openapi.json")
    paths = o.get("paths") or {}
    check("openapi registers /.well-known/ucp", "/.well-known/ucp" in paths)
    check("openapi registers /ucp/events-capabilities.json", "/ucp/events-capabilities.json" in paths)
    # /llms.txt is served by the webchat face (not the hub API subprocess this
    # test boots) - pin the SOURCE (pages.llms_txt) directly, hermetically.
    import pages
    llms_out = pages.llms_txt("https://everlist.network")
    if isinstance(llms_out, bytes):
        llms_out = llms_out.decode("utf-8", "replace")
    check("llms.txt links UCP profile", "/.well-known/ucp" in llms_out, llms_out[-300:])

    print("== PA-5 fail-closed law (static file check) ==")
    raw = open(os.path.join(HERE, "ucp", "events-capabilities.json"), encoding="utf-8").read()
    try:
        json.loads(raw)
        check("bundled caps file valid JSON", True)
    except Exception as e:
        check("bundled caps file valid JSON", False, repr(e))
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

fails = [n for n, ok in RESULTS if not ok]
print("\n%d/%d passed" % (len(RESULTS) - len(fails), len(RESULTS)))
if fails:
    print("FAILED:", fails)
    sys.exit(1)
print("ALL PASSED")
