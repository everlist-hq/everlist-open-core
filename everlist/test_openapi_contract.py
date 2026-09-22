"""H13b (run #9): OpenAPI contract tests — the spec's schemas cannot lie.
Serves /openapi.json from a live isolated hub, then:
  1. components/schemas exist for the core resources (Listing, Booking, Error,
     LedgerEntry, ...).
  2. every core operation carries a response schema ($ref or inline).
  3. LIVE RESPONSE VALIDATION: each core endpoint is actually exercised
     (seeded free+paid listings, full booking lifecycle) and the real JSON
     body is validated against the served schema with
     jsonschema.Draft202012Validator ($refs resolved against the fetched spec).
  4. error contract: a 400 (bad listing create) and a 404 (unknown listing)
     validate against the Error schema.
Run: python test_openapi_contract.py
"""
import json, os, socket, subprocess, sys, tempfile, time
import urllib.error, urllib.request

import jsonschema
import referencing
import referencing.jsonschema

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def req(base, method, path, body=None, headers=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(base + path, data=data, method=method,
                               headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {}
    except Exception as e:
        return -1, {"error": str(e)}


TMP = tempfile.mkdtemp(prefix="hub-openapi-contract-")
PORT = free_port(); BASE = f"http://127.0.0.1:{PORT}"
env = {**os.environ, "HUB_STATE_FILE": os.path.join(TMP, "state.json"),
       "PYTHONUNBUFFERED": "1"}
logf = open(os.path.join(TMP, "hub.log"), "a")
proc = subprocess.Popen([sys.executable, os.path.join(HERE, "app.py"), str(PORT)],
                        stdout=logf, stderr=subprocess.STDOUT, env=env)
end = time.time() + 15; ready = False
while time.time() < end:
    try:
        with socket.create_connection(("127.0.0.1", PORT), timeout=0.5): ready = True; break
    except OSError: time.sleep(0.2)
assert ready, "test hub did not start"

# (method, path, expected status) for every core operation with a $ref response
CORE_OPS = [
    ("GET", "/listings", 200),
    ("POST", "/listings", 201),
    ("GET", "/listings/{id}", 200),
    ("GET", "/search", 200),
    ("GET", "/bookings", 200),
    ("GET", "/book/{id}", 200),
    ("POST", "/book", 201),
    ("POST", "/book/{id}/confirm", 200),
    ("POST", "/book/{id}/cancel", 200),
    ("POST", "/book/{id}/rate", 200),
    ("GET", "/ledger", 200),
    ("GET", "/verticals", 200),
    ("GET", "/.well-known/agent-hub.json", 200),
    ("GET", "/openapi.json", 200),
]
REQUIRED_SCHEMAS = ["Listing", "Booking", "Error", "LedgerEntry",
                    "OrderList", "PaymentTerms"]

try:
    print("== contract: components/schemas exist ==")
    st, spec = req(BASE, "GET", "/openapi.json")
    check("GET /openapi.json -> 200", st == 200, str(st))
    comps = spec.get("components", {}).get("schemas", {})
    for name in REQUIRED_SCHEMAS:
        check(f"components/schemas/{name} exists", name in comps,
              f"have: {sorted(comps)}")

    print("== contract: every core operation carries a response schema ==")
    for method, path, _code in CORE_OPS:
        op = spec.get("paths", {}).get(path, {}).get(method.lower(), {})
        resp = op.get("responses", {}).get(str(_code), {})
        sch = resp.get("content", {}).get("application/json", {}).get("schema", {})
        ok = bool(sch) and ("$ref" in sch or "type" in sch or "allOf" in sch)
        check(f"{method} {path} -> {_code} has response schema", ok,
              json.dumps(resp)[:120])

    print("== seed: live hub traffic (free + paid listings, full lifecycle) ==")
    st, own = req(BASE, "POST", "/access", {"agent": "contract-owner", "acts": ["book", "list"]})
    assert st == 201, f"owner /access failed: {st} {own}"
    st, buy = req(BASE, "POST", "/access", {"agent": "contract-buyer", "acts": ["book", "list"]})
    assert st == 201, f"buyer /access failed: {st} {buy}"
    OLT, OBT = own["tokens"]["list"], own["tokens"]["book"]
    BBT = buy["tokens"]["book"]
    H = lambda t: {"X-Hub-Token": t}

    st, free = req(BASE, "POST", "/listings", {
        "vertical": "events", "title": "Contract Free Meetup", "date": "2026-10-01",
        "location": "Berlin", "price": 0, "capacity": 5}, H(OLT))
    assert st == 201, f"free create failed: {st} {free}"
    st, paid = req(BASE, "POST", "/listings", {
        "vertical": "food", "title": "Contract Pizza", "merchant": "M",
        "price": 12}, H(OLT))
    assert st == 201, f"paid create failed: {st} {paid}"
    fid, pid, mc = free["id"], paid["id"], paid["manage_code"]

    st, bk1 = req(BASE, "POST", "/book", {"listing_id": fid, "human_verified": True,
                                          "attendee": "Anon Rate"}, H(BBT))
    assert st == 201, f"booking 1 failed: {st} {bk1}"
    st, bk2 = req(BASE, "POST", "/book", {"listing_id": pid, "human_verified": True,
                                          "buyer": "Anon Buyer", "quantity": 1}, H(BBT))
    assert st == 201, f"booking 2 failed: {st} {bk2}"
    st, bk3 = req(BASE, "POST", "/book", {"listing_id": fid, "human_verified": True,
                                          "attendee": "Anon Cancel"}, H(BBT))
    assert st == 201 and "booking_secret" in bk3 and "cancel_token" in bk3, \
        f"booking 3 failed: {st} {bk3}"

    st, cf = req(BASE, "POST", f"/book/{bk2['id']}/confirm", {"manage_code": mc}, H(OLT))
    assert st == 200, f"confirm failed: {st} {cf}"
    st, rt = req(BASE, "POST", f"/book/{bk1['id']}/rate", {"rating": 5}, H(BBT))
    assert st == 200, f"rate failed: {st} {rt}"
    st, cx = req(BASE, "POST", f"/book/{bk3['id']}/cancel", {}, H(bk3["cancel_token"]))
    assert st == 200, f"cancel failed: {st} {cx}"
    print(f"seeded: listings {fid}/{pid}, bookings {bk1['id']}/{bk2['id']}/{bk3['id']}")

    # live fetches: (method, path) -> (status, body); responses captured during
    # the seed flow above are reused for the mutating ops
    LIVE = {
        ("GET", "/listings"): req(BASE, "GET", "/listings"),
        ("GET", "/listings/{id}"): req(BASE, "GET", f"/listings/{fid}"),
        ("GET", "/search"): req(BASE, "GET", "/search?q=Contract"),
        ("POST", "/listings"): (201, paid),
        ("GET", "/bookings"): req(BASE, "GET", "/bookings", headers=H(BBT)),
        ("GET", "/book/{id}"): req(BASE, "GET", f"/book/{bk1['id']}",
                                    headers=H(bk1["booking_secret"])),
        ("POST", "/book"): (201, bk3),
        ("POST", "/book/{id}/confirm"): (200, cf),
        ("POST", "/book/{id}/cancel"): (200, cx),
        ("POST", "/book/{id}/rate"): (200, rt),
        ("GET", "/ledger"): req(BASE, "GET", "/ledger"),
        ("GET", "/verticals"): req(BASE, "GET", "/verticals"),
        ("GET", "/.well-known/agent-hub.json"): req(BASE, "GET", "/.well-known/agent-hub.json"),
        ("GET", "/openapi.json"): (200, spec),
    }

    # validator: $refs resolved against the FETCHED spec document itself
    registry = referencing.Registry().with_resource(
        "openapi.json",
        referencing.Resource.from_contents(
            spec, default_specification=referencing.jsonschema.DRAFT202012))

    def validator_for(schema_name):
        return jsonschema.Draft202012Validator(
            {"$ref": f"openapi.json#/components/schemas/{schema_name}"},
            registry=registry)

    print("== live validation: real responses vs served schemas ==")
    for method, path, code in CORE_OPS:
        want_status = code
        lst, body = LIVE[(method, path)]
        status_ok = lst == want_status
        check(f"live {method} {path} -> {want_status}", status_ok, str(lst))
        if not status_ok:
            continue
        sch = spec["paths"][path][method.lower()]["responses"][str(code)][
            "content"]["application/json"]["schema"]
        ref = sch.get("$ref", "")
        name = ref.rsplit("/", 1)[-1] if ref.startswith("#/components/schemas/") else None
        if name is None:
            check(f"live {method} {path}: schema is $ref into components", False,
                  str(sch)[:120])
            continue
        errors = sorted(validator_for(name).iter_errors(body), key=lambda e: list(e.path))
        check(f"live {method} {path} validates against {name}", not errors,
              "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:3]))

    print("== error contract: 400 + 404 against Error schema ==")
    err_validator = validator_for("Error")
    st, e400 = req(BASE, "POST", "/listings", {"vertical": "events", "title": "x"}, H(OLT))
    errs = list(err_validator.iter_errors(e400))
    check("bad listing create -> 400 + validates against Error",
          st == 400 and not errs, f"{st}; " + "; ".join(e.message for e in errs[:3]))
    st, e404 = req(BASE, "GET", "/listings/lst-nonexistent")
    errs = list(err_validator.iter_errors(e404))
    check("unknown listing -> 404 + validates against Error",
          st == 404 and not errs, f"{st}; " + "; ".join(e.message for e in errs[:3]))
finally:
    proc.terminate()
    try: proc.wait(timeout=5)
    except Exception: proc.kill()
    logf.close()

fails = [n for n, ok in RESULTS if not ok]
print(f"\n=== openapi-contract: {len(RESULTS) - len(fails)}/{len(RESULTS)} passed ===")
if fails:
    print("FAILED:", fails); sys.exit(1)
print("OPENAPI_CONTRACT_ALL_PASSED")
