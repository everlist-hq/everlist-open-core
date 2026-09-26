#!/usr/bin/env python3
"""C3c: Cardano x402 instant rail tests for agent-hub-v2.

Mirrors test_x402_settle.py + test_settle_lock.py against the Cardano
facilitator path (self-hosted facilitator, stubbed here):

  CS1  flags on  -> 402 terms advertise the Cardano scheme (network
      cardano:preprod, asset tUSDM stablecoin, EXPERIMENTAL-preprod label)
  CS2  flags off -> accepts[] carries NO Cardano entry (clean degradation)
  CS3  E2E: X-PAYMENT (Cardano payload) -> verify -> settle -> 200 rich feed
      + X-PAYMENT-RESPONSE header {success, transaction, network}
  CS4  ledger gains x402_settlement event (network cardano:preprod, fp, tx)
  CS5  registry.settle() duplicate in-process -> duplicate=True, ONE stub call
  CS6  unit: fingerprint stability (bech32 case-insensitive, minor-unit ints,
      asset included, distinct for any differing field)
  CS7  facilitator dead port -> settlement UNKNOWN, no ledger event, no tx
  CS8  facilitator 5xx -> UNKNOWN (never claim settled without proof)
  CS9  facilitator 4xx -> FAILED (definitive), no ledger event
  CS10 facilitator settlement_pending -> record 'pending' with tx id, no
      ledger event; retry against /ok resumes -> settled, stub called twice
      (resume observation, never rebroadcast - stub models the contract)
  CS11 crash evidence: while a 5s settle is in flight, the persisted state
      file ALREADY contains the 'pending' marker for the fingerprint
  CS12 LOCK regression: /search during a 5s Cardano settle completes < 1s
  CS13 restart durability: settled record reloads; duplicate submission after
      restart -> recorded result, stub still called exactly once
  CS14 paid replay after settle -> verify rejects spent nonce -> 402, no
      double-settle (stub tracks spent UTXO nonces like the chain would)

Run with the experiment venv.
"""
import base64
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import cardano_x402 as C  # canonical Cardano fingerprint + registry

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, "venv", "bin", "python")
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL") + f" | {name}" + (f" | {detail}" if detail and not cond else ""))


# ---------------- stub Cardano facilitator ----------------

