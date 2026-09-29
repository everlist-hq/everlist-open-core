"""W2 #1: Abuse-resistant DUST sponsorship (Buildathon Wave 2, owner-approved 2026-09-26).

The hub operates ONE sponsor wallet; zero-DUST organizers/workers transact while
the sponsor pays fees. Anti-abuse rules (owner-approved, from the Wave 1 field
scan - concepts only, own implementation):
  L1  per-organizer sponsorship limit per time window (sliding, monotone ledger)
  L2  sponsor-pool budget cap (hard ceiling; refuses when exhausted for the window)
  L3  optional organizer stake threshold (sponsored action requires a minimum
      prior funded escrow count - bots without skin in the game never qualify)

Design mirrors hub discipline: caller holds LOCK, all state memory-resident,
pure functions over counters so tests can drive time explicitly. Never raises;
returns (ok, reason) - the hub turns refusals into honest 429/402 responses.

Env:
  HUB_SPONSOR_ENABLED     default "1"
  HUB_SPONSOR_WINDOW_SECS default 86400
  HUB_SPONSOR_PER_ORG     default 5 ops per organizer per window
  HUB_SPONSOR_POOL_CAP    default 50 ops per window (global budget)
  HUB_SPONSOR_MIN_FUNDED  default 1 (funded escrows required before sponsorship;
                          0 disables the stake gate)
"""
import os
import threading
import time

_ENABLED = os.environ.get("HUB_SPONSOR_ENABLED", "1") == "1"
_WINDOW = int(os.environ.get("HUB_SPONSOR_WINDOW_SECS", "86400"))
_PER_ORG = int(os.environ.get("HUB_SPONSOR_PER_ORG", "5"))
_POOL_CAP = int(os.environ.get("HUB_SPONSOR_POOL_CAP", "50"))
_MIN_FUNDED = int(os.environ.get("HUB_SPONSOR_MIN_FUNDED", "1"))

# (key) -> list[float] timestamps of sponsored ops this window; pruned on access
_LEDGER = {}
# organizer -> count of prior funded (released) escrows, fed by the hub
_FUNDED = {}
# cumulative counters for observability (survive in-process; hub persists the rest)
_STATS = {"granted": 0, "refused_window": 0, "refused_pool": 0, "refused_stake": 0}


def configure(enabled=None, window=None, per_org=None, pool_cap=None, min_funded=None):
    """Override defaults (tests use this; prod uses env)."""
    global _ENABLED, _WINDOW_SECS, _PER_ORG_N, _POOL_CAP_N, _MIN_FUNDED_N
    if enabled is not None:
        _ENABLED = bool(enabled)
    if window is not None:
        _WINDOW_SECS = int(window)
    if per_org is not None:
        _PER_ORG_N = int(per_org)
    if pool_cap is not None:
        _POOL_CAP_N = int(pool_cap)
    if min_funded is not None:
        _MIN_FUNDED_N = int(min_funded)


_WINDOW_SECS = _WINDOW
_PER_ORG_N = _PER_ORG
_POOL_CAP_N = _POOL_CAP
_MIN_FUNDED_N = _MIN_FUNDED


def _prune(hist, now):
    return [t for t in hist if now - t < _WINDOW_SECS]


def check(organizer, funded_count=0, now=None):
    """May `organizer` get ONE sponsored op now? Returns (ok, reason).
    Caller MUST hold LOCK (or accept the tiny race; every caller in app.py
    already sits inside `with LOCK:`)."""
    if not _ENABLED:
        return True, "sponsorship disabled -> allowed (sponsor role not in play)"
    now = time.time() if now is None else now
    if _MIN_FUNDED_N > 0 and int(funded_count) < _MIN_FUNDED_N:
        _STATS["refused_stake"] += 1
        return False, ("stake threshold not met (%d/%d funded escrows): "
                       "sponsored fees require prior successful bookings" %
                       (funded_count, _MIN_FUNDED_N))
    hist = _prune(_LEDGER.get(organizer, []), now)
    if len(hist) >= _PER_ORG_N:
        _LEDGER[organizer] = hist
        _STATS["refused_window"] += 1
        return False, ("organizer sponsorship limit reached (%d per %d s); "
                       "fund your own DUST or retry later" % (_PER_ORG_N, _WINDOW_SECS))
    pool = _prune([t for h in _LEDGER.values() for t in h], now)
    if len(pool) >= _POOL_CAP_N:
        _LEDGER[organizer] = hist
        _STATS["refused_pool"] += 1
        return False, ("sponsor pool budget exhausted for this window (%d ops); "
                       "retry later" % _POOL_CAP_N)
    hist.append(now)
    _LEDGER[organizer] = hist
    _STATS["granted"] += 1
    return True, "sponsored"


def record(organizer, now=None):
    """Explicit ledger entry for a sponsored op performed outside check()
    (e.g. hub-side auto-sponsorship). Idempotence is the caller's duty."""
    now = time.time() if now is None else now
    _LEDGER.setdefault(organizer, []).append(now)


def stats(now=None):
    """Observability for /openapi + honest status reporting."""
    now = time.time() if now is None else now
    pool = _prune([t for h in _LEDGER.values() for t in h], now)
    return {"enabled": _ENABLED, "window_secs": _WINDOW_SECS,
            "per_org_limit": _PER_ORG_N, "pool_cap": _POOL_CAP_N,
            "min_funded": _MIN_FUNDED_N,
            "pool_used_in_window": len(pool),
            "orgs_in_window": sum(1 for h in _LEDGER.values() if _prune(h, now)),
            **_STATS}
