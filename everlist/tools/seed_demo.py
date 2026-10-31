#!/usr/bin/env python3
"""seed_demo.py - seed EverList demo listings.

Two modes:
  default          H16 generic demo (demo_listings.json): one demo-<slug>
                   agent per listing, manage codes printed, refuses to seed
                   on top of an existing hub (use 'make demo-reset').
  --agent NAME     partner mode: ONE organizer identity owns everything via a
                   REAL acct- account (signup PoW solved locally, ~0.3s);
                   /orders + /organizer/earnings + confirm/archive all work
                   from the organizer console after pasting the account code
                   (shown ONCE — it is the credential).
"""
import argparse
import hashlib
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SEED = os.path.join(HERE, "..", "demo_listings.json")


def api(hub, method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(hub.rstrip("/") + path, data=data, method=method,
                                 headers={"Content-Type": "application/json",
                                          **({"X-Hub-Token": token} if token else {})})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def solve_pow(hub, kind):
    """GET challenge, solve sha256 leading-zeros locally, return pow object."""
    with urllib.request.urlopen(hub.rstrip("/") + f"/auth/challenge?kind={kind}", timeout=15) as r:
        ch = json.loads(r.read().decode())
    target = ch["difficulty"]
    prefix = ch["challenge"]
    nonce = 0
    while True:
        d = hashlib.sha256((prefix + str(nonce)).encode()).digest()
        bits = 0
        for b in d:
            if b == 0:
                bits += 8
                continue
            bits += 8 - b.bit_length()
            break
        if bits >= target:
            return {"challenge": prefix, "nonce": nonce}
        nonce += 1


def hub_listing_count(hub):
    st, res = api(hub, "GET", "/listings")
    if st != 200:
        print(f"FAIL: cannot read hub listings ({st}): {res}")
        sys.exit(1)
    return len(res.get("listings", []))


def main():
    ap = argparse.ArgumentParser(description="Seed EverList demo listings")
    ap.add_argument("--hub", default=os.environ.get("HUB_URL", "http://127.0.0.1:8802"))
    ap.add_argument("--file", default=DEFAULT_SEED)
    ap.add_argument("--agent", default="",
                    help="partner mode: single organizer identity owning ALL listings "
                         "(creates a real acct- account; code printed once)")
    args = ap.parse_args()
    hub = args.hub.rstrip("/")

    # H16 honesty: never seed on top of an existing hub
    existing = hub_listing_count(hub)
    if existing:
        print(f"hub already has {existing} listing(s) — refusing to seed on top "
              f"(use 'make demo-reset' for a fresh demo)")
        return 1

    seed = json.load(open(args.file))
    created = []

    if args.agent:
        # --- partner mode: real account ownership (B3c law) ----------------
        organizer = args.agent
        powobj = solve_pow(hub, "signup")
        st, up = api(hub, "POST", "/accounts/signup", {"agent": organizer, "pow": powobj})
        if st == 429:
            print("FAIL: signup rate-limited; wait or restart the hub")
            return 1
        if st not in (200, 201):
            print(f"FAIL signup ({st}): {up}")
            return 1
        account_code = up.get("account_code", "")
        print(f"[account] organizer account created: {up.get('account_id', '?')} (agent: {organizer})")
        print(f"[account] ACCOUNT CODE (shown ONCE, save it): {account_code}")
        st, login = api(hub, "POST", "/accounts/login",
                        {"account_code": account_code, "agent": organizer})
        if st != 200:
            print(f"FAIL login: {login}")
            return 1
        tok = login["tokens"]["list"]
        print(f"[login] ownership token minted (sub={login.get('account_id', '?')}, ttl={login.get('ttl')}s)")
        for item in seed["listings"]:
            payload = {k: v for k, v in item.items() if k != "slug"}
            payload["source"] = "demo-seed"
            st, res = api(hub, "POST", "/listings", payload, token=tok)
            if st != 201:
                print(f"FAIL listing {item.get('title')}: {res}")
                return 1
            created.append(res["id"])
            mc = res.get("manage_code", "")
            print(f"  seeded {res['id']:>10}  {item['vertical']:<8}  {item['title']}"
                  + (f"  manage:{mc}" if mc else ""))
        print(f"\nDemo ready: {len(created)} listings at {hub}")
        print("Organizer console: paste the ACCOUNT CODE above once — full powers "
              "(confirm/archive/new listings)")
    else:
        # --- H16 generic demo: one demo-<slug> agent per listing ------------
        for item in seed["listings"]:
            agent = "demo-" + item["slug"]
            st, acc = api(hub, "POST", "/access", {"agent": agent, "acts": ["list"]})
            if st not in (200, 201):
                print(f"FAIL token for {agent}: {acc}")
                return 1
            payload = {k: v for k, v in item.items() if k != "slug"}
            payload["source"] = "demo-seed"
            st, res = api(hub, "POST", "/listings", payload, token=acc["tokens"]["list"])
            if st != 201:
                print(f"FAIL listing {item.get('title')}: {res}")
                return 1
            created.append(res["id"])
            mc = res.get("manage_code", "")
            print(f"  seeded {res['id']:>10}  {item['vertical']:<8}  {item['title']}"
                  + (f"  manage:{mc}" if mc else ""))
        print(f"\nDemo ready: {len(created)} listings at {hub}")
        print("Try: search yoga | book <free listing id> (chat) | SDK examples/pizzeria.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
