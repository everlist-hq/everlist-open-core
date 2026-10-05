"""FIRST-TOUCH battery (owner law 2026-10-03): "its always the first input that
breaks it". Every case below replays how a REAL human opens a chat - EN/DE,
questions, greetings, typos, caps, vague topics, booking-first, email-first,
capability questions - each in a FRESH session against an isolated hub, each
asserting a USEFUL outcome. A search-shaped first input must SEARCH (results
or the honest empty-state), never lecture; capability questions must reach the
catalog; signup/email shapes must create the account. This suite exists
because exact-string journey tests never swept the space of first messages."""
import sys, os, time, socket, threading, tempfile, atexit, subprocess
import json, re, urllib.request, urllib.error, http.cookiejar
HERE = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, HERE)
import test_x402_settle as X4  # StubFacil reuse

PASS, FAIL = [], []

def check(name, cond, detail=""):
    (PASS if cond else FAIL).append((name, detail))
    print(("PASS " if cond else "FAIL ") + name + (f" -- {detail}" if detail and not cond else ""),
          flush=True)

def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p

LECTURE = "Search is what I do best"

# (input, expectation) - search = results/empty-state; signup = account created;
# capability = catalog answer (catalog_*) ; social = any non-empty reply
CORPUS = [
    ("Can you find me outdoor events in vienna?", "search"),
    ("Could you show me jazz concerts tonight", "search"),
    ("I'm looking for free yoga", "search"),
    ("find me a concert", "search"),
    ("Show me what's on this weekend", "search"),
    ("Do you have any food events?", "search"),
    ("search for outdoor cinema", "search"),
    ("any events in vienna?", "search"),
    ("what events are on this weekend?", "search"),
    ("what's on in vienna?", "search"),
    ("anything happening tonight?", "search"),
    ("whats on?", "search"),
    ("events outdoors vienna", "search"),
    ("EVENTS OUTDOORS VIENNA", "search"),
    ("events in vienna?", "search"),
    ("yoga?", "search"),
    ("concerts please", "search"),
    ("hello, can you help me find a concert in vienna?", "search"),
    ("please help me find outdoor events in vienna", "search"),
    ("hi whats on in vienna this weekend", "search"),
    ("finde outdoor events in wien", "search"),
    ("ich suche kostenlose yoga", "search"),
    ("zeig mir veranstaltungen in wien", "search"),
    ("was ist los dieses wochenende?", "search"),
    ("veranstaltungen in wien", "search"),
    ("i want to book something outdoors in vienna", "search"),
    ('Please book "Free Morning Yoga in the Park" for me', "booking"),
    ("book the yoga class", "search"),
    ("I want to book the cinema", "search"),
    ("newuser9@example.com", "signup"),
    ("signup", "signup"),
    ("hello", "social"),
    ("hey", "social"),
    ("what can you do?", "catalog:overview"),
    ("help", "social"),
    ("can i bring a dog?", "catalog:dog"),
    ("how do transfers work?", "catalog:transfer"),
    ("thanks", "social"),
]

