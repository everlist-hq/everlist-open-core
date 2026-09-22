"""Unit-level property tests for hublib signed tokens + x402 pure decode edges
(deep-run #8, task T3).

PURE UNIT SUITE: no hub boot, no network, no ports, no randomness.
Run: /opt/venv/bin/python test_hublib.py   (same runtime as the make-test gate)

Scope:
  (a) mint/verify roundtrip over a grid of subs x acts x ttls
  (b) single-use nonce burn (in-process registry) + no-burn on failed authz
  (c) one-byte tamper (flip/insert/delete) at 10 positions -> always refused
  (d) cross-domain (wrong action) + wrong key -> refused
  (e) expiry (ttl=1 after sleep 1.2), ttl huge / negative / garbage types
  (f) malformed tokens (empty, no-dot, garbage b64, extra segments, 1MB, wrong types)
  (g) x402verify.verify_payment pure decode edges + payment_fingerprint properties
      + SettlementRegistry idempotency via stub client (no network)

Known honest-behavior findings asserted as current behavior (NOT fixed here):
  F-T3-1: verify_payment leaks uncaught AttributeError when the decoded
          X-PAYMENT JSON is not a dict (list/int/null/bool/string) or the inner
          'payload' is a non-dict. Documented contract is (None, reason).
  F-T3-2: x402facilitate.payment_fingerprint (from|to|value|nonce) and
          x402verify.payment_fingerprint (nonce-only) disagree for the same
          payment. app.py uses the facilitate fp for BOTH the settlement
          registry and the ledger event, but the /premium/events response
          (premium_meta) reports the verify fp - the payer-visible fingerprint
          cannot be looked up in the ledger (display/audit mismatch).
"""
import base64
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import hublib
import x402facilitate
import x402verify
from eth_account import Account

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, detail)


def refused(key, tok, act, **kw):
    """verify_token wrapper: returns True iff verify refused WITHOUT raising.
    verify_token's contract is (None, reason) for every failure, never an
    exception; this wrapper also catches, so a leak fails the check, not the suite."""
    try:
        p, err = hublib.verify_token(key, tok, act, **kw)
    except Exception as ex:  # pragma: no cover - would be a real contract break
        print("   UNCAUGHT hublib exception:", type(ex).__name__, str(ex)[:80])
        return False
    return p is None and isinstance(err, str) and err != ""


# ================= section 1: roundtrip grid (a) =================
KEY = "t3-unit-key"
KEY2 = "t3-other-key"
SUBS = ["agent-alpha", "acct-12345", "agent-\u00fcn\u00efcode-\u03a9", "a" * 200,
        "agent.with.dots_and-underscore"]
ACTS = ["book", "list", "confirm", "cancel", "manage"]
TTLS = [1, 60, 3600, 86400]

print("== (a) mint/verify roundtrip grid ==")
n = 0
for sub in SUBS:
    for act in ACTS:
        for ttl in TTLS:
            n += 1
            tok = hublib.mint_token(KEY, act, sub, ttl)
            p, err = hublib.verify_token(KEY, tok, act)
            ok = (err is None and isinstance(p, dict)
                  and p.get("sub") == sub and p.get("act") == act and p.get("v") == 1)
            check(f"roundtrip[{n}] act={act} ttl={ttl} sub={sub[:14]!r}", ok,
                  "" if ok else f"err={err}")

p, err = hublib.verify_token(KEY, hublib.mint_token(KEY, "book", "struct-probe", 3600), "book")
now = time.time()
check("payload exp ~= now+ttl", p is not None and abs(p["exp"] - (now + 3600)) < 5)
check("payload nonce is 16 hex chars", p is not None and isinstance(p.get("nonce"), str)
      and len(p["nonce"]) == 16 and all(c in "0123456789abcdef" for c in p["nonce"]))

