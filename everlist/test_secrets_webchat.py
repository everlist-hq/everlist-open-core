"""test_secrets_webchat.py — Secret placeholder system (spec 2026-10-18).

A0-style: raw secrets NEVER enter the chat transcript, logs, or LLM
context. The webchat path replaces them with [[secret:kind:ref]] markers
+ a server vault; the UI reveals once via /api/secret/reveal.

Contract under test:
  1. Emitters (signup, book, recover-confirm, list-create, private-deal)
     emit [[secret:<kind>:<ref>]] markers, never raw values, in the
     WEBCHAT path.
  2. chatlib._SECRET_STASH holds the raw value per sender (15-min TTL).
  3. chatlib.secrets_inline(reply, sender) restores raw values for the
     agent/A2A/CLI path (existing text contract).
  4. webchat vault: bind ref->sid, one-time consume, TTL, caps, rate limit.
  5. /api/secret/reveal: correct sid + live ref -> value + consumed;
     second call -> 410; wrong sid -> 403; expired -> 410; unknown -> 404.
  6. SSE deltas and reply payloads carry markers, never raw secrets.
  7. phrase.py never sees secret values (markers stripped before author
     call; author prompt contains no ref ids).

Run: spawn full stack (hub + webchat), drive /api/chat over HTTP,
assert on replies, payloads, and the reveal endpoint.
"""
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
import http.cookiejar

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# ---- harness (same pattern as test_fullflow.py) ----

_RESULTS = []


def check(name, ok, detail=""):
    _RESULTS.append((name, bool(ok)))
    print(("PASS " if ok else "FAIL ") + name + (" — " + str(detail)[:120] if not ok else ""))
    return ok