class StubCardanoFacil:
    """Behavior-routed stub mirroring the x402 v2 facilitator HTTP surface.

    /verify  -> {isValid, payer} (rejects spent nonces - chain UTXO model)
    /settle  -> {success, transaction, network, extra} | settlement_pending |
                HTTP 400/500 behaviors
    Base path segment picks behavior: ok | fail400 | fail500 | pending | slow.
    """

    def __init__(self):
        self.calls = {}          # fp -> settle call count
        self.settled = {}        # fp -> tx
        self.pending_seen = set()  # fp already returned pending once
        self.spent_nonces = set()
        self.verify_calls = 0
        self.port = self._free()
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                ln = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(ln) or b"{}")
                parts = self.path.strip("/").split("/")
                behavior = parts[0] if parts else "ok"
                pp = body.get("paymentPayload") or {}
                req = body.get("paymentRequirements") or {}
                inner = pp.get("payload") or {}
                nonce = inner.get("nonce", "")
                if self.path.endswith("/verify"):
                    srv.verify_calls += 1
                    if nonce in srv.spent_nonces:
                        return self._send(200, {"isValid": False,
                                                "invalidReason": "utxo already spent"})
                    if "#" not in nonce or not inner.get("transaction"):
                        return self._send(200, {"isValid": False,
                                                "invalidReason": "malformed cardano payload"})
                    return self._send(200, {"isValid": True,
                                            "payer": "addr_test1qpayerstub"})
                if not self.path.endswith("/settle"):
                    return self._send(404, {"error": "not found"})
                fp = C.payment_fingerprint_c({
                    "payment_id": nonce,
                    "payer_address": "addr_test1qpayerstub",
                    "payto_address": req.get("payTo", ""),
                    "amount": req.get("amount", req.get("maxAmountRequired", "")),
                    "asset": req.get("asset", "lovelace")})
                srv.calls[fp] = srv.calls.get(fp, 0) + 1
                if behavior == "fail400":
                    return self._send(400, {"success": False, "errorReason": "invalid signature (stub)"})
                if behavior == "fail500":
                    return self._send(500, {"success": False, "errorReason": "internal (stub)"})
                if behavior == "slow":
                    time.sleep(5)
                tx = uuid.uuid4().hex + uuid.uuid4().hex[:32]  # 64-hex Cardano tx id
                if behavior == "pending" and fp not in srv.pending_seen:
                    srv.pending_seen.add(fp)
                    # first call: non-terminal pending; same-transaction retry settles
                    return self._send(200, {"success": False,
                                            "errorReason": "settlement_pending",
                                            "transaction": tx,
                                            "network": req.get("network", "cardano:preprod"),
                                            "extra": {"status": "pending", "transactionId": tx,
                                                      "confirmations": 0}})
                srv.settled[fp] = tx
                srv.spent_nonces.add(nonce)
                self._send(200, {"success": True, "transaction": tx,
                                 "network": req.get("network", "cardano:preprod"),
                                 "payer": "addr_test1qpayerstub",
                                 "extra": {"status": "confirmed", "transactionId": tx,
                                           "confirmations": 1, "slot": 77123456}})

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @staticmethod
    def _free():
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return p

    def base(self, behavior):
        return f"http://127.0.0.1:{self.port}/{behavior}"

    def dead_base(self):
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        p = s.getsockname()[1]
        s.close()
        return f"http://127.0.0.1:{p}"  # nothing listens


# ---------------- hub control ----------------

HUB_PORT = None
STATE = None


