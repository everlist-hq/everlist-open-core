"""Badge loop / press kit pins (owner GO 2026-11-12, spec-import-and-badges §4):
/presskit renders EN + DE overlay, badge snippets are ESCAPED verbatim (copy-
paste text, never live markup), sitemap carries the EN/DE pair, webchat wiring
present (route + static-path map). Static-gate style per DL-3 precedent.
Run: python test_presskit.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else detail))


import pages
import i18n

# ---- EN render ----
en = pages.presskit_html(loc="en").decode()
check("P EN 200-shape + title", "Press & partner kit" in en)
check("P EN badge text", "Bookable on EverList" in en)
check("P DE badge snippet present", "Buchbar auf EverList" in en)
check("P snippets escaped (no live badge markup)",
      "&lt;a class=&quot;el-badge&quot;" in en and '<a class="el-badge"' not in en)
check("P placeholder targets named", "/p/your-name" in en and "/l/ID" in en)
check("P approved logo referenced", "logo-512.png" in en)
check("P reciprocity section", "What we do in return" in en)

# ---- DE overlay (law: DE copy ships from i18n.DE, never half-translated) ----
de = pages.presskit_html(loc="de").decode()
check("P DE title", "Presse &amp; Partner-Kit" in de)
check("P DE intro", "keine Doppeleingabe" in de)
check("P DE section headers", "Das Badge" in de and "Textbausteine" in de and "Was wir dafür tun" in de)
check("P i18n key count sane", all(k in i18n.DE for k in (
    "Press & partner kit", "The badge", "Suggested copy", "Assets")))

# ---- sitemap pair ----
sm = pages.sitemap_xml().decode()
check("P sitemap EN/DE pair",
      "https://everlist.network/presskit" in sm and "https://everlist.network/de/presskit" in sm)

# ---- webchat wiring (static gate: route + cache header pattern present) ----
src = open(os.path.join(HERE, "webchat.py"), encoding="utf-8").read()
check("W route registered", 'rest == "/presskit"' in src and "presskit_html(HUB_URL, loc)" in src)
check("W static-path map includes /presskit", '"/privacy", "/presskit"' in src)
check("W cache pattern consistent", src.count('presskit_html(HUB_URL, loc)') == 1)

print()
bad = [n for n, ok in RESULTS if not ok]
print(f"{len(RESULTS) - len(bad)}/{len(RESULTS)} checks passed")
if bad:
    print("FAILED:", bad)
    sys.exit(1)
print("ALL PRESSKIT CHECKS PASSED")
