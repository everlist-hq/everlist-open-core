"""Chat intent layer for the EverList Booking chat agent (B3b/B3c).

Deterministic, LLM-free intent mapping: chat text -> hub query -> reply text.
Kept separate from wrapper.py so it is unit-tested without starting an Agent.

Supported intents:
  search/find/listings [query] -> GET /search?q=...
  list Title | cat | date | price | loc | cap -> POST /listings (one-prompt listing, B3c)
  book <id> <name>             -> books FREE listings for logged-in accounts; guidance otherwise
  fee/commission               -> manifest declared-fee transparency info
  help/hello                   -> capability summary
  anything else                -> LLM router: a search, or a clean EverList-only
                                 boundary; fail-open keeps deterministic keyword search
"""

import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse

import chatlog
import storage
import urllib.request
import sys
from datetime import datetime as _dt, timedelta as _td

from cryptography.hazmat.primitives import serialization as _ser
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as _EdPriv

# B3c: per-sender anti-spam cap for chat-created listings (in-memory, pilot-grade)
_LIST_CAP = 3
_list_counts: dict[str, int] = {}


def _hub_get(hub_url: str, path: str, token: str | None = None) -> dict:
    req = urllib.request.Request(hub_url.rstrip("/") + path)
    if token:
        req.add_header("X-Hub-Token", token)
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read().decode())


def _hub_post(hub_url: str, path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        hub_url.rstrip("/") + path, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("X-Hub-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        # server said no (validation/auth): surface the real reason, never 'unreachable'
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": f"hub rejected the request (HTTP {e.code})"}


def _hub_get_claim(hub_url: str, path: str, claim: str):
    """P2: GET with a private-deal claim code (X-Claim-Code header)."""
    req = urllib.request.Request(hub_url.rstrip("/") + path,
                                 headers={"X-Claim-Code": claim})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode())
        except Exception:
            body = {}
        body["_status"] = e.code
        return body


def _hub_delete(hub_url: str, path: str, payload: dict, token: str | None = None) -> tuple[int, dict]:
    """H7: DELETE with body (token-authed), surfacing real rejection reasons."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        hub_url.rstrip("/") + path, data=body, method="DELETE",
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("X-Hub-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": f"hub rejected the request (HTTP {e.code})"}


def _show_listing(hub_url: str, arg: str, sender: str = "") -> str:
    """H9: full listing detail via GET /listings/{id} (404 unknown, 410 archived)."""
    lid = (arg or "").strip()
    if not lid or " " in lid or "/" in lid:
        return ("Which one would you like to see? Try 'show 2' after a search, "
                "or 'my-bookings' to see your bookings. 🙂")
    # Owner visibility (P2): a logged-in owner may view their own private deal.
    # The hub 404s everyone else identically (no existence oracle).
    _tok = ((_session(sender) or {}).get("tokens", {}) or {}).get("list") if sender else None
    try:
        l = _hub_get(hub_url, f"/listings/{lid}", token=_tok)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return f"No listing '{lid}'. Try 'search' to browse, or check the id."
        if e.code == 410:
            return f"Listing '{lid}' is archived — its owner hid it."
        return f"Could not fetch listing (HTTP {e.code})."
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    return _fmt_listing(l)


def _booking_status(hub_url: str, sender: str, arg: str) -> str:
    """H10: poll one booking's status. Logged-in: session token. Anonymous:
    re-mint /access for this chat's own agent address (deterministic principal
    — the same identity that made the booking). No existence oracle: unknown
    or not-yours are the same answer."""
    bid = (arg or "").strip()
    if not bid or " " in bid or "/" in bid:
        return "Usage: booking <booking id> — e.g. 'booking bk-abc123'"
    s = _session(sender)
    token = (s or {}).get("tokens", {}).get("book") or (s or {}).get("tokens", {}).get("list")
    note = ""
    if not token:
        # anonymous chat: this chat's agent address IS its principal — re-mint
        try:
            acc = _hub_post(hub_url, "/access", {"agent": sender, "acts": ["book"]})
            token = acc[1].get("tokens", {}).get("book")
            note = "(acting as this chat's agent identity) "
        except Exception:
            return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    try:
        b = _hub_get(hub_url, f"/bookings/{bid}", token=token)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return (f"No booking '{bid}' is visible to you — it either doesn't exist "
                    "or you are not its buyer/owner.")
        return f"Could not fetch booking (HTTP {e.code})."
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    qty = b.get("quantity", 1)
    qty_s = f" x{qty}" if qty > 1 else ""
    return (f"📋 Booking {b['id']}{note}\n"
            f"Listing: {b.get('listing_id')} | Status: {b.get('escrow', '?')} | "
            f"Amount: {b.get('amount', '?')} USD (fee {b.get('hub_fee', 0)}, payout {b.get('owner_payout', 0)}){qty_s}\n"
            + _escrow_journey(b.get("escrow", "HELD"), b.get("amount")) + "\n"
            "Private details (name etc.) stay secret-gated: 'book {bid}' shows how they're retrieved.".format(bid=b["id"]))


# C9d: the one true sheet - owner-picked grammar after 15 rounds of the sheet
# lab: ֎ mark - ⌂ place - ◷ time - $ real currency - ♟ person
# (always last, spaced) - math-bold names & dates (real weight in every chat).
# The knot frame ships in the brain (C9e) - webchat CSS pins monospace so it
# locks perfectly; foreign chats may drift slightly - accepted trade. Monochrome text symbols only
# (U+FE0E pinned where emoji-prone) - no generic color emoji, ever.
_G_MARK = "֎"      # eternity sign - the brand mark
_G_PLACE = "⌂"     # house = place
_G_TIME = "◷"      # clock face = time
_G_PERSON = "♟"    # pawn = a human wanted; closes every row
_G_ESCROW = "✪"    # seal = escrow-protected


def _escrow_journey(esc_state: str, amount) -> str:
    """W2 item 12: the escrow journey as a text-safe 4-step strip (textContent-
    safe glyphs only, no emoji). Real states only — WAIVED/DIRECT honestly
    show 'no payment needed' instead of a fake timeline."""
    if str(esc_state) in ("WAIVED", "DIRECT") or not float(amount or 0) > 0:
        return "✪ Money journey: nothing to pay — honestly."
    if esc_state == "REFUNDED":
        marks = ["✓", "✓", "—", "↩"]
        last = "REFUNDED to you"
    elif esc_state == "RELEASED":
        marks = ["✓", "✓", "✓", "✓"]
        last = "RELEASED to organizer"
    elif esc_state == "HELD":
        marks = ["✓", "✓", "·", "·"]
        last = "money held safely"
    else:  # unknown state: show it honestly, no invented steps
        return "✪ Payment status: %s (hub state — see Bookings for actions)." % esc_state
    steps = ["asked", "held", "happened", "released"]
    strip = " ".join("[%s %s]" % (m, s) for m, s in zip(marks, steps))
    return ("✪ %s — %s" % (strip, last))


_G_INSTANT = "⇢"   # instant settlement
_G_QUOTE = "»"     # description
_G_LINK = "⇗"      # external link
_G_OK = "✓"        # verified gate
_CUR = {"USD": "$"}    # real currency symbols (hub amounts are USD)

_BOLD = {}
for _i, _c in enumerate("abcdefghijklmnopqrstuvwxyz"):
    _BOLD[_c.upper()] = chr(0x1D5D4 + _i)   # sans-bold capitals
    _BOLD[_c] = chr(0x1D5EE + _i)           # sans-bold small
for _i, _c in enumerate("0123456789"):
    _BOLD[_c] = chr(0x1D7EC + _i)           # sans-bold digits


def _mb(t) -> str:
    """Math-bold text - renders BOLD in every chat, no markdown needed."""
    return "".join(_BOLD.get(c, c) for c in str(t))


# C9e: the knot frame ships IN THE BRAIN - the sheet is one framed document
# (owner verdict: "where is the lines?"). Webchat adds monospace CSS so it
# locks perfectly at home; foreign chats may drift slightly - accepted trade.
_FW = 56  # inner text width in monospace cells


def _fit(t) -> str:
    t = str(t)
    return t if len(t) <= _FW - 1 else t[:_FW - 2] + "\u2026"


def _row(t) -> str:
    return " " + _fit(t)


def _frame(header, blocks):
    """One knot-framed sheet: top rule, optional header + mid rule, entry
    blocks separated by thin seams, bottom rule. All lines exactly _FW+3."""
    fill = "\u2550" * (_FW - 3)
    out = ["\u2554\u2550\u1368" + fill + "\u1368\u2550\u2557"]
    if header is not None:
        out.append(_row(header))
        out.append("\u2560\u2550\u1368" + fill + "\u1368\u2550\u2563")
    for i, blk in enumerate(blocks):
        if i:
            out.append("\u2570" + "\u2500" * (_FW + 1) + "\u256f")
        out.extend(_row(x) for x in blk)
    out.append("\u255a\u2550\u1368" + fill + "\u1368\u2550\u255d")
    return "\n".join(out)

# C9c: result-list display limits
_INLINE_LIMIT = 6   # <= this many results: full cards straight away
_HARD_CAP = 12      # never flood the chat with more full cards at once
_INDEX_CAP = 20     # index lines shown before pointing at refinement
_PREVIEW_CARDS = 3  # full cards attached under a long index
_LAST_RESULTS: dict[str, list] = {}  # per-sender stash for '3' / '2-6' / 'all' follow-ups
_LAST_SEARCH: dict[str, dict] = {}   # Brain v2: last search spec per sender (q + filters)


def _weekday(date_s: str) -> str | None:
    try:
        return _dt.strptime(date_s, "%Y-%m-%d").strftime("%a")
    except Exception:
        return None


def _fmt_price(l: dict) -> str:
    """'$15' / '$12.50' / '$0' - free is $0: the count language covers all."""
    try:
        p = float(l.get("price", 0))
    except (TypeError, ValueError):
        return "$%s" % l.get("price", "?")
    s = "%.2f" % p
    if s.endswith(".00"):
        s = s[:-3]
    return "$" + s


def _fmt_spots(l: dict) -> str | None:
    """'♟ 50 open' / '♟ 3 left' / '♟ 0 left' (sold out) / None if no capacity."""
    try:
        cap = int(l.get("capacity") or 0)
    except (TypeError, ValueError):
        return None
    if cap <= 0:
        return None
    try:
        reg = int(l.get("registered", 0))
    except (TypeError, ValueError):
        reg = 0
    reg = max(0, min(reg, cap))
    word = "open" if reg == 0 else "left"
    return "%s %d %s" % (_G_PERSON, cap - reg, word)


def _fmt_facts(l: dict, full_date: bool = False, person: bool = True) -> str:
    """One glance, four answers: ⌂ place - ◷ date - $ price - ♟ person.
    Rows show 'Sat 10-03' (year dropped); the card shows the full date."""
    bits = []
    if l.get("location"):
        bits.append("%s %s" % (_G_PLACE, str(l["location"]).strip()))
    if l.get("date"):
        d = str(l["date"])
        wd = _weekday(d)
        if wd:
            d = "%s %s" % (wd, d)
        if l.get("time"):
            d += " " + str(l["time"])
        if not full_date and len(d) > 12 and d[-10:][:4].isdigit():
            d = d[:-10] + d[-5:]  # 'Sat 2026-10-03' -> 'Sat 10-03'
        bits.append("%s %s" % (_G_TIME, _mb(d)))
    bits.append(_fmt_price(l))
    spots = _fmt_spots(l)
    if person and spots:
        bits.append(spots)
    return " · ".join(bits)


def _listing_rows(l: dict, num=None) -> list:
    """Inner rows of one listing (no side rails): number + bold title, full-date
    facts row, person + terms, gate, story, link. Minimal-text law: no id, no
    instruction rows - the leading number is the handle ('book <n>')."""
    title = str(l.get("title", "?")).strip() or "?"
    head = ("%2d  %s" % (num, _mb(title))) if num else _mb(title)
    rows = [head]
    rows.append(_fmt_facts(l, full_date=True, person=False))
    money = []
    spots = _fmt_spots(l)
    if spots:
        money.append(spots)
    pt = l.get("payment_terms")  # C12: terms are part of the public listing face
    if isinstance(pt, dict):
        if pt.get("rail") == "instant":
            money.append("%s instant rail - settled at booking, no refund window" % _G_INSTANT)
        else:
            _dep = " · deposit %s" % pt["deposit_required"] if pt.get("deposit_required") else ""
            money.append("%s protected · refund window %sh%s" % (_G_ESCROW, pt.get("refund_window_hours", "?"), _dep))
    if money:
        rows.append(" · ".join(money))
    if l.get("require_verified_buyer"):  # C11: the gate is part of the public face
        rows.append("%s verified buyers only - Tier-2 Midnight sign-in required to book" % _G_OK)
    if l.get("description"):
        d = str(l["description"]).strip()
        rows.append("%s %s" % (_G_QUOTE, d[:100] + "…" if len(d) > 100 else d))
    if l.get("url"):
        rows.append("%s %s" % (_G_LINK, l["url"]))
    return rows


def _fmt_listing(l: dict, num=None) -> str:
    """Level-2 card - ONE fixed shape on every surface (webchat, Agentverse
    wrapper, CLI share this brain). Horizontal knot rules + seams only, no
    side rails, so it aligns in every chat with the bold letters intact."""
    return _frame(None, [_listing_rows(l, num)])


_RICH_KEYS = ("title", "category", "date", "price", "location", "capacity",
              "description", "tags", "url", "merchant", "vertical", "provider",
              "duration_minutes", "receive", "verified_only")  # S6: receive = instant-rail payout wallet (0x...); C11: verified_only = Tier-2 buyer gate


def _parse_kv_inline(body: str) -> dict | None:
    """F5b (2026-09-20): single-line `key: value key: value ...` form. Returns
    a rich dict when at least one known key is present — text before the first
    key becomes the title — else None (quick pipe / bare-title fallthrough)."""
    hits = [(m.start(), m.group(1).lower()) for m in
            re.finditer(r"(?<![a-z_])(%s)\s*:" % "|".join(_RICH_KEYS), body, re.I)]
    if not hits:
        return None
    fields: dict[str, str] = {}
    pre = body[:hits[0][0]].strip().rstrip(",;")
    if pre:
        fields["title"] = pre
    for i, (pos, k) in enumerate(hits):
        end = hits[i + 1][0] if i + 1 < len(hits) else len(body)
        v = body[pos:end].split(":", 1)[1].strip()
        if v:
            fields.setdefault(k, v)
    return fields or None


def _parse_rich(body: str) -> dict | None:
    """Parse `key: value` format (multi-line, or single-line since F5b);
    None if body isn't rich format."""
    if "\n" not in body:
        return _parse_kv_inline(body)
    fields: dict[str, str] = {}
    for ln in body.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ":" in ln:
            k, _, v = ln.partition(":")
            k = k.strip().lower()
            if k in _RICH_KEYS or re.fullmatch(r"[a-z_]{1,24}", k):  # C5: community verticals add their own keys
                fields[k] = v.strip()
                continue
        if "title" not in fields and "|" not in ln:
            fields["title"] = ln  # bare first line = title
    return fields


# B3c-accounts: per-sender chat sessions (sender -> {account_id, tokens, verified, ts}).
# In-memory, pilot-grade: a logged-in chat acts AS the account for 24h (hub TTL).
_SESSIONS = {}
_SESSIONS_CAP = 10_000  # HARDENING: bound memory vs unique-sender spam (evict oldest)
_SESSION_TTL = 24 * 3600
_ACCOUNT_CAP = 25   # verified organizers get a higher listing cap than anonymous chat


# ---- U2: conversational listing intake (owner call 2026-09-18: no forms) ----
# Per-sender guided listing: bare 'list' starts it, answers fill fields one at
# a time, 'confirm' composes the same rich text _create_listing already
# parses (one validation path — no duplicate rules), 'cancel' aborts.
_INTAKE = {}                 # sender -> {fields: {...}, ts: float}
_EVENT_CATS_FALLBACK = ["meetup", "concert", "workshop", "conference", "market",
                        "sports", "community", "party", "exhibition", "other"]
_CATS_CACHE: dict = {}       # vertical -> (ts, [cats])


def _valid_categories(hub_url: str, vertical: str = "events") -> list | None:
    """F3 (2026-09-20): the hub's valid categories for a vertical (cached
    10 min). None on error — validation then fails open to the hub's own
    honest reject, never blocks a listing on a chat-side outage."""
    now = time.time()
    hit = _CATS_CACHE.get(vertical)
    if hit and now - hit[0] < 600:
        return hit[1]
    try:
        d = _hub_get(hub_url, "/verticals")
        cats = [str(c).strip().lower() for c in
                ((d.get("verticals") or {}).get(vertical) or {}).get("categories", [])]
        if not cats:
            return None
        _CATS_CACHE[vertical] = (now, cats)
        return cats
    except Exception:
        return None
_INTAKE_CAP = 500            # bounded like _LAST_RESULTS
_INTAKE_TTL = 15 * 60        # idle intake dies after 15 minutes
_INTAKE_STEPS = [            # guided order; title+price are the only musts
    ("title", "the name of your thing", "Rooftop Jazz Night"),
    ("price", "what it costs in EUR (0 = free)", "15"),
    ("date", "when it happens (YYYY-MM-DD, or 'any')", "2026-10-03"),
    ("location", "where (city or address, or 'any')", "Vienna"),
    ("category", "type of thing (concert, workshop, food, repair, ...)", "concert"),
    ("capacity", "how many people fit (seats, spots...)", "50"),
    ("description", "a short pitch — what happens, what to expect", "Live jazz on a rooftop, one set, drinks at the bar"),
]


def _intake_get(sender: str):
    s = _INTAKE.get(sender)
    if s and (time.time() - s.get("ts", 0)) > _INTAKE_TTL:
        _INTAKE.pop(sender, None)
        return None
    return s


