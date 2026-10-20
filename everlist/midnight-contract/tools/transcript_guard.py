#!/usr/bin/env python3
"""W3.0 transcript-law guard (2026-10-20).

Law: NO circuit may pass private values to query()-style ledger reads.

Why: Compact's query() arguments land in the PUBLIC transaction
transcript even when the circuit compiles and every test passes green —
the leak class found by the Sponsorship Gate team in the Wave-2 field
(2026-10-19 re-scan, techmining #13). Our contracts use committed
lookups (.lookup/.member on published commitments) instead, so this
guard pins the invariant: any future query() call fails the gate BEFORE
it can leak a secret.

Checks:
1. no `query(` call in any src/*.compact (comments included — a stray
   mention means someone is reaching for it; write the intent as a
   comment WITHOUT the call syntax)
2. no `.query(` either (method form)

Run: python3 tools/transcript_guard.py  (exit 0 = clean, 1 = leak found)
Wired into CI (experiments/.github/workflows/tests.yml).
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.normpath(os.path.join(HERE, "..", "src"))

FORBIDDEN = re.compile(r"(^|[^\w.])query\s*\(")


def main() -> int:
    if not os.path.isdir(SRC):
        print(f"transcript_guard: no src/ at {SRC}", file=sys.stderr)
        return 1
    findings = []
    for name in sorted(os.listdir(SRC)):
        if not name.endswith(".compact"):
            continue
        path = os.path.join(SRC, name)
        with open(path, encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                if FORBIDDEN.search(line):
                    findings.append(f"{path}:{lineno}: {line.rstrip()}")
    if findings:
        print("TRANSCRIPT LAW VIOLATED — query() leaks args to the public transcript:")
        for f in findings:
            print("  " + f)
        print("Use committed lookups (.lookup/.member on published commitments) instead.")
        return 1
    print("transcript_guard: clean — zero query() calls across all .compact sources")
    return 0


if __name__ == "__main__":
    sys.exit(main())