for act in ACTS:
    sub = f"subj-{act}"
    tok = hublib.mint_token(KEY, act, sub, 3600)
    p2, err2 = hublib.verify_token(KEY, tok, act, subject=sub)
    check(f"subject= param matches for act={act}", err2 is None and p2 is not None
          and p2.get("sub") == sub, "" if err2 is None else f"err={err2}")

# no-burn-on-failed-authz: subject mismatch must NOT consume the nonce
sub = "burn-order-probe"
tok = hublib.mint_token(KEY, "book", sub, 3600)
pb, errb = hublib.verify_token(KEY, tok, "book", subject="wrong-sub")
check("authz-failure refused (wrong subject)", pb is None and "subject" in (errb or ""), f"err={errb}")
pb2, errb2 = hublib.verify_token(KEY, tok, "book", subject=sub)
check("nonce NOT burned by failed authz (doc: checked before consumption)",
      errb2 is None and pb2 is not None, "" if errb2 is None else f"err={errb2}")
pb3, errb3 = hublib.verify_token(KEY, tok, "book")
check("nonce burned by the SUCCESSFUL verify (replay refused)",
      pb3 is None and "replay" in (errb3 or ""), f"err={errb3}")

# ================= section 2: single_use (b) =================
print("== (b) single-use burn (in-process registry) ==")
tok = hublib.mint_token(KEY, "list", "single-use", 3600)
p1, e1 = hublib.verify_token(KEY, tok, "list")
check("first verify ok", e1 is None and p1 is not None)
p2, e2 = hublib.verify_token(KEY, tok, "list")
check("second verify refused: replayed nonce", p2 is None and "replay" in (e2 or ""), f"err={e2}")
tok_fresh = hublib.mint_token(KEY, "list", "single-use", 3600)
p3, e3 = hublib.verify_token(KEY, tok_fresh, "list")
check("fresh nonce still verifies after a burn (per-nonce registry)",
      e3 is None and p3 is not None)

tok3 = hublib.mint_token(KEY, "confirm", "no-burn-mode", 3600)
pa, ea = hublib.verify_token(KEY, tok3, "confirm", single_use=False)
pb4, eb4 = hublib.verify_token(KEY, tok3, "confirm", single_use=False)
check("single_use=False: first verify ok", ea is None and pa is not None)
check("single_use=False: repeat verify ok (no burn)", eb4 is None and pb4 is not None)

# ================= section 3: tamper property (c) =================
print("== (c) one-byte tamper at 10 positions x flip/insert/delete ==")
tamper_tok = hublib.mint_token(KEY, "book", "tamper-probe", 3600)
L = len(tamper_tok)
pos_idx = [round(i * (L - 1) / 9) for i in range(10)]  # spans body AND signature

def mutations(s, i):
    orig = s[i]
    flipped = ("B" if orig != "B" else "C")
    return {"flip": s[:i] + flipped + s[i + 1:],
            "insert": s[:i] + "X" + s[i:],
            "delete": s[:i] + s[i + 1:]}

count = 0
for i in pos_idx:
    for kind, mut in mutations(tamper_tok, i).items():
        count += 1
        check(f"tamper[{count}] pos={i}/{L} {kind} refused",
              mut != tamper_tok and refused(KEY, mut, "book"))

# ================= section 4: cross-domain + wrong key (d) =================
print("== (d) cross-domain / cross-key refusal ==")
tok_book = hublib.mint_token(KEY, "book", "xdom-probe", 3600)
pk, ek = hublib.verify_token(KEY, tok_book, "book")
check("control: correct act+key verifies", ek is None and pk is not None)
pk, ek = hublib.verify_token(KEY, tok_book, "list")
check("token for 'book' refused when verified as 'list'",
      pk is None and "wrong action" in (ek or ""), f"err={ek}")
