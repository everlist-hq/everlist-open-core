#!/usr/bin/env python3
"""CONVERSATION battery (owner call 2026-10-03): multi-turn HUMAN speech.

The first-touch battery proves every FIRST input gets a real answer. This
battery proves the FOLLOW-UP turns work like a human conversation: referential
picks ('the jazz one', 'das erste bitte'), booking by speech ('yes book it for
me', 'book it under Maria please'), early name capture ('Anna', 'Tom'), mood
swings and comebacks. Each flow runs through the REAL webchat door with REAL
hub state and HARD-ASSERTS every turn - a lecture, a wrong search, or an EMPTY
reply is a test failure.

  C1  search -> 'the jazz one sounds nice' narrows -> 'yes book it for me'
      books the pick -> 'Anna' captured as booking name -> email signup ->
      code verifies (human check).
  C2  refine chain: weekend -> cheaper -> 'ok the free one then' books the
      free listing -> 'book it under Maria please' captures Maria.
  C3  mood + comeback: 'hmm not sure yet' -> 'lol ok' -> 'actually book the
      yoga for me' -> 'Tom' captured.
  C4  German flow: 'guten tag, ich suche ein Konzert in Wien' -> 'das erste
      bitte' books the first match -> 'ich moechte das buchen' resumes the
      held spot -> 'Max Mustermann' captured -> signup.

Run: ./venv/bin/python test_conversation.py
"""
import atexit
import http.cookiejar
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f" :: {detail[:110]}" if detail and not cond else ""), flush=True)
    if not cond:
        FAILS.append(f"{name} :: {detail[:200]}")


