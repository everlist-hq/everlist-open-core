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

    fails = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} PASS")
    if fails:
        print("FAILURES:", fails)
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