pk, ek = hublib.verify_token(KEY2, tok_book, "book")
check("wrong key refused (bad signature)", pk is None and "signature" in (ek or ""), f"err={ek}")
tok_list2 = hublib.mint_token(KEY2, "list", "xdom-probe", 3600)
pk, ek = hublib.verify_token(KEY, tok_list2, "list")
check("wrong key refused (other direction)", pk is None and "signature" in (ek or ""), f"err={ek}")

# ================= section 5: expiry + ttl extremes (e) =================
print("== (e) expiry and ttl extremes ==")
tok1 = hublib.mint_token(KEY, "list", "expiry-probe", ttl=1)
time.sleep(1.2)
pk, ek = hublib.verify_token(KEY, tok1, "list")
check("ttl=1 refused after sleep(1.2): token expired",
      pk is None and "expired" in (ek or ""), f"err={ek}")

tok_big = hublib.mint_token(KEY, "list", "huge-ttl", ttl=10 ** 9)
pk, ek = hublib.verify_token(KEY, tok_big, "list")
check("ttl=10**9 verifies without crash", ek is None and pk is not None)

tok_past = hublib.mint_token(KEY, "list", "past-ttl", ttl=-10)
pk, ek = hublib.verify_token(KEY, tok_past, "list")
check("ttl=-10 (already past) refused without crash",
      pk is None and "expired" in (ek or ""), f"err={ek}")

# signed-but-garbage exp types (extra overrides exp BEFORE signing, so the
# signature is valid and the type bomb is reached honestly)
tok_se = hublib.mint_token(KEY, "list", "exp-str", ttl=3600, extra={"exp": "abc"})
check("signed exp='abc' refused without crash (malformed token)", refused(KEY, tok_se, "list"))
tok_sn = hublib.mint_token(KEY, "list", "exp-none", ttl=3600, extra={"exp": None})
check("signed exp=None refused without crash (malformed token)", refused(KEY, tok_sn, "list"))

tok_x = hublib.mint_token(KEY, "book", "extra-probe", 3600, extra={"gen": 7})
px, ex = hublib.verify_token(KEY, tok_x, "book")
check("extra payload field roundtrips (B1 gen)", ex is None and px is not None and px.get("gen") == 7)

# ================= section 6: malformed tokens (f) =================
print("== (f) malformed tokens -> refused, never uncaught ==")

def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

SIG64 = "ab" * 32
mal_cases = [
    ("empty string", ""),
    ("no dot", "not-a-token"),
    ("dot only", "."),
    ("missing signature", "abc."),
    ("missing body", "." + SIG64),
    ("extra segment", "a." + SIG64 + ".c"),
    ("garbage body b64", b64u(b"garbage") + "." + SIG64),
    ("empty json object body", b64u(b"{}") + "." + SIG64),
    ("invalid b64 chars no dot", "!!!"),
    ("invalid b64 chars with sig", "!!!." + SIG64),
    ("1MB token string", "A" * 1048576 + "." + "0" * 64),
    ("None token", None),
    ("int token", 123),
    ("valid v=2 forgery (unsigned)", b64u(json.dumps({"v": 2, "act": "book",
                                                      "sub": "x", "exp": 9999999999,
                                                      "nonce": "ff"}).encode()) + "." + SIG64),
]
for name, bad in mal_cases:
    check(f"malformed refused: {name}", refused(KEY, bad, "book"))

pk, ek = hublib.verify_token(KEY, "  " + hublib.mint_token(KEY, "list", "pad", 3600) + "\n", "list")
check("whitespace-padded valid token verifies (strip is current behavior)",
      ek is None and pk is not None, "" if ek is None else f"err={ek}")

tok_ek = hublib.mint_token("", "list", "empty-key", 3600)
pk, ek = hublib.verify_token("", tok_ek, "list")
check("empty-key mint/verify roundtrip (current HMAC behavior)",
      ek is None and pk is not None, "" if ek is None else f"err={ek}")

# ================= section 7: x402 pure decode edges (g) =================
print("== (g) x402verify.verify_payment pure decode edges ==")

