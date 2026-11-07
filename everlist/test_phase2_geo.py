#!/usr/bin/env python3
"""Phase 2 find-quality geo (owner GO 2026-11-07): server-side geo search.

Covers:
- near=lat,lon + radius_km= filter: only listings with valid lat/lon in range
- listings WITHOUT lat/lon excluded from geo filters (the dateless law, for space)
- honest 400s: malformed/out-of-range near, radius_km without near, non-positive
  radius_km, sort=distance without near (no silent fallbacks)
- per-result distance_km rides on response COPIES only; plain (non-geo) searches
  carry no distance_km and stay uncontaminated after geo searches
- sort=distance nearest-first, ascending distances; without sort, prior order kept
- OpenAPI contract documents the geo params (near/radius_km in /search note)
Run: ./venv/bin/python test_phase2_geo.py
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
    tmp = tempfile.mkdtemp(prefix="hub-phase2geo-")
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


def main():
    global HUB
    HUB, _p, _log = spawn()

    st, res = req("POST", "/access", {"agent": "p2-geo-owner", "acts": ["list", "book"]})
    assert st in (200, 201), str(res)
    OWN = res["tokens"]["list"]

    # inventory: three coordinate listings around Vienna center + one coord-less
    # (haversine sanity: center->B ~1.3 km, center->C ~15.8 km)
    CENTER = (48.2082, 16.3738)
    probes = [
        ("Geo Near",   {"lat": CENTER[0], "lon": CENTER[1]}),          # ~0 km
        ("Geo Mid",    {"lat": 48.22,    "lon": 16.37}),               # ~1.3 km
        ("Geo Far",    {"lat": 48.35,    "lon": 16.37}),               # ~15.8 km
        ("Geo NoCoords", {}),                                            # excluded from geo
    ]
    ids = []
    for title, geo in probes:
        body = {"vertical": "events", "title": title, "price": 10,
                "capacity": 10, "date": "2026-12-20", "location": "Vienna",
                "category": "meetup", **geo}
        st, res = req("POST", "/listings", body, headers={"X-Hub-Token": OWN})
        assert st == 201, f"{title}: {st} {str(res)[:160]}"
        ids.append(res["id"])

    near = f"near={CENTER[0]},{CENTER[1]}"

    def titles(lst):
        return sorted(l["title"] for l in lst)

    # 1) radius keeps only in-range coords listings; coord-less excluded
    st, res = req("GET", f"/search?{near}&radius_km=5")
    got = res.get("listings", [])
    check("P2 radius 5km keeps near+mid, excludes far+coordless",
          st == 200 and titles(got) == ["Geo Mid", "Geo Near"],
          f"{st} {titles(got)}")
    check("P2 radius results carry distance_km",
          all("distance_km" in l for l in got),
          str([(l.get("title"), l.get("distance_km")) for l in got]))

    # 2) huge radius keeps every coords listing, still excludes coord-less
    st, res = req("GET", f"/search?{near}&radius_km=50")
    got = res.get("listings", [])
    check("P2 radius 50km keeps all coords listings, coordless still out",
          st == 200 and titles(got) == ["Geo Far", "Geo Mid", "Geo Near"],
          f"{st} {titles(got)}")

    # 3) near WITHOUT radius: coords listings only, distance_km present
    st, res = req("GET", f"/search?{near}")
    got = res.get("listings", [])
    check("P2 bare near returns coords listings with distance_km",
          st == 200 and len(got) == 3 and all("distance_km" in l for l in got),
          f"{st} {len(got)}")

    # 4) sort=distance: nearest-first, ascending
    st, res = req("GET", f"/search?{near}&radius_km=50&sort=distance")
    got = res.get("listings", [])
    ds = [l.get("distance_km") for l in got]
    check("P2 sort=distance nearest-first ascending",
          st == 200 and [l["title"] for l in got] == ["Geo Near", "Geo Mid", "Geo Far"]
          and ds == sorted(ds) and ds[0] < 0.5 and 1.0 < ds[1] < 2.0 and 14.0 < ds[2] < 18.0,
          f"{st} {[(l['title'], l.get('distance_km')) for l in got]}")

    # 5) filters echo near/radius_km
    st, res = req("GET", f"/search?{near}&radius_km=5")
    f = res.get("filters", {})
    check("P2 filters echo near and radius_km",
          st == 200 and f.get("near") == f"{CENTER[0]},{CENTER[1]}" and f.get("radius_km") == 5,
          str(f))

    # 6) honest 400 walls
    for label, qs, errpart in [
        ("malformed near", "near=notacity", "near must be"),
        ("out-of-range near", "near=91,16", "near must be"),
        ("radius without near", "radius_km=5", "requires near"),
        ("negative radius", f"{near}&radius_km=-1", "positive"),
        ("sort=distance without near", "sort=distance", "requires near"),
    ]:
        st, res = req("GET", f"/search?{qs}")
        check(f"P2 400 {label}", st == 400 and errpart in str(res.get("error", "")),
              f"{st} {str(res)[:120]}")

    # 7) purity: plain searches carry NO distance_km, even after geo searches ran
    st, res = req("GET", "/search?vertical=events")
    got = res.get("listings", [])
    check("P2 plain search has no distance_km (projection law)",
          st == 200 and got and all("distance_km" not in l for l in got),
          str([l.get("title") for l in got if "distance_km" in l]))

    # 8) other explicit sorts unaffected by geo params when no near given
    st, res = req("GET", "/search?vertical=events&sort=price")
    prices = [float(l.get("price", 0)) for l in res.get("listings", [])]
    check("P2 price sort intact", st == 200 and prices == sorted(prices), f"{prices}")

    # 9) geo filter + q-term compose (term matches all Geo probes)
    st, res = req("GET", f"/search?q=geo&{near}&radius_km=5")
    check("P2 q+geo compose",
          st == 200 and titles(res.get("listings", [])) == ["Geo Mid", "Geo Near"],
          f"{st} {titles(res.get('listings', []))}")

    # 10) OpenAPI contract documents geo params
    st, res = req("GET", "/openapi.json")
    note = str(res.get("paths", {}).get("/search", {}).get("get", {}))
    check("P2 openapi documents near/radius_km/sort=distance",
          st == 200 and "near" in note and "radius_km" in note and "distance" in note,
          note[:160])

    failed = [n for n, ok in RESULTS if not ok]
    print(f"\nPhase 2 geo: {len(RESULTS) - len(failed)} passed, {len(failed)} failed")
    if failed:
        print("FAILED:")
        for n in failed:
            print(f"  - {n}")
        sys.exit(1)


if __name__ == "__main__":
    main()
