#!/usr/bin/env python3
"""T5: QR tickets - mint / door capability / name privacy / one-time redeem.

Covered here:
- capacity bookings mint a ticket; the raw token rides the 201 ONCE
  (ticket_token_once) and never lands on the persisted booking record
- GET /ticket/{token}: capability law (the token holder IS the attendee),
  honest door status, unknown token = plain 404
- POST /ticket/{token}/name: buyer door-display choice (full/first/guest),
  explicit UGC only (control chars rejected), no other credential needed
- POST /ticket/{token}/redeem: owner proof only (manage_code path proven;
  admin/list-token paths share the /confirm idiom), first scan wins, a
  second scan honestly reports first_time=false with the ORIGINAL timestamp
- buyer surfaces re-deliver the token: GET /book/{id} (booking secret) and
  GET /bookings/{id} (buyer view) carry the ticket block incl. ticket_token;
  the owner view stays token-free; the token persists hub-side by design
  (door capability, not identity) and rides the state snapshot
- QR PNG generation (segno, pure python, CSP-safe data: URI path)
- chat surface: fastpath + dispatcher know the 'ticket' command (static)
- OpenAPI documents the ticket trio (H13: documented == handled)

Run: python test_tickets.py
"""
import atexit
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _kill(p):
    if p:
        p.terminate()
        try: p.wait(timeout=5)
        except Exception: p.kill()


_ACTIVE = []
atexit.register(lambda: [_kill(p) for p in _ACTIVE])


def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5): return True
        except OSError: time.sleep(0.2)
    return False


def post(base, path, body, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Hub-Token"] = token
    rq = urllib.request.Request(base + path, data=json.dumps(body).encode(),
                                method="POST", headers=headers)
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception:
        return -1, {}


def get(base, path, token=None):
    headers = {}
    if token:
        headers["X-Hub-Token"] = token
    rq = urllib.request.Request(base + path, headers=headers)
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception:
        return -1, {}


TMP = tempfile.mkdtemp(prefix="hub-tickets-")
STATE = os.path.join(TMP, "state.json")
PORT = free_port()
HUB = f"http://127.0.0.1:{PORT}"
env = {**os.environ, "HUB_STATE_FILE": STATE,
       "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
hub = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(PORT)],
                       stdout=logf, stderr=subprocess.STDOUT, env=env)
_ACTIVE.append(hub)
assert wait_ready(PORT), "hub did not start"


def tokens(agent, acts):
    _, r = post(HUB, "/access", {"agent": agent, "acts": acts})
    return r.get("tokens", {})


LT = tokens("tick-merchant", ["list"])["list"]
BT = tokens("tick-buyer", ["book"])["book"]

# --- seed: one capacity listing (events vertical => tracks_capacity) -------
st, lr = post(HUB, "/listings", {"vertical": "events", "title": "T5 Gala",
    "price": 12, "location": "Vienna", "capacity": 10, "date": "2026-12-01"},
    token=LT)
assert st == 201, f"seed failed: {lr}"
LID, MCODE = lr["id"], lr["manage_code"]

# --- mint: booking 201 carries the door token exactly once -----------------
st, br = post(HUB, "/book", {"listing_id": LID, "attendee": "T5 Buyer",
                           "human_verified": True}, token=BT)
check("booking created on capacity vertical", st == 201 and br.get("escrow") == "HELD",
      f"got {st}: {br}")
BID = br.get("id", "")
TOK = br.get("ticket_token_once", "")
check("201 carries ticket_token_once (door link)", bool(TOK))
check("booking secret present for buyer surfaces", bool(br.get("booking_secret")))

# --- door read: capability law, honest status -------------------------------
st, t = get(HUB, f"/ticket/{TOK}")
check("door status opens with token alone (capability)",
      st == 200 and t.get("you_are_buyer") is True and t.get("you_are_owner") is False,
      f"got {st}: {t}")
check("door guest defaults to honest pseudonym",
      str(t.get("guest", "")).startswith("Guest #"))
check("door projection carries event context",
      t.get("title") == "T5 Gala" and t.get("when") == "2026-12-01" and t.get("qty") == 1)
st, _ = get(HUB, "/ticket/" + "x" * 40)
check("unknown token: indistinguishable 404", st == 404)
st, _ = get(HUB, "/ticket/short")
check("malformed token: 404 (no oracle)", st == 404)

# --- name privacy: buyer choice, explicit UGC only --------------------------
st, n1 = post(HUB, f"/ticket/{TOK}/name",
              {"display_name": "Ada Lovelace", "display_choice": "full"})
