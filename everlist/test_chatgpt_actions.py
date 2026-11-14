'''ChatGPT Actions face (2026-11-14, owner order: "fully in ChatGPT, payments too").

Pins (isolated hub boot, mirrors test_ucp_profile.py):
  - /openapi-actions.json: 200, parseable JSON, OpenAPI 3.0.x ONLY
    (ChatGPT Actions reject 3.1 - 3.0 is the compatibility law)
  - real-wire law: every path in the subset exists in the canonical
    /openapi.json contract; NO invented endpoints
  - honesty law: description pins confirm-before-booking, verbatim rail
    reporting, hosted-checkout link (never a fabricated payment)
  - contract completeness: /openapi.json self-description registers the face
  - discovery completeness: llms.txt links the face
  - fail-closed: hub boots WITHOUT a valid bundled spec answer 503,
    never garbage

Run: ./venv/bin/python test_chatgpt_actions.py
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


def req(url):
    r = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def boot_hub(state_dir):
    port = free_port()
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(state_dir, "state.json"),
           "PYTHONUNBUFFERED": "1"}
    logf = open(os.path.join(state_dir, "hub.log"), "a")
    proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                            stdout=logf, stderr=subprocess.STDOUT, env=env)
    end = time.time() + 15
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return proc, port
        except OSError:
            time.sleep(0.2)
    proc.kill()
    raise AssertionError("test hub did not start")


TMP = tempfile.mkdtemp(prefix="hub-chatgpt-")
try:
    proc, PORT = boot_hub(TMP)
    HUB = "http://127.0.0.1:%d" % PORT
    print("== ChatGPT Actions face ==")

    c, spec = req(HUB + "/openapi-actions.json")
    check("actions face 200", c == 200, str(spec)[:150])
    check("openapi 3.0.x only", str(spec.get("openapi", "")).startswith("3.0."), str(spec.get("openapi")))
    paths = sorted(spec.get("paths", {}).keys())
    expected = sorted(["/search", "/listings/{id}", "/access", "/book", "/bookings/{id}",
                       "/book/{id}/cancel", "/escrow/{id}/proof", "/checkout/sessions"])
    check("exactly the curated wire subset", paths == expected, str(paths))

    # real-wire law: every subset path must exist in the canonical contract
    c2, canonical = req(HUB + "/openapi.json")
    check("canonical openapi.json 200", c2 == 200, str(c2))
    canon_paths = set(canonical.get("paths", {}).keys())
    missing = [p for p in paths if p not in canon_paths]
    check("NO invented endpoints (all paths exist canonically)", not missing, str(missing))

    # honesty law pins in the spec description
    desc = str(spec.get("info", {}).get("description", ""))
    check("honesty: confirm-before-booking law", "confirm" in desc.lower() and "before" in desc.lower())
    check("honesty: verbatim rail reporting", "rail" in desc.lower())
    check("honesty: hosted checkout link (no fabricated payment)", "checkout" in desc.lower())

    # contract completeness: the canonical contract registers the face
    check("canonical contract registers the face", "/openapi-actions.json" in canon_paths)

    # discovery completeness: llms.txt links the face. /llms.txt is served by
    # the webchat face (not the hub API subprocess this test boots) - pin the
    # SOURCE directly, hermetically (same approach as test_ucp_profile.py).
    import pages
    llms_out = pages.llms_txt("https://everlist.network")
    if isinstance(llms_out, bytes):
        llms_out = llms_out.decode("utf-8", "replace")
    check("llms.txt links the ChatGPT Actions face", "openapi-actions.json" in llms_out)
finally:
    try:
        proc.kill()
    except Exception:
        pass

# fail-closed law: move the bundled spec -> fresh hub -> 503 (never garbage)
spec_path = os.path.join(HERE, "chatgpt", "openapi-actions.json")
if os.path.exists(spec_path):
    TMP2 = tempfile.mkdtemp(prefix="hub-chatgpt-fc-")
    os.rename(spec_path, spec_path + ".bak")
    try:
        proc2, PORT2 = boot_hub(TMP2)
        try:
            c3, body = req("http://127.0.0.1:%d/openapi-actions.json" % PORT2)
            check("fail-closed: missing spec -> 503", c3 == 503, str((c3, body))[:150])
            check("fail-closed: error names the file", "openapi-actions.json" in str(body.get("error", "")))
        finally:
            proc2.kill()
    finally:
        os.rename(spec_path + ".bak", spec_path)
else:
    check("fail-closed test skipped (spec file absent)", False, "chatgpt/openapi-actions.json missing")

failed = [n for n, ok in RESULTS if not ok]
print("== %d/%d passed ==" % (len(RESULTS) - len(failed), len(RESULTS)))
sys.exit(1 if failed else 0)