def b64j(o) -> str:
    if isinstance(o, bytes):
        return base64.b64encode(o).decode()
    if isinstance(o, str):
        return base64.b64encode(o.encode()).decode()
    return base64.b64encode(json.dumps(o).encode()).decode()

PAY_TO = "0x" + "11" * 20
NET_KW = dict(network="base-sepolia", pay_to=PAY_TO, max_amount_units=1000)


def vp(hdr, **over):
    """verify_payment wrapper -> ('OK', info) | ('ERR', reason) | ('RAISED', ExcType).
    Catches so a contract leak fails the check instead of the suite."""
    kw = dict(NET_KW)
    kw.update(over)
    try:
        info, err = x402verify.verify_payment(hdr, **kw)
        return ("OK", info) if err is None else ("ERR", err)
    except Exception as ex:
        return ("RAISED", type(ex).__name__)


SIGNER = Account.from_key("0x" + "11" * 32)
_nonce_counter = [0]


def signed_header(**over):
    """Deterministic locally-signed X-PAYMENT header (fixed key, counter nonce)."""
    _nonce_counter[0] += 1
    now = int(time.time())
    auth = {"from": SIGNER.address, "to": PAY_TO, "value": 2000,
            "validAfter": now - 10, "validBefore": now + 600,
            "nonce": "0x" + format(_nonce_counter[0], "064x")}
    auth.update(over)
    typed = x402verify.encode_typed_data(
        domain_data=x402verify.USDC_DOMAINS["base-sepolia"],
        message_types=x402verify.TRANSFER_TYPES, message_data=auth)
    sig = SIGNER.sign_message(typed)["signature"].hex()
    if not sig.startswith("0x"):
        sig = "0x" + sig
    return b64j({"x402Version": 1, "scheme": "exact", "network": "base-sepolia",
                 "payload": {"authorization": auth, "signature": sig}}), auth


def err_is(kind, res, prefix):
    return res[0] == kind and (res[1].startswith(prefix) if kind == "ERR" else True)


dec_err = [
    ("not base64", "not base64!!!"),
    ("base64 of bad json", b64j("not json{")),
    ("empty header", ""),
    ("base64 of empty bytes", b64j(b"")),
    ("x402Version=2", b64j({"x402Version": 2, "scheme": "exact",
                            "network": "base-sepolia"})),
    ("unsupported scheme", b64j({"x402Version": 1, "scheme": "x",
                                 "network": "base-sepolia"})),
    ("wrong network", b64j({"x402Version": 1, "scheme": "exact", "network": "base"})),
    ("missing inner payload", b64j({"x402Version": 1, "scheme": "exact",
                                    "network": "base-sepolia"})),
    ("missing signature", b64j({"x402Version": 1, "scheme": "exact",
                                "network": "base-sepolia",
                                "payload": {"authorization": {}}})),
    ("None header", None),
]
for name, hdr in dec_err:
    res = vp(hdr)
    check(f"x402 decode error: {name}", err_is("ERR", res, ""), f"-> {res[0]}: {str(res[1])[:60]}")

auth_min = {"to": PAY_TO, "value": 2000, "validAfter": 0,
            "validBefore": 99999999999, "nonce": "0x" + "ab" * 32}
auth_err = [
    ("authorization missing 'from'", b64j({"x402Version": 1, "scheme": "exact",
        "network": "base-sepolia", "payload": {"authorization": auth_min,
                                                "signature": "0x" + "00" * 65}}), "malformed authorization"),
    ("authorization value is dict", b64j({"x402Version": 1, "scheme": "exact",
        "network": "base-sepolia", "payload": {"authorization": {**auth_min,
            "from": SIGNER.address, "value": {}}, "signature": "0x" + "00" * 65}}), "malformed authorization"),
    ("authorization is a string", b64j({"x402Version": 1, "scheme": "exact",
        "network": "base-sepolia", "payload": {"authorization": "oops",
                                                "signature": "0x" + "00" * 65}}), "malformed authorization"),
]
for name, hdr, prefix in auth_err:
    res = vp(hdr)
    check(f"x402 decode error: {name}", err_is("ERR", res, prefix),
          f"-> {res[0]}: {str(res[1])[:60]}")

