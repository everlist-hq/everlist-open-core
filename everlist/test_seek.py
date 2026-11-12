#!/usr/bin/env python3
"""SEEK system (owner GO 2026-11-12, spec-seek-listings-2026-11-12.md).
Covers: role wall + pay alias, free joins (WAIVED), vetted applications
(no money, no capacity block), verified-worker Tier-2 fail-closed wall,
accept -> booking via shared _book_core with money_direction=seeker_to_filler,
auto-decline on slot fill, withdraw, role immutability via manage,
SSR WANTED card face, chat need-command wiring (static).
Run: ./venv/bin/python test_seek.py
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

def spawn():
    port = free_port()
    tmp = tempfile.mkdtemp(prefix="hub-seek-")
    sdir = os.path.join(tmp, "schemas"); os.makedirs(sdir)
    for fn in ("sports.json", "volunteers.json"):
        with open(os.path.join(HERE, "schemas", fn)) as fh:
            json.dump(json.load(fh), open(os.path.join(sdir, fn), "w"))
    env = {**os.environ, "HUB_STATE_FILE": os.path.join(tmp, "state.json"),
           "HUB_POW_SIGNUP_BITS": "8", "HUB_SCHEMAS_DIR": sdir, "PYTHONUNBUFFERED": "1"}
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
    global HUB
    HUB, p, logf = spawn()
    st, vert = req("GET", "/verticals", base=HUB)
    vs = vert.get("verticals", {})
    check("S1 sports+volunteers schemas load", st == 200 and "sports" in vs and "volunteers" in vs, sorted(vs))

    _, acc = req("POST", "/access", {"agent": "seek-owner", "acts": ["list", "book"]}, base=HUB)
    OWN, OWNBOOK = acc["tokens"]["list"], acc["tokens"]["book"]
    _, acc2 = req("POST", "/access", {"agent": "seek-joiner", "acts": ["book", "list"]}, base=HUB)
    J1 = acc2["tokens"]["book"]
    _, acc3 = req("POST", "/access", {"agent": "seek-joiner2", "acts": ["book", "list"]}, base=HUB)
    J2 = acc3["tokens"]["book"]

    # free join seek (sports)
    st, res = req("POST", "/listings", {"vertical": "sports", "role": "seek", "title": "4th volleyball player",
        "date": "2026-12-01", "location": "Vienna", "price": 0, "capacity": 4, "category": "team-mate",
        "application_mode": "join"}, headers={"X-Hub-Token": OWN}, base=HUB)
    sid = res.get("id", "")
    own_mgrs = {}; own_mgrs[sid] = res.get("manage_code", "")
    stg, resg = req("GET", f"/listings/{sid}", base=HUB)
    check("S1 seek created", st == 201 and sid.startswith("spor-") and resg.get("role") == "seek", f"{st} {str(resg)[:120]}")

    # pay alias
    st, res = req("POST", "/listings", {"vertical": "volunteers", "role": "seek", "title": "Cleanup crew",
        "date": "2026-12-02", "location": "Vienna", "pay": 0, "capacity": 5, "category": "cleanup"},
        headers={"X-Hub-Token": OWN}, base=HUB)
    stg2, resg2 = req("GET", f"/listings/{res.get('id')}", base=HUB)
    check("S1 pay alias satisfies price", st == 201 and resg2.get("price") == 0 and resg2.get("role") == "seek", f"{st} {str(resg2)[:120]}")
    st, res = req("POST", "/listings", {"vertical": "sports", "pay": 10, "title": "x", "date": "d", "location": "l",
        "capacity": 1}, headers={"X-Hub-Token": OWN}, base=HUB)
    check("S1 pay refused on offer", st == 400, f"{st}")
    st, res = req("POST", "/listings", {"vertical": "sports", "role": "seek", "pay": 10, "price": 10, "title": "x",
        "date": "d", "location": "l", "capacity": 1}, headers={"X-Hub-Token": OWN}, base=HUB)
    check("S1 pay+price double-set refused", st == 400, f"{st}")

    # free join booking
    st, res = req("POST", "/book", {"listing_id": sid, "player": "Ana", "quantity": 1, "human_verified": True},
        headers={"X-Hub-Token": J1}, base=HUB)
    check("S1 join booking WAIVED", st == 201 and res.get("escrow") == "WAIVED", f"{st} {str(res)[:120]}")
    st, res = req("GET", f"/listings/{sid}", base=HUB)
    check("S1 registered count", res.get("registered") == 1, str(res.get("registered")))

    # SSR WANTED card face (direct pages pin)
    import pages
    card = pages._card_html(dict(res))
    check("S1 WANTED chip", "seekchip" in card and "Wanted" in card, card[:160])
    check("S1 join progress N/M", "1 / 4" in card and "joined" in card, card[-160:])

    # vetted seek with verified wall
    st, res = req("POST", "/listings", {"vertical": "sports", "role": "seek", "title": "Training partner",
        "date": "2026-12-03", "location": "Vienna", "price": 0, "capacity": 1, "category": "training-partner",
        "application_mode": "vetted", "require_verified_worker": True}, headers={"X-Hub-Token": OWN}, base=HUB)
    vid = res.get("id", "")
    check("S2 vetted seek created", st == 201 and vid.startswith("spor-"), f"{st} {str(res)[:120]}")
    st, res = req("POST", "/book", {"listing_id": vid, "player": "Bob", "human_verified": True},
        headers={"X-Hub-Token": J1}, base=HUB)
    check("S2 verified-worker wall fail-closed", st == 403 and not res.get("verified", True), f"{st} {str(res)[:120]}")
    st, res = req("POST", "/book", {"listing_id": vid, "player": "Bob", "human_verified": True},
        headers={"X-Hub-Token": J1}, base=HUB)
    # same applicant on non-walled vetted seek below; wall seek stays closed (email-code NEVER law pinned above)

    # vetted seek WITHOUT wall: applications
    st, res = req("POST", "/listings", {"vertical": "sports", "role": "seek", "title": "Kitchen help",
        "date": "2026-12-04", "location": "Vienna", "price": 0, "capacity": 1, "category": "other",
        "application_mode": "vetted"}, headers={"X-Hub-Token": OWN}, base=HUB)
    kid = res.get("id", ""); own_mgrs[kid] = res.get("manage_code", "")
    st, res = req("POST", "/book", {"listing_id": kid, "player": "Bob", "human_verified": True},
        headers={"X-Hub-Token": J1}, base=HUB)
    aid1 = res.get("application_id", "")
    check("S2 book on vetted = application not booking", st == 201 and aid1.startswith("app-") and "bid" not in res,
        f"{st} {str(res)[:140]}")
    st, res = req("POST", "/book", {"listing_id": kid, "player": "Bob2", "human_verified": True},
        headers={"X-Hub-Token": J1}, base=HUB)
    check("S2 duplicate pending refused", st == 409, f"{st}")
    st, res = req("POST", "/book", {"listing_id": kid, "player": "Cara", "human_verified": True},
        headers={"X-Hub-Token": J2}, base=HUB)
    aid2 = res.get("application_id", "")
    check("S2 pending never blocks capacity", st == 201 and aid2.startswith("app-"), f"{st} {str(res)[:120]}")

    # owner lists applications - identity privacy
    MGR = own_mgrs[kid]
    st, res = req("POST", f"/listings/{kid}/applications", {"action": "list", "manage_code": MGR}, headers={"X-Hub-Token": OWN}, base=HUB)
    apps = res.get("applications", [])
    check("S2 owner sees 2 applications", st == 200 and len(apps) == 2, f"{st} {str(res)[:120]}")
    check("S2 filler identity truncated", all(len(a["filler_ref"]) <= 6 for a in apps), str(apps)[:120])

    # accept first -> booking with direction flip; second auto-declined
    st, res = req("POST", f"/listings/{kid}/applications", {"action": "accept", "application_id": aid1, "manage_code": MGR},
        headers={"X-Hub-Token": OWN}, base=HUB)
    bid = res.get("booking_id", "")
    check("S2 accept creates booking", st == 201 and bid.startswith("bk-"), f"{st} {str(res)[:140]}")
    check("S3 money_direction seeker_to_filler", res.get("money_direction") == "seeker_to_filler", str(res)[:140])
    st, res = req("GET", f"/bookings/{bid}", headers={"X-Hub-Token": J1}, base=HUB)
    check("S3 booking carries direction", res.get("money_direction") == "seeker_to_filler", str(res)[:160])
    MGR = own_mgrs[kid]
    st, res = req("POST", f"/listings/{kid}/applications", {"action": "list", "manage_code": MGR}, headers={"X-Hub-Token": OWN}, base=HUB)
    a2 = [a for a in res.get("applications", []) if a["id"] == aid2]
    check("S2 slot-fill auto-declines other pending", a2 and a2[0]["status"] == "declined", str(a2)[:120])

    # withdraw path
    st, res = req("POST", "/book", {"listing_id": vid, "player": "Dora", "human_verified": True},
        headers={"X-Hub-Token": J2}, base=HUB)
    # vid is walled -> expect application refusal; use a third seek for withdraw
    st, res = req("POST", "/listings", {"vertical": "volunteers", "role": "seek", "title": "Crew",
        "date": "2026-12-05", "location": "Vienna", "price": 0, "capacity": 2, "application_mode": "vetted",
        "category": "crew"}, headers={"X-Hub-Token": OWN}, base=HUB)
    cid = res.get("id", "")
    st, res = req("POST", "/book", {"listing_id": cid, "volunteer": "Dora", "human_verified": True},
        headers={"X-Hub-Token": J2}, base=HUB)
    aid3 = res.get("application_id", "")
    st, res = req("POST", f"/listings/{cid}/applications", {"action": "withdraw", "application_id": aid3},
        headers={"X-Hub-Token": J2}, base=HUB)
    check("S2 applicant withdraws", st == 200 and res.get("status") == "withdrawn", f"{st} {str(res)[:120]}")

    # role immutability via manage (schema-derived edit allowlist)
    st, res = req("POST", f"/listings/{sid}/manage", {"action": "edit", "role": "offer", "manage_code": own_mgrs[sid]},
        headers={"X-Hub-Token": OWN}, base=HUB)
    check("S1 role immutable via manage", st == 400, f"{st} {str(res)[:120]}")

    # chat wiring (static pins; chatlib import needs repo venv deps)
    cl = open(os.path.join(HERE, "chatlib.py")).read()
    check("S1 chat need-command wired", "def _create_seek(" in cl and 'startswith("need ")' in cl, "")

    fails = [n for n, ok in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} PASS")
    if fails:
        print("FAILURES:", fails)
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
