#!/usr/bin/env python3
"""chatlog_mine.py — mine chat + guard logs for chat improvement signals.

Owner ask (2026-09-26): analyse the logs systematically. Reads .run/chatlog.jsonl
(and .1 rotation) plus .run/phrase-guard.jsonl and prints a report:

  * volume + surfaces + latency p50/p95
  * phrase layer: shipped/retried/fallback/outage rates (SLO: fallback < 1%)
  * guard violations grouped by pattern (the prompt-patch queue)
  * unhandled-ish turns: error/guidance replies, empty matches, 4xx
  * robot-string scan across replies
  * top user phrasings (query patterns for the voice laws)

Usage:
    python tools/chatlog_mine.py [--days 7] [--json out.json]
Exit 0 always (analysis, not a gate).
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = os.path.join(HERE, ".run")
CHATLOG = os.path.join(RUN, "chatlog.jsonl")
GUARDLOG = os.path.join(RUN, "phrase-guard.jsonl")

ROBOT_STRINGS = [
    "is the hub up", "(empty response)", "invalid input", "traceback",
    "error:", "exception", "none)", "[object",
]


def _pctl(xs, p):
    if not xs:
        return 0
    xs = sorted(xs)
    k = max(0, min(len(xs) - 1, int(len(xs) * p / 100)))
    return xs[k]


def load_chatlog(days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    for path in (CHATLOG, CHATLOG + ".1"):
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for ln in f:
                try:
                    r = json.loads(ln)
                except Exception:
                    continue
                try:
                    ts = datetime.fromisoformat(r.get("ts", ""))
                except Exception:
                    continue
                if ts < cutoff:
                    continue
                rows.append(r)
    return rows


def load_guardlog(days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    if not os.path.exists(GUARDLOG):
        return rows
    with open(GUARDLOG, encoding="utf-8") as f:
        for ln in f:
            try:
                r = json.loads(ln)
            except Exception:
                continue
            try:
                ts = datetime.fromisoformat(r.get("ts", ""))
            except Exception:
                continue
            if ts >= cutoff:
                rows.append(r)
    return rows


def mine_chat(rows):
    out = {}
    out["turns"] = len(rows)
    out["surfaces"] = Counter(r.get("surface", "?") for r in rows)
    lat = [r.get("ms") for r in rows if isinstance(r.get("ms"), (int, float))]
    out["latency_ms"] = {"p50": _pctl(lat, 50), "p95": _pctl(lat, 95),
                         "n": len(lat)}
    # robot strings in replies
    robo = Counter()
    for r in rows:
        rep = (r.get("reply") or "").lower()
        for bad in ROBOT_STRINGS:
            if bad in rep:
                robo[bad] += 1
    out["robot_strings"] = dict(robo)
    # error-ish / guidance turns (candidates for phrasing quality review)
    errish = [r for r in rows
              if (r.get("reply") or "").lower().startswith(("❌", "⚠️", "hmm"))]
    out["error_turns"] = len(errish)
    # top user phrasings (first 3 words)
    phr = Counter()
    for r in rows:
        t = (r.get("text") or "").strip().lower()
        if t:
            phr[" ".join(t.split()[:3])[:40]] += 1
    out["top_phrasings"] = phr.most_common(12)
    # no-match turns: what users searched for and got nothing
    nomatch = [r.get("text", "")[:60] for r in rows
               if (r.get("reply") or "").startswith("Nothing matched")]
    out["nomatch_queries"] = Counter(nomatch).most_common(10)
    return out


def mine_guard(rows):
    out = {"events": len(rows)}
    ev = Counter(r.get("event", "?") for r in rows)
    out["by_event"] = dict(ev)
    shipped = ev.get("shipped", 0) + ev.get("fallback", 0)
    out["fallback_rate_pct"] = (
        round(100.0 * ev.get("fallback", 0) / shipped, 2) if shipped else None)
    viol = Counter()
    for r in rows:
        for v in r.get("violations", []):
            key = v_key = v.split(":")[0] if ":" in v else v
            viol[key] += 1
    out["violation_classes"] = dict(viol.most_common(10))
    out["retried_ok_pct"] = (
        round(100.0 * ev.get("shipped", 0) and
              (sum(1 for r in rows if r.get("event") == "shipped"
                   and r.get("attempt", 1) > 1)) /
              max(1, ev.get("shipped", 0)), 1))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--json", help="also write the report as JSON here")
    args = ap.parse_args()
    chat = mine_chat(load_chatlog(args.days))
    guard = mine_guard(load_guardlog(args.days))
    report = {"window_days": args.days, "chat": chat, "guard": guard}
    print("== chat log (%dd) ==" % args.days)
    print("turns=%d  surfaces=%s" % (chat["turns"], dict(chat["surfaces"])))
    print("latency ms: p50=%s p95=%s (n=%s)" % (
        chat["latency_ms"]["p50"], chat["latency_ms"]["p95"],
        chat["latency_ms"]["n"]))
    print("robot strings found: %s" % (chat["robot_strings"] or "none"))
    print("error-ish turns: %s" % chat["error_turns"])
    print("no-match top queries:")
    for q, n in chat["nomatch_queries"]:
        print("   %3dx  %s" % (n, q))
    print("top user phrasings:")
    for p, n in chat["top_phrasings"]:
        print("   %3dx  %s" % (n, p))
    print("\n== phrase guard ==")
    print("events: %s  by_event: %s" % (guard["events"], guard["by_event"]))
    if guard["fallback_rate_pct"] is not None:
        print("fallback rate: %s%%  (SLO < 1%%)" % guard["fallback_rate_pct"])
        print("violation classes: %s" % guard["violation_classes"])
    else:
        print("guard log empty or layer not enabled yet")
    if args.json:
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        print("\nreport: %s" % args.json)


if __name__ == "__main__":
    main()
