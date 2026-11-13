"""QR venue poster pins (owner GO 2026-11-12, spec-import-and-badges §4):
/poster/<id> renders a print-ready A4 poster (EN/DE), QR as CSP-safe data:
URI, honest fields (missing omitted, price 0 = Free/Kostenlos), escaped
text, approved logo only. Static-gate style per DL-3 precedent — no live
server needed. Run: python test_poster.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


import poster  # noqa: E402

FX = {"id": "evt-99", "title": "Keksbackkurs <Weihnachten> & More",
      "date": "2026-12-05", "time": "15:00", "price": 12.5,
      "location": "Wien, Atelier X", "capacity": 20}

en = poster.poster_html(FX, "https://everlist.network", "en").decode()
de = poster.poster_html(FX, "https://everlist.network", "de").decode()

# ---- renderer laws ----
check("R noindex (print artifact stays out of search)", "noindex" in en)
check("R A4 print rule (in external poster.css — CSP law)",
      "@page { size: A4 portrait" in open(os.path.join(HERE, "static", "poster.css"), encoding="utf-8").read())
check("R stylesheet EXTERNAL (CSP style-src strips inline)",
      '<link rel="stylesheet" href="/poster.css?v=' in en and "<style" not in en)
check("R stylesheet carries version param", "poster.css?v=" in en)
css = open(os.path.join(HERE, "static", "poster.css"), encoding="utf-8").read()
check("R v2 self-hosted fonts (@font-face Fraunces+Inter)",
      "@font-face" in css and "/fonts/fraunces-latin-700-normal.woff2" in css
      and "/fonts/inter-latin-400-normal.woff2" in css)
check("R v2 brand tokens (night band + accent)", "#1A252B" in css and "#86C0A6" in css)
check("R v2 dark bands + wordmark + perforation + qrbox",
      'class="band"' in en and 'class="band foot"' in en
      and 'class="wordmark"' in en and 'class="perf"' in en and 'class="qrbox"' in en)
check("R v2 PDF download link EN",
      'href="https://everlist.network/poster/evt-99.pdf"' in en and 'class="dl"' in en)
check("R v2 PDF download link DE (Als PDF herunterladen)",
      'Als PDF herunterladen' in de
      and 'href="https://everlist.network/poster/evt-99.pdf"' in de)
check("R EN tagline", "Bookable via EverList" in en)
check("R DE tagline", "Buchbar \u00fcber EverList" in de)
check("R DE Sie-form footer", "Veranstalter:" in de)
check("R scan CTA EN/DE", "Scan to book" in en and "Zum Buchen scannen" in de)
check("R approved logo (absolute, standalone artifact)",
      'src="https://everlist.network/logo-512.png"' in en)
check("R QR embedded as data: URI (CSP-safe)", "data:image/png;base64," in en)
check("R listing URL present", "everlist.network/l/evt-99" in en)
check("R title HTML-escaped", "&lt;Weihnachten&gt;" in en
      and "<Weihnachten>" not in en)
check("R price EN format", "\u20ac12.50" in en)
check("R price DE format", "12,50 \u20ac" in de)
check("R date+time row", "2026-12-05" in en and "15:00" in en)
check("R DE fact labels", ">Datum</b>" in de and ">Ort</b>" in de
      and ">Preis</b>" in de)

free_en = poster.poster_html({"id": "x", "title": "t", "price": 0},
                             "https://e.network", "en").decode()
free_de = poster.poster_html({"id": "x", "title": "t", "price": 0},
                             "https://e.network", "de").decode()
noprice = poster.poster_html({"id": "x", "title": "t"},
                             "https://e.network", "de").decode()
check("R price 0 = Free (F6, no escrow copy)", "Free" in free_en)
check("R price 0 = Kostenlos (DE)", "Kostenlos" in free_de)
check("R missing price row omitted (never invented)", "Preis" not in noprice)
empty = poster.poster_html({}, "https://e.network", "en").decode()
check("R empty listing degrades honestly", "Scan to book" in empty)
check("R returns bytes", isinstance(poster.poster_html(FX, "https://e.network"), bytes))

# ---- wiring pins (drift class: prod matcher / route / test registration) ----
wc = open(os.path.join(HERE, "webchat.py"), encoding="utf-8").read()
check("W webchat imports poster", "import poster as _poster" in wc)
check("W /poster/ route serves poster_html", "rest.startswith(\"/poster/\")" in wc
      and "poster_html" in wc)
check("W poster route uses PUBLIC base url", "EVERLIST_PUBLIC_URL" in wc)
check("W poster path mapped in static-path map", 'return "/poster/*"' in wc)

dep = open(os.path.join(HERE, "tools", "deploy.sh"), encoding="utf-8").read()
check("W deploy matcher carries /poster/*", "/poster/*" in dep)
check("W deploy matcher carries /poster.css", "/poster.css" in dep)

mk = open(os.path.join(HERE, "Makefile"), encoding="utf-8").read()
check("W Makefile registers test_poster.py", "test_poster.py" in mk)
check("W Makefile registers test_poster_pdf.py", "test_poster_pdf.py" in mk)

# ---- ship-list law (incident class: poster.py broke webchat boot on VPS) --
# ops/ship.sh is a local orchestration file, NOT part of either repo — skip
# these pins where it doesn't exist (GitHub runner checkout). Local gates
# still enforce them.
_ship = os.path.join(HERE, "..", "..", "ops", "ship.sh")
if os.path.isfile(_ship):
    ship = open(_ship, encoding="utf-8").read()
    check("S ship FILES carries poster.py", " poster.py " in ship)
    check("S ship FILES carries static/poster.css", "static/poster.css" in ship)
    check("S ship FILES carries poster_pdf.py", "poster_pdf.py" in ship)
    check("S ship FILES carries all font files", ship.count("static/fonts/") >= 10)
else:
    check("S ship.sh absent (CI checkout) — ship pins skipped", True)

# ---- PDF twin laws (B3-PDF, owner 2026-11-13: downloadable as PDF, A4) -----
import poster_pdf
_pdf = poster_pdf.poster_pdf_bytes(FX, "https://everlist.network", "en")
check("P PDF renders valid bytes (%PDF magic)",
      isinstance(_pdf, bytes) and _pdf[:5] == b"%PDF-")
check("P PDF fail-open (empty listing -> bytes or None, never raises)",
      isinstance(poster_pdf.poster_pdf_bytes({}, "https://everlist.network", "en"),
                 (bytes, type(None))))
_pdf_src = open(os.path.join(HERE, "poster_pdf.py"), encoding="utf-8").read()
check("P PDF source keeps never-invented law", "never invented" in _pdf_src)
_req = open(os.path.join(HERE, "requirements.txt"), encoding="utf-8").read()
check("P fpdf2 pinned in requirements.txt", "fpdf2==" in _req)
check("P fonts staged (TTF for PDF + woff2 for web)",
      os.path.isfile(os.path.join(HERE, "static", "fonts", "fraunces-latin-700-normal.ttf"))
      and os.path.isfile(os.path.join(HERE, "static", "fonts", "inter-latin-400-normal.woff2")))
check("W webchat imports poster_pdf", "import poster_pdf as _poster_pdf" in wc)
check("W .pdf route BEFORE html branch",
      0 < wc.find('rest.startswith("/poster/") and rest.endswith(".pdf")')
      < wc.find('elif rest.startswith("/poster/"):'))
check("W PDF served as attachment (Content-Disposition)",
      'Content-Disposition' in wc and 'attachment' in wc)
check("W font + pdf MIME types registered", '".woff2"' in wc and '".ttf"' in wc
      and '".pdf"' in wc)
check("W deploy matcher carries /fonts/*", "/fonts/*" in dep)
check("W _send_bytes supports extra headers", "extra_headers" in wc)

# ---- enrich A3 pins (pdf flyer extraction shipped with SEEK ship) ----
enrich_src = open(os.path.join(HERE, "enrich.py"), encoding="utf-8").read()
check("E pdf_text stdlib-only (no pypdf import)", "def pdf_text" in enrich_src
      and "import pypdf" not in enrich_src)
check("E flyer dispatcher present", "def draft_from_flyer" in enrich_src)

print()
bad = [n for n, ok in RESULTS if not ok]
print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("ALL POSTER CHECKS PASSED")
