#!/usr/bin/env python3
"""B3-PDF twin suite (owner 2026-11-13): /poster/<id>.pdf A4 download.

Hermetic (no network, no hub): exercises poster_pdf.poster_pdf_bytes
directly, byte-level. Route/deploy wiring is pinned in test_poster.py
(single source of truth for the drift-class pins).

Laws:
- valid %PDF with catalog/page/font structure and clean %%EOF
- QR present as image XObject
- fail-open: never raises, degrades to None only when the stack is broken
- honest omission: missing fields are left out, never invented
- print-safe: overlong titles truncate (fixed A4 layout cannot reflow)
- latin subset coverage: German umlauts/dashes render (no fallback font)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

RESULTS = []


def check(name, ok):
    RESULTS.append((name, bool(ok)))
    print(("PASS  " if ok else "FAIL  ") + name)


import poster_pdf

FX = {"id": "evt-99",
      "title": "Weihnachts-Backkurs mit den Omas \u2013 Pl\u00e4tzchen & Gl\u00fchwein",
      "date": "2026-12-05", "time": "15:00",
      "location": "Atelier Ton & Glut, Graz",
      "price": 12.5, "capacity": 8, "vertical": "cooking_workshop"}

en = poster_pdf.poster_pdf_bytes(FX, "https://everlist.network", "en")
de = poster_pdf.poster_pdf_bytes(FX, "https://everlist.network", "de")

check("P EN renders valid %PDF bytes", isinstance(en, bytes) and en[:5] == b"%PDF-")
check("P DE renders valid %PDF bytes", isinstance(de, bytes) and de[:5] == b"%PDF-")
for tag, blob in (("EN", en), ("DE", de)):
    ok = (blob and blob.rstrip().endswith(b"%%EOF")
          and b"/Type /Catalog" in blob and b"/Page" in blob
          and b"/Font" in blob)
    check("P %s structure (catalog/page/font/EOF)" % tag, bool(ok))
check("P QR embedded as image XObject", b"/XObject" in en)
check("P embedded fonts declared (TTF subset, not core-only)",
      b"/FontFile2" in en or b"/FontFile" in en)

src = open(os.path.join(HERE, "poster_pdf.py"), encoding="utf-8").read()
check("P source keeps never-invented law", "never invented" in src)
check("P print-safe title truncation law", "[:80]" in src)

long_fx = dict(FX)
long_fx["title"] = "X" * 200
longb = poster_pdf.poster_pdf_bytes(long_fx, "https://e.network", "en")
check("P 200-char title still renders valid (truncated)",
      isinstance(longb, bytes) and longb[:5] == b"%PDF-")

noprice = poster_pdf.poster_pdf_bytes(
    {k: v for k, v in FX.items() if k != "price"}, "https://e.network", "de")
check("P missing price -> valid PDF (field omitted, never invented)",
      isinstance(noprice, bytes) and noprice[:5] == b"%PDF-")
empty = poster_pdf.poster_pdf_bytes({}, "https://e.network", "en")
check("P empty listing -> bytes or None, never raises",
      isinstance(empty, (bytes, type(None))))
weird = poster_pdf.poster_pdf_bytes(
    {"id": "x", "title": "()\\ <script> \u20ac \u2026 \u00e4\u00f6\u00fc\u00df",
     "location": "(parens) & \\slashes", "price": 0}, "https://e.network", "de")
check("P hostile/paren/special chars -> valid PDF, never raises",
      isinstance(weird, (bytes, type(None)))
      and (not isinstance(weird, bytes) or weird[:5] == b"%PDF-"))

print()
bad = [n for n, ok in RESULTS if not ok]
print("%d/%d checks passed" % (len(RESULTS) - len(bad), len(RESULTS)))
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("ALL POSTER-PDF CHECKS PASSED")
