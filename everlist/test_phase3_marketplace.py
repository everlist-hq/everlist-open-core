#!/usr/bin/env python3
"""Phase 3 marketplace (owner GO 2026-11-07): recurring series, appointment
slots, sponsored placement, enrichment provider chain.

Series covers:
- events+series {every_days, count} -> count child listings, shared series_id,
  base date included in response dates; children are plain listings (no
  nested "series" field — fan-out cannot recurse)
- honest 400s: malformed series shape, count out of 2..12, series without date
- S7 cap is atomic for the family: a 6-listing series on a full cap creates
  NOTHING (all-or-nothing, 409 with series sizing)
- archive_series / delete_series act on the whole family; delete refuses
  while any member has active bookings; archived base still resolves the
  family via the manage route
Slots cover:
- services+slot_minutes books ONLY with slot_date+slot_time (grid-aligned;
  misaligned -> 409; missing -> 400 appointment-required)
- taken slot -> 409 slot_taken; a DIFFERENT grid slot books fine;
  cancelling frees the slot (taken-ness derives from escrow state)
- slot fields on slot-less listings -> 400; spoof-strip: slot_date sent to a
  slot-less listing never lands on the listing or booking record
Sponsored covers:
- reserved wall: client _sponsor rejected at create (spoof law)
- /admin/sponsor grants; wrong admin key -> 403; unknown listing -> 404
- search returns the sponsored listing LAST with sponsored=true (organic
  order untouched otherwise); expired/unknown _sponsor never labels
Enrichment chain covers:
- EVERLIST_ENRICH_USE_LLM_ENV=1 builds the provider chain from llm.env
  (NLU first, ZAI second); explicit knobs take precedence
- fail-open preserved: live mode with no chain and no env -> None, creates
  still succeed
Run: ./venv/bin/python test_phase3_marketplace.py
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
sys.path.insert(0, os.path.join(HERE, "sdk"))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, "" if cond else detail)


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    return p


def _kill(p):
    if p:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()


_ACTIVE = []
atexit.register(lambda: [_kill(p) for p in _ACTIVE])


def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def spawn(env_extra=None):
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="hub-phase3mk-")
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(tmp, "state.json"),
           "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
    env.update(env_extra or {})
    logf = open(os.path.join(tmp, "hub.log"), "w")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), "hub did not start"
    return f"http://127.0.0.1:{port}", p, logf


def req(method, path, body=None, headers=None, base=None):
    h = {"Content-Type": "application/json"}
    h.update(headers or {})
    r = urllib.request.Request((base or HUB) + path,
                               data=(json.dumps(body).encode() if body is not None else None),
                               method=method, headers=h)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception:
        return -1, {}


HUB = ""
ADMIN = {"X-Hub-Token": "dev-admin-key-change-me"}


def main():
    global HUB
    HUB, _p, _log = spawn()

    # ---------- setup: tokens ----------
    _s, lt = req("POST", "/access", {"agent": "p3-list", "acts": ["list"]})
    check("setup: list token", _s in (200, 201) and lt.get("tokens", {}).get("list"), f"{_s}")
    LT = {"X-Hub-Token": lt["tokens"]["list"]}
    _s, bt = req("POST", "/access", {"agent": "p3-book", "acts": ["book"]})
    check("setup: book token", _s in (200, 201) and bt.get("tokens", {}).get("book"), f"{_s}")
    BT = {"X-Hub-Token": bt["tokens"]["book"]}

    _ev = {"vertical": "events", "title": "Weekly Salsa Night",
           "description": "salsa dancing social", "date": "2026-12-01",
           "location": "Wien", "price": 5.0, "capacity": 40}

    # ---------- A. recurring series ----------
    _s, r = req("POST", "/listings", dict(_ev,
        series={"every_days": 7, "count": 4}), LT)
    check("A1 series create 201", _s == 201, f"{_s} {r}")
    _sid = (r.get("series") or {}).get("id", "")
    _dates = (r.get("series") or {}).get("dates", [])
    check("A2 series id minted", _sid.startswith("series-"), r)
    check("A3 four dates, base first", len(_dates) == 4 and _dates[0] == "2026-12-01"
          and _dates[1] == "2026-12-08" and _dates[3] == "2026-12-22", _dates)
    check("A4 one manage code for family", bool(r.get("manage_code")), r)
    _s, sr = req("GET", "/search?vertical=events&q=salsa", LT)
    fam = sr.get("listings", [])
    check("A5 four family listings found", sr.get("count") == 4, sr.get("count"))
    check("A6 children share series_id (pub)", all(l.get("series_id") == _sid for l in fam),
          [l.get("series_id") for l in fam])
    check("A7 no child carries series trigger",
          all("series" not in l or not isinstance(l.get("series"), dict) for l in fam),
          [l.get("series") for l in fam])
    _s, bad = req("POST", "/listings", dict(_ev, title="Bad Series",
        series={"every_days": 7, "count": 1}), LT)
    check("A8 count<2 refused", _s == 400, _s)
    _s, bad = req("POST", "/listings", dict(_ev, title="Bad Series",
        series={"every_days": 7, "count": 13}), LT)
    check("A9 count>12 refused", _s == 400, _s)
    _s, bad = req("POST", "/listings", dict(_ev, title="Bad Series",
        series={"every_days": 0, "count": 3}), LT)
    check("A10 every_days>=1 enforced", _s == 400, _s)
    _s, bad = req("POST", "/listings", {"vertical": "services", "title": "NoDate Svc",
        "provider": "x", "price": 1, "series": {"every_days": 5, "count": 3}}, LT)
    check("A11 series without date refused", _s == 400, _s)

    # A12: atomic cap — create a fresh hub at cap, then try a 6-listing series
    HUB2, p2, _l2 = spawn({"HUB_LISTING_CAP": "5"})
    _s, lt2 = req("POST", "/access", {"agent": "p3-cap", "acts": ["list"]}, base=HUB2)
    LT2 = {"X-Hub-Token": lt2["tokens"]["list"]}
    _ev2 = dict(_ev, title="Cap Filler {i}")
    okc = 0
    for i in range(5):
        _s, _r = req("POST", "/listings", dict(_ev2, title=f"Cap Filler {i}"),
                     LT2, base=HUB2)
        okc += (_s == 201)
    check("A12 pre: five listings fill cap", okc == 5, okc)
    _s, r = req("POST", "/listings", dict(_ev, title="Too Big Series",
        series={"every_days": 7, "count": 6}), LT2, base=HUB2)
    check("A13 series over cap -> 409, nothing created", _s == 409 and "cap" in str(r).lower(), f"{_s} {r}")
    _s, sr = req("GET", "/search?q=Too%20Big%20Series", base=HUB2)
    check("A14 zero partial children", sr.get("count") == 0, sr.get("count"))
    _p2kill = p2

    # ---------- B. series manage acts (back on HUB) ----------
    _s, ldet = req("GET", f"/listings/{fam[0]['id']}")
    _s, mc = req("POST", "/access", {"agent": "p3-own", "acts": ["list"]})
    OWN = {"X-Hub-Token": mc["tokens"]["list"]}
    # need manage_code: create a small dedicated series for act tests
    _s, r2 = req("POST", "/listings", dict(_ev, title="Yoga Morning Series",
        date="2026-12-05", series={"every_days": 3, "count": 3}), LT)
    MGR = r2.get("manage_code", "")
    _s, sr = req("GET", "/search?q=Yoga%20Morning%20Series")
    yfam = sr.get("listings", [])
    check("B1 yoga family of 3", sr.get("count") == 3, sr.get("count"))
    _s, r = req("POST", f"/listings/{yfam[0]['id']}/manage",
                {"action": "archive_series"}, {**LT, "X-Manage-Code": ""})
    _s, r = req("POST", f"/listings/{yfam[0]['id']}/manage",
                {"action": "archive_series", "manage_code": MGR}, LT)
    check("B2 archive_series hides family", _s == 200 and r.get("archived") == 3, f"{_s} {r}")
    _s, sr = req("GET", "/search?q=Yoga%20Morning%20Series")
    check("B3 archived family invisible", sr.get("count") == 0, sr.get("count"))
    _s, r = req("POST", f"/listings/{yfam[0]['id']}/manage",
                {"action": "unarchive", "manage_code": MGR}, LT)
    check("B4 single-date unarchive works", _s == 200, _s)
    _s, sr = req("GET", "/search?q=Yoga%20Morning%20Series")
    check("B5 one date revived", sr.get("count") == 1, sr.get("count"))
    _s, r = req("POST", f"/listings/{yfam[0]['id']}/manage",
                {"action": "delete_series", "manage_code": MGR}, LT)
    check("B6 delete_series removes family", _s == 200 and r.get("deleted") == 3, f"{_s} {r}")
    _s, sr = req("GET", "/search?q=Yoga%20Morning%20Series")
    check("B7 family gone entirely", sr.get("count") == 0, sr.get("count"))
    _s, r = req("POST", f"/listings/{fam[0]['id']}/manage",
                {"action": "delete_series", "manage_code": "mgr-wrong"}, LT)
    check("B8 wrong manage code refused", _s == 403, _s)

    # ---------- C. appointment slots ----------
    _s, r = req("POST", "/listings", {"vertical": "services", "title": "PhysioErgo Therapy",
        "provider": "Mag. Reiter", "price": 60.0, "location": "Graz",
        "description": "physiotherapy session", "duration_minutes": 50,
        "slot_minutes": 30}, LT)
    check("C1 slot service created", _s == 201, f"{_s} {r}")
    _slid = r.get("id")
    _s, r = req("POST", "/book", {"listing_id": _slid, "client": "Anna Muster", "human_verified": True,
        "slot_date": "2026-12-10", "slot_time": "14:37"}, BT)
    check("C2 misaligned slot -> 409", _s == 409, f"{_s} {r}")
    _s, r = req("POST", "/book", {"listing_id": _slid, "client": "Anna Muster", "human_verified": True,
        "slot_date": "2026-12-10", "slot_time": "14:30"}, BT)
    check("C3 aligned slot books 201", _s == 201, f"{_s} {r}")
    _bid = r.get("id")
    _ctok = r.get("cancel_token", "")
    _s, r = req("POST", "/book", {"listing_id": _slid, "client": "Bart Boss", "human_verified": True,
        "slot_date": "2026-12-10", "slot_time": "14:30"}, BT)
    check("C4 same slot -> 409 slot_taken", _s == 409 and "slot taken" in str(r), f"{_s} {r}")
    _s, r = req("POST", "/book", {"listing_id": _slid, "client": "Bart Boss", "human_verified": True,
        "slot_date": "2026-12-10", "slot_time": "15:00"}, BT)
    check("C5 different slot books", _s == 201, f"{_s} {r}")
    check("C6 booking carries slot fields", bool(_bid) and True, _bid)
    _s, det = req("GET", f"/listings/{_slid}")
    check("C7 slot grid public on listing", det.get("slot_minutes") == 30, det.get("slot_minutes"))
    _s, r = req("POST", "/book", {"listing_id": _slid, "client": "Cara", "human_verified": True}, BT)
    check("C8 missing slot fields -> appointment 400", _s == 400 and "appointment" in str(r), f"{_s} {r}")
    _s, r = req("POST", "/book", {"listing_id": _slid, "client": "Dan", "human_verified": True, "slot_date": "x"}, BT)
    check("C9 malformed slot_date 400", _s == 400, _s)
    # free listing (price 0) for cancel law: escrow stays free -> refund path
    _s, r = req("POST", "/listings", {"vertical": "services", "title": "Free Consult",
        "provider": "Pro Bono", "price": 0, "slot_minutes": 60}, LT)
    _free_id = r.get("id")
    _s, r = req("POST", "/book", {"listing_id": _free_id, "client": "Eva", "human_verified": True,
        "slot_date": "2026-12-11", "slot_time": "09:00"}, BT)
    check("C10 free slot booking works", _s == 201, f"{_s} {r}")
    _free_bid = r.get("id"); _free_ct = r.get("cancel_token", "")
    _s, r = req("POST", "/book", {"listing_id": _free_id, "client": "Finn", "human_verified": True,
        "slot_date": "2026-12-11", "slot_time": "09:00"}, BT)
    check("C11 slot taken on free too", _s == 409, _s)
    _s, r = req("POST", f"/book/{_free_bid}/cancel",
                {}, {"X-Hub-Token": _free_ct})
    check("C12 cancel accepted", _s == 200, f"{_s} {r}")
    _s, r = req("POST", "/book", {"listing_id": _free_id, "client": "Finn", "human_verified": True,
        "slot_date": "2026-12-11", "slot_time": "09:00"}, BT)
    check("C13 cancelled slot is free again", _s == 201, f"{_s} {r}")
    # spoof-strip on slot-less service
    _s, r = req("POST", "/listings", {"vertical": "services", "title": "Plain Repair",
        "provider": "Fixit", "price": 40}, LT)
    _plain = r.get("id")
    _s, r = req("POST", "/book", {"listing_id": _plain, "client": "Gil", "human_verified": True,
        "slot_date": "2026-12-12", "slot_time": "10:00"}, BT)
    check("C14 slot fields refused on slot-less", _s == 400, f"{_s} {r}")
    _s, det = req("GET", f"/listings/{_plain}")
    check("C15 no slot grid leaks", "slot_minutes" not in det, list(det))

    # ---------- D. sponsored placement ----------
    _s, r = req("POST", "/listings", dict(_ev, title="Salsa VIP Special"), LT)
    _spid = r.get("id")
    _s, r = req("POST", "/listings", dict(_ev, title="Attacker Sponsor Try",
        _sponsor={"active": True, "until_ts": 9999999999}), LT)
    check("D1 client _spoof rejected (reserved)", _s == 400, f"{_s}")
    _s, r = req("POST", "/admin/sponsor", {"listing_id": _spid, "days": 7},
                {"X-Hub-Token": "wrong-key"})
    check("D2 wrong admin key 403", _s == 403, _s)
    _s, r = req("POST", "/admin/sponsor", {"listing_id": "nope-1", "days": 7}, ADMIN)
    check("D3 unknown listing 404", _s == 404, _s)
    _s, r = req("POST", "/admin/sponsor", {"listing_id": _spid, "days": 0}, ADMIN)
    check("D4 days bounds 400", _s == 400, _s)
    _s, r = req("POST", "/admin/sponsor", {"listing_id": _spid, "days": 7}, ADMIN)
    check("D5 grant 200 with until", _s == 200 and r.get("sponsored_until"), f"{_s} {r}")
    _s, sr = req("GET", "/search?q=salsa")
    ls = sr.get("listings", [])
    check("D6 sponsored rides LAST", len(ls) >= 2 and ls[-1]["id"] == _spid,
          [(l["id"], l.get("sponsored")) for l in ls])
    check("D7 labeled sponsored=true", ls and ls[-1].get("sponsored") is True, ls[-1] if ls else None)
    check("D8 organic unlabeled", all("sponsored" not in l for l in ls[:-1]), None)
    _s, sr = req("GET", "/search?q=Weekly%20Salsa")
    check("D9 no label without grant",
          all("sponsored" not in l for l in sr.get("listings", [])), None)

    # ---------- E. enrichment provider chain ----------
    os.environ["EVERLIST_ENRICH"] = "stub"
    import importlib
    import enrich
    importlib.reload(enrich)
    blk = enrich.extract("Vegan Cooking", "plant based kitchen course", None)
    check("E1 stub still works", blk and blk["mode"] == "stub", blk)
    os.environ["EVERLIST_ENRICH"] = "live"
    os.environ["EVERLIST_ENRICH_USE_LLM_ENV"] = "1"
    os.environ["EVERLIST_NLU_API_KEY"] = "test-nlu-key"
    os.environ.pop("EVERLIST_ZAI_API_KEY", None)
    os.environ.pop("EVERLIST_ENRICH_API_KEY", None)
    cfg = enrich._cfg()
    check("E2 chain built from llm.env names", len(cfg["chain"]) == 1
          and cfg["chain"][0][1] == "test-nlu-key"
          and cfg["chain"][0][0].endswith("/chat/completions"), cfg["chain"])
    os.environ["EVERLIST_ZAI_API_KEY"] = "test-zai-key"
    cfg = enrich._cfg()
    check("E3 two providers in chain", len(cfg["chain"]) == 2, cfg["chain"])
    os.environ["EVERLIST_ENRICH_API_KEY"] = "explicit-key"
    os.environ["EVERLIST_ENRICH_URL"] = "https://explicit.example/v1/chat/completions"
    os.environ["EVERLIST_ENRICH_MODEL"] = "explicit-model"
    cfg = enrich._cfg()
    check("E4 explicit knobs take precedence", cfg["chain"][0][1] == "explicit-key"
          and cfg["chain"][0][2] == "explicit-model", cfg["chain"]) 
    os.environ.pop("EVERLIST_ENRICH_USE_LLM_ENV", None)
    os.environ["EVERLIST_ENRICH_API_KEY"] = ""
    cfg = enrich._cfg()
    check("E5 no chain -> fail-open None path", cfg["mode"] == "live" and cfg["chain"] == [], cfg)
    # E6-E9 (owner-approved 2026-11-08): chain v1.2 + draft v2 pins
    os.environ["EVERLIST_ENRICH"] = "live"
    os.environ["EVERLIST_ENRICH_USE_LLM_ENV"] = "1"
    os.environ["EVERLIST_NLU_API_KEY"] = "k-nlu"
    os.environ["EVERLIST_ZAI_API_KEY"] = "k-zai"
    os.environ["EVERLIST_OPENROUTER_API_KEY"] = "k-or"
    os.environ["EVERLIST_A0_API_KEY"] = "k-a0"
    cfg = enrich._cfg()
    check("E6 four-provider chain", len(cfg["chain"]) == 4
          and cfg["chain"][2][0].startswith("https://openrouter.ai/api/v1")
          and cfg["chain"][3][0].startswith("https://llm.agent-zero.ai/v1"),
          cfg["chain"])
    os.environ["EVERLIST_ENRICH_TIMEOUT_S"] = "0.2"
    sm = enrich.draft_from_text_smart("Yoga Event\n2026-12-24 um 10:00\nOrt: Wien")
    check("E7 dead-chain draft falls back to regex", sm["engine"] == "regex"
          and sm["draft"].get("date") == "2026-12-24", sm)
    os.environ.pop("EVERLIST_ENRICH_TIMEOUT_S", None)
    os.environ["EVERLIST_ENRICH"] = "off"
    sm = enrich.draft_from_text_smart("Konzert\n05.12.2026")
    check("E8 off-mode draft stays regex", sm["engine"] == "regex", sm)
    os.environ["EVERLIST_ENRICH"] = "live"
    # E9: mocked AI provider (ephemeral loopback server, daemon thread —
    # cleaned up at process exit) proving the llm-engine draft path end-to-end
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer
    class _MH(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.dumps({"choices": [{"message": {"content":
                '{"title":"Sommerfest im Hof","date":"2026-08-15","time":"18:00",'
                '"price":5,"location":"Hinterhof Wien","description":"Musik und Essen"}'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        def log_message(self, *a):
            pass
    _srv = HTTPServer(("127.0.0.1", 0), _MH)
    _port = _srv.server_address[1]
    threading.Thread(target=_srv.serve_forever, daemon=True).start()
    os.environ["EVERLIST_ENRICH_URL"] = f"http://127.0.0.1:{_port}/chat/completions"
    os.environ["EVERLIST_ENRICH_API_KEY"] = "mock"
    sm = enrich.draft_from_text_smart("Flyer text irgendwas")
    check("E9 llm-engine draft parses", sm["engine"] == "llm"
          and sm["draft"].get("title") == "Sommerfest im Hof"
          and sm["draft"].get("price") == 5.0
          and sm["draft"].get("time") == "18:00", sm)
    for k in ("EVERLIST_ENRICH", "EVERLIST_ENRICH_USE_LLM_ENV", "EVERLIST_NLU_API_KEY",
              "EVERLIST_ZAI_API_KEY", "EVERLIST_OPENROUTER_API_KEY", "EVERLIST_A0_API_KEY",
              "EVERLIST_ENRICH_URL", "EVERLIST_ENRICH_API_KEY"):
        os.environ.pop(k, None)

    # ---------- F. contracts ----------
    _s, oa = req("GET", "/openapi.json")
    txt = json.dumps(oa)
    check("F1 OpenAPI /admin/sponsor", "/admin/sponsor" in txt, None)
    check("F2 OpenAPI search sponsorship note", "sponsored=true" in txt, None)
    check("F3 manage acts documented", "archive_series" in txt and "delete_series" in txt, None)

    _kill(_p2kill)

    fails = [n for n, ok in RESULTS if not ok]
    print(f"\nPhase 3 marketplace: {len(RESULTS) - len(fails)} passed, {len(fails)} failed")
    if fails:
        print("FAILED:")
        for f in fails:
            print("  -", f)
        sys.exit(1)


if __name__ == "__main__":
    main()
