#!/usr/bin/env python3
"""Quickstart — from zero to a booked event in ~10 minutes (X2).

Walks through the full agent journey against any Agent Hub:
  1. discover the hub (manifest)
  2. create a Tier-1 keypair account (seed stays LOCAL, hub stores pubkey only)
  3. search listings
  4. book one (escrow holds the payment)
  5. cancel with the one-time cancel token

Run:  python3 sdk/examples/quickstart.py [hub_url]
Docs: README.md § Quickstart
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from agenthub import AgentHub, HubError  # noqa: E402


def main() -> None:
    hub_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8802"
    hub = AgentHub(hub_url)

    print(f"* connecting to {hub_url}")
    man = hub.manifest()
    print(f"  hub: {man['hub']}  fee: {man['fairness']['fee_policy']['actual_fee_pct']}%"
          f"  escrow: {man['fairness']['escrow']}")

    print("* creating a keypair account (Tier-1)")
    acct = hub.signup_keypair("quickstart-agent")
    seed = acct["seed"]
    print(f"  account: {acct['account_id']}")
    print("  seed (store it safely — shown ONCE, the hub keeps only your pubkey):")
    print(f"    {seed[:8]}...{seed[-8:]}")

    print("* searching for events")
    hits = hub.search("yoga")
    if not hits:
        print("  no yoga listings — searching everything")
        hits = hub.listings()
    for l in hits[:5]:
        avail = getattr(l, "available", "?")
        print(f"  {l.id}: {l.title} — €{l.price} ({avail} available)")
    if not hits:
        print("  hub has no listings yet; run `make demo-seed` first")
        return

    target = hits[0]
    print(f"* booking {target.id} ({target.title})")
    # human_verified=True is the INTERIM stub (demo/testnet only): the hub accepts
    # the flag as-is. Production replaces it with a ZK personhood credential
    # (verify-midnight) — see SPEC section 22. Never fake this in production.
    booking = hub.book(target.id, quantity=1, attendee="quickstart-demo",
                      human_verified=True)
    print(f"  booking {booking.id}: €{booking.amount:.2f}"
          f"  escrow: {booking.escrow}")
    print(f"  cancel token (one-time, store it): {booking.cancel_token or 'n/a'}")

    print("* my bookings")
    for b in hub.bookings():
        print(f"  {b.id}: {b.listing_id} — escrow {b.escrow}")

    print("* cancelling the demo booking")
    try:
        hub.cancel(booking.id, booking.cancel_token)
        print(f"  cancelled {booking.id} — escrow releases back to the buyer")
    except HubError as e:
        print(f"  cancel not available here: {e}")

    print("* done — that was the whole agent surface: "
          "manifest → account → search → book → manage")


if __name__ == "__main__":
    main()