def _intake_put(sender: str, fields: dict):
    if len(_INTAKE) >= _INTAKE_CAP and sender not in _INTAKE:
        for k in sorted(_INTAKE, key=lambda k: _INTAKE[k].get("ts", 0))[:len(_INTAKE) // 10]:
            _INTAKE.pop(k, None)
    _INTAKE[sender] = {"fields": fields, "ts": time.time()}
    storage.draft_put(sender, fields)  # W2 item 11: durable shadow, best-effort


def _intake_next_question(fields: dict) -> str:
    """The next unfilled step's question, with a progress line."""
    skipped = set(fields.get("__skipped", []))
    for i, (key, what, example) in enumerate(_INTAKE_STEPS):
        if not fields.get(key) and key not in skipped:
            done = sum(1 for k, _, _ in _INTAKE_STEPS if fields.get(k) or k in skipped)
            return (f"[{done + 1}/{len(_INTAKE_STEPS)}] {what}?\n"
                    f"(example: {example} — or 'skip', 'cancel')")
    return ""


# Owner report 2026-09-22: mid-wizard questions ('dont we need more detail?',
# 'what categories are there?') were eaten as field answers and the category
# wall rejected every conversational phrasing robotically. Middle-ground law:
# data-shaped fields keep their validators; anything conversational gets a
# warm answer and the wizard re-asks.
_INTAKE_Q_RX = re.compile(
    r"\?\s*$|^(?:what|whats|which|why|how|when|where|who|can|could|should|"
    r"do|does|did|is|are|dont|don't|doesnt|doesn't|tell|explain|wait|hm+|"
    r"maybe|perhaps|not sure|isn't|isnt|aren't|arent)\b", re.I)


_JAILBREAK_RX = re.compile(
    r"(ignore|disregard|forget|bypass)\b.{0,40}\b(rules?|instructions?|prompt)\b"
    r"|\b(system )?prompt\b|\breveal (your )?(prompt|instructions)\b"
    r"|\byou are now\b|\bpretend (to be|you are)\b|\bact as\b", re.I)


def _loose_price(text):
    """Loose price capture: 'actually it should be free', 'no sorry, 5 euros'."""
    t = (text or "").lower()
    if re.search(r"\bfree\b|\bno charge\b", t):
        return "0"
    m = re.search(r"(\d{1,4}(?:[.,]\d{1,2})?)\s*(?:euros?|eur\b|€)", t)
    if m:
        return m.group(1).replace(",", ".")
    m = re.search(r"\bprice\b[^0-9]{0,16}(\d{1,4}(?:[.,]\d{1,2})?)", t)
    if m:
        return m.group(1).replace(",", ".")
    return None


def _loose_date(text):
    """ISO date embedded in a sentence: 'lets say 2026-10-05'."""
    m = re.search(r"\b(20\d{2}-\d{2}-\d{2})\b", text or "")
    return m.group(1) if m else None


_WEEKDAYS = {"monday": 0, "montag": 0, "tuesday": 1, "dienstag": 1,
             "wednesday": 2, "mittwoch": 2, "thursday": 3, "donnerstag": 3,
             "friday": 4, "freitag": 4, "saturday": 5, "samstag": 5,
             "sunday": 6, "sonntag": 6}


def _resolve_relative_date(text):
    """R4 battery: 'next friday', 'tomorrow', '31.12.2026' -> ISO date;
    None when the text is not a resolvable date phrase."""
    import datetime as _dtm
    t = (text or "").strip().lower()
    today = _dtm.date.today()
    m = re.fullmatch(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)
    if m:
        try:
            return _dtm.date(int(m.group(3)), int(m.group(2)),
                             int(m.group(1))).isoformat()
        except ValueError:
            return None
    if t in ("today", "heute"):
        return today.isoformat()
    if t in ("tomorrow", "morgen"):
        return (today + _dtm.timedelta(days=1)).isoformat()
    m = re.fullmatch(
        r"next (monday|tuesday|wednesday|thursday|friday|saturday|sunday"
        r"|montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)", t)
    if m:
        delta = (_WEEKDAYS[m.group(1)] - today.weekday()) % 7
        if delta == 0:
            delta = 7
        return (today + _dtm.timedelta(days=delta)).isoformat()
    return None


def _loose_capacity(text):
    """Headcount phrases: 'ehh 20 people', 'room for 30'."""
    m = re.search(r"(\d{1,4})\s*(?:people|persons?|spots?|seats?|guests?|pax\b)",
                  text or "", re.I)
    return m.group(1) if m else None


def _intake_clarify(hub_url: str, key: str, fields: dict) -> str:
    """Answer a question/aside mid-wizard warmly, then re-ask the step.
    Never consumes the turn as a field value."""
    nl = chr(10)
    if key == "category":
        cats = _valid_categories(hub_url) or _EVENT_CATS_FALLBACK
        body = ("Happy to explain! A listing needs a type so people can find it "
                "-- pick whichever fits: " + ", ".join(cats) + ". "
                "A yoga class usually fits workshop or community; not sure? "
                "Skip makes it other.")
    elif key == "date":
        body = ("Happy to help! The wizard walks through: title, price, date, place, "
                "type, capacity, pitch. Only the title is truly required; skip the rest. "
                "For the date: 2026-10-03 style, or any if it has no fixed date.")
    else:
        body = ("Happy to help! The wizard walks through: title, price, date, place, "
                "type, capacity, pitch. Only the title is required; skip the rest.")
    return body + nl + nl + _intake_next_question(fields)

def _intake_reply(hub_url: str, sender: str, text: str) -> str | None:
    """Conversational listing intake. Returns a reply string, or None when
    the message isn't intake-related (caller falls through to normal routing).
    Non-destructive: the one-shot 'list | ...' syntax (agents) is untouched —
    only bare 'list' starts the guided flow, and any 'list ...' with fields
    still goes straight to _create_listing."""
    t = (text or "").strip()
    low = t.lower()
    s = _intake_get(sender)

    # --- start: bare 'list' only ---
    if low == "list":
        if s:
            q = _intake_next_question(s["fields"])
            if q:
                return "We're already listing something. " + q
            return _intake_preview(s["fields"])
        # W2 item 11: restart recovery (G2) — hot store died (restart/TTL);
        # a durable draft resumes silently instead of starting over.
        d = storage.draft_get(sender)
        if d:
            _intake_put(sender, d)
            q = _intake_next_question(d)
            return ("Picking up where we left off — " + q) if q else _intake_preview(d)
        _intake_put(sender, {})
        return ("\u2728 Let's list it. I'll ask a few things — answer each in one line.\n"
                + _intake_next_question({}))

    if not s:
        # W2 item 11: orphan-confirm resume — on bare confirm/without hot store,
        # resume a durable draft if one exists; otherwise reply honestly.
        if low in ("confirm", "done", "finish", "create it", "publish"):
            d = storage.draft_get(sender)
            if d:
                _skip1 = set(d.get("__skipped", []))
                _open1 = [k for k, _, _ in _INTAKE_STEPS
                          if not d.get(k) and k not in _skip1]
                if _open1:
                    _intake_put(sender, d)
                    return ("Picking up your draft -- still open: "
                            + ", ".join(_open1) + "."
                            + chr(10) + chr(10) + _intake_next_question(d))
                return _intake_create(hub_url, sender, d)
            return "I don't have a listing in progress — say 'list' and we'll start one."
        if low in ("cancel", "stop", "abort"):
            # R4 battery: mercury invented 'Canceled.' with nothing in progress
            return ("Nothing to cancel right now :) Say 'list' to create a "
                    "listing -- or tell me what you feel like: 'jazz tonight', "
                    "'free yoga', 'sushi'.")
        return None  # not in intake; normal routing

    # --- control words ---
    if low in ("cancel", "stop", "nevermind", "never mind", "abort"):
        _INTAKE.pop(sender, None)
        storage.draft_del(sender)  # W2 item 11: shadow dies with the draft
        return "Okay, listing cancelled. Say 'list' whenever you want to try again."
    if low in ("restart", "start over", "start from scratch"):
        # W2 item 11: clear fields, back to [1/7] — same sender, fresh draft.
        _intake_put(sender, {})
        return ("\u2728 Fresh start — let's list it again.\n"
                + _intake_next_question({}))
    if low in ("confirm", "done", "finish", "create it", "publish"):
        # R4b battery: 'confirm' at step 2/7 published a half-empty listing.
        # Same completeness law 'yes' already had: open steps first.
        _skip0 = set(s["fields"].get("__skipped", []))
        _open0 = [k for k, _, _ in _INTAKE_STEPS
                  if not s["fields"].get(k) and k not in _skip0]
        if _open0:
            return ("Almost! Still open: " + ", ".join(_open0) + "."
                    + chr(10) + chr(10) + _intake_next_question(s["fields"]))
        return _intake_create(hub_url, sender, s["fields"])
    if low in ("yes", "y"):
        # 'yes' only confirms once every step is answered or skipped
        skipped = set(s["fields"].get("__skipped", []))
        if all(s["fields"].get(k) or k in skipped for k, _, _ in _INTAKE_STEPS):
            return _intake_create(hub_url, sender, s["fields"])
        return "Not everything is answered yet — " + _intake_next_question(s["fields"])
    if low in ("skip", "no idea", "dunno", "later", "next"):
        t = ""  # mark this field skipped, ask the next

    # --- break-out commands (search/book/help/one-shot 'list ...') run
    # normally; intake survives so 'list' can resume it ---
    if _INTAKE_BREAK.match(t):
        return None

    # --- 'key: value' mid-flow corrections (e.g. 'price: 20' at the preview) ---
    ed = _intake_edit_field(sender, t)
    if ed:
        return ed

    # --- fill current step ---
    fields = dict(s["fields"])
    skipped = set(fields.pop("__skipped", []))
    for key, _, _ in _INTAKE_STEPS:
        if fields.get(key) or key in skipped:
            continue
        if t:
            v = t[:300].strip()
            nl2 = chr(10) + chr(10)
            if _JAILBREAK_RX.search(v):
                return ("I keep our house rules :) -- but finding and booking real "
                        "things is where I shine." + nl2 + _intake_next_question(fields))
            det_price = _loose_price(v)
            det_date = _loose_date(v)
            det_cap = _loose_capacity(v)
            if key == "price" and det_price is not None:
                v = det_price
            elif key == "price" and det_cap is not None:
                fields["capacity"] = det_cap
                _intake_put(sender, fields)
                return ("Got it -- room for " + det_cap + ". Still need the price: "
                        "how much in EUR? (0 = free)")
            if key == "date":
                v2 = v.lower()
                if v2 in ("any", "tbd", "flexible"):
                    v = v2
                elif det_date:
                    v = det_date
            if key == "capacity" and det_cap is not None:
                v = det_cap
            _d8 = _resolve_relative_date(v)
            if key not in ("title", "date") and _d8:
                fields["date"] = _d8
                _intake_put(sender, fields)
                return ("Noted -- " + _d8 + " saved as the date." + nl2
                        + _intake_next_question(fields))
            if key not in ("title", "description", "price") and det_price is not None:
                fields["price"] = det_price
                _intake_put(sender, fields)
                return ("Noted -- price is now " + det_price + " EUR." + nl2
                        + _intake_next_question(fields))
            if key not in ("title", "description", "price") and det_cap is not None:
                fields["capacity"] = det_cap
                _intake_put(sender, fields)
                return ("Noted -- room for " + det_cap + "." + nl2
                        + _intake_next_question(fields))
            if key not in ("title", "description", "price", "category"):
                cats0 = _valid_categories(hub_url) or _EVENT_CATS_FALLBACK
                chits = [c for c in cats0
                         if c != "other" and re.search(r"\b%s\b" % re.escape(c), v.lower())]
                if len(chits) == 1:
                    fields["category"] = chits[0]
                    _intake_put(sender, fields)
                    return ("Noted -- type: " + chits[0] + "." + nl2
                            + _intake_next_question(fields))
            if key not in ("title", "description") and _INTAKE_Q_RX.search(v):
                if _WEATHER_RX.search(v.lower()):
                    return ("Good question! I can pull a real forecast once the listing "
                            "has a date and place -- just ask 'weather' after we confirm."
                            + nl2 + _intake_next_question(fields))
                if re.search(r"\bjoke\b|\bfunny\b|\blaugh\b", v, re.I):
                    return ("Hehe -- I'm all business while we build your listing. "
                            "Ask me again after, and I'll still be here."
                            + nl2 + _intake_next_question(fields))
                return _intake_clarify(hub_url, key, fields)
            if key == "price" and det_price is None and not re.match(r"^[0-9]+([.,][0-9]+)?$", v.strip()):
                return "Price must be a number — try again (example: 15, or 0 for free)."
            if key == "date":
                _iso = _resolve_relative_date(v)
                if _iso:
                    v = _iso
            if key == "date" and re.match(r"^\d{4}-\d{2}-\d{2}$", v.lower()):
                import datetime as _dtm2
                try:
                    _yd = _dtm2.date(*map(int, v.split("-")))
                except ValueError:
                    return "Dates look like 2026-10-03 — and it must be a real date (or 'any')."
                if _yd < _dtm2.date.today():
                    return ("That date is in the past -- pick today or later "
                            "('any' works if it has no fixed date).")
            if key == "date" and not (v.lower() in ("any", "tbd", "flexible")
                                      or re.match(r"^\d{4}-\d{2}-\d{2}", v.lower())):
                return "Dates look like 2026-10-03 — or say 'any' if it has no fixed date."
            if key == "capacity" and v.strip() == "0":
                return ("Capacity 0 wouldn't leave room for anyone :) -- how "
                        "many people fit? (or 'skip' if unsure)")
            if key == "capacity" and not re.match(r"^[0-9]{1,4}$", v.strip()):
                return "Capacity must be a whole number — try again (example: 50)."
            if key == "category":
                cats = _valid_categories(hub_url) or _EVENT_CATS_FALLBACK
                vl = v.lower()
                hits = ([vl] if vl in cats else
                        [c for c in cats if c != "other" and re.search(r"\b%s\b" % re.escape(c), vl)])
                if not hits:
                    return _intake_clarify(hub_url, key, fields)
                if len(hits) > 1:
                    return ("I can see both " + " and ".join(hits) +
                            " -- which one fits best?" + nl2 +
                            _intake_next_question(fields))
                v = hits[0]  # one clear category mentioned in the sentence
            fields[key] = v
        else:
            skipped.add(key)  # explicit skip: never ask again this round
        fields["__skipped"] = sorted(skipped)
        _intake_put(sender, fields)
        q = _intake_next_question(fields)
        if q:
            return ("\u2713 " if t else "") + q
        return _intake_preview(fields)   # everything answered/skipped
    return None


def _intake_preview(fields: dict) -> str:
    """Compact recap of what will be created."""
    skipped = set(fields.get("__skipped", []))
    bits = []
    for key, _, _ in _INTAKE_STEPS:
        if fields.get(key):
            bits.append(f"{key}: {fields[key]}")
        elif key in skipped:
            bits.append(f"{key}: —")
    return ("Here's your listing:\n" + "\n".join("  " + b for b in bits) +
            "\n\nSay 'confirm' to publish it, or send changes like 'price: 20' to edit a field.")


def _intake_after_edit(fields: dict) -> str:
    """After a mid-flow edit keep the wizard MOVING: ask the next open
    question; only show the confirm preview when every step is answered or
    skipped. (Owner report 2026-09-22: 'free' at step 2 showed 'Say confirm'
    with 5 fields still missing.)"""
    q = _intake_next_question(fields)
    return (chr(0x2713) + " " + q) if q else _intake_preview(fields)


def _intake_card(fields: dict) -> dict:
    """W2 item 11: the partial listing dict carried in /api/chat's additive
    `card` field. UI renders it via makeCard in a pinned dashed preview slot;
    every intake edit re-emits it. preview=true marks it as a draft."""
    skipped = set(fields.get("__skipped", []))
    card = {}
    if fields.get("title"):
        card["title"] = fields["title"]
    try:
        card["price"] = float(fields.get("price") or 0)
    except (TypeError, ValueError):
        card["price"] = 0
    if fields.get("date") and fields["date"].lower() not in ("any", "tbd", "flexible"):
        card["date"] = fields["date"]
    if fields.get("location") and fields["location"].lower() not in ("any", "tbd", "flexible"):
        card["location"] = fields["location"]
    if fields.get("category"):
        card["category"] = fields["category"]
    if fields.get("capacity"):
        try:
            card["capacity"] = int(fields["capacity"])
        except (TypeError, ValueError):
            pass
    if fields.get("description"):
        card["description"] = fields["description"][:200]
    card["preview"] = True
    card["skipped"] = sorted(skipped)
    return card


def intake_envelope(sender: str):
    """W2 item 11: (draft, card) for /api/chat — additive reply fields for the
    web UI only (agent callers get the plain reply; envelope absent = absent
    keys, so the response shape never breaks). draft carries step/progress so
    the transcript can render an honest 'listing in progress' hint."""
    s = _intake_get(sender)
    if not s:
        return None, None
    fields = s["fields"]
    skipped = set(fields.get("__skipped", []))
    total = len(_INTAKE_STEPS)
    done = sum(1 for k, _, _ in _INTAKE_STEPS if fields.get(k) or k in skipped)
    nxt = next((k for k, _, _ in _INTAKE_STEPS if not fields.get(k) and k not in skipped), None)
    draft = {"active": True, "progress": "%d/%d" % (done, total), "step": nxt or "review"}
    complete = nxt is None
    if complete:
        draft["ready"] = True
    return draft, _intake_card(fields)


def _intake_create(hub_url: str, sender: str, fields: dict) -> str:
    """Compose the rich-format list command and run it through the SAME
    _create_listing path (one validation chain, no duplicated rules)."""
    if not fields.get("title"):
        return "A listing needs at least a title. " + _intake_next_question(fields)
    if not fields.get("price"):
        fields["price"] = "0"
    L = ["list", "title: " + fields["title"], "price: " + str(fields["price"])]
    for k in ("date", "location", "category", "capacity", "description"):
        if fields.get(k) and fields[k].lower() not in ("any", "tbd", "flexible"):
            L.append(f"{k}: " + fields[k])
    out = _create_listing(hub_url, sender, "\n".join(L))
    if out.startswith("✅ Listed!"):
        _INTAKE.pop(sender, None)
        storage.draft_del(sender)  # W2 item 11: published — shadow is done
        return out
    # F3 (2026-09-20): reject/unreachable keeps the intake alive — the seven
    # answers are not thrown away; the user fixes and re-confirms.
    return (out + "\n\nYour answers are saved — fix what went wrong "
            "('category: concert', 'price: 10', ...) and 'confirm' again, or 'cancel'.")


def _intake_edit_field(sender: str, text: str) -> str | None:
    """Handle 'price: 20' style edits while intake is active. W2 item 11 adds
    plain-language mappings: 'make it free' -> price 0, 'it's in Berlin' /
    'in Berlin' -> location."""
    s = _intake_get(sender)
    if not s:
        return None
    t = (text or "").strip()
    low = t.lower()
    if re.search(r"\b(make|set) it (free|0)\b", low) or low in (
            "it's free", "its free", "it is free", "free"):
        fields = dict(s["fields"])
        skipped = set(fields.pop("__skipped", []))
        skipped.discard("price")
        fields["price"] = "0"
        fields["__skipped"] = sorted(skipped)
        _intake_put(sender, fields)
        return "Free it is! " + _intake_after_edit(fields)
    m_place = re.match(r"^(?:it'?s )?in ([a-zA-Z][\w .'-]{1,60})$", t, re.IGNORECASE)
    if m_place:
        fields = dict(s["fields"])
        skipped = set(fields.pop("__skipped", []))
        skipped.discard("location")
        fields["location"] = m_place.group(1).strip()[:120]
        fields["__skipped"] = sorted(skipped)
        _intake_put(sender, fields)
        return _intake_after_edit(fields)
    m = re.match(r"^([a-z_]{2,20}):\s*(.+)$", t, re.IGNORECASE)
    if not m:
        return None
    key = m.group(1).lower()
    known = {k for k, _, _ in _INTAKE_STEPS}
    if key not in known:
        return None
    fields = dict(s["fields"])
    skipped = set(fields.pop("__skipped", []))
    skipped.discard(key)  # editing un-skips
    fields[key] = m.group(2)[:300].strip()
    fields["__skipped"] = sorted(skipped)
    _intake_put(sender, fields)
    return _intake_after_edit(fields)


# commands that break out of intake (they run normally; intake stays alive)
_INTAKE_BREAK = re.compile(
    r"^(?:search\b|find\b|show\b|browse\b|book\b|help\b|signup\b|login\b|logout\b|whoami\b|"
    r"account\b|status\b|my-(?:bookings|listings)\b|edit\s|delete\s|archive\s|unarchive\s|"
    r"list\s|list\n|listings\b|verify-|set-payout\b|notify\b|email-|recover\b|delete-account\b|"
    r"unsubscribe\b|home\b|reset\b)",
    re.IGNORECASE)


def _session(sender: str):
    """Return the session dict for this sender, or None if expired/absent."""
    if len(_SESSIONS) >= _SESSIONS_CAP and sender not in _SESSIONS:
        for k in sorted(_SESSIONS, key=lambda k: _SESSIONS[k].get("ts", 0))[:len(_SESSIONS) // 10]:
            _SESSIONS.pop(k, None)  # evict oldest 10%
    s = _SESSIONS.get(sender)
    if not s or time.time() - s["ts"] > _SESSION_TTL:
        _SESSIONS.pop(sender, None)
        return None
    return s



def _pow_solve(hub_url: str, kind: str):
    """HARDENING-v2: fetch a PoW challenge and burn the required CPU here.
    Returns {challenge, nonce} or None if the hub is unreachable."""
    try:
        ch = _hub_get(hub_url, f"/auth/challenge?kind={kind}")
    except Exception:
        return None
    challenge, diff = ch["challenge"], int(ch["difficulty"])
    n = 0
    while True:
        d = hashlib.sha256((challenge + str(n)).encode()).digest()
        bits = 0
        for b in d:
            if b == 0:
                bits += 8
                continue
            bits += 8 - b.bit_length()  # leading zero bits of first nonzero byte
            break
        if bits >= diff:
            return {"challenge": challenge, "nonce": n}
        n += 1


def _pubkey_of(seed_hex: str) -> str:
    """ed25519 public key (64 hex) for a 32-byte seed; '' if seed invalid."""
    try:
        sk = _EdPriv.from_private_bytes(bytes.fromhex(seed_hex))
    except Exception:
        return ""
    return sk.public_key().public_bytes(_ser.Encoding.Raw, _ser.PublicFormat.Raw).hex()


def _sign_login(hub_url: str, seed_hex: str, agent: str):
    """Challenge-response login: server proves we need no stored secret.
    Returns (status_code, body_dict)."""
    pub = _pubkey_of(seed_hex)
    if not pub:
        return None, {"error": "invalid seed (64 hex chars expected)"}
    try:
        ch = _hub_get(hub_url, f"/auth/challenge?kind=login&pubkey={pub}")
        sk = _EdPriv.from_private_bytes(bytes.fromhex(seed_hex))
        sig = sk.sign(b"everlist-login:" + ch["challenge"].encode()).hex()
        return _hub_post(hub_url, "/accounts/login", {"pubkey": pub, "agent": agent, "sig": sig})
    except urllib.error.HTTPError as ex:
        # real hub rejection (unknown pubkey, bad sig): surface the true reason,
        # never mask it as 'unreachable'
        try:
            return ex.code, json.loads(ex.read().decode())
        except Exception:
            return ex.code, {"error": f"HTTP {ex.code}"}
    except Exception:
        return None, {"unreachable": True}


def _set_session(sender: str, res: dict) -> None:
    # F5: cap enforced on the WRITE path too — a flood of successful logins
    # with unique senders must not grow _SESSIONS unboundedly between reads
    # (mirrors the _session() read-path eviction).
    if len(_SESSIONS) >= _SESSIONS_CAP and sender not in _SESSIONS:
        for k in sorted(_SESSIONS, key=lambda k: _SESSIONS[k].get("ts", 0))[:len(_SESSIONS) // 10]:
            _SESSIONS.pop(k, None)  # evict oldest 10%
    _SESSIONS[sender] = {"account_id": res.get("account_id"), "tokens": res.get("tokens", {}),
                         "verified": bool(res.get("human_verified")), "ts": time.time(),
                         "payout_pk": res.get("payout_pk"),
                         "verified_by": res.get("verified_by"),
                         "midnight_credential": res.get("midnight_credential")}

def _welcome(res: dict) -> str:
    v = ("\n✅ You are verified as human — bookings need no extra credential."
         if res.get("human_verified") else
         "\n⏳ Not yet human-verified — ask the hub operator to vouch for you (pilot).")
    return (f"✅ Welcome back! This chat now acts as account {res.get('account_id')} (24h). "
            f"Your listings: cap {_ACCOUNT_CAP}, no per-listing codes needed.{v}")


def _signup(hub_url: str, sender: str) -> str:
    """CRYPTO accounts: the seed is generated HERE and shown ONCE; the hub
    stores ONLY the public key. Nothing secret ever exists server-side."""
    pow_ = _pow_solve(hub_url, "signup")
    if pow_ is None:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    seed = os.urandom(32).hex()
    pub = _pubkey_of(seed)
    try:
        code, res = _hub_post(hub_url, "/accounts/signup", {"agent": sender, "pubkey": pub, "pow": pow_})
    except urllib.error.HTTPError as ex:
        try:
            err = json.loads(ex.read().decode()).get("error", "")
        except Exception:
            err = ""
        return f"Signup rejected: {err or ('HTTP ' + str(ex.code))}"
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if code != 201:
        return f"Signup rejected: {res.get('error') or ('HTTP ' + str(code))}"
    aid = res.get("account_id")
    code2, lres = _sign_login(hub_url, seed, sender)  # auto-login: we still hold the seed
    if code2 == 200:
        _set_session(sender, lres)
        logged = "\n✅ You are logged in here right away — list away!"
    else:
        logged = "\nLog in here with: login-seed <seed>"
    return (f"✅ Account created ({aid}) — cryptographic kind.\n\n"
            f"🔑 Your account SEED (shown ONCE — store it like a crypto seed phrase):\n"
            f"{seed}\n"
            "The hub stores ONLY your public key — it cannot leak or lose your secret. "
            "From any other chat: login-seed <seed>"
            + logged + "\n"
            "Next: 'email-bind you@example.com' enables self-service recovery, and "
            "operator vouch makes you human-verified (pilot).")



def _login(hub_url: str, sender: str, code: str) -> str:
    """Legacy code-account login (pre-crypto accounts + rotate/recover codes)."""
    if not code:
        return "Usage: login acct-xxxxxxxx  (your account code) — or login-seed <seed> for keypair accounts"
    try:
        code_st, res = _hub_post(hub_url, "/accounts/login", {"account_code": code.strip(), "agent": sender})
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if code_st != 200:
        # _hub_post RETURNS (status, body) for HTTP rejections. A failed login
        # must never mint a session (B10: a bogus code used to answer
        # 'Welcome back ... account None' and poison the chat session).
        return f"❌ {res.get('error') or 'Invalid account code. Check it and try again.'}"
    _set_session(sender, res)
    return _welcome(res)


def _login_seed(hub_url: str, sender: str, seed: str) -> str:
    """Keypair-account login: challenge-response, the seed itself is never sent."""
    seed = seed.strip().lower().removeprefix("elseed-")
    if not re.fullmatch(r"[0-9a-f]{64}", seed or ""):
        return "Usage: login-seed <64-hex seed from signup>"
    code2, res = _sign_login(hub_url, seed, sender)
    if code2 is None:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if code2 != 200:
        return f"❌ {res.get('error', 'Login failed — check the seed.')}"
    _set_session(sender, res)
    return _welcome(res)



def _email_bind(hub_url: str, sender: str, email: str) -> str:
    s = _session(sender)
    if not s:
        return "Login first (login <code>) - then 'email-bind me@example.com' attaches a recovery email."
    try:
        code2, res = _hub_post(hub_url, "/accounts/email/bind", {"email": email}, token=s["tokens"].get("list"))
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    if code2 != 200:
        return f"Email bind rejected: {res.get('error', 'unknown reason')}"
    s["pending_email"] = res.get("email")  # remember for email-code confirmation
    mode = res.get("delivery", "")
    note = ("(dev mode: code visible in hub log)" if mode == "logged" else
            "check your inbox" if mode == "sent" else f"delivery mode: {mode}")
    return (f"Verification code sent to {res.get('email')} - {note}. "
            "Confirm with: email-code <6-char code>")


def _email_code(hub_url: str, sender: str, code: str) -> str:
    s = _session(sender)
    if not s:
        return "Login first, then confirm your email code."
    try:
        pending = s.get("pending_email")
        if not pending:
            return "No email pending in this chat. First: email-bind <your email>"
        code2, res = _hub_post(hub_url, "/accounts/email/verify", {"email": pending, "code": code})
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    if code2 != 200:
        return f"{res.get('error', 'Invalid or expired code. Request a new one with email-bind <email>.')}"
    if res.get("account_id") != s.get("account_id"):
        return "That code verified a different chat's pending email. Do the bind from this chat."
    return ("Email verified - recovery enabled! If you ever lose your account code:\n"
            "  recover <your email>  -> code arrives by email\n"
            "  recover-confirm <code>  -> new account code (old one dies)")


def _recover(hub_url: str, email: str) -> str:
    if not email:
        return "Usage: recover you@example.com"
    try:
        pow_ = _pow_solve(hub_url, "recover")
        if pow_ is None:
            raise RuntimeError
        _, res = _hub_post(hub_url, "/accounts/email/recover", {"email": email, "pow": pow_})
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    mode = res.get("delivery", "")
    note = ("(dev mode: code visible in hub log)" if mode == "logged" else
            "check your inbox" if mode == "sent" else
            "a recovery code was sent if that email is bound to an account")
    return f"{note}. Then: recover-confirm <email> <code>"


def _recover_confirm(hub_url: str, email: str, code: str) -> str:
    """Recovery rotates the credential: keypair accounts get a fresh seed (shown
    ONCE, hub stores only the new pubkey); legacy code accounts get a fresh code."""
    if not email or not code:
        return "Usage: recover-confirm <email> <6-char code from the recovery email>"
    seed = os.urandom(32).hex()
    pub = _pubkey_of(seed)
    try:
        code2, res = _hub_post(hub_url, "/accounts/email/recover/confirm",
                               {"email": email, "code": code, "pubkey": pub})
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    if code2 != 200:
        return f"{res.get('error', 'Invalid or expired recovery code. Request a new one with recover <email>.')}"
    if res.get("kind") == "keypair":
        return (f"Recovered account {res.get('account_id')}!\n\n"
                f"\U0001f511 Your NEW account SEED (shown ONCE): {seed}\n"
                "Store it - and 'login-seed <seed>' to continue here.")
    return (f"Recovered account {res.get('account_id')}!\n\n"
            f"Your NEW account code (shown ONCE): {res.get('account_code')}\n"
            "Store it - and 'login <code>' to continue here.")



def _whoami(hub_url: str, sender: str) -> str:
    s = _session(sender)
    if not s:
        return ("You're chatting anonymously (per-listing codes, cap 3). "
                "'signup' creates an account; 'login-seed <seed>' or 'login <code>' restores yours.")
    payout = s.get("payout_pk")
    pline = ("payout key set ✅" if payout else
             "no payout key yet ('set-payout <64-hex coin PUBLIC key>' — your payouts are sent there)")
    vby = s.get("verified_by")
    vline = {"midnight-zk": "✅ verified: Midnight ZK credential (Tier-2)",
             "midnight-zk-revoked": "⚠️ your Midnight credential was REVOKED — verification lost",
             "admin-vouch": "✅ verified: operator vouch (pilot)"}.get(
        vby, "⏳ not human-verified yet ('verify-midnight <credential_id>' or ask the operator)")
    return (f"Logged in as {s['account_id']} · {vline} · "
            f"listing cap {_ACCOUNT_CAP} · {pline}. 'logout' to end the session here.")


def _verify_midnight(hub_url: str, sender: str, cid: str) -> str:
    """M14 Tier-2 sign-in: present a Midnight credential id; the hub checks the
    credential contract (admitted + not revoked) and marks the account
    verified_by: midnight-zk server-side."""
    s = _session(sender)
    if not s:
        return "Login first ('login <code>' / 'login-seed <seed>'), then verify-midnight."
    cid = (cid or "").strip()
    if not re.fullmatch(r"[1-9][0-9]{0,11}", cid):
        return ("Usage: verify-midnight <credential_id>\n"
                "The credential id comes from your wallet's Midnight personhood registration (M15 walkthrough).")
    code, res = _hub_post(hub_url, "/accounts/verify-midnight",
                          {"credential_id": cid}, s["tokens"].get("list"))
    if code is None:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if code == 200:
        s["verified"] = True
        s["verified_by"] = res.get("verified_by")
        s["midnight_credential"] = int(cid)
        return (f"✅ Midnight credential {cid} verified ({res.get('mode')} mode, tx …{str(res.get('evidence_tx'))[-8:]})\n"
                "You are now human-verified via Tier-2 — bookings need no extra credential.")
    if code == 409:
        return f"❌ {res.get('error', 'credential binding conflict')}"
    if code == 502:
        return f"⚠️ {res.get('error', 'verifier unavailable')} ({res.get('mode', '?')} mode) — fail-closed, nothing changed."
    if res.get("revoked"):
        s["verified"] = False
        s["verified_by"] = "midnight-zk-revoked"
        return f"❌ credential {cid} is REVOKED on-chain — verification lost (fail-closed)."
    return f"❌ {res.get('error', 'credential not verified')} ({res.get('mode', '?')} mode)"


def _set_payout(hub_url: str, sender: str, pk: str) -> str:
    s = _session(sender)
    if not s:
        return "Login first ('login <code>' / 'login-seed <seed>'), then set-payout."
    pk = pk.strip().lower()
    if not re.fullmatch(r"[0-9a-f]{64}", pk or ""):
        return ("Usage: set-payout <64-hex coin PUBLIC key>\n"
                "⚠️ PUBLIC key only — never send a secret key or seed; the hub stores public keys and never needs secrets.")
    code, res = _hub_post(hub_url, "/accounts/payout", {"payout_pk": pk}, s["tokens"].get("list"))
    if code is None:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if code != 200:
        return f"❌ {res.get('error', 'payout registration failed')}"
    s["payout_pk"] = pk
    return (f"✅ Payout key registered ({pk[:12]}…). Midnight escrow releases target this coin key.\n"
            "Keep the matching secret ONLY in your wallet — no one else will ever need it.")


def _notify_pref(hub_url: str, sender: str, arg: str) -> str:
    s = _session(sender)
    if not s:
        return "Login first ('login <code>' / 'login-seed <seed>'), then change notification settings."
    arg = arg.strip().lower()
    if arg not in ("off", "on"):
        return ("Usage: notify off | notify on\n"
                "Notifications = booking created / confirmed / refunded mails (verified email only).")
    code, res = _hub_post(hub_url, "/accounts/notify", {"notify_email": arg == "on"}, s["tokens"].get("list"))
    if code is None:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    if code != 200:
        return "x " + str(res.get("error", "could not update notification preference"))
    return ("Notifications ON: you get booking created/confirmed/refunded mails." if arg == "on"
            else "Notifications OFF: no booking mails to this account.")


def _logout(sender: str) -> str:
    if _SESSIONS.pop(sender, None):
        return "👋 Logged out. This chat is anonymous again."
    return "You weren't logged in."


def _logout_all(hub_url: str, sender: str) -> str:
    """B1: revoke every login token of this account (all chats/devices/agents)."""
    s = _session(sender)
    if not s:
        return ("Login first (login <code> or login-seed <seed>) - "
                "logout-all revokes every login of your account everywhere.")
    try:
        code2, res = _hub_post(hub_url, "/accounts/logout-all", {}, token=s["tokens"].get("list"))
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    if code2 != 200:
        return f"{res.get('error', 'Could not revoke sessions.')}"
    _SESSIONS.pop(sender, None)
    return ("🔒 Every login token of your account is revoked - on every chat, device and agent. "
            "Log in again wherever you still need access.")


def _delete_account(hub_url: str, sender: str, arg: str) -> str:
    """H7: two-step account self-deletion. Step 1 asks for the typed account id
    (intent proof against accidents); step 2 performs it and ends the session.
    The public ledger keeps its pseudonymous refs — the money trail survives."""
    s = _session(sender)
    if not s:
        return ("Login first (login <code> or login-seed <seed>) - "
                "delete-account erases YOUR logged-in account and archives its listings.")
    arg = (arg or "").strip()
    if not arg:
        s["pending_delete"] = s.get("account_id")
        aid = s.get("account_id", "?")
        return (f"⚠️ This PERMANENTLY erases account {aid}: your recovery email is deleted and "
                f"all your listings are archived (bookers keep their protected bookings).\n"
                f"Sure? Type:  delete-account confirm {aid}")
    if not s.get("pending_delete"):
        return "Safety first: run delete-account once to see what it does, then confirm."
    expected = s.get("pending_delete")
    if arg != f"confirm {expected}" and arg != expected:
        return (f"Confirmation mismatch. To erase account {expected}, type exactly:\n"
                f"delete-account confirm {expected}")
    try:
        code2, res = _hub_delete(hub_url, "/accounts/me", {"confirm": expected},
                                 token=s["tokens"].get("list"))
    except Exception:
        return "Sorry - the EverList hub is unreachable right now. Try again shortly."
    if code2 != 200:
        return f"{res.get('error', 'Could not delete the account.')}"
    _SESSIONS.pop(sender, None)
    n = res.get("listings_archived", 0)
    return (f"🗑️ Account {expected} is erased (recovery email deleted, every token revoked). "
            f"{n} listing(s) archived. The public ledger keeps its pseudonymous refs for payment auditability.")


def _create_deal(hub_url: str, sender: str, text: str) -> str:
    """P2: private escrow deal in one message (p2p vertical, visibility:private).
    Quick:  deal Bike for sale | 120 | 2026-09-20 | Vienna | secondhand
    Rich:   deal\n title: ... price: ... date: ... location: ... category: ...
            description: ... tags: a, b rail: escrow|instant refund_window: 72 deposit: 20
    Returns the listing id + one-time claim code to send the other party."""
    sender = (sender or "anonymous-chat")[:128]
    sess = _session(sender)
    cap = _ACCOUNT_CAP if sess else _LIST_CAP
    if _list_counts.get(sender, 0) >= cap:
        return (f"You've reached the pilot limit of {cap} listings "
                + ("for this account." if sess else "per agent. 'signup' raises it to 25."))
    t = text.strip()
    body = t[12:].strip() if t.lower().startswith("private deal") else t[4:].strip()
    if not body:
        return ("To open a private escrow deal:\n"
                "deal Bike for sale | 120 | 2026-09-20 | Vienna | secondhand\n"
                "or rich:\ndeal\ntitle: Bike sale\nprice: 120\ndate: 2026-09-20\n"
                "location: Vienna\ncategory: secondhand\ndescription: ...\ntags: bike\n"
                "rail: escrow  (or instant)\nrefund_window: 72\ndeposit: 20")
    rich = _parse_rich(body)
    if rich is not None:
        f = rich
    else:
        parts = [x.strip() for x in body.split("|")]
        f = {"title": parts[0] if parts else ""}
        for _k, _i in (("price", 1), ("date", 2), ("location", 3), ("category", 4)):
            if len(parts) > _i and parts[_i]:
                f[_k] = parts[_i]
    title = str(f.get("title", "")).strip()[:80]
    if not title:
        return "A deal needs a title. Example: deal Bike for sale | 120 | 2026-09-20 | Vienna | secondhand"
    try:
        price = float(str(f.get("price", "0")).strip() or 0)
    except ValueError:
        return "Price must be a number. Example: deal Bike for sale | 120 | 2026-09-20 | Vienna | secondhand"
    payload = {"vertical": "p2p", "visibility": "private", "title": title,
               "price": price, "source": "chat-agent",
               "date": (str(f.get("date", "")).strip() or "TBD"),
               "location": (str(f.get("location", "")).strip() or "TBD")}
    if f.get("category"):
        payload["category"] = str(f["category"]).strip().lower()
    if f.get("description"):
        payload["description"] = str(f["description"])[:500]
    if f.get("tags"):
        payload["tags"] = [x.strip().lower() for x in re.split(r"[,;]", str(f["tags"])) if x.strip()][:10]
    pt = {"rail": str(f.get("rail") or "escrow").strip().lower()}
    if f.get("refund_window"):
        try:
            pt["refund_window_hours"] = int(str(f["refund_window"]).strip())
        except ValueError:
            return "refund_window must be whole hours (1-720), e.g. refund_window: 72"
    if f.get("deposit"):
        try:
            pt["deposit_required"] = float(str(f["deposit"]).strip())
        except ValueError:
            return "deposit must be a number, e.g. deposit: 20"
    payload["payment_terms"] = pt
    try:
        if sess:
            token = sess["tokens"]["list"]
        else:
            _, acc = _hub_post(hub_url, "/access", {"agent": sender, "acts": ["list"]})
            token = acc["tokens"]["list"]
        status, res = _hub_post(hub_url, "/listings", payload, token=token)
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if status != 201:
        if "unknown fields" in str(res.get("error", "")):
            return ("This hub has no p2p vertical yet (community schema missing) — "
                    "use 'list' for a public listing instead.")
        return f"Deal rejected: {res.get('error') or res.get('detail') or 'unknown error'}"
    _list_counts[sender] = _list_counts.get(sender, 0) + 1
    lid = res.get("id", "?")
    claim = res.get("claim_code", "")
    mgmt = ("Owned by your account — manage it without codes." if sess
            else f"🔑 Manage code (shown ONCE): {res.get('manage_code', '')}")
    return (f"🔒 Private deal created: '{title}' — {price:g} USD (id: {lid})\n"
            f"🗝 Claim code (shown ONCE — the ONLY key to this deal): {claim}\n\n"
            f"Send the other party BOTH things: id {lid} + claim code.\n"
            f"They book via any EverList agent ('book {lid} {claim} <name>') or the SDK "
            "(booking field claim=...). The money is held safely when they book; you release it "
            "when done — if you stall past the refund window it returns to them automatically.\n"
            + mgmt)


def _create_listing(hub_url: str, sender: str, text: str) -> str:
    """One-prompt listing, two formats:
    Quick:  list Title | category | date | price | location | capacity
    Rich:   list\n title: ... \n description: ... \n tags: a, b \n url: https://...
    Only title and price are mandatory; the rest get honest defaults (events vertical)."""
    sender = (sender or "anonymous-chat")[:128]
    sess = _session(sender)
    cap = _ACCOUNT_CAP if sess else _LIST_CAP
    if _list_counts.get(sender, 0) >= cap:
        return (f"You've reached the pilot limit of {cap} listings "
                + ("for this account." if sess else "per agent. "
                   "'signup' creates an account with cap 25.") )
    body = text.strip()[4:].strip()
    rich = _parse_rich(body)
    if rich is not None:
        parts = [rich.get("title", "")]
        tail = [rich.get(k, "") for k in ("category", "date", "price", "location", "capacity")]
        parts += tail
        extra = {k: rich[k] for k in ("description", "tags", "url", "vertical",
                                      "provider", "duration_minutes", "receive", "verified_only") if rich.get(k)}
    else:
        parts = [p.strip() for p in body.split("|")]
        extra = {}
    if not parts or not parts[0]:
        return ("To list an event, send either:\n"
                "list Rooftop Jazz Night | concert | 2026-09-20 | 15 | Berlin | 50\n"
                "or rich format:\n"
                "list\ntitle: Free Surya Kriya Taster Class\ncategory: workshop\n"
                "date: 2026-09-20\nprice: 0\nlocation: Bad Tatzmannsdorf\ncapacity: 12\n"
                "description: what your class is about\ntags: yoga, free\n"
                "url: https://your-site.example\n"
                "(only title and price are required)")
    title = parts[0][:80]
    category = (parts[1].lower() if len(parts) > 1 and parts[1] else "other")
    date = parts[2] if len(parts) > 2 and parts[2] else "TBD"
    price = parts[3] if len(parts) > 3 and parts[3] else "0"
    location = parts[4] if len(parts) > 4 and parts[4] else "TBD"
    capacity = parts[5] if len(parts) > 5 and parts[5] else "20"
    try:
        float(price)
    except ValueError:
        return (f"Price must be a number, got {price!r}. "
                "Example: list Rooftop Jazz Night | concert | 2026-09-20 | 15 | Berlin | 50")
    try:
        cap = int(capacity)
    except ValueError:
        cap = 20
    if category != "other":
        _v = str(extra.get("vertical", "events")).strip().lower() or "events"
        _cats = _valid_categories(hub_url, _v)
        if _cats and category not in _cats:
            return ("Category '%s' is not valid for a %s listing. Valid: %s"
                    % (category, _v, ", ".join(_cats)))
    # mint a list token for this sender, then create the listing (owner = token principal)
    # H15: vertical is DATA - chat supports events (default) and services; the
    # hub schema (GET /verticals) decides required fields, not chat code.
    vert = str(extra.get("vertical", "events")).strip().lower()
    if vert not in ("events", "services", "classes", "jobs"):
        # C5: community verticals - ask the hub's live registry instead of hardcoding
        try:
            _known = sorted(_hub_get(hub_url, "/verticals")["verticals"].keys())
            _extra = [v for v in _known if v not in ("events", "food", "services")]  # built-ins only; food has no chat branch yet
        except Exception:
            _extra = []
        _hint = (", plus community verticals: " + ", ".join(_extra)) if _extra else ","
        return (f"Unknown vertical '{vert}'. Chat supports: events (default), services, jobs{_hint}\n"
                "Example:\nlist\nvertical: services\ntitle: Mobile Massage\n"
                "provider: Serenity Spa\nprice: 30\ncategory: wellness")
    if vert == "classes":
        # C5 reference community vertical - payload per ITS hub schema (live)
        try:
            sch = _hub_get(hub_url, "/verticals")["verticals"]["classes"]
        except Exception:
            return "Sorry - the EverList hub is unreachable right now. Try again shortly."
        payload = {"vertical": "classes", "title": title, "price": float(price),
                   "date": date, "location": location, "source": "chat-agent"}
        if category:
            payload["category"] = category
        payload["capacity"] = cap  # classes tracks capacity like events
        for k in ("instructor", "skill_level", "duration_minutes"):
            v = str(extra.get(k, "")).strip()
            if v:
                try:
                    payload[k] = int(v)  # positive_int fields; hub re-validates
                except ValueError:
                    payload[k] = v
        missing = [f for f in sch["required"] if f not in payload]
        if missing:
            return (f"Classes listings need: {', '.join(missing)}. Example:\n"
                    "list\nvertical: classes\ntitle: Morning Vinyasa\nprice: 12\n"
                    "date: 2026-09-25\nlocation: Vienna\ncapacity: 12\n"
                    "instructor: Ana\nskill_level: beginner\ncategory: yoga")
    elif vert == "services":  # C5: chained - classes branch above already built its payload
        provider = str(extra.get("provider", "")).strip()
        if not provider:
            return ("Services listings need a provider. Example:\n"
                    "list\nvertical: services\ntitle: Mobile Massage\nprovider: Serenity Spa\n"
                    "price: 30\ncategory: wellness\nlocation: Vienna\nduration_minutes: 60\n"
                    "description: what you offer")
        payload = {
            "vertical": "services", "title": title, "provider": provider,
            "price": float(price), "category": category, "source": "chat-agent",
        }
        if location and location != "TBD":
            payload["location"] = location
        try:
            payload["duration_minutes"] = int(str(extra.get("duration_minutes", "")).strip())
        except (TypeError, ValueError):
            pass
    elif vert == "jobs":  # C5 community vertical via schemas/jobs.json - payload per ITS hub schema (live)
        try:
            sch = _hub_get(hub_url, "/verticals")["verticals"]["jobs"]
        except Exception:
            return "Sorry - the EverList hub is unreachable right now. Try again shortly."
        payload = {"vertical": "jobs", "title": title, "price": float(price),
                   "date": date, "location": location, "source": "chat-agent"}
        if category:
            payload["category"] = category
        payload["capacity"] = cap  # jobs tracks capacity: worker slots
        try:
            payload["duration_minutes"] = int(str(extra.get("duration_minutes", "")).strip())
        except (TypeError, ValueError):
            pass
        missing = [f for f in sch["required"] if f not in payload]
        if missing:
            return (f"Jobs listings need: {', '.join(missing)}. Example:\n"
                    "list\nvertical: jobs\ntitle: Barista for one morning\nprice: 45\n"
                    "date: 2026-10-02\nlocation: Berlin\ncapacity: 2\ncategory: shift\n"
                    "duration_minutes: 240")
    elif vert == "events":
        payload = {
            "vertical": "events", "title": title, "category": category,
            "date": date, "price": float(price), "location": location,
            "capacity": cap, "source": "chat-agent",
        }
    else:  # unreachable while the whitelist gate above holds - stay honest if it ever drifts
        return "Internal routing error: no listing builder for this vertical. Please report it."
    if extra.get("description"):
        payload["description"] = extra["description"][:500]
    if extra.get("url"):
        payload["url"] = extra["url"][:300]
    if extra.get("tags"):
        payload["tags"] = extra["tags"]
    # S6-L1: optional instant-rail receive wallet; the hub validates the 0x format
    if extra.get("receive"):
        payload["receive_addr"] = str(extra["receive"]).strip()[:64]
    # C12: chat merchants can set payment terms in rich format
    # (rail: escrow|instant, refund_window: hours, deposit: amount)
    if any(extra.get(k) for k in ("rail", "refund_window", "deposit")):
        _rail = str(extra.get("rail") or "escrow").strip().lower()
        _ptc = {"rail": _rail}
        if extra.get("refund_window"):
            try:
                _ptc["refund_window_hours"] = int(str(extra["refund_window"]).strip())
            except ValueError:
                return "refund_window must be a whole number of hours (1-720), e.g. 'refund_window: 72'"
        if extra.get("deposit"):
            try:
                _ptc["deposit_required"] = float(str(extra["deposit"]).strip())
            except ValueError:
                return "deposit must be a number, e.g. 'deposit: 5'"
        payload["payment_terms"] = _ptc
    # C11 (SPEC section 22): verified_only: yes|no - strict parse; anything else
    # refuses rather than silently flipping the Tier-2 buyer gate.
    _rvb = str(extra.get("verified_only") or "").strip().lower()
    if _rvb:
        if _rvb not in ("yes", "no", "true", "false"):
            return ("verified_only must be yes or no, e.g. 'verified_only: yes' - "
                    "it restricts booking to Tier-2-verified accounts (verify-midnight)")
        payload["require_verified_buyer"] = _rvb in ("yes", "true")
    try:
        if sess:
            token = sess["tokens"]["list"]   # sub=acct-<id>: listing owned by the ACCOUNT
        else:
            _, acc = _hub_post(hub_url, "/access", {"agent": sender, "acts": ["list"]})
            token = acc["tokens"]["list"]
        status, res = _hub_post(hub_url, "/listings", payload, token=token)
    except Exception:
        import sys, traceback
        traceback.print_exc(file=sys.stderr)
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if status != 201:
        return f"Listing rejected: {res.get('error') or res.get('known') or 'unknown error'}"
    _list_counts[sender] = _list_counts.get(sender, 0) + 1
    if sess:
        return (f"✅ Listed! '{res.get('title', title)}' is live (id: {res.get('id')}). "
                f"Anyone can find it with 'search'. "
                f"({_list_counts[sender]}/{_ACCOUNT_CAP} listings used)\n"
                f"Owned by your account — edit/delete anytime, no code needed: "
                f"'edit {res.get('id')} price: 5' or 'delete {res.get('id')}'")
    code = res.get("manage_code", "")
    return (f"✅ Listed! '{res.get('title', title)}' is live (id: {res.get('id')}). "
            f"Anyone can find it with 'search'. "
            f"({_list_counts[sender]}/{_LIST_CAP} listings used)\n\n"
            f"🔑 Your manage code (shown ONCE — store it!): {code}\n"
            f"It owns the listing: 'edit {res.get('id')} <code> ...' or 'delete {res.get('id')} <code>'. "
            f"Tip: 'signup' gives you an account (cap 25, no codes).")


def _owned_listing(hub_url: str, sender: str, body: str, action: str) -> str:
    """Edit/delete with two credential modes:
    logged-in account:  edit <id> field: value [...]        (session token IS the proof)
    anonymous chat:     edit <id> <manage_code> field: value [...]"""
    sess = _session(sender)
    bits = body.split(None, 2)  # [id, code?, rest?] / [id, rest?] when logged in
    lid = bits[0].strip() if bits else ""
    if not lid:
        return (f"Usage: {action} <listing_id>"
                + ("" if sess else " <manage_code>")
                + (" field: value [...] (e.g. price: 5, capacity: 30)" if action == "edit" else ""))
    payload = {"action": action}
    code = ""
    if sess:
        rest = body[len(lid):].strip()          # everything after id = edit fields
    else:
        code = bits[1].strip() if len(bits) > 1 else ""
        rest = bits[2] if len(bits) > 2 else ""
        payload["manage_code"] = code
    if action == "edit":
        rich = _parse_rich(rest) or {}
        # also accept single-line 'field: value' pairs (e.g. 'edit ev-12 price: 5 capacity: 30')
        if not rich:
            for m in re.finditer(r"(title|description|price|location|date|capacity|category|tags|url)\s*:\s*([^:]+)(?=\s+\w+\s*:|$)", rest):
                rich[m.group(1)] = m.group(2).strip()
        for k in ("title", "description", "price", "location", "date", "capacity", "category", "tags", "url"):
            if rich.get(k):
                payload[k] = rich[k]
        if len(payload) == (2 if not sess else 1):
            return ("Nothing to change. Example: "
                    + (f"edit {lid} price: 5 capacity: 30" if sess else f"edit {lid} mgr-abc123 price: 5"))
    try:
        if sess:
            token = (sess.get("tokens") or {}).get("list")  # sub=acct-<id>: hub checks account ownership
            if not token:
                return "Session expired — 'login <account_code>' again, or use your manage code."
        else:
            _, acc = _hub_post(hub_url, "/access", {"agent": sender, "acts": ["list"]})
            token = acc["tokens"]["list"]
        status, res = _hub_post(hub_url, f"/listings/{urllib.parse.quote(lid)}/manage", payload, token=token)
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if status == 401:
        return "Session expired — 'login <account_code>' again, or use your manage code."
    if status == 403:
        return ("❌ Not authorized: wrong manage code (shown once at creation), "
                "or the listing belongs to another account.")
    if status != 200:
        return f"Rejected: {res.get('error') or 'unknown error'}"
    if action == "delete":
        _list_counts[sender] = max(0, _list_counts.get(sender, 1) - 1)
        return f"🗑️ Listing {lid} deleted. Slot freed ({_list_counts[sender]}/{_ACCOUNT_CAP if sess else _LIST_CAP} used)."
    if action == "archive":
        return f"📁 Listing {lid} archived — hidden from search; existing bookings stay fulfillable. 'unarchive {lid}' restores it."
    if action == "unarchive":
        return f"📂 Listing {lid} unarchived — visible again."
    return f"✅ Updated {lid}: changed {', '.join(res.get('fields', []))}."


def _my_listings(hub_url: str, sender: str) -> str:
    sess = _session(sender)
    sender_n = (sender or "anonymous-chat")[:128]
    _tok = (sess or {}).get("tokens", {}).get("list")
    try:
        data = _hub_get(hub_url, "/listings", token=_tok)
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    mine = [l for l in (data.get("listings") or [])
            if str(l.get("owner", "")) == (sess["account_id"] if sess else sender_n)]
    if not mine:
        return "You have no listings yet. Create one with 'list ...'"
    lines = [f"• {l['title']} (id: {l['id']}, price {l.get('price')} USD)" for l in mine]
    tail = "\n\nEdit: 'edit <id>" + ("' (no code — account session)" if sess else " <code>'") \
           + " · Delete: 'delete <id>" + ("'" if sess else " <code>'")
    return (f"Your listings ({len(mine)}):\n" + "\n".join(lines) + tail)


def _rate_booking(hub_url: str, sender: str, arg: str) -> str:
    """C4: buyer rates a SETTLED booking 1-5, once. Logged-in: session token.
    Anonymous: re-mint /access for this chat's agent address (the same
    deterministic principal that made the booking)."""
    bits = (arg or "").split()
    if len(bits) != 2 or not bits[1].isdigit() or not (1 <= int(bits[1]) <= 5):
        return "Usage: rate <booking_id> <1-5> — e.g. 'rate bk-abc123 5' (possible after the organizer confirms, or on free bookings)"
    bid, val = bits[0], int(bits[1])
    s = _session(sender)
    token = (s or {}).get("tokens", {}).get("book") or (s or {}).get("tokens", {}).get("list")
    if not token:
        try:
            acc = _hub_post(hub_url, "/access", {"agent": sender, "acts": ["book"]})
            token = (acc[1] or {}).get("tokens", {}).get("book")
        except Exception:
            return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if not token:
        return "Could not authenticate you — try 'login <account_code>'."
    status, res = _hub_post(hub_url, f"/book/{urllib.parse.quote(bid)}/rate", {"rating": val}, token=token)
    if status == 200:
        agg = res.get("aggregate") or ""
        return f"⭐ Thanks! You rated {bid}: {val}/5." + (f" {agg}" if agg else "")
    if status == 401:
        return "Session expired — 'login <account_code>' again."
    if status == 403:
        return "❌ Only the booking's buyer can rate it."
    if status == 409:
        return f"Rejected: {res.get('error', 'not possible for this booking')}"
    if status == 404:
        return f"No booking '{bid}' is visible to you."
    if status == 400:
        return f"Rejected: {res.get('error', 'rating must be 1-5')}"
    return f"Could not rate (HTTP {status})."


def _my_bookings(hub_url: str, sender: str) -> str:
    """C3: principal-scoped booking list (hub GET /bookings). Logged-in:
    session token. Anonymous: re-mint /access for this chat's agent address
    (deterministic principal — same pattern as 'booking <id>')."""
    s = _session(sender)
    token = (s or {}).get("tokens", {}).get("book") or (s or {}).get("tokens", {}).get("list")
    note = ""
    if not token:
        try:
            acc = _hub_post(hub_url, "/access", {"agent": sender, "acts": ["book"]})
            token = (acc[1] or {}).get("tokens", {}).get("book")
            note = " (as this chat's agent identity)"
        except Exception:
            return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    if not token:
        return "Could not authenticate you — try 'login <account_code>'."
    try:
        data = _hub_get(hub_url, "/bookings", token=token)
    except urllib.error.HTTPError as e:
        if e.code == 401:
            return "Session expired — 'login <account_code>' again."
        return f"Could not fetch bookings (HTTP {e.code})."
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    mine = data.get("bookings") or []
    if not mine:
        return ("You have no bookings yet. Browse with 'search' and book with "
                "'book <id> <name>' — free listings book instantly.")
    lines = []
    for b in mine[:10]:
        qty = b.get("quantity", 1)
        qty_s = f" x{qty}" if qty > 1 else ""
        lines.append(f"• {b.get('id')} — {b.get('listing_id')} | {b.get('escrow', '?')} | "
                     f"{b.get('amount', 0)} USD{qty_s}")
    more = f"\n(+{len(mine) - 10} more)" if len(mine) > 10 else ""
    return (f"Your bookings ({len(mine)}){note}:\n" + "\n".join(lines) + more
            + "\n\nPoll one: 'booking <id>' — shows payment status.")


_FILLER_WORDS = {"find", "me", "a", "an", "the", "for", "please", "show", "us", "under", "over",
                 "something", "anything", "want", "looking", "i", "we", "to", "do",
                 "in", "on", "at", "my", "under", "around"}


def _show_results(hub_url: str, sender: str, arg: str) -> str:
    """C9c pagination: '1', '2-6', 'all' replay the last search as framed cards,
    each numbered by its position in that search (the number is the book handle)."""
    sel = (arg or "").strip().lower()
    results = _LAST_RESULTS.get(sender) or []
    if not results:
        return "Nothing to show yet — run a search first (e.g. 'search jazz')."
    if sel == "all":
        if len(results) > _HARD_CAP:
            blocks = [_listing_rows(x, i + 1) for i, x in enumerate(results[:_HARD_CAP])]
            return (_frame("From your last search (first %d of %d):" % (_HARD_CAP, len(results)), blocks)
                    + "\nRefine with 'search <keyword> under <price>' to narrow further.")
        picks, hidden, start = results, 0, 1
    elif re.fullmatch(r"\d+", sel):
        i = int(sel)
        if not 1 <= i <= len(results):
            return f"No result {i} — the last search found {len(results)}."
        picks, hidden, start = [results[i - 1]], len(results) - 1, i
    elif re.fullmatch(r"\d+\s*-\s*\d+", sel):
        a, b = (int(x) for x in sel.split("-"))
        a, b = min(a, b), max(a, b)
        if a < 1 or b > len(results):
            return f"Range out of bounds — the last search found {len(results)}."
        picks, hidden, start = results[a - 1:b], len(results) - (b - a + 1), a
    else:
        return "Say a number ('3'), a range ('2-6') or 'all' from your last search."
    blocks = [_listing_rows(x, start + i) for i, x in enumerate(picks)]
    out = _frame("From your last search (%d result(s)):" % len(results), blocks)
    if hidden:
        out += "\n(%d more — say 'all' or a range like '2-6'.)" % hidden
    return out


def _human_date(iso: str) -> str:
    """'2026-09-20' -> 'Sat 20 Sep' (year only when not this year). Tolerant."""
    import datetime as _dtm
    try:
        d = _dtm.date.fromisoformat((iso or "").strip()[:10])
        s = d.strftime("%a %d %b").replace(" 0", " ")
        if d.year != _dtm.date.today().year:
            s += " %d" % d.year
        return s
    except Exception:
        return iso or ""


def _smart_search(hub_url: str, text: str, sender: str = "") -> str:
    """Natural-language search: 'find me a free yoga class' -> max_price=0 + word match.
    Multi-word queries union per-word matches (hub q is substring-AND by design)."""
    low = text.strip().lower()
    free = "free" in low.split()
    # C2 structured qualifiers, parsed OUT of the keyword text (regex spans so
    # dates/prices survive intact; qualifiers AND-combine in the hub):
    qual: dict[str, str] = {}

    def _take(pattern: str, key: str, group: int = 1) -> None:
        nonlocal low
        m = re.search(pattern, low)
        if m:
            qual[key] = m.group(group).replace(",", ".") if key.endswith("_price") else m.group(group)
            low = (low[:m.start()] + " " + low[m.end():]).strip()

    _take(r"\bunder\s+(\d+(?:[.,]\d+)?)", "max_price")
    _take(r"\bover\s+(\d+(?:[.,]\d+)?)", "min_price")
    _take(r"\bfrom\s+(\d{4}-\d{2}-\d{2})", "from")
    _take(r"\b(?:until|till|by)\s+(\d{4}-\d{2}-\d{2})", "to")
    if re.search(r"\bcheapest\b", low):
        qual["sort"] = "price"
        low = re.sub(r"\bcheapest\b", " ", low)
    if re.search(r"\b(soonest|earliest)\b", low):
        qual["sort"] = "date"
        low = re.sub(r"\b(?:soonest|earliest)\b", " ", low)
    params = ([] + (["max_price=0"] if free else []))
    for k in ("max_price", "min_price", "from", "to", "sort"):
        if k in qual:
            params.append(k + "=" + urllib.parse.quote(qual[k]))
    words = [w for w in low.replace(",", " ").split()
             if w not in _FILLER_WORDS and w != "free" and w not in ("search", "find", "listings", "events", "show")]
    try:
        data = _hub_get(hub_url, "/search" + (("?" + "&".join(params)) if params else ""))
        base = data.get("listings") or []
        if words:
            seen: dict[str, dict] = {}
            for w in words[:3]:
                d2 = _hub_get(hub_url, "/search?" + "&".join(params + ["q=" + urllib.parse.quote(w)]))
                for l in (d2.get("listings") or []):
                    seen.setdefault(l.get("id"), l)
            listings = list(seen.values())
        else:
            listings = base
    except urllib.error.HTTPError as ex:
        # B7 honesty: real hub rejections (e.g. q too long) must not masquerade
        # as 'unreachable' — surface the actual reason.
        try:
            err = json.loads(ex.read().decode()).get("error", "")
        except Exception:
            err = ""
        return f"Search rejected: {err or ('HTTP ' + str(ex.code))}"
    except Exception:
        return "Sorry — the EverList hub is unreachable right now. Try again shortly."
    parts = ([] + (["free only"] if free else []))
    if "max_price" in qual:
        parts.append("under " + qual["max_price"])
    if "min_price" in qual:
        parts.append("over " + qual["min_price"])
    if "from" in qual:
        parts.append("from " + _human_date(qual["from"]))
    if "to" in qual:
        parts.append("until " + _human_date(qual["to"]))
    if qual.get("sort") == "price":
        parts.append("cheapest first")
    if qual.get("sort") == "date":
        parts.append("soonest first")
    qualifier = (" — " + ", ".join(parts)) if parts else ""
    if not listings:
        sug = ""
        try:
            import datetime as _dt
            up = None
            try:
                up = _hub_get(hub_url, "/search?sort=date&from=" + _dt.date.today().isoformat()).get("listings")
            except Exception:
                up = _hub_get(hub_url, "/search?sort=date").get("listings")
            up = [l for l in (up or []) if l.get("id")][:3]
            if up:
                # Owner battery 2026-09-22: suggested listings must be
                # referenceable ('tell me more about the first one') -- stash
                # them as the sender's results, same shape as a real search.
                if len(_LAST_RESULTS) > 500:
                    for k in list(_LAST_RESULTS)[:len(_LAST_RESULTS) - 500]:
                        _LAST_RESULTS.pop(k, None)
                        _LAST_SEARCH.pop(k, None)
                _LAST_RESULTS[sender] = up
                _LAST_SEARCH[sender] = {
                    "q": " ".join(words) if words else "",
                    "filters": {**({"free": True} if free else {}),
                                **{k: (float(v) if k.endswith("_price") else v) for k, v in qual.items()}}}
                rows = "\n".join(
                    "• %s — %s · say 'show %s'" % (
                        _mb(str(l.get("title") or "?")),
                        _human_date(str(l.get("date") or l.get("start") or "")),
                        l.get("id"))
                    for l in up)
                sug = ("\n\nMeanwhile, here's what's coming up:\n" + rows
                       + "\nSay 'search all' to browse everything.")
        except Exception:
            sug = ""
        if sug:
            return f"Nothing matched{qualifier} — no worries! 🌱{sug}"
        return (f"Nothing matched{qualifier} — but new things are posted all the "
                "time! 🌱 Try a broader search like 'jazz' or 'yoga', drop a "
                "filter ('search all'), or ask me for "
                "'something free this weekend'.")
    if len(_LAST_RESULTS) > 500:
        # F8: evict the OLDEST sender's stash (insertion order) — never wipe
        # every user's follow-up state because the cap was hit
        for k in list(_LAST_RESULTS)[:len(_LAST_RESULTS) - 500]:
            _LAST_RESULTS.pop(k, None)
            _LAST_SEARCH.pop(k, None)
    _LAST_RESULTS[sender] = listings
    _LAST_SEARCH[sender] = {
        "q": " ".join(words) if words else "",
        "filters": {**({"free": True} if free else {}),
                    **{k: (float(v) if k.endswith("_price") else v) for k, v in qual.items()}}}
    n = len(listings)
    head = "%s %s · %d found%s" % (_G_MARK, _mb("EverList"), n, qualifier)
    tail = "\nTo book one, say 'book <n>' - $0 listings book without payment."
    if n <= _INLINE_LIMIT:
        return _frame(head, [_listing_rows(l, i + 1) for i, l in enumerate(listings[:_HARD_CAP])]) + tail

    def _idx_line(i: int, x: dict) -> str:
        title = str(x.get("title", "?")).strip() or "?"
        return "%2d  %s · %s" % (i, _mb(title), _fmt_facts(x))

    blocks = [[_idx_line(i, x) for i, x in enumerate(listings[:_INDEX_CAP], 1)]]
    if n > _INDEX_CAP:
        blocks.append(["… and %d more - refine: 'search <keyword> under <price>'" % (n - _INDEX_CAP)])
    blocks += [_listing_rows(x, i + 1) for i, x in enumerate(listings[:_PREVIEW_CARDS])]
    return _frame(head, blocks) + tail


_HELP = (
    "Hi! I'm EverList Booking — an open marketplace with protected payments "
    "where AI agents book real things.\n\nCommands:\n"
    "• search — all listings; 'search jazz' — filtered; 'find me a free yoga class' — natural language\n"
    "• filters: under/over <price> · from/until <YYYY-MM-DD> · soonest · cheapest (combine freely)\n"
    "• list — publish something: guided chat (one question at a time), or all at once: list <title> | <category> | <date> | <price> | <location> | <capacity>\n"
    "• deal <title> | <price> | <date> | <location> | [category] — PRIVATE escrow deal; you get a one-time claim code to send the other party\n"
    "• book <id> <pvt-claim> <name> — book a private deal (claim code = the key)\n"
    "• list\n title: … description: … tags: … url: … verified_only: yes — rich listing (verified_only = Tier-2 buyer gate)\n"
    "• signup — create a keypair organizer account (seed shown ONCE; cap 25, no per-listing codes)\n"
    "• login-seed <seed> — act as your keypair account from any chat (24h)\n"
    "• login <account_code> — legacy code accounts (24h)\n"
    "• email-bind <email> / email-code <code> — enable email recovery\n"
    "• recover <email> / recover-confirm <email> <code> — recover a lost account code\n"
    "• set-payout <64-hex coin PUBLIC key> — where your payouts are sent (PUBLIC key only!)\n"
    "• verify-midnight <credential_id> — Tier-2 sign-in with your Midnight personhood credential\n"
    "• whoami — session status; logout — end session in this chat; logout-all — revoke every login\n"
    "• delete-account — erase your account (typed confirmation; listings archived, ledger refs kept)\n"
    "• my-listings — your listings\n"
    "• my-bookings — your bookings with payment status (poll one: 'booking <id>')\n"
    "• edit <id> [code] price: 5 — change your listing (code only when anonymous)\n"
    "• delete <id> [code] — remove your listing\n"
    "• archive <id> [code] / unarchive <id> [code] — hide/restore a listing (registrations kept)\n"
    "• show <id> — full listing details (description, url, availability)\n"
    "• booking <id> — check your booking's escrow status (buyer or owner)\n"
    "• rate <booking_id> <1-5> — rate a settled booking (after confirm, or free listings)\n"
    "• book <n> <name> — book listing n from your last search (FREE = instant; paid = guidance)\n"
    "• fee — how our fee model stays fair"
)


# Identity intro — handed out by the deterministic fast path in handle_text
# and by brain.respond (identity is site meta, never off-topic).
_WHOAMI = (
    "I'm the EverList assistant. I run this marketplace: I find listings, book "
    "them with protected payment, and list your own offerings — in one "
    "message, no forms.\n"
    "Try 'search jazz berlin', 'free yoga this weekend', or 'signup' to create "
    "an account. 'help' shows everything."
)

# Words that are COMMANDS/social, never keyword searches (instant fast path).
_FASTPATH_SKIP = {
    "book", "cancel", "signup", "login", "whoami", "logout", "fee", "help",
    "menu", "commands", "deal", "list", "edit", "delete", "rate", "archive",
    "unarchive", "recover", "verify", "payout", "notify", "deposit",
    "bookings", "listings", "escrow", "refund", "weather", "forecast",
    "joke", "jokes", "thanks", "thank", "ok", "okay", "cool", "nice",
    "great", "sorry", "bye", "hello", "hi", "yes", "yeah", "no", "welcome",
    # R4 battery: German phatic words -- never search material
    "hallo", "danke", "dankeschoen", "tschuess", "ciao", "moin",
    "more", "next",
    # R4b: pronouns are never search keywords ('book it' must not search 'it')
    "it", "this", "that", "them", "one",
}

# LLM-first law (owner call 2026-09-20): conversational/social shapes never
# take the instant-search fast path — they go to mercury when live, and only
# fall back to the deterministic walls when the brain cannot serve.
_SOCIAL_CONV_RX = re.compile(
    r"^(hi+|hello+|hey+|yo|hiya|hola|good (morning|afternoon|evening|night|day)"
    r"|thanks?|thank you|thx|ty|perfect|awesome|nice|great|cool|lol|lmao|bye+|"
    r"goodbye|see (ya|you)|farewell|how are you|hows it going|good night"
    r"|hallo+|guten (morgen|tag|abend)|moin|dankeschoen|danke|tschuess|ciao)"
    r"\b[!,.:;)*(/\- ]*$", re.I)

# Chat-first listing creation (owner vision; production evidence 2026-09-20:
# the brain sent a user to the dashboard — wrong, the chat 'list' flow exists).
_LISTING_HOW_RX = re.compile(
    r"\b(how|can|where)\b[^.?!]*\b(list|listing|listings|sell|offer|post)\b"
    r"|\b(make|create|add|publish|put up|set up)\b[^.?!]*\b(listing|listings|something)\b"
    r"|\blist something\b|\bsell (something|stuff|things|tickets)\b", re.I)
_LISTING_HOW = (
    "You can do it right here in chat! 💬 Just say 'list' and I'll walk you "
    "through it one question at a time — title, date, price — and your listing "
    "goes live with escrow protection. Want a private two-party deal instead? "
    "Say 'deal'."
)

# ---- Brain v2 executors (owner call 2026-09-16) --------------------------
# brain.py decides WHAT to do (one validated JSON action per turn); these
# functions DO it and own every fact: hub data, prices, weather numbers, nav
# tokens, policy text. The LLM never renders listings (SPEC: chatlib is the
# only JSON-to-sheet translator) and never writes declines or money moments.

_NAV_TOKEN = "[[nav:%s]]"

_ESCROW_EXPLAINER = (
    "✪ How the money works: when you book a paid listing, your payment is held "
    "safely — the organizer can see it's there but can't touch it.\n"
    "It's released to them after the event ends, and every listing shows its "
    "refund window before you book. Say 'search' to find something worth booking."
)


def _fee_reply(hub_url: str) -> str:
    """Fee transparency (deterministic, manifest-grounded, human wording)."""
    try:
        m = _hub_get(hub_url, "/.well-known/agent-hub.json")
        fair = m.get("fairness") or {}
        fp = fair.get("fee_policy") or {}
        declared = (m.get("payments") or {}).get("hub_fee", m.get("fee"))
        if declared is None and fp.get("actual_fee_pct") is not None:
            declared = fp["actual_fee_pct"]
        num = ""
        if declared is not None:
            if isinstance(declared, str):
                mm = re.search(r"([\d.]+)\s*%", declared)
                num = (mm.group(1) + "%") if mm else declared
            elif isinstance(declared, (int, float)):
                num = f"{declared:g}%" if abs(declared) <= 1 else f"{declared:g}"
        if num == "0%":
            fee_line = "EverList charges no service fee — the price you see is what you pay. "
        elif num:
            fee_line = (f"EverList adds a small service fee of {num} — it's shown right on "
                        "the listing before you pay, so you always see the full price up "
                        "front. ")
        else:
            fee_line = ("Any service fee is always shown right on the listing before you "
                        "pay, so you see the full price up front. ")
        return (
            "Good question — no surprises here. 💬\n"
            + fee_line
            + "Your payment is held safely when you book and only reaches the "
              "organizer after the event — and if it's cancelled inside the refund "
              "window, you get it back."
        )
    except Exception:
        return "I can't check the fee details right now — try again in a moment. 🙏"


def nav_reply(hub_url: str, target: str, sender: str) -> str:
    """Deterministic site navigation (brain action 'nav').
    home: clear the sender's search state so the board shows all listings;
    dashboard: point at the Bookings tab; results: replay the stashed cards."""
    t = (target or "home").strip().lower()
    if t not in ("home", "dashboard", "results"):
        t = "home"
    if t == "home":
        _LAST_RESULTS.pop(sender, None)
        _LAST_SEARCH.pop(sender, None)
        return (_NAV_TOKEN % "home") + (
            "🔎 The whole board is back — every live listing is up.\n"
            "Tell me what you feel like — 'jazz tonight', 'free yoga', 'sushi' — and I'll pull them out for you.")
    if t == "dashboard":
        return (_NAV_TOKEN % "dash") + (
            "🔑 Your bookings live in the Bookings tab — just opened it for you.\n"
            "In chat you can also say 'my-bookings' anytime.")
    if _LAST_RESULTS.get(sender):
        return (_NAV_TOKEN % "results") + _show_results(hub_url, sender, "all")
    return (_NAV_TOKEN % "home") + _smart_search(hub_url, "search", sender)


def brain_search(hub_url: str, sender: str, act: dict, text: str = "") -> str:
    """Execute a brain search/refine action through the deterministic core.
    Builds a canonical command from validated fields (refine merges onto the
    sender's last search spec), then reuses _smart_search for execution,
    rendering and stash bookkeeping. Bare 'cheaper' refinements honestly
    re-sort by price instead of inventing a budget."""
    q = str(act.get("q") or "").strip().lower()
    q = re.sub(r"[^\w\s-]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()[:40]
    f = act.get("filters") or {}
    spec = {"q": q, "filters": {}}
    try:
        if f.get("free") is True:
            spec["filters"]["free"] = True
        for k in ("max_price", "min_price"):
            try:
                v = float(f.get(k))
            except (TypeError, ValueError):
                continue
            if 0 <= v <= 1_000_000:
                spec["filters"][k] = v
        for k in ("from", "to"):
            v = str(f.get(k) or "")
            if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
                try:
                    _dt.strptime(v, "%Y-%m-%d")
                    spec["filters"][k] = v
                except ValueError:
                    pass
        if f.get("sort") in ("price", "date"):
            spec["filters"]["sort"] = f["sort"]
    except Exception:
        spec = {"q": q, "filters": {}}
    # refine: merge onto the last search spec (only provided fields override)
    if act.get("refine") and _LAST_SEARCH.get(sender):
        last = _LAST_SEARCH[sender]
        if not spec["q"]:
            spec["q"] = last.get("q") or ""
        for k, v in (last.get("filters") or {}).items():
            spec["filters"].setdefault(k, v)
        if not any(k in spec["filters"] for k in ("max_price", "min_price", "free")):
            # bare 'actually cheaper': honest re-sort, no invented budget
            spec["filters"]["sort"] = "price"
    parts = ["search"]
    if spec["q"]:
        parts.append(spec["q"])
    fl = spec["filters"]
    if fl.get("free"):
        parts.append("free")
    if "max_price" in fl:
        parts.append("under %g" % fl["max_price"])
    if "min_price" in fl:
        parts.append("over %g" % fl["min_price"])
    if fl.get("from"):
        parts.append("from " + fl["from"])
    if fl.get("to"):
        parts.append("until " + fl["to"])
    if fl.get("sort") == "price":
        parts.append("cheapest")
    elif fl.get("sort") == "date":
        parts.append("soonest")
    say = str(act.get("say") or "").strip()
    say = re.sub(r"https?://\S+|[*_`~#>\[\]|]", "", say).strip()
    out = _smart_search(hub_url, " ".join(parts), sender)
    if say and len(say) <= 160 and not out.startswith("Nothing matched"):
        return say + "\n" + out
    return out


_WEATHER_RX = re.compile(
    r"\b(weather|rain(?:s|ing|ed)?|temperature|forecast|sunny|cold|hot)\b", re.I)
_FEEQ_RX = re.compile(r"\bfees?\b|\bcommission\b", re.I)
_ESCROWQ_RX = re.compile(r"\bescrow\b|\brefund\b|\bmoney back\b|\bdeposit\b|\bpayment\b", re.I)


def _http_json(url: str, timeout: float = 5.0):
    """Tiny GET->dict helper for external (non-hub) JSON APIs."""
    req = urllib.request.Request(url, headers={"Accept": "application/json",
                                              "User-Agent": "everlist-chat/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _weather_reply(hub_url: str, sender: str, text: str, anchor_idx=None):
    """Weather FOR a listing the user is looking at (owner-approved
    2026-09-16). Grounded: matches a stashed listing by title overlap, then
    pulls a real forecast (Open-Meteo, no key) for its date + location.
    Returns None when there is no listing context to anchor on."""
    results = _LAST_RESULTS.get(sender) or []
    if not results:
        return None
    if anchor_idx is not None:
        if not (0 <= anchor_idx < len(results)):
            return None
        i, l = anchor_idx, results[anchor_idx]
    else:
        toks = set(re.findall(r"[a-z0-9']+", (text or "").lower()))
        best, best_score = None, 0
        for i, l in enumerate(results):
            title_toks = set(re.findall(r"[a-z0-9']+", str(l.get("title") or "").lower()))
            score = len(title_toks & toks)
            if score > best_score:
                best, best_score = (i, l), score
        if not best:
            return None
        i, l = best
    date = str(l.get("date") or "")
    loc = str(l.get("location") or "").strip()
    title = str(l.get("title") or "that event")
    if not loc:
        return None
    try:
        d = _dt.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        return None
    today = _dt.now().date()
    if d < today:
        return None
    if (d - today).days > 15:
        return ("The forecast for '%s' is too far out — forecasts reach ~16 days. "
                "Its date and place are on its card." % title)
    try:
        geo = _http_json("https://geocoding-api.open-meteo.com/v1/search?name="
                         + urllib.parse.quote(loc) + "&count=1")
        g = ((geo or {}).get("results") or [None])[0]
        if not g:
            return ("I couldn't locate '%s' on the map for a forecast — the card "
                    "still shows its date and place." % loc)
        fc = _http_json(
            "https://api.open-meteo.com/v1/forecast?latitude=%s&longitude=%s"
            "&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max"
            "&start_date=%s&end_date=%s&timezone=auto"
            % (g.get("latitude"), g.get("longitude"), date, date))
        dd = (fc or {}).get("daily") or {}
        tmax = (dd.get("temperature_2m_max") or [None])[0]
        tmin = (dd.get("temperature_2m_min") or [None])[0]
        pp = (dd.get("precipitation_probability_max") or [None])[0]
        if tmax is None:
            return None
        rng = ("%d" % round(tmin)) if (tmin is None or round(tmin) == round(tmax)) \
            else ("%d to %d" % (round(tmin), round(tmax)))
        line = "🌦 '%s' on %s in %s: %s°C" % (title, date, loc, rng)
        if pp is not None:
            line += ", %d%% chance of rain" % int(pp)
        line += (".\nThat's spot %d from your last search — say 'book %d' and "
                 "your money stays protected until the event ends." % (i + 1, i + 1))
        return line
    except Exception:
        return "I couldn't fetch the forecast just now — try again in a moment."


_ORDINALS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
             "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10}


def _resolve_listing(sender: str, which: str):
    """Resolve a brain-provided reference ('2', 'the second one', 'the jazz
    night') to (1-based index, listing) in the sender's last search, or None.
    Single-result stashes resolve regardless of text (the only thing shown)."""
    results = _LAST_RESULTS.get(sender) or []
    if not results:
        return None
    w = (which or "").strip().lower()
    m = re.search(r"\b(\d+)\b", w)
    if m:
        i = int(m.group(1))
        if 1 <= i <= len(results):
            return i, results[i - 1]
    for word, i in _ORDINALS.items():
        if word in w and 1 <= i <= len(results):
            return i, results[i - 1]
    toks = set(re.findall(r"[a-z0-9']+", w)) - {"the", "one", "a", "an", "that", "this"}
    if toks:
        best, best_score = None, 0
        for i, l in enumerate(results, 1):
            title_toks = set(re.findall(r"[a-z0-9']+", str(l.get("title") or "").lower()))
            score = len(title_toks & toks)
            if score > best_score:
                best, best_score = (i, l), score
        if best:
            return best
    if len(results) == 1:
        return 1, results[0]
    return None


def brain_show(hub_url: str, sender: str, which: str) -> str:
    """Brain action 'show': full details of one result the user means."""
    got = _resolve_listing(sender, which)
    if not got:
        return _show_results(hub_url, sender, "all")
    i, l = got
    out = _show_listing(hub_url, str(l.get("id") or ""), sender=sender)
    return out


def brain_book(hub_url: str, sender: str, which: str, who: str = "") -> str:
    """Brain action 'book': resolve the reference, then delegate to the typed
    deterministic book path (handle_text 'book <n> <name>') — escrow facts,
    PoW and account gates stay exactly where they were."""
    who = (who or "").strip()
    if not re.fullmatch(r"[\w \-.']{0,40}", who):
        who = ""
    got = _resolve_listing(sender, which)
    if not got:
        stash = _LAST_RESULTS.get(sender) or []
        if stash:
            return ("Which one do you mean? The last search found %d — say e.g. "
                    "'book the second one' or 'book 2' (plus a name to book under)." % len(stash))
        return ("Run a search first (e.g. 'search jazz'), then tell me which one "
                "to book — 'book the first one for <your-name>'.")
    i, l = got
    return handle_text(hub_url, ("book %d %s" % (i, who)).strip(), sender=sender)


def brain_meta(hub_url: str, sender: str, text: str, say: str, which: str = "") -> str:
    """Execute a brain meta action. Policy questions (fees, escrow, refunds,
    payments) always get deterministic template answers — the LLM may never
    state a policy. Weather-at-a-listing is grounded in the stash + a real
    forecast. Everything else: the sanitized LLM line (generic site truths)."""
    low = (text or "").lower()
    if _FEEQ_RX.search(low):
        return _fee_reply(hub_url)
    if _ESCROWQ_RX.search(low):
        return _ESCROW_EXPLAINER
    if _WEATHER_RX.search(low):
        anchor = (which or "") + " " + (text or "")
        got = _resolve_listing(sender, which or text)
        out = _weather_reply(hub_url, sender, anchor if not got else which or text)
        if out:
            return out
        if got:
            return ("I couldn't fetch the live forecast just now — sorry! 🙏 "
                    "Here's the event again so you have the date and place:\n"
                    + _show_results(hub_url, sender,
                                    str(got[0]) if isinstance(got, tuple) else ""))
        return (say or "").strip() or (
            "Tell me which event you mean — run a search first, then ask e.g. "
            "'weather at the jazz night' and I'll pull its date, place and forecast.")
    return (say or "").strip() or _HELP


def last_results(sender: str, cap: int = 48) -> list:
    """Public read-only view of a sender's stashed search results (raw dicts,
    same order the 'book <n>' / 'rate <n>' indexes refer to). Web UI uses this
    to open the results on the board; cap keeps payloads small."""
    return list(_LAST_RESULTS.get(sender) or [])[:cap]


def handle_text(hub_url: str, text: str, sender: str = "") -> str:
    """Public entry: delegates to _handle_text_core and logs the top-level
    turn (owner call 2026-09-18: keep all chat messages to improve the chat).
    Depth-guarded: internal re-entries (brain_book typed re-entry, fail-open
    re-entry) do NOT double-log. Logging can never break the chat."""
    _d0 = chatlog.depth_inc()
    _t0 = time.time()
    try:
        reply = _handle_text_core(hub_url, text, sender)
    except Exception as e:
        if _d0 == 0:
            chatlog.log_turn(sender, text, "", (time.time() - _t0) * 1000,
                             ok=False, error=e)
        raise
    finally:
        chatlog.depth_dec()
    if _d0 == 0:
        chatlog.log_turn(sender, text, reply, (time.time() - _t0) * 1000)
    return reply



# ---- deterministic social / semantic layer (120-input battery 2026-09-20):
# answers that must NEVER vary with the LLM live here, not in the brain. ----
_SOCIAL_GREET_RX = re.compile(
    r"^(hi+|hello+|hey+|yo|hiya|hola|good (morning|afternoon|evening|day)|moin)"
    r"( (there|everlist|friend|team|all|folks))?\b[!., :;)*(/\-]*$", re.I)
_SOCIAL_THANKS_RX = re.compile(
    r"^(thank(s| you)( so| very| a lot| so much| a million| many| mate| bro| everlist)*"
    r"|thx|ty|perfect|awesome|amazing|great job|well done|nice (work|one)|legend)"
    r"( to all)?[!., ]*$"
    r"|^(many|so|big|special|warm|huge) thanks[!., ]*$", re.I)
_SOCIAL_MOOD_RX = re.compile(
    r"^(i'?m|im|i am|feeling)?\s*(feeling \s*)?(so |very |really |pretty |kinda |"
    r"sorta |a bit |quite |super )?(bored|sad|angry|tired|lonely|stressed|down|"
    r"anxious)( (af|asf|rn|today|right now|lately|anymore|tho|though|ngl|tbh))?"
    r"[!. ]*$", re.I)
_SOCIAL_FUN_RX = re.compile(r"^(lol|lmao|haha+|hehe+|rofl)\b[!. ]*$", re.I)
_SOCIAL_HUNGRY_RX = re.compile(
    r"^(i'?m |im )?(hungry|thirsty|starving)$|^i need to eat$|^feed me$|^i want (to eat|food)$", re.I)
_ACCOUNT_HELP_RX = re.compile(
    r"\b(forgot|lost|don'?t know)\b.*\b(account|password|seed|login|log ?in|code)\b"
    r"|^how (do|can) i (log ?in|log ?in again|recover|get back (in|into))\b"
    r"|^i lost my (seed|seed phrase|recovery)\b|^can'?t (log ?in|access)\b", re.I)
_STACK_RX = re.compile(
    r"^what(?: is|'s| s| about) (x402|midnight)\b|^tell me about (x402|midnight)\b"
    r"|^explain (x402|midnight)\b|^how does (x402|midnight) work\b"
    r"|^what (is|'s) the (payment|blockchain)( layer| tech)?( here| on everlist)?\b", re.I)
_RULES_RX = re.compile(
    r"\b(show|print|reveal|dump|paste|tell me)\b.*\b(instructions|rules|prompt|system prompt)\b"
    r"|^what (are|r) (your|ur) rules\b|^your (rules|instructions|prompt)\b", re.I)
_BOT_RX = re.compile(
    r"^(are|am) you (human|real|a (robot|bot|ai|human|person|machine))\b"
    r"|^(are|am) (you )?(u )?(an? )?(ai|bot|robot|human)\?*$", re.I)
_NAVHOME_RX = re.compile(
    r"^(dashboard|home|main page|start over|start page|front page|go home|go back|"
    r"back|back (home|to (the )?(main page|start|start page|front page)))"
    r"( please)?$|(take|bring) me (back |home|to the (main page|start( page)?|front page))", re.I)
_FAREWELL_RX = re.compile(
    r"^(bye+|goodbye|good bye|see (ya|you)( later| soon| around)?|cya|later|"
    r"farewell|good night|nite|goodnight)( everlist)?[!,. ]*$", re.I)
_FAREWELL_MSG = "Bye for now! 👋 Come back when you're ready to book something fun."
_FEEBROAD_RX = re.compile(r"\bfees?\b|\bcommission\b|\bcosts?\b", re.I)
_EMOTICON_RX = re.compile(r"(?<!\d)[:;=] ?[)(dp3/|]+(?!\d)", re.I)
_TYPO_MAP = {"hlep": "help", "hepl": "help", "halp": "help", "hlp": "help",
             "helo": "hello", "hellop": "help", "heello": "hello"}
_CANCEL_Q_RX = re.compile(
    r"\b(cancel+ed?|refund)\b[^.?!]*\b(money|back|policy|window|get|do i)\b"
    r"|^can i get a refund\b|^how (do|can) i get a refund\b|^refund( please| pls)?[!. ]*$"
    r"|^get my money back\b|^what if\b[^.?!]*\bcancel", re.I)
_CANCEL_Q_MSG = (
    "If a booking is cancelled inside the listing's refund window, your "
    "escrowed money goes straight back to you — that's the point of escrow. 🛡 "
    "The window is shown on every listing before you book. You can cancel any "
    "time from 'my-bookings'.")
_ACCOUNT_HELP = (
    "No stress — here's how to get back in:\n"
    "• 'recover <your-email>' — if you bound an email, I'll send you a code\n"
    "• 'login-seed <seed>' — if you saved your signup seed (it was shown once)\n"
    "• 'signup' — start fresh if neither works\n"
    "Your bookings and listings are tied to the account, not the chat.")
_STACK_X402 = (
    "x402 is the payment layer for paid bookings: it's the web's native '402 "
    "Payment Required' turned into a real payment flow — your agent pays from "
    "its wallet and the money is protected right away. You'll mostly see it "
    "as 'payment goes through x402' on paid listings. 💳")
_STACK_MIDNIGHT = (
    "Midnight is the privacy-first blockchain EverList builds on: it powers the "
    "escrow that keeps booking money safe and the zk-personhood proofs that "
    "verify you're a real human without exposing who you are. 🛡")
_DELETE_ACC_RX = re.compile(
    r"^delete( my| the)? ?account( please| pls| plz| now)?$"
    r"|^close (my )?account( please| pls| plz| now)?$", re.I)
_DELETE_ACC_MSG = (
    "⚠️ Deleting your account is permanent, so I keep it behind a typed "
    "confirmation: type 'delete-account' exactly and follow the confirm step. "
    "Your listings get archived and the ledger keeps the payment history — "
    "that part can't be undone.")


def _social_safe_reply(low, hub_url, sender):
    """Deterministic FACTS and SAFETY guards, early tier (owner call 2026-09-20:
    LLM-first chat — conversational turns go to the brain; these programmatic
    answers stay for money/cancel policy, account recovery, stack explainers,
    delete-account guard, nav tokens, typos, junk and bare-number steering).
    Returns reply text, or None to continue."""
    bare = _EMOTICON_RX.sub(" ", low)
    bare = re.sub(r"[!?.,;: ]+$", "", bare).strip()
    bare = re.sub(r"\s+", " ", bare)
    if _SOCIAL_HUNGRY_RX.match(bare):
        return _smart_search(hub_url, "search food", sender)
    if bare in _TYPO_MAP:
        return handle_text(hub_url, _TYPO_MAP[bare], sender=sender)
    if _NAVHOME_RX.match(bare):
        return nav_reply(hub_url, "home", sender)
    if _DELETE_ACC_RX.match(bare):
        return _DELETE_ACC_MSG
    if _CANCEL_Q_RX.search(low):
        return _CANCEL_Q_MSG
    if _ACCOUNT_HELP_RX.search(low):
        return _ACCOUNT_HELP
    if _STACK_RX.match(bare):
        return _STACK_X402 if "x402" in bare else _STACK_MIDNIGHT
    if _RULES_RX.search(low):
        return ("I find, book and list real things — events, classes, food, "
                "services — with protected payment. 'help' shows every "
                "command; what can I find for you?")
    if _BOT_RX.match(bare):
        return ("I'm the EverList assistant — part software, all marketplace! 🤖 "
                "I find real things to do and book them safely, your money stays protected. What "
                "are you in the mood for?")
    # empty/whitespace: not junk — the search path answers with upcoming
    # suggestions (upgrade law: empty search stays friendly)
    if not low or not bare:
        return None
    # junk wall for SHORT mash only: emoji/punct-only, keyboard-row runs,
    # or a single <=8-char token that is one consonant pile. Long inputs and
    # phrases are real queries (B7: oversized searches must reach the hub;
    # 'crypto'/'rhythm' words have 5-consonant runs and must not be eaten).
    if ((not re.search(r"[a-z0-9]", low, re.I))
            or re.fullmatch(r"(asdf|qwer|zxcv|sdfg|dfgh|hjkl|asdfg|hjkl)\w*", bare)
            or (" " not in bare and len(bare) <= 8
                and re.search(r"[bcdfghjklmnpqrstvwxyz]{5,}", bare))
            or (len(bare) <= 120 and re.search(r"</?[a-z][a-z0-9]{0,40}>", bare))):
        return "Still here to help! What are you looking to book? 🙂"
    if re.fullmatch(r"\d+", bare) and not _LAST_RESULTS.get(sender):
        return ("Not sure what you mean by that number — do a search first, "
                "then use it like 'show 2' or 'book 2 Anna'. What are you "
                "looking for?")
    return None


def _social_instant_reply(low, hub_url, sender):
    """INSTANT tier (owner call 2026-09-20 ~18:00): phatic turns that need zero
    creativity — thanks/ok/bye/good night/lol — answered programmatically in
    0ms. The LLM is reserved for turns where variety is actually felt
    (greetings, moods, how-are-you). These can never be wrong."""
    bare = _EMOTICON_RX.sub(" ", low)
    bare = re.sub(r"[!?.,;: ]+$", "", bare).strip()
    bare = re.sub(r"\s+", " ", bare)
    if _SOCIAL_THANKS_RX.match(bare):
        return ("Anytime! 😊 When you're ready: 'jazz tonight', 'free yoga', "
                "'sushi' — say the word and I'll find it.")
    if re.search(r"good ?night", bare, re.I):
        return ("Good night! 🌙 Whenever you're next in the mood — jazz, sushi, "
                "a workshop — I'm here.")
    if _FAREWELL_RX.match(bare):
        return _FAREWELL_MSG
    if _SOCIAL_FUN_RX.match(bare):
        return "Glad you're entertained! 😄 Want me to find something fun to book?"
    if bare in ("ok", "okay", "cool", "nice", "great"):
        return ("👍 Tell me what you feel like — 'jazz tonight', 'free yoga', "
                "'sushi' — and I'll find it.")
    if bare == "sorry":
        return ("No worries at all! 😊 Whenever you're ready: 'jazz tonight', "
                "'free yoga', 'sushi'.")
    if bare in ("hm", "hmm", "hmm?", "hm?", "huh", "eh", "uh", "mm", "mmm"):
        return ("Take your time :) Whenever you're ready: 'jazz tonight', "
                "'free yoga', 'sushi'.")
    return None


def _social_fallback_reply(low, hub_url, sender):
    """Conversational walls used ONLY when the brain cannot serve the turn
    (offline / rate-capped / disabled). LLM-first law (owner call 2026-09-20):
    when mercury is live, greetings/acks/moods/farewells go to the brain so
    answers feel alive; this tier keeps the chat friendly without it."""
    bare = _EMOTICON_RX.sub(" ", low)
    bare = re.sub(r"[!?.,;: ]+$", "", bare).strip()
    bare = re.sub(r"\s+", " ", bare)
    if re.fullmatch(r"(hallo+|guten (morgen|tag|abend)|moin)[!,.:; )*-]*", bare, re.I):
        return ("Hallo! \U0001F44B Ich finde und buche Dinge fuer dich -- direkt "
                "hier im Chat. Probier: 'jazz tonight', 'free yoga this weekend'.")
    if re.fullmatch(r"(danke|dankeschoen|vielen dank)[!,.:; )*-]*", bare, re.I):
        return ("Gern! \U0001F60A Wenn du bereit bist: 'jazz tonight', 'free yoga', "
                "'sushi' -- sag Bescheid.")
    if _SOCIAL_GREET_RX.match(bare):
        return (
            "Hey! 👋 I'm EverList — I find things to do and book them for you, "
            "all in one chat. Your money is only released once the event's over, so "
            "every booking is safe.\n\n"
            "Try: 'jazz tonight', 'free yoga this weekend', 'sushi' — or 'book 2' "
            "once you see something you like. What are you in the mood for?")
    if _SOCIAL_THANKS_RX.match(bare):
        return ("Anytime! 😊 When you're ready: 'jazz tonight', 'free yoga', "
                "'sushi' — say the word and I'll find it.")
    if re.search(r"good ?night", bare, re.I):
        return ("Good night! 🌙 Whenever you're next in the mood — jazz, sushi, "
                "a workshop — I'm here.")
    if _FAREWELL_RX.match(bare):
        return _FAREWELL_MSG
    if _SOCIAL_MOOD_RX.match(bare) and not re.search(r"\bnot\b|n't", bare):
        return ("Sorry you're feeling that way 🫂 A good event can help — tell me "
                "what you're in the mood for: music, food, something active?")
    if _SOCIAL_FUN_RX.match(bare):
        return "Glad you're entertained! 😄 Want me to find something fun to book?"
    return None


def _handle_text_core(hub_url: str, text: str, sender: str = "") -> str:
    """Map one incoming chat text to one reply text (pure function, testable)."""
    low = (text or "").strip().lower()

    # --- U2: conversational listing intake (owner call 2026-09-18: no forms).
    # Bare 'list' starts the guided flow; mid-intake free text fills fields.
    # One-shot 'list ...' syntax (agents) still routes to _create_listing.
    _ireply = _intake_reply(hub_url, sender, text or "")
    if _ireply is not None:
        return _ireply

    # R4b battery: chained commands ('book 1 then show my bookings') are two
    # turns in one -- answer both, never leak the tail into booking args.
    # Guarded: command-word start only, and AFTER intake (titles eat this).
    if re.match(r"^(book|search|show|cancel|help|my-bookings|bookings|whoami|logout|more|fee)\b", low) \
            and "|" not in text:
        _parts = re.split(r"\s+(?:then|and then|after that|and also|also)\s+",
                          text.strip(), maxsplit=1, flags=re.I)
        if len(_parts) == 2 and _parts[1].strip() and _parts[0].strip():
            _r1 = handle_text(hub_url, _parts[0].strip(), sender)
            _r2 = handle_text(hub_url, _parts[1].strip(), sender)
            return _r1 + (chr(10) * 2) + _r2

    # --- one-prompt listing creation (B3c) — before search ('list' vs 'listings')
    if low == "list" or low.startswith("list ") or low.startswith("list\n") or low.startswith("list\r\n"):
        return _create_listing(hub_url, sender, text.strip())

    # --- deterministic social / semantic layer (120-input battery 2026-09-20):
    # greetings, acks, moods, account/stack help, cancellation policy, typos,
    # junk inputs — answers that must NEVER vary with the LLM.
    _srep = _social_safe_reply(low, hub_url, sender)
    if _srep is not None:
        return _srep
    _irep = _social_instant_reply(low, hub_url, sender)
    if _irep is not None:
        return _irep

    # --- account auth (B3c-accounts)
    if low == "signup" or low.startswith("signup "):
        return _signup(hub_url, sender)
    if low.startswith("login-seed "):
        return _login_seed(hub_url, sender, text.strip()[11:].strip())
    if low.startswith("login"):
        return _login(hub_url, sender, text.strip()[5:].strip())
    if low in ("whoami", "account", "status"):
        return _whoami(hub_url, sender)
    if low == "logout":
        return _logout(sender)
    if low == "logout-all":
        return _logout_all(hub_url, sender)
    # H7: account deletion — must match BEFORE the 'delete ' listing branch
    if low == "delete-account" or low.startswith("delete-account "):
        return _delete_account(hub_url, sender, text.strip()[14:].strip())

    # --- email recovery (B3c-email)
    if low.startswith("email-bind "):
        return _email_bind(hub_url, sender, text.strip()[10:].strip())
    if low.startswith("email-code "):
        return _email_code(hub_url, sender, text.strip()[10:].strip())
    if low.startswith("recover-confirm "):
        bits = text.strip()[15:].strip().split(None, 1)
        email = bits[0] if bits else ""
        code = bits[1] if len(bits) > 1 else ""
        return _recover_confirm(hub_url, email, code)
    if low.startswith("recover "):
        return _recover(hub_url, text.strip()[8:].strip())

    # --- payout key (M9)
    if low.startswith("set-payout "):
        return _set_payout(hub_url, sender, text.strip()[11:].strip())
    if low.startswith("notify "):
        return _notify_pref(hub_url, sender, text.strip()[7:].strip())
    if low == "notify":
        return _notify_pref(hub_url, sender, "")
    if low == "set-payout":
        return _set_payout(hub_url, sender, "")

    # --- Midnight Tier-2 sign-in (M14)
    if low.startswith("verify-midnight "):
        return _verify_midnight(hub_url, sender, text.strip()[16:].strip())
    if low == "verify-midnight":
        return _verify_midnight(hub_url, sender, "")

    # --- ownership commands (B3c-ownership)
    if low == "my-bookings" or low == "my bookings":
        return _my_bookings(hub_url, sender)
    if low == "my-listings" or low == "my listings":
        return _my_listings(hub_url, sender)
    if low.startswith("edit ") or low.startswith("edit\n"):
        return _owned_listing(hub_url, sender, text.strip()[4:].strip(), "edit")
    if low.startswith("delete "):
        return _owned_listing(hub_url, sender, text.strip()[6:].strip(), "delete")
    # --- page/board reset (C9e): 'show me the main page again', 'back to all'
    if re.fullmatch(
        r"(show (me |us )?|take (me |us )?|back (to |on )?)*(the )?(main |home |start |front )?(page|screen|board|homepage)"
        r"( again| once more| please)?|back to (all|everything|start)|reset( the)? (board|page|screen)", low):
        _LAST_RESULTS.pop(sender, None)
        _LAST_SEARCH.pop(sender, None)
        return ("[[nav:home]]🔎 The whole board is back — every live listing is up.\n"
                "Tell me what you feel like — 'jazz tonight', 'free yoga', 'sushi' — and I'll pull them out for you.")

    # --- dismissals & negations (C9f): don't keyword-search feelings.
    # 'nah never mind', 'i decided differently' -> acknowledge, keep state.
    # 'i don't want yoga, show me something else' -> browse all EXCEPT that.
    _m = re.search(
        r"\b(?:i\s+)?(?:do(?:e)?s?n?['’]?t|don['’]?t|not)\s+"
        r"(?:want|like|need|do|care for)\s+(\w+)", low)
    if _m and not re.match(r"^(search|find|book|show|help)\b", low):
        excl = _m.group(1)
        if excl in ("it", "that", "this", "them", "to", "the", "a", "any"):
            excl = None
        listings = []
        try:
            listings = (_hub_get(hub_url, "/listings") or {}).get("listings") or []
        except Exception:
            pass
        if excl:
            listings = [l for l in listings
                        if excl not in str(l.get("title", "")).lower()
                        and excl not in str(l.get("category", "")).lower()
                        and excl not in str(l.get("description", "")).lower()]
        if listings:
            if len(_LAST_RESULTS) > 500:
                _LAST_RESULTS.clear()
            _LAST_RESULTS[sender] = listings
            return (_frame("%s %s · %d found (without %s)" % (_G_MARK, _mb("EverList"), len(listings), excl or "that"),
                           [_listing_rows(l, i + 1) for i, l in enumerate(listings[:_HARD_CAP])])
                    + "\nTo book one, say 'book <n>' - $0 listings book without payment.")
        return ("Got it — no %s on the board right now anyway. "
                "Tell me what you're in the mood for instead." % (excl or "that"))

    # dismissals ('nah never mind', 'i decided differently') — acknowledge,
    # never keyword-search feelings. Token-based: short messages built only
    # from dismissal tokens (+ optional reason) match; real searches don't.
    _DTOK = ("i decided differently", "i decided otherwise", "changed my mind",
             "never mind", "nevermind", "forget it", "no thanks", "no thank you",
             "not now", "not today", "maybe later", "thank you", "thanks",
             "nah", "nope", "no", "ok", "okay", "alright", "fine", "thx")
    _core = low
    for _ in range(4):
        _prev = _core
        for t in _DTOK:
            _core = re.sub(r"\b" + re.escape(t) + r"\b", " ", _core)
        _core = re.sub(r"[^a-z']+", " ", _core).strip()
        if _core == _prev:
            break
    # must contain real letters (a dismissal word); pure numbers/punctuation
    # ('2', '7', '2-6' replay handles) must fall through to the dispatcher.
    if low and not _core and len(low) <= 40 and re.search(r"[a-z]", low):
        # LLM-first: dismissal-word inputs ('thanks', 'thx', 'ok') go to the
        # brain when live; the fallback tier owns them offline (2026-09-20).
        _d_fb = _social_fallback_reply(low, hub_url, sender)
        if _d_fb is not None:
            return _d_fb
        return ("No problem 👍 The board stays as it is. When you're ready: tell me what "
                "you feel like — 'jazz tonight', 'free yoga', 'sushi' — and I'll find it.")

    # C9c: numbered follow-ups to the last search ('2', '2-6', 'all')
    if re.fullmatch(r"\d+(?:\s*-\s*\d+)?|all", low):
        return _show_results(hub_url, sender, low)
    # H9: full listing detail — BEFORE smart-search (it would eat 'show' as a search keyword)
    if low.startswith("show "):
        arg = text.strip()[5:].strip().lower()
        if arg in ("all", "everything", "the board", "listings"):
            if _LAST_RESULTS.get(sender):
                return _show_results(hub_url, sender, "all")
            return handle_text(hub_url, "search", sender=sender)
        if "my booking" in arg or arg in ("bookings", "my bookings"):
            return _my_bookings(hub_url, sender)
        if "my listing" in arg or arg in ("listings of mine", "my listings"):
            return _my_listings(hub_url, sender)
        return _show_listing(hub_url, text.strip()[5:].strip(), sender=sender)
    if low.startswith("unarchive "):
        return _owned_listing(hub_url, sender, text.strip()[9:].strip(), "unarchive")
    if low.startswith("archive "):
        return _owned_listing(hub_url, sender, text.strip()[8:].strip(), "archive")

    # --- smart natural-language search
    # Brain v2: genuinely typed keyword queries stay deterministic (fast,
    # zero-LLM). Conversational searches — relative dates ('this weekend'),
    # fuzzy asks ('something fun', 'near me') — break out to the brain tail,
    # which resolves dates and intent properly. Fail-open law intact: brain
    # unavailable -> the tail re-enters as 'search <text>' -> this path.
    _CONV_RX = re.compile(
        r"\b(me|us|my|our|something|anything|nice|fun|cool|good|great|please|"
        r"around|near|tonight|today|tomorrow|weekend|next week|this week|"
        r"next month|sometime|maybe|looking for)\b")
    for kw in ("search", "find", "listings", "events"):
        if low == kw or low.startswith(kw + " "):
            if _CONV_RX.search(low):
                break               # conversational -> brain tail below
            rest = text.strip()[len(kw):].strip()
            return _smart_search(hub_url, (kw + " " + rest) if rest else kw, sender)

    # H10: booking status poll — BEFORE the booking-intent (startswith('book') would swallow it)
    if low.startswith("booking "):
        return _booking_status(hub_url, sender, text.strip()[8:].strip())
    # C4: buyer rates a settled booking (its own command — 'book' would swallow 'rate' otherwise never)
    if low == "rate" or low.startswith("rate "):
        return _rate_booking(hub_url, sender, text.strip()[4:].strip())

    # --- P2: private deal creation (one-liner)
    if low == "deal" or low.startswith("deal ") or low.startswith("deal\n") or low.startswith("private deal"):
        return _create_deal(hub_url, sender, text)

    # --- booking intent (H15: FREE listings book IN CHAT for logged-in accounts;
    # paid listings stay honest guidance - payment is a real gate)
    # Brain v2: TYPED forms only — the token after 'book' must be a number,
    # a pvt-claim, or a hyphenated listing id ('book 2 Alex', 'book even-2',
    # 'book p2p-3 pvt-<claim> Name', bare 'book' = guidance). Natural language
    # ('book the first one', 'book the jazz night') falls through to the brain,
    # which resolves the reference and re-enters as a clean typed command.
    if low == "book" or (low.startswith("book ") and re.fullmatch(
            r"\d+|pvt-[0-9a-f]{16}|[a-z][a-z0-9]*(?:-[a-z0-9]+)+", low.split()[1])):
        rest = text.strip()[4:].strip()
        bits = rest.split(None, 1)
        lid = bits[0] if bits else ""
        who = bits[1].strip() if len(bits) > 1 else ""
        _from_stash = False
        if lid and re.fullmatch(r"\d+", lid):
            # C9f/C9i: ids are never pure digits (SPEC 14), so a digit is a
            # positional handle into the sender's last search. Empty stash or
            # out-of-range -> honest guidance, never the generic SDK wall.
            # (A message carrying a pvt-claim keeps the P2 fall-through.)
            _stash = _LAST_RESULTS.get(sender) or []
            _k = int(lid)
            if 1 <= _k <= len(_stash):
                lid = _stash[_k - 1].get("id", lid)
                _from_stash = True
            elif not re.search(r"pvt-[0-9a-f]{16}", who):
                if _stash:
                    return ("No result %d - your last search found %d. "
                            "Say 'book <n> <name>' with n from that search." % (_k, len(_stash)))
                return ("No result %d - you have no last search here. Run one first "
                        "(e.g. 'search jazz'), then 'book <n> <name>'." % _k)
        mclaim = re.search(r"pvt-[0-9a-f]{16}", who)  # P2: inline claim ('book p2p-3 pvt-... Name')
        claim = mclaim.group(0) if mclaim else ""
        if claim:
            who = who.replace(claim, "").strip()
        target = None
        _lid_rx = re.fullmatch(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+", lid or "")
        if lid and _lid_rx:
            # Mega battery 2026-09-23: fetch the listing DIRECTLY - a /search
            # scan misses private deals and ids beyond page 1 of /listings.
            _btok = ((_session(sender) or {}).get("tokens", {}) or {}).get("list")
            try:
                t = _hub_get(hub_url, f"/listings/{urllib.parse.quote(lid)}", token=_btok)
                target = t if isinstance(t, dict) and t.get("id") == lid else None
            except urllib.error.HTTPError:
                target = None
            except Exception:
                target = None
            if target is None and _from_stash:
                # C9i regression guard 2026-09-23: the id came from the sender's
                # search stash — trust the stashed record when the direct fetch
                # cannot resolve it (paged/mock/moved listing). Typed unknown
                # ids still get the honest answer below.
                _sl = next((x for x in (_LAST_RESULTS.get(sender) or [])
                            if x.get("id") == lid), None)
                if _sl:
                    target = _sl
            if target is None and claim:
                # P2: private deal — never in /search; fetch directly with the claim
                try:
                    t = _hub_get_claim(hub_url, f"/listings/{urllib.parse.quote(lid)}", claim)
                    target = t if isinstance(t, dict) and t.get("id") == lid else None
                except Exception:
                    target = None
        if target is None and _lid_rx:
            # Mega battery 2026-09-23: honest chat answer for a well-formed
            # but unknown/hidden id - never the agent/SDK wall (that audience
            # is SDK, not chat).
            return (f"No listing '{lid}' that I can book from this chat.\n"
                    "Double-check the id (ids look like 'even-1' or 'p2p-3'), "
                    "or say 'search' to browse what's live. \U0001F642")
        if target is None:
            return (
                "Bookings need two things EverList enforces for fairness:\n"
                "1. a verified-human credential (fake agents are rejected)\n"
                "2. payment via x402 — skipped automatically for free listings (escrow WAIVED)\n"
                + (f"\nUse the EverList SDK (agenthub client) with listing id '{lid}'.\n" if lid else "\n")
                + "A booking agent with credentials can complete it end-to-end."
            )
        if float(target.get("price", 1)) > 0:
            pt = target.get("payment_terms")
            pt_line = ""
            if isinstance(pt, dict):
                pt_line = ("\n⚡ Terms: instant rail — settled at booking, no refund window."
                           if pt.get("rail") == "instant" else
                           f"\n🛡 Terms: protected · refund window {pt.get('refund_window_hours', '?')}h"
                           + (f" · deposit {pt.get('deposit_required')}" if pt.get("deposit_required") else "")
                           + "\nCustom terms: the SDK booking must echo accepted_payment_terms exactly.")
            if sender.startswith("web-"):
                return (
                    f"'{target.get('title')}' is a paid listing (${target.get('price')}). 💳\n"
                    "Free things book instantly right here in chat — for paid ones, "
                    "your booking agent handles the wallet payment (that's what the "
                    "escrow protects). Want me to show free options instead? 🌱"
                    + pt_line
                )
            return (
                f"'{target.get('title')}' is a PAID listing ({target.get('price')}).\n"
                "Payment goes through x402 — use the EverList SDK (agenthub client) "
                f"with listing id '{lid}'"
                + (f" and booking field claim='{claim}'" if claim else "")
                + ". Free listings book right here in chat."
                + pt_line
            )
        sess = _session(sender)
        if not sess:
            return (f"'{target.get('title')}' is FREE — I can book it for you right here.\n"
                    "First create an account ('signup'), then: book " + lid + " <your-name>\n"
                    "(First booking? A one-time human check — the hub operator vouches for you, just ask.)")
        if not who:
            return (f"'{target.get('title')}' is FREE. Who is the booking for?\n"
                    "book " + lid + " <your-name>\n"
                    "(First booking? A one-time human check — the hub operator vouches for you, just ask.)")
        try:
            sch = _hub_get(hub_url, "/verticals")["verticals"][target["vertical"]]["booking"]
            payload = {"listing_id": lid, sch["identity"]: who[:80]}
            if claim:
                payload["claim"] = claim  # P2: private-deal claim (hub validates, never stores)
            status, res = _hub_post(hub_url, "/book", payload, token=sess["tokens"]["book"])
        except Exception:
            return "Sorry — the EverList hub is unreachable right now. Try again shortly."
        if status == 201:
            # W1: keep the cancel token server-side so the web dashboard can
            # offer one-click cancel without exposing tokens to the browser.
            try:
                _s = _SESSIONS.get(sender)
                if _s is not None and res.get("cancel_token") and res.get("id"):
                    _s.setdefault("cancel_tokens", {})[res["id"]] = res["cancel_token"]
            except Exception:
                pass
            return (f"✅ Booked! '{target.get('title')}' — booking {res.get('id')}.\n"
                    "\n"
                    "💳 Money: " + ("your payment is locked in safely — the organizer "
                                     "can't touch it until the event has ended" if float(res.get('amount') or 0) > 0
                                    else "nothing to pay — this one's free") + ".\n"
                    + _escrow_journey(res.get("escrow", "HELD"), res.get("amount")) + "\n"
                    "\n"
                    "🔑 YOUR BOOKING SECRET — shown once, only here. This chat resets "
                    "if you reload the page, so copy it NOW:\n"
                    f"{res.get('booking_secret')}\n"
                    "(It unlocks your private booking details.)\n"
                    "\n"
                    "⏭ What happens next:\n"
                    "· The organizer confirms via the hub — just wait, no action needed.\n"
                    "· Changed your mind? Cancel from your Bookings tab (/?view=dash).\n"
                    "· You can check status anytime by asking: booking " + str(res.get('id')))
        err = res.get("error", "unknown error")
        if "verified-human" in err:
            return ("Booking rejected: your account needs a human proof.\n"
                    "Pilot: the operator can vouch for you. Production: Midnight zk-personhood "
                    "(real human, identity stays private).")
        return f"Booking rejected: {err}"

    # --- listing creation: chat-first, deterministic (never 'go to dashboard')
    if _LISTING_HOW_RX.search(low):
        return _LISTING_HOW

    # --- fee transparency intent (word-boundary law: 'feeling' is not 'fee')
    if _FEEBROAD_RX.search(low):
        return _fee_reply(hub_url)

    # --- greeting/help
    if low in ("help", "menu", "commands", "help me", "help please", "help pls"):
        return _HELP   # full command reference (tests: set-payout PUBLIC warning)

    # R4b: 'back to my listing' resumes a real draft or says honestly that
    # nothing is in progress -- never invent state (battery 2026-09-22).
    if re.search(r"\b(back to|resume|continue with|pick up)\b[^\n]{0,24}\b(listing|wizard|draft)\b"
                 r"|\bmy (?:listing|draft)\b", low) \
            and not re.match(r"^(search|book|show|delete|edit)\b", low):
        _d5 = storage.draft_get(sender)
        if _d5:
            _intake_put(sender, _d5)
            return ("Picking up your listing draft -- " + _intake_next_question(_d5))
        return ("Nothing in progress right now :) Say 'list' to start a listing -- "
                "or tell me what you feel like: 'jazz tonight', 'free yoga', 'sushi'.")

    # R4b: 'book it/this/that' resolves against the sender's stash --
    # chat-created references must book, not search the pronoun.
    _bm = re.fullmatch(r"book\s+(it|this|that|them|one)", low)
    if _bm:
        _stash_b = _LAST_RESULTS.get(sender) or []
        if len(_stash_b) == 1:
            return handle_text(hub_url, "book " + str(_stash_b[0].get("id", "")), sender)
        if _stash_b:
            return ("Which one? Say 'book <n>' with n from your last search "
                    "(1-%d)." % len(_stash_b))
        return ("Nothing to book yet :) Run a search first -- e.g. "
                "'search jazz' or 'free yoga this weekend' -- then 'book <n>'.")

    # --- instant search fast path (production 2026-09-20: plain keyword
    # searches paid a multi-second LLM round-trip). Short, plain, non-question
    # searches run deterministically; conversational shapes still hit the brain.
    _words = low.replace(",", " ").split()
    _qwords = {"who", "what", "when", "where", "why", "how", "which", "is",
               "are", "do", "does", "did", "can", "should", "whats", "wheres"}
    _fb_early = _social_fallback_reply(low, hub_url, sender)
    if ("?" not in text and _fb_early is None
            and not (_qwords & set(_words))
            and not _CONV_RX.search(low)
            and not _LISTING_HOW_RX.search(low)):
        _kws = [w for w in _words
                if w not in _FILLER_WORDS and w not in _FASTPATH_SKIP]
        if _kws and len(_kws) <= 3 and len(_words) <= 4:
            import brain as _brain_mod
            _fixed = _brain_mod._screen(" ".join(_kws))
            if _fixed is not None:
                return _fixed          # e.g. 'translate hello to french'
            return _smart_search(hub_url, " ".join(_kws), sender)

    # --- fallback: Brain v2 (owner call 2026-09-16) --------------------------
    # One LLM turn classifies the message into a validated action
    # (search/refine/nav/ack/meta/off_topic); deterministic executors above
    # do the doing and own every fact. Fail-open law unchanged: brain
    # unavailable (no key / API error / bad JSON / rate-capped / disabled via
    # EVERLIST_BRAIN_DISABLED) -> deterministic keyword search, so real
    # searches never die with the LLM.
    # R4 battery: booking status lives IN CHAT (chat-first law) -- never send
    # anyone to a dashboard for it. Bare 'more'/'next' with a stash shows it.
    _tl = text.strip().lower()
    if re.search(r"\bstatus of (my|the) booking\b|\bbookings? status\b"
                 r"|\bmy bookings\b", _tl) \
            and not re.match(r"^(book|search|list|cancel)\b", _tl):
        return _my_bookings(hub_url, sender)
    if _tl in ("more", "next") and (_LAST_RESULTS.get(sender) or []):
        _res = _LAST_RESULTS.get(sender) or []
        _head = "%s %s \u00b7 %d found" % (_G_MARK, _mb("EverList"), len(_res))
        return (_frame(_head, [_listing_rows(x, i + 1)
                               for i, x in enumerate(_res[:_HARD_CAP])])
                + "\nTo book one, say 'book <n>'.")

    # Owner battery 2026-09-22: weather questions WITH listing context are a
    # deterministic data lookup (grounded forecast), never LLM creativity.
    if _WEATHER_RX.search(text) and (_LAST_RESULTS.get(sender) or []):
        _w = None
        try:
            _w = _weather_reply(hub_url, sender, text)
        except Exception:
            _w = None
        if _w:
            return _w
        try:
            _w = _weather_reply(hub_url, sender, text, anchor_idx=0)
        except Exception:
            _w = None
        if _w:
            return _w
        _got = _LAST_RESULTS.get(sender) or []
        if _got:
            _gid = str((_got[0] or {}).get("id") or "")
            return ("I can't check the weather for that one yet -- it needs a "
                    "fixed date and place first. Here it is so you have the "
                    "details:" + chr(10) + _show_results(hub_url, sender, _gid))
    try:
        import brain
    except ImportError:
        brain = None
    if brain is not None:
        try:
            out = brain.respond(hub_url, text, sender, chatlib=sys.modules[__name__],
                                social_house=_fb_early or "")
        except Exception:
            out = None  # fail-open law: brain must never take the chat down
        if out is not None:
            return out
    # Fail-open: deterministic keyword search. Direct _smart_search call —
    # deliberately NOT a handle_text re-entry: conversational texts
    # ('find me something fun') would match the conversational break-out
    # above and recurse infinitely when the brain is unavailable (2026-09-17).
    if _fb_early is not None:
        return _fb_early
    return _smart_search(hub_url, "search " + text.strip(), sender)