check("door name set via capability (full)", st == 200 and n1.get("guest") == "Ada Lovelace",
      f"got {st}: {n1}")
st, n2 = post(HUB, f"/ticket/{TOK}/name",
              {"display_name": "Ada Lovelace", "display_choice": "first"})
check("first-name-only choice", st == 200 and n2.get("guest") == "Ada")
st, n3 = post(HUB, f"/ticket/{TOK}/name",
              {"display_name": "", "display_choice": "guest"})
check("guest (private) choice hides the name",
      st == 200 and str(n3.get("guest", "")).startswith("Guest #"))
st, _ = post(HUB, f"/ticket/{TOK}/name",
             {"display_name": "Bad\nName", "display_choice": "full"})
check("control characters rejected (UGC law)", st == 400)
post(HUB, f"/ticket/{TOK}/name", {"display_name": "Ada Lovelace", "display_choice": "full"})

# --- one-time redeem: owner proof only --------------------------------------
st, _ = post(HUB, f"/ticket/{TOK}/redeem", {})
check("redeem without credential refused", st == 401)
st, _ = post(HUB, f"/ticket/{TOK}/redeem", {"manage_code": "mgr-wrongwrong"})
check("wrong manage_code refused", st == 403)
st, rc = post(HUB, f"/ticket/{TOK}/redeem", {"manage_code": MCODE})
ts1 = rc.get("redeemed_ts")
check("first scan wins (owner manage_code)",
      st == 200 and rc.get("first_time") is True and bool(ts1), f"got {st}: {rc}")
st, rc2 = post(HUB, f"/ticket/{TOK}/redeem", {"manage_code": MCODE})
check("second scan honest: first_time=false, ORIGINAL ts",
      st == 200 and rc2.get("first_time") is False and rc2.get("redeemed_ts") == ts1,
      f"got {st}: {rc2}")
st, _ = post(HUB, "/ticket/" + "y" * 40 + "/redeem", {"manage_code": MCODE})
check("redeem unknown ticket: 404", st == 404)

# --- buyer re-delivery surfaces ---------------------------------------------
st, det = get(HUB, f"/book/{BID}", token=br.get("booking_secret"))
tk = (det or {}).get("ticket") or {}
check("booking-secret view re-delivers the token",
      st == 200 and tk.get("ticket_token") == TOK
      and str(tk.get("ticket_url", "")).endswith("/t/" + TOK), f"got {st}: tk={tk}")
st, b2 = get(HUB, f"/bookings/{BID}", token=BT)
tk2 = (b2 or {}).get("ticket") or {}
check("buyer projection carries ticket + raw token",
      st == 200 and b2.get("view") == "buyer" and tk2.get("ticket_token") == TOK)
check("once-field never persists on the record",
      "ticket_token_once" not in b2)
st, b3 = get(HUB, f"/bookings/{BID}", token=LT)
tk3 = (b3 or {}).get("ticket") or {}
check("owner projection: state only, token-free",
      st == 200 and b3.get("view") == "owner" and tk3 and "ticket_token" not in tk3
      and "ticket_url" not in tk3, f"got {st}: tk3={tk3}")
check("owner sees redeemed state", tk3.get("redeemed") is True)

# --- persistence + QR + surfaces --------------------------------------------
snap = json.load(open(STATE))
tks = snap.get("tickets") or {}
check("token persists hub-side (door capability, not identity)",
      any(isinstance(t, dict) and t.get("token") == TOK for t in tks.values()))
import tickets as tkmod
png = tkmod.qr_png(TOK, "https://everlist.network")
check("QR PNG renders (segno)", png[:8] == b"\x89PNG\r\n\x1a\n")

st, spec = get(HUB, "/openapi.json")
paths = (spec or {}).get("paths") or {}
check("openapi documents the ticket trio",
      all(p in paths for p in ("/ticket/{token}", "/ticket/{token}/name",
                               "/ticket/{token}/redeem")))

chat_src = open(os.path.join(HERE, "chatlib.py"), encoding="utf-8").read()
check("chat fastpath knows 'ticket'", '\n    "ticket",' in chat_src)
check("chat dispatcher routes the ticket command",
      'low == "ticket"' in chat_src and "def _ticket_cmd" in chat_src)
check("chat stash keeps ticket tokens server-side",
      'ticket_tokens' in chat_src and 'ticket_token_once' in chat_src)

# --- excellence pins (2026-11-01: door page + ticket mail quality laws) -----
import pages_dl as _pdl
import emailkit as _ek

