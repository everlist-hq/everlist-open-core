#!/usr/bin/env python3
"""CATALOGS system (owner GO 2026-11-12, spec-partner-catalogs v2.1, P1-P3).
Covers: merchant registry (ownership, slug/cap walls, public read), merchant
attach on listings (owner walls, manage attach/detach), versioned catalogs
(content_hash, no-change 409, since_hash 304, tree validation), feed quota
(P1: max 2 per merchant, explicit merchant browse uncapped), two-answer
search (catalog_items grouped, ZERO leakage into listing results), merchant
SSR page (menu + offers, honest 404).
Run: ./venv/bin/python test_catalogs.py
"""
import atexit, json, os, socket, subprocess, sys, tempfile, time
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

def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False

_PROCS = []
atexit.register(lambda: [p.terminate() for p in _PROCS])

def spawn(env_extra=None):
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="hub-cat-")
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(tmp, "state.json"),
           "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1",
           "HUB_MERCHANT_FEED_QUOTA": "2", "HUB_MERCHANT_CAP": "2"}
    env.update(env_extra or {})
    logf = open(os.path.join(tmp, "hub.log"), "w")
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _PROCS.append(p)
    assert wait_ready(port), "hub did not start"
    return f"http://127.0.0.1:{port}", p, logf

def req(method, path, body=None, headers=None, base=""):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        r.add_header(k, v)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}

def _spawn_state(state_file):
    """HRD: spawn a hub bound to an EXISTING state file (persistence respawn)."""
    port = free_port()
    env = {**os.environ, "HUB_STATE_FILE": state_file,
           "HUB_POW_SIGNUP_BITS": "8", "PYTHONUNBUFFERED": "1"}
    logf = tempfile.TemporaryFile()
    p = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _PROCS.append(p)
    assert wait_ready(port), "hub (state-file spawn) did not start"
    return p, f"http://127.0.0.1:{port}"