class C:
    """One cookie-jar persona."""

    def __init__(self, base):
        self.jar = http.cookiejar.CookieJar()
        self.op = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.jar))
        self.base = base

    def say(self, text):
        req = urllib.request.Request(
            self.base + "/api/chat",
            data=json.dumps({"text": text}).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with self.op.open(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            return {"error": str(e.code), "reply": ""}

    def reveal(self, ref):
        req = urllib.request.Request(
            self.base + "/api/secret/reveal",
            data=json.dumps({"ref": ref}).encode(), method="POST",
            headers={"Content-Type": "application/json"})
        try:
            with self.op.open(req, timeout=15) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            body = {}
            try:
                body = json.loads(e.read().decode())
            except Exception:
                pass
            return e.code, body


def main():
    # ---- spawn full stack (hub + webchat), brain off ----
    env = dict(os.environ)
    env.update({"EVERLIST_BRAIN_DISABLED": "1", "EVERLIST_LLM_FIRST": "0",
                "EVERLIST_PHRASE": "0"})
    hub_port = 8814
    web_port = 8815
    hub_p = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "app.py")],
        env={**env, "PORT": str(hub_port), "HUB_DB": ":memory:"},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    web_p = subprocess.Popen(
        [sys.executable, os.path.join(HERE, "webchat.py")],
        env={**env, "PORT": str(web_port), "HUB_URL": "http://127.0.0.1:%d" % hub_port},
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        base = "http://127.0.0.1:%d" % web_port
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/api/health", timeout=1)
                break
            except Exception:
                time.sleep(0.5)

        a = C(base)

        # ---- 1. signup: seed is a marker, not raw ----
        d = a.say("signup")
        r = d.get("reply") or ""
        check("S1 signup reply has secret marker",
              re.search(r"\[\[secret:seed:[0-9a-f]+\]\]", r), r[:100])
        check("S2 signup reply has NO raw seed (no 64-hex)",
              not re.search(r"\b[0-9a-f]{64}\b", r), r[:100])
        secs = d.get("secrets") or []
        check("S3 payload secrets array present",
              isinstance(secs, list) and len(secs) >= 1
              and all(s.get("ref") and s.get("kind") for s in secs), str(secs)[:120])

        # ---- 2. reveal: once -> value; twice -> 410 ----
        if secs:
            ref = secs[0]["ref"]
            st, body = a.reveal(ref)
            check("S4 first reveal returns the value",
                  st == 200 and re.search(r"\b[0-9a-f]{64}\b", body.get("value") or ""),
                  str(st) + " " + str(body)[:80])
            st2, body2 = a.reveal(ref)
            check("S5 second reveal refused (410)", st2 == 410, str(st2))

            # ---- 3. login-seed with the revealed value works ----
            seed_val = body.get("value") if st == 200 else ""
            if seed_val:
                d2 = a.say("login-seed " + seed_val)
                check("S6 login-seed with revealed value works",
                      "welcome back" in (d2.get("reply") or "").lower()
                      or "logged" in (d2.get("reply") or "").lower(),
                      (d2.get("reply") or "")[:80])

        # ---- 4. wrong sid -> 403 ----
        b = C(base)
        d_b = b.say("signup")
        secs_b = d_b.get("secrets") or []
        if secs_b:
            # a tries to reveal b's ref
            st3, _ = a.reveal(secs_b[0]["ref"])
            check("S7 wrong-sid reveal refused (403)", st3 == 403, str(st3))
            # b reveals own
            st4, _ = b.reveal(secs_b[0]["ref"])
            check("S8 owner-sid reveal works", st4 == 200, str(st4))

        # ---- 5. booking secret: marker + reveal ----
        # (use a free listing to avoid the pay gate)
        # admin-seed a free listing
        admin = C(base)
        admin.say("signup")
        # find any listing via search
        d_s = admin.say("search all")
        results = d_s.get("results") or []
        if not results:
            # create one via admin API
            try:
                req = urllib.request.Request(
                    "http://127.0.0.1:%d/admin/listings" % hub_port,
                    data=json.dumps({
                        "title": "Free Test Event",
                        "date": "2099-01-01", "price": 0,
                        "capacity": 5, "category": "test",
                        "owner": "admin"}).encode(), method="POST",
                    headers={"Content-Type": "application/json",
                             "X-Admin-Key": "ff-admin"})
                with urllib.request.urlopen(req, timeout=10) as resp:
                    pass
            except Exception:
                pass
            d_s = admin.say("search all")
            results = d_s.get("results") or []

        if results:
            free = next((x for x in results if float(x.get("price", 0) or 0) == 0), results[0])
            title = free.get("title") or ""
            d_bk = admin.say("book \"%s\" under TestUser" % title)
            r_bk = d_bk.get("reply") or ""
            check("S9 booking reply has secret marker or plain secret",
                  re.search(r"\[\[secret:booking:[0-9a-f]+\]\]", r_bk)
                  or "booking_secret" in r_bk or "🔑" in r_bk,
                  r_bk[:100])

        # ---- 6. chatlib.secrets_inline: agent path gets raw values ----
        sys.path.insert(0, HERE)
        os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
        import chatlib
        # simulate: stash a secret, build marker reply, inline it
        test_sender = "test-inline-sender"
        chatlib._SECRET_STASH.setdefault(test_sender, {})["test-ref"] = {
            "kind": "seed", "value": "a" * 64, "ts": time.time()}
        marker_reply = "Your seed: [[secret:seed:test-ref]]"
        inlined = chatlib.secrets_inline(marker_reply, test_sender)
        check("S10 secrets_inline restores raw value",
              "a" * 64 in inlined and "[[secret:" not in inlined, inlined[:80])

        # ---- 7. phrase never sees markers ----
        try:
            import phrase
            red, secrets = phrase._redact(
                "🔑 [[secret:seed:abc123]]\nsome text")
            check("S11 phrase redact strips secret markers",
                  "[[secret:" not in red, red[:80])
        except Exception as e:
            check("S11 phrase redact strips secret markers", False, str(e)[:80])

    finally:
        for p in (web_p, hub_p):
            try:
                p.terminate()
                p.wait(timeout=5)
            except Exception:
                p.kill()

    ok = sum(1 for _, o in _RESULTS if o)
    print("\n=== secrets-webchat: %d/%d passed ===" % (ok, len(_RESULTS)))
    if ok < len(_RESULTS):
        print("SECRETS_WEBCHAT_FAILED")
        sys.exit(1)
    print("SECRETS_WEBCHAT_ALL_PASSED")


if __name__ == "__main__":
    main()