# F-T3-1 (FIXED, run8): non-dict decoded JSON now honors the documented
# (None, reason) contract — guarded honestly instead of leaking AttributeError.
non_dict = [
    ("top-level json array", b64j([1, 2]), "malformed payment payload: expected JSON object"),
    ("top-level json int", b64j(123), "malformed payment payload: expected JSON object"),
    ("top-level json null", b64j(None), "malformed payment payload: expected JSON object"),
    ("top-level json bool", b64j(True), "malformed payment payload: expected JSON object"),
    ("top-level json string", b64j('"hello"'), "malformed payment payload: expected JSON object"),
    ("inner payload is string", b64j({"x402Version": 1, "scheme": "exact",
                                      "network": "base-sepolia", "payload": "oops"}),
     "malformed payment payload: 'payload' must be an object"),
]
for name, hdr, reason in non_dict:
    res = vp(hdr)
    check(f"x402 F-T3-1 (FIXED): {name} -> honest (None, reason)",
          res[0] == "ERR" and res[1] == reason, f"-> {res}")

print("-- x402 locally-signed happy path + business refusals --")
hdr_ok, auth_ok = signed_header()
res = vp(hdr_ok)
check("x402 happy path verifies", res[0] == "OK", f"-> {str(res[1])[:80]}")
info = res[1] if res[0] == "OK" else {}
check("x402 info fields (from lowered, value, nonce, network)",
      info.get("from") == SIGNER.address.lower() and info.get("value") == 2000
      and info.get("nonce") == auth_ok["nonce"] and info.get("network") == "base-sepolia")
res = vp(hdr_ok)
check("x402 replay of same header refused (nonce burned)",
      err_is("ERR", res, "replayed payment"), f"-> {str(res[1])[:60]}")

hdr_wt, _ = signed_header(to="0x" + "22" * 20)
check("x402 wrong recipient refused", err_is("ERR", vp(hdr_wt), "wrong recipient"),
      f"-> {str(vp(hdr_wt)[1])[:60]}")

hdr_lv, _ = signed_header(value=5)
check("x402 insufficient amount refused", err_is("ERR", vp(hdr_lv), "insufficient payment amount"),
      f"-> {str(vp(hdr_lv)[1])[:60]}")

hdr_ex, _ = signed_header(validBefore=int(time.time()) - 5000)
check("x402 expired window refused",
      err_is("ERR", vp(hdr_ex), "authorization outside validity window"),
      f"-> {str(vp(hdr_ex)[1])[:60]}")

hdr_nv, _ = signed_header(validAfter=int(time.time()) + 100000)
check("x402 not-yet-valid window refused",
      err_is("ERR", vp(hdr_nv), "authorization outside validity window"),
      f"-> {str(vp(hdr_nv)[1])[:60]}")

_hdr_bs, auth_bs = signed_header()  # fresh nonce: nonce check precedes crypto in verify_payment
bad_sig_hdr = b64j({"x402Version": 1, "scheme": "exact", "network": "base-sepolia",
                    "payload": {"authorization": auth_bs, "signature": "0x" + "00" * 65}})
check("x402 garbage 65-byte signature refused",
      err_is("ERR", vp(bad_sig_hdr), "signature verification failed"),
      f"-> {str(vp(bad_sig_hdr)[1])[:60]}")

print("-- x402 payment_fingerprint properties (pure) --")
auth_fp = {"from": SIGNER.address, "to": PAY_TO, "value": 2000, "nonce": "0x" + "cd" * 32}
fp_a = x402facilitate.payment_fingerprint(auth_fp)
fp_b = x402facilitate.payment_fingerprint(dict(auth_fp))
check("facilitate fingerprint deterministic", fp_a == fp_b and len(fp_a) == 16)
fp_cs = x402facilitate.payment_fingerprint({**auth_fp,
    "from": SIGNER.address.upper().replace("0X", "0x")})
