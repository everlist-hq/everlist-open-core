"""Escrow state-machine property fuzz (deep-run #9, backlog Q1 / F1).

Model-based fuzz of the booking/escrow machine over a REAL isolated hub:
- python dict model mirrors each booking's expected escrow state
  (WAIVED/HELD -> RELEASED/REFUNDED, or DIRECT) + listing capacity counters
- ~120 seeded random ops: keypair signup, free/paid listings (escrow +
  instant rails), valid + invalid-qty booking, owner + wrong-actor confirm,
  valid cancel + garbage-token cancel, rate once/replay/out-of-range,
  get_booking, private_details with right/wrong secret
- after EVERY op the invariant sweep runs: terminal frozenness (GET
  /bookings + GET /book/{id}), capacity vs /listings/{id}.registered,
  refund logic, exactly-once post-settle rating, per-listing money
  conservation from /ledger, liveness (/search 200) every 10 ops,
  hub process alive + state file parseable after every op

Run: ./venv/bin/python test_escrow_fuzz.py   (fixed seed -> deterministic)
"""
import atexit
import hashlib
import json
import os
import random
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request

from cryptography.hazmat.primitives import serialization as _ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

SEED = 20260921
random.seed(SEED)  # FIXED SEED - set once at top

HERE = os.path.dirname(os.path.abspath(__file__))
PORT = 8953
SCRATCH = "/tmp/run9/f1"
STATE = os.path.join(SCRATCH, "state.json")
LOGF = os.path.join(SCRATCH, "hub.log")
BASE = f"http://127.0.0.1:{PORT}"
N_OPS = 120
RESULTS = []

os.makedirs(SCRATCH, exist_ok=True)
for _f in (STATE, STATE + ".lock", LOGF):
    try:
        os.remove(_f)
    except FileNotFoundError:
        pass


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, detail)


