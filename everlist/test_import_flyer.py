"""A3 flyer import pins (owner GO 2026-11-12, impl-plan Track A3):
pdf_text()/draft_from_flyer() extract honest, bounded, fail-open drafts from
flyer PDFs/text with the STDLIB ONLY (no pypdf install exists or approved).
The draft is ADVICE — never authority (organizer confirms every field).
Run: python test_import_flyer.py
"""
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


import enrich  # noqa: E402


def _fake_pdf(text_ops):
    content = zlib.compress(text_ops)
    return (b"%PDF-1.4\n1 0 obj<</Length " + str(len(content)).encode()
            + b"/Filter/FlateDecode>>stream\n" + content
            + b"\nendstream\nendobj\ntrailer<</Root 1 0 R>>\n%%EOF")


FLYER = (b"BT /F1 12 Tf (Keksbackkurs Weihnachten) Tj 0 -20 Td "
         b"(Datum: 2026-12-05 15:00) Tj 0 -20 Td (Preis: EUR 129,90) Tj "
         b"0 -20 Td (Ort: Vollpension Graz) Tj 0 -20 Td "
         b"(Backen Sie Ihre eigenen Platzchen mit uns.) Tj ET")

# ---- extraction laws ----
out = enrich.pdf_text(_fake_pdf(FLYER))
check("P pdf text extracted", bool(out) and "Keksbackkurs" in (out or ""))
check("P line fidelity (newline joins)", bool(out) and "\n" in out)

d = enrich.draft_from_flyer(_fake_pdf(FLYER))
check("P dispatcher returns pdf source", bool(d) and d.get("source") == "pdf")
draft = (d or {}).get("draft") or {}
check("P title = first visual line", draft.get("title") == "Keksbackkurs Weihnachten",
      repr(draft.get("title")))
check("P date parsed", draft.get("date") == "2026-12-05")
check("P time parsed", draft.get("time") == "15:00")
check("P price parsed (EUR 129,90 -> 129.9)", draft.get("price") == 129.9)
check("P Ort: anchor respected", draft.get("location") == "Vollpension Graz",
      repr(draft.get("location")))
check("P description carries the rest", "Platzchen" in (draft.get("description") or ""))

# ---- plain-text passthrough ----
d2 = enrich.draft_from_flyer(
    "Keramik Workshop\n2026-11-20\n\u20ac45,00\nOrt: Studio Blau Salzburg".encode("utf-8"))
check("T text source labeled", bool(d2) and d2.get("source") == "text")
check("T text draft fields", (d2 or {}).get("draft", {}).get("price") == 45.0
      and (d2 or {}).get("draft", {}).get("location") == "Studio Blau Salzburg")

# ---- fail-open law ----
check("F non-PDF bytes -> None", enrich.pdf_text(b"hello world this is not a pdf at all") is None)
check("F empty bytes -> None", enrich.pdf_text(b"") is None)
check("F wrong type -> None", enrich.pdf_text(None) is None)
check("F truncated PDF -> None", enrich.pdf_text(b"%PDF-1.4\nstream\n\x00\x01\x02") is None)
check("F dispatcher None -> None", enrich.draft_from_flyer(None) is None)
check("F dispatcher empty -> None", enrich.draft_from_flyer(b"") is None)
big = b"%PDF-1.4\n" + b"x" * (10_000_001 - 10)
check("F oversized PDF -> None (10 MB cap)", enrich.pdf_text(big) is None)

# ---- stdlib-only law (no pypdf import exists in the module) ----
src = open(os.path.join(HERE, "enrich.py"), encoding="utf-8").read()
check("L no pypdf dependency", "import pypdf" not in src)
check("L zlib is the decompressor", "import zlib" in src and "zlib.decompress" in src)

print()
bad = [n for n, ok in RESULTS if not ok]
print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("ALL FLYER CHECKS PASSED")