check("facilitate fingerprint case-insensitive (EIP-55 safe)", fp_cs == fp_a)
fp_n = x402facilitate.payment_fingerprint({**auth_fp, "nonce": "0x" + "ef" * 32})
check("facilitate fingerprint nonce-sensitive", fp_n != fp_a)

fp_v1 = x402verify.payment_fingerprint(auth_fp)
fp_v2 = x402verify.payment_fingerprint(dict(auth_fp))
check("verify fingerprint deterministic", fp_v1 == fp_v2 and len(fp_v1) == 16)
check("F-T3-2 (FIXED): facilitate vs verify fingerprints AGREE for the "
      "same payment (single canonical composition)", fp_a == fp_v1,
      f"fac={fp_a} ver={fp_v1}")

print("-- x402 SettlementRegistry idempotency (stub client, no network) --")


class StubFacil:
    def __init__(self, status, resp):
        self.status, self.resp, self.calls = status, resp, 0

    def _call(self, path, body):
        self.calls += 1
        return self.status, self.resp


reg = x402facilitate.SettlementRegistry()
stub = StubFacil(200, {"success": True, "transaction": "0xdeadbeef",
                       "network": "base-sepolia", "payer": SIGNER.address.lower()})
r1 = reg.settle(fp_a, {"x": 1}, {"scheme": "exact"}, stub)
r2 = reg.settle(fp_a, {"x": 1}, {"scheme": "exact"}, stub)
check("settle settles once with tx proof",
      r1["status"] == "settled" and r1["tx"] == "0xdeadbeef")
check("duplicate settle returns recorded result, never re-calls facilitator",
      r2.get("duplicate") is True and r2["status"] == "settled" and stub.calls == 1)

stub0 = StubFacil(0, {"error": "timeout"})
r3 = reg.settle("fp-timeout-01", {}, {}, stub0)
check("timeout/0 -> status unknown (never settled without tx)", r3["status"] == "unknown")
stub4 = StubFacil(400, {"error": "invalid sig"})
r4 = reg.settle("fp-4xx-000001", {}, {}, stub4)
check("definitive 4xx -> status failed with error", r4["status"] == "failed"
      and r4.get("error") == "invalid sig")
stub5 = StubFacil(500, {})
r5 = reg.settle("fp-5xx-000001", {}, {}, stub5)
check("5xx -> status unknown (may have settled)", r5["status"] == "unknown")

# F-T3-2 (SYNTHETIC sensitivity property): reconcile() still flags a real
# mismatch. Since the F-T3-2 fix, verify and facilitate agree for the SAME
# payment — so the synthetic mismatch now uses a DIFFERENT payment's fp
# (different nonce) to prove reconcile's gap detection still works.
reg2 = x402facilitate.SettlementRegistry()
reg2._s[fp_a] = {"fingerprint": fp_a, "status": "settled", "tx": "0xabc"}
_other = x402facilitate.payment_fingerprint({**auth_fp, "nonce": "0x" + "ab" * 32})
assert _other != fp_a
ledger = [{"kind": "x402_settlement", "ts": 0.0,
           "detail": {"fingerprint": _other, "tx": "0xabc"}}]
rec = x402facilitate.reconcile(reg2, ledger)
check("F-T3-2 (synthetic): reconcile flags a settled payment as "
      "missing_in_ledger due to fingerprint mismatch",
      rec["ok"] is False and rec["missing_in_ledger"] == [fp_a], f"-> {rec}")

# ================= verdict =================
fails = [n for n, ok in RESULTS if not ok]
print(f"\n=== hublib: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILED:", fails)
sys.exit(1 if fails else 0)