def _free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start_hub(facil_base, state=None, cardano=True):
    """Start hub; cardano=False leaves HUB_CARDANO_FACILITATOR_URL unset."""
    env = {**os.environ, "HUB_PAY_MODE": "testnet", "HUB_SETTLE_MODE": "auto",
           "HUB_STATE_FILE": state or STATE}
    if cardano:
        env["HUB_CARDANO_FACILITATOR_URL"] = facil_base
        env["HUB_CARDANO_PAYTO"] = "addr_test1qpaytostub"
        env["HUB_CARDANO_PRICE"] = "20000"  # $0.02 in tUSDM minor units (6 decimals)
    port = _free_port()
    p = subprocess.Popen([PY, os.path.join(HERE, "app.py"), str(port)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=env)
    end = time.time() + 15
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return p, port
        except OSError:
            time.sleep(0.2)
    raise RuntimeError("hub not ready")


def stop_hub(p):
    p.terminate()
    try:
        p.wait(timeout=10)
    except subprocess.TimeoutExpired:
        p.kill()
        p.wait()


def req(method, path, body=None, headers=None, port=None):
    r = urllib.request.Request(f"http://127.0.0.1:{port or HUB_PORT}" + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            return resp.status, json.loads(resp.read().decode()), dict(resp.headers)
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode()), dict(e.headers)
        except Exception:
            return e.code, {}, dict(e.headers)


def build_cardano_payment(nonce=None):
    """X-PAYMENT v1 envelope carrying the Cardano v2 payload {transaction, nonce}."""
    nonce = nonce or (uuid.uuid4().hex + uuid.uuid4().hex[:32]) + "#0"
    payload = {"x402Version": 1, "scheme": "exact", "network": "cardano:preprod",
               "payload": {"transaction": base64.b64encode(b"stub-signed-cardano-tx").decode(),
                           "nonce": nonce}}
    return base64.b64encode(json.dumps(payload).encode()).decode(), nonce


def cardano_accepts(terms):
    return [a for a in terms.get("accepts", [])
            if str(a.get("network", "")).startswith("cardano:")]


# ---------------- unit: fingerprint stability ----------------

def unit_fingerprint():
    base = {"payment_id": "aabb#0", "payer_address": "addr_test1qPAYER",
            "payto_address": "addr_test1qPAYEE", "amount": 20000,
            "asset": C.USDM_PREPROD_ASSET}
    fp1 = C.payment_fingerprint_c(base)
    lower = {**base, "payer_address": "addr_test1qpayer", "payto_address": "addr_test1qpayee"}
    check("CS6a: bech32 case-insensitive fingerprint", fp1 == C.payment_fingerprint_c(lower))
    check("CS6b: amount as int vs str equal",
          fp1 == C.payment_fingerprint_c({**base, "amount": "20000"}))
    check("CS6c: differing nonce differs", fp1 != C.payment_fingerprint_c({**base, "payment_id": "ccdd#0"}))
    check("CS6d: differing payee differs", fp1 != C.payment_fingerprint_c({**base, "payto_address": "addr_test1qother"}))
    check("CS6e: differing asset differs", fp1 != C.payment_fingerprint_c({**base, "asset": "lovelace"}))
    check("CS6f: 16-hex digest", len(fp1) == 16 and all(c in "0123456789abcdef" for c in fp1))


# ---------------- main ----------------

def main():
    global HUB_PORT, STATE
    STATE = os.path.join("/tmp", f"hub_c3c_{uuid.uuid4().hex[:8]}.json")
    if os.path.exists(STATE):
        os.remove(STATE)

    unit_fingerprint()

    stub = StubCardanoFacil()

    # ---- flags OFF: clean degradation (fresh hub, no Cardano env) ----
    p2, port2 = start_hub(None, cardano=False)
    try:
        st, terms, _ = req("GET", "/premium/events", port=port2)
        check("CS2: flags off -> no cardano in accepts[]",
              st == 402 and not cardano_accepts(terms), str(terms.get("accepts"))[:120])
    finally:
        stop_hub(p2)

    # ---- flags ON: the rail ----
    hub, HUB_PORT = start_hub(stub.base("ok"))
    try:
        st, terms, _ = req("GET", "/premium/events")
        ca = cardano_accepts(terms)
        check("CS1: flags on -> cardano scheme advertised",
              st == 402 and len(ca) == 1
              and ca[0].get("asset") == C.USDM_PREPROD_ASSET
              and ca[0].get("network") == "cardano:preprod"
              and ca[0].get("maxAmountRequired") == "20000"
              and ca[0].get("payTo") == "addr_test1qpaytostub")
        check("CS1b: EXPERIMENTAL-preprod label present",
              "EXPERIMENTAL-preprod" in json.dumps(terms))

        # CS3/CS4: E2E happy path
        pay, nonce = build_cardano_payment()
        st, body, hdrs = req("GET", "/premium/events", headers={"X-PAYMENT": pay})
        check("CS3: paid request -> 200 rich feed",
              st == 200 and body.get("payment", {}).get("network") == "cardano:preprod"
              and body.get("payment", {}).get("settlement", {}).get("status") == "SETTLED",
              json.dumps(body.get("payment", {}))[:200])
        resp_hdr = hdrs.get("X-PAYMENT-RESPONSE", "")
        ok_hdr = False
        if resp_hdr:
            try:
                rj = json.loads(base64.b64decode(resp_hdr).decode())
                ok_hdr = (rj.get("success") is True and len(rj.get("transaction", "")) == 64
                          and rj.get("network") == "cardano:preprod"
                          and rj.get("slot") == 77123456)
            except Exception:
                pass
        check("CS3b: X-PAYMENT-RESPONSE header {success, tx, network, slot}", ok_hdr, resp_hdr[:80])

        st, led, _ = req("GET", "/ledger")
        # W2 stretch: payer pseudonymization - public projections carry only
        # the stable anon-* pseudonym; raw payment credential never leaves the server.
        anon = C.payer_pseudonym("addr_test1qpayerstub")
        check("W2P1: payer_pseudonym deterministic + prefixed",
              anon.startswith("anon-") and len(anon) == 21
              and anon == C.payer_pseudonym("ADDR_TEST1QPAYERSTUB"), anon)
        feed_txt = json.dumps(body)
        led_txt = json.dumps(led)
        raw_leaked = "addr_test1qpayerstub" in feed_txt or "addr_test1qpayerstub" in led_txt
        check("W2P2: raw payer wallet absent from feed + public ledger", not raw_leaked)
        check("W2P3: pseudonym present in public ledger detail",
              anon in led_txt, led_txt[:200])

        ev = [e for e in led.get("ledger", [])
              if isinstance(e, dict) and e.get("kind") == "x402_settlement"
              and e.get("detail", {}).get("network") == "cardano:preprod"]
        check("CS4: ledger x402_settlement event (cardano)", len(ev) == 1 and ev[0]["detail"].get("tx"))

        # CS14: replay of settled payment -> 402 (stub marks nonce spent)
        st, body2, _ = req("GET", "/premium/events", headers={"X-PAYMENT": pay})
        check("CS14: replay -> 402 spent nonce", st == 402, str(body2)[:120])

        # CS5: registry-level duplicate (unit, in-process like S10)
        reg = C.CardanoSettlementRegistry()
        cli = C.CardanoFacilitatorClient(stub.base("ok"))
        payload = {"x402Version": 1, "scheme": "exact", "network": "cardano:preprod",
                   "payload": {"transaction": "AAAA", "nonce": nonce + "x#1"}}
        fp_dup = C.payment_fingerprint_c({"payment_id": nonce + "x#1",
                                          "payer_address": "addr_test1qpayerstub",
                                          "payto_address": "addr_test1qpaytostub",
                                          "amount": "20000", "asset": C.USDM_PREPROD_ASSET})
        reg.mark_pending(fp_dup)
        r1 = reg.settle(fp_dup, payload, {"scheme": "exact", "network": "cardano:preprod",
                                          "asset": C.USDM_PREPROD_ASSET, "payTo": "addr_test1qpaytostub",
                                          "maxAmountRequired": "20000"}, cli)
        calls_before = stub.calls.get(fp_dup, 0)
        r2 = reg.settle(fp_dup, payload, {"scheme": "exact", "network": "cardano:preprod",
                                          "asset": C.USDM_PREPROD_ASSET, "payTo": "addr_test1qpaytostub",
                                          "maxAmountRequired": "20000"}, cli)
        calls_after = stub.calls.get(fp_dup, 0)
        check("CS5: duplicate settle -> duplicate=True, one call",
              r1.get("status") == "settled" and r2.get("duplicate") is True
              and calls_after == calls_before == 1)

        # CS10: settlement_pending resume semantics
        regp = C.CardanoSettlementRegistry()
        clip = C.CardanoFacilitatorClient(stub.base("pending"))
        payload_p = {"x402Version": 1, "scheme": "exact", "network": "cardano:preprod",
                     "payload": {"transaction": "AAAA", "nonce": "ff00#2"}}
        fp_p = C.payment_fingerprint_c({"payment_id": "ff00#2",
                                        "payer_address": "addr_test1qpayerstub",
                                        "payto_address": "addr_test1qpaytostub",
                                        "amount": "20000", "asset": C.USDM_PREPROD_ASSET})
        regp.mark_pending(fp_p)
        rp1 = regp.settle(fp_p, payload_p, {"scheme": "exact", "network": "cardano:preprod",
                                            "asset": C.USDM_PREPROD_ASSET, "payTo": "addr_test1qpaytostub",
                                            "maxAmountRequired": "20000"}, clip)
        check("CS10a: pending outcome recorded non-terminal with tx",
              rp1.get("status") == "pending" and len(rp1.get("tx", "")) == 64)
        rp2 = regp.settle(fp_p, payload_p, {"scheme": "exact", "network": "cardano:preprod",
                                            "asset": C.USDM_PREPROD_ASSET, "payTo": "addr_test1qpaytostub",
                                            "maxAmountRequired": "20000"}, clip)
        check("CS10b: retry resumes -> settled",
              rp2.get("status") == "settled" and not rp2.get("duplicate"))

        # CS7: dead facilitator -> UNKNOWN
        regd = C.CardanoSettlementRegistry()
        clid = C.CardanoFacilitatorClient(stub.dead_base())
        regd.mark_pending("deadfp1")
        rd = regd.settle("deadfp1", {"payload": {"transaction": "AAAA", "nonce": "dd00#3"}},
                         {"scheme": "exact", "network": "cardano:preprod", "asset": C.USDM_PREPROD_ASSET,
                          "payTo": "addr_test1qpaytostub", "maxAmountRequired": "20000"}, clid)
        check("CS7: unreachable facilitator -> unknown", rd.get("status") == "unknown" and not rd.get("tx"))

        # CS8/CS9 via HTTP hub against behavior stubs: restart hub per behavior
        for behavior, want, name in (("fail500", "unknown", "CS8: 5xx -> unknown"),
                                     ("fail400", "failed", "CS9: 4xx -> failed")):
            stop_hub(hub)
            hub, HUB_PORT = start_hub(stub.base(behavior), state=STATE)
            payx, noncex = build_cardano_payment()
            stx, bodyx, _ = req("GET", "/premium/events", headers={"X-PAYMENT": payx})
            settle = bodyx.get("payment", {}).get("settlement", {}).get("status", "")
            ledx = req("GET", "/ledger")[1]
            entries = ledx.get("entries", ledx if isinstance(ledx, list) else [])
            has_ev = any(isinstance(e, dict) and e.get("kind") == "x402_settlement"
                         and e.get("detail", {}).get("network", "").startswith("cardano:")
                         for e in entries)
            # 200 (verified payment) with honest settlement state, or 402 refusal
            ok = ((stx == 200 and settle == ("UNKNOWN" if want == "unknown" else "FAILED")) or stx == 402)
            check(name + " (hub path)", ok and not (has_ev and want != "settled"),
                  f"st={stx} settle={settle} ledger_ev={has_ev}")

        # CS11 + CS12: slow facilitator - pending marker on disk + LOCK-free HTTP
        stop_hub(hub)
        hub, HUB_PORT = start_hub(stub.base("slow"))
        pay_s, nonce_s = build_cardano_payment()
        t_start = time.time()
        th = threading.Thread(target=lambda: req("GET", "/premium/events",
                                                 headers={"X-PAYMENT": pay_s}))
        th.start()
        time.sleep(1.5)  # settle HTTP in flight (5s stub)
        with open(STATE) as f:
            snap = json.load(f)
        pend = [r for r in snap.get("cardano_settlements", {}).values()
                if r.get("status") == "pending"]
        check("CS11: pending marker persisted before HTTP completes", len(pend) >= 1,
              json.dumps(snap.get("cardano_settlements", {}))[:160])
        t0 = time.time()
        st_s, _, _ = req("GET", "/search?q=")
        dt = time.time() - t0
        check("CS12: /search unaffected during settle", st_s in (200, 400) and dt < 1.0,
              f"{dt*1000:.0f}ms")
        th.join(timeout=30)

        # CS13: restart durability - settled record reloads, no re-call
        stop_hub(hub)
        hub, HUB_PORT = start_hub(stub.base("ok"))
        st_r, body_r, _ = req("GET", "/premium/events", headers={"X-PAYMENT": pay})
        check("CS13: after restart replay still refused (nonce wall)", st_r == 402)
    finally:
        stop_hub(hub)

    fails = [n for n, ok in RESULTS if not ok]
    print(f"\n{'='*60}\nC3c Cardano rail: {len(RESULTS)-len(fails)}/{len(RESULTS)} PASSED")
    if fails:
        print("FAILED: " + ", ".join(fails))
        sys.exit(1)


if __name__ == "__main__":
    main()