def main():
    tmp = tempfile.mkdtemp(prefix="firsttouch-")
    hub_log_path = os.path.join(tmp, "hub.log")
    hub_port, wc_port = free_port(), free_port()
    stub = X4.StubFacil()
    env = dict(os.environ, HUB_PAY_MODE="testnet", HUB_SETTLE_MODE="auto",
               HUB_STATE_FILE=os.path.join(tmp, "state.json"),
               HUB_FACILITATOR_URL=stub.base("ok"),
               HUB_EMAIL_MODE="log", HUB_ADMIN_KEY="ft-admin",
               # 2026-10-04 (ship3 flake): conversational shapes ('anything
               # happening tonight?') reach the LLM-first brain in the spawned
               # webchat; a slow LLM call blows the 30s client timeout. This
               # battery asserts deterministic routing outcomes only (same
               # precedent as test_chat_help's pin) - disable the brain here.
               EVERLIST_BRAIN_DISABLED="1", EVERLIST_LLM_FIRST="0")
    hub_log = open(hub_log_path, "a")
    hub = subprocess.Popen([sys.executable, "app.py", str(hub_port)],
                           cwd=HERE, env=env, stdout=hub_log,
                           stderr=subprocess.STDOUT)
    atexit.register(lambda: hub.terminate())
    atexit.register(lambda: hub_log.close())
    end = time.time() + 20
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", hub_port), timeout=0.5):
                break
        except OSError:
            time.sleep(0.2)
    else:
        print("FATAL: hub not ready")
        return 1

    import webchat
    webchat.PORT = wc_port
    webchat.HUB_URL = f"http://127.0.0.1:{hub_port}"
    # 2026-10-05 (chat-continuity A/B): the deterministic qualifier search
    # path answers FASTER, so 38 first-touch POSTs at 0.2s pacing trip the
    # production G4 flood bucket (ip burst 30) on the tail inputs --
    # pre-change baseline ran 429-free, post-change 8x 429, same machine.
    # This battery asserts ROUTING outcomes (same precedent as the brain pin
    # above); flood limits have their own suite (test_write_limits). The
    # knobs are env-tunable 'for load tests / CI' (webchat.py header).
    webchat.RL_IP_BURST = 200
    webchat.RL_IP_PER_MIN = 200
    webchat.RL_S_BURST = 50
    webchat.RL_S_PER_MIN = 200
    srv = webchat.ThreadingHTTPServer(("127.0.0.1", wc_port), webchat.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    atexit.register(srv.shutdown)
    base = f"http://127.0.0.1:{wc_port}"

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

    def hub_call(method, path, obj=None, headers=None):
        r = urllib.request.Request(f"http://127.0.0.1:{hub_port}" + path,
            data=json.dumps(obj).encode() if obj is not None else None,
            method=method,
            headers={"Content-Type": "application/json", **(headers or {})})
        with urllib.request.urlopen(r, timeout=15) as resp:
            return json.loads(resp.read().decode())

    d = hub_call("POST", "/access", {"agent": "firsttouch-seeder", "acts": ["list"]})
    ltok = d["tokens"]["list"]
    for p in (
        {"vertical": "events", "title": "Open-Air Cinema: Sci-Fi Classics",
         "date": "2099-06-01", "location": "Vienna", "price": 9, "capacity": 20,
         "tags": ["outdoor", "cinema"], "description": "Classic sci-fi under the stars."},
        {"vertical": "events", "title": "Free Morning Yoga in the Park",
         "date": "2099-07-01", "location": "Vienna", "price": 0, "capacity": 15,
         "tags": ["yoga", "outdoor"], "description": "Gentle flow, all levels."},
        {"vertical": "events", "title": "Rooftop Jazz Night",
         "date": "2099-08-02", "location": "Vienna", "price": 12, "capacity": 40,
         "tags": ["jazz", "concert"], "description": "Live jazz on the roof."},
    ):
        hub_call("POST", "/listings", p, {"X-Hub-Token": ltok})

    CATALOG_MARKS = {
        "overview": "find things to book",
        "dog": "house rule",
        "transfer": "Transfers work right in chat",
    }
    for text, expect in CORPUS:
        c = C()  # FRESH session: every case is a TRUE first touch
        d = c.say(text)
        r = d.get("reply") or ""
        n = len(d.get("results") or [])
        low = r.lower()
        tag = f"first-touch [{expect}] {text[:44]!r}"
        if expect == "search":
            ok = (n > 0 or re.search(r"no (matched|matches|results|listings)|board|match", low)) \
                 and "search is what i do best" not in low
            check(tag, ok, f"results={n} reply={r[:80]!r}")
        elif expect == "signup":
            ok = "account created" in low and "acct-" in low
            check(tag, ok, r[:80])
        elif expect == "booking":
            ok = bool(re.search(r"book it for you right here|is free|paid listing|hold", low)) \
                 and "search is what i do best" not in low
            check(tag, ok, r[:80])
        elif expect.startswith("catalog:"):
            mark = CATALOG_MARKS[expect.split(":")[1]]
            ok = mark.lower() in low and "search is what i do best" not in low
            check(tag, ok, r[:80])
        else:  # social
            ok = bool(r.strip()) and "search is what i do best" not in low
            check(tag, ok, r[:80])

    print("=" * 60)
    print(f"first-touch battery: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        for f in FAIL:
            print(f"  - {f}")
        return 1
    print("FIRSTTOUCH_PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
