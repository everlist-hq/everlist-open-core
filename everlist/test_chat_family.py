"""Family relaxation + honest-results labeling (owner 2026-10-19).

Pins the smart-relaxation contract end to end against an isolated hub:
  - a keyword inside a food auto-tag family that matches NO listing relaxes
    honestly ('No <kw> on the board right now — but N food experience(s)...')
    — never other cities, never invented numbers
  - the quoted count EQUALS the stash size (board chip honesty), the stash is
    suggestion-labeled (results_kind='suggestions') and referenceable
  - gibberish stays the honest generic no-match (no family invention)
  - agent (non-web) surfaces keep the referenceable 'coming up' rows
  - free-search relaxation never leaks paid items (money honesty)

Design note (suite lesson 2026-10-19): dead keywords are chosen AT RUNTIME
through the real chat path — the hub seed and its FUZZY matching drift, so
hard-coded 'absent' keywords rot silently ('pizzeria' fuzzily matched the
seeded 'Margherita Pizza' and bypassed the whole branch).

Run: ./venv/bin/python test_chat_family.py
"""
import atexit
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chatlib  # noqa: E402

# Deterministic tier only (same pin as test_chat_help).
os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
import brain as _brain_hermetic  # noqa: E402
_brain_hermetic._DISABLED = True

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    d = str(detail).encode("utf-8", "backslashreplace").decode("utf-8")
    print(("PASS" if cond else "FAIL"), name, ("" if cond else d))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


PORT = free_port()
TMP = tempfile.mkdtemp(prefix="hub-family-")


def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


logf = open(os.path.join(TMP, "hub.log"), "w")
env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
assert wait_ready(PORT)
HUB = "http://127.0.0.1:%d" % PORT
atexit.register(lambda: (proc.terminate(), logf.close()))


def _hub_post(path, obj, headers=None):
    rq = urllib.request.Request(HUB + path, data=json.dumps(obj).encode(),
                                headers={"Content-Type": "application/json", **(headers or {})},
                                method="POST")
    with urllib.request.urlopen(rq, timeout=10) as r:
        return json.loads(r.read().decode())


# ---- fixtures: one FREE + one PAID food listing (titles keep 'pizza' on
# purpose: relaxation must key on the FAMILY, not on the dead keyword) ------
_tok = _hub_post("/access", {"agent": "family-suite", "acts": ["list"]}).get("tokens", {}).get("list", "")
_cre = _hub_post("/listings", {"vertical": "events",
                               "title": "Trattoria Night — four courses",
                               "description": "Italian dinner at a family kitchen in Vienna",
                               "date": "2099-01-01", "location": "Vienna",
                               "price": 0, "capacity": 8},
                 {"X-Hub-Token": _tok})
assert _cre.get("id"), _cre
_tok2 = _hub_post("/access", {"agent": "family-suite2", "acts": ["list"]}).get("tokens", {}).get("list", "")
_hub_post("/listings", {"vertical": "events",
                        "title": "Paid Pizza Workshop",
                        "description": "hands-on baking class, dinner included",
                        "date": "2099-02-02", "location": "Vienna",
                        "price": 15, "capacity": 6},
          {"X-Hub-Token": _tok2})


def _family_word(kw):
    return any(re.search(rx, kw, re.I) for _, rx in chatlib._AUTO_TAG_RULES)


# ---- runtime dead-keyword calibration (see design note) --------------------
KW = None
for _kw in ("brunch", "lunch", "bbq", "grill", "breakfast", "restaurant",
            "vegetarian", "menu", "kitchen", "catering"):
    if not _family_word(_kw):
        continue
    _probe = chatlib.handle_text(HUB, _kw, sender="probe-%s-%d" % (_kw, os.getpid()))
    if _probe.startswith("Nothing matched"):
        KW = _kw
        break
check("calibration: found a family word that zero-matches", KW is not None,
      "no candidate relaxed; seed drifted too far")
if KW is None:
    print("FAMILY_FAILURES")
    sys.exit(1)

# ---- 1. the owner's exact shape --------------------------------------------
WEB = "web-family-%d" % os.getpid()
r1 = chatlib.handle_text(HUB, KW + "?", sender=WEB)
_stash = chatlib.last_results(WEB)
_N = len(_stash)
_plural = "" if _N == 1 else "s"
_verb = "is" if _N == 1 else "are"
_expected = "No %s on the board right now — but %d food experience%s %s" % (KW, _N, _plural, _verb)
check("family: honest prefix kept", r1.startswith("Nothing matched"), r1[:80])
check("family: owner line fires with quoted count == stash",
      _expected in r1 and "open for you on the board" in r1 and _N >= 1,
      "N=%d %r" % (_N, r1[:140]))

# ---- 2. stash honesty -------------------------------------------------------
check("family: labeled suggestions", chatlib.last_results_kind(WEB) == "suggestions")

# ---- 3. suggestions stay referenceable -------------------------------------
r3 = chatlib.handle_text(HUB, "show 1", sender=WEB)
check("family: 'show 1' resolves the stash",
      str(_stash[0].get("id")) in r3 if _stash else False, r3[:90])

# ---- 4. gibberish stays generic --------------------------------------------
WEB2 = "web-family-gib-%d" % os.getpid()
r4 = chatlib.handle_text(HUB, "zzzqqqxyzzy", sender=WEB2)
check("gibberish: honest no-match, no family invention",
      r4.startswith("Nothing matched") and "right now — but" not in r4, r4[:90])

# ---- 5. agent surfaces keep the referenceable rows -------------------------
AG = "agent-family-%d" % os.getpid()
r5 = chatlib.handle_text(HUB, KW + "?", sender=AG)
check("agent: family line + coming-up rows",
      ("No %s on the board right now" % KW) in r5 and "coming up" in r5
      and "show " in r5, r5[:120])

# ---- 6. money honesty under filters (branch-agnostic) -----------------------
# 'free <kw>' may legitimately hit the free listing as REAL results ('1 found
# — free only') or fire relaxation — either branch is honest. The invariant:
# the PAID workshop never appears, and whatever gets stashed is free.
WEB3 = "web-family-free-%d" % os.getpid()
r6 = chatlib.handle_text(HUB, "free " + KW, sender=WEB3)
_stash3 = chatlib.last_results(WEB3)
_leak = any("workshop" in str(l.get("title") or "").lower() for l in _stash3)
_free_only = all(float(l.get("price") or 0) == 0 for l in _stash3)
check("free filter: paid workshop never leaks, stash is free-only",
      not _leak and _free_only and ("workshop" not in r6.lower()), r6[:140])

# ---- 7. city-qualified zero-match: never suggests other cities --------------
WEB4 = "web-family-qual-%d" % os.getpid()
r7 = chatlib.handle_text(HUB, KW + " in graz", sender=WEB4)
check("city-qualified zero-match: honest + never suggests Vienna listings",
      "Nothing matched" in r7 and "Trattoria" not in r7
      and "open for you on the board" not in r7, r7[:110])
_n_pass = sum(1 for _, ok in RESULTS if ok)
_n_fail = len(RESULTS) - _n_pass
print("\nfamily suite: %d passed, %d failed" % (_n_pass, _n_fail))
print("FAMILY_ALL_PASSED" if not _n_fail else "FAMILY_FAILURES")
sys.exit(1 if _n_fail else 0)
