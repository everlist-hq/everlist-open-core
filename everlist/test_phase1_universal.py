#!/usr/bin/env python3
"""Phase 1 universal listings (owner GO 2026-11-07): breadth is DATA.

Covers:
- five new community verticals load (C5 drop-in loader), prefixes rid-/rnt-/exp-/chc-/pet-,
  appear in /verticals, built-ins intact, vocab walls enforced, booking lifecycle per vertical
- route law: /search?location= matches rides from_location OR to_location
- bm25 law: sqlite-mode /search?q= relevance order without explicit sort; explicit sort overrides
Run: ./venv/bin/python test_phase1_universal.py
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
    tmp = tempfile.mkdtemp(prefix="hub-phase1-")
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


SCHEMAS = {
    "rides.json": {
        "name": "rides",
        "required": ["title", "price", "capacity", "date", "location"],
        "optional": ["description", "category", "tags", "url", "from_location", "to_location", "time"],
        "categories": ["carpool", "long-distance", "airport", "daily-commute", "event-return", "other"],
        "tracks_capacity": True,
        "field_types": {"capacity": "positive_int", "date": "nonempty",
                        "from_location": "nonempty", "to_location": "nonempty"},
        "booking": {"required": ["passenger"], "fields": ["passenger", "pickup", "quantity"],
                     "identity": "passenger", "action": "reserve+pay"}},
    "rentals.json": {
        "name": "rentals",
        "required": ["title", "price", "capacity", "date", "location"],
        "optional": ["description", "category", "tags", "url", "end_date", "deposit_info"],
        "categories": ["tools", "electronics", "outdoor", "vehicle", "space", "parking", "other"],
        "tracks_capacity": True,
        "field_types": {"capacity": "positive_int", "date": "nonempty", "end_date": "nonempty"},
        "booking": {"required": ["renter"], "fields": ["renter", "quantity", "notes"],
                     "identity": "renter", "action": "rent+pay"}},
    "experiences.json": {
        "name": "experiences",
        "required": ["title", "price", "capacity", "date", "location"],
        "optional": ["description", "category", "tags", "url", "time", "meeting_point",
                     "duration_minutes", "languages"],
        "categories": ["tour", "outdoor", "culture", "food-drink", "adventure", "citywalk", "other"],
        "tracks_capacity": True,
        "field_types": {"capacity": "positive_int", "date": "nonempty", "duration_minutes": "positive_int"},
        "booking": {"required": ["attendee"], "fields": ["attendee", "quantity"],
                     "identity": "attendee", "action": "register+pay"}},
    "childcare.json": {
        "name": "childcare",
        "required": ["title", "price", "capacity", "date", "location"],
        "optional": ["description", "category", "tags", "url", "time", "age_range", "duration_minutes"],
        "categories": ["babysitting", "daycare", "after-school", "other"],
        "tracks_capacity": True,
        "field_types": {"capacity": "positive_int", "date": "nonempty", "age_range": "nonempty",
                        "duration_minutes": "positive_int"},
        "booking": {"required": ["guardian"], "fields": ["guardian", "notes", "quantity"],
                     "identity": "guardian", "action": "book+pay"}},
    "petsitting.json": {
        "name": "petsitting",
        "required": ["title", "price", "capacity", "date", "location"],
        "optional": ["description", "category", "tags", "url", "time", "pet_types", "duration_minutes"],
        "categories": ["dog-walking", "cat-visits", "boarding", "grooming", "other"],
        "tracks_capacity": True,
        "field_types": {"capacity": "positive_int", "date": "nonempty", "pet_types": "nonempty",
                        "duration_minutes": "positive_int"},
        "booking": {"required": ["pet_owner"], "fields": ["pet_owner", "notes", "quantity"],
                     "identity": "pet_owner", "action": "book+pay"}},
}
PREFIX = {"rides": "ride-", "rentals": "rent-", "experiences": "expe-",
          "childcare": "chil-", "petsitting": "pets-"}


def spawn_with_schemas(env_extra=None):
    """Spawn an isolated hub whose schemas dir contains ONLY the five new files."""
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="hub-phase1-")
    sdir = os.path.join(tmp, "schemas")
    os.makedirs(sdir)
    for fname, schema in SCHEMAS.items():
        with open(os.path.join(sdir, fname), "w") as fh:
            json.dump(schema, fh)
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(tmp, "state.json"),
           "HUB_POW_SIGNUP_BITS": "8", "HUB_SCHEMAS_DIR": sdir, "PYTHONUNBUFFERED": "1"}
    env.update(env_extra or {})
    logf = open(os.path.join(tmp, "hub.log"), "w")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), "hub did not start"
    return f"http://127.0.0.1:{port}", p, logf


def main():
    global HUB
    HUB, _p, _log = spawn_with_schemas()

    st, vert = req("GET", "/verticals")
    vs = vert.get("verticals", {})
    check("P1 hub boots with five new schema files", st == 200 and
          all(v in vs for v in PREFIX), sorted(vs.keys()))
    check("P1 built-ins intact", all(v in vs for v in ("events", "food", "services")),
          sorted(vs.keys()))

    st, res = req("POST", "/access", {"agent": "p1-owner", "acts": ["list", "book"]})
    assert st in (200, 201), str(res)
    OWN = res["tokens"]["list"]
    BOOK = res["tokens"]["book"]

    created = {}
    for v, pref in PREFIX.items():
        body = {"vertical": v, "title": f"Phase1 {v} probe", "price": 25,
                "capacity": 3, "date": "2026-12-20", "location": "Vienna",
                "category": [c for c in vs[v]["categories"] if c != "other"][0]}
        if v == "rides":
            body.update({"from_location": "Vienna", "to_location": "Graz"})
        if v == "rentals":
            body.update({"end_date": "2026-12-24", "deposit_info": "50 deposit via terms"})
        if v == "experiences":
            body.update({"duration_minutes": 90, "meeting_point": "main station"})
        if v == "childcare":
            body.update({"age_range": "3-6", "duration_minutes": 120})
        if v == "petsitting":
            body.update({"pet_types": "dog+cat", "duration_minutes": 45})
        st, res = req("POST", "/listings", body, headers={"X-Hub-Token": OWN})
        ok = st == 201 and res.get("id", "").startswith(pref)
        check(f"P1 {v} listing created ({pref} prefix)", ok, f"{st} {str(res)[:140]}")
        if ok:
            created[v] = res["id"]

    # vocabulary walls still enforced per vertical
    st, res = req("POST", "/listings", {"vertical": "rides", "title": "Bad Cat", "price": 5,
                                        "capacity": 1, "date": "2026-12-21", "location": "x",
                                        "from_location": "a", "to_location": "b",
                                        "category": "quantum"}, headers={"X-Hub-Token": OWN})
    check("P1 rides category vocab enforced (400)", st == 400, f"{st} {str(res)[:120]}")

    st, res = req("POST", "/listings", {"vertical": "petsitting", "title": "Bad Pets",
                                        "price": 5, "capacity": 1, "date": "2026-12-21",
                                        "location": "x", "pet_types": ""},
                  headers={"X-Hub-Token": OWN})
    check("P1 petsitting pet_types nonempty enforced (400)", st == 400, f"{st} {str(res)[:120]}")

    # booking lifecycle across all new verticals (identity fields differ by schema)
    BIDENT = {"rides": "passenger", "rentals": "renter", "experiences": "attendee",
              "childcare": "guardian", "petsitting": "pet_owner"}
    for v, ident in BIDENT.items():
        st, res = req("POST", "/book", {"listing_id": created[v], ident: "Test Person",
                                        "quantity": 1, "human_verified": True},
                      headers={"X-Hub-Token": BOOK})
        check(f"P1 {v} booking works (HELD)",
              st == 201 and res.get("escrow") == "HELD", f"{st} {str(res)[:140]}")

    st, lst = req("GET", "/listings/" + created["rides"])
    check("P1 rides seats tracked (registered=1)",
          st == 200 and lst.get("registered") == 1, str(lst.get("registered")))

    # ---- route law: /search?location= matches from_location OR to_location
    _p.terminate()
    HUB2, _p2, _log2 = spawn_with_schemas()
    HUB = HUB2
    st, res = req("POST", "/access", {"agent": "p1-owner2", "acts": ["list"]})
    OWN2 = res["tokens"]["list"]
    st, res = req("POST", "/listings", {"vertical": "rides", "title": "Vienna to Graz shuttle",
                                        "price": 18, "capacity": 3, "date": "2026-12-22",
                                        "location": "Vienna", "from_location": "Vienna",
                                        "to_location": "Graz", "category": "long-distance"},
                  headers={"X-Hub-Token": OWN2})
    assert st == 201, str(res)
    RID = res["id"]
    for q, label in (("graz", "to_location"), ("vienna", "from_location")):
        st, res = req("GET", f"/search?vertical=rides&location={q}")
        ids = [l["id"] for l in res.get("listings", [])]
        check(f"P1 route law: location={q} matches {label}", RID in ids, str(ids))
    st, res = req("GET", "/search?vertical=rides&location=linz")
    ids = [l["id"] for l in res.get("listings", [])]
    check("P1 route law: unrelated city stays empty", not ids, str(ids))

    # ---- bm25 law: relevance order without explicit sort (sqlite mode)
    # Design: ONE query term ('salsa'), three matching docs. The high-frequency
    # doc is inserted LAST — if relevance ordering is active it must rank first
    # (proving order is not insertion order). Explicit price sort overrides.
    HUB3, _p3, _log3 = spawn_with_schemas({"HUB_STORAGE_MODE": "sqlite"})
    HUB = HUB3
    st, res = req("POST", "/access", {"agent": "p1-owner3", "acts": ["list"]})
    OWN3 = res["tokens"]["list"]
    trip = [("Salsa Party", "a relaxed evening party", 10),
            ("Salsa Evening", "dancing until late", 11),
            ("Salsa Workshop Night", "salsa salsa salsa workshop for everyone", 12)]
    ids = []
    for t, desc, price in trip:
        st, res = req("POST", "/listings", {"vertical": "experiences", "title": t,
                                            "description": desc, "price": price,
                                            "capacity": 5, "date": "2026-12-%d" % (len(ids) + 21),
                                            "location": "Vienna", "category": "culture",
                                            "duration_minutes": 60},
                      headers={"X-Hub-Token": OWN3})
        assert st == 201, str(res)
        ids.append(res["id"])
    time.sleep(0.5)  # derived index settles
    st, res = req("GET", "/search?q=salsa")
    order = [l["id"] for l in res.get("listings", [])]
    check("P1 bm25: all three match one term", len(order) == 3, str(order))
    check("P1 bm25: high-frequency listing ranks first (not insertion order)",
          order and order[0] == ids[2] and order != ids, str(order))
    st, res = req("GET", "/search?q=salsa&sort=price")
    check("P1 explicit sort still overrides relevance",
          [l["id"] for l in res.get("listings", [])] == ids,
          str([l["id"] for l in res.get("listings", [])]))

    print()
    bad = [n for n, ok in RESULTS if not ok]
    print(f"phase1 universal: {len(RESULTS) - len(bad)} passed, {len(bad)} failed")
    if bad:
        print("FAILED:")
        for n in bad:
            print("  -", n)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
