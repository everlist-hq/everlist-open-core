"""Fuzz/property validation walls over hub HTTP field handling (deep-run #8, T2).
Closes backlog Q1: no fuzz inputs in any suite.

Stdlib-only (random + string), fixed seed 8152026, ~200 fuzz cases over an
isolated hub on :8952. Each batch = one check; global invariants (never 5xx,
honest error bodies, no secret/traceback leaks, hub stays alive) checked per
batch. Run: venv/bin/python test_fuzz_fields.py
"""
import base64
import json
import os
import random
import shutil
import socket
import string
import subprocess
import sys
import tempfile
import time
import atexit
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8952
BASE = f"http://127.0.0.1:{PORT}"
SCRATCH = "/tmp/run8/t2"
STATE = os.path.join(SCRATCH, "state.json")
LOGF = os.path.join(SCRATCH, "hub.log")
SEED = 8152026
RNG = random.Random(SEED)

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, detail)


def wait_ready(port, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def http(method, path, body_bytes=None, headers=None, timeout=15):
    """Raw HTTP: returns (status, text). status 0 = connection-level failure
    (same honesty convention as test_hardening's oversized-body probe)."""
    r = urllib.request.Request(
        BASE + path, method=method, data=body_bytes,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except (urllib.error.URLError, ConnectionError, BrokenPipeError,
            socket.timeout, OSError) as e:
        if isinstance(e, urllib.error.HTTPError):
            return e.code, ""
        return 0, f"conn-cut: {type(e).__name__}"


def req(method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    st, txt = http(method, path, data, headers)
    try:
        return st, json.loads(txt)
    except Exception:
        return st, {"_raw": txt}


def jbody(st, txt):
    try:
        return json.loads(txt)
    except Exception:
        return None


# ---------------- fuzz input generators (seeded, stdlib-only) ----------------
HOSTILE_UNICODE = [
    "\u202e",        # RTL override
    "\u202d",        # LTR override
    "\u200f", "\u200e",   # bidi marks
    "\u200b", "\u200c", "\u200d",  # zero-width chars
    "\ufeff",        # BOM
    "\u2028", "\u2029",   # line/para separators
    "\u0000", "\u0007", "\u001b[31m",  # NUL, bell, ESC sequence
    "\ud83d\ude00\u202e",  # emoji + override
    "سلام\u200bיי\u202e",   # mixed bidi scripts
]
SQLISH = [
    "' OR '1'='1",
    '"; DROP TABLE listings;--',
    "1' UNION SELECT secret--",
    '%%%;..///',
    '*?[]{}()',
    'a\'b"c\\d;e--',
    'NEAR(a b) NOT c',
    "' AND manage_code_hash IS NOT NULL --",
]


def rnd_string(n, alphabet=None):
    alphabet = alphabet or (string.ascii_letters + string.digits + " ".join([""]) + "\t!@#$%^&*()<>/\\;:'\"[]{}|~=+`)".replace("", ""))
    alphabet = string.ascii_letters + string.digits + " !@#$%^&*()<>/\\;:'\"[]{}|~=+`\t"
    return "".join(RNG.choice(alphabet) for _ in range(n))


def hostile_string(base_len=40):
    core = rnd_string(base_len)
    poison = RNG.choice(HOSTILE_UNICODE)
    pos = RNG.randrange(0, len(core) + 1)
    return core[:pos] + poison + core[pos:]


def oversize_string(kb):
    return rnd_string(kb * 1024)


# ---------------- hub lifecycle ----------------
shutil.rmtree(SCRATCH, ignore_errors=True)
os.makedirs(SCRATCH, exist_ok=True)
log_fh = open(LOGF, "w")
env = {**os.environ, "HUB_STATE_FILE": STATE}
proc = subprocess.Popen(["./venv/bin/python", os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=log_fh, stderr=subprocess.STDOUT, env=env, cwd=HERE)


def _kill():
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()


atexit.register(_kill)
assert wait_ready(PORT), "hub did not start on :8952"


# ---------------- setup: tokens + fixtures (not fuzz cases) ----------------
c, acc = req("POST", "/access", {"agent": "fuzz-t2", "acts": ["book", "list"]})
assert c == 201 and acc.get("tokens"), f"setup /access failed: {c} {acc}"
TOK_LIST = acc["tokens"]["list"]
TOK_BOOK = acc["tokens"]["book"]
H_LIST = {"X-Hub-Token": TOK_LIST}
H_BOOK = {"X-Hub-Token": TOK_BOOK}


def make_listing(title):
    st, li = req("POST", "/listings", {"vertical": "events", "title": title,
                "category": "meetup", "date": "2027-01-15", "price": 0,
                "location": "Fuzzville", "capacity": 50}, headers=H_LIST)
    assert st == 201 and li.get("id"), f"setup listing failed: {st} {li}"
    return li["id"]


LID_BOOK = make_listing("Fuzz Setup Book")
LID_RATE = make_listing("Fuzz Setup Rate")


def make_booking(lid, attendee):
    st, bk = req("POST", "/book", {"listing_id": lid, "quantity": 1,
                "human_verified": True, "attendee": attendee}, headers=H_BOOK)
    assert st in (201, 200), f"setup booking failed: {st} {bk}"
    return bk


BOOK_OK = make_booking(LID_RATE, "Rate Fuzzer A")   # invalid-rating target
RATE_OK = make_booking(LID_RATE, "Rate Fuzzer B")   # valid-rating target
BID_RATE = RATE_OK.get("id")
BID_BOOK = BOOK_OK.get("id")
# The booking-creation response legitimately carries booking_secret/cancel_token.


# ---------------- invariant helpers ----------------

def leak_scan(txt, allow_booking_secrets=False):
    """Secret/stack-trace leak scan over a raw response body."""
    low = txt.lower()
    for tok in ("manage_code_hash", "traceback"):
        if tok in low:
            return tok
    for tok in ("booking_secret", "cancel_token"):
        if tok in low and not allow_booking_secrets:
            return tok
    return None


BAD_STATUS, BAD_ERR, LEAKS = [], [], []


def fuzz_case(batch, endpoint, desc, st, txt, allow_booking_secrets=False,
              allowed=(0,), reflect=None):
    """Record one fuzz case against the global invariants.
    allowed: extra statuses considered honest for this case (conn-cut 0 always ok).
    reflect: raw request input echoed back by the endpoint (e.g. /search filters.q);
    echoed input is stripped BEFORE the leak scan (input reflection is not a leak).
    The hard walls (never 5xx, leaks) apply unconditionally."""
    if reflect:
        txt = txt.replace(reflect, "").replace(reflect.lower(), "")
    if st in (500, 502, 503):
        BAD_STATUS.append(f"[{batch}] {endpoint} {desc} -> {st}")
    tok = leak_scan(txt, allow_booking_secrets)
    if tok:
        LEAKS.append(f"[{batch}] {endpoint} {desc} leaked {tok}")
    if st >= 400 and st not in allowed and st != 0:
        body = jbody(st, txt)
        if isinstance(body, dict) and not isinstance(body.get("error"), str):
            BAD_ERR.append(f"[{batch}] {endpoint} {desc} -> {st} body without string 'error': {txt[:120]}")


def alive_check(batch):
    st, txt = http("GET", "/search?q=fuzz")
    ok = st == 200
    check(f"hub alive after {batch} (clean /search 200)", ok,
          "" if ok else f"search -> {st}")
    if st >= 500:
        BAD_STATUS.append(f"[{batch}] liveness /search -> {st}")


def invariant_checks(batch, ncases):
    check(f"fuzz: {batch} never 5xx ({ncases} cases)", not BAD_STATUS,
          "; ".join(BAD_STATUS[:5]))
    check(f"fuzz: {batch} error contract + no leaks", not BAD_ERR and not LEAKS,
          "; ".join((BAD_ERR + LEAKS)[:5]))
    alive_check(batch)
    BAD_STATUS.clear(); BAD_ERR.clear(); LEAKS.clear()


# ============ batch 1: /listings oversize + hostile unicode (30 cases) ============
print("== fuzz: listings oversize/unicode ==")
n = 0
for kb in (1, 4, 16, 50, 100):
    for field in ("title", "description", "price", "location", "category", "tags", "url"):
        val = oversize_string(kb) if field not in ("price",) else oversize_string(kb)
        body = {"vertical": "events", "title": "ok", "category": "meetup",
                "date": "2027-02-01", "price": 1, "location": "ok", "capacity": 2}
        body[field] = val
        st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
        fuzz_case("listings-oversize", "/listings", f"{field}={kb}KB", st, txt)
        n += 1
for field in ("title", "description", "location", "category", "tags", "url"):
    for _ in range(4):
        body = {"vertical": "events", "title": "ok", "category": "meetup",
                "date": "2027-02-01", "price": 1, "location": "ok", "capacity": 2}
        body[field] = hostile_string()
        st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
        fuzz_case("listings-unicode", "/listings", f"{field}=hostile-unicode", st, txt)
        n += 1
invariant_checks("listings-oversize/unicode", n)

# ============ batch 2: /listings types/prices/missing/schema/dup/nest (40) ============
print("== fuzz: listings types/prices/missing/schema ==")
n = 0
BASE_L = {"vertical": "events", "title": "ok", "category": "meetup",
          "date": "2027-02-01", "price": 1, "location": "ok", "capacity": 2}
for price in (0, -1, -10**18, 10**18, 10.5, -0.01, "1", "free", True, None, [], {}):
    body = dict(BASE_L); body["price"] = price
    st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
    fuzz_case("listings-price", "/listings", f"price={price!r}", st, txt)
    n += 1
for field in ("title", "date", "location", "price", "capacity"):
    body = dict(BASE_L); body.pop(field)
    st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
    fuzz_case("listings-missing", "/listings", f"missing {field}", st, txt)
    n += 1
for wrong in (("title", 123), ("date", 20270201), ("location", None),
              ("capacity", "two"), ("tags", "notalist"), ("vertical", 42),
              ("title", ["a"]), ("date", {})):
    body = dict(BASE_L); body[wrong[0]] = wrong[1]
    st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
    fuzz_case("listings-wrongtype", "/listings", f"{wrong[0]}={wrong[1]!r}", st, txt)
    n += 1
for cat in ("zzz-invalid", "MEETUP-X", "concert'; DROP", "\u202econcert", "", "   ", "meetup\u0000"):
    body = dict(BASE_L); body["category"] = cat
    st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
    fuzz_case("listings-category", "/listings", f"category={cat!r}", st, txt)
    n += 1
for vert in ("nope", "Events", "e\u200bv", ""):
    body = dict(BASE_L); body["vertical"] = vert
    st, txt = http("POST", "/listings", json.dumps(body).encode(), H_LIST)
    fuzz_case("listings-vertical", "/listings", f"vertical={vert!r}", st, txt)
    n += 1
# duplicate JSON keys (raw body, last-key-wins vs rejection — never 5xx)
dup = ('{"vertical":"events","title":"a","title":"b","category":"meetup",'
       '"date":"2027-02-01","price":1,"price":99999,"location":"x","capacity":2}')
st, txt = http("POST", "/listings", dup.encode(), H_LIST)
fuzz_case("listings-dupkeys", "/listings", "duplicate title+price keys", st, txt)
n += 1
# deep nesting (JSON bomb-ish, bounded)
for depth in (100, 1000):
    nested = "x"
    for _ in range(depth):
        nested = '["' + nested.replace('"', '\\"') + '"]'
    raw = ('{"vertical":"events","title":' + nested + ',"category":"meetup",'
           '"date":"2027-02-01","price":1,"location":"x","capacity":2}')
    st, txt = http("POST", "/listings", raw.encode(), H_LIST)
    fuzz_case("listings-deepnest", "/listings", f"nesting depth {depth}", st, txt)
    n += 1
# wrong top-level types
for raw in (b'[]', b'"string"', b'123', b'null', b'{'):
    st, txt = http("POST", "/listings", raw, H_LIST)
    fuzz_case("listings-badjson", "/listings", f"top-level {raw[:12]!r}", st, txt)
    n += 1
invariant_checks("listings-fields", n)

# ============ batch 3: /book fuzz (50 cases) ============
print("== fuzz: book fields ==")
n = 0
for qty in (0, -1, -10**18, 10**18, 1.5, "1", True, None, [], {}):
    body = {"listing_id": LID_BOOK, "quantity": qty, "human_verified": True,
            "attendee": "QF" + rnd_string(8)}
    st, txt = http("POST", "/book", json.dumps(body).encode(), H_BOOK)
    fuzz_case("book-qty", "/book", f"quantity={qty!r}", st, txt)
    n += 1
for att in ([oversize_string(1), oversize_string(16), oversize_string(100)]
            + [hostile_string() for _ in range(6)] + [None, 123, [], {}, ""]):
    body = {"listing_id": LID_BOOK, "quantity": 1, "human_verified": True, "attendee": att}
    st, txt = http("POST", "/book", json.dumps(body).encode(), H_BOOK)
    d = (f"len{len(att)}" if isinstance(att, str) else repr(att))
    fuzz_case("book-attendee", "/book", f"attendee {d}", st, txt)
    n += 1
for lid in ("even-999999", "", "../../etc/passwd", "even-1'; DROP--",
            None, 123, 10**18, [], {}, True, "\u202eeven-1"):
    body = {"listing_id": lid, "quantity": 1, "human_verified": True, "attendee": "QX"}
    st, txt = http("POST", "/book", json.dumps(body).encode(), H_BOOK)
    fuzz_case("book-lid", "/book", f"listing_id={lid!r}", st, txt)
    n += 1
# missing required / bad human_verified / oversized body
for body in ({"quantity": 1, "attendee": "QM"},
             {"listing_id": LID_BOOK, "attendee": "QM"},
             {"listing_id": LID_BOOK, "quantity": 1},
             {"listing_id": LID_BOOK, "quantity": 1, "human_verified": "yes", "attendee": "QM"},
             {"listing_id": LID_BOOK, "quantity": 1, "human_verified": 1, "attendee": "QM"},
             {"listing_id": LID_BOOK, "quantity": 1, "human_verified": True,
              "attendee": "QM", "junk": oversize_string(100)}):
    st, txt = http("POST", "/book", json.dumps(body).encode(), H_BOOK)
    fuzz_case("book-required", "/book", str(sorted(body.keys())), st, txt)
    n += 1
for _ in range(11):
    body = {"listing_id": LID_BOOK, "quantity": RNG.choice([1, 2, 0, -3, 2.5]),
            "human_verified": True, "attendee": hostile_string(RNG.randrange(1, 60))}
    st, txt = http("POST", "/book", json.dumps(body).encode(), H_BOOK)
    fuzz_case("book-random", "/book", "random combo", st, txt)
    n += 1
invariant_checks("book-fields", n)

# ============ batch 4: GET /search?q= fuzz (40 cases) ============
print("== fuzz: search q ==")
n = 0
for q in ["a", "a" * 199, "a" * 200, "a" * 201, "a" * 1000, "a" * 5000,
          "\u202e" * 50, "\u200b" * 250, "\ufeffquery\u202e", "\\x00term",
          "\u0000", "\u001b[31mred", "term\u2028next"] \
         + SQLISH + [rnd_string(RNG.randrange(1, 260)) for _ in range(15)]:
    st, txt = http("GET", "/search?q=" + urllib.parse.quote(q, safe=""))
    d = f"len{len(q)}" if len(q) > 30 else repr(q[:30])
    fuzz_case("search-q", "/search", f"q {d}", st, txt, reflect=q)
    n += 1
invariant_checks("search-q", n)

# ============ batch 5: /book/{id}/rate fuzz (20 cases) ============
print("== fuzz: rating ==")
n = 0
for rating in (0, 6, -1, -5, 10, 10**18, 4.5, "5", True, None, [], {}):
    st, txt = http("POST", f"/book/{BID_RATE}/rate", json.dumps({"rating": rating}).encode(), H_BOOK)
    fuzz_case("rating", f"/book/{BID_RATE}/rate", f"rating={rating!r}", st, txt)
    n += 1
# unknown / wrong-type ids with rating payloads
for bid in ("book-999999", "", None, 123, "../../etc/passwd"):
    st, txt = http("POST", f"/book/{urllib.parse.quote(str(bid), safe='')}/rate",
                   json.dumps({"rating": 5}).encode(), H_BOOK)
    fuzz_case("rating-bid", "/book/{id}/rate", f"id={bid!r}", st, txt)
    n += 1
st, txt = http("POST", f"/book/{BID_RATE}/rate", b"{not json", H_BOOK)
fuzz_case("rating-badjson", "/book/{id}/rate", "malformed JSON body", st, txt)
n += 1
st, txt = http("POST", f"/book/{BID_RATE}/rate", json.dumps({}).encode(), H_BOOK)
fuzz_case("rating-missing", "/book/{id}/rate", "missing rating field", st, txt)
n += 1
# one honest valid rating on the dedicated booking, then replay
st, txt = http("POST", f"/book/{BID_RATE}/rate", json.dumps({"rating": 5}).encode(), H_BOOK)
fuzz_case("rating-valid", f"/book/{BID_RATE}/rate", "valid rating=5", st, txt,
          allow_booking_secrets=True, allowed=(200, 201))
n += 1
st, txt = http("POST", f"/book/{BID_RATE}/rate", json.dumps({"rating": 5}).encode(), H_BOOK)
fuzz_case("rating-replay", f"/book/{BID_RATE}/rate", "second rating (once-only)", st, txt)
n += 1
invariant_checks("rating", n)

# ============ batch 6: /premium/events payment header fuzz (20 cases) ============
print("== fuzz: premium payment header ==")
n = 0
HDRS = [
    ("not base64!!", "plain garbage"),
    (base64.b64encode(b"not json at all").decode(), "base64 of text"),
    (base64.b64encode(b"{}").decode(), "empty json"),
    (base64.b64encode(b'{"x":1}').decode(), "wrong field"),
    (base64.b64encode(b'{"x402Version":"two"}').decode(), "wrong type version"),
    (base64.b64encode(b'{"x402Version":1,"scheme":"exact","network":"nowhere",'
                      b'"payload":"zz"}').decode(), "bogus network"),
    (base64.b64encode(b'[]').decode(), "json array"),
    (base64.b64encode(b'\x00\x01\x02').decode(), "binary bytes"),
    (base64.b64encode(oversize_string(100).encode()).decode(), "100KB payload"),
    ("", "empty header"),
    ("AAAA", "truncated b64"),
    ("e30=", "b64 {}"),
]
for hv, desc in HDRS:
    st, txt = http("GET", "/premium/events", None, {"X-PAYMENT": hv})
    fuzz_case("premium", "/premium/events", desc, st, txt, allowed=(400, 402))
    n += 1
for _ in range(8):
    junk = RNG.choice([rnd_string(RNG.randrange(1, 200)),
                       base64.b64encode(hostile_string().encode("utf-8", "surrogatepass")).decode(),
                       base64.b64encode(json.dumps({k: RNG.choice([None, [], {}, 1.5, -1, 10**20])
                                                    for k in RNG.sample(
                            ["x402Version", "scheme", "network", "payload", "resource"],
                            RNG.randrange(1, 5))}).encode()).decode()])
    st, txt = http("GET", "/premium/events", None, {"X-PAYMENT": junk})
    fuzz_case("premium-random", "/premium/events", "random header", st, txt,
              allowed=(400, 402))
    n += 1
st, txt = http("GET", "/premium/events")
fuzz_case("premium-none", "/premium/events", "no header (terms 402)", st, txt,
          allowed=(402,))
n += 1
invariant_checks("premium-header", n)

# ============ teardown + verdict ============
_kill()
log_fh.close()

fails = [name for name, ok in RESULTS if not ok]
print(f"\n=== fuzz: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILED:", fails)
sys.exit(1 if fails else 0)
