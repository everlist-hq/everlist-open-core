"""SDK-conformance + drift suite (deep-run #8 T1; closes backlog Q2).
Exercises sdk/agenthub/client.py against a live ISOLATED hub — SDK calls only,
never raw HTTP. Boots its own hub on port 8951 with a throwaway state file.
Run: ./venv/bin/python test_sdk.py

Secret discipline: booking secrets / cancel tokens / manage codes are
referenced by variable only — never printed.
"""
import os
import signal
import socket
import subprocess
import sys
import time
import atexit

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from sdk.agenthub.client import AgentHub, HubError, HubNetworkError, DEFAULT_TIMEOUT  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, detail)


# ================= isolation: boot our own hub on 8951 =================
PORT = 8951
BASE = f"http://127.0.0.1:{PORT}"
SCRATCH = "/tmp/run8/t1"
STATE = os.path.join(SCRATCH, "state.json")
LOGF = os.path.join(SCRATCH, "hub.log")
VENV_PY = os.path.join(HERE, "venv", "bin", "python")
_ACTIVE = []
atexit.register(lambda: [_kill(p) for p in _ACTIVE])


def _kill(p):
    if p and p.poll() is None:
        try:  # kill the whole process group (app.py may spawn children)
            os.killpg(os.getpgid(p.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            p.terminate()
        try: p.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                p.kill()


os.makedirs(SCRATCH, exist_ok=True)
_probe = socket.socket()
try:
    _probe.bind(("127.0.0.1", PORT))
except OSError:
    print(f"FATAL: port {PORT} already in use - refusing to start", file=sys.stderr)
    sys.exit(2)
finally:
    _probe.close()

env = {**os.environ,
       "HUB_PORT": str(PORT),
       "HUB_STATE_FILE": STATE,
       "HUB_POW_SIGNUP_BITS": "8",   # B2: tests lower PoW cost (isolated instance)
       "HUB_POW_RECOVER_BITS": "8"}
log_fh = open(LOGF, "w")
proc = subprocess.Popen([VENV_PY, os.path.join(HERE, "app.py")], cwd=HERE,
                        stdout=log_fh, stderr=subprocess.STDOUT, env=env,
                        start_new_session=True)
_ACTIVE.append(proc)


def wait_ready(timeout=20):
    """Hub is up when GET /search answers (boot wait only - no sleeps elsewhere)."""
    end = time.time() + timeout
    probe = AgentHub(BASE, timeout=2)
    while time.time() < end:
        try:
            probe.search("warm")
            return True
        except HubNetworkError:
            time.sleep(0.25)
        except HubError:
            return True  # hub answered with an HTTP status -> it is up
    return False


assert wait_ready(), "isolated hub did not start on 8951 (see /tmp/run8/t1/hub.log)"

try:
    # ================= section 1: discovery + account token flow =================
    print("== discovery + signup/login token flow ==")
    sdk = AgentHub(BASE)
    check("default timeout knob exists", sdk.timeout == DEFAULT_TIMEOUT > 0,
          f"timeout={sdk.timeout}")
    verticals = sdk.list_verticals()
    check("verticals via SDK", "services" in verticals and "events" in verticals)

    owner = AgentHub(BASE)
    reg = owner.signup_keypair("sdk-owner")
    check("signup_keypair returns seed+pubkey", len(reg.get("seed", "")) == 64
          and len(reg.get("pubkey", "")) == 64)
    try:
        owner._token("list"); owner._token("book")
        has_tokens = True
    except HubError:
        has_tokens = False
    check("signup stores list+book tokens", has_tokens)

    buyer = AgentHub(BASE)
    buyer.signup_keypair("sdk-buyer")

    # account LOGIN flow: seed never travels; challenge-response mints tokens
    relogin = AgentHub(BASE)
    lr = relogin.login_seed(reg["seed"], "sdk-owner")
    check("login_seed returns tokens", bool(lr.get("tokens", {}).get("list")))
    check("login tokens are authorized (principal-scoped /bookings)",
          relogin.bookings() == [])

    # ================= section 2: add_listing returns SERVER truth =================
    print("== add_listing server truth + manage_code ==")
    free = owner.add_listing("services", title="SDK Free Consult", price=0,
                             provider="sdk-owner", category="consulting",
                             description="free tier consult")
    check("server id returned", bool(free.id))
    check("server truth: registered=0 available=True",
          free.registered == 0 and free.available is True)
    check("price echoed as number", free.price == 0.0)
    mc = (free.extra or {}).get("manage_code", "")
    check("one-time manage_code reachable as extra['manage_code']",
          mc.startswith("mgr-") and len(mc) > 10,
          f"present={bool(mc)}")  # never print the code itself
    got = owner.get_listing(free.id)
    check("get_listing returns same server record",
          got.id == free.id and got.available and got.registered == 0)

    paid = owner.add_listing("services", title="SDK Paid Design", price=12.5,
                             provider="sdk-owner", category="design")
    check("paid listing server truth", bool(paid.id) and paid.price == 12.5)

    # ================= section 3: search with qualifiers =================
    print("== search qualifiers (q / category / max_price) ==")
    hits = sdk.search("SDK Free Consult")
    check("full-text q finds free listing", any(h.id == free.id for h in hits))
    cat = sdk.search("SDK", category="design")
    check("category qualifier filters", any(h.id == paid.id for h in cat)
          and not any(h.id == free.id for h in cat))
    cap_lo = sdk.search("SDK", max_price=10)
    check("max_price cap excludes paid", any(h.id == free.id for h in cap_lo)
          and not any(h.id == paid.id for h in cap_lo))
    cap_hi = sdk.search("SDK", max_price=20)
    check("higher cap includes both", {h.id for h in cap_hi} >= {free.id, paid.id})

    # ================= section 4: book a EUR 0 WAIVED listing =================
    print("== booking: EUR 0 -> escrow WAIVED ==")
    bk = buyer.book(free.id, quantity=1, human_verified=True, client="Alice Ref")
    check("booking id returned", bool(bk.id))
    check("free booking escrow WAIVED", bk.escrow == "WAIVED")
    check("free booking amount 0", bk.amount == 0.0)
    check("booking secret returned once (held, not printed)", bool(bk.secret))
    check("cancel_token returned (held, not printed)", bool(bk.cancel_token))
    mine = buyer.bookings()
    check("bookings() principal-scoped contains it", any(b.id == bk.id for b in mine))
    check("owner orders() sees it", any(b.id == bk.id for b in owner.orders()))
    gb = buyer.get_booking(bk.id)
    check("get_booking shows WAIVED", gb.get("escrow") == "WAIVED")

    # ================= section 5: error paths =================
    print("== error paths: 401 / 403 / 404 ==")
    bad = AgentHub(BASE)
    bad._tokens["book"] = "garbage.definitely-not-a-token"  # simulated stolen/bad token
    try:
        bad.bookings()
        check("bad token rejected", False, "no exception raised")
    except HubError as e:
        check("bad token rejected (401-ish wall)", e.status == 401, f"status={e.status}")
    except HubNetworkError:
        check("bad token rejected", False, "network error, not HTTP 401")

    try:
        buyer.confirm(bk.id)  # buyer's list token does NOT own the listing
        check("confirm by non-owner rejected", False, "no exception raised")
    except HubError as e:
        check("confirm by non-owner -> 403", e.status == 403, f"status={e.status}")

    try:
        owner.get_listing("sdk-nope-404")
        check("unknown listing rejected", False, "no exception raised")
    except HubError as e:
        check("unknown listing -> 404", e.status == 404, f"status={e.status}")

    try:
        owner.confirm("sdk-nope-book")
        check("unknown booking confirm rejected", False, "no exception raised")
    except HubError as e:
        check("unknown booking confirm -> 404", e.status == 404, f"status={e.status}")

    # ================= section 6: owner confirm -> RELEASED, free-feedback rate ==
    print("== owner confirm -> RELEASED; rate() free feedback ==")
    conf = owner.confirm(bk.id)
    check("confirm response RELEASED", conf.get("escrow") == "RELEASED"
          and conf.get("ok") is True)
    check("free confirm pays 0.0", float(conf.get("owner_received", -1)) == 0.0)
    gb2 = buyer.get_booking(bk.id)
    check("buyer-visible escrow now RELEASED", gb2.get("escrow") == "RELEASED")

    rr = buyer.rate(bk.id, 5)
    check("rate accepted", rr.get("ok") is True and rr.get("rating") == 5)
    check("free booking rated in free-feedback channel",
          rr.get("channel") == "free-feedback")
    try:
        buyer.rate(bk.id, 4)
        check("double-rate rejected", False, "no exception raised")
    except HubError as e:
        check("double-rate -> 409", e.status == 409, f"status={e.status}")

    # ================= section 7: timeout plumbing (H11) =================
    print("== timeout plumbing ==")
    tiny = AgentHub(BASE, timeout=1.0)
    check("timeout param plumbs through constructor", tiny.timeout == 1.0)
    # non-routable IP: connect cannot complete -> HubNetworkError, fast
    dead = AgentHub("http://10.255.255.1:9", timeout=1.0)
    t0 = time.monotonic()
    try:
        dead.list_verticals()
        check("non-routable target raises", False, "no exception raised")
    except HubNetworkError:
        elapsed = time.monotonic() - t0
        check("non-routable target -> HubNetworkError (fast)", elapsed < 8,
              f"elapsed={elapsed:.1f}s")
    except HubError as e:
        check("non-routable target raises", False, f"unexpected HubError {e.status}")

    # HUB_SDK_TIMEOUT env is honored at import (one central knob)
    envrun = subprocess.run(
        [VENV_PY, "-c", "import sys; sys.path.insert(0, %r);"
         "import os; from sdk.agenthub.client import AgentHub, DEFAULT_TIMEOUT as d;"
         "c = AgentHub('http://127.0.0.1:1');"
         "print(d, c.timeout)" % HERE],
        env={**os.environ, "HUB_SDK_TIMEOUT": "2.5"},
        capture_output=True, text=True, timeout=30)
    got = envrun.stdout.strip().split()
    check("HUB_SDK_TIMEOUT env honored at import AND construction (run8 polish)",
          len(got) == 2 and got[0] == "2.5" and got[1] == "2.5",
          f"got={envrun.stdout.strip()!r}")

finally:
    _kill(proc)
    _ACTIVE.clear()
    log_fh.close()

# ================= verdict =================
fails = [n for n, ok in RESULTS if not ok]
print(f"\n=== sdk: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILED:", fails)
sys.exit(1 if fails else 0)