_tk_info = {"bid": "bk-EX1", "title": "Excellence Pin Event", "when": "Di, 03.11.2026 · 09:30",
            "location": "Raum 2", "listing_id": "l-ex1", "qty": 2,
            "guest": "Jean-Luc", "display_choice": "full", "redeemed": False,
            "you_are_owner": True, "you_are_buyer": True}
_tk_page = _pdl.ticket_html(_tk_info, "PinTokenPinTokenPinTok1", "https://everlist.network",
                            "de", owner=True, buyer=True).decode()
check("door page: status chip present",
      'tkchip tkok' in _tk_page)
check("door page: labeled detail rows (DE Datum/Ort)",
      'tkrows' in _tk_page and "Datum" in _tk_page and "Ort" in _tk_page)
check("door page: location reaches the page (projection law)",
      "Raum 2" in _tk_page)
check("door page: radio pills replace select (rich-control law)",
      'type="radio" name="display_choice"' in _tk_page and "<select" not in _tk_page)
check("door page: two-step check-in confirm gate",
      'tkconfirm' in _tk_page and "Ja, jetzt einchecken" in _tk_page)
check("door page: branded buttons",
      'tkbtn' in _tk_page)
_tk_nav = _tk_page.split('<nav', 1)[-1].split('</nav>', 1)[0]
check("door page: capability focus — no dash nav_extra",
      "/?view=dash" not in _tk_nav)
check("door page: stylesheet cache-bust current",
      "style.css?v=20261105d" in _tk_page)
_tk_used = _pdl.ticket_html(dict(_tk_info, redeemed=True, redeemed_ts="2026-11-01 09:41 UTC",
                                 you_are_owner=False, you_are_buyer=False),
                            "PinTokenPinTokenPinTok1", "https://everlist.network",
                            "en", owner=False, buyer=False).decode()
check("door page: used state chip, no mutating controls",
      'tkchip tkused' in _tk_used and 'tkconfirm' not in _tk_used
      and 'tkpills' not in _tk_used)

_em_de = _ek.ticket_email(title="Pin Event", booking_id="bk-EX1",
                          when="Di, 03.11.2026 · 09:30", location="Raum 2", qty=2,
                          door_name="Jean-Luc", ticket_url="https://everlist.network/t/x",
                          amount=24.0, escrow="HELD", qr=b"fauxpng", listing_id="l-ex1", loc="de")
_em_en = _ek.ticket_email(title="Pin Event", booking_id="bk-EX1",
                          when="Tue, Nov 3 2026 · 09:30", location="Room 2", qty=2,
                          door_name="Jean-Luc", ticket_url="https://everlist.network/t/x",
                          amount=24.0, escrow="HELD", qr=None, listing_id="l-ex1", loc="en")
check("ticket mail: EUR per money convention (DE after, EN before)",
      "24,00 €" in _em_de["html"] and "€ 24.00" in _em_en["html"])
check("ticket mail: calendar link in HTML and text",
      "/l/l-ex1.ics" in _em_de["html"] and "/l/l-ex1.ics" in _em_de["text"])
check("ticket mail: hero QR card with booking caption",
      "cid:ticketqr@everlist.network" in _em_de["html"]
      and "· EverList</div>" in _em_de["html"])
check("ticket mail: German calendar wording",
      "Zum Kalender hinzufügen" in _em_de["html"])

_ds = open(os.path.join(HERE, "tools", "deploy.sh")).read()
check("deploy.sh: @chat matcher routes /t/* to the webchat face", "/t/*" in _ds)
_js = open(os.path.join(HERE, "static", "app.js")).read()
check("app.js: ticket reveal opens the ticket page (not copy-only)",
      's.kind === "ticket"' in _js and "window.open(d.value" in _js)
check("app.js: chat transcript survives new tabs (localStorage)",
      "localStorage.getItem(TS_KEY)" in _js and "localStorage.setItem(TS_KEY" in _js)
_wc = open(os.path.join(HERE, "webchat.py")).read()
check("webchat: ticket secret label is the action (Show ticket)",
      '"ticket": "Show ticket"' in _wc)

_tk_hy = tkmod.mint("bk-EX2", "t", "w", 1)
tkmod.set_name(_tk_hy, "Jean-Luc", "full")
check("name law: hyphens survive (Jean-Luc stays Jean-Luc)",
      tkmod.display_name_of(_tk_hy) == "Jean-Luc")

print(f"\nT5 tickets: {len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED:")
    for n in FAIL:
        print("  -", n)
    sys.exit(1)