def req(method, path, body=None, token=None):
    r = urllib.request.Request(
        BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json",
                 **({"X-Hub-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


# ---------------------------------------------------------------- boot
_env = {k: v for k, v in os.environ.items() if k != "HUB_INDEXER_URL"}  # chain gate OFF
_env.update({
    "HUB_PORT": str(PORT),
    "HUB_STATE_FILE": STATE,
    "HUB_EMAIL_MODE": "log",
    "HUB_POW_SIGNUP_BITS": "8",
    "HUB_POW_RECOVER_BITS": "8",
    "HUB_RATE_BOOKS_PER_MIN": "100000",
    "HUB_READ_LIMIT": "100000",
    "HUB_LIMIT_ACCESS": "100000",
    "HUB_LIMIT_CHALLENGE": "100000",
    "HUB_LIMIT_CREATE": "100000",
    "HUB_LIMIT_BOOK": "100000",
    "HUB_LIMIT_MANAGE": "100000",
    "HUB_LIMIT_RATE": "100000",
})
_log_fh = open(LOGF, "w")
_proc = subprocess.Popen(
    [os.path.join(HERE, "venv", "bin", "python"), "app.py"],
    cwd=HERE, stdout=_log_fh, stderr=subprocess.STDOUT,
    env=_env, start_new_session=True)


def _kill_hub():
    if _proc.poll() is None:
        try:
            os.killpg(os.getpgid(_proc.pid), signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            _proc.wait(timeout=5)
        except Exception:
            try:
                os.killpg(os.getpgid(_proc.pid), signal.SIGKILL)
            except Exception:
                pass


atexit.register(_kill_hub)

_deadline = time.time() + 25
_up = False
while time.time() < _deadline:
    try:
        if req("GET", "/search?q=warmup")[0] == 200:
            _up = True
            break
    except Exception:
        pass
    time.sleep(0.2)
if not _up:
    print("FATAL: hub did not become ready via /search")
    _kill_hub()
    sys.exit(1)
print(f"hub up on :{PORT} (seed={SEED}, state={STATE})")


def solve_pow(kind):
    _, ch = req("GET", f"/auth/challenge?kind={kind}")
    n = 0
    while True:
        d = hashlib.sha256((ch["challenge"] + str(n)).encode()).digest()
        bits = 0
        for b in d:
            if b == 0:
                bits += 8
                continue
            bits += 8 - b.bit_length()
            break
        if bits >= ch["difficulty"]:
            return {"challenge": ch["challenge"], "nonce": n}
        n += 1


def fee_c(price, qty):
    """Mirror hub hub_fee_c(): 1% default, integer minor units, floor."""
    price_c = int(round(price * 100)) * qty
    return (price_c * 100) // 10000


# ---------------------------------------------------------------- model
AGENTS = {}     # name -> {sk, pub, tokens{book,list}}
LISTINGS = {}   # lid -> {capacity, registered, price, owner, instant, terms}
BOOKINGS = {}   # bid -> {state, listing, price, qty, fee, buyer, secret,
                #         cancel_token, rated, rating_val}
OPLOG = []
BAD_QTYS = [0, -1, 101, 2.5, "3", True, None, [2]]


def _pick_listing():
    cands = [lid for lid, l in LISTINGS.items() if l["registered"] < l["capacity"]]
    return random.choice(cands) if cands else None


def _pick_booking(pred=lambda b: True):
    cands = [bid for bid, b in BOOKINGS.items() if pred(b)]
    return random.choice(cands) if cands else None


REAL_BUG = []


def op_signup():
    if len(AGENTS) >= 8:
        return op_book(False)
    name = f"fuzz-{len(AGENTS)}-{random.randint(100, 999)}"
    seed = random.randbytes(32).hex()
    sk = Ed25519PrivateKey.from_private_bytes(bytes.fromhex(seed))
    pub = sk.public_key().public_bytes(_ser.Encoding.Raw, _ser.PublicFormat.Raw).hex()
    c, a = req("POST", "/accounts/signup",
               {"agent": name, "pubkey": pub, "pow": solve_pow("signup")})
    if c != 201:
        return False, f"signup {c}: {a}"
    cst, ch = req("GET", f"/auth/challenge?kind=login&pubkey={pub}")
    if cst != 200:
        return False, f"challenge {cst}"
    sig = sk.sign(b"everlist-login:" + ch["challenge"].encode()).hex()
    c, l = req("POST", "/accounts/login", {"pubkey": pub, "agent": name, "sig": sig})
    if c != 200 or not l.get("tokens", {}).get("book"):
        return False, f"login {c}"
    AGENTS[name] = {"sk": sk, "pub": pub, "tokens": l["tokens"]}
    return True, name


def op_create_listing(free):
    if not AGENTS:
        ok, msg = op_signup()
        if not ok:
            return False, msg
    owner = random.choice(sorted(AGENTS))
    tok = AGENTS[owner]["tokens"]["list"]
    instant = (not free) and random.random() < 0.3
    price = 0.0 if free else round(random.uniform(3, 60), 2)
    cap = random.randint(1, 5)
    body = {"vertical": "events", "title": f"Fuzz Gala {random.randint(1000, 9999)}",
            "category": "meetup", "date": "2026-12-24", "price": price,
            "location": "V", "capacity": cap}
    if instant:
        body["payment_terms"] = {"rail": "instant"}
    c, r = req("POST", "/listings", body, token=tok)
    if c != 201 or not r.get("id"):
        return False, f"create {c}: {r}"
    lid = r["id"]
    _, pubv = req("GET", f"/listings/{lid}")
    LISTINGS[lid] = {"capacity": cap, "registered": 0, "price": price,
                     "owner": owner, "instant": instant,
                     "terms": pubv.get("payment_terms") or {}}
    return True, lid


def op_book(bad_qty):
    if not AGENTS:
        ok, msg = op_signup()
        if not ok:
            return False, msg
    lid = _pick_listing()
    if lid is None:
        return op_create_listing(free=random.random() < 0.5)
    buyer = random.choice(sorted(AGENTS))
    tok = AGENTS[buyer]["tokens"]["book"]
    m = LISTINGS[lid]
    if bad_qty:
        qty = random.choice(BAD_QTYS)
        body = {"listing_id": lid, "quantity": qty, "human_verified": True,
                "attendee": f"att-{random.randint(100, 999)}"}
        c, r = req("POST", "/book", body, token=tok)
        return c == 400, f"bad-qty {qty!r} -> {c} (want 400)"
    want = random.randint(1, 3)
    body = {"listing_id": lid, "quantity": want, "human_verified": True,
            "attendee": f"att-{random.randint(100, 999)}"}
    if m["instant"]:
        body["accepted_payment_terms"] = m["terms"]
    c, r = req("POST", "/book", body, token=tok)
    if m["registered"] + want > m["capacity"]:
        return c == 409, f"overbook want={want} -> {c} (want 409)"
    if c != 201:
        return False, f"book {c}: {r}"
    bid = r["id"]
    exp = "WAIVED" if m["price"] == 0 else ("DIRECT" if m["instant"] else "HELD")
    exp_fee_c = fee_c(m["price"], r.get("quantity", want))
    exp_fee = exp_fee_c / 100.0
    if r.get("escrow") != exp or abs(r.get("hub_fee", -1) - exp_fee) > 0.005:
        return False, (f"book resp mismatch escrow={r.get('escrow')}/{exp} "
                       f"fee={r.get('hub_fee')}/{exp_fee}")
    BOOKINGS[bid] = {"state": exp, "listing": lid, "price": m["price"],
                     "qty": r.get("quantity", want), "fee": exp_fee,
                     "fee_c": exp_fee_c, "buyer": buyer,
                     "secret": r["booking_secret"], "cancel_token": r["cancel_token"],
                     "tok_burned": False,
                     "rated": False, "rating_val": None}
    m["registered"] += r.get("quantity", want)
    return True, bid


def op_confirm(wrong_actor):
    bid = _pick_booking()
    if bid is None:
        return op_book(False)
    b = BOOKINGS[bid]
    owner = LISTINGS[b["listing"]]["owner"]
    if wrong_actor:
        others = [n for n in sorted(AGENTS) if n != owner]
        if not others:
            return op_book(False)
        tok = AGENTS[random.choice(others)]["tokens"]["list"]
        c, r = req("POST", f"/book/{bid}/confirm", {}, token=tok)
        return c == 403, f"wrong-actor confirm -> {c} (want 403)"
    tok = AGENTS[owner]["tokens"]["list"]
    c, r = req("POST", f"/book/{bid}/confirm", {}, token=tok)
    if b["state"] in ("WAIVED", "HELD"):
        if c != 200:
            return False, f"confirm {c}: {r}"
        b["state"] = "RELEASED"
        return True, f"{bid} -> RELEASED"
    return c == 409, f"confirm on {b['state']} -> {c} (want 409)"


def op_cancel(garbage):
    bid = _pick_booking()
    if bid is None:
        return op_book(False)
    b = BOOKINGS[bid]
    if garbage:
        others = [x for x in BOOKINGS if x != bid]
        if others and random.random() < 0.5:
            tok = BOOKINGS[random.choice(others)]["cancel_token"]  # cross-booking token
        else:
            tok = "garbage-" + random.randbytes(6).hex()
        c, r = req("POST", f"/book/{bid}/cancel", {}, token=tok)
        return c == 403, f"bad-token cancel -> {c} (want 403)"
    c, r = req("POST", f"/book/{bid}/cancel", {}, token=b["cancel_token"])
    if b["tok_burned"]:
        return c == 403, f"cancel replay (token burned) -> {c} (want 403)"
    b["tok_burned"] = True  # nonce consumed on every subject-valid attempt, even refused ones
    if b["state"] in ("WAIVED", "HELD"):
        if c != 200:
            return False, f"cancel {c}: {r}"
        b["state"] = "REFUNDED"
        LISTINGS[b["listing"]]["registered"] -= b["qty"]
        return True, f"{bid} -> REFUNDED"
    return c == 409, f"cancel on {b['state']} -> {c} (want 409)"


def op_rate(mode):
    bid = _pick_booking()
    if bid is None:
        return op_book(False)
    b = BOOKINGS[bid]
    tok = AGENTS[b["buyer"]]["tokens"]["book"]
    if mode == "range":
        val = random.choice([0, 6, "5", 3.5, True])
        c, r = req("POST", f"/book/{bid}/rate", {"rating": val}, token=tok)
        return c == 400, f"rating {val!r} -> {c} (want 400)"
    if mode == "replay":
        rated = _pick_booking(lambda x: x["rated"])
        if rated is None:
            return op_rate("once")
        rb = BOOKINGS[rated]
        c, r = req("POST", f"/book/{rated}/rate", {"rating": 3},
                   token=AGENTS[rb["buyer"]]["tokens"]["book"])
        return c == 409, f"replay rate -> {c} (want 409)"
    if b["state"] in ("HELD", "REFUNDED"):
        c, r = req("POST", f"/book/{bid}/rate", {"rating": 4}, token=tok)
        return c == 409, f"rate pre-settle {b['state']} -> {c} (want 409)"
    if b["rated"]:
        return op_rate("replay")
    if b["buyer"] == LISTINGS[b["listing"]]["owner"]:
        c, r = req("POST", f"/book/{bid}/rate", {"rating": 4}, token=tok)
        return c == 403, f"self-review rate -> {c} (want 403)"
    val = random.randint(1, 5)
    c, r = req("POST", f"/book/{bid}/rate", {"rating": val}, token=tok)
    if c != 200:
        return False, f"rate {c}: {r}"
    b["rated"] = True
    b["rating_val"] = val
    return True, f"{bid} rated {val}"


def op_get_booking():
    bid = _pick_booking()
    if bid is None:
        return op_book(False)
    b = BOOKINGS[bid]
    tok = AGENTS[b["buyer"]]["tokens"]["book"]
    c, lst = req("GET", "/bookings", token=tok)
    if c != 200:
        return False, f"GET /bookings {c}"
    mine = {x["id"]: x for x in lst.get("bookings", [])}
    if bid not in mine:
        return False, f"booking {bid} missing from buyer /bookings"
    if mine[bid].get("escrow") != b["state"]:
        return False, f"/bookings escrow {mine[bid].get('escrow')} != model {b['state']}"
    c2, poll = req("GET", f"/bookings/{bid}", token=tok)
    if c2 != 200 or poll.get("escrow") != b["state"]:
        return False, f"GET /bookings/{bid} -> {c2} escrow={poll.get('escrow')}"
    other = [n for n in sorted(AGENTS)
             if n != b["buyer"] and n != LISTINGS[b["listing"]]["owner"]]
    if other:
        c3, _ = req("GET", f"/bookings/{bid}",
                    token=AGENTS[random.choice(other)]["tokens"]["book"])
        if c3 != 404:
            return False, f"foreign buyer status poll -> {c3} (want 404, no oracle)"
    return True, f"{bid} visible+consistent"


def op_private_details(wrong):
    bid = _pick_booking()
    if bid is None:
        return op_book(False)
    b = BOOKINGS[bid]
    tok = b["secret"] if not wrong else "wrong-" + random.randbytes(8).hex()
    c, r = req("GET", f"/book/{bid}", token=tok)
    if wrong:
        return c == 403, f"wrong secret -> {c} (want 403)"
    if c != 200:
        return False, f"secret GET {c}: {r}"
    priv = r.get("private_details", {})
    if priv.get("escrow") != b["state"]:
        return False, f"private escrow {priv.get('escrow')} != model {b['state']}"
    if not wrong and "attendee" not in priv:
        return False, "real identity field missing from private_details"
    return True, f"{bid} private ok"


# ---------------------------------------------------------------- invariants
_deep_cursor = [0]


def invariants(op_no):
    # (7) hub process alive
    if _proc.poll() is not None:
        REAL_BUG.append(f"op {op_no}: hub process DIED rc={_proc.returncode}")
        check("inv-hub-alive", False, "process exited")
        return False
    # (6) liveness via /search every 10 ops
    if op_no % 10 == 0:
        c, s = req("GET", "/search?q=fuzz")
        check(f"inv-search-200@{op_no}", c == 200, f"search -> {c}")
    # (1) terminal frozenness via GET /bookings (bulk per buyer) + /book/{id}
    for name, a in AGENTS.items():
        c, lst = req("GET", "/bookings", token=a["tokens"]["book"])
        if c != 200:
            REAL_BUG.append(f"op {op_no}: GET /bookings as {name} -> {c}")
            check("inv-terminal", False, "/bookings unreachable")
            return False
        hub_states = {x["id"]: x.get("escrow") for x in lst.get("bookings", [])}
        for bid, b in BOOKINGS.items():
            if b["buyer"] != name:
                continue
            hs = hub_states.get(bid)
            if hs != b["state"]:
                REAL_BUG.append(
                    f"op {op_no}: booking {bid} hub={hs} model={b['state']} "
                    f"(listing {b['listing']})")
                check("inv-terminal", False, f"{bid} state drift")
                return False
    if BOOKINGS:
        term = [bid for bid, b in BOOKINGS.items()
                if b["state"] in ("RELEASED", "REFUNDED", "DIRECT")]
        if term:
            bid = term[_deep_cursor[0] % len(term)]
            _deep_cursor[0] += 1
            b = BOOKINGS[bid]
            c2, priv = req("GET", f"/book/{bid}", token=b["secret"])
            st = priv.get("private_details", {}).get("escrow") if c2 == 200 else None
            if c2 != 200 or st != b["state"]:
                REAL_BUG.append(
                    f"op {op_no}: terminal {bid} mutated? secret-GET -> {c2} "
                    f"escrow={st} model={b['state']}")
                check("inv-terminal-deep", False, f"{bid}")
                return False
            check("inv-terminal-deep", True, f"{bid} frozen at {b['state']}")
    # (2) capacity counters: registered == model AND <= capacity
    for lid, lm in LISTINGS.items():
        c, lv = req("GET", f"/listings/{lid}")
        if c != 200:
            REAL_BUG.append(f"op {op_no}: GET /listings/{lid} -> {c}")
            check("inv-capacity", False, f"{lid} unreadable")
            return False
        reg = lv.get("registered", 0)
        if reg != lm["registered"] or reg > lm["capacity"]:
            REAL_BUG.append(
                f"op {op_no}: listing {lid} registered={reg} "
                f"model={lm['registered']} capacity={lm['capacity']}")
            check("inv-capacity", False, f"{lid} reg={reg} cap={lm['capacity']}")
            return False
    check("inv-capacity", True, f"{len(LISTINGS)} listings ok")
    # (5) money conservation per listing from /ledger (integer cents)
    c, led = req("GET", "/ledger")
    if c != 200:
        REAL_BUG.append(f"op {op_no}: GET /ledger -> {c}")
        check("inv-money", False, "ledger unreachable")
        return False
    entries = {t["booking"]: t for t in led.get("ledger", []) if t.get("booking")}
    for lid, lm in LISTINGS.items():
        exp = sum(b["fee_c"] for b in BOOKINGS.values()
                  if b["listing"] == lid and b["state"] == "RELEASED" and b["price"] > 0)
        got = sum(int(round(entries[bid]["hub_fee"] * 100))
                  for bid, b in BOOKINGS.items()
                  if b["listing"] == lid and b["state"] == "RELEASED" and b["price"] > 0
                  and bid in entries)
        if exp != got:
            REAL_BUG.append(
                f"op {op_no}: listing {lid} hub_fees={got}c != 1% of released "
                f"paid prices={exp}c")
            check("inv-money", False, f"{lid} {got}c vs {exp}c")
            return False
    # every booking has exactly one ledger entry whose escrow mirrors the model
    for bid, b in BOOKINGS.items():
        t = entries.get(bid)
        if t is None or t.get("escrow") != b["state"]:
            REAL_BUG.append(
                f"op {op_no}: ledger entry for {bid} missing/mismatched "
                f"({t and t.get('escrow')} vs {b['state']})")
            check("inv-money", False, f"ledger drift on {bid}")
            return False
        if int(round(t.get("hub_fee", -1) * 100)) != b["fee_c"]:
            REAL_BUG.append(
                f"op {op_no}: ledger fee for {bid} = {t.get('hub_fee')} "
                f"!= model {b['fee_c'] / 100.0}")
            check("inv-money", False, f"fee drift on {bid}")
            return False
    check("inv-money", True, f"{len(BOOKINGS)} bookings, fees consistent")
    return True


# ---------------------------------------------------------------- main loop
OP_POOL = [
    ("book", lambda: op_book(False), 0.18),
    ("book-badqty", lambda: op_book(True), 0.07),
    ("confirm", lambda: op_confirm(False), 0.13),
    ("confirm-wrong", lambda: op_confirm(True), 0.06),
    ("cancel", lambda: op_cancel(False), 0.10),
    ("cancel-badtok", lambda: op_cancel(True), 0.06),
    ("rate", lambda: op_rate("once"), 0.10),
    ("rate-replay", lambda: op_rate("replay"), 0.05),
    ("rate-range", lambda: op_rate("range"), 0.05),
    ("get-booking", op_get_booking, 0.08),
    ("private-details", lambda: op_private_details(False), 0.04),
    ("private-wrongsec", lambda: op_private_details(True), 0.04),
    ("signup", op_signup, 0.04),
]


def draw(i):
    if len(AGENTS) < 4:
        return ("signup", op_signup)
    if len(LISTINGS) < 4:
        return ("create-free" if len(LISTINGS) % 2 == 0 else "create-paid",
                lambda: op_create_listing(len(LISTINGS) % 2 == 0))
    r = random.random() * sum(w for _, _, w in OP_POOL)
    acc = 0.0
    for name, fn, w in OP_POOL:
        acc += w
        if r <= acc:
            return (name, fn)
    return ("book", lambda: op_book(False))


for i in range(1, N_OPS + 1):
    name, fn = draw(i)
    try:
        ok, detail = fn()
    except Exception as e:  # harness crash on an op is a failed check, not silence
        ok, detail = False, f"harness exc: {e!r}"
    check(f"op{i:03d}-{name}", ok, str(detail)[:140])
    OPLOG.append((i, name, ok))
    if not invariants(i):
        break
    if not ok:
        # protocol mismatch -> likely real bug; stop fuzzing, report sequence
        break

# final: kill hub, then state file must still parse (never corrupted)
_kill_hub()
try:
    with open(STATE) as f:
        json.load(f)
    check("state-file-intact", True)
except Exception as e:
    check("state-file-intact", False, repr(e))

fails = [n for n, okr in RESULTS if not okr]
print(f"\n=== escrow-fuzz: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILED:", fails[:25])
    print("OP SEQUENCE:", [(i, n) for i, n, okr in OPLOG if not okr][:5],
          "... last ops:", [(i, n) for i, n, _ in OPLOG[-8:]])
if REAL_BUG:
    print("REAL BUG FOUND:")
    for x in REAL_BUG[:10]:
        print(" -", x)
sys.exit(1 if (fails or REAL_BUG) else 0)