def main():
    HUB, p, logf = spawn()
    _, a1 = req("POST", "/access", {"agent": "cat-owner", "acts": ["list", "book"]}, base=HUB)
    OWN = a1["tokens"]["list"]
    _, a2 = req("POST", "/access", {"agent": "cat-other", "acts": ["list", "book"]}, base=HUB)
    OTHER = a2["tokens"]["list"]
    O = {"X-Hub-Token": OWN}
    X = {"X-Hub-Token": OTHER}

    # --- merchant registry
    st, r = req("POST", "/merchants", {"slug": "Pizzeria Nostra!", "name": "x"}, headers=O, base=HUB)
    check("C1 slug wall rejects bad slug", st == 400, f"{st}")
    st, r = req("POST", "/merchants", {"slug": "pizzeria-nostra", "name": "Pizzeria Nostra",
        "description": "Neapolitan pizza, Vienna",
        "locations": [{"city": "Vienna", "address": "Naschmarkt 5"}],
        "fulfillment": ["pickup", "delivery"],
        "promos": [{"label": "-10% first order", "detail": "code ERSTI"}]}, headers=O, base=HUB)
    check("C1 merchant created", st == 201 and r.get("merchant", {}).get("slug") == "pizzeria-nostra",
          f"{st} {str(r)[:120]}")
    st, r = req("POST", "/merchants", {"slug": "pizzeria-nostra", "name": "Dup"}, headers=X, base=HUB)
    check("C1 duplicate slug 409", st == 409, f"{st}")
    st, r = req("POST", "/merchants", {"slug": "second-owner", "name": "Two"}, headers=X, base=HUB)
    check("C1 second owner merchant ok", st == 201, f"{st}")
    st, r = req("POST", "/merchants", {"slug": "third-one", "name": "Three"}, headers=X, base=HUB)
    check("C1 second merchant within cap 201", st == 201, f"{st} {str(r)[:100]}")
    st, r = req("POST", "/merchants", {"slug": "fourth-one", "name": "Four"}, headers=X, base=HUB)
    check("C1 merchant cap (2/owner) 409", st == 409, f"{st} {str(r)[:100]}")
    st, r = req("POST", "/merchants", {"name": "NoToken"}, base=HUB)
    check("C1 merchant create needs token", st == 401, f"{st}")

    # --- attach walls on listing create
    TREE = {"name": "Menu", "children": [
        {"name": "Pizze", "items": [
            {"title": "Margherita", "price": 8.9, "tags": ["vegetarian"]},
            {"title": "Salami Pizza", "price": 10.5, "tags": ["pork"]},
            {"title": "Diavola", "price": 11.0}]},
        {"name": "Drinks", "items": [{"title": "Spezi 0.5l", "price": 3.2}]}]}
    st, r = req("POST", "/listings", {"vertical": "food", "title": "Pizza Night Pop-Up",
        "date": "2026-11-20", "time": "18:00", "location": "Vienna", "price": 0,
        "capacity": 20, "category": "other", "merchant": "nope-unknown"}, headers=O, base=HUB)
    check("C1 unknown merchant attach 400", st == 400, f"{st} {str(r)[:100]}")
    ids = []
    for d in ("2026-11-20", "2026-11-27", "2026-12-04"):
        st, r = req("POST", "/listings", {"vertical": "food", "title": f"Pizza Night {d}",
            "date": d, "time": "18:00", "location": "Vienna", "price": 0,
            "capacity": 20, "category": "other", "merchant": "pizzeria-nostra"}, headers=O, base=HUB)
        ids.append(r.get("id", ""))
    check("C1 3 listings attached to merchant", all(i.startswith("food-") for i in ids), str(ids))
    st, r = req("POST", "/listings", {"vertical": "food", "title": "Hijack attempt",
        "date": "2026-11-21", "location": "Vienna", "price": 0, "capacity": 5,
        "merchant": "pizzeria-nostra"}, headers=X, base=HUB)
    check("C1 foreign merchant attach 403", st == 403, f"{st}")

    # --- manage attach/detach
    _, a3 = req("POST", "/access", {"agent": "cat-other2", "acts": ["list"]}, base=HUB)
    st, r = req("POST", "/listings", {"vertical": "food", "title": "Detach Probe",
        "date": "2026-11-21", "time": "18:00", "location": "Vienna", "price": 0,
        "capacity": 5, "category": "other"}, headers=X, base=HUB)
    dprobe = r.get("id")
    mgrc = r.get("manage_code", "")
    # manage ops authenticate with the one-time manage_code (or owning-account
    # login) - a plain /access token is NOT a manage credential (H-law).
    st, r = req("POST", f"/listings/{dprobe}/manage", {"action": "attach_merchant", "merchant": "pizzeria-nostra",
                "manage_code": mgrc}, headers=X, base=HUB)
    check("C1 attach foreign merchant via manage 403", st == 403, f"{st} {str(r)[:100]}")
    st, r = req("POST", f"/listings/{dprobe}/manage", {"action": "attach_merchant", "merchant": "second-owner",
                "manage_code": mgrc}, headers=X, base=HUB)
    check("C1 attach own merchant via manage 200", st == 200 and r.get("merchant") == "second-owner", f"{st} {str(r)[:100]}")
    st, r = req("POST", f"/listings/{dprobe}/manage", {"action": "detach_merchant", "manage_code": mgrc},
                headers=X, base=HUB)
    check("C1 detach via manage 200", st == 200 and r.get("merchant") is None, f"{st}")

    # --- catalogs versioning
    st, r = req("POST", "/catalogs", {"merchant": "second-owner", "tree": TREE}, headers=O, base=HUB)
    check("C2 catalog for foreign merchant 403", st == 403, f"{st}")
    st, r = req("POST", "/catalogs", {"merchant": "pizzeria-nostra", "tree": {"items": [{"no": "title"}]}}, headers=O, base=HUB)
    check("C2 tree validation: item needs title", st == 400, f"{st}")
    st, r = req("POST", "/catalogs", {"merchant": "pizzeria-nostra", "tree": TREE}, headers=O, base=HUB)
    cid = r.get("id", "")
    H1 = r.get("content_hash", "")
    check("C2 catalog v1 created", st == 201 and cid.startswith("cat-") and len(H1) == 64, f"{st} {str(r)[:120]}")
    st, r = req("POST", "/catalogs", {"merchant": "pizzeria-nostra", "tree": TREE}, headers=O, base=HUB)
    check("C2 second catalog same merchant 409", st == 409, f"{st}")
    st, r = req("POST", f"/catalogs/{cid}/replace", {"tree": TREE}, headers=O, base=HUB)
    check("C2 no-change replace 409", st == 409, f"{st}")
    TREE2 = json.loads(json.dumps(TREE)); TREE2["children"][0]["items"][0]["price"] = 9.5
    st, r = req("POST", f"/catalogs/{cid}/replace", {"tree": TREE2}, headers=O, base=HUB)
    check("C2 changed replace -> v2", st == 200 and r.get("version") == 2 and r.get("content_hash") != H1,
          f"{st} {str(r)[:120]}")
    st, r = req("GET", f"/catalogs/{cid}?since_hash={r.get('content_hash')}", base=HUB)
    check("C2 since_hash match -> 304", st == 304, f"{st}")
    st, r = req("GET", f"/catalogs/{cid}?fields=summary", base=HUB)
    check("C2 summary omits tree", st == 200 and "tree" not in r and r.get("version") == 2, str(r)[:120])

    # --- merchant public read + feed quota
    st, r = req("GET", "/merchants/pizzeria-nostra", base=HUB)
    m = r.get("merchant", {})
    check("C1 merchant public read", st == 200 and m.get("name") == "Pizzeria Nostra"
          and len(r.get("listings", [])) == 3, f"{st} listings={len(r.get('listings', []))}")
    check("C1 merchant read carries catalog", (r.get("catalog") or {}).get("id") == cid
          and (r.get("catalog") or {}).get("version") == 2, str((r.get("catalog") or {}))[:100])
    st, r = req("GET", "/listings", base=HUB)
    lst = r.get("listings", [])
    mn = [l for l in lst if l.get("merchant") == "pizzeria-nostra"]
    qn = r.get("merchant_quota", {})
    check("P1 feed quota caps at 2", len(mn) == 2 and qn.get("max_per_merchant") == 2,
          f"merchant listings in feed: {len(mn)} quota={qn}")
    st, r = req("GET", "/listings?merchant=pizzeria-nostra", base=HUB)
    check("P1 explicit merchant browse uncapped", len(r.get("listings", [])) == 3, str(len(r.get("listings", []))))

    # --- two-answer search: items ride alongside, never leak into listings
    st, r = req("GET", "/search?q=salami", base=HUB)
    ci = r.get("filters", {}).get("catalog_items") if isinstance(r.get("filters"), dict) else None
    ci = ci if ci is not None else r.get("catalog_items", [])
    check("P3 catalog_items grouped by merchant", len(ci) >= 1
          and ci[0].get("merchant") == "pizzeria-nostra" and "Pizza" in ci[0].get("title", ""),
          str(ci)[:160])
    check("P3 leakage guard: no catalog item in listing hits",
          all("Salami Pizza" not in str(l.get("title")) for l in r.get("results", r.get("listings", []))),
          "")

    # --- merchant SSR page (direct projection over spawned hub)
    import pages
    html = pages.merchant_html("pizzeria-nostra", hub=HUB)
    check("P1 merchant SSR page renders", html is not None and "Pizzeria Nostra" in html
          and "Salami Pizza" in html and "Pizza Night" in html, "")
    check("P1 unknown merchant SSR honest 404", pages.merchant_html("no-such-merchant", hub=HUB) is None, "")
    w = open(os.path.join(HERE, "webchat.py")).read()
    check("P1 webchat /m/ route wired", 'rest.startswith("/m/")' in w and "merchant_html" in w, "")

    # ---- HRD: hardening pass pins (quality mandate 2026-11-13) ----
    # HRD-A honest public collections (H5)
    st, r = req("GET", "/merchants", base=HUB)
    check("HRD-A1 GET /merchants collection 200", st == 200 and r.get("count", 0) >= 2
          and any(m.get("slug") == "pizzeria-nostra" for m in r.get("merchants", [])),
          f"{st} {str(r)[:120]}")
    st, r = req("GET", "/catalogs", base=HUB)
    check("HRD-A2 GET /catalogs collection 200", st == 200 and r.get("count", 0) >= 1
          and any(c.get("id") == cid for c in r.get("catalogs", [])), f"{st} {str(r)[:120]}")
    # HRD-B prefix tighten (H4): /catalogsXYZ must not ride the catalogs branch
    st, r = req("GET", "/catalogsXYZ", base=HUB)
    check("HRD-B1 /catalogsXYZ no longer matches branch", st == 404, f"{st}")
    # HRD-C raw bodiless 304 (H1, RFC 9110): no body bytes on the wire
    import http.client as _hc
    import urllib.parse as _up
    st, r = req("GET", f"/catalogs/{cid}", base=HUB)
    _h2v = r.get("content_hash", "")
    _u = _up.urlparse(HUB)
    _conn = _hc.HTTPConnection(_u.hostname, _u.port, timeout=8)
    _conn.request("GET", f"/catalogs/{cid}?since_hash={_h2v}")
    _resp = _conn.getresponse()
    _body = _resp.read()
    check("HRD-C1 304 is bodiless on the wire", _resp.status == 304 and _body == b"",
          f"status={_resp.status} body={len(_body)}B")
    _conn.close()
    # HRD-D merchant lifecycle (H3): update arm + guarded delete
    st, r = req("POST", "/merchants/pizzeria-nostra", {"description": "Forno a legna since today"},
                headers=O, base=HUB)
    check("HRD-D1 update without action -> 400", st == 400, f"{st}")
    st, r = req("POST", "/merchants/pizzeria-nostra", {"action": "update", "name": "Pizzeria Nostra SI"},
                headers=X, base=HUB)
    check("HRD-D2 foreign update -> 403", st == 403, f"{st}")
    st, r = req("POST", "/merchants/pizzeria-nostra", {"action": "update", "description": "Forno a legna, Napoli rules"},
                headers=O, base=HUB)
    check("HRD-D3 owner update -> 200", st == 200 and "Napoli" in r.get("merchant", {}).get("description", ""),
          f"{st} {str(r)[:120]}")
    st, r = req("POST", "/merchants/pizzeria-nostra", {"action": "delete"}, headers=O, base=HUB)
    check("HRD-D4 delete with attached actives -> 409", st == 409 and "attached" in r.get("error", ""),
          f"{st} {str(r)[:120]}")
    st, r = req("POST", "/merchants/second-owner", {"action": "delete"}, headers=X, base=HUB)
    check("HRD-D5 delete unattached merchant -> 200", st == 200, f"{st} {str(r)[:120]}")
    st, r = req("GET", "/merchants/second-owner", base=HUB)
    check("HRD-D6 deleted merchant -> honest 404", st == 404, f"{st}")
    # HRD-E merchant SEO (H6): JSON-LD + sitemap pairs, public fields only
    html = pages.merchant_html("pizzeria-nostra", hub=HUB)
    check("HRD-E1 merchant page carries LocalBusiness JSON-LD",
          html is not None and '"LocalBusiness"' in html, "")
    sx = pages.sitemap_xml(hub=HUB).decode()
    check("HRD-E2 sitemap carries /m/ EN+DE pair",
          "/m/pizzeria-nostra" in sx and "/de/m/pizzeria-nostra" in sx, "")
    # HRD-F static dead-code pins (H2) + write backstop presence (H7)
    app_src = open(os.path.join(HERE, "app.py"), encoding="utf-8").read()
    check("HRD-F1 no dead no-op lines left", "u.method if False" not in app_src, "")
    check("HRD-F2 no dead stack var in _cat_walk", "stack = [(([], tree),)]" not in app_src, "")
    check("HRD-F3 catalog writes backstopped", "catalog write rate limit reached" in app_src, "")
    # HRD-G persistence respawn (state round-trip, previously unproven)
    sf = os.path.join(tempfile.mkdtemp(prefix="hub-cat-persist-"), "state.json")
    p1, B1 = _spawn_state(sf)
    _, ap = req("POST", "/access", {"agent": "persist-probe", "acts": ["list"]}, base=B1)
    PT = ap["tokens"]["list"]
    st, r = req("POST", "/merchants", {"slug": "persist-check", "name": "Persist Check"},
                headers={"X-Hub-Token": PT}, base=B1)
    check("HRD-G1 merchant created on hub-A", st == 201, f"{st}")
    p1.terminate(); p1.wait(timeout=10)
    p2, B2 = _spawn_state(sf)
    st, r = req("GET", "/merchants/persist-check", base=B2)
    check("HRD-G2 merchant survives respawn", st == 200, f"{st}")
    # re-mint for the SAME agent name on the respawned hub: principal identity
    # is the agent name, so ownership holds whichever way signing keys persist
    _, ap2 = req("POST", "/access", {"agent": "persist-probe", "acts": ["list"]}, base=B2)
    PT2 = ap2["tokens"]["list"]
    st, r = req("POST", "/merchants/persist-check", {"action": "delete"},
                headers={"X-Hub-Token": PT2}, base=B2)
    check("HRD-G3 delete on respawned hub -> 200", st == 200, f"{st} {str(r)[:120]}")
    p2.terminate(); p2.wait(timeout=10)
    p3, B3 = _spawn_state(sf)
    st, r = req("GET", "/merchants/persist-check", base=B3)
    check("HRD-G4 delete survives respawn", st == 404, f"{st}")
    p3.terminate(); p3.wait(timeout=10)

    fails = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} PASS")
    if fails:
        print("FAILURES:", fails)
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
