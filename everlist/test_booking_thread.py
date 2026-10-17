"""BOOKING-THREAD battery (owner law 2026-10-17: "always after my first test
it breaks somewhere"). Replays the owner's exact broken transcript end-to-end
through the REAL webchat stack plus the anomaly paths that lose chat state:

  search -> book paid CTA -> signup -> 'now book' -> 'what i said before'

Before the fix: T4 fell into the bare-name steer, T5 became a literal
search. After the fix every booking-shaped or referential follow-up keeps
the thread (Pay gate re-render or completed booking) — via the durable
LAST_BOOK_WANT ledger, never a fresh guess. Also pins the guards: a NEWER
search means the human moved on (no resurrection), dismissals never book,
German go-aheads work, and a free-listing gate auto-resumes after signup
into need_name -> 'Anna' -> Booked.
Run: python test_booking_thread.py (spawns own hub + webchat, brain pinned off)
"""
import json, os, socket, sys, tempfile, threading, time, atexit, subprocess
import urllib.request, urllib.error, http.cookiejar
HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, HERE)
os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
os.environ["EVERLIST_LLM_FIRST"] = "0"
import test_x402_settle as X4  # StubFacil reuse

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""), flush=True)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def main():
    tmp = tempfile.mkdtemp(prefix="bthread-")
    hub_port, wc_port = free_port(), free_port()
    stub = X4.StubFacil()
    env = dict(os.environ, HUB_PAY_MODE="testnet", HUB_SETTLE_MODE="auto",
               HUB_STATE_FILE=os.path.join(tmp, "state.json"),
               HUB_FACILITATOR_URL=stub.base("ok"),
               HUB_EMAIL_MODE="log", HUB_ADMIN_KEY="bt-admin",
               EVERLIST_BRAIN_DISABLED="1", EVERLIST_LLM_FIRST="0")
    hub_log = open(os.path.join(tmp, "hub.log"), "a")
    hub = subprocess.Popen([sys.executable, "app.py", str(hub_port)],
                           cwd=HERE, env=env, stdout=hub_log,
                           stderr=subprocess.STDOUT)
    atexit.register(lambda: hub.terminate())
    atexit.register(lambda: hub_log.close())
    end = time.time() + 20
    while time.time() < end:
        try:
            socket.create_connection(("127.0.0.1", hub_port), timeout=0.5)
            break
        except OSError:
            time.sleep(0.2)
    else:
        print("FATAL: hub not ready")
        return 1

    import webchat
    webchat.PORT = wc_port
    webchat.HUB_URL = f"http://127.0.0.1:{hub_port}"
    webchat.RL_IP_BURST = 200
    webchat.RL_IP_PER_MIN = 200
    webchat.RL_S_BURST = 50
    webchat.RL_S_PER_MIN = 200
    srv = webchat.ThreadingHTTPServer(("127.0.0.1", wc_port), webchat.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    atexit.register(srv.server_close)
    base = f"http://127.0.0.1:{wc_port}"

    def hub_call(method, path, obj=None, headers=None):
        r = urllib.request.Request(f"http://127.0.0.1:{hub_port}" + path,
            data=json.dumps(obj).encode() if obj is not None else None,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read().decode())

    d = hub_call("POST", "/access", {"agent": "bthread-seeder", "acts": ["list"]})
    ltok = d["tokens"]["list"]
    for p in (
        {"vertical": "events", "title": "Vinyl & Coffee Market — October Crates",
         "date": "2099-10-24", "location": "Vienna", "price": 5, "capacity": 20,
         "tags": ["vinyl", "market"], "description": "Crates."},
        {"vertical": "events", "title": "Free Morning Yoga in the Park",
         "date": "2099-07-01", "location": "Vienna", "price": 0, "capacity": 15,
         "tags": ["yoga"], "description": "Flow."},
    ):
        hub_call("POST", "/listings", p, {"X-Hub-Token": ltok})

    class C:
        def __init__(self):
            self.jar = http.cookiejar.CookieJar()
            self.op = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self.jar))

        def say(self, text):
            r = urllib.request.Request(base + "/api/chat",
                data=json.dumps({"text": text}).encode(), method="POST",
                headers={"Content-Type": "application/json"})
            try:
                with self.op.open(r, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    return json.loads(e.read().decode())
                except Exception:
                    return {}

    def is_pay_gate(d):
        return "payment_request" in d and isinstance(d.get("payment_request"), dict)

    def is_name_steer(r):
        return "Which one would you like? Say 'the first one'" in r

    # ------------------------------------------------------------------
    # 1) EXACT owner transcript (2026-10-17 prod break): every follow-up
    #    keeps the booking thread. T4/T5 were the breakage.
    # ------------------------------------------------------------------
    c = C()
    d1 = c.say("any events in vienna?")
    check("T1 search finds the paid listing", len(d1.get("results") or []) == 2,
          str(len(d1.get("results") or [])))

    d2 = c.say('Please book \u201cVinyl & Coffee Market \u2014 October Crates\u201d for me (even-1)')
    r2 = d2.get("reply") or ""
    check("T2 CTA hits the account gate", "paid listing" in r2.lower()
          and "signup" in r2.lower(), r2[:90])
    _want_after_t2 = {k: v for k, v in webchat.chatlib._LAST_BOOK_WANT.items()
                      if v.get("lid") == "even-1"}
    check("T2 thread stashed durably", bool(_want_after_t2),
          "no want recorded for even-1")

    d3 = c.say("signup")
    r3 = d3.get("reply") or ""
    check("T3 signup creates account + resumes Pay gate",
          "Account created" in r3 and is_pay_gate(d3),
          f"acct={'Account created' in r3} pay={is_pay_gate(d3)}")

    d4 = c.say("now book")
    r4 = d4.get("reply") or ""
    check("T4 'now book' re-offers the exact Pay gate (old: name steer)",
          is_pay_gate(d4) and "Vinyl" in r4 and not is_name_steer(r4), r4[:90])

    d5 = c.say("what i said before")
    r5 = d5.get("reply") or ""
    check("T5 'what i said before' keeps the thread (old: fresh search)",
          is_pay_gate(d5) and "Vinyl" in r5 and not r5.startswith("Nothing matched")
          and not is_name_steer(r5), r5[:90])

    # ------------------------------------------------------------------
    # 2) anomaly variant: the one-shot stash is LOST (board rewrite class);
    #    the durable want must still recover 'go ahead'. Anon user, so the
    #    correct recovery is the anon paid gate (signup ask) — the Pay button
    #    only arms after login.
    # ------------------------------------------------------------------
    c2 = C()
    c2.say("any events in vienna?")
    c2.say("book even-1")
    webchat.chatlib._PENDING_BOOK.clear()  # simulate the consumer-loss anomaly
    d2b = c2.say("go ahead")
    r2b = d2b.get("reply") or ""
    check("stash-loss anomaly: 'go ahead' keeps the thread (anon gate re-render)",
          "Vinyl" in r2b and "signup" in r2b.lower()
          and "paid listing" in r2b.lower() and not is_name_steer(r2b), r2b[:90])

    # ------------------------------------------------------------------
    # 3) changed-mind guard: a NEWER search after the gate means the human
    #    moved on — a later referential turn must NOT resurrect the booking.
    # ------------------------------------------------------------------
    c3 = C()
    c3.say("any events in vienna?")
    c3.say("book even-1")
    d3a = c3.say("show me free yoga")   # newer search thread
    d3b = c3.say("what i said before")  # referential, but want is stale now
    r3b = d3b.get("reply") or ""
    check("changed-mind guard: no resurrection after a newer search",
          not is_pay_gate(d3b), r3b[:90])

    # ------------------------------------------------------------------
    # 4) dismissal guard: 'no' / 'never mind' must never book.
    # ------------------------------------------------------------------
    c4 = C()
    c4.say("any events in vienna?")
    c4.say("book even-1")
    d4a = c4.say("never mind")
    r4a = d4a.get("reply") or ""
    check("dismissal never books", "Vinyl & Coffee Market" not in r4a
          or "paid listing" not in r4a.lower() or not is_pay_gate(d4a), r4a[:90])

    # ------------------------------------------------------------------
    # 5) German go-ahead after the gate: thread survives at the need_account
    #    stage ('Still holding your spot' — the designed reply).
    # ------------------------------------------------------------------
    c5 = C()
    c5.say("any events in vienna?")
    c5.say("book even-1")
    d5a = c5.say("jetzt buchen")
    r5a = d5a.get("reply") or ""
    check("German 'jetzt buchen' keeps the held spot",
          "Vinyl" in r5a and "holding your spot" in r5a.lower()
          and "signup" in r5a.lower() and not is_name_steer(r5a), r5a[:90])

    # ------------------------------------------------------------------
    # 6) free-listing journey: gate -> signup auto-resume -> name -> human
    #    check (email code, zero operators) -> book it -> Booked, then the
    #    want ledger is cleared (no zombie resurrection).
    # ------------------------------------------------------------------
    c6 = C()
    c6.say("any events in vienna?")
    d6a = c6.say("book even-2")
    r6a = d6a.get("reply") or ""
    check("free booking hits the account gate", "signup" in r6a.lower(), r6a[:90])
    d6b = c6.say("signup")
    r6b = d6b.get("reply") or ""
    check("signup auto-resumes into the name ask",
          "Account created" in r6b and "name" in r6b.lower(), r6b[-160:])
    d6c = c6.say("Anna")
    r6c = d6c.get("reply") or ""
    check("'Anna' rides through to the human check",
          "human check" in r6c.lower() or "email" in r6c.lower(), r6c[:90])
    d6d = c6.say("anna@example.com")
    r6d = d6d.get("reply") or ""
    check("email paste sends the verification code",
          "code" in r6d.lower(), r6d[:90])
    import re as _re
    _m = _re.findall(r"verification code: ([A-Za-z0-9]{6})",
                     open(os.path.join(tmp, "hub.log")).read())
    code6 = _m[-1] if _m else ""
    check("email code lands in hub log (dev mode)", bool(code6))
    d6e = c6.say(code6)
    r6e = d6e.get("reply") or ""
    check("code paste verifies + auto-resumes the held booking",
          "verified" in r6e.lower() and "Booked" in r6e, r6e[:160])
    d6f = c6.say("book it")
    r6f = d6f.get("reply") or ""
    check("post-success 'book it' gets the honest already-booked reply",
          "already booked" in r6f.lower()
          and "Free Morning Yoga" in r6f
          and not ("Vinyl" in r6f and "paid listing" in r6f.lower()), r6f[:110])
    d6g = c6.say("what i said before")
    r6g = d6g.get("reply") or ""
    check("no zombie resurrection after success",
          "already booked" in r6g.lower()
          or "Booked" not in r6g, r6g[:110])

    print("=" * 60)
    print(f"booking-thread battery: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("BOOKING_THREAD_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