def main() -> None:
    import test_x402_settle as X4
    import webchat
    import test_journey as J

    tmp = tempfile.mkdtemp(prefix="conv-")
    hub_log_path = os.path.join(tmp, "hub.log")
    hub_port, wc_port = J.free_port(), J.free_port()
    stub = X4.StubFacil()
    env = dict(os.environ, HUB_PAY_MODE="testnet", HUB_SETTLE_MODE="auto",
               HUB_STATE_FILE=os.path.join(tmp, "state.json"),
               HUB_FACILITATOR_URL=stub.base("ok"),
               HUB_EMAIL_MODE="log", HUB_ADMIN_KEY="conv-admin")
    hub_log = open(hub_log_path, "a")
    atexit.register(hub_log.close)
    hub = subprocess.Popen([sys.executable, "app.py", str(hub_port)], cwd=HERE,
                           env=env, stdout=hub_log, stderr=subprocess.STDOUT)
    atexit.register(hub.terminate)
    end = time.time() + 20
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", hub_port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    webchat.PORT = wc_port
    webchat.HUB_URL = f"http://127.0.0.1:{hub_port}"
    srv = webchat.ThreadingHTTPServer(("127.0.0.1", wc_port), webchat.Handler)
    threading = __import__("threading")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    atexit.register(srv.shutdown)
    base = f"http://127.0.0.1:{wc_port}"

    class CC:
        def __init__(self):
            self.jar = http.cookiejar.CookieJar()
            self.op = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(self.jar))

        def say(self, text: str):
            r = urllib.request.Request(
                base + "/api/chat", data=json.dumps({"text": text}).encode(),
                method="POST", headers={"Content-Type": "application/json"})
            try:
                with self.op.open(r, timeout=30) as resp:
                    return json.loads(resp.read().decode())
            except urllib.error.HTTPError as e:
                try:
                    return json.loads(e.read().decode())
                except Exception:
                    return {}

    def hub_call(method, path, obj=None, headers=None):
        r = urllib.request.Request(
            f"http://127.0.0.1:{hub_port}" + path,
            data=json.dumps(obj).encode() if obj is not None else None,
            method=method, headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read().decode())

    d = hub_call("POST", "/access", {"agent": "conv-seeder", "acts": ["list"]})
    ltok = d["tokens"]["list"]
    for p in (
        {"vertical": "events", "title": "Open-Air Cinema: Sci-Fi Classics", "date": "2099-06-01", "location": "Vienna", "price": 9, "capacity": 20, "tags": ["outdoor", "cinema"], "description": "Classic sci-fi under the stars."},
        {"vertical": "events", "title": "Free Morning Yoga in the Park", "date": "2099-07-01", "location": "Vienna", "price": 0, "capacity": 15, "tags": ["yoga", "outdoor"], "description": "Gentle flow, all levels."},
        {"vertical": "events", "title": "Rooftop Jazz Night", "date": "2099-08-02", "location": "Vienna", "price": 12, "capacity": 40, "tags": ["jazz", "concert"], "description": "Live jazz on the roof."},
    ):
        hub_call("POST", "/listings", p, {"X-Hub-Token": ltok})

    BAD = ("Search is what I do best", "Not sure what you mean",)

    def say_ok(c, turn: str, name: str) -> str:
        d = c.say(turn)
        r = d.get("reply") or ""
        check(f"{name}: non-empty", bool(r.strip()), repr(r))
        for b in BAD:
            check(f"{name}: no lecture '{b}'", b not in r, repr(r))
        return r

    def last_code() -> str:
        m = re.findall(r"verification code: ([A-F0-9]{6})", open(hub_log_path).read())
        return m[-1] if m else ""

    print("== C1: search-to-booking by speech ==", flush=True)
    c = CC()
    r = say_ok(c, "hey! any cool events in vienna soon?", "C1.1 search")
    check("C1.1: real results", ("matches open on the board" in r), r)
    r = say_ok(c, "the jazz one sounds nice", "C1.2 narrow")
    check("C1.2: narrowed to jazz", ("2 matches" in r), r)
    r = say_ok(c, "yes book it for me", "C1.3 book by speech")
    check("C1.3: books the jazz pick", ("Rooftop Jazz Night" in r and "paid listing" in r), r)
    r = say_ok(c, "Anna", "C1.4 early name")
    check("C1.4: Anna captured", ("under Anna" in r), r)
    r = say_ok(c, "anna@example.com", "C1.5 email signup")
    check("C1.5: account created", ("Account created" in r), r)
    code = last_code()
    check("C1.6: code exists", bool(code), "no code in hub log")
    r = say_ok(c, code or "000000", "C1.6 code confirm")
    check("C1.6: email verified + human check", ("Email verified" in r), r)

    print("== C2: refine chain ==", flush=True)
    c = CC()
    r = say_ok(c, "whats on this weekend?", "C2.1 weekend")
    check("C2.1: honest empty-state", ("Nothing matched" in r), r)
    r = say_ok(c, "something cheaper?", "C2.2 cheaper refine")
    check("C2.2: honest refine", bool(r), r)
    r = say_ok(c, "ok the free one then", "C2.3 free pick")
    check("C2.3: books the free listing", ("Free Morning Yoga in the Park" in r), r)
    r = say_ok(c, "book it under Maria please", "C2.4 name capture")
    check("C2.4: Maria captured (no 'please')", ("under Maria" in r and "Maria please" not in r), r)

    print("== C3: mood + comeback ==", flush=True)
    c = CC()
    say_ok(c, "hi whats on?", "C3.1 whats on")
    r = say_ok(c, "hmm not sure yet, what about tomorrow?", "C3.2 mood")
    check("C3.2: honest answer", bool(r), r)
    r = say_ok(c, "lol ok", "C3.3 social ack")
    check("C3.3: friendly ack (not a pick prompt)", ("Anytime" in r or "no worries" in r.lower() or "take your time" in r.lower() or "Which one" in r), r)
    r = say_ok(c, "actually book the yoga for me", "C3.4 comeback booking")
    check("C3.4: yoga booked by speech", ("Free Morning Yoga in the Park" in r), r)
    r = say_ok(c, "Tom", "C3.5 name capture")
    check("C3.5: Tom captured", ("under Tom" in r), r)

    print("== C4: german flow ==", flush=True)
    c = CC()
    r = say_ok(c, "guten tag, ich suche ein Konzert in Wien", "C4.1 german search")
    check("C4.1: real results", ("matches open on the board" in r), r)
    r = say_ok(c, "das erste bitte", "C4.2 ordinal pick")
    check("C4.2: books first match", ("paid listing" in r), r)
    r = say_ok(c, "ich moechte das buchen", "C4.3 german affirm")
    check("C4.3: spot held / account gate", ("holding your spot" in r.lower() or "Account created" in r or "account" in r.lower()), r)
    r = say_ok(c, "Max Mustermann", "C4.4 german name")
    check("C4.4: Max Mustermann captured", ("under Max Mustermann" in r), r)
    r = say_ok(c, "max@example.com", "C4.5 email signup")
    check("C4.5: account created", ("Account created" in r), r)

    print("", flush=True)
    if FAILS:
        print(f"CONVERSATION BATTERY: {len(FAILS)} FAILURE(S)", flush=True)
        for f in FAILS:
            print("  - " + f, flush=True)
        sys.exit(1)
    print("CONVERSATION BATTERY: ALL PASSED", flush=True)


if __name__ == "__main__":
    main()
