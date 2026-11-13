"""agent-hub-v2 - open, fair agent commerce hub (stdlib only, MIT).

Universal booking core: any vertical (events, food, ...) is just a schema.
Fairness is enforced in the protocol:
- hub fee is CAPPED and declared in the manifest (violators are non-conformant)
- every transaction goes to a public ledger (GET /ledger)
- escrow by default: money is held until fulfillment is confirmed
- open participation: no auth gate on the protocol level (identity/staking is a pluggable layer)
"""
import json, os, re, sys, shutil, threading, time, hmac, hashlib, secrets, base64, binascii
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as _EdPriv, Ed25519PublicKey as _EdPub
from cryptography.hazmat.primitives import serialization as _ser
from cryptography.exceptions import InvalidSignature as _InvalidSig
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hublib  # I2/G5: versioned, domain-separated HMAC action tokens
import enrich  # Phase 2 find-quality: AI write-side compression (fail-open)
import tickets as ticketing  # T5: QR tickets (door check-in)
from storage import configure, read_snapshot, write_snapshot, mode, search_ids

# fee is fully hub-declared; no protocol cap. Agents judge via the public ledger.

def anon_ref():
    """I5: per-booking random opaque reference. NOT derivable from the name,
    NOT linkable across bookings by the same participant."""
    return "anon-" + secrets.token_hex(8)

# ---- seed data: two verticals, same core ---------------------------------
LISTINGS = [
    {"id": "evt-1", "vertical": "events", "title": "AI Builders Meetup",
     "category": "meetup", "tags": ["ai", "tech", "networking"],
     "date": "2026-09-15", "location": "Berlin", "price": 10.0,
     "capacity": 50, "registered": 0, "owner": "event-owner-agent", "source": "demo-seed"},
    {"id": "evt-2", "vertical": "events", "title": "Rooftop Jazz Night",
     "category": "concert", "tags": ["music", "jazz", "rooftop"],
     "date": "2026-09-12", "location": "Berlin", "price": 15.0,
     "capacity": 30, "registered": 0, "owner": "event-owner-agent", "source": "demo-seed"},
    {"id": "food-1", "vertical": "food", "title": "Margherita Pizza",
     "category": "pizzeria", "tags": ["pizza", "italian", "vegetarian"],
     "merchant": "Luigi's", "preparation_minutes": 20, "price": 8.5,
     "available": True, "owner": "lufgis-pizzeria-agent", "source": "demo-seed"},
    {"id": "food-2", "vertical": "food", "title": "Vegan Bowl",
     "category": "vegan", "tags": ["vegan", "healthy", "salad"],
     "merchant": "Green Corner", "preparation_minutes": 15, "price": 11.0,
     "available": True, "owner": "green-corner-agent", "source": "demo-seed"},
]
BOOKINGS = []   # booking records (pseudonymous)
SECRETS = {}    # booking id -> secret (private detail access)
TICKETS = {}    # T5: QR tickets; token persists hub-side (door bearer-
                # capability, not identity), re-delivered ONLY via buyer-
                # authenticated surfaces (booking 201, /book/{id}, chat)
LEDGER = []     # public, append-only transaction ledger
EARNINGS = {}   # W3.4: owner principal -> {settledCount: int, totalVolume: float, events: [ts]} — PRIVATE mirror (never in LEDGER: recording owner+volume publicly would leak what the floor proof hides); the on-chain earnings.compact ledger is the real ZK ledger, this is the pilot mirror that feeds it
IDEMPOTENCY = {}  # I4: Idempotency-Key -> {hash, response} (persisted with G1)
IDEMPOTENCY_CAP = 50_000  # HARDENING: bound state.json growth (FIFO evict oldest)
RATE_LIMITS = {}  # G4: principal -> [timestamps] for the 60s window
ID_COUNTERS = {}  # per-vertical id counters - persisted, NEVER decremented (ids never reused after deletes)
# B3c-accounts: chat-native organizer accounts (pilot-grade auth).
# acct-<id> -> {code_hash, bound: [agent names], human_verified, verified_by, created}.
# The account CODE is the credential (shown ONCE, sha256-only); login mints tokens
# with sub=acct-<id>; open /access can NEVER mint acct- principals (forgery wall).
ACCOUNTS = {}
# SEEK system (owner GO 2026-11-12, docs/spec-seek-listings-2026-11-12.md):
# role=seek listings turn the marketplace around - a seeker posts what/when/
# where a human is WANTED; fillers join (WAIVED) or apply (vetted). Money
# direction on paid seeks: seeker funds, filler receives (S3 flip recorded on
# the booking). Fiscal wording law: seeks say "pay", never "price" (the API
# stores price; every surface words it as pay).
APPLICATIONS = {}   # aid -> {id, listing_id, filler, book_fields, message, status, created, bid?}
MERCHANTS = {}      # slug -> merchant profile (catalogs, P-track)
CATALOGS = {}       # catalog id -> versioned tree (catalogs, P-track)
SEEK_JOB_ROLES = ("join", "vetted")  # application_mode values
# CATALOGS (owner GO 2026-11-12, spec-partner-catalogs v2.1): merchants own
# catalog trees; catalog ITEMS are searchable but never feed/listing noise.
_MERCHANT_FEED_QUOTA = int(os.environ.get("HUB_MERCHANT_FEED_QUOTA", "2") or 0)
_MERCHANT_CAP = int(os.environ.get("HUB_MERCHANT_CAP", "5") or 0)
_MERCH_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}$")
_MERCH_FULFILL = ("pickup", "delivery", "shipping", "onsite")

def _pub_merchant(m):
    """Public merchant copy (no secrets stored; kept as a function so future
    server-only fields have one wall to live behind)."""
    return dict(m)

def _catalog_hash(tree):
    return hashlib.sha256(json.dumps(tree, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode()).hexdigest()

def _cat_walk(tree):
    """Yield (path_labels, item) over a catalog tree."""
    if not isinstance(tree, dict):
        return
    def walk(node, path):
        for it in (node.get("items") or [])[:200]:
            yield path, it
        for ch in (node.get("children") or [])[:50]:
            if isinstance(ch, dict) and ch.get("name"):
                yield from walk(ch, path + [str(ch["name"])[:60]])
    yield from walk(tree, [])
# Self-service page branding (owner call 2026-10-31): partners customize THEIR
# page themselves. GET /branding is public; PUT requires an acct- principal
# (same ownership law as manage/confirm). FIXED rails are server-pinned and
# NEVER customizable: demo/testnet labels, escrow wording, attribution — the
# money interface stays honest everywhere.
BRANDING = {}
BRANDING_MAX = {"brand_name": 80, "tagline": 160, "hero_text": 400, "logo_url": 300,
                "location": 120, "about_text": 800, "site_url": 300, "instagram_url": 300,
                "accent2": 7, "theme": 10}
BRANDING_THEMES = ("dark", "light")
BRANDING_IMG_FIELDS = ("logo_image", "hero_image")            # set ONLY via /branding/image
BRANDING_IMG_CAPS = {"logo": ("logo_image", 90000), "hero": ("hero_image", 420000)}  # decoded bytes
LISTING_IMG_CAP = 380000  # decoded bytes (listing photos; base64 stays under the G4 1.2M cap)
BRANDING_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
BRANDING_LANGS = ("de", "en")
ACCOUNTS_CAP = int(os.environ.get("HUB_ACCOUNTS_CAP", "10000"))  # TOTAL anti-DoS cap (state.json atomically rewritten per mutation) - env-tunable, NOT per-day
# auth endpoints: global fixed-window limits (pilot-grade anti-bruteforce/DoS;
# per-IP is unreliable behind relays, documented honestly in SPEC)
# HARDENING-v2: PoW replaced tight caps as the primary DoS gate — limits are
# generous per-source backstops now (a fair user hits none of them).
# B7: public-read sanity limits. Generous by design — legit agents never feel them.
READ_Q_MAX = 200                                        # search term length cap
READ_PAGE_MAX = int(os.environ.get("HUB_READ_PAGE_MAX", "500"))  # max results per page
READ_LIMIT = int(os.environ.get("HUB_READ_LIMIT", "600"))        # reads/min/source
# B8: state backup rotation. Backup triggers only when the state file exceeds
# HUB_BACKUP_MIN_BYTES (default 1MB) so small dev states stay clean.
BACKUP_MIN_BYTES = int(os.environ.get("HUB_BACKUP_MIN_BYTES", "1000000"))
BACKUP_KEEP = int(os.environ.get("HUB_BACKUP_KEEP", "5"))
# H3: durability. os.replace is atomic but NOT durable — after a power cut the
# last persist may exist only in page cache. fsync the temp file before the
# replace and fsync the directory after it (the rename itself needs it).
# Default ON; HUB_FSYNC=0 disables (benchmarking only).
FSYNC_ENABLED = os.environ.get("HUB_FSYNC", "1") != "0"
AUTH_LIMITS = {"signup": (30, 3600), "login": (120, 60), "rotate": (10, 3600),
                 "email": (int(os.environ.get("HUB_LIMIT_EMAIL", "5")), 3600), "verify": (int(os.environ.get("HUB_LIMIT_VERIFY", "30")), 3600), "recover": (10, 3600),
                 "read": (READ_LIMIT, 60),
                 # H5: write-path backstops (per source) on every mutating route;
                 # env-tunable like READ_LIMIT (tests shrink them; ops can tune)
                 "access": (int(os.environ.get("HUB_LIMIT_ACCESS", "60")), 60),
                 # RTF1 (red-team 2026-09-19): challenge issuance had NO backstop
                 # (probe: 1200/1200 zero 429s while every other kind capped)
                 "challenge": (int(os.environ.get("HUB_LIMIT_CHALLENGE", "240")), 60),
                 "create": (int(os.environ.get("HUB_LIMIT_CREATE", "60")), 60),
                 "book": (int(os.environ.get("HUB_LIMIT_BOOK", "60")), 60),
                 "manage": (int(os.environ.get("HUB_LIMIT_MANAGE", "60")), 60),
                 "branding": (int(os.environ.get("HUB_LIMIT_BRANDING", "60")), 60),   # self-service branding writes (2026-10-31)
                 # Import ladder (owner GO 2026-11-12, spec-import-and-badges §3):
                 # URL/text DRAFT extraction wall — per source, env-tunable.
                 # Fetching remote pages is expensive + untrusted input: capped.
                 "draft": (int(os.environ.get("HUB_LIMIT_DRAFT", "12")), 3600),
                 "admin": (int(os.environ.get("HUB_LIMIT_ADMIN", "30")), 60),
                 "delete": (int(os.environ.get("HUB_LIMIT_DELETE", "30")), 60),
                 # S2 sweep: dedicated per-source kinds for the M9/M14 account
                 # endpoints - pre-auth, so brute-forceable secrets count
                 "payout": (int(os.environ.get("HUB_LIMIT_PAYOUT", "20")), 3600),
                 "rate": (int(os.environ.get("HUB_LIMIT_RATE", "30")), 60),
                 # TRACK E: checkout session create + pay/verify walls (per source)
                 "checkout": (int(os.environ.get("HUB_LIMIT_CHECKOUT", "30")), 3600),
                 "checkout_pay": (int(os.environ.get("HUB_LIMIT_CHECKOUT_PAY", "20")), 3600)}
# HARDENING-v2: per-source fairness (was: one global bucket per kind — a single
# attacker could deny service to ALL signups by filling the shared window).
AUTH_HITS = {}  # (kind, source_ip) -> [timestamps]

# TRACK E2/E3 (owner-approved 2026-10-19): embeddable checkout sessions -
# "EverList as Stripe": any website sells an EverList listing through a
# hosted checkout window on the hub domain. Sessions are CAPABILITY URLs
# (chk- 128-bit); bookings are created ONLY through the shared _book_core
# engine (zero drift from the /book gates). Rails: FREE listings = demo rail
# (escrow WAIVED, no money moves). PAID listings = wallet rail (E7,
# owner-approved 2026-10-19): on testnet hubs (HUB_PAY_MODE=testnet) the
# buyer's EIP-3009 wallet signature rides the verify call into _book_core -
# money moves exactly when the booking lands (atomic pay+book). Fiat/card
# rails stay deferred (TRACK E4/E5); HUB_CHECKOUT_PROVIDER remains reserved
# for that future door.
CHECKOUT_TTL = int(os.environ.get("HUB_CHECKOUT_TTL", "86400"))
CHECKOUT_CAP = int(os.environ.get("HUB_CHECKOUT_CAP", "5000"))
CHECKOUT_PENDING_TTL = int(os.environ.get("HUB_CHECKOUT_PENDING_TTL", "900"))  # email-code window (mirrors /accounts law)
CHECKOUT_RESEND_COOLDOWN = int(os.environ.get("HUB_CHECKOUT_RESEND_COOLDOWN", "60"))
CHECKOUT_MAX_ATTEMPTS = 5
CHECKOUT_PROVIDER = os.environ.get("HUB_CHECKOUT_PROVIDER", "").strip()
CHECKOUT_SESSIONS = {}  # sid -> session dict; persisted in state.json

_AUTH_HITS_CAP = 100_000  # bound memory vs source-spoofing floods
TRUST_PROXY = os.environ.get("HUB_TRUST_PROXY", "") == "1"  # behind reverse proxy only


def _source_of(handler):
    """Client source for fairness limiting. Direct socket address by default;
    X-Forwarded-For only when HUB_TRUST_PROXY=1 (reverse-proxy deployments)."""
    if TRUST_PROXY:
        xff = handler.headers.get("X-Forwarded-For", "")
        if xff:
            return xff.split(",")[0].strip()[:64]
    return str(handler.client_address[0]) if handler.client_address else "unknown"


# ---------------- TRACK E helpers (embeddable checkout, E2/E3) ----------------

def _checkout_mask(email):
    """Masked email for capability-URL faces (chk- links are bearer tokens)."""
    if not email or "@" not in email:
        return ""
    name, dom = email.split("@", 1)
    return (name[:1] + "***@" + dom) if name else "***@" + dom

def _checkout_total_c(sess, listing):
    try:
        return int(round(float(listing.get("price", 0)) * 100)) * sess["qty"]
    except (TypeError, ValueError):
        return 0

def _checkout_face(sess):
    """Public face of a checkout session: listing snapshot + money honesty.
    Carries NO secrets (booking_secret/cancel_token stay email-only)."""
    with LOCK:
        listing = next((l for l in LISTINGS if l["id"] == sess["listing_id"]), None)
    if not listing:
        return {"listing": None}
    pub = _pub_listing(listing)
    total_c = _checkout_total_c(sess, listing)
    resp = {"listing": pub, "quantity": sess["qty"],
            "total": total_c / 100.0,
            "buyer_fee": 0.0,
            "fee_note": "no EverList buyer fee - the price is what you pay",
            "payment_terms": sess["terms"],
            "identity_label": VERTICAL_SCHEMAS[listing["vertical"]]["booking"]["identity"]}
    # Payment request for wallet-pay rail (only in testnet, only for paid listings)
    if total_c > 0 and PAY_MODE == "testnet":
        _recv = str(listing.get("receive_addr") or PAYTO).lower()
        resp["payment_request"] = {
            "listing_id": listing["id"],
            "network": "base-sepolia",
            "asset": BASE_SEPOLIA_USDC,
            "receiver": _recv,
            # EXACTLY the units _book_core's x402verify wall checks against:
            # int(round((price_c / 100.0) * 1_000_000)) - zero drift.
            "units": str(int(round((total_c / 100.0) * 1_000_000))),
        }
    return resp

_CHECKOUT_MAIL_HITS = {}  # sha256(email) -> [timestamps]: anti email-bombing

def _checkout_mail_allow(email, now):
    """Max 3 verification mails per address per hour, GLOBAL across sessions
    (sessions are mintable; mailboxes are not). Caller holds LOCK."""
    key = hashlib.sha256(email.encode()).hexdigest()
    hist = [t for t in _CHECKOUT_MAIL_HITS.get(key, []) if now - t < 3600]
    if len(hist) >= 3:
        _CHECKOUT_MAIL_HITS[key] = hist
        return False
    hist.append(now)
    _CHECKOUT_MAIL_HITS[key] = hist
    if len(_CHECKOUT_MAIL_HITS) > 50_000:
        for k in list(_CHECKOUT_MAIL_HITS)[: len(_CHECKOUT_MAIL_HITS) // 10]:
            _CHECKOUT_MAIL_HITS.pop(k, None)
    return True



def _paginate(items, query):
    """B7: offset pagination for public reads. Default (no params) returns up to
    READ_PAGE_MAX — identical behavior for small hubs; huge result sets page via
    offset+limit instead of growing responses unboundedly. Returns (slice, off, lim)."""
    try:
        off = max(0, int(query.get("offset", ["0"])[0]))
    except (ValueError, TypeError):
        off = 0
    try:
        lim = int(query.get("limit", [str(READ_PAGE_MAX)])[0])
    except (ValueError, TypeError):
        lim = READ_PAGE_MAX
    lim = max(1, min(lim, READ_PAGE_MAX))
    return items[off:off + lim], off, lim


# S6: rating_wsum/rating_wtot (weighted-average numerator/denominator), review_flags
# (L4 interlock heuristics) and rating_times (burst detection) are server-internal.
_SERVER_ONLY_LISTING_FIELDS = frozenset({"manage_code_hash", "claim_code_hash", "rating_wsum", "rating_wtot", "review_flags", "rating_times", "promo_code_hash", "_enrich_kw", "_enrich"})


def _review_weight(b):
    """S6-L3: review weight scales with the settled amount (capped 1..50). A
    0.50 self-loop counts a fraction of a 50-unit booking; free bookings do not
    enter this channel at all (L2)."""
    try:
        amt = float(b.get("amount", 0) or 0)
    except (TypeError, ValueError):
        amt = 0.0
    return max(1.0, min(50.0, amt))


def _agg_text(lst):
    """S6: honest aggregate display - amount-weighted paid average plus the
    separate free-feedback channel (never merged)."""
    out = []
    wtot = lst.get("rating_wtot", 0)
    if wtot > 0:
        out.append(f"paid reviews: {lst.get('rating_wsum', 0) / wtot:.1f}/5 weighted ({lst.get('rating_count', 0)} rating(s))")
    fc = lst.get("free_rating_count", 0)
    if fc:
        out.append(f"free-class feedback: {lst.get('free_rating_sum', 0) / fc:.1f}/5 ({fc} free booking(s))")
    return (" | " .join(out)) if out else ""


def _s6_flag_review(lst):
    """S6-L4: cheap interlock heuristics over booking payment evidence.
    Flags feed a MANUAL review queue - detection only, never auto-deletion."""
    reasons = []
    mine = [x for x in BOOKINGS if x.get("listing_id") == lst["id"]]
    rated = [x for x in mine if isinstance(x.get("rating"), int)]
    # (1) repeated payer wallet on the same listing
    seen = {}
    for x in rated:
        pp = str(x.get("payment_payer") or "").lower()
        if pp:
            seen[pp] = seen.get(pp, 0) + 1
    dup = {p: c for p, c in seen.items() if c > 1}
    if dup:
        reasons.append(f"repeated payer wallet(s): {len(dup)}")
    # (2) interlock: payer wallet also paid a sibling listing of the same owner
    owner = lst.get("owner")
    if owner:
        sib = {x["id"] for x in LISTINGS if x.get("owner") == owner} - {lst["id"]}
        here = {str(x.get("payment_payer") or "").lower() for x in rated if x.get("payment_payer")}
        there = {str(x.get("payment_payer") or "").lower() for x in BOOKINGS
                 if x.get("listing_id") in sib and x.get("payment_payer")}
        if here & there:
            reasons.append("interlock: payer wallet also paid a sibling listing of this owner")
    # (3) burst: 3+ paid ratings within a 10-minute window
    times = sorted(x.get("rated_at", 0) for x in rated
                   if x.get("escrow") != "WAIVED" and x.get("rated_at"))
    if len(times) >= 3 and times[-1] - times[-3] <= 600:
        reasons.append("burst: 3+ paid ratings within 10 minutes")
    if reasons:
        flags = lst.setdefault("review_flags", [])
        if not any(e.get("reasons") == reasons for e in flags):
            flags.append({"ts": time.time(), "reasons": reasons})
            del flags[:-100]  # bounded


def _s6_recompute_aggregates():
    """S6 boot migration: rebuild channel-split + weighted aggregates from the
    booking history so pre-S6 ratings aggregate under the new rules too."""
    for l in LISTINGS:
        l["rating_sum"] = 0; l["rating_count"] = 0
        l["free_rating_sum"] = 0; l["free_rating_count"] = 0
        l["rating_wsum"] = 0; l["rating_wtot"] = 0
    for b in BOOKINGS:
        r = b.get("rating")
        if not isinstance(r, int) or not (1 <= r <= 5):
            continue
        lst = next((x for x in LISTINGS if x["id"] == b.get("listing_id")), None)
        if lst is None:
            continue
        if b.get("escrow") == "WAIVED":
            lst["free_rating_sum"] += r; lst["free_rating_count"] += 1
        else:
            w = _review_weight(b)
            lst["rating_wsum"] += r * w; lst["rating_wtot"] += w
            lst["rating_sum"] += r; lst["rating_count"] += 1
    for l in LISTINGS:
        if l.get("rating_wtot"):
            l["rating_avg"] = round(l["rating_wsum"] / l["rating_wtot"], 2)


# P1 2026-10-11: location alias normalization — 'wien' and 'vienna' (and
# future bilingual city pairs) must match each other in /search no matter
# which language the listing or the query used (owner report: searches for
# Vienna missed German-stored listings and suggested other cities).
_LOC_ALIASES = {"wien": "vienna"}


def _loc_norm(s):
    """Lowercase + alias-normalize a location string for filter matching."""
    n = (s or "").strip().lower()
    return _LOC_ALIASES.get(n, n)


def _parse_latlon(raw):
    """Phase 2 geo: parse 'lat,lon' degrees; None when malformed (caller 400s)."""
    try:
        a, b = str(raw or "").split(",", 1)
        lat, lon = float(a), float(b)
    except ValueError:
        return None
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return lat, lon


def _dist_km(lat1, lon1, lat2, lon2):
    """Haversine great-circle distance in km (deterministic, no deps)."""
    import math
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = (math.sin(dp / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2)
    return 2 * math.asin(min(1.0, math.sqrt(a))) * 6371.0088


_TIME_SHAPE = re.compile(r"^\d{2}:\d{2}$")


def _is_hhmm(v):
    """Phase 2 time facets: strict zero-padded 24h HH:MM (00-23:00-59).
    Guards BOTH query params and stored listing times; malformed stored
    values cannot satisfy a time facet (fail-closed, like coordless geo)."""
    s = str(v or "")
    if not _TIME_SHAPE.match(s):
        return False
    h, m = int(s[:2]), int(s[3:])
    return h <= 23 and m <= 59


_DEMO_OWNER_PREFIXES = ("demo-", "everlist-org-", "escrow-sandbox")


def _is_demo_listing(l):
    """A6 2026-11-04 (owner: launch honesty — 'Sandra is not real'): seed and
    curated-example supply is machine-flagged so NO surface can present it
    as live organizers. Covers demo-seed sources, demo-* owners, the
    everlist-org-* seed families and the escrow sandbox. Real organizer
    listings never match. Consumed by _pub_listing (API + SPA + SSR)."""
    if str(l.get("source") or "").startswith("demo-seed"):
        return True
    own = str(l.get("owner") or "")
    if own.startswith(_DEMO_OWNER_PREFIXES):
        return True
    # write-path proof artifacts (POST /listings direct, e.g. postship-writeproof)
    # are test supply too - found live on prod 2026-11-05 (even-75)
    return "writeproof" in own


def _normalize_sponsor(v):
    """Phase 3 marketplace: sponsor state is SERVER-OWNED (admin-granted via
    /admin/sponsor; the reserved wall rejects client '_sponsor'). This runs
    on trusted persisted state only — malformed stored state deactivates
    instead of crashing search."""
    if not isinstance(v, dict):
        return None
    try:
        ok = bool(v.get("active")) and float(v.get("until_ts", 0)) > time.time()
    except (TypeError, ValueError):
        return None
    return {"active": True, "until_ts": float(v["until_ts"])} if ok else None


def _pub_listing(l):
    """H9: server-only fields must NEVER reach a public response.
    manage_code_hash = sha256 of the owner's manage code; with it an attacker
    could brute-force the ~48-bit code offline and forge ownership. Internal
    state (LISTINGS) keeps it; every response copy passes through here.
    A6 2026-11-04: demo/example supply carries a server-derived demo flag
    (true only; absent for real organizers)."""
    pub = {k: v for k, v in l.items() if k not in _SERVER_ONLY_LISTING_FIELDS}
    if _is_demo_listing(l):
        pub["demo"] = True
    # UI hint only: all checkout/session/booking walls remain authoritative.
    # No receiver, account or booking secrets are added to this public projection.
    from datetime import date
    try:
        day = date.fromisoformat(str(l.get("date") or ""))
        ended = day < date.today()
    except ValueError:
        ended = False
    available = (not ended and not l.get("archived") and l.get("visibility", "public") == "public"
                 and l.get("available", True)
                 and ("capacity" not in l or int(l.get("registered") or 0) < int(l["capacity"])))
    paid = float(l.get("price") or 0) > 0
    pub["checkout"] = {"eligible": bool(available and (not paid or PAY_MODE == "testnet")),
                       "mode": "testnet" if paid and PAY_MODE == "testnet" else "demo" if not paid else "unavailable"}
    # Same one-place calculation as hosted checkout; organizer commission is NOT a buyer surcharge.
    pub["price_preview"] = {"quantity": 1, "total": _checkout_total_c({"qty": 1}, l) / 100.0, "buyer_fee": 0.0}
    return pub


def _read_gate(handler):
    """B7: coarse per-source read backstop. Caller must NOT hold LOCK."""
    with LOCK:
        return _auth_allow("read", _source_of(handler))


def _gen_check(payload):
    """B1: per-account token generation. rotate / recover/confirm / logout-all bump
    the account's gen; tokens embedding an older gen are dead. Non-account tokens
    (per-booking, /access agent tokens) pass through untouched."""
    if not payload:
        return None, "missing token"
    sub = payload.get("sub", "")
    if sub.startswith("acct-"):
        with LOCK:
            acct = ACCOUNTS.get(sub)
        if not acct:
            return None, "account no longer exists"
        if int(payload.get("gen", 0)) < int(acct.get("gen", 0)):
            return None, "token revoked - account credential rotated or logout-all; log in again"
    return payload, None


# RTF2 (red-team 2026-09-19): C0 controls (except \t\n\r), DEL and bidi
# overrides have no legitimate use in user-supplied text — they enable SMTP
# subject/header games and RTL spoofing in rendered surfaces. Newlines stay
# legal in long-form fields (description); title/location ban them entirely.
_BAD_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e]")


def _auth_allow(kind, src="global"):
    """Fixed-window limiter, PER SOURCE. Caller MUST hold LOCK."""
    limit, window = AUTH_LIMITS[kind]
    now = time.time()
    key = (kind, str(src))
    if len(AUTH_HITS) >= _AUTH_HITS_CAP and key not in AUTH_HITS:
        for k in list(AUTH_HITS)[: len(AUTH_HITS) // 10]:
            AUTH_HITS.pop(k, None)
    hist = [t for t in AUTH_HITS.get(key, []) if now - t < window]
    if len(hist) >= limit:
        AUTH_HITS[key] = hist
        return False
    hist.append(now)
    AUTH_HITS[key] = hist
    return True


# HARDENING-v2: proof-of-work cost curve (hashcash-style). Expensive anonymous
# actions (signup, recover) must burn client CPU; legit users pay ~0.3s ONCE,
# attackers pay per attempt — and limits stay generous because PoW is the gate.
POW_DIFFICULTY = {  # leading zero BITS; env-tunable (B2: tests lower it; ops can raise it)
    "signup": int(os.environ.get("HUB_POW_SIGNUP_BITS", "18")),
    "recover": int(os.environ.get("HUB_POW_RECOVER_BITS", "16")),
}  # ~0.3s / ~0.07s client CPU per solution at defaults
POW_CHALLENGES = {}  # challenge -> {exp, kind, used} ; single-use, TTL 10 min
POW_CAP = 100_000
LOGIN_CHALLENGES = {}  # aid -> {ch, exp} ; one live login challenge per account


def _pow_issue(kind):
    ch = secrets.token_hex(16)
    POW_CHALLENGES[ch] = {"exp": time.time() + 600, "kind": kind}
    if len(POW_CHALLENGES) > POW_CAP:
        now = time.time()
        for k in [k for k, v in POW_CHALLENGES.items() if v["exp"] < now][: len(POW_CHALLENGES) // 2]:
            POW_CHALLENGES.pop(k, None)
    return {"algo": "sha256-leading-zeros", "challenge": ch,
            "difficulty": POW_DIFFICULTY[kind], "ttl": 600,
            "hint": "find nonce N (int) with sha256(challenge + str(N)) having <difficulty> leading zero bits; POST it back as pow: {challenge, nonce}"}


def _pow_spend(kind, powobj):
    """Verify+consume one PoW solution. Returns error string or None. Caller holds LOCK."""
    if not isinstance(powobj, dict):
        return "pow required: GET /auth/challenge?kind=" + kind
    ch = str(powobj.get("challenge", ""))
    nonce = powobj.get("nonce")
    rec = POW_CHALLENGES.get(ch)
    if not rec or rec["kind"] != kind:
        return "invalid or expired pow challenge"
    if rec.pop("used", False):
        return "pow challenge already used"
    if time.time() > rec["exp"]:
        POW_CHALLENGES.pop(ch, None)
        return "pow challenge expired"
    if not isinstance(nonce, int) or isinstance(nonce, bool) or abs(nonce) > 10**15:
        return "pow nonce must be an integer"
    digest = hashlib.sha256((ch + str(nonce)).encode()).digest()
    need = POW_DIFFICULTY[kind]
    bits = 0
    for b in digest:
        if b == 0:
            bits += 8; continue
        bits += 8 - b.bit_length()  # leading zero bits of this byte
        break
    if bits < need:
        return f"pow insufficient difficulty (need {need} zero bits)"
    rec["used"] = True
    return None


# RLock: _gen_check may run while the caller already holds LOCK
# (e.g. GET /listings owner-projection) - threading.Lock would
# self-deadlock on reentrant acquisition (found via faulthandler dump)
LOCK = threading.RLock()

# G1: JSON snapshot persistence (atomic write on every mutation, load on start).
# Privacy: SECRETS (real attendee/buyer names) are NEVER persisted - identities stay
# memory-only by design; booking records + ledger + listings + idempotency + token
# nonces survive restarts.


def _backup_locked():
    """B8: rotate state backups. Called at the START of a persist, BEFORE the
    incoming snapshot overwrites STATE_FILE: copies the CURRENT file (the
    pre-persist snapshot) to <state_dir>/backups/state-<ns>.json and keeps the
    newest BACKUP_KEEP. Backup failure must NEVER break persistence."""
    try:
        if not os.path.exists(STATE_FILE) or os.path.getsize(STATE_FILE) < BACKUP_MIN_BYTES:
            return
        bdir = os.path.join(os.path.dirname(STATE_FILE), "backups")
        os.makedirs(bdir, exist_ok=True)
        try:
            os.chmod(bdir, 0o700)  # H17: backups hold the same secrets
        except OSError:
            pass
        _bpath = os.path.join(bdir, f"state-{time.time_ns()}.json")
        shutil.copy2(STATE_FILE, _bpath)
        try:
            os.chmod(_bpath, 0o600)  # H17: copy2 preserves the 0644 source mode
        except OSError:
            pass
        baks = sorted(f for f in os.listdir(bdir)
                      if f.startswith("state-") and f.endswith(".json"))
        for old_b in baks[:-BACKUP_KEEP]:
            try:
                os.remove(os.path.join(bdir, old_b))
            except OSError:
                pass
    except Exception as ex:
        print(f"[BACKUP] warning: rotation failed ({ex})", flush=True)


def _persist_locked():
    """Atomic snapshot write. Caller MUST hold LOCK."""
    _backup_locked()
    snap = {"listings": LISTINGS, "bookings": BOOKINGS, "ledger": LEDGER,
            "idempotency": IDEMPOTENCY, "accounts": ACCOUNTS, "id_counters": ID_COUNTERS,
            "checkout": CHECKOUT_SESSIONS,
            "nonces": {n: e for n, e in getattr(hublib, "_NONCES", {}).items()},
            "x402_nonces": (x402verify.snapshot_used_nonces() if PAY_MODE == "testnet" else {}),
            "settlements": (SETTLEMENTS.snapshot() if PAY_MODE == "testnet" else {}),
            "cardano_settlements": CARDANO_SETTLEMENTS.snapshot(),   # C3c
            "cardano_nonces": cardano_x402.snapshot_used_nonces(),   # C3c nonce wall
            "tickets": TICKETS,   # T5: QR tickets
            "earnings": EARNINGS,   # W3.4: private earnings mirror (never public LEDGER)
            "branding": BRANDING,  # v2: partner branding MUST survive restarts (was silently dropped)
            "applications": APPLICATIONS,  # SEEK vetted applications (messages: private-store law)
            "merchants": MERCHANTS, "catalogs": CATALOGS}  # catalogs P-track
    write_snapshot(snap)


def _load_state():
    """Load snapshot at startup. Missing state = fresh start; corrupt = fail-closed (exit 78)."""
    try:
        snap = read_snapshot()
        if snap is None:
            return
        LISTINGS[:] = snap.get("listings", [])
        BOOKINGS[:] = snap.get("bookings", [])
        APPLICATIONS.update(snap.get("applications", {}))
        MERCHANTS.update(snap.get("merchants", {}))
        CATALOGS.update(snap.get("catalogs", {}))
        LEDGER[:] = snap.get("ledger", [])
        IDEMPOTENCY.update(snap.get("idempotency", {}))
        ACCOUNTS.update(snap.get("accounts", {}))
        CHECKOUT_SESSIONS.update(snap.get("checkout", {}))  # TRACK E: durable checkout sessions
        ID_COUNTERS.update(snap.get("id_counters", {}))
        EARNINGS.update(snap.get("earnings", {}))   # W3.4: private earnings mirror
        TICKETS.update(snap.get("tickets", {}))     # T5: QR tickets
        BRANDING.update(snap.get("branding", {}))   # v2: restore partner branding
        # Incident 2026-10-19 (prod 502s): persisted counters can run stale
        # behind real listing ids (even:36 while even-71 existed) — a fresh
        # mint then collides, duplicates ride into RAM, and EVERY persist
        # dies on UNIQUE(listings.id). Reconcile counters to restored reality
        # at boot; the mint guard below is the second layer.
        for _l in LISTINGS:
            _lid = str(_l.get("id") or "")
            if "-" in _lid:
                _pfx, _, _sfx = _lid.rpartition("-")
                if _sfx.isdigit():
                    ID_COUNTERS[_pfx] = max(int(ID_COUNTERS.get(_pfx, 0)), int(_sfx))
        # B3c-email + B1 migration: legacy accounts predate email/gen fields
        _EFIELDS = {"email": None, "email_verified": False, "notify_email": True, "marketing_email": True, "pending_email": None,
                    "pending_code_hash": None, "pending_exp": 0,
                    "recovery_code_hash": None, "recovery_exp": 0, "gen": 0, "email_lang": "en",
                    "payout_pk": None, "midnight_credential": None}
        for _a, _v in ACCOUNTS.items():
            for _k, _d in _EFIELDS.items():
                _v.setdefault(_k, _d)
        # Owner call 2026-09-23: demo listings must look normal (investor demos).
        # Titles lose the big [TEST] prefix, placeholder descriptions get
        # realistic copy. The test flag stays in `source` and surfaces ONLY as
        # small print in the details panel. Idempotent; demo-seed sources only.
        _DEMO_COPY = {
            "Open Mic Night": "Open-mic night in the back room of the Kiez cafe: five-minute slots on the small stage, sign-up sheet at the bar from 18:30. Acoustic guitar and a house piano are set up; spoken word and readings welcome. Free entry, arrive early for a slot.",
            "Board Game Afternoon": "Long tables of modern board games in the loft space — from quick fillers to full three-hour strategy nights. A teach-and-play corner walks newcomers through a short game before they pick a table. Coffee and cake available all afternoon.",
            "Saturday Morning Run Club": "Community run club meeting every other Saturday at the Tiergarten fountain. An easy 5k at conversational pace and a steadier 10k group. All paces welcome, nobody gets dropped, coffee at the park cafe afterwards.",
            "Photo Walk: Old Town": "A slow two-hour walk through the old town with cameras out — street scenes, river light, and the courtyards most people walk past. Phone cameras welcome; framing tips shared as you go. Ends at a cafe with a print swap.",
            "Language Exchange Evening": "Language tables for German, English and Spanish in the back garden of the Kiez cafe. A friendly moderator keeps the tables moving every 30 minutes so everyone gets practice. All levels welcome; drinks at bar prices.",
            "Sunrise Yoga in the Park": "A gentle vinyasa flow on the meadow as the city wakes up — mats provided, no experience needed. The class runs about an hour, ending with ten minutes of breathing before the day starts. Free community session.",
            "Clothes Swap Party": "Bring up to five pieces you no longer wear and take home something new-to-you. Rail sorted by size, a mirror corner, and volunteers keeping the racks flowing. Leftovers go to charity at the end of the day.",
            "Lightning Talks: Builders Edition": "Six five-minute talks from local builders — what shipped, what broke, what they learned. After the talks the mic opens for impromptu demos. Free pizza and soft drinks all evening; doors 17:30.",
            "Community Cook-Off": "Everyone brings one dish, everyone tastes everything. A friendly cook-off with a crowd-vote prize for the favourite plate, plus a recipe swap at the kitchen table. Families welcome; ingredients list shared a week before.",
            "Come Sing: Pop Choir Taster": "One joyful hour of pop-choir singing — no experience needed, lyrics and warm-ups provided. We learn one easy arrangement together and finish with a run-through for anyone who wants to record it.",
            "Chess & Coffee Open Play": "Open chess tables in the cafe's glass courtyard — quick pairings all morning, boards and clocks provided. Beginners get a coach for their first games; regulars settle into longer matches. Coffee special for players.",
            "Star Night: Telescope Session": "Volunteer astronomers set up telescopes by the lake and guide you across the November sky — the Pleiades, Jupiter, and the darker star clusters. Warm clothes recommended; hot tea provided. Family-friendly.",
            "Maker Meet & Greet": "Show-and-tell for makers: bring a project, a prototype, or just curiosity. Tables for electronics, 3D printing, sewing and woodworking; open mic for five-minute project stories. Free entry.",
            "Year-End Community Dinner": "Potluck-style community dinner to close the year — bring a dish if you like, or just bring yourself. Long tables, candles, and a short year-in-review toast from the neighbourhood association.",
        }
        for _l in LISTINGS:
            if (str(_l.get("source", "")).startswith("demo-seed") or str(_l.get("owner", "")).startswith("demo-test")) and "[TEST]" in str(_l.get("title", "")): 
                _ct = str(_l["title"]).replace("[TEST] ", "").replace("[TEST]", "").strip()
                _l["title"] = _ct
                if _ct in _DEMO_COPY:
                    _l["description"] = _DEMO_COPY[_ct]
        # C12: legacy listings predate payment_terms (SPEC §19) — inject the
        # vertical default at load so every listing always shows real terms
        for _l in LISTINGS:
            if not isinstance(_l.get("payment_terms"), dict):
                _l["payment_terms"] = _default_payment_terms(_l.get("vertical", "events"))
        hublib._NONCES.update(snap.get("nonces", {}))
        if PAY_MODE == "testnet":
            x402verify.load_used_nonces(snap.get("x402_nonces", {}))
            SETTLEMENTS.load(snap.get("settlements", {}))
        CARDANO_SETTLEMENTS.load(snap.get("cardano_settlements", {}))  # C3c
        cardano_x402.load_used_nonces(snap.get("cardano_nonces", []))  # C3c nonce wall
        print(f"G1: restored {len(BOOKINGS)} bookings, {len(LEDGER)} ledger entries, "
              f"{len(LISTINGS)} listings from {STATE_FILE}")
    except Exception as ex:
        # HARDENING: corrupt state = stop, never overwrite. Starting fresh would
        # let the first mutation atomically destroy potentially recoverable data.
        sys.stderr.write(
            f"FATAL: state file {STATE_FILE} is corrupt ({ex}).\n"
            "Refusing to start to avoid destroying data.\n"
            "Fix the file or move it aside, then restart.\n")
        sys.exit(78)

# I2/H1: signing keys from env; never log or return these
# G5: fail-closed in production — a missing key must never silently fall back to dev defaults
BOOKING_KEY = os.environ.get("HUB_BOOKING_KEY", "dev-booking-key-change-me")
ADMIN_KEY = os.environ.get("HUB_ADMIN_KEY", "dev-admin-key-change-me")
# M14 Tier-2 sign-in: where the credential contract lives. No env set = the
# recorded offline-sim fixture is the honest fallback (mode: simulated);
# HUB_CRED_INDEXER set = live chain reads (mode: chain). Fail-closed always.
CRED_ADDRESS = os.environ.get("HUB_CRED_ADDRESS", "midnight-credential-sim")
CRED_INDEXER = os.environ.get("HUB_CRED_INDEXER", "")
from midnight_credential import FIXTURE_PATH as _CRED_FIXTURE  # default evidence source
FIXTURE_DEFAULT = _CRED_FIXTURE
RUN_ENV = os.environ.get("HUB_ENV", "development")
if RUN_ENV == "production" and (BOOKING_KEY.startswith("dev-") or ADMIN_KEY.startswith("dev-")):
    sys.stderr.write("FATAL: HUB_ENV=production requires HUB_BOOKING_KEY and HUB_ADMIN_KEY (no dev defaults)\n")
    sys.exit(78)
elif ADMIN_KEY.startswith("dev-"):
    # S1: a misconfigured exposed deployment (HUB_ENV unset) must not run the
    # well-known dev admin key SILENTLY - loud on stderr, fatal only in prod
    sys.stderr.write("WARNING: HUB_ADMIN_KEY is the dev default - localhost only; set it before any network exposure\n")
# G3: all operational config via env with sane defaults
PORT = int(os.environ.get("HUB_PORT", "8802"))
FEE_PCT = float(os.environ.get("HUB_FEE_PCT", "2.0"))
if not (0 <= FEE_PCT <= 50):
    sys.stderr.write(f"FATAL: HUB_FEE_PCT must be in [0, 50], got {FEE_PCT}\n")
    sys.exit(78)
# demo-kit: operator-brandable display metadata (protocol fields untouched)
HUB_NAME = os.environ.get("HUB_NAME", "agent-hub-v2")
HUB_DESCRIPTION = os.environ.get(
    "HUB_DESCRIPTION",
    "Agent commerce hub - universal booking core, per-vertical schemas. Open core; EverList network membership is curated.")
DATA_DIR = os.environ.get("HUB_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))
# FED1 (run #5): HUB_STATE_DIR was silently ignored (only HUB_STATE_FILE existed),
# so operator drills booted against the repo's default state.json — one flock
# away from production-state corruption. Support the alias explicitly.
STATE_FILE = os.environ.get("HUB_STATE_FILE",
                            os.path.join(os.environ.get("HUB_STATE_DIR", DATA_DIR), "state.json"))
configure(STATE_FILE)
sys.stderr.write("[hub] state file: %s\n" % STATE_FILE)  # FED1: isolation mistakes must be visible at boot
# H12: bounded rotating request log (ops hygiene; wrapper.py got its own in B4).
# One structured line per response: method, path (query stripped, truncated),
# status, latency, source, request-id. Bodies/headers are NEVER logged; log
# failures are swallowed — observability must never break the hub.
import logging
import logging.handlers
REQ_LOG_FILE = os.environ.get("HUB_REQUEST_LOG",
    os.path.join(os.path.dirname(STATE_FILE), "requests.log"))  # beside state: per-instance isolation
REQ_LOG_MAX = int(os.environ.get("HUB_LOG_MAX_BYTES", str(5 * 1024 * 1024)))
REQ_LOG_N = int(os.environ.get("HUB_LOG_BACKUPS", "3"))
_reqlog = None
try:  # H12: a logging problem must never prevent startup
    os.makedirs(os.path.dirname(REQ_LOG_FILE), exist_ok=True)
    _reqlog = logging.getLogger("hub.requests")
    _reqlog.setLevel(logging.INFO)
    _reqlog.addHandler(logging.handlers.RotatingFileHandler(
        REQ_LOG_FILE, maxBytes=REQ_LOG_MAX, backupCount=REQ_LOG_N))
    _reqlog.propagate = False
except Exception:
    _reqlog = None  # hub runs unlogged rather than not at all
PAY_MODE = os.environ.get("HUB_PAY_MODE", "simulated")  # simulated | testnet (real EIP-3009 verification)
if PAY_MODE not in ("simulated", "testnet"):
    sys.stderr.write(f"FATAL: HUB_PAY_MODE must be simulated|testnet, got {PAY_MODE}\n")
    sys.exit(78)
if PAY_MODE == "testnet":
    import x402verify  # real EIP-3009 verification (C3a); settlement = C3b
    import x402facilitate
SETTLE_MODE = os.environ.get("HUB_SETTLE_MODE", "off")  # off (verify-only) | auto (settle after verify)
if SETTLE_MODE not in ("off", "auto"):
    sys.stderr.write(f"FATAL: HUB_SETTLE_MODE must be off|auto, got {SETTLE_MODE}\n")
    sys.exit(78)
# B3c-email: account email binding + recovery. Modes: off (default) | log (dev: code in hub log) | smtp
EMAIL_MODE = os.environ.get("HUB_EMAIL_MODE", "off")
if EMAIL_MODE not in ("off", "log", "smtp"):
    sys.stderr.write(f"FATAL: HUB_EMAIL_MODE must be off|log|smtp, got {EMAIL_MODE}\n")
    sys.exit(78)
SMTP_HOST = os.environ.get("HUB_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("HUB_SMTP_PORT", "587"))
SMTP_USER = os.environ.get("HUB_SMTP_USER", "")
SMTP_PASS = os.environ.get("HUB_SMTP_PASS", "")
MAIL_FROM = os.environ.get("HUB_MAIL_FROM", SMTP_USER or "everlist@localhost")
PUBLIC_URL_DIGEST = os.environ.get("HUB_PUBLIC_URL", "https://everlist.network").rstrip("/")


def _send_email(to, subject, body):
    """Honest delivery: off/log are dev modes (label says so); smtp really sends.
    body: plain string (legacy), or dict from emailkit (subject/text/html +
    optional unsub_url) -> proper MIME with HTML part + unsubscribe headers."""
    if EMAIL_MODE == "off":
        return "off"
    if EMAIL_MODE == "log":
        plain = body["text"] if isinstance(body, dict) else body
        print(f"[EMAIL:log] to={to} subject={subject!r} body={plain!r}", flush=True)
        return "logged"
    import emailkit
    unsub = body.get("unsub_url") if isinstance(body, dict) else None
    if isinstance(body, dict):
        msg = emailkit.mime_message(MAIL_FROM, to, subject, body["text"], body.get("html"),
                                    unsub_url=unsub, list_id="booking",
                                    related=body.get("related"))
    else:
        msg = emailkit.mime_message(MAIL_FROM, to, subject, body)
    emailkit.send_smtp(SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_FROM, to, msg)
    return "sent"


# ---- B-phase booking notifications (owner-approved 2026-09-17) -------------
# Ride the existing honest email layer: off = silent, log = dry-run visible in
# tests, smtp = live (when the owner drops creds in). Rules:
#   * only accounts with a VERIFIED email get mail (never raw strings)
#   * best-effort: notification failures NEVER fail the booking/money flow
#   * never called while holding LOCK (SMTP can take 15s -> would stall hub)
#   * every mail says how to turn notifications off (honest unsubscribe)


def _listing_of(b):
    with LOCK:
        return next((l for l in LISTINGS if l["id"] == b.get("listing_id")), None)


def _earnings_record_locked(b):
    """W3.4: record an earnings event the moment money settles to the
    listing owner (RELEASED via confirm, or DIRECT at booking). PRIVATE
    mirror keyed by listing owner - deliberately NEVER appended to the
    public LEDGER (recording owner+volume publicly would leak exactly
    what proveEarningsFloor exists to hide). Paid rails only: payout <= 0
    (WAIVED / zero-amount) is a no-op. Caller MUST hold LOCK."""
    lst = next((x for x in LISTINGS if x["id"] == b.get("listing_id")), None)
    if lst is None:
        return
    owner = lst.get("owner")
    try:
        payout = float(b.get("owner_payout") or 0)
    except (TypeError, ValueError):
        return
    if not owner or payout <= 0:
        return
    e = EARNINGS.setdefault(owner, {'settledCount': 0, 'totalVolume': 0.0, 'events': []})
    e['settledCount'] += 1
    e['totalVolume'] = round(e['totalVolume'] + payout, 2)
    e['events'].append(round(time.time(), 3))


def _acct_email_of(principal):
    """Verified email for an account principal whose notify pref is ON, or None.
    Per-recipient: each mail is gated by THAT account's preference."""
    if not (isinstance(principal, str) and principal.startswith("acct-")):
        return None
    a = ACCOUNTS.get(principal)
    if a and a.get("email_verified") and a.get("email") and a.get("notify_email") is not False:
        return a["email"]
    return None


def urlquote(s):
    from urllib.parse import quote as _q
    return _q(s, safe='')


def emailkit_digest(org_name, week_start, week_end, created, confirmed, cancelled,
                    gross, listings_active, unsub_url=None, loc='en'):
    import emailkit as _ek
    return _ek.organizer_digest(org_name=org_name, week_start=week_start,
        week_end=week_end, created=created, confirmed=confirmed,
        cancelled=cancelled, gross=gross, listings_active=listings_active,
        unsub_url=unsub_url, loc=loc)


def emailkit_code(kind, code, loc='en'):
    import emailkit as _ek
    return _ek.code_email(kind, code, loc=loc)


def _html_resp(self, code, html):
    body = html.encode()
    self.send_response(code)
    self.send_header("Content-Type", "text/html; charset=utf-8")
    self.send_header("Content-Length", str(len(body)))
    self.send_header("Cache-Control", "no-store")
    self.end_headers()
    self.wfile.write(body)


def _unsub_token(principal):
    import hmac as _hmac
    return _hmac.new(BOOKING_KEY.encode(), principal.encode(), 'sha256').hexdigest()[:32]


def _unsub_valid(princ, tok):
    import hmac as _hm
    try:
        return (isinstance(princ, str) and princ.startswith('acct-')
                and _hm.compare_digest(_unsub_token(princ), tok))
    except Exception:
        return False


def _notify_booking(event, booking, listing, *, extra=''):
    # Best-effort booking event mail to buyer and/or owner. Never raises.
    # Branded multipart templates (emailkit); every mail carries a signed
    # one-click unsubscribe link (RFC 8058) scoped to THAT account.
    try:
        import emailkit
        bid = booking.get('id', '?')
        title = (listing or {}).get('title', 'a listing')
        amt = booking.get('amount')
        esc = booking.get('escrow', '?')
        buyer_p = booking.get('booked_by')
        owner_p = (listing or {}).get('owner')
        buyer = _acct_email_of(buyer_p)
        owner = _acct_email_of(owner_p)

        def _unsub(principal):
            if not (isinstance(principal, str) and principal.startswith('acct-')):
                return None
            return '%s/accounts/notify/unsubscribe?u=%s&t=%s' % (
                emailkit.PUBLIC_URL, urlquote(principal), _unsub_token(principal))

        jobs = []
        if event == 'created' and owner:
            jobs.append(('created', owner, owner_p, 'owner'))
        if event == 'created' and buyer:
            # T5 mail (owner 2026-11-01): the QR ticket rides the booking
            # mail IMMEDIATELY - details inline, QR attached, no website
            # visit. Verified buyer accounts only (standing email law).
            try:
                import tickets as _tking
                if _tking.lookup_by_bid(TICKETS, bid) is not None:
                    jobs.append(('ticket', buyer, buyer_p, 'buyer'))
            except Exception:
                pass
        elif event == 'released' and buyer:
            jobs.append(('released', buyer, buyer_p, 'buyer'))
        elif event == 'refunded':
            if buyer:
                jobs.append(('refunded', buyer, buyer_p, 'buyer'))
            if owner:
                # hub event 'refunded' -> owner-facing template is 'cancelled'
                jobs.append(('cancelled', owner, owner_p, 'owner'))
        for ev, to, principal, role in jobs:
            _loc = 'de' if (ACCOUNTS.get(principal) or {}).get('email_lang') == 'de' else 'en'
            if ev == 'ticket':
                import tickets as _tking
                _tkr = _tking.lookup_by_bid(TICKETS, bid)
                if _tkr is None:
                    continue
                try:
                    _qr = _tking.qr_png(_tkr['token'], emailkit.PUBLIC_URL)
                except Exception:
                    _qr = None  # segno absent: mail still carries details + link
                tmpl = emailkit.ticket_email(
                    title=title, booking_id=bid,
                    when=str((listing or {}).get('date') or ''),
                    location=str((listing or {}).get('location') or ''),
                    qty=_tkr.get('qty', 1),
                    door_name=_tking.display_name_of(_tkr),
                    ticket_url=_tking.ticket_url(_tkr['token'], emailkit.PUBLIC_URL),
                    amount=amt, escrow=esc, qr=_qr,
                    listing_id=str((listing or {}).get('id') or ''),
                    unsub_url=_unsub(principal), loc=_loc)
            else:
                tmpl = emailkit.booking_email(ev, title=title, booking_id=bid,
                                              amount=amt, escrow=esc, role=role,
                                              note=(extra or None),
                                              unsub_url=_unsub(principal), loc=_loc)
            _send_email(to, tmpl['subject'], tmpl)
    except Exception as e:  # notifications must never break the money flow
        try:
            print('[notify:error] %s: %s' % (type(e).__name__, e), flush=True)
        except Exception:
            pass



if PAY_MODE == "testnet":
    FACIL = x402facilitate.FacilitatorClient(
        os.environ.get("HUB_FACILITATOR_URL", x402facilitate.DEFAULT_FACILITATOR),
        os.environ.get("HUB_FACILITATOR_KEY"), timeout=15)
    SETTLEMENTS = x402facilitate.SettlementRegistry()
# C3c: Cardano x402 instant rail — STABLECOIN-FIRST (tUSDM preprod default;
# ADA=lovelace is per-listing opt-in only). Flag off (no facilitator URL) =
# scheme NOT advertised at all (clean degradation). EXPERIMENTAL-preprod.
import cardano_x402
CARDANO_NET = "cardano:" + os.environ.get("HUB_CARDANO_NETWORK", "preprod").strip()
CARDANO_FACIL_URL = os.environ.get("HUB_CARDANO_FACILITATOR_URL", "").strip()
CARDANO_ON = bool(CARDANO_FACIL_URL)
CARDANO_SETTLEMENTS = cardano_x402.CardanoSettlementRegistry()  # always present (persistable)
if CARDANO_ON:
    CARDANO_FACIL = cardano_x402.CardanoFacilitatorClient(
        CARDANO_FACIL_URL, os.environ.get("HUB_CARDANO_FACILITATOR_KEY"), timeout=30)
    _da = cardano_x402.DEFAULT_ASSETS.get(CARDANO_NET) or []
    CARDANO_ASSET = os.environ.get("HUB_CARDANO_ASSET", "").strip() or (
        _da[0]["asset"] if _da else "")  # default = network stablecoin (tUSDM/USDM)
    CARDANO_PRICE = int(os.environ.get("HUB_CARDANO_PRICE", "0"))  # minor units
    CARDANO_PAYTO = os.environ.get("HUB_CARDANO_PAYTO", "").strip()  # merchant addr
    if not CARDANO_ASSET or not CARDANO_PAYTO or CARDANO_PRICE <= 0:
        sys.stderr.write("FATAL: Cardano rail on but HUB_CARDANO_ASSET/PAYTO/PRICE incomplete\n")
        sys.exit(1)
    CARDANO_LABEL = ("EXPERIMENTAL-preprod" if CARDANO_NET.endswith("preprod")
                     or CARDANO_NET.endswith("preview") else "EXPERIMENTAL")
    if CARDANO_ASSET == "lovelace":
        sys.stderr.write("WARN: Cardano rail asset=lovelace (ADA opt-in); exposure is"
                         " seconds only — never for value held across time\n")
# LEVEL-1 chain gating (owner-approved 2026-09-20): the hub never claims a
# money state the chain doesn't back. Opt-in: HUB_INDEXER_URL enables it;
# HUB_INDEXER_URL_2 adds a second, independent read for terminal flips
# (both sources must agree). Unset = legacy ungated behavior.
CHAIN_INDEXER = os.environ.get("HUB_INDEXER_URL", "").strip()
CHAIN_INDEXER_2 = os.environ.get("HUB_INDEXER_URL_2", "").strip()
CHAIN_GATE = bool(CHAIN_INDEXER)
# W2 #1: sponsor-relay mode (owner-approved Buildathon Wave 2 scope). When on,
# the hub covers organizer chain fees for escrow-rail bookings - gated by the
# abuse-resistant rules in sponsorship.py (per-org window limit, pool cap,
# stake threshold). Default OFF: real fee payment activates with the funded
# preprod E2E (M18); until then the gate + ledger are honest no-ops.
SPONSOR_RELAY = os.environ.get("HUB_SPONSOR_RELAY", "") == "1"


def _chain_gate_read(er, dual=False):
    """Read the escrow behind an escrow_ref from the configured indexer(s).

    Single source for intake checks (POST /book); dual source (both must
    succeed and agree) for terminal flips (/confirm, /cancel). Returns
    (escrow_dict, None) on success or (None, (http_code, body)) on failure.
    Never raises, never guesses - fail-closed on any doubt.
    """
    from midnight_indexer import EscrowIndexerClient, IndexerError
    sources = [CHAIN_INDEXER] if CHAIN_INDEXER else []
    if dual and CHAIN_INDEXER_2:
        sources.append(CHAIN_INDEXER_2)
    if not sources:
        return None, (503, {"error": "chain gate misconfigured (no indexer URL)"})
    results = []
    for url in sources:
        try:
            cli = EscrowIndexerClient(url, er["contract"], timeout=10.0)
            results.append(cli.escrow(er["escrow_id"]))
        except IndexerError as e:
            return None, (503, {"error": "chain verification unavailable (%s)" % e,
                                "note": "fail-closed: money transitions stay unchanged - retry shortly"})
        except Exception as e:  # malformed response, JSON error - same honest refusal
            return None, (503, {"error": "chain read failed (%s: %s)" % (type(e).__name__, e),
                                "note": "fail-closed: money transitions stay unchanged"})
    if len(results) == 2 and results[0]["state"] != results[1]["state"]:
        return None, (503, {"error": "indexer sources disagree on escrow state",
                            "note": "fail-closed: operator should compare both indexer sources"})
    return results[0], None


RATE_BOOKS_PER_MIN = int(os.environ.get("HUB_RATE_BOOKS_PER_MIN", "10"))

# C2: x402 premium endpoint config (wire format per payments_x402.md)
import base64
PREMIUM_PRICE_USD = float(os.environ.get("HUB_PREMIUM_PRICE_USD", "0.01"))
PAYTO = os.environ.get("HUB_PAYTO", "0x1111111111111111111111111111111111111111")  # SIMULATED default
BASE_SEPOLIA_USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"  # official testnet USDC
# G5: identities stay memory-only by default (no persistence of secrets/PII);

VERTICAL_SCHEMAS = {
    # H15: verticals are DATA. tracks_capacity = server-counts registrations
    # (events-style, registered increments/decrements); field_types = per-field
    # validation applied when the field is present; booking.fields = client-
    # settable booking fields; booking.identity = the ONE field whose real value
    # goes to the secret store (public copy gets an unlinkable anon-ref).
    "events": {"required": ["title", "date", "location", "price", "capacity"],
               "optional": ["description", "category", "tags", "url", "time", "lat", "lon", "series"],
               "categories": ["meetup", "concert", "workshop", "conference", "market",
                               "sports", "community", "party", "exhibition", "other"],
               "tracks_capacity": True,
               "field_types": {"capacity": "positive_int", "date": "nonempty", "time": "time_hhmm",
                                "lat": "float_latlon", "lon": "float_latlon"},
               "booking": {"required": ["attendee"], "fields": ["attendee", "quantity"],
                            "identity": "attendee", "action": "register+pay"}},
    "food":   {"required": ["title", "price"],  # merchant OPTIONAL (spec v2.1): validated at create, settable only via attach_merchant/detach_merchant
               "optional": ["description", "category", "tags", "url", "preparation_minutes"],
               "categories": ["pizzeria", "vegan", "asian", "burger", "bakery",
                               "cafe", "grocery", "other"],
               "field_types": {"preparation_minutes": "positive_int"},
               "booking": {"required": ["buyer", "quantity"], "fields": ["buyer", "quantity"],
                            "identity": "buyer", "action": "order+pay"}},
    # H15: second-vertical proof — adding a vertical is DATA, not code.
    "services": {"required": ["title", "provider", "price"],
                 "optional": ["description", "category", "tags", "url", "location",
                               "duration_minutes", "slot_minutes"],
                 "categories": ["cleaning", "repair", "tutoring", "design", "consulting",
                                 "wellness", "transport", "other"],
                 "field_types": {"duration_minutes": "positive_int", "slot_minutes": "positive_int"},
                 "booking": {"required": ["client"], "fields": ["client", "quantity", "slot_date", "slot_time"],
                              "identity": "client", "action": "book+pay"}},
}

# I1: field ownership. Server-owned fields may never come from clients.
def _escrow_guide(b):
    """DL-3 (mining 2026-10-31, zkEscrow transaction-center checklist): per-state
    plain-language next steps for an escrow-bearing booking, plus wallet-less
    verification pointers. Server-derived ONLY (state/escrow_ref from the
    booking row) - never client input. Present for every booking so agents get
    a stable shape; non-escrow rails explain their own state honestly."""
    state = str(b.get("escrow") or "HELD")
    ref = b.get("escrow_ref") or {}
    contract = ref.get("contract") or ""
    eid = ref.get("escrow_id") or ""
    verify = ("GET /escrow/%s/proof?contract=%s (verify-without-trust: dual-source"
              " indexer read, fail-closed)" % (eid, contract) if contract and eid else None)
    page = ("/verify?contract=%s&escrow=%s" % (contract, eid)) if contract and eid else None
    STEPS = {
        "HELD": "Funds are protected in escrow. Fulfillment happens next; after the refund window closes the organizer is paid. You can watch the chain state any time.",
        "DISPUTED": "Booking is frozen for arbitration: no release and no refund until resolved. Both parties can contact the hub.",
        "RELEASED": "Escrow released to the organizer - settlement is final and published on the public ledger.",
        "REFUNDED": "Escrow refunded to the buyer - settlement is final and published on the public ledger.",
        "WAIVED": "No money moves on this booking (free listing) - there is no escrow to watch.",
        "DIRECT": "Instant rail: payment settled directly at booking time (no protected hold).",
    }
    return {
        "state": state,
        "what_now": STEPS.get(state, "Escrow state " + state + " - see /how for what states mean."),
        "chain_verification": {
            "endpoint": verify,
            "wallet_less_page": page,
            "available": bool(verify)},
        "ledger": "GET /ledger or /transparency (public, pseudonymous)",
    }


RESERVED_BOOKING_FIELDS = {"id", "vertical", "escrow", "amount", "hub_fee",
    "owner_payout", "created", "booking_secret", "rail", "confirmation",
    "verified_by", "payment_terms", "claim", "promo_applied",
    "payment_payer", "payment_value", "payment_nonce"}  # M14: verification provenance is server-derived only; C12: terms snapshot is server-copied from the listing (clients echo consent via accepted_payment_terms, never claim terms); S6: x402 payment evidence is server-verified, never client-claimed

# EverList taxonomy: category = controlled vocab per vertical (validated at
# listing time); tags = free-form, normalized (lowercase, trimmed, deduped,
# capped). Both are optional; search is faceted over vertical+category+tags.
TAXONOMY = {"tag_max": 8, "tag_len": 24}


def normalize_tags(raw):
    """Free-form tags -> clean list. Accepts list or "a, b" string."""
    if raw is None:
        return []
    if isinstance(raw, str):
        raw = raw.replace(";", ",").split(",")
    if not isinstance(raw, list):
        raise ValueError("tags must be a list or comma-separated string")
    tags = []
    for t in raw[: TAXONOMY["tag_max"] * 3]:  # input cap before dedupe
        t = str(t).strip().lower()[: TAXONOMY["tag_len"]]
        if t and t not in tags:
            tags.append(t)
        if len(tags) >= TAXONOMY["tag_max"]:
            break
    return tags
RESERVED_LISTING_FIELDS = {"id", "registered", "available", "owner", "manage_code_hash", "claim_code_hash",
    "rating_sum", "rating_count", "rating_avg", "free_rating_sum", "free_rating_count",
    "rating_wsum", "rating_wtot", "review_flags", "rating_times",
    "image", "_sponsor", "series_id"}  # owner = authenticated principal; manage_code_hash/claim_code_hash = server-only (anti-spoof, P2); rating aggregates = S6 server-owned (clients can never seed fake reputation); image is upload-only (B2: set via POST /listings/{id}/image, never client-settable)

# C12: payment-terms policy (SPEC §19, owner-pinned 2026-09-12). Terms live on
# the LISTING; booking = acceptance (paid bookings echo custom terms via
# accepted_payment_terms); changes post-booking need both parties. Escrow is
# the default rail whenever real money attaches; x402 instant is the merchant's
# per-listing opt-in (no refund window — that is the trade-off). Defaults per
# SPEC §19c: events/services 72h, food (marketplace-style) 7 days.
PAYMENT_TERMS_RAILS = ("escrow", "instant")
_PAYMENT_WINDOW_MIN, _PAYMENT_WINDOW_MAX = 1, 720  # hours
_DEFAULT_REFUND_WINDOW_HOURS = {"events": 72, "services": 72, "food": 168}


def _default_payment_terms(vertical):
    return {"rail": "escrow", "refund_window_hours": _DEFAULT_REFUND_WINDOW_HOURS.get(vertical, 72),
            "deposit_required": 0.0}


def _normalize_payment_terms(raw, price, vertical):
    """Validate/normalize client-supplied payment_terms. Returns
    (terms_dict_or_None, error_or_None). Unknown keys rejected (I1 style);
    window integer-bounded; deposit bounded to [0, price]; instant + window is
    a contradiction (instant means settled-at-booking)."""
    if raw is None:
        return None, None
    if not isinstance(raw, dict):
        return None, "payment_terms must be an object"
    unk = [k for k in raw if k not in ("rail", "refund_window_hours", "deposit_required")]
    if unk:
        return None, f"payment_terms unknown keys rejected: {sorted(unk)}"
    rail = raw.get("rail", "escrow")
    if rail not in PAYMENT_TERMS_RAILS:
        return None, f"payment_terms.rail must be one of {list(PAYMENT_TERMS_RAILS)}"
    dep = raw.get("deposit_required")
    if dep is None:
        dep_out = 0.0
    else:
        try:
            dep_out = float(dep)
        except (TypeError, ValueError):
            return None, "payment_terms.deposit_required must be a number"
        if dep_out != dep_out or dep_out < 0 or (price is not None and dep_out > price):
            return None, "payment_terms.deposit_required must be a number between 0 and the listing price"
    if rail == "instant":
        if raw.get("refund_window_hours") not in (None, 0):
            return None, "instant rail has no refund window (that is the trade-off); omit refund_window_hours or use the escrow rail"
        return {"rail": "instant", "refund_window_hours": 0, "deposit_required": dep_out}, None
    w = raw.get("refund_window_hours")
    if w is None:
        w = _DEFAULT_REFUND_WINDOW_HOURS.get(vertical, 72)
    if isinstance(w, bool) or not isinstance(w, int) or not (_PAYMENT_WINDOW_MIN <= w <= _PAYMENT_WINDOW_MAX):
        return None, f"payment_terms.refund_window_hours must be an integer in [{_PAYMENT_WINDOW_MIN}, {_PAYMENT_WINDOW_MAX}]"
    return {"rail": "escrow", "refund_window_hours": w, "deposit_required": dep_out}, None


def _listing_is_custom_terms(listing):
    t = listing.get("payment_terms")
    if not t:
        return False
    return t != _default_payment_terms(listing.get("vertical", "events"))


# C5: community vertical schemas — drop-in extension point (verticals are DATA).
# Organizers contribute schemas/<name>.json (process: docs/community-schemas.md);
# the hub validates each file FAIL-CLOSED at boot: a bad community file is
# rejected + logged, never crashes the hub and never weakens a built-in.
# Built-ins always win: files cannot override events/food/services.

def _load_community_schemas():
    sdir = os.environ.get("HUB_SCHEMAS_DIR",
                          os.path.join(os.path.dirname(os.path.abspath(__file__)), "schemas"))
    if not os.path.isdir(sdir):
        return
    _types = {"positive_int", "nonempty", "float_latlon"}  # + float_latlon (D1 2026-10-15): lat/lon for client-side distance
    _top = {"name", "required", "optional", "categories", "tracks_capacity",
            "field_types", "booking", "description"}
    # price/capacity are NOT in this wall: they are structurally governed
    # ('price' must be required; 'capacity' required iff tracks_capacity; the
    # req/opt-overlap check blocks dual listing). The wall keeps out the
    # SERVER-OWNED fields only (identity/escrow/owner/counter fields).
    _server = RESERVED_LISTING_FIELDS | RESERVED_BOOKING_FIELDS
    for fn in sorted(os.listdir(sdir)):
        if not fn.endswith(".json"):
            continue
        try:
            with open(os.path.join(sdir, fn)) as fh:
                raw = json.load(fh)
            if not isinstance(raw, dict):
                raise ValueError("top level must be an object")
            unk = [k for k in raw if k not in _top]
            if unk:
                raise ValueError(f"unknown top-level keys: {sorted(unk)}")
            name = str(raw.get("name", "")).strip().lower()
            if not re.fullmatch(r"[a-z][a-z0-9_]{2,15}", name):
                raise ValueError("name must match [a-z][a-z0-9_]{3,16}")
            if name in VERTICAL_SCHEMAS:
                print(f"[schemas] {fn}: ignored - built-in vertical '{name}' cannot be overridden", flush=True)
                continue
            req = [str(x) for x in (raw.get("required") or [])]
            opt = [str(x) for x in (raw.get("optional") or [])]
            if not req:
                raise ValueError("required must be a non-empty list")
            if set(req) & set(opt):
                raise ValueError("fields cannot be both required and optional")
            bad = [f for f in req + opt if f in _server]
            if bad:
                raise ValueError(f"server-owned fields are not community-settable: {sorted(bad)}")
            if "price" not in req:
                raise ValueError("'price' must be required (escrow accounting depends on it)")
            cats = [str(c).strip().lower() for c in (raw.get("categories") or [])]
            if not cats or len(set(cats)) != len(cats):
                raise ValueError("categories must be a non-empty duplicate-free list")
            ft = raw.get("field_types") or {}
            if not isinstance(ft, dict) or any(t not in _types for t in map(str, ft.values())):
                raise ValueError(f"field_types values must be in {sorted(_types)}")
            ft = {str(k): str(v) for k, v in ft.items()}
            if set(ft) - (set(req) | set(opt)):
                raise ValueError("field_types keys must be declared required/optional fields")
            tracks = bool(raw.get("tracks_capacity", False))
            if tracks and "capacity" not in req:
                raise ValueError("tracks_capacity=true requires 'capacity' in required")
            bk = raw.get("booking") or {}
            b_req = [str(x) for x in (bk.get("required") or [])]
            b_fields = [str(x) for x in (bk.get("fields") or [])]
            ident = str(bk.get("identity", "")).strip()
            action = str(bk.get("action", "")).strip()
            if not b_req or not b_fields or not ident:
                raise ValueError("booking.required, booking.fields and booking.identity are all required")
            if not set(b_req) <= set(b_fields):
                raise ValueError("booking.required must be a subset of booking.fields")
            if ident not in b_req:
                raise ValueError("booking.identity must be a required booking field")
            bad_b = [f for f in b_fields if f in RESERVED_BOOKING_FIELDS]
            if bad_b:
                raise ValueError(f"booking fields may not use reserved names: {sorted(bad_b)}")
            if not re.fullmatch(r"[a-z]+(\+[a-z]+)*", action):
                raise ValueError("booking.action must look like 'book+pay'")
            VERTICAL_SCHEMAS[name] = {
                "required": req, "optional": opt, "categories": cats,
                "tracks_capacity": tracks, "field_types": ft,
                "booking": {"required": b_req, "fields": b_fields,
                            "identity": ident, "action": action}}
            print(f"[schemas] community vertical '{name}' loaded from {fn}", flush=True)
        except Exception as ex:
            print(f"[schemas] REJECTED {fn}: {ex}", flush=True)


_load_community_schemas()

# H15: client-settable booking fields DERIVED from the vertical schemas —
# adding a vertical (built-in or community) extends this automatically (no code edit).
CLIENT_BOOKING_FIELDS = {v: set(s["booking"]["fields"])
                         for v, s in VERTICAL_SCHEMAS.items()}

def hub_fee_c(price_c):
    """Hub-declared fee (G3: HUB_FEE_PCT env, default 2%). Integer minor units internally."""
    return (price_c * int(round(FEE_PCT * 100))) // 10000


def hub_fee(price):
    """Fair fee on major units (edge adapter over integer internals)."""
    return hub_fee_c(int(round(price * 100))) / 100.0

# ---- H13: machine-readable API contract (OpenAPI 3.1) -----------------------
# H13b (run #9): component schemas for the core resources, sampled from the
# LIVE wire (isolated hub, seeded free+paid listings, full booking flow) and
# validated against real responses by test_openapi_contract.py.
# Privacy law: owner/attendee/buyer fields are pseudonymous principals or
# random anon- refs — no personal data ever appears in listing/booking/ledger JSON.
_SCHEMAS = {
    "Listing": {
        "type": "object",
        "description": "Public listing view. Vertical-optional fields are absent when the "
                       "vertical doesn't define them (events: date/location/capacity/registered; "
                       "food: merchant; services: provider). No currency field on the wire "
                       "(v0.2 single hub unit; amounts in major units).",
        "required": ["id", "vertical", "title", "price"],
        "properties": {
            "id": {"type": "string", "description": "public listing id (even-/food-/srv- prefixed)"},
            "vertical": {"type": "string"},
            "title": {"type": "string"},
            "price": {"type": "number", "description": "major units; 0 = free"},
            "date": {"type": "string", "description": "YYYY-MM-DD (capacity verticals)"},
            "location": {"type": "string"},
            "capacity": {"type": "integer"},
            "registered": {"type": "integer", "description": "server-counted registrations (tracks_capacity verticals)"},
            "available": {"type": "boolean"},
            "visibility": {"type": "string", "enum": ["public", "private"]},
            "owner": {"type": "string", "description": "owner-anonymized: pseudonymous principal (agent name / acct- ref), never personal data"},
            "category": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "image": {"type": "string", "description": "listing photo as data URL - set ONLY via POST /listings/{id}/image (B2 upload-only law)"},
            "description": {"type": "string"},
            "url": {"type": "string"},
            "merchant": {"type": "string"},
            "provider": {"type": "string"},
            "preparation_minutes": {"type": "integer"},
            "duration_minutes": {"type": "integer"},
            "payment_terms": {"$ref": "#/components/schemas/PaymentTerms"},
            "rating_sum": {"type": "integer"},
            "rating_count": {"type": "integer"},
            "free_rating_sum": {"type": "integer"},
            "free_rating_count": {"type": "integer"},
            "checkout": {"type": "object", "description": "Non-secret UI hint only; session creation and booking revalidate all gates.",
                         "properties": {"eligible": {"type": "boolean"}, "mode": {"type": "string", "enum": ["testnet", "demo", "unavailable"]}}},
            "price_preview": {"type": "object", "description": "Server-calculated one-place total, same rounding as hosted checkout. Organizer commission is not added to the buyer price.",
                              "properties": {"quantity": {"type": "integer"}, "total": {"type": "number"}, "buyer_fee": {"type": "number"}}},
            "demo": {"type": "boolean", "description": "true only on seed/curated-example supply (server-derived, never client-claimed) — demo boards must never read as live organizers (A6 2026-11-04)"},
        },
    },
    "PaymentTerms": {
        "type": "object",
        "description": "Listing payment terms (vertical default or custom; booking = exact consent, SPEC 19).",
        "required": ["rail", "refund_window_hours", "deposit_required"],
        "properties": {
            "rail": {"type": "string", "enum": ["escrow", "instant"]},
            "refund_window_hours": {"type": "integer", "minimum": 1, "maximum": 720},
            "deposit_required": {"type": "number", "minimum": 0},
        },
    },
    "ListingList": {
        "type": "object",
        "description": "Listing collection wrapper (GET /listings; GET /search adds a filters object — extra properties allowed).",
        "required": ["count", "offset", "limit", "returned", "listings"],
        "properties": {
            "count": {"type": "integer"},
            "offset": {"type": "integer"},
            "limit": {"type": "integer"},
            "returned": {"type": "integer"},
            "listings": {"type": "array", "items": {"$ref": "#/components/schemas/Listing"}},
        },
    },
    "Booking": {
        "type": "object",
        "description": "Booking record as served by GET /bookings (and private_details in GET /book/{id}). "
                       "The buyer-anonymized identity field is exactly one of attendee/buyer/client, "
                       "chosen by the vertical, and holds a random anon- unlinkable ref.",
        "required": ["id", "listing_id", "vertical", "escrow", "amount", "hub_fee",
                     "owner_payout", "created", "booked_by", "payment_terms"],
        "properties": {
            "id": {"type": "string", "pattern": "^bk-"},
            "listing_id": {"type": "string"},
            "vertical": {"type": "string"},
            "escrow": {"type": "string", "enum": ["HELD", "WAIVED", "DIRECT", "RELEASED", "REFUNDED", "DISPUTED", "ARB_RELEASED", "ARB_REFUNDED"]},
            "amount": {"type": "number", "description": "total in major units; 0 = free booking"},
            "hub_fee": {"type": "number"},
            "owner_payout": {"type": "number"},
            "quantity": {"type": "integer", "minimum": 1},
            "created": {"type": "number", "description": "unix epoch seconds"},
            "booked_by": {"type": "string", "description": "pseudonymous booking principal"},
            "payment_terms": {"$ref": "#/components/schemas/PaymentTerms"},
            "attendee": {"type": "string", "description": "events identity field: anon- unlinkable ref in public views, real value only in private details"},
            "buyer": {"type": "string", "description": "food/p2p identity field: anon- ref in public views, real value only in private details"},
            "client": {"type": "string", "description": "services identity field: anon- ref in public views, real value only in private details"},
            "worker": {"type": "string", "description": "jobs identity field (community vertical): anon- ref in public views"},
            "rating": {"type": "integer", "minimum": 1, "maximum": 5},
            "escrow_ref": {"type": "object", "description": "optional on-chain escrow link {contract, escrow_id, tx}"},
        },
    },
    "BookingCreated": {
        "type": "object",
        "description": "POST /book 201: Booking plus one-time credentials (booking_secret shown ONCE).",
        "allOf": [
            {"$ref": "#/components/schemas/Booking"},
            {"type": "object",
             "required": ["booking_secret", "secret_note", "cancel_token", "flow"],
             "properties": {
                 "booking_secret": {"type": "string", "description": "shown ONCE; credential for GET /book/{id}"},
                 "secret_note": {"type": "string"},
                 "cancel_token": {"type": "string"},
                 "flow": {"type": "array", "items": {"type": "string"}},
             }},
        ],
    },
    "OrderList": {
        "type": "object",
        "description": "Principal-scoped bookings wrapper (GET /bookings): the caller's own order list.",
        "required": ["bookings", "principal", "note"],
        "properties": {
            "bookings": {"type": "array", "items": {"$ref": "#/components/schemas/Booking"}},
            "principal": {"type": "string"},
            "note": {"type": "string"},
        },
    },
    "PrivateBooking": {
        "type": "object",
        "description": "GET /book/{id}: private details behind the one-time booking secret.",
        "required": ["id", "private_details"],
        "properties": {
            "id": {"type": "string"},
            "private_details": {"$ref": "#/components/schemas/Booking"},
        },
    },
    "ListingCreated": {
        "type": "object",
        "description": "POST /listings 201: manage_code shown ONCE.",
        "required": ["ok", "id", "manage_code", "manage_note"],
        "properties": {
            "ok": {"type": "boolean", "const": True},
            "id": {"type": "string"},
            "manage_code": {"type": "string", "pattern": "^mgr-"},
            "manage_note": {"type": "string"},
        },
    },
    "EarningsView": {
        "type": "object",
        "description": "GET /organizer/earnings 200: private mirror of settled payouts (owner-only).",
        "required": ["settledCount", "totalVolume"],
        "properties": {
            "settledCount": {"type": "integer"},
            "totalVolume": {"type": "number"},
            "events": {"type": "integer"},
            "principal": {"type": "string"},
            "note": {"type": "string"},
            "zk": {"type": "string"},
        },
    },
    "EarningsProof": {
        "type": "object",
        "description": "POST /organizer/earnings-proof 200: revenue-floor proof - pass/fail only, totals never disclosed.",
        "required": ["met", "thresholds"],
        "properties": {
            "met": {"type": "boolean"},
            "thresholds": {"type": "object", "properties": {
                "min_settlements": {"type": "integer"},
                "min_volume": {"type": "number"}}},
            "protocol": {"type": "string"},
            "zk_contract": {"type": "string"},
        },
    },
    "ConfirmResponse": {
        "type": "object",
        "description": "POST /book/{id}/confirm 200: owner fulfillment, escrow RELEASED (instant-rail bookings settle at booking and skip confirm).",
        "required": ["ok", "id", "escrow"],
        "properties": {
            "ok": {"type": "boolean", "const": True},
            "id": {"type": "string"},
            "escrow": {"type": "string", "enum": ["RELEASED", "DIRECT"]},
            "owner_received": {"type": "number"},
            "confirmation": {"type": "string"},
        },
    },
    "CancelResponse": {
        "type": "object",
        "description": "POST /book/{id}/cancel 200: buyer pre-fulfillment cancel, full refund.",
        "required": ["ok", "id", "escrow"],
        "properties": {
            "ok": {"type": "boolean", "const": True},
            "id": {"type": "string"},
            "escrow": {"type": "string", "enum": ["REFUNDED"]},
        },
    },
    "RateResponse": {
        "type": "object",
        "description": "POST /book/{id}/rate 200: buyer rating after settlement; free bookings go to the separate free-feedback channel.",
        "required": ["ok", "id", "rating", "channel"],
        "properties": {
            "ok": {"type": "boolean", "const": True},
            "id": {"type": "string"},
            "rating": {"type": "integer", "minimum": 1, "maximum": 5},
            "channel": {"type": "string"},
            "aggregate": {"type": "string"},
            "note": {"type": "string"},
        },
    },
    "LedgerEntry": {
        "type": "object",
        "description": "One append-only money event (GET /ledger). Three kinds: booking entries "
                       "(default; escrow updated on transition, original fee retained on refund "
                       "for audit), x402_settlement (detail object), escrow_sync (chain mirror). "
                       "Pseudonymous: booking refs only, no participant identity.",
        "required": ["ts"],
        "properties": {
            "kind": {"type": "string", "description": "absent = booking entry; else x402_settlement | escrow_sync"},
            "ts": {"type": "number", "description": "unix epoch seconds"},
            "booking": {"type": "string"},
            "amount": {"type": "number"},
            "hub_fee": {"type": "number"},
            "owner_payout": {"type": "number"},
            "escrow": {"type": "string", "enum": ["HELD", "WAIVED", "DIRECT", "RELEASED", "REFUNDED", "DISPUTED", "ARB_RELEASED", "ARB_REFUNDED"]},
            "released_to": {"type": "string"},
            "detail": {"type": "object", "description": "x402_settlement: {fingerprint, tx, value, payer (pseudonymized anon-*), network}"},
            "from": {"type": "string", "description": "escrow_sync: prior hub state"},
            "to": {"type": "string", "description": "escrow_sync: new chain state"},
            "chain_tx": {"type": "string", "description": "escrow_sync: chain transaction"},
        },
    },
    "Ledger": {
        "type": "object",
        "description": "GET /ledger wrapper: full append-only ledger plus hub totals.",
        "required": ["ledger", "totals"],
        "properties": {
            "ledger": {"type": "array", "items": {"$ref": "#/components/schemas/LedgerEntry"}},
            "totals": {"type": "object", "required": ["total_volume", "total_hub_fees", "x402_settlements"],
                       "properties": {"total_volume": {"type": "number"},
                                      "total_hub_fees": {"type": "number"},
                                      "x402_settlements": {"type": "integer"}}},
            "settled_volume": {"type": "number"},
            "settled_hub_fees": {"type": "number"},
            "note": {"type": "string"},
            "privacy": {"type": "string"},
        },
    },
    "Error": {
        "type": "object",
        "description": "Uniform error body; hint/note and a few flow-specific extras (retry_after, payment_terms, how, verified) may appear.",
        "required": ["error"],
        "properties": {
            "error": {"type": "string"},
            "hint": {"type": "string"},
            "note": {"type": "string"},
        },
    },
    "VerticalSchema": {
        "type": "object",
        "description": "One vertical's data-driven schema (VERTICAL_SCHEMAS; community verticals add more).",
        "required": ["required", "optional", "categories", "booking"],
        "properties": {
            "required": {"type": "array", "items": {"type": "string"}},
            "optional": {"type": "array", "items": {"type": "string"}},
            "categories": {"type": "array", "items": {"type": "string"}},
            "tracks_capacity": {"type": "boolean"},
            "field_types": {"type": "object"},
            "booking": {"type": "object", "required": ["required", "fields", "identity", "action"],
                        "properties": {"required": {"type": "array", "items": {"type": "string"}},
                                       "fields": {"type": "array", "items": {"type": "string"}},
                                       "identity": {"type": "string"},
                                       "action": {"type": "string"}}},
        },
    },
    "Verticals": {
        "type": "object",
        "description": "GET /verticals: registry keyed by vertical name.",
        "required": ["verticals"],
        "properties": {"verticals": {"type": "object",
                                     "additionalProperties": {"$ref": "#/components/schemas/VerticalSchema"}}},
    },
    "Manifest": {
        "type": "object",
        "description": "GET /.well-known/agent-hub.json discovery manifest.",
        "required": ["protocol", "api_contract"],
        "properties": {
            "protocol": {"type": "string"},
            "api_contract": {"type": "string", "const": "/openapi.json"},
            "hub": {"type": "string"},
            "open_source": {"type": "string"},
            "license_model": {"type": "string"},
        },
    },
    "OpenAPI": {
        "type": "object",
        "description": "GET /openapi.json: this contract document itself.",
        "required": ["openapi", "info", "paths"],
        "properties": {"openapi": {"type": "string"}, "info": {"type": "object"}, "paths": {"type": "object"}},
    },
}


def _openapi_spec():
    """H13: OpenAPI 3.1 contract, built from the VERIFIED route inventory.
    test_h13_openapi.py proves every documented path+method is really handled
    (never the generic 404 catch-all) — the spec cannot lie about a route."""
    def op(summary, tag, sec=None, note=None):
        o = {"summary": summary, "tags": [tag]}
        if sec:
            o["security"] = sec
        if note:
            o["description"] = note
        return o
    tok = [{"X-Hub-Token": []}]
    spec = {
        "openapi": "3.1.0",
        "info": {
            "title": "EverList Hub API",
            "version": "agent-hub/0.2",
            "description": "Open, community-driven commerce hub for AI agents. "
                           "Credentials travel ONLY in the X-Hub-Token header; writes carry "
                           "an Idempotency-Key. Normative contract: SPEC.md. "
                           "Schema note (run #9 H13b): core response schemas live under "
                           "components/schemas (Listing, Booking, OrderList, LedgerEntry, Error, ...), "
                           "sampled from live-wire responses; vertical-specific request fields "
                           "come from /verticals. Error strings remain non-normative."},
        "tags": [{"name": t} for t in
                 ("discovery", "listings", "bookings", "accounts", "payments", "registry", "admin")],
        "paths": {
            "/.well-known/agent-hub.json": {"get": op("Discovery manifest", "discovery")},
            "/.well-known/x402.json": {"get": op("x402 payment discovery (DL-1)", "discovery",
                                        note="machine-readable payment terms at the standard agents-probe location; built from the same constants as the live 402 on /premium/events")},
            "/ticket/{token}": {"get": op("T5 door ticket honest status (capability URL)", "bookings",
                                 note="projection: event, date, qty, door name (buyer-chosen choice), redeemed state; capability law - the token holder IS the attendee (you_are_buyer), you_are_owner only with the listing owner token; page is noindex/no-store")},
            "/ticket/{token}/name": {"post": op("Door-display name via the ticket capability itself", "bookings",
                                     note="holder of the ticket token IS the attendee (capability law); body display_name + display_choice full|first|guest; name is explicit UGC, never silently persisted identity")},
            "/ticket/{token}/redeem": {"post": op("ONE-TIME door check-in (owner action)", "bookings",
                                       note="owner proof like /confirm: admin confirm token, owning acct- list token, or listing manage_code; first scan wins, later scans honestly report first_time=false with the original time")},
            "/escrow/{id}/proof": {"get": op("Verify-without-trust escrow proof (DL-2)", "bookings",
                                        note="?contract=<address> (or HUB_ESCROW_CONTRACT); escrow re-read from indexer(s), dual-source when configured, FAIL-CLOSED on disagreement; no booking details, pseudonymous booking_ref only")},
            "/manifest.json": {"get": op("Legacy manifest alias", "discovery")},
            "/openapi.json": {"get": op("This contract (OpenAPI 3.1)", "discovery")},
            "/verticals": {"get": op("Vertical schema registry", "discovery")},
            "/listings": {
                "get": op("Public listings (query: vertical, archived)", "listings",
                          note="?archived=1 is OWNER-ONLY (auth required)"),
                "post": {**op("Create listing (manage_code ONCE; visibility:private adds a one-time claim_code)", "listings", sec=tok,
                           note="optional payment_terms {rail: escrow|instant, refund_window_hours 1-720, deposit_required <= price}; omitted = vertical default (escrow, 72h events/services, 168h food); optional require_verified_buyer: true gates booking to Tier-2-verified accounts (SPEC section 22)"),
                           "responses": {"409": {"description": "cap reached (honest counts: cap, active) or duplicate of an active listing (existing id)"}}}},
            "/listings/{id}": {"get": op("One listing, full rich record (private deals need ?claim= or X-Claim-Code)", "listings",
                                        note="404 unknown / 410 archived")},
            "/listings/{id}/manage": {"post": op("Edit/archive/unarchive/make_private/make_public/delete a listing (plus archive_series/delete_series on recurring series)", "listings", sec=tok,
                                  note="series acts: action=archive_series hides every dated sibling at once; delete_series removes the family — both refuse while any member holds active bookings")},
            "/listings/{id}/image": {"post": op("Set or clear the listing photo (owning acct- token, or list token + manage_code; clear:true removes)", "listings", sec=tok,
                                          note="body {data_url: data:image/png|jpeg|webp;base64,...} or {clear:true}; SVG refused; decoded cap 380KB; stored same-origin as a data URL (CSP img-src data:)")},
            "/search": {"get": op("Search listings (q, from/to date, min/max_price, tags=, sort, near=lat,lon, radius_km=, after/before=HH:MM, ...)", "listings",
                                  note="from/to = YYYY-MM-DD on the listing date (dateless listings excluded); "
                                       "tags=comma,any-of; sort=date|price|newest|distance (newest = creation order reversed); "
                                       "geo: near=lat,lon + optional radius_km= (listings without lat/lon excluded); "
                                       "time: after=/before=HH:MM zero-padded 24h on the listing time (time-less listings excluded); "
                                       "sort=distance requires near=; matched listings carry distance_km; "
                                       "sponsorship: admin-granted listings ride the LAST page position (capped 1), labeled sponsored=true")},
            "/listing/draft": {
                "post": op("Paste-a-flyer OR share-a-link: free text or an existing page URL -> prefilled listing DRAFT (never creates; organizer confirms then POSTs /listings); engine: regex always, LLM-assisted when the enrichment chain is live, URL pages read schema.org JSON-LD first (response names engine+model)", "listings", sec=tok,
                           note="body {text} or {url} (not both); deterministic extraction (title/date/time/price/location); URL fetches are SSRF-walled (public hosts only, 1MB cap, html-only) and rate-limited per source; response carries needs_confirm [date,price] — never trust AI-extracted prices without review")},
            "/merchants": {
                "post": op("Create a merchant profile (unique kebab slug; fulfillment pickup/delivery/shipping/onsite; locations + promos; per-owner cap); update/delete via POST /merchants/{slug} action=update|delete (owner-walled; delete refuses 409 while active listings are attached and cascades the catalog)", "listings", sec=tok,
                           note="owner = token principal; listings attach via {merchant: slug} at create or manage action attach_merchant/detach_merchant (ownership-walled both ways); public GET /merchants/{slug} returns profile + the merchant's OWN uncapped listings + catalog summary; feed quota (default 2/merchant) applies only to the general /listings feed")},
            "/catalogs": {
                "post": op("Create a versioned catalog tree for a merchant (depth<=3, items need title, price numeric)", "listings", sec=tok,
                           note="one catalog per merchant; replace via POST /catalogs/{id}/replace bumps version and REQUIRES content change (same content_hash -> 409); public GET /catalogs/{id} returns version+content_hash+tree, ?fields=summary omits the tree, ?since_hash=<hash> -> 304 when unchanged; catalog items NEVER appear in /listings or /search listing results - they surface as grouped catalog_items")},
            "/bookings": {"get": op("Your bookings (principal-scoped)", "bookings", sec=tok)},
            "/bookings/{id}": {"get": op("Booking status (buyer or listing owner)", "bookings", sec=tok,
                                        note="unknown-or-not-yours = indistinguishable 404 (no existence oracle)")},
            "/orders": {"get": op("Incoming orders for listings you own", "bookings", sec=tok)},
            "/book/{id}": {"get": op("Private booking details", "bookings", sec=tok,
                                    note="credential = booking secret (shown once at creation), via X-Hub-Token header")},
            "/book": {"post": op("Create booking (escrow HELD / WAIVED at price 0 / DIRECT on the instant rail; testnet instant bookings accept an optional X-PAYMENT EIP-3009 header -> verified payer wallet bound for S6 review integrity)", "bookings", sec=tok,
                                 note="Idempotency-Key supported; verified-human gate applies; optional escrow_ref {contract, escrow_id, tx} links the on-chain escrow (escrow-rail paid bookings only; REQUIRED for escrow-rail paid bookings when chain gating is enabled via HUB_INDEXER_URL - SPEC section 24). Custom payment terms (SPEC §19): paid bookings on listings with non-default terms must echo accepted_payment_terms exactly (409 otherwise; the error returns the terms). Listings with require_verified_buyer accept ONLY Tier-2-verified accounts (server-side; the human_verified stub never counts, SPEC section 22)")},
            "/book/{id}/confirm": {"post": op("Owner confirms booking (escrow RELEASE)", "bookings", sec=tok)},
            "/book/{id}/cancel": {"post": op("Buyer cancels pre-fulfillment (full refund)", "bookings", sec=tok)},
            "/book/{id}/dispute": {"post": op("Either party freezes a HELD booking for arbitration (DISPUTED; no release or refund until resolved)", "bookings", sec=tok)},
            "/branding": {"get": op("Public page branding (partner-editable fields only)", "discovery"),
                          "post": op("Update branding (owner acct- token ONLY; fixed rails rejected)", "bookings", sec=tok,
                                     note="fields: brand_name, tagline, hero_text, logo_url(https), location, accent(#RRGGBB), accent2(#RRGGBB), theme(dark|light), about_text, site_url(https), instagram_url(https, instagram.com host), lang(de|en); MERGE: absent=unchanged, empty=cleared")},
            "/branding/image": {"post": op("Upload branding image (owner acct- token ONLY)", "bookings", sec=tok,
                                          note="body {kind: logo|hero, data_url: data:image/png|jpeg|webp;base64,...}; SVG refused; decoded caps logo 90KB / hero 420KB; stored same-origin as data URL")},
            "/organizer/earnings": {"get": op("W3.4: organizer earnings view (private mirror of settled payouts; owner-only)", "bookings", sec=tok,
                                   note="totals are exactly what proveEarningsFloor hides - owner token required")},
            "/organizer/earnings-proof": {"post": op("W3.4: revenue-floor proof - PASS/FAIL only for verifier-chosen {min_volume, min_settlements}; actual totals never disclosed", "bookings", sec=tok,
                                        note="pilot mirror check with the honesty of earnings.compact proveEarningsFloor; on-chain proof is the organizer act (M25/M26)")},
            "/organizer/batch-settle": {"post": op("W3.3: organizer batch settle - release ALL your HELD/WAIVED bookings in ONE call (per-booking chain gate verify-then-flip; DISPUTED untouched)", "bookings", sec=tok,
                                        note="pilot hub surface for the on-chain batchRelease2 circuit; per-booking walls all applied")},
            "/book/{id}/transfer": {"post": op("Buyer transfers booking to a new attendee name (pre-fulfillment; rotates secret + cancel token)", "bookings", sec=tok)},
            "/book/{id}/rate": {"post": op("Buyer rates a settled booking 1-5 (once)", "bookings", sec=tok,
                                note="buyer's own book token; escrow must be RELEASED, WAIVED or DIRECT (instant = settled at booking); free (amount 0; channel set by economic value, not the mutable escrow label - run #5) ratings go to a separate free-feedback channel, paid aggregates are amount-weighted, self-reviews rejected (S6); ledger untouched")},
            "/admin/sync-escrow": {"post": op("Mirror sync: pull chain escrow state into the hub (admin)", "admin",
                                              note="X-Admin-Key required; chain is source of truth; downward overwrites refused (C7)")},
            "/mcp": {"post": op("Model Context Protocol endpoint (JSON-RPC 2.0): initialize / tools/list / tools/call over the six everlist_* tools", "discovery",
                                note="thin adapter onto this same REST contract; auth = X-Hub-Token header only (a token in tool arguments is ignored - MCP-ARGS law)")},
            "/access": {"post": op("Bootstrap tokens for an agent identity (interim open)", "accounts",
                                  note="acct- principals refused; accounts use /accounts/login")},
            "/accounts/signup": {"post": op("Create account (PoW-gated; keypair or legacy code)", "accounts")},
            "/accounts/login": {"post": op("Login (ed25519 challenge-response or legacy code)", "accounts")},
            "/accounts/vouch": {"post": op("Operator vouches for a human (pilot-era)", "accounts")},
            "/accounts/rotate": {"post": op("Rotate account code (old code dies instantly)", "accounts")},
            "/accounts/logout-all": {"post": op("Revoke all tokens (generation bump)", "accounts")},
            "/accounts/email/bind": {"post": op("Bind recovery email (code sent)", "accounts")},
            "/accounts/email/verify": {"post": op("Verify email code", "accounts")},
            "/checkout/sessions": {"post": op("Create embeddable checkout session (TRACK E)", "checkout",
                note="Public listings carry checkout:{eligible,mode}, a non-secret UI hint; sessions revalidate all walls. Public, rate-limited. Creates a hosted checkout session (chk- capability URL) for a PUBLIC listing. FREE listings: demo rail, escrow WAIVED at booking (no money moves). PAID listings: wallet rail (E7) on testnet hubs (HUB_PAY_MODE=testnet) - the session face carries payment_request (receiver/units/asset) and the verify step takes the buyer's EIP-3009 signature; money moves exactly when the booking lands. Paid sessions are refused honestly on non-testnet hubs (TRACK E4/E5 fiat deferred). Payment terms + total are snapshotted at create; listing changes stale the session.")},
            "/checkout/sessions/{sid}": {"get": op("Checkout session status", "checkout",
                note="Capability-URL face: status, masked email, listing snapshot, total. No secrets.")},
            "/checkout/sessions/{sid}/pay": {"post": op("Checkout pay step", "checkout",
                note="POST {email, name} binds the buyer and emails a 6-digit code (cooldown + per-address mail cap).")},
            "/checkout/sessions/{sid}/verify": {"post": op("Checkout verify step", "checkout",
                note="POST {code} proves mailbox control (bind-or-create account, Tier-1 email law) and books through the shared booking engine. PAID sessions (wallet rail): POST {code, payment} - the buyer's EIP-3009 payment (base64 x402 envelope, signed for the session face's payment_request) is verified by the booking engine itself; money moves exactly when the booking lands (atomic pay+book; a proven code without payment returns honest 402 and burns no attempt). The 201 carries the one-time booking credentials (buyer channel only; merchant postMessage gets booking_id only).")},
            "/accounts/email/recover": {"post": op("Request recovery code (anti-enumeration)", "accounts")},
            "/accounts/email/recover/confirm": {"post": op("Confirm recovery -> NEW account code", "accounts")},
            "/accounts/notify/unsubscribe": {"get": op("Unsubscribe landing page (signed link from email footer)", "accounts"),
                                             "post": op("One-click unsubscribe (RFC 8058)", "accounts")},
            "/accounts/payout": {"post": op("Register organizer payout coin PUBLIC key (64-hex; secrets never accepted)", "accounts")},
            "/accounts/notify": {"post": op("Booking-notification preference (notify_email: true|false)", "accounts")},
            "/accounts/lang": {"post": op("Email language preference (email_lang: 'en'|'de') - booking mails, digest, codes", "accounts")},
            "/accounts/verify-midnight": {"post": op("Tier-2 sign-in: verify a Midnight credential (admitted + not revoked) and mark the account verified_by: midnight-zk", "accounts",
                                         note="fail-closed; mode (chain|simulated) labels the verification source")},
            "/accounts/me": {"delete": op("Account self-deletion (GDPR-style; ledger survives pseudonymously)", "accounts", sec=tok)},
            "/premium/events": {"get": op("Premium data (x402 payment)", "payments",
                                         note="402 + payment instructions without a valid payment header")},
            "/ledger": {"get": op("Public append-only money ledger (pseudonymous)", "registry")},
            "/registry": {"get": op("Open hub registry (self-listed)", "registry")},
            "/challenge": {"get": op("Registry ownership proof (echo nonce)", "registry")},
            "/auth/challenge": {"get": op("Signup PoW / login challenges", "accounts",
                                         note="?kind=signup | ?kind=login&pubkey=<64hex>")},
            "/admin/tokens": {"post": op("Operator: mint action tokens (admin key)", "admin")},
            "/admin/sponsor": {"post": op("Sponsor a listing (admin): labeled, capped placement — organic order is never for sale", "admin", sec=tok,
                                  note="body {listing_id, days 1..60}; sponsored listing appears LAST per results page with sponsored=true; grant is admin-only")},
        },
        "components": {"securitySchemes": {"X-Hub-Token": {
            "type": "apiKey", "in": "header", "name": "X-Hub-Token"}},
            "schemas": _SCHEMAS},
    }

    # H13b: attach $ref response schemas INSIDE each core operation object
    # (OpenAPI: responses belong to the operation, never the path item).
    for _m, _p, _code, _sch, _desc in (
        ("get", "/listings", "200", "ListingList", "Listing collection"),
        ("post", "/listings", "201", "ListingCreated", "Listing created (manage_code shown once)"),
        ("get", "/listings/{id}", "200", "Listing", "Full listing record"),
        ("get", "/search", "200", "ListingList", "Search results"),
        ("get", "/bookings", "200", "OrderList", "Principal-scoped bookings"),
        ("get", "/book/{id}", "200", "PrivateBooking", "Private booking details (booking secret)"),
        ("post", "/book", "201", "BookingCreated", "Booking created (booking_secret shown once)"),
        ("post", "/checkout/sessions", "201", "CheckoutSession", "Checkout session created"),
        ("get", "/checkout/sessions/{sid}", "200", "CheckoutSession", "Checkout session status"),
        ("post", "/checkout/sessions/{sid}/pay", "200", "CheckoutPending", "Checkout email bound, code sent"),
        ("post", "/checkout/sessions/{sid}/verify", "201", "CheckoutBooked", "Checkout booking created"),
        ("post", "/book/{id}/confirm", "200", "ConfirmResponse", "Owner confirmed (escrow RELEASED)"),
        ("post", "/book/{id}/cancel", "200", "CancelResponse", "Buyer cancelled (full refund)"),
        ("post", "/book/{id}/dispute", "200", "CancelResponse", "Dispute opened (funds frozen for arbitration)"),
        ("get", "/organizer/earnings", "200", "EarningsView", "Organizer earnings view (private mirror)"),
        ("post", "/organizer/earnings-proof", "200", "EarningsProof", "Revenue-floor proof (pass/fail only)"),
        ("post", "/organizer/batch-settle", "200", "BatchSettle", "Organizer batch settle: release ALL your HELD/WAIVED bookings in one call (per-booking chain gate; disputes untouched)"),
        ("post", "/book/{id}/rate", "200", "RateResponse", "Rating recorded"),
        ("get", "/ledger", "200", "Ledger", "Public money ledger"),
        ("get", "/verticals", "200", "Verticals", "Vertical schema registry"),
        ("get", "/.well-known/agent-hub.json", "200", "Manifest", "Discovery manifest"),
        ("get", "/openapi.json", "200", "OpenAPI", "This contract document"),
    ):
        spec["paths"][_p][_m]["responses"] = {
            _code: {"description": _desc,
                    "content": {"application/json": {"schema": {
                        "$ref": f"#/components/schemas/{_sch}"}}}},
        }
    # S7: document both 409s on POST /listings (cap + duplicate)
    spec["paths"]["/listings"]["post"]["responses"]["409"] = {
        "description": "cap reached (honest counts: cap, active) or duplicate of an active listing (existing id)"}
    return spec


class Handler(BaseHTTPRequestHandler):
    def _json(self, code, data, extra_headers=None):
        # CATALOGS hardening (RFC 9110): 204/304 MUST NOT carry a body - a
        # 304 especially must not imply a Content-Length for representation
        # data it deliberately does not contain.
        if code in (204, 304):
            rid = "req-" + secrets.token_hex(8)  # H12: per-request trace id
            self.send_response(code)
            for k, v in (extra_headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            if _reqlog is not None:  # H12
                try:
                    p = self.path.split("?", 1)[0][:120]
                    lat = (time.time() - getattr(self, "_t0", time.time())) * 1000.0
                    _reqlog.info("%s %s -> %d %.1fms src=%s rid=%s",
                                 getattr(self, "command", "?"), p, code, lat,
                                 _source_of(self), rid)
                except Exception:
                    pass
            return
        body = json.dumps(data, indent=2).encode()
        rid = "req-" + secrets.token_hex(8)  # H12: per-request trace id
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Request-Id", rid)  # H12: echoed for support/traceability
        for k, v in (extra_headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        if _reqlog is not None:  # H12: bounded request log — never breaks the hub
            try:
                p = self.path.split("?", 1)[0][:120]  # query NEVER logged (challenges/nonces), truncated
                lat = (time.time() - getattr(self, "_t0", time.time())) * 1000.0
                _reqlog.info("%s %s -> %d %.1fms src=%s rid=%s",
                             getattr(self, "command", "?"), p, code, lat,
                             _source_of(self), rid)
            except Exception:
                pass

    def _cardano_premium(self, pay_hdr: str, dec: dict):
        """C3c: Cardano x402 instant rail (stablecoin-first, EXPERIMENTAL-preprod).

        Payload = x402 v2 Cardano shape {transaction, nonce} inside our v1
        X-PAYMENT envelope (documented transport deviation). Verify delegates
        to the facilitator's read-only /verify (no local CBOR crypto); settle
        follows the CHAOS pattern (pending under LOCK -> HTTP unlocked ->
        ledger+persist re-LOCK). A retry of the SAME payload while settlement
        is pending RESUMES observation (upstream protocol); terminal records
        and the nonce wall block replays.
        """
        def _402(detail):
            return self._json(402, {"x402Version": 1, "error": "invalid payment",
                                    "detail": detail, "mode": CARDANO_LABEL,
                                    "network": CARDANO_NET})
        if not CARDANO_ON:
            return _402("cardano rail not enabled on this hub")
        if dec.get("scheme") != "exact" or dec.get("network") != CARDANO_NET:
            return _402(f"scheme/network mismatch: {dec.get('scheme')}/{dec.get('network')}"
                        f" (advertised: exact/{CARDANO_NET})")
        inner = dec.get("payload") or {}
        if not isinstance(inner, dict) or not inner.get("transaction") or not inner.get("nonce"):
            return _402("malformed cardano payload: need payload.transaction + payload.nonce (txHash#index)")
        nonce = str(inner["nonce"])
        if "#" not in nonce:
            return _402("nonce must be a UTXO reference txHash#index")
        reqs = {"scheme": "exact", "network": CARDANO_NET, "asset": CARDANO_ASSET,
                "amount": str(CARDANO_PRICE), "maxAmountRequired": str(CARDANO_PRICE),
                "payTo": CARDANO_PAYTO, "maxTimeoutSeconds": 600,
                "extra": {"assetTransferMethod": "default",
                          "confirmationPolicy": {"l1Confirmations": 1}}}
        # pending-resume: same payload retry while settlement is non-terminal
        if cardano_x402.nonce_used(nonce):
            rec = next((r for r in CARDANO_SETTLEMENTS.snapshot().values()
                        if r.get("nonce") == nonce), None)
            if rec is not None and rec.get("status") == "pending":
                srec = CARDANO_SETTLEMENTS.settle(rec["fingerprint"], dec, reqs, CARDANO_FACIL)
                with LOCK:
                    if srec.get("status") == "settled":
                        LEDGER.append({"kind": "x402_settlement", "ts": time.time(),
                                        "detail": {"fingerprint": rec["fingerprint"],
                                                    "tx": srec.get("tx", ""),
                                                    "value": CARDANO_PRICE,
                                                    "payer": cardano_x402.payer_pseudonym(rec.get("payer", "")),
                                                    "network": CARDANO_NET,
                                                    "asset": CARDANO_ASSET}})
                    _persist_locked()
                return self._cardano_feed(dec, srec, rec.get("fingerprint", ""),
                                          rec.get("payer", ""))
            return _402("replayed payment (nonce already used)")
        # 1) facilitator verify (read-only) - runs UNLOCKED (no shared state)
        st, vresp = CARDANO_FACIL._call("verify", {"paymentPayload": dec,
                                                    "paymentRequirements": reqs})
        if st != 200 or not vresp.get("isValid"):
            reason = vresp.get("invalidReason") or vresp.get("error") or f"verify http {st}"
            return _402(f"facilitator verify rejected: {str(reason)[:120]}")
        payer = str(vresp.get("payer", ""))
        fp = cardano_x402.payment_fingerprint_c(
            {"payment_id": nonce, "payer_address": payer,
             "payto_address": CARDANO_PAYTO, "amount": CARDANO_PRICE,
             "asset": CARDANO_ASSET})
        # 2) under LOCK: burn nonce + durable pending marker BEFORE the HTTP hop
        with LOCK:
            cardano_x402.mark_nonce_used(nonce)
            srec = None
            if SETTLE_MODE == "auto":
                CARDANO_SETTLEMENTS.mark_pending(fp, nonce=nonce, payer=payer)
            _persist_locked()
        # 3) settle UNLOCKED (CHAOS 2026-09-20: never hold LOCK across HTTP)
        if SETTLE_MODE == "auto":
            srec = CARDANO_SETTLEMENTS.settle(fp, dec, reqs, CARDANO_FACIL)
            with LOCK:
                if srec.get("status") == "settled":
                    LEDGER.append({"kind": "x402_settlement", "ts": time.time(),
                                    "detail": {"fingerprint": fp, "tx": srec.get("tx", ""),
                                                "value": CARDANO_PRICE,
                                                "payer": cardano_x402.payer_pseudonym(payer),
                                                "network": srec.get("network", CARDANO_NET),
                                                "asset": CARDANO_ASSET}})
                _persist_locked()  # settlement record + ledger event persisted together
        return self._cardano_feed(dec, srec, fp, payer)

    def _cardano_feed(self, dec: dict, srec: dict | None, fp: str, payer: str):
        """Shared 200 responder for the Cardano rail (feed + honest settlement state)."""
        with LOCK:
            res = [l for l in LISTINGS if l["vertical"] == "events" and l.get("visibility") != "private"]
            rich = [{**_pub_listing(l), "premium_meta": {"owner_public": l.get("owner", ""),
                     "fill_ratio": round(l.get("registered", 0) / max(1, l.get("capacity", 1)), 3),
                     "payment": {"mode": CARDANO_LABEL, "verified": True,
                                  "settlement": (srec["status"] if srec else "pending (HUB_SETTLE_MODE=off)"),
                                  "fingerprint": fp,
                                  "payer": cardano_x402.payer_pseudonym(payer),
                                  "payer_note": "pseudonymized: stable per wallet for anti-abuse analytics; raw credential stays server-side (W2 privacy)"}}} for l in res]
        if srec is not None and srec.get("status") == "settled":
            settle_info = {"status": "SETTLED", "tx": srec.get("tx", ""),
                            "network": srec.get("network", CARDANO_NET),
                            "asset": CARDANO_ASSET}
        elif srec is not None and srec.get("status") == "pending":
            settle_info = {"status": "PENDING", "tx": srec.get("tx", ""),
                            "note": "settlement_pending - retry the SAME payment to resume observation; never rebuild the transaction"}
        elif srec is not None and srec.get("status") == "unknown":
            settle_info = {"status": "UNKNOWN",
                            "note": "facilitator timeout/error - outcome unproven; check facilitator before retry"}
        elif srec is not None:
            settle_info = {"status": "FAILED", "error": srec.get("error", "facilitator rejected")}
        else:
            settle_info = {"status": "NOT_ATTEMPTED",
                            "note": "HUB_SETTLE_MODE=off - verified only; set auto to settle via facilitator"}
        pay_resp = {"success": bool(srec and srec.get("status") == "settled"),
                    "network": CARDANO_NET,
                    "transaction": (srec or {}).get("tx", ""),
                    "slot": ((srec or {}).get("extra") or {}).get("slot"),
                    "errorReason": (None if not srec or srec.get("status") == "settled"
                                    else ("settlement_pending" if srec.get("status") == "pending"
                                          else srec.get("error", "settlement_failed"))),
                    "extra": {"status": (srec or {}).get("status", "not_attempted"),
                              "label": CARDANO_LABEL}}
        hdr = {"X-PAYMENT-RESPONSE": base64.b64encode(json.dumps(pay_resp).encode()).decode()}
        return self._json(200, {"mode": CARDANO_LABEL,
            "payment": {"scheme": "exact", "network": CARDANO_NET,
                         "asset": CARDANO_ASSET, "value": CARDANO_PRICE,
                         "verified": True, "settlement": settle_info,
                         "fingerprint": fp},
            "count": len(rich), "events": rich}, extra_headers=hdr)

    # ---------------- TRACK E methods (embeddable checkout, E2/E3) ----------------
    def _serve_listing_image(self, lid_ext):
        """SEO 2026-11-07: fetchable per-listing photo at /img/{id}.{ext} so
        og:image/JSON-LD point at a REAL organizer upload instead of the brand
        default (data URLs are invisible to crawlers/unfurlers). Walls:
        public+unarchived listings ONLY (private deals keep the no-oracle
        uniform 404), magic-byte sniff png/jpeg/webp (SVG refused, mirrors the
        upload law), decoded cap 380KB, nosniff, short cache (photo swaps stay
        honest within 5 min)."""
        import base64 as _b64, re as _re
        m = _re.match(r"^([A-Za-z0-9_-]+)\.(png|jpg|webp)$", lid_ext or "")
        if not m:
            return self._json(404, {"error": "no image"})
        lid, ext = m.group(1), m.group(2)
        if not _read_gate(self):
            return self._json(429, {"error": "too many read requests — slow down (retry shortly)"})
        with LOCK:
            l = next((x for x in LISTINGS if x["id"] == lid), None)
            du = str((l or {}).get("image") or "")
            lvis = (l or {}).get("visibility", "public")
            larch = (l or {}).get("archived", False)
        if not l or larch or lvis != "public" or not du.startswith("data:image/"):
            return self._json(404, {"error": "no image"})
        mm = _re.match(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$", du)
        if not mm:
            return self._json(404, {"error": "no image"})
        ctype = {"png": "image/png", "jpeg": "image/jpeg", "webp": "image/webp"}[mm.group(1)]
        # URL ext must map 1:1 to the stored type (png->png, jpg->jpeg, webp->webp)
        if {"png": "png", "jpeg": "jpg", "webp": "webp"}[mm.group(1)] != ext:
            return self._json(404, {"error": "no image"})
        try:
            body = _b64.b64decode(mm.group(2), validate=True)
        except Exception:
            return self._json(404, {"error": "no image"})
        if len(body) > 380 * 1024 or len(body) < 8:
            return self._json(404, {"error": "no image"})
        sig = body[:4]
        ok = (sig.startswith(b"\x89PNG") if mm.group(1) == "png"
              else sig.startswith(b"\xff\xd8\xff") if mm.group(1) == "jpeg"
              else body[:4] == b"RIFF" and body[8:12] == b"WEBP")
        if not ok:
            return self._json(404, {"error": "no image"})
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "max-age=300")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'")
        self.end_headers()
        self.wfile.write(body)
        return None

    def _serve_checkout_asset(self, fname):
        """Strict-allowlist static server for checkout assets (literal fnames
        only; normpath guard keeps the traversal wall even if that changes)."""
        base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
        fpath = os.path.normpath(os.path.join(base, fname))
        if not fpath.startswith(base + os.sep) or not os.path.isfile(fpath):
            return self._json(404, {"error": "asset missing"})
        ctype = ("text/html; charset=utf-8" if fname.endswith(".html")
                 else "application/javascript; charset=utf-8")
        with open(fpath, "rb") as fh:
            body = fh.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if fname.endswith(".html") else "max-age=300")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; "
                         "connect-src 'self'; img-src 'self' data:; form-action 'self'; "
                         "base-uri 'none'; frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
        self.end_headers()
        self.wfile.write(body)
        return None

    def _checkout_session(self, sid, sub, data):
        """Shared session lookup + expiry + stale detection, then dispatch.
        sub: '' (status face), 'pay' or 'verify'."""
        with LOCK:
            sess = CHECKOUT_SESSIONS.get(sid)
            if not sess:
                return self._json(404, {"error": "no checkout session"})
            if sess["exp"] < time.time():
                CHECKOUT_SESSIONS.pop(sid, None)
                _persist_locked()
                return self._json(410, {"error": "checkout session expired",
                    "how": "start again from the merchant site"})
            if sess["status"] in ("open", "pending_verify"):
                # lazy stale detection: archived/made-private/re-priced/re-termsed
                # under the session -> honest dead end (email stays verified)
                listing = next((l for l in LISTINGS if l["id"] == sess["listing_id"]), None)
                stale = (not listing or listing.get("archived")
                         or listing.get("visibility") == "private")
                if not stale:
                    _pt = listing.get("payment_terms") or _default_payment_terms(listing["vertical"])
                    try:
                        _tot = int(round(float(listing.get("price", 0)) * 100)) * sess["qty"]
                    except (TypeError, ValueError):
                        _tot = -1
                    stale = (_pt != sess["terms"] or _tot != sess.get("total_c", -1))
                if stale:
                    sess["status"] = "stale"
                    _persist_locked()
            status = sess["status"]
        if status == "stale":
            return self._json(409, {"error": "listing changed - this checkout is no longer valid",
                "how": "start a new checkout on the merchant site"})
        if sub == "":
            face = _checkout_face(sess)
            return self._json(200, {"ok": True, "sid": sid, "status": status,
                "rail": sess["rail"], "email_masked": _checkout_mask(sess.get("email", "")),
                "exp": sess["exp"], "pay_exp": sess.get("pay_exp", 0),
                "booking_id": sess.get("booking_id") or None, **face})
        if sub == "pay":
            return self._checkout_pay(sess, data)
        return self._checkout_verify(sess, data)

    def _checkout_pay(self, sess, data):
        """Pay step: bind email + name to the session and email a 6-digit code.
        No money moves HERE: free listings book escrow-WAIVED at verify; paid
        listings (wallet rail, PAY_MODE=testnet) take the buyer's wallet
        signature AT verify - money moves exactly when the booking lands."""
        email = str(data.get("email", "")).strip().lower()
        if not email or "@" not in email or "." not in email.rsplit("@", 1)[1] or len(email) > 254 or " " in email:
            return self._json(400, {"error": "valid email required (name@domain.tld)"})
        name = str(data.get("name", "")).strip()
        if not name or len(name) > 80 or _BAD_CHARS_RE.search(name):
            return self._json(400, {"error": "name required (max 80 chars, no control characters)"})
        now = time.time()
        with LOCK:
            if not _auth_allow("checkout_pay", _source_of(self)):
                return self._json(429, {"error": "checkout rate limit reached for your source, retry later"})
            if sess["status"] == "booked":
                return self._json(409, {"error": "already booked", "booking_id": sess["booking_id"]})
            if sess["status"] == "stale":
                return self._json(409, {"error": "listing changed - start a new checkout on the merchant site"})
            if sess["status"] == "processing":
                return self._json(409, {"error": "booking already in progress - GET the session for status"})
            if sess["status"] not in ("open", "pending_verify"):
                return self._json(409, {"error": "checkout session not open"})
            if sess["status"] == "pending_verify" and sess.get("email") and email != sess["email"]:
                return self._json(409, {"error": "email already bound to this checkout - start a new session for another address"})
            live = sess["status"] == "pending_verify" and sess.get("pay_exp", 0) > now
            if live and now - sess.get("last_code", 0) < CHECKOUT_RESEND_COOLDOWN:
                retry = int(CHECKOUT_RESEND_COOLDOWN - (now - sess.get("last_code", 0))) + 1
                return self._json(429, {"error": "code already sent - retry later", "retry_after": retry},
                                  extra_headers={"Retry-After": str(retry)})
            if not _checkout_mail_allow(email, now):
                return self._json(429, {"error": "too many verification emails for this address - try again later"})
            code = secrets.token_hex(3).upper()
            sess["status"] = "pending_verify"
            sess["email"] = email
            sess["name"] = name
            sess["code_hash"] = hashlib.sha256(code.encode()).hexdigest()
            sess["pay_exp"] = now + CHECKOUT_PENDING_TTL
            sess["attempts"] = 0
            sess["last_code"] = now
            _persist_locked()
            d = emailkit_code("verify", code, loc=sess.get("lang", "en"))
        delivered = bool(_send_email(email, d["subject"], d))
        resp = {"ok": True, "status": "pending_verify",
                "email_masked": _checkout_mask(email), "pay_exp": sess["pay_exp"],
                "rail": sess["rail"]}
        if delivered:
            resp["delivery"] = "sent"
        else:
            resp["delivery"] = "suppressed"
            resp["note"] = ("email delivery is off on this hub (HUB_EMAIL_MODE=off) - "
                            "checkout cannot complete until SMTP or log mode is configured")
        return self._json(200, resp)

    def _checkout_verify(self, sess, data):
        """Verify step: the 6-digit code proves mailbox control (Tier-1 email
        law, owner GO 2026-10-03). Bind-or-create the account (one email = one
        account), then book through the SHARED _book_core engine with an
        internally minted, gen-bound book token - identical gates, zero drift.
        The 201 body carries the one-time booking credentials - buyer-only
        channel (this HTTPS session); merchant postMessage gets booking_id only."""
        code = str(data.get("code", "")).strip().upper()
        now = time.time()
        with LOCK:
            if sess["status"] == "booked":
                return self._json(409, {"error": "already booked", "booking_id": sess["booking_id"]})
            if sess["status"] == "processing":
                return self._json(409, {"error": "booking already in progress - GET the session for status"})
            if sess["status"] == "stale":
                return self._json(409, {"error": "listing changed - start a new checkout"})
            if sess["status"] != "pending_verify":
                return self._json(400, {"error": "pay first",
                    "how": "POST /checkout/sessions/{sid}/pay {email, name}"})
            if not sess.get("code_hash") or sess.get("pay_exp", 0) < now:
                sess["status"] = "open"
                _persist_locked()
                return self._json(410, {"error": "verification window expired",
                    "how": "POST /pay again for a fresh code"})
            if sess["attempts"] >= CHECKOUT_MAX_ATTEMPTS:
                return self._json(429, {"error": "too many wrong codes - request a fresh one via /pay"})
            sess["attempts"] += 1
            if not code or not hmac.compare_digest(sess["code_hash"], hashlib.sha256(code.encode()).hexdigest()):
                _persist_locked()
                return self._json(403, {"error": "invalid code",
                    "attempts_left": max(0, CHECKOUT_MAX_ATTEMPTS - sess["attempts"])})
            # E7 wallet-pay: paid sessions move money AT booking time only -
            # the signed payment rides THIS call into _book_core, so a proven
            # code without a wallet signature costs nothing (no money moved,
            # no nonce consumed) and the attempt is not burned.
            payment_b64 = ""  # free sessions move no money
            if sess.get("total_c", 0) > 0:
                if PAY_MODE != "testnet":
                    return self._json(409, {"error": "paid checkout requires PAY_MODE=testnet on this hub"})
                payment_b64 = str(data.get("payment", "") or "").strip()
                if not payment_b64:
                    sess["attempts"] = 0  # code proven correct - wallet hiccup must not punish it
                    _persist_locked()
                    return self._json(402, {"error": "wallet signature required for paid checkout",
                        "how": "approve the payment in your wallet, then confirm the code again"})
            # mailbox control proven -> bind-or-create (one email = one account)
            email, name = sess["email"], sess["name"]
            aid = next((a for a, v in ACCOUNTS.items()
                        if v.get("email") == email and v.get("email_verified")), None)
            if not aid:
                if len(ACCOUNTS) >= ACCOUNTS_CAP:
                    return self._json(429, {"error": "hub at account capacity; contact the operator"})
                aid = "acct-" + secrets.token_hex(4)
                while aid in ACCOUNTS:
                    aid = "acct-" + secrets.token_hex(4)
                ACCOUNTS[aid] = {"bound": [], "created": time.time(),
                                 "email_lang": sess.get("lang", "en"),
                                 "email": None, "email_verified": False,
                                 "notify_email": True, "marketing_email": True,
                                 "pending_email": None, "pending_code_hash": None,
                                 "pending_exp": 0, "recovery_code_hash": None,
                                 "recovery_exp": 0, "payout_pk": None,
                                 "midnight_credential": None, "gen": 0}
            acct = ACCOUNTS[aid]
            acct["email"] = email
            acct["email_verified"] = True
            acct["human_verified"] = True          # Tier-1 email-code law
            acct["verified_by"] = "email-code"
            acct["pending_email"] = None
            acct["pending_code_hash"] = None
            acct["pending_exp"] = 0
            sess["acct_id"] = aid
            sess["status"] = "processing"
            sess["code_hash"] = None
            _persist_locked()
            tok = hublib.mint_token(BOOKING_KEY, "book", aid, ttl=120,
                                    extra={"gen": int(acct.get("gen", 0))})
            lid, qty = sess["listing_id"], sess["qty"]
            listing = next((l for l in LISTINGS if l["id"] == lid), None)
            idf = VERTICAL_SCHEMAS[listing["vertical"]]["booking"]["identity"] if listing else "name"
        # booking engine OUTSIDE the LOCK (it takes LOCK internally)
        book = {"listing_id": lid, idf: name}
        if qty > 1:
            book["quantity"] = qty
        # E7: echo snapshotted terms for paid listings with CUSTOM terms
        # (C12 consent law, mirrors the engine's own validation; the stale
        # wall guarantees listing terms == sess['terms'] at verify time)
        if listing and (listing.get("price") or 0) > 0 and _listing_is_custom_terms(listing):
            book["accepted_payment_terms"] = sess["terms"]
        # E7: payment rides INTO the engine - money moves exactly when the
        # booking lands (atomic pay+book). payment=None for free sessions.
        payment = payment_b64 if payment_b64 else None
        bcode, bbody, beh = self._book_core(book, token=tok, idem_key=sess["sid"], payment=payment)
        with LOCK:
            if bcode == 201 and isinstance(bbody, dict):
                sess["status"] = "booked"
                sess["booking_id"] = str(bbody.get("id", ""))
                sess["payment_payer"] = str(bbody.get("payment_payer") or "")
                _persist_locked()
                _moved = "paid wallet rail - money moved" if (sess.get("total_c", 0) > 0) else "demo rail - no money moved"
                return self._json(201, {**bbody,
                    "checkout": {"sid": sess["sid"], "rail": sess["rail"], "money": _moved,
                                 "payment_payer": sess.get("payment_payer") or None,
                                 "note": "booked via embeddable checkout"}},
                    extra_headers=beh)
            # honest failure: reopen the session (email/account stay verified);
            # pass the REAL booking error through (capacity race, field walls...)
            sess["status"] = "open"
            _persist_locked()
            if isinstance(bbody, dict):
                bbody = {**bbody, "note": "email verified and kept - POST /pay for a fresh code to retry"}
            return self._json(bcode, bbody, extra_headers=beh)


    def _bk_json(self, code, data, extra_headers=None):
        """Book-core exit shim: tuple result instead of an HTTP write."""
        return (code, data, extra_headers)

    def _seek_apply(self, data, listing, principal, acct_t2):
        """SEEK vetted application: records an APPLICATION (no booking, no
        ledger entry, no capacity change). require_verified_worker enforces
        the Tier-2 wall fail-closed (email-code NEVER satisfies it). The
        applicant message lives in APPLICATIONS only - same private-store
        discipline as booking secrets; public surfaces show counts."""
        if listing.get("require_verified_worker") and not acct_t2:
            return self._bk_json(403, {"error": "this seek requires a Tier-2-verified worker",
                "note": "verify via POST /accounts/verify-midnight (fail-closed Midnight personhood credential); chat: 'verify-midnight <credential_id>'",
                "verified": False})
        with LOCK:
            if listing.get("archived"):
                return self._bk_json(409, {"error": "listing archived - not bookable"})
            lid = listing["id"]
            _apps = [a for a in APPLICATIONS.values()
                     if a["listing_id"] == lid and a["filler"] == principal and a["status"] == "pending"]
            if _apps:
                return self._bk_json(409, {"error": f"you already have a pending application on {lid}",
                    "application_id": _apps[0]["id"]})
            msg = data.get("message")
            if msg is not None:
                msg = _BAD_CHARS_RE.sub("", str(msg)).strip()[:300] or None
            v = listing["vertical"]
            allowed_bf = CLIENT_BOOKING_FIELDS[v] | {"quantity", "human_verified"}
            book_fields = {k: data[k] for k in data if k in allowed_bf}
            _n = ID_COUNTERS.get("app", 0) + 1
            ID_COUNTERS["app"] = _n
            aid = f"app-{_n}"
            APPLICATIONS[aid] = {"id": aid, "listing_id": lid, "filler": principal,
                "book_fields": book_fields, "message": msg, "status": "pending",
                "created": time.time()}
            _persist_locked()
        return self._bk_json(201, {"ok": True, "application_id": aid, "status": "pending",
            "note": "application recorded - the seeker accepts or declines; no money moved"})

    def _book_core(self, data, token=None, claim=None, idem_key=None, payment=None, _accept_replay=False):
        """Booking engine core (extracted verbatim from the /book route).

        Returns (code, body, extra_headers). The HTTP route wraps this;
        checkout sessions call it with an internally minted book token so
        embedded bookings pass the EXACT same gates (zero drift).

        """
        cred = token if token is not None else self.headers.get("X-Hub-Token", "")  # I2: book token (route header or internal mint)
        p, err = hublib.verify_token(BOOKING_KEY, cred, "book", single_use=False) if cred \
            else (None, "missing X-Hub-Token")
        if not p:
            if cred:  # valid token but wrong action => authenticated, not authorized
                for other in ("list",):
                    po, _ = hublib.verify_token(BOOKING_KEY, cred, other, single_use=False)
                    if po:
                        return self._bk_json(403, {"error": f"token is for '{other}', not 'book'"})
            return self._bk_json(401, {"error": err or "invalid book token",
                "hint": "POST /access {agent: '<your-agent>', acts: ['book']} then send token as X-Hub-Token",
                "note": "interim open bootstrap; production = Midnight zk-personhood (A2)"})
        p, gerr = _gen_check(p)  # B1
        if not p:
            return self._bk_json(401, {"error": gerr or "token revoked",
                "hint": "log in again (POST /accounts/login) for fresh tokens"})
        principal = p["sub"]
        # H5: per-source backstop — G4 caps per principal, but principals are
        # freely mintable pre-personhood; rotation must not defeat flooding
        with LOCK:
            if not _auth_allow("book", _source_of(self)):
                return self._bk_json(429, {"error": "booking rate limit reached for your source, retry later"})
        # B3c-accounts: verified accounts carry their human proof server-side
        # (admin-vouch pilot / email-code deploy / Midnight zk A2 production)
        acct_verified = False
        if principal.startswith("acct-"):
            with LOCK:
                acct = ACCOUNTS.get(principal)
            if acct and acct.get("human_verified"):
                acct_verified = True
        if not data.get("human_verified") and not acct_verified:
            return self._bk_json(403, {"error": "booking requires verified-human credential",
                "note": "production: zk-proof of personhood (Midnight); interim: verified EverList account or stub flag"})
        # G4: per-principal fixed-window rate limit (default 10 books / 60s,
        # HUB_RATE_BOOKS_PER_MIN env) - derived from the VERIFIED token principal,
        # not attacker-chosen payload names
        now = time.time()
        with LOCK:
            hist = [t for t in RATE_LIMITS.setdefault(principal, []) if now - t < 60]
            if len(hist) >= RATE_BOOKS_PER_MIN:
                retry = int(60 - (now - hist[0])) + 1
                return self._bk_json(429, {"error": f"rate limit: max {RATE_BOOKS_PER_MIN} bookings/min per principal",
                                        "retry_after": retry},
                                  extra_headers={"Retry-After": str(retry)})
            hist.append(now)
            RATE_LIMITS[principal] = hist
        lid = data.get("listing_id")
        _claim = str(data.pop("claim", "") or claim or self.headers.get("X-Claim-Code", "")).strip()
        with LOCK: listing = next((l for l in LISTINGS if l["id"] == lid), None)
        if not listing: return self._bk_json(404, {"error": f"no listing {lid}"})
        if listing.get("visibility") == "private":
            # P2: private deal — booking needs the claim (or owner auth); uniform 404
            _ok = bool(_claim) and listing.get("claim_code_hash") == hashlib.sha256(_claim.encode()).hexdigest()
            if not _ok:
                _cred = self.headers.get("X-Hub-Token", "")
                _pl, _err = None, "missing X-Hub-Token"
                if _cred:
                    for _act in ("list", "book"):
                        _pl, _err = hublib.verify_token(BOOKING_KEY, _cred, _act, single_use=False)
                        if _pl: break
                if _pl:
                    _pl, _err = _gen_check(_pl)  # B1
                _ok = bool(_pl) and _pl.get("sub") == listing.get("owner")
            if not _ok:
                return self._bk_json(404, {"error": f"no listing {lid}"})
        if listing.get("archived"):  # before any validation: the honest answer is 'archived', not field errors
            return self._bk_json(409, {"error": "listing archived - not bookable"})
        # C11 Tier-2 split (owner GO 2026-10-03): email-code satisfies the
        # Tier-1 verified-human gate above, but NEVER the Tier-2 buyer gate —
        # only midnight-zk / admin-vouch count here (fail-closed).
        acct_t2 = False
        if acct_verified and principal.startswith("acct-"):
            with LOCK:
                acct = ACCOUNTS.get(principal)
            if acct and acct.get("verified_by") in ("midnight-zk", "admin-vouch"):
                acct_t2 = True
        if listing.get("require_verified_buyer") and not acct_t2:
            # C11 (SPEC section 22): the merchant demanded Tier-2-verified buyers.
            # The client-asserted human_verified stub NEVER satisfies this gate —
            # only server-side verification (midnight-zk / admin-vouch) counts.
            return self._bk_json(403, {"error": "this listing requires a Tier-2-verified buyer",
                "note": "sign in to your account and verify via POST /accounts/verify-midnight (fail-closed Midnight personhood credential); chat: 'verify-midnight <credential_id>'",
                "verified": False})
        # SEEK (owner GO 2026-11-12): vetted seeks take APPLICATIONS, never
        # direct bookings - capacity decrements only at ACCEPT (first accept
        # wins; pending applications never block). Applications are NOT
        # ledger events: no money moves at apply time.
        if (listing.get("role") == "seek"
                and str(listing.get("application_mode") or "join") == "vetted"
                and not _accept_replay):
            return self._seek_apply(data, listing, principal, acct_t2)
        if listing.get("role") == "seek" and listing.get("require_verified_worker") and not acct_t2:
            # same Tier-2 law as require_verified_buyer: email-code NEVER counts
            return self._bk_json(403, {"error": "this seek requires a Tier-2-verified worker",
                "note": "verify via POST /accounts/verify-midnight (fail-closed Midnight personhood credential); chat: 'verify-midnight <credential_id>'",
                "verified": False})
        v = listing["vertical"]
        missing = [f for f in VERTICAL_SCHEMAS[v]["booking"]["required"] if f not in data]
        if missing: return self._bk_json(400, {"error": f"missing fields: {missing}"})
        # H17: human_verified must be a real boolean ("yes" passed truthiness)
        hv = data.get("human_verified")
        if hv is not None and not isinstance(hv, bool):
            return self._bk_json(400, {"error": "human_verified must be a boolean"})
        if not data.get("human_verified") and not acct_verified:  # H15: consistent with the first gate — vouched accounts carry server-side proof
            return self._bk_json(403, {"error": "booking requires verified-human credential",
                "note": "production: zk-proof of personhood (Midnight); interim: verified EverList account or stub flag"})
        # I1: field ownership — reject reserved fields, keep only allowlisted client fields
        reserved_seen = [k for k in data if k in RESERVED_BOOKING_FIELDS]
        if reserved_seen:
            return self._bk_json(400, {"error": f"reserved fields rejected: {reserved_seen}"})
        allowed = CLIENT_BOOKING_FIELDS[v] | {"listing_id", "human_verified", "escrow_ref", "accepted_payment_terms", "promo_code"}
        unknown = [k for k in data if k not in allowed]
        if unknown:
            return self._bk_json(400, {"error": f"unknown fields rejected: {unknown}",
                "allowed": sorted(CLIENT_BOOKING_FIELDS[v])})
        # H17: identity field is a bounded nonempty STRING (probe: numbers,
        # objects, empty and 5000-char values were accepted; schema-driven
        # so every vertical's identity field gets the same wall)
        # Phase 3 marketplace (owner GO 2026-11-07): appointment slots on
        # services. slot_minutes = LISTING-side grid (schema-validated);
        # slot_date + slot_time = BOOKING-side (which slot). Taken = any
        # active booking holding the same slot — derived from escrow state,
        # so a cancel/refund frees the slot automatically (zero hook code).
        _slot_grid = listing.get("slot_minutes")
        _b_sd = data.get("slot_date")
        _b_st = data.get("slot_time")
        if _b_sd is not None or _b_st is not None:
            if _slot_grid is None:
                return self._bk_json(400, {"error": "this listing has no slot grid; slot_date/slot_time not accepted"})
            if not isinstance(_b_sd, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", _b_sd.strip()):
                return self._bk_json(400, {"error": "slot_date must be YYYY-MM-DD"})
            _b_sd = _b_sd.strip()
            if not isinstance(_b_st, str) or not re.fullmatch(r"([01]\d|2[0-3]):[0-5]\d", _b_st.strip()):
                return self._bk_json(400, {"error": "slot_time must be HH:MM (24h, zero-padded)"})
            _b_st = _b_st.strip()
            if (int(_b_st[:2]) * 60 + int(_b_st[3:])) % int(_slot_grid) != 0:
                return self._bk_json(409, {"error": f"slot_time must align to the {int(_slot_grid)}-minute grid"})
            with LOCK:
                _taken = [b for b in BOOKINGS
                          if b.get("listing_id") == lid
                          and b.get("slot_date") == _b_sd and b.get("slot_time") == _b_st
                          and b.get("escrow") in ("HELD", "WAIVED", "DIRECT")]
            if _taken:
                return self._bk_json(409, {"error": "slot taken", "slot_date": _b_sd, "slot_time": _b_st,
                    "note": "pick another grid slot; cancellations free their slot automatically"})
            data["slot_date"] = _b_sd
            data["slot_time"] = _b_st
        elif _slot_grid is not None:
            return self._bk_json(400, {"error": "this listing books by appointment: send slot_date (YYYY-MM-DD) and slot_time (HH:MM, aligned to the " + str(int(_slot_grid)) + "-minute grid)"})
        else:
            data.pop("slot_date", None)  # spoof-strip on non-slot listings
            data.pop("slot_time", None)
        idf = VERTICAL_SCHEMAS[v]["booking"]["identity"]
        if not isinstance(data[idf], str):
            return self._bk_json(400, {"error": f"{idf} must be a string"})
        _idv = data[idf].strip()
        if not _idv:
            return self._bk_json(400, {"error": f"{idf} cannot be empty"})
        if len(_idv) > 80:
            return self._bk_json(400, {"error": f"{idf} too long (max 80 chars)"})
        data[idf] = _idv
        qty_raw = data.get("quantity", 1)
        # I3: strict integer quantity — bool/float/str rejected, no silent truncation
        if isinstance(qty_raw, bool) or not isinstance(qty_raw, int) or not (1 <= qty_raw <= 100):
            return self._bk_json(400, {"error": "quantity must be an integer in [1, 100]"})
        qty = qty_raw
        # M5: optional on-chain escrow reference — shape-validated pointer
        # (contract address + escrow id + tx hash). The chain is the source
        # of truth; the hub only stores and mirrors it (M7), never invents it.
        er = data.get("escrow_ref")
        if er is not None:
            if not isinstance(er, dict) or set(er.keys()) != {"contract", "escrow_id", "tx"}:
                return self._bk_json(400, {"error": "escrow_ref must be an object with exactly: contract, escrow_id, tx"})
            _erc = er.get("contract")
            if not isinstance(_erc, str) or not _erc.strip() or len(_erc) > 80:
                return self._bk_json(400, {"error": "escrow_ref.contract must be a nonempty string (max 80 chars)"})
            _eri = er.get("escrow_id")
            if isinstance(_eri, bool) or not isinstance(_eri, int) or _eri < 1 or _eri >= 2 ** 64:
                return self._bk_json(400, {"error": "escrow_ref.escrow_id must be a positive integer (< 2^64, contract Uint<64>)"})
            _ert = er.get("tx")
            if not isinstance(_ert, str) or not _ert.strip() or len(_ert) > 100:
                return self._bk_json(400, {"error": "escrow_ref.tx must be a nonempty string (max 100 chars)"})
            er = {"contract": _erc.strip(), "escrow_id": _eri, "tx": _ert.strip()}
        # I4: idempotency — same key + identical payload replays the same booking;
        # same key + different payload -> 409 conflict. Bound to the token principal:
        # agent B can never replay agent A's stored response (it contains secrets).
        idem_key = idem_key or self.headers.get("Idempotency-Key", "")
        canon = json.dumps({"principal": principal, **data}, sort_keys=True, separators=(",", ":"))
        if idem_key:
            with LOCK:
                if len(IDEMPOTENCY) >= IDEMPOTENCY_CAP and idem_key not in IDEMPOTENCY:
                    for k in list(IDEMPOTENCY)[:len(IDEMPOTENCY) // 10]:
                        IDEMPOTENCY.pop(k, None)  # FIFO evict oldest 10%
                prev = IDEMPOTENCY.get(idem_key)
                if prev:
                    if prev["hash"] != hashlib.sha256(canon.encode()).hexdigest():
                        return self._bk_json(409, {"error": "Idempotency-Key reused with different payload"})
                    return self._bk_json(201, {**prev["response"], "replayed": True})
        # LEVEL-1 chain gate - INTAKE (owner-approved 2026-09-20): an
        # escrow_ref must point at a REAL, currently-HELD on-chain escrow
        # before it can back a booking. Single-source read here (terminal
        # flips get dual-source); the LOCK section below re-asserts the
        # amount against the authoritative price. Network stays OUTSIDE
        # the LOCK (the settlement lesson).
        _chain_v = None
        if CHAIN_GATE and er is not None:
            _chain_v, _cerr = _chain_gate_read(er, dual=False)
            if _chain_v is None:
                _ccode, _cbody = _cerr
                return self._bk_json(_ccode, _cbody)
            if _chain_v["state_name"] != "HELD":
                return self._bk_json(409, {
                    "error": "escrow_ref points at a %s escrow - only a HELD escrow can back a new booking" % _chain_v["state_name"],
                    "note": "released/refunded escrows cannot be re-claimed; squatting a settled escrow is refused",
                    "chain": {"state": _chain_v["state_name"], "escrow_id": er["escrow_id"]}})
        with LOCK:  # I3: single reservation section — check + increment atomic under one LOCK
            # Phase 3: appointment-slot re-check INSIDE the reservation lock
            # (the pre-lock wall narrows input; this closes read-then-act)
            if data.get("slot_date") and data.get("slot_time"):
                _re = [b for b in BOOKINGS
                       if b.get("listing_id") == lid
                       and b.get("slot_date") == data["slot_date"] and b.get("slot_time") == data["slot_time"]
                       and b.get("escrow") in ("HELD", "WAIVED", "DIRECT")]
                if _re:
                    return self._bk_json(409, {"error": "slot taken",
                        "slot_date": data["slot_date"], "slot_time": data["slot_time"]})
            listing = next((l for l in LISTINGS if l["id"] == lid), None)
            if not listing: return self._bk_json(404, {"error": f"no listing {lid}"})
            if listing.get("archived"):
                return self._bk_json(409, {"error": "listing archived - not bookable"})
            _lsch = VERTICAL_SCHEMAS[listing["vertical"]]
            if _lsch.get("tracks_capacity"):
                if listing.get("registered", 0) + qty > listing["capacity"]:
                    return self._bk_json(409, {"error": "event full"})
            elif not listing.get("available", True):
                return self._bk_json(409, {"error": "listing unavailable"})
            # I3: money as integer minor units internally (convert at the edge)
            price_c = int(round(listing["price"] * 100)) * qty
            # promo redemption (owner-approved 2026-09-30): validate + recompute
            # the price EARLY so fee/escrow/chain-amount checks all validate
            # against the honest discounted total. The use is only decremented
            # at booking-commit time - a failed booking never burns a use.
            _promo_pcode = data.get("promo_code")
            _promo_pct = 0
            if _promo_pcode is not None:
                if not isinstance(_promo_pcode, str) or not re.fullmatch(r"[A-Za-z0-9]{3,24}", _promo_pcode.strip()):
                    return self._bk_json(400, {"error": "promo_code must be 3-24 letters/digits"})
                _promo_pcode = _promo_pcode.strip().upper()
                _ph = listing.get("promo_code_hash")
                if not _ph:
                    return self._bk_json(404, {"error": "this listing has no promo code"})
                if not hmac.compare_digest(hashlib.sha256(_promo_pcode.encode()).hexdigest(), str(_ph)):
                    return self._bk_json(403, {"error": "invalid promo code"})
                if int(listing.get("promo_uses_left") or 0) < 1:
                    return self._bk_json(409, {"error": "promo code exhausted - no redemptions left"})
                if price_c <= 0:
                    return self._bk_json(409, {"error": "promo needs a paid listing (this one is free)"})
                _promo_pct = int(listing.get("promo_pct") or 0)
                if not (1 <= _promo_pct <= 50):
                    return self._bk_json(409, {"error": "promo on this listing is misconfigured - the organizer needs to reset it"})
                price_c = price_c * (100 - _promo_pct) // 100
            fee_c = hub_fee_c(price_c); payout_c = price_c - fee_c
            price = price_c / 100.0; fee = fee_c / 100.0; payout = payout_c / 100.0
            # C12 (SPEC §19a): booking = acceptance of the listing's payment
            # terms. Default-terms bookings stay friction-free; custom terms
            # (instant rail / custom window / deposit) require the buyer to
            # echo the terms object exactly — API-enforced consent.
            _pt = listing.get("payment_terms") or _default_payment_terms(v)
            if price_c > 0 and _listing_is_custom_terms(listing):
                _echo = data.get("accepted_payment_terms")
                if _echo != _pt:
                    return self._bk_json(409, {"error": "this listing uses custom payment terms - confirm by echoing them exactly",
                        "payment_terms": _pt,
                        "how": "re-send the booking with accepted_payment_terms set to exactly the payment_terms object shown here"})
            # B3c-waiver: free listings need no payment rail — escrow state WAIVED
            # (verified-human gate still applies; ledger stays complete).
            # C12: instant rail = settled at booking -> DIRECT (no escrow,
            # no refund window, no confirm/cancel money step).
            escrow_state = "WAIVED" if price_c == 0 else (
                "DIRECT" if _pt.get("rail") == "instant" else "HELD")
            # M5: an on-chain escrow ref on a free booking is a contradiction —
            # free listings waive the payment rail entirely. Same for instant:
            # DIRECT means no escrow exists for this booking.
            if er is not None and escrow_state in ("WAIVED", "DIRECT"):
                return self._bk_json(409, {"error": "escrow_ref requires an escrow-rail paid booking (free listings waive the rail; instant bookings settle directly without escrow)"})
            # W2 #1: abuse-resistant sponsorship gate (owner-approved). When
            # sponsor-relay mode is on, the hub covers the organizer's chain
            # fees for this escrow lifecycle - subject to the three
            # anti-abuse rules in sponsorship.py (window limit, pool cap,
            # stake threshold). Refusals are honest 402s with the reason.
            if SPONSOR_RELAY and escrow_state == "HELD":
                import sponsorship as _sp
                _funded = sum(1 for x in BOOKINGS
                              if x.get("listing_id") == listing["id"]
                              and x.get("escrow") == "RELEASED")
                _ok, _why = _sp.check(listing.get("owner", "unknown"), _funded)
                if not _ok:
                    return self._bk_json(402, {"error": "sponsored fee relay refused",
                                            "reason": _why,
                                            "sponsorship": _sp.stats()})
            # LEVEL-1 chain gate - INTAKE ASSERTIONS (in-LOCK, no network;
            # the chain read happened outside above). Under gating an
            # escrow-rail paid booking MUST carry a chain-verified
            # escrow_ref (E3: no zero-money HELD->RELEASED farming), the
            # on-chain amount must cover the booking total exactly, and
            # the escrow's claim deadline must not have passed (D2
            # anchored to the CHAIN deadline, not just hub terms).
            if CHAIN_GATE and escrow_state == "HELD":
                if er is None:
                    return self._bk_json(400, {
                        "error": "escrow_ref required for paid escrow-rail bookings (chain gating enabled)",
                        "note": "book with escrow_ref {contract, escrow_id, tx} pointing at a live HELD escrow on the hub's configured indexer"})
                try:
                    _camt = float(str(_chain_v.get("amount")))
                except (TypeError, ValueError):
                    _camt = None
                if _camt is None or int(round(_camt * 100)) != price_c:
                    return self._bk_json(409, {
                        "error": "escrow amount does not match the booking total",
                        "chain_amount": _chain_v.get("amount"),
                        "booking_total": price,
                        "note": "the on-chain escrow must cover the booking exactly (price x quantity, minor units)"})
                try:
                    _cdl = float(str(_chain_v.get("deadline")))
                except (TypeError, ValueError):
                    _cdl = None
                if _cdl is not None and time.time() > _cdl:
                    return self._bk_json(409, {
                        "error": "escrow claim deadline already passed on-chain",
                        "deadline": _chain_v.get("deadline"),
                        "note": "a spent or expiring escrow cannot back a new booking"})
            # S1 red-team 3: duplicate (contract, escrow_id) would let two
            # bookings claim the same on-chain escrow (double-claim / squat
            # before the real buyer books) - wall lives inside the LOCK
            if er is not None:
                dup = next((x for x in BOOKINGS if x.get("escrow_ref")
                            and x["escrow_ref"]["contract"] == er["contract"]
                            and x["escrow_ref"]["escrow_id"] == er["escrow_id"]), None)
                if dup is not None:
                    return self._bk_json(409, {"error": "escrow_ref already claimed by booking %s" % dup["id"]})
            # S6-L1 + P0 human paid bookings (spec 2026-09-29): payment
            # evidence (testnet). A valid X-PAYMENT header binds the
            # buyer's wallet to this booking (self-pay review walls,
            # interlock detection). P0 widens this from instant-rail-only
            # to EVERY paid booking: humans in the webchat pay the same
            # way agents do. Absent header -> booking proceeds, rating
            # later weights at the floor.
            _payer6 = _pvalue6 = _pnonce6 = None
            _paysettle = None
            if price_c > 0 and PAY_MODE == "testnet":
                _phdr = payment if payment is not None else self.headers.get("X-PAYMENT", "")
                if _phdr:
                    _recv6 = str(listing.get("receive_addr") or PAYTO).lower()
                    _units6 = int(round(price * 1_000_000))
                    _info6, _perr6 = x402verify.verify_payment(
                        _phdr, network="base-sepolia", pay_to=_recv6,
                        max_amount_units=_units6)
                    if _perr6:
                        return self._bk_json(402, {"x402Version": 1, "error": "invalid payment",
                                                "detail": _perr6, "mode": "TESTNET"})
                    _payer6 = str(_info6["from"]).lower()
                    _pvalue6 = _info6["value"]
                    _pnonce6 = _info6["nonce"]
                    # N7 replay-across-restart + D4 crash safety: persist
                    # the used nonce and the pending marker IMMEDIATELY.
                    _persist_locked()
                    if SETTLE_MODE == "auto":
                        _fp6 = x402facilitate.payment_fingerprint(
                            {"from": _info6["from"], "to": _recv6,
                             "value": _info6["value"], "nonce": _info6["nonce"]})
                        SETTLEMENTS.mark_pending(_fp6)
                        _persist_locked()
                        _paysettle = (_fp6, _info6, _recv6)
            # H2: unguessable booking IDs (no sequential enumeration)
            bid = "bk-" + secrets.token_hex(12)
            secret = secrets.token_hex(16)
            # I1: server-owned fields ONLY; client data enters via explicit allowlist
            _idf = VERTICAL_SCHEMAS[v]["booking"]["identity"]  # H15: schema-declared
            priv_fields = {k: d for k, d in data.items() if k == _idf}
            pub = {k: (anon_ref() if k == _idf else d)
                   for k, d in data.items() if k in CLIENT_BOOKING_FIELDS[v]}
            if _promo_pcode is not None:  # commit the redemption (same LOCK as the booking append)
                listing["promo_uses_left"] = int(listing.get("promo_uses_left") or 0) - 1
            booking = {"id": bid, "listing_id": lid, "vertical": v,
                "escrow": escrow_state, "amount": price, "hub_fee": fee,
                "owner_payout": payout, "quantity": qty, "created": time.time(),
                "booked_by": principal,
                "payment_terms": _pt,  # C12: server-copied snapshot of the terms IN FORCE at booking time; later listing edits never rewrite a done deal
                **pub}
            if _promo_pct:
                booking["promo_applied"] = {"pct": _promo_pct}  # server-derived; the raw code is never stored
            # M14: bookings carry verification provenance SERVER-SIDE only
            # (verified_by is reserved - clients can never claim it)
            if principal.startswith("acct-"):
                _acct = ACCOUNTS.get(principal)
                if _acct and _acct.get("human_verified"):
                    booking["verified_by"] = _acct.get("verified_by") or "midnight-zk"
            if _payer6:
                # S6: server-verified payment evidence (never client-claimed)
                booking["payment_payer"] = _payer6
                booking["payment_value"] = _pvalue6
                booking["payment_nonce"] = _pnonce6
            if er is not None:
                booking["escrow_ref"] = er  # M5: chain pointer, verbatim after validation
            # real identity stored ONLY here, retrievable only with the secret
            SECRETS[bid] = {"secret": secret, "private": priv_fields}
            BOOKINGS.append(booking)
            LEDGER.append({"ts": time.time(), "booking": bid, "amount": price,
                "hub_fee": fee, "owner_payout": payout, "escrow": escrow_state})
            if VERTICAL_SCHEMAS[v].get("tracks_capacity"):
                listing["registered"] = listing.get("registered", 0) + qty
            # T5: QR ticket mint for capacity verticals (door check-in).
            # The token is a BEARER door-capability (not a name): returned
            # ONCE in the 201, persisted hub-side by design, re-delivered
            # ONLY via buyer-authenticated surfaces.
            _tk_raw = None
            if VERTICAL_SCHEMAS[v].get("tracks_capacity"):
                _tk = ticketing.mint(bid, listing.get("title"),
                                     str(listing.get("date") or ""), qty)
                TICKETS[_tk["token_hash"]] = _tk
                _tk_raw = _tk["token"]
            if escrow_state == "DIRECT":
                _earnings_record_locked(booking)  # W3.4: instant rail settles at booking; WAIVED (payout 0) no-ops inside
            _persist_locked()
        _notify_booking("created", booking, listing)
        # P0 human paid bookings (spec 2026-09-29): settle the verified
        # payment OUTSIDE the global LOCK (the settlement lesson — one
        # facilitator hop must never serialize the hub). The x402 nonce
        # is already marked used + persisted and SETTLEMENTS.settle() is
        # fingerprint-idempotent, so this is safe unlocked. Booking ships
        # immediately; settlement lands in the ledger either way.
        if _paysettle is not None:
            _fp6, _info6, _recv6 = _paysettle
            _srec6 = SETTLEMENTS.settle(
                _fp6, _info6["payload"],
                {"scheme": "exact", "network": "base-sepolia",
                 "asset": BASE_SEPOLIA_USDC, "payTo": _recv6,
                 "maxAmountRequired": str(_info6["value"])},
                FACIL)
            with LOCK:
                if _srec6["status"] == "settled":
                    LEDGER.append({"kind": "x402_settlement", "ts": time.time(),
                                   "detail": {"fingerprint": _fp6, "tx": _srec6["tx"],
                                               "value": _info6["value"], "payer": _info6["from"],
                                               "network": _srec6.get("network", "base-sepolia"),
                                               "booking": bid}})
                _persist_locked()
        # C12: per-rail flow lines (plain list building — no starred unpacks)
        if escrow_state == "DIRECT":
            _flow = ["instant rail — payment settled at booking (DIRECT, no refund window)"]
        elif escrow_state == "WAIVED":
            _flow = ["free listing — payment WAIVED (no escrow rail)",
                     "confirm: owner POST /book/{id}/confirm with X-Hub-Token (mint via POST /admin/tokens, act=confirm)",
                     f"cancel: buyer POST /book/{bid}/cancel with X-Hub-Token: cancel_token before fulfillment -> full refund"]
        else:
            _flow = ["escrow HELD (funds locked)",
                     "confirm: owner POST /book/{id}/confirm with X-Hub-Token (mint via POST /admin/tokens, act=confirm)",
                     f"cancel: buyer POST /book/{bid}/cancel with X-Hub-Token: cancel_token before fulfillment -> full refund"]
        resp = {**booking,
            "booking_secret": secret, "secret_note": "shown ONCE; required to view private details",
            "cancel_token": hublib.mint_token(BOOKING_KEY, "cancel", bid,
                # S7: TTL must outlive the advertised refund window — a buyer
                # on a 30-day window loses their only self-refund credential
                # at day 7 with a fixed 7d token.
                ttl=max(7 * 24 * 3600,
                        int((_pt or {}).get("refund_window_hours", 0) or 0) * 3600 + 48 * 3600)),
            "flow": _flow}
        if _tk_raw:
            resp["ticket_token_once"] = _tk_raw  # 201-only door link
        if idem_key:
            with LOCK:
                IDEMPOTENCY[idem_key] = {"hash": hashlib.sha256(canon.encode()).hexdigest(),
                                         "response": resp}
                _persist_locked()
        return self._bk_json(201, resp)

    def do_GET(self):
        self._t0 = time.time()  # H12: latency start
        u = urlparse(self.path)
        if u.path == "/accounts/notify/unsubscribe":
            # Signed, account-scoped unsubscribe landing (email footer link).
            # Honest + idempotent: valid signature flips notify off (stays off);
            # anything else gets the branded 'say notify off' page. Never 500s.
            try:
                import emailkit as _ek
                q = parse_qs(u.query)
                princ = q.get("u", [""])[0]
                tok = q.get("t", [""])[0]
                if (princ.startswith("acct-") and tok
                        and _unsub_valid(princ, tok)
                        and princ in ACCOUNTS):
                    with LOCK:
                        # S1 split: the EMAIL FOOTER link unsubscribes MARKETING
                        # (weekly digest) only. Transactional booking
                        # notifications stay on notify_email (chat-toggled),
                        # security codes are never gated.
                        ACCOUNTS[princ]["marketing_email"] = False
                        _persist_locked()
                    return _html_resp(self, 200, _ek.unsub_page(ok=True))
                return _html_resp(self, 200, _ek.unsub_page(ok=False))
            except Exception:
                return _html_resp(self, 200, "<html><body><p>Unsubscribe link invalid. "
                    "Say notify off in the EverList chat.</p></body></html>")
        # TRACK E: checkout session status + hosted checkout assets
        _mckg = re.match(r"^/checkout/sessions/(chk-[0-9a-f]{32})$", u.path)
        if _mckg:
            return self._checkout_session(_mckg.group(1), "", {})
        if u.path == "/checkout":
            return self._serve_checkout_asset("checkout.html")
        if u.path == "/checkout.js":
            return self._serve_checkout_asset("checkout.js")
        if u.path == "/checkout.css":
            return self._serve_checkout_asset("checkout.css")
        if u.path == "/book.js":
            return self._serve_checkout_asset("book.js")
        if u.path == "/polish.js":
            # Prod drift-proofing (2026-11-07): the LIVE Caddyfile matcher
            # lacks /polish.js (template has it; live predates it), so this
            # asset fell to the hub catch-all and 404ed. Serving it here —
            # like book.js — makes the quiet-polish layer Caddy-independent;
            # new static assets must not depend on matcher drift ever again.
            return self._serve_checkout_asset("polish.js")
        if u.path == "/auth/challenge":
            """HARDENING-v2: challenge issuance for cost curves.
            kind=signup -> sha256 PoW challenge (must be solved to signup)
            kind=login&pubkey=<hex> -> single-use ed25519 login challenge"""
            q = parse_qs(u.query)
            kind = q.get("kind", [""])[0]
            if kind in ("signup", "recover"):
                with LOCK:
                    # RTF1: same per-source backstop discipline as every other
                    # auth kind — challenge minting is no longer free
                    if not _auth_allow("challenge", _source_of(self)):
                        return self._json(429, {"error": "challenge rate limit reached for your source, retry later"})
                    return self._json(200, _pow_issue(kind))
            if kind == "login":
                pubkey_hex = q.get("pubkey", [""])[0].strip().lower()
                if len(pubkey_hex) != 64:
                    return self._json(400, {"error": "kind=login needs pubkey=<64 hex>"})
                with LOCK:
                    aid = next((a for a, v in ACCOUNTS.items() if v.get("pubkey") == pubkey_hex), None)
                    if not aid:
                        return self._json(404, {"error": "unknown pubkey"})
                    ch = secrets.token_hex(16)
                    LOGIN_CHALLENGES[aid] = {"ch": ch, "exp": time.time() + 120}
                    return self._json(200, {"algo": "ed25519", "challenge": ch,
                        "ttl": 120, "msg": "sign b'everlist-login:' + challenge with your seed's private key; POST sig (128 hex) to /accounts/login with pubkey + agent"})
            return self._json(400, {"error": "kind must be signup or login"})
        if u.path == "/.well-known/x402.json":
            """DL-1 (mining 2026-10-31, x402-bazaar convention): machine-readable
            x402 payment discovery at the standard agents-probe location.
            Honest by construction: built from the SAME module constants that
            power the live /premium/events 402, so this file cannot drift from
            actual payment terms. Network-specific live terms (incl. the
            Cardano rail when enabled) stay authoritative at the 402 itself."""
            _x402 = {
                "x402Version": 1,
                "mode": PAY_MODE.upper(),
                "accepts": [{
                    "scheme": "exact", "network": "base-sepolia",
                    "asset": BASE_SEPOLIA_USDC,
                    "maxAmountRequired": str(int(round(PREMIUM_PRICE_USD * 1_000_000))),
                    "payTo": PAYTO,
                    "resource": "/premium/events",
                    "description": "Premium events feed (agent-hub-v2)",
                    "maxTimeoutSeconds": 300,
                    "extra": {"name": "USD Coin", "version": "2"}}],
                "discover": {
                    "live_terms_402": "/premium/events (GET without X-PAYMENT returns per-network accepts)",
                    "openapi": "/openapi.json", "manifest": "/.well-known/agent-hub.json"},
                "note": ("TESTNET mode: real EIP-3009 verification."
                         if PAY_MODE == "testnet" else
                         "SIMULATED payment verification - no real settlement.")}
            if CARDANO_ON:
                _x402["cardano_rail"] = {"network": CARDANO_NET, "asset": CARDANO_ASSET,
                                         "live_terms": "GET /premium/events without X-PAYMENT"}
            return self._json(200, _x402)
        if u.path == "/.well-known/agent-hub.json":
            # standard discovery location - agents probe any domain for this
            return self._json(200, {
                "protocol": "agent-hub/0.2", "open_source": "MIT",
                "license_model": "open-core: hub/SDK/registry open; EverList network membership curated (see /network)",
                "api_contract": "/openapi.json",
                "hub": HUB_NAME,
                "description": HUB_DESCRIPTION,
                "auth": {
            "kind": "crypto-accounts",
            "contract": "SPEC 12a: Ed25519 keypair accounts, challenge-response login, PoW-gated signup",
            "challenge": "/auth/challenge",
            "signup": "/accounts/signup"
        },
        "fairness": {"fee_policy": {"actual_fee_pct": FEE_PCT,
                                "note": "fully declared by hub; no protocol cap. Agents verify declared vs ledger and choose"},
                              "ledger": "/ledger", "escrow": True,
                              "open_registry": "/registry",
                              "mirror": {"sync": "/admin/sync-escrow",
                                         "rail": "midnight-shielded-escrow",
                                         "policy": "chain is source of truth; sync never overwrites downward (C7)"}},
                "identity": {"booking_requires": "interim: open bootstrap (no credential enforced yet); flagship target: verified-human credential (ZK: real human, private by default)",
                              "adapters": [
                                  {"scheme": "midnight-zk-personhood", "status": "flagship (ZK: real human, identity stays private)"},
                                  {"scheme": "email-or-phone-attestation", "status": "interim stub until Midnight contract is live"}],
                              "disputes": "selective disclosure to auditors via ZK (Midnight)"},
                "payments": {
                    "mode": PAY_MODE,  # I4: honest self-declaration (simulated|testnet)
                    "protocol": "x402",
                    "pricing": {"unit": "merchant fiat (EUR/USD) or USDC",
                                 "rule": "prices are NEVER denominated in volatile assets"},
                    "accepted_assets": [
                        {"asset": "USDC (EVM)", "role": "native x402 'exact' scheme - verified per C1 research", "rail": "x402"},
                        {"asset": "ETH", "role": "x402 EVM chains - HYPOTHESIS until C3 verification", "rail": "x402"},
                        {"asset": "ADA / Cardano-native stablecoins (USDM/USDCx)", "role": "x402 'exact' on Cardano via the merged Cardano facilitator (C3c, EXPERIMENTAL-preprod, stablecoin-first; ADA = per-listing opt-in only)", "rail": "x402"},
                        {"asset": "FET", "role": "custom adapter; for ASI-native agents; merchants never receive FET (round-5)", "rail": "custom"}],
                    "deferred": [
                        {"asset": "BTC", "why": "needs processor/Lightning adapter - later"},
                        {"asset": "NIGHT/DUST", "why": "Midnight mainnet ~6mo old, no merchant off-ramp yet - revisit"}],
                    "conversion": "at payment time via DEX router/processor; hub never custodies funds",
                    "rails": {
                        "default": "x402 transparent (USDC/ETH/ADA/FET) - cheap, standard, merchant-friendly",
                        "privacy": "midnight shielded rail (Zswap): hides payer, amount, and asset; private escrow state via Compact; per-transaction selective disclosure for disputes/compliance",
                        "why_two": "public rails leak purchase history; sensitive bookings (medical, legal, personal) need shielded payment by default"},
                    "principle": "buyers pay in what they hold; merchants receive stable value; privacy is a choice"},
                "distribution": {"channels": ["agentverse marketplace (hub runs as uAgent)",
                                 "almanac registration (agent identity/address)",
                                 "agent framework skills (A0, MCP, uAgents wrapper)"],
                                  "role_of_fet": "ecosystem access + agent discovery; NOT a merchant settlement currency"},
                "fet_utility": {
                    "infrastructure": ["hub runs as uAgent", "almanac registration (agent identity, small FET)", "agentverse marketplace listing"],
                    "earns_fet": "premium hub services sold to ASI-native agents (paid in FET -> converted to USDC at settlement)",
                    "stakes_fet": "optional verified-hub trust bond in registry (slashed on proven fraud)",
                    "never": "merchant settlement currency"},
                "verification": {"why": "DL-adoption 2026-10-31: do not take our word for it - check the chain",
                                  "escrow_proof": {"endpoint": "/escrow/{id}/proof?contract=<address>",
                                                    "trust_model": "verify-without-trust: escrow re-read from configured indexer(s), dual-source when configured, fail-closed on disagreement"},
                                  "wallet_less_verify_page": "/verify?contract=<address>&escrow=<id> (no wallet, no account)",
                                  "payment_discovery": "/.well-known/x402.json",
                                  "booking_status_field": "GET /bookings/{id} returns escrow_guide (per-state next steps + verification pointers)",
                                  "attack_us": "/break-it (try-to-break-it sandbox; include the word BREAKIT in a chat report - routes to a human)",
                                  "nullifier_law": "domain-tagged nullifiers (contract‖action‖phase‖era) - experiments/midnight-escrow/NULLIFIER_DOMAINS.md"},
                "privacy": {"pseudonymous_ids": True,
                              "booking_details": "visible only with booking secret",
                              "note": "public ledger shows amounts + pseudonyms only"},
                "capabilities": {"search": "/search?q=", "verticals": "/verticals",
                                  "listings": "/listings", "book": "POST /book",
                                  "bookings": "/bookings", "orders": "/orders (merchant view, list token)",
                                  "ledger": "/ledger",
                                  "mcp": {"endpoint": "/mcp", "protocol": "MCP (JSON-RPC 2.0 over HTTP POST)",
                                          "tools": ["everlist_contract", "everlist_verticals", "everlist_search",
                                                    "everlist_listing", "everlist_book", "everlist_booking"],
                                          "auth": "same X-Hub-Token as REST (header-only; a token in tool arguments is ignored - MCP-ARGS law)"},
                                  "add_listing": "POST /listings",
                                  "premium": {"endpoint": "/premium/events", "protocol": "x402",
                                               "status": ("TESTNET - real EIP-3009 signature verification (eth-account), no on-chain settlement yet (C3b)" if PAY_MODE == "testnet" else "SIMULATED - stub verification, no real settlement (C3a = real EIP-3009 on base-sepolia)")}},
                "schemas": VERTICAL_SCHEMAS})
        if u.path == "/premium/events":
            """C2: x402-protected richer feed. SIMULATED mode: stub verification.
            Wire format per payments_x402.md (C1 research)."""
            pay_hdr = self.headers.get("X-PAYMENT", "")
            # C3c: route by network — cardano:* goes to the Cardano rail
            _is_cardano = False
            try:
                _dec = json.loads(base64.b64decode(pay_hdr).decode())
                _is_cardano = str(_dec.get("network", "")).startswith("cardano:")
            except Exception:
                pass
            if _is_cardano:
                return self._cardano_premium(pay_hdr, _dec)
            if not pay_hdr:
                # FED4 (run #5): advertise the ACTUAL serving origin, not a
                # hardcoded localhost:8802 — agents paid the wrong host otherwise.
                _xhost = self.headers.get("Host") or ("localhost:%d" % PORT)
                _xscheme = "https" if self.headers.get("X-Forwarded-Proto", "").lower() == "https" else "http"
                terms = {"x402Version": 1, "error": "Payment Required",
                         "mode": PAY_MODE.upper(),
                         "accepts": [{
                             "scheme": "exact", "network": "base-sepolia",
                             "asset": BASE_SEPOLIA_USDC,
                             "maxAmountRequired": str(int(round(PREMIUM_PRICE_USD * 1_000_000))),
                             "payTo": PAYTO,
                             "resource": "%s://%s/premium/events" % (_xscheme, _xhost),
                             "description": "Premium events feed (agent-hub-v2)",
                             "maxTimeoutSeconds": 300,
                             "extra": {"name": "USD Coin", "version": "2"}}],
                         "note": ("TESTNET mode: real EIP-3009 signature verification; on-chain settlement via facilitator is C3b."
                                  if PAY_MODE == "testnet" else
                                  "SIMULATED payment verification - no real settlement. Production mode verifies EIP-3009 signatures (C3a).")}
                if CARDANO_ON:
                    # C3c: second instant rail — Cardano stablecoin (default tUSDM
                    # preprod; ADA=lovelace only as explicit opt-in). Payload shape
                    # is the x402 v2 Cardano body {transaction, nonce} carried in
                    # our v1 X-PAYMENT envelope (transport deviation, documented).
                    terms["accepts"].append({
                        "scheme": "exact", "network": CARDANO_NET,
                        "asset": CARDANO_ASSET,
                        "maxAmountRequired": str(CARDANO_PRICE),
                        "payTo": CARDANO_PAYTO,
                        "resource": "%s://%s/premium/events" % (_xscheme, _xhost),
                        "description": "Premium events feed (agent-hub-v2, Cardano rail)",
                        "maxTimeoutSeconds": 600,
                        "extra": {"label": CARDANO_LABEL,
                                  "assetTransferMethod": "default",
                                  "confirmationPolicy": {"l1Confirmations": 1},
                                  "note": "stablecoin-first rail; payload = {transaction, nonce} (x402 v2 Cardano shape) inside this X-PAYMENT envelope"}})
                return self._json(402, terms)
            if PAY_MODE == "testnet":
                info, err = x402verify.verify_payment(
                    pay_hdr, network="base-sepolia", pay_to=PAYTO,
                    max_amount_units=int(round(PREMIUM_PRICE_USD * 1_000_000)))
                if err:
                    return self._json(402, {"x402Version": 1, "error": "invalid payment",
                                            "detail": err, "mode": "TESTNET"})
                with LOCK:
                    _persist_locked()  # C3a: persist used x402 nonce IMMEDIATELY (N7 replay-across-restart)
                    fp = x402facilitate.payment_fingerprint({"from": info["from"],
                                                              "to": PAYTO, "value": info["value"],
                                                              "nonce": info["nonce"]})
                    srec = None
                    if SETTLE_MODE == "auto":
                        # D4-fix: durable pending marker BEFORE leaving for the facilitator.
                        # x402 nonce is already persisted; without this marker a crash
                        # mid-call leaves the payment replay-blocked with no hub evidence.
                        SETTLEMENTS.mark_pending(fp)
                        _persist_locked()
                if SETTLE_MODE == "auto":
                    # MED-fix (chaos run 2026-09-20): the facilitator HTTP round-trip
                    # (15s timeout) used to run under the global LOCK — one paid request
                    # serialized the whole hub for the full chain hop (measured: 7s
                    # /search stall with an 8s facilitator). Safe to run unlocked because:
                    # - the x402 nonce is marked used + persisted BEFORE this point, so
                    #   the payment can never be replayed through /premium/events
                    # - SETTLEMENTS.settle() is fingerprint-idempotent; concurrent or
                    #   duplicate submissions return the recorded result, never re-call
                    # - this block touches no hub shared state (registry has own lock)
                    # C3b: idempotent settlement; duplicate submissions return the
                    # recorded result without re-calling the facilitator.
                    # paymentPayload = the REAL decoded x402 payload (signed auth)
                    srec = SETTLEMENTS.settle(fp, info["payload"],
                                               {"scheme": "exact", "network": "base-sepolia",
                                                "asset": BASE_SEPOLIA_USDC,
                                                "payTo": PAYTO,
                                                "maxAmountRequired": str(info["value"])},
                                               FACIL)
                    with LOCK:
                        if srec["status"] == "settled":
                            LEDGER.append({"kind": "x402_settlement", "ts": time.time(),
                                            "detail": {"fingerprint": fp, "tx": srec["tx"],
                                                        "value": info["value"], "payer": info["from"],
                                                        "network": srec.get("network", "base-sepolia")}})
                        _persist_locked()  # settlement record + ledger event persisted together
                with LOCK:
                    res = [l for l in LISTINGS if l["vertical"] == "events" and l.get("visibility") != "private"]
                    rich = [{**_pub_listing(l), "premium_meta": {"owner_public": l.get("owner", ""),
                             "fill_ratio": round(l.get("registered", 0) / max(1, l.get("capacity", 1)), 3),
                             "payment": {"mode": "TESTNET", "verified": True,
                                          "settlement": (srec["status"] if srec else "pending (HUB_SETTLE_MODE=off)"),
                                          "fingerprint": x402verify.payment_fingerprint(info),
                                          "payer": info["from"], "value": info["value"]}}} for l in res]
                if srec is not None and srec["status"] == "settled":
                    settle_info = {"status": "SETTLED", "tx": srec["tx"],
                                    "network": srec.get("network", "base-sepolia")}
                elif srec is not None and srec["status"] == "unknown":
                    settle_info = {"status": "UNKNOWN",
                                    "note": "facilitator timeout/error - outcome unproven; check facilitator before retry"}
                elif srec is not None:
                    settle_info = {"status": "FAILED", "error": srec.get("error", "facilitator rejected")}
                else:
                    settle_info = {"status": "NOT_ATTEMPTED",
                                    "note": "HUB_SETTLE_MODE=off - verified only; set auto to settle via facilitator"}
                return self._json(200, {"mode": "TESTNET",
                    "payment": {"scheme": "exact", "network": "base-sepolia", "asset": "USDC",
                                 "value": info["value"], "verified": True,
                                 "settlement": settle_info},
                    "count": len(rich), "events": rich})
            # simulated mode: decode + validate authorization (stub signature)
            try:
                dec = json.loads(base64.b64decode(pay_hdr).decode())
                auth = dec["payload"]["authorization"]
                assert dec.get("x402Version") == 1 and dec.get("scheme") == "exact"
                assert auth["to"] == PAYTO
                assert int(auth["value"]) >= int(round(PREMIUM_PRICE_USD * 1_000_000))
                now = int(time.time())
                assert int(auth["validAfter"]) <= now < int(auth["validBefore"])
            except Exception as ex:
                return self._json(402, {"x402Version": 1, "error": "invalid payment",
                                        "detail": str(ex)[:120], "mode": "SIMULATED"})
            with LOCK:
                res = [l for l in LISTINGS if l["vertical"] == "events" and l.get("visibility") != "private"]
                # 'richer': only premium gets per-listing owner contact + inventory ratio
                rich = [{**_pub_listing(l), "premium_meta": {"owner_public": l.get("owner", ""),
                         "fill_ratio": round(l.get("registered", 0) / max(1, l.get("capacity", 1)), 3),
                         "payment": "SIMULATED x402 exact/base-sepolia USDC"}} for l in res]
            return self._json(200, {"mode": "SIMULATED",
                "payment": {"scheme": "exact", "network": "base-sepolia", "asset": "USDC",
                             "value": auth["value"], "settlement": "stubbed (C3a = real EIP-3009 verification)"},
                "count": len(rich), "events": rich})
        if u.path == "/manifest.json":
            return self._json(200, {"hub": HUB_NAME, "version": "0.2",  # run7 D2: matches SPEC §11 + canonical manifest (was 0.3)
                "type": "universal-commerce",
                "canonical_manifest": "/.well-known/agent-hub.json"})
        if u.path.startswith("/img/") and u.path.count("/") == 2:
            return self._serve_listing_image(u.path[len("/img/"):])
        if u.path == "/openapi.json":
            # H13: machine-readable API contract — agents read it natively
            return self._json(200, _openapi_spec())
        if u.path == "/verticals":
            return self._json(200, {"verticals": VERTICAL_SCHEMAS})
        if u.path.startswith("/payterms/"):
            # P0 human paid bookings (spec 2026-09-29): the SINGLE SOURCE OF
            # TRUTH for what a browser wallet must pay for this listing. The
            # webchat relays these terms to the Pay button — payment numbers
            # are never invented client-side; they are the same terms the
            # /book X-PAYMENT verification checks against.
            _plid = u.path.split("/", 2)[2] if u.path.count("/") >= 2 else ""
            _pl = None
            with LOCK:
                _pl = next((x for x in LISTINGS if x["id"] == _plid), None)
                if _pl is not None:
                    _plp = float(_pl["price"])
                    _plr = str(_pl.get("receive_addr") or PAYTO).lower()
                    _plt = dict(_pl.get("payment_terms") or {})
                    _plv = _pl["vertical"]
            if _pl is None:
                return self._json(404, {"error": f"no listing {_plid}"})
            if _plp <= 0:
                return self._json(409, {"error": "free listing — no payment needed"})
            return self._json(200, {
                "listing_id": _plid, "vertical": _plv,
                "identity_field": VERTICAL_SCHEMAS[_plv]["booking"]["identity"],
                "scheme": "EIP-3009", "network": "base-sepolia",
                "asset": BASE_SEPOLIA_USDC, "pay_to": _plr,
                "max_amount_units": str(int(round(_plp * 1_000_000))),
                "mode": PAY_MODE.upper(), "payment_terms": _plt})
        if u.path == "/merchants" or u.path.startswith("/merchants/"):
            # CATALOGS P1 public reads: profile + OWN uncapped listing set +
            # catalog summary (items never leak into /listings).
            if u.path == "/merchants":
                # hardening: bare GET = public collection (honest 200, never
                # a naked 404; also the sitemap/llms discovery source).
                with LOCK:
                    _coll = [_pub_merchant(m) for m in MERCHANTS.values()]
                return self._json(200, {"count": len(_coll), "merchants": _coll})
            _mslug = u.path[len("/merchants"):].lstrip("/")
            if not _mslug or len(_mslug) > 40 or not _MERCH_SLUG_RE.fullmatch(_mslug):
                return self._json(404, {"error": "no merchant"})
            with LOCK:
                _m = MERCHANTS.get(_mslug)
                if not _m:
                    return self._json(404, {"error": "no merchant %s" % _mslug})
                _own_ls = [_pub_listing(l) for l in LISTINGS
                           if l.get("merchant") == _mslug and not l.get("archived")
                           and l.get("visibility") != "private"]
                _cat = next((c for c in CATALOGS.values() if c.get("merchant") == _mslug), None)
                _cat_pub = None
                if _cat:
                    _items = [{"path": " / ".join(pth), "title": str(it.get("title", ""))[:80],
                               "price": it.get("price")} for pth, it in _cat_walk(_cat["tree"])]
                    _cat_pub = {"id": _cat["id"], "version": _cat["version"],
                                "content_hash": _cat["content_hash"], "items": _items[:200]}
            return self._json(200, {"merchant": _pub_merchant(_m),
                "listings": _own_ls, "catalog": _cat_pub})
        if u.path == "/catalogs" or u.path.startswith("/catalogs/"):
            # CATALOGS P2 public read: version + content_hash (+ tree unless
            # fields=summary); since_hash match -> honest 304.
            if u.path == "/catalogs":
                # hardening: bare GET = public collection; prefix tightened
                # so /catalogsXYZ can no longer match this branch.
                with LOCK:
                    _coll = [{"id": c["id"], "merchant": c["merchant"],
                              "version": c["version"], "content_hash": c["content_hash"]}
                             for c in CATALOGS.values()]
                return self._json(200, {"count": len(_coll), "catalogs": _coll})
            _crid = u.path[len("/catalogs"):].lstrip("/")
            if not _crid or "/" in _crid or len(_crid) > 40:
                return self._json(404, {"error": "no catalog"})
            with LOCK:
                _c = CATALOGS.get(_crid)
            if not _c:
                return self._json(404, {"error": "no catalog %s" % _crid})
            _wh = parse_qs(u.query).get("since_hash", [""])[0].strip()
            if _wh and _wh == _c["content_hash"]:
                return self._json(304, {})
            body = {"id": _c["id"], "merchant": _c["merchant"], "version": _c["version"],
                    "content_hash": _c["content_hash"]}
            if parse_qs(u.query).get("fields", [""])[0] != "summary":
                body["tree"] = _c["tree"]
            return self._json(200, body)
        if u.path == "/listings":
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests — slow down (retry shortly)"})
            v = parse_qs(u.query).get("vertical", [""])[0]
            fm = parse_qs(u.query).get("merchant", [""])[0].strip().lower()
            show_arch = parse_qs(u.query).get("archived", [""])[0] in ("1", "true")
            if show_arch:
                # HARDENING: archived listings are OWNER-ONLY. Audit finding:
                # previously readable by anyone (leaked hidden listings).
                cred = self.headers.get("X-Hub-Token", "")
                payload, err = None, "missing X-Hub-Token"
                if cred:
                    for act in ("list", "book"):
                        payload, err = hublib.verify_token(BOOKING_KEY, cred, act, single_use=False)
                        if payload: break
                if payload:
                    payload, err = _gen_check(payload)  # B1
                if not payload:
                    return self._json(401, {"error": "archived listings are owner-only",
                        "hint": "send X-Hub-Token (login token or /access list token)"})
                me = payload["sub"]
                with LOCK:
                    res = [_pub_listing(l) for l in LISTINGS
                           if l.get("archived") and l.get("owner") == me
                           and (not v or l["vertical"] == v)]
                return self._json(200, {"count": len(res), "listings": res})
            with LOCK:
                _me = None  # P2: the owner sees their own private deals here
                _cred = self.headers.get("X-Hub-Token", "")
                if _cred:
                    _pl, _err = None, "missing X-Hub-Token"
                    for _act in ("list", "book"):
                        _pl, _err = hublib.verify_token(BOOKING_KEY, _cred, _act, single_use=False)
                        if _pl: break
                    if _pl:
                        _pl, _err = _gen_check(_pl)  # B1
                    if _pl:
                        _me = _pl.get("sub")
                res = [_pub_listing(l) for l in LISTINGS
                       if not l.get("archived")
                       and (l.get("visibility") != "private" or (l.get("owner") == _me and _me))
                       and (not v or l["vertical"] == v)
                       and (not fm or l.get("merchant") == fm)]
                # P1 feed quota (spec §6): a merchant's catalog must not flood
                # the feed. Explicit merchant= browses (the merchant page's own
                # set) are uncapped; the owner always sees their own full set.
                _quota_note = None
                if not fm and _MERCHANT_FEED_QUOTA > 0:
                    _cap = _MERCHANT_FEED_QUOTA
                    _seen, _kept, _qap = {}, [], set()
                    for l in res:
                        _ms = l.get("merchant")
                        if not _ms or (_me and l.get("owner") == _me):
                            _kept.append(l); continue
                        _seen.setdefault(_ms, 0)
                        if _seen[_ms] < _cap:
                            _seen[_ms] += 1; _kept.append(l)
                        else:
                            _qap.add(_ms)
                    if _qap:
                        res = _kept
                        _quota_note = {"max_per_merchant": _cap, "applied_for": sorted(_qap)}
            total = len(res)
            res, off, lim = _paginate(res, parse_qs(u.query))
            _body = {"count": total, "offset": off, "limit": lim,
                     "returned": len(res), "listings": res}
            if _quota_note:
                _body["merchant_quota"] = _quota_note
            return self._json(200, _body)
        if u.path.startswith("/listings/"):
            # H9: single-listing fetch, full rich record. Unknown -> 404;
            # archived -> 410 Gone (exists, not publicly available).
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests — slow down (retry shortly)"})
            lid = u.path[len("/listings/"):]
            with LOCK:
                l = next((x for x in LISTINGS if x["id"] == lid), None)
            if not l:
                return self._json(404, {"error": f"no listing {lid}"})
            if l.get("visibility") == "private":
                # P2: private deal — claim (?claim= or X-Claim-Code) or owner token.
                # Everyone else gets the same answer as unknown: no existence oracle.
                _claim = (parse_qs(u.query).get("claim", [""])[0]
                          or self.headers.get("X-Claim-Code", "")).strip()
                _ok = bool(_claim) and l.get("claim_code_hash") == hashlib.sha256(_claim.encode()).hexdigest()
                if not _ok:
                    _cred = self.headers.get("X-Hub-Token", "")
                    _pl, _err = None, "missing X-Hub-Token"
                    if _cred:
                        for _act in ("list", "book"):
                            _pl, _err = hublib.verify_token(BOOKING_KEY, _cred, _act, single_use=False)
                            if _pl: break
                    if _pl:
                        _pl, _err = _gen_check(_pl)  # B1
                    _ok = bool(_pl) and _pl.get("sub") == l.get("owner")
                if not _ok:
                    return self._json(404, {"error": f"no listing {lid}"})
            if l.get("archived"):
                return self._json(410, {"error": f"listing {lid} archived — its owner can unarchive it"})
            return self._json(200, _pub_listing(l))
        if u.path == "/search":
            """Faceted search: q (FTS5 full-text) + structured filters.
            All filters AND-combined; agents can discover vocab via /verticals."""
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests — slow down (retry shortly)"})
            q = parse_qs(u.query)
            term = q.get("q", [""])[0].strip().lower()
            if len(term) > READ_Q_MAX:
                return self._json(400, {"error": f"q too long (max {READ_Q_MAX} chars)"})
            fvert = q.get("vertical", [""])[0]
            fcat = q.get("category", [""])[0].strip().lower()
            ftag = q.get("tag", [""])[0].strip().lower()
            floc = q.get("location", [""])[0].strip().lower()
            floc = _LOC_ALIASES.get(floc, floc)  # P1: query side of the alias pair
            fmax = q.get("max_price", [""])[0]
            fmin = q.get("min_price", [""])[0]
            ffrom = q.get("from", [""])[0].strip()
            fto = q.get("to", [""])[0].strip()
            fsort = q.get("sort", [""])[0].strip().lower()
            ftags_raw = q.get("tags", [""])[0].strip().lower()
            ftags = [t.strip() for t in ftags_raw.split(",") if t.strip()] if ftags_raw else []
            frole = q.get("role", [""])[0].strip().lower()
            if frole and frole not in ("offer", "seek"):
                return self._json(400, {"error": "role must be offer or seek"})
            if fsort and fsort not in ("date", "price", "newest", "distance"):
                return self._json(400, {"error": "sort must be one of: date, price, newest, distance"})
            DATE_SHAPE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
            if ffrom and not DATE_SHAPE.match(ffrom):
                return self._json(400, {"error": "from must be YYYY-MM-DD"})
            if fto and not DATE_SHAPE.match(fto):
                return self._json(400, {"error": "to must be YYYY-MM-DD"})
            try:
                fmaxv = float(fmax) if fmax else None
            except ValueError:
                return self._json(400, {"error": "max_price must be a number"})
            try:
                fminv = float(fmin) if fmin else None
            except ValueError:
                return self._json(400, {"error": "min_price must be a number"})
            # Phase 2 geo: near=lat,lon + radius_km=, honest 400s, no silent
            # fallback: malformed coords, a radius without near=, or
            # sort=distance without near= are client errors.
            fnear_raw = q.get("near", [""])[0].strip()
            fnear = _parse_latlon(fnear_raw) if fnear_raw else None
            if fnear_raw and fnear is None:
                return self._json(400, {"error": "near must be lat,lon degrees (lat -90..90, lon -180..180)"})
            frad_raw = q.get("radius_km", [""])[0].strip()
            try:
                frad = float(frad_raw) if frad_raw else None
            except ValueError:
                return self._json(400, {"error": "radius_km must be a number"})
            if frad is not None:
                if frad <= 0:
                    return self._json(400, {"error": "radius_km must be positive"})
                if fnear is None:
                    return self._json(400, {"error": "radius_km requires near=lat,lon"})
            if fsort == "distance" and fnear is None:
                return self._json(400, {"error": "sort=distance requires near=lat,lon"})
            # Phase 2 time facets: after=/before=HH:MM on the listing start
            # time; honest 400s, strict zero-padded 24h shape only.
            fafter = q.get("after", [""])[0].strip()
            fbefore = q.get("before", [""])[0].strip()
            if fafter and not _is_hhmm(fafter):
                return self._json(400, {"error": "after must be HH:MM (zero-padded 24h, 00:00-23:59)"})
            if fbefore and not _is_hhmm(fbefore):
                return self._json(400, {"error": "before must be HH:MM (zero-padded 24h, 00:00-23:59)"})
            if fafter and fbefore and fafter > fbefore:
                return self._json(400, {"error": "after must not be later than before"})
            with LOCK:
                # C6: sqlite mode narrows q via the derived FTS5 index first
                # (token match, O(matches) instead of a full substring scan).
                # fts_ids None = index unavailable -> legacy substring scan.
                fts_ids = search_ids(term) if (term and mode() == "sqlite") else None
                # Phase 1 relevance: remember the bm25 rank (best first) so the
                # filtered result can keep relevance order for plain q-searches
                # (explicit sorts override it below).
                _rank = {lid: i for i, lid in enumerate(fts_ids)} \
                    if (term and fts_ids) else None
                if fts_ids == []:
                    res = []
                else:
                    pool = LISTINGS
                    if fts_ids is not None:
                        _idset = set(fts_ids)
                        pool = [l for l in LISTINGS
                                if not l.get("archived")
                                and l.get("visibility") != "private" and l["id"] in _idset]
                    res = [l for l in pool
                           if not l.get("archived")
                           and l.get("visibility") != "private"
                           and (not term or fts_ids is not None
                                or term in json.dumps(l).lower())
                           and (not fvert or l["vertical"] == fvert)
                           and (not fcat or l.get("category") == fcat)
                           and (not ftag or ftag in (l.get("tags") or []))
                           and (not ftags or any(t in (l.get("tags") or []) for t in ftags))
                           and (not floc or floc in _loc_norm(str(l.get("location", "")))
                                # Phase 1 universal listings: route verticals (rides) —
                                # any schema-declared *_location field satisfies a
                                # location query (from_location/to_location matching).
                                or any(floc in _loc_norm(str(v)) for _k, v in l.items()
                                       if _k.endswith("_location") and isinstance(v, str)))
                           # C2 date range: a listing without a date cannot satisfy it
                           and (not ffrom or str(l.get("date", "")) >= ffrom)
                           and (not fto or bool(l.get("date")) and str(l.get("date")) <= fto)]
                if frole:
                    res = [l for l in res if l.get("role", "offer") == frole]
                if fmaxv is not None:
                    res = [l for l in res if float(l.get("price", 0)) <= fmaxv]
                if fminv is not None:
                    res = [l for l in res if float(l.get("price", 0)) >= fminv]
                # Phase 2 geo: a listing without numeric lat/lon cannot satisfy
                # a geo filter (the dateless-listing law, applied to space).
                # Distances live in _geo_km (keyed by id, never on the canonical
                # dicts); filter preserves prior order unless sort=distance.
                _geo_km = {}
                if fnear is not None:
                    _kept = []
                    for l in res:
                        try:
                            _la, _lo = float(l.get("lat")), float(l.get("lon"))
                        except (TypeError, ValueError):
                            continue
                        if not (-90.0 <= _la <= 90.0 and -180.0 <= _lo <= 180.0):
                            continue
                        _kept.append(l)
                        _geo_km[l["id"]] = round(_dist_km(fnear[0], fnear[1], _la, _lo), 3)
                    res = _kept
                    if frad is not None:
                        res = [l for l in res if _geo_km.get(l["id"], float("inf")) <= frad]
                if fsort == "distance":
                    res.sort(key=lambda l: _geo_km.get(l["id"], float("inf")))
                # Phase 2 time facets: a listing without a well-formed HH:MM
                # time cannot satisfy a time facet (the coordless-geo law,
                # applied to time-of-day); zero-padded 24h strings compare
                # chronologically, bounds inclusive.
                if fafter or fbefore:
                    res = [l for l in res
                           if _is_hhmm(l.get("time"))
                           and (not fafter or l["time"] >= fafter)
                           and (not fbefore or l["time"] <= fbefore)]
                # Phase 1 relevance: plain q-searches keep bm25 order (best
                # first); any explicit sort below overrides it deterministically.
                if _rank is not None and not fsort:
                    res.sort(key=lambda l: _rank.get(l["id"], len(_rank)))
                if fsort == "price":
                    res.sort(key=lambda l: float(l.get("price", 0)))
                elif fsort == "date":
                    res.sort(key=lambda l: (not l.get("date"), str(l.get("date", ""))))
                elif fsort == "newest":
                    res.reverse()  # LISTINGS is append-ordered; ids are monotonic
                # Phase 3 marketplace: ONE sponsored listing rides the LAST
                # position of the result window — organic order is never for
                # sale; the paid slot is additive, capped (1/page), labeled.
                _sponsored = None
                for _l in res:
                    if _normalize_sponsor(_l.get("_sponsor")) is not None:
                        _sponsored = _l
                        break
                if _sponsored is not None and len(res) > 1:
                    res = [l for l in res if l is not _sponsored] + [_sponsored]
            # CATALOGS P3: two-answer search. Listing hits stay the first
            # answer; catalog ITEM hits ride alongside, grouped by merchant,
            # deterministic substring match over item titles + tags. Catalog
            # items NEVER leak into the listing result set itself.
            _cat_items = []
            if term:
                with LOCK:
                    for c in CATALOGS.values():
                        _mslug = c.get("merchant")
                        for pth, it in _cat_walk(c.get("tree") or {}):
                            _hay = " ".join([str(it.get("title", ""))] +
                                            [str(t) for t in (it.get("tags") or []) if isinstance(t, str)]).lower()
                            if term in _hay:
                                _cat_items.append({"catalog_id": c["id"], "merchant": _mslug,
                                    "path": " / ".join(pth), "title": str(it.get("title", ""))[:80],
                                    "price": it.get("price")})
                            if len(_cat_items) >= 20:
                                break
                        if len(_cat_items) >= 20:
                            break
            total = len(res)
            res, off, lim = _paginate(res, parse_qs(u.query))
            return self._json(200, {"count": total, "offset": off, "limit": lim,
                "returned": len(res), "filters": {
                "q": term, "vertical": fvert, "role": frole or None,
                "category": fcat, "tag": ftag,
                "catalog_items": _cat_items,
                "tags": ftags or None, "location": floc, "min_price": fmin or None,
                "max_price": fmax or None, "from": ffrom or None, "to": fto or None,
                "near": fnear_raw or None, "radius_km": frad or None,
                "after": fafter or None, "before": fbefore or None,
                "sort": fsort or None}, "listings": [
                    # Phase 2 geo: distance_km rides on the response COPY only
                    # (_pub_listing builds fresh dicts; canonical LISTINGS stay
                    # free of request-derived values).
                    dict(_pub_listing(x),
                         **({"distance_km": _geo_km[x["id"]]} if x["id"] in _geo_km else {}),
                         **({"sponsored": True} if _normalize_sponsor(x.get("_sponsor")) is not None else {}))
                    for x in res]})
        if u.path == "/suggest":
            """C6-UX discovery helper: live vocabulary matching q.
            Empty q returns the full tag/category/vertical tree root;
            agents explore iteratively instead of guessing vocab."""
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests - slow down (retry shortly)"})
            sq = parse_qs(u.query).get("q", [""])[0].strip().lower()
            if len(sq) > READ_Q_MAX:
                return self._json(400, {"error": f"q too long (max {READ_Q_MAX} chars)"})
            tags, cats, verts = set(), set(), set()
            with LOCK:
                for l in LISTINGS:
                    if l.get("archived") or l.get("visibility") == "private":
                        continue
                    for t in (l.get("tags") or []):
                        if sq in str(t).lower():
                            tags.add(str(t))
                    c = l.get("category")
                    if c and sq in str(c).lower():
                        cats.add(str(c))
                    v = l.get("vertical")
                    if v and sq in str(v).lower():
                        verts.add(str(v))
            return self._json(200, {"q": sq, "tags": sorted(tags)[:100],
                "categories": sorted(cats)[:100], "verticals": sorted(verts)[:100]})
        if u.path == "/branding":
            # Public read: the partner landing overlays its branding from here
            # (self-service customization, owner call 2026-10-31). Server-pinned
            # FIXED rails are NOT editable - they cannot be hidden or altered.
            with LOCK:
                return self._json(200, {"branding": dict(BRANDING), "hub": HUB_NAME,
                    "fixed": ["escrow_badges", "testnet_label", "attribution", "checkout_ux"],
                    "note": "partner-editable fields only; PUT requires the owning acct- account"})
        if u.path == "/organizer/earnings":
            # W3.4: organizer earnings view (private mirror; owner-only).
            # NEVER public: totals are exactly what proveEarningsFloor hides.
            cred = self.headers.get("X-Hub-Token", "")
            if not cred:
                return self._json(401, {"error": "missing X-Hub-Token",
                    "hint": "log in (POST /accounts/login) and send your list token"})
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
            if p:
                p, err = _gen_check(p)
            if not p:
                return self._json(403, {"error": err or "token not valid for earnings",
                    "hint": "send your list token (the owning account)"})
            me = p.get("sub", "")
            with LOCK:
                e = EARNINGS.get(me) or {"settledCount": 0, "totalVolume": 0.0, "events": []}
                ev = {"settledCount": e.get("settledCount", 0),
                      "totalVolume": round(float(e.get("totalVolume", 0.0)), 2),
                      "events": len(e.get("events", [])),
                      "principal": me}
            return self._json(200, {**ev,
                "note": "private mirror of settled payouts (RELEASED + DIRECT, payout>0)",
                "zk": "prove a floor without revealing totals: POST /organizer/earnings-proof {min_volume, min_settlements} (earnings.compact proveEarningsFloor is the on-chain ZK act)"})
        if u.path == "/bookings":
            cred = self.headers.get("X-Hub-Token", "")  # I2: token required, principal-scoped
            # F2 2026-11-03: browsers landing on /bookings directly (typed
            # URL, old link) get the human face — the SPA dashboard — not raw
            # JSON. Tokened callers and JSON agents are unaffected.
            if not cred and "text/html" in (self.headers.get("Accept") or ""):
                self.send_response(302)
                self.send_header("Location", "/?view=dash")
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                return
            payload, err = None, "missing X-Hub-Token"
            if cred:
                for act in ("book", "list"):
                    payload, err = hublib.verify_token(BOOKING_KEY, cred, act, single_use=False)
                    if payload: break
            if payload:
                payload, err = _gen_check(payload)  # B1
            if not payload:
                return self._json(401, {"error": err or "invalid token",
                    "hint": "POST /access {agent: '<your-agent>'} then send token as X-Hub-Token"})
            me = payload["sub"]
            with LOCK:
                mine = [b for b in BOOKINGS if b.get("booked_by") == me]
            return self._json(200, {"bookings": mine, "principal": me,
                "note": "principal-scoped: you see only your own bookings"})
        if u.path == "/sponsorship/stats":
            """W2 #1 observability: honest sponsorship budget state (no secrets)."""
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests - slow down (retry shortly)"})
            import sponsorship as _sp
            return self._json(200, _sp.stats())
        if u.path.startswith("/escrow/") and u.path.endswith("/proof"):
            """W2 #2: verify-without-trust escrow proof endpoint (Buildathon
            Wave 2). Anyone (esp. AI agents) can verify chain state of an
            escrow WITHOUT trusting the hub: we re-read the escrow from the
            configured indexer(s) (dual-source when configured; fail-closed)
            and return the raw chain projection + verification metadata. No
            booking details, no identities - only what the chain itself says.
            Path: /escrow/{escrow_id}/proof?contract=<address>
                  (contract optional when HUB_ESCROW_CONTRACT is set)"""
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests - slow down (retry shortly)"})
            eid_raw = u.path[len("/escrow/"):-len("/proof")]
            if not re.fullmatch(r"[1-9][0-9]{0,11}", eid_raw or ""):
                return self._json(400, {"error": "escrow id must be a positive integer"})
            eid = int(eid_raw)
            q = parse_qs(u.query)
            contract = (q.get("contract", [""])[0].strip()
                        or os.environ.get("HUB_ESCROW_CONTRACT", "").strip())
            if not contract:
                return self._json(400, {"error": "contract address required (?contract= or HUB_ESCROW_CONTRACT)"})
            er = {"contract": contract, "escrow_id": eid, "tx": ""}
            esc, gerr = _chain_gate_read(er, dual=True)
            if esc is None:
                code, body = gerr
                return self._json(code, body)
            # pseudonymous linkage: does any booking reference this escrow?
            # (no booking details leak - only existence of the link + booking id)
            with LOCK:
                linked = next((b["id"] for b in BOOKINGS
                               if (b.get("escrow_ref") or {}).get("contract") == contract
                               and (b.get("escrow_ref") or {}).get("escrow_id") == eid), None)
            return self._json(200, {
                "escrow_id": eid,
                "contract": contract,
                "state": esc.get("state"),
                "state_name": esc.get("state_name"),
                "amount": esc.get("amount"),
                "deadline": esc.get("deadline"),
                "tx": esc.get("tx"),
                "verified_at": time.time(),
                "sources": ("dual (both indexers agree)" if CHAIN_INDEXER_2 else "single indexer"),
                "trust_model": "verify-without-trust: state re-read from indexer(s); hub claim is NOT required",
                "booking_ref": linked,
                "note": "fail-closed projection of on-chain state; booking linkage is pseudonymous",
            })
        if u.path.startswith("/bookings/"):
            # H10: single-booking status poll. Participant (buyer) or listing-owner
            # only. Unknown-or-not-yours is an indistinguishable 404 (no existence
            # oracle). Projection is pseudonymous; private details stay secret-gated
            # via GET /book/{id} + booking secret.
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests — slow down (retry shortly)"})
            cred = self.headers.get("X-Hub-Token", "")
            payload, err = None, "missing X-Hub-Token"
            if cred:
                for act in ("book", "list"):
                    payload, err = hublib.verify_token(BOOKING_KEY, cred, act, single_use=False)
                    if payload: break
            if payload:
                payload, err = _gen_check(payload)  # B1
            if not payload:
                return self._json(401, {"error": err or "invalid token",
                    "hint": "send your login/agent token as X-Hub-Token"})
            me = payload["sub"]
            bid = u.path[len("/bookings/"):]
            with LOCK:
                b = next((x for x in BOOKINGS if x["id"] == bid), None)
                allowed = bool(b) and (b.get("booked_by") == me or
                    any(l.get("owner") == me and l["id"] == b.get("listing_id") for l in LISTINGS))
            if not allowed:
                return self._json(404, {"error": f"no booking {bid} visible to you (unknown, or you are not the buyer/owner)"})
            _tp = None
            _tkb = ticketing.lookup_by_bid(TICKETS, bid)
            if _tkb is not None:
                _tp = {"redeemed": bool(_tkb.get("redeemed_ts")),
                       "guest": ticketing.display_name_of(_tkb),
                       "title": _tkb.get("title"), "when": _tkb.get("when"),
                       "qty": _tkb.get("qty"), "display_choice": _tkb.get("display_choice")}
                if b["booked_by"] == me:
                    _pubt = os.environ.get("EVERLIST_PUBLIC_URL", "https://everlist.network").rstrip("/")
                    _tp["ticket_url"] = ticketing.ticket_url(_tkb["token"], _pubt)
                    _tp["ticket_token"] = _tkb["token"]
            return self._json(200, {**b, "view": "buyer" if b["booked_by"] == me else "owner",
                "ticket": _tp,
                "escrow_guide": _escrow_guide(b),
                "note": "pseudonymous projection; private details remain secret-gated (GET /book/{id})"})
        if u.path == "/orders":
            """Merchant-scoped incoming orders (E1/E2 gap fix): bookings made
            against listings this principal owns. Privacy projection applies:
            pseudonymous refs only — real buyer names stay in the secret store."""
            cred = self.headers.get("X-Hub-Token", "")
            payload, err = None, "missing X-Hub-Token"
            if cred:
                payload, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                if payload:
                    payload, err = _gen_check(payload)  # B1
            if not payload:
                return self._json(401, {"error": err or "invalid token",
                    "hint": "merchant list token required (POST /access acts=['list'])"})
            me = payload["sub"]
            with LOCK:
                my_listings = {l["id"] for l in LISTINGS if l.get("owner") == me}
                # H15: identity field is schema-declared per vertical (attendee/buyer/client)
                _idf = tuple(sorted({s["booking"]["identity"] for s in VERTICAL_SCHEMAS.values()}))
                pubfields = ("id", "listing_id", "vertical", "escrow", "amount",
                             "hub_fee", "owner_payout", "quantity", "created",
                             "booked_by", "escrow_ref") + _idf
                orders = [{k: b[k] for k in pubfields if k in b}
                          for b in BOOKINGS if b.get("listing_id") in my_listings]
            return self._json(200, {"orders": orders, "merchant": me, "count": len(orders)})
        if u.path == "/ledger":
            with LOCK:
                # totals cover booking-fee entries; x402 settlement events carry
                # their own shape (kind=x402_settlement, detail.*) and are excluded
                totals = {"total_volume": round(sum(t.get("amount", 0) for t in LEDGER), 2),
                          "total_hub_fees": round(sum(t.get("hub_fee", 0) for t in LEDGER), 2),
                          "x402_settlements": sum(1 for t in LEDGER if t.get("kind") == "x402_settlement")}
            # Run7 D2: totals are GROSS (include refunded bookings' original fee) —
            # this matches check_hub C5's recompute-from-entries. settled_* subtotals
            # exclude REFUNDED entries so operators see what actually stuck.
            _settled_vol = round(sum(t.get("amount", 0) for t in LEDGER if t.get("escrow") != "REFUNDED"), 2)
            _settled_fees = round(sum(t.get("hub_fee", 0) for t in LEDGER if t.get("escrow") != "REFUNDED"), 2)
            return self._json(200, {"ledger": LEDGER, "totals": totals,
                "settled_volume": _settled_vol, "settled_hub_fees": _settled_fees,
                "note": "public ledger; amounts + per-booking random opaque refs only - participant identities are never stored. One entry per booking (escrow field updated on transition, original fee retained on refund for audit). settled_volume/settled_hub_fees exclude refunded bookings. Residual-linkage disclosure: a single hub's operator could still correlate bookings within its own private store; true cross-hub unlinkability requires the Midnight personhood adapter (A2)",
                "privacy": "anon refs are random per booking - NOT name-derived, NOT linkable across bookings"})
        if u.path == "/challenge":
            """D2: registry ownership proof - echo the nonce to prove URL control."""
            q = parse_qs(u.query)
            nonce = (q.get("nonce") or [""])[0]
            return self._json(200, {"challenge_response": nonce,
                                     "note": "registry ownership proof (D2)"})
        if u.path == "/registry":
            return self._json(200, {"tiers": {
                    "open": "unverified self-registration; agents browse at own risk",
                    "verified": "community-reviewed hubs meeting content-policy + fairness checks"},
                "responsibility": "each hub operator is responsible for the legality of its own listings; agents and registries filter",
                "hubs": [
                    {"url": "http://localhost:8802", "type": "universal-commerce", "tier": "verified",
                     "content_policy": "/policy"}]})
        if u.path.startswith("/book/"):
            parts = [p for p in u.path.split("/") if p]
            if len(parts) == 2:  # GET /book/{id} - private details
                bid = parts[1]
                cred = self.headers.get("X-Hub-Token", "")  # H1: credentials in headers, never in URLs
                rec = SECRETS.get(bid)
                if not rec: return self._json(404, {"error": "no booking"})
                if not hmac.compare_digest(cred, rec["secret"]):
                    p, err = hublib.verify_token(BOOKING_KEY, cred, "details",
                                                 single_use=False, subject=bid)
                    if not p or p.get("sub") != bid:
                        return self._json(403, {"error": err or "invalid or missing credential"})
                with LOCK:
                    b = next((x for x in BOOKINGS if x["id"] == bid), None)
                if not b: return self._json(404, {"error": "no booking"})
                _tp = None
                _tkb = ticketing.lookup_by_bid(TICKETS, bid)
                if _tkb is not None:
                    _pubt = os.environ.get("EVERLIST_PUBLIC_URL", "https://everlist.network").rstrip("/")
                    _tp = {"ticket_url": ticketing.ticket_url(_tkb["token"], _pubt),
                           "ticket_token": _tkb["token"],
                           "redeemed": bool(_tkb.get("redeemed_ts")),
                           "guest": ticketing.display_name_of(_tkb),
                           "title": _tkb.get("title"), "when": _tkb.get("when"),
                           "qty": _tkb.get("qty"), "display_choice": _tkb.get("display_choice")}
                return self._json(200, {"id": bid, "ticket": _tp,
                    "private_details": {**b, **rec["private"]}})
        if u.path.startswith("/ticket/"):
            # T5: door ticket capability read. The token IS the credential;
            # the projection is the honest door status. Names only per the
            # buyer's explicit display choice - never SECRETS identity.
            if not _read_gate(self):
                return self._json(429, {"error": "too many read requests - slow down (retry shortly)"})
            tok = u.path[len("/ticket/"):]
            if not re.fullmatch(r"[A-Za-z0-9_-]{16,120}", tok or ""):
                return self._json(404, {"error": "no ticket"})
            tk = ticketing.lookup_by_token(TICKETS, tok)
            if tk is None:
                return self._json(404, {"error": "no ticket"})
            bid = tk.get("bid")
            cred = self.headers.get("X-Hub-Token", "")
            with LOCK:
                _b = next((x for x in BOOKINGS if x["id"] == bid), None)
                _cl = next((x for x in LISTINGS if x["id"] == _b.get("listing_id")), None) if _b else None
            buyer = True  # capability law: whoever holds the link IS the attendee
            owner = False
            if cred and _b is not None:
                rec = SECRETS.get(bid)
                if rec and hmac.compare_digest(cred, rec["secret"]):
                    pass  # booking secret holder: attendee confirmed (already buyer)
            if cred:
                p, _perr = hublib.verify_token(BOOKING_KEY, cred, "details", single_use=False, subject=bid)
                if p and p.get("sub") == bid:
                    buyer = True
                if not owner:
                    p, _perr = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                    if p:
                        p, _perr = _gen_check(p)
                    if p and _cl is not None and str(p.get("sub", "")).startswith("acct-") and p["sub"] == _cl.get("owner"):
                        owner = True
            proj = {"bid": bid, "title": tk.get("title"), "when": tk.get("when"),
                    "location": str((_cl or {}).get("location") or ""),
                    "listing_id": str((_b or {}).get("listing_id") or ""),
                    "qty": tk.get("qty"), "guest": ticketing.display_name_of(tk),
                    "display_choice": tk.get("display_choice"),
                    "redeemed": bool(tk.get("redeemed_ts")),
                    "you_are_owner": owner, "you_are_buyer": buyer}
            if tk.get("redeemed_ts"):
                proj["redeemed_ts"] = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(tk["redeemed_ts"]))
            return self._json(200, proj)
        if u.path == "/admin/review-queue":
            # S6-L4: manual review queue. Same admin gate as /admin/tokens.
            cred = self.headers.get("X-Hub-Token", "")
            if not hmac.compare_digest(cred, ADMIN_KEY):
                return self._json(403, {"error": "invalid admin key"})
            with LOCK:
                flagged = [{"id": l["id"], "title": l.get("title"), "owner": l.get("owner"),
                            "paid_rating_count": l.get("rating_count", 0),
                            "flags": l.get("review_flags", [])}
                           for l in LISTINGS if l.get("review_flags")]
            return self._json(200, {"flagged": flagged,
                "note": "S6-L4 manual review queue - detection only, never auto-deleted"})
        return self._json(404, {"error": "not found", "hint": "GET /.well-known/agent-hub.json (web pages like /agents or /transparency live on the webchat face, not this API face)"})

    def do_POST(self):
        self._t0 = time.time()  # H12: latency start
        path = urlparse(self.path).path
        # G4: global request-body cap (64KB) - reject before parsing.
        # Narrow exemption: owner image uploads - /branding/image and
        # /listings/{id}/image (magic-byte sniffed, DECODED caps inside).
        _g4 = 1200000 if (path == "/branding/image" or (path.startswith("/listings/") and path.endswith("/image"))) else 65536
        if int(self.headers.get("Content-Length", 0)) > _g4:
            return self._json(413, {"error": "request body too large (max %d bytes)" % _g4})
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            data = json.loads(raw) if raw.strip() else {}
        except Exception:
            # FED5 (run #5): malformed JSON on /mcp is a JSON-RPC parse error
            # (-32700, id null); parse text never leaks interpreter internals.
            if path == "/mcp":
                return self._json(400, {"jsonrpc": "2.0", "id": None,
                    "error": {"code": -32700, "message": "Parse error"}})
            return self._json(400, {"error": "invalid JSON body"})
        if path == "/accounts/notify/unsubscribe":
            # RFC 8058 one-click unsubscribe (List-Unsubscribe-Post). Same
            # signature law as the GET landing page. Never fails a mailbox.
            try:
                import emailkit as _ek
                q = parse_qs(u.query)
                princ = q.get("u", [""])[0]
                tok = q.get("t", [""])[0]
                if (princ.startswith("acct-") and tok
                        and _unsub_valid(princ, tok)
                        and princ in ACCOUNTS):
                    with LOCK:
                        ACCOUNTS[princ]["marketing_email"] = False
                        _persist_locked()
                    return self._json(200, {"ok": True, "marketing_email": False})
                return self._json(400, {"error": "invalid unsubscribe token"})
            except Exception:
                return self._json(400, {"error": "invalid unsubscribe token"})
        if path == "/mcp":
            # Phase D: MCP (Model Context Protocol) face - JSON-RPC 2.0 over
            # HTTP, thin loopback adapter onto this hub's own REST contract.
            # No logic of its own: auth/rate-limit/validation all live in the
            # REST layer and apply to every tool call unchanged.
            import mcp as _mcp
            st, body, extra = _mcp.handle(self, data, globals().get("_MCP_HUB_PORT", PORT))
            return self._json(st, body, extra_headers=extra or {})
        if path == "/access":
            # H5: per-source backstop — token minting must not be free (counts
            # every attempt, before validation)
            with LOCK:
                if not _auth_allow("access", _source_of(self)):
                    return self._json(429, {"error": "access rate limit reached for your source, retry later"})
            # I2 interim bootstrap: open issuance PRE-personhood (documented; replaced by Midnight A2)
            agent = str(data.get("agent", "")).strip()
            if not agent or len(agent) > 128:
                return self._json(400, {"error": "agent name required (max 128 chars)"})
            # RTF2: control chars + bidi overrides in agent names leak into
            # token subjects, chat surfaces and digests; names are identity —
            # keep them printable single-line (A3 probe: U+202E/U+0007 accepted)
            if _BAD_CHARS_RE.search(agent) or "\n" in agent or "\r" in agent:
                return self._json(400, {"error": "agent name must not contain control characters or bidi overrides"})
            if agent.lower().startswith("acct-"):
                # B3c-accounts forgery wall (CASE-INSENSITIVE: ACCT- would mint a token
                # whose sub only differs by case — future case-insensitive comparisons
                # would turn that into account takeover; refuse the whole namespace)
                return self._json(403, {"error": "acct- principals require the account code: POST /accounts/login {account_code, agent}"})
            acts = data.get("acts", ["book"])
            if not isinstance(acts, list) or not acts or any(a not in ("book", "list") for a in acts):
                return self._json(400, {"error": "acts must be a non-empty subset of ['book', 'list']"})
            ttl = min(max(int(data.get("ttl", 3600)), 60), 24*3600)
            toks = {a: hublib.mint_token(BOOKING_KEY, a, agent, ttl=ttl) for a in acts}
            return self._json(201, {"agent": agent, "tokens": toks, "ttl": ttl,
                "note": "interim open bootstrap (pre-personhood): anyone may obtain book/list tokens today; production identity = Midnight zk-personhood (A2)",
                "usage": "send as X-Hub-Token header on POST /book, POST /listings, GET /bookings"})

        # ---------------- TRACK E: embeddable checkout (E2/E3) ----------------
        if path == "/checkout/sessions":
            # Session create: public, per-source limited. The session is a
            # capability URL (chk- 128-bit); the hosted checkout page does the
            # pay/verify dance same-origin. Booking happens ONLY through
            # _book_core at verify time (zero drift from /book gates).
            if not isinstance(data, dict):
                return self._json(400, {"error": "JSON object required"})
            lid = str(data.get("listing_id", "")).strip()
            if not lid or len(lid) > 40:
                return self._json(400, {"error": "listing_id required"})
            qty = data.get("quantity", 1)
            if isinstance(qty, bool) or not isinstance(qty, int) or not (1 <= qty <= 100):
                return self._json(400, {"error": "quantity must be an integer in [1, 100]"})
            lang = str(data.get("lang", "en")).strip().lower()
            if lang not in ("en", "de"):
                lang = "en"
            origin = str(data.get("origin", "")).strip()
            if origin:
                # best-effort postMessage target ONLY (never a security
                # boundary: the payload carries no secrets either way)
                if not origin.startswith(("http://", "https://")) or len(origin) > 100 or "/" in origin[8:]:
                    origin = ""
            with LOCK:
                if not _auth_allow("checkout", _source_of(self)):
                    return self._json(429, {"error": "checkout rate limit reached for your source, retry later"})
                listing = next((l for l in LISTINGS if l["id"] == lid), None)
                if not listing or listing.get("visibility") == "private":
                    return self._json(404, {"error": f"no listing {lid}"})
                if listing.get("archived"):
                    return self._json(409, {"error": "listing archived - not bookable"})
                _v = listing["vertical"]
                _pt = listing.get("payment_terms") or _default_payment_terms(_v)
                price_c = int(round(listing["price"] * 100)) * qty
                # honesty walls BEFORE any session exists. Checkout v1 = FREE
                # listings only (demo rail, no money moves): paid listings
                # need PAY_MODE=testnet (wallet-pay rail) - refusing otherwise
                # IS the contract (OpenAPI note + pay-step docstring promise it).
                if price_c > 0 and PAY_MODE != "testnet":
                    return self._json(409, {"error": "paid listings need PAY_MODE=testnet (wallet-pay rail, TRACK E7) on this hub - fiat/card rails deferred (TRACK E4/E5); checkout covers free listings here"})
                sch = VERTICAL_SCHEMAS[_v]
                if sch.get("tracks_capacity"):
                    left = listing["capacity"] - listing.get("registered", 0)
                    if qty > left:
                        return self._json(409, {"error": "event full", "left": max(left, 0)})
                elif not listing.get("available", True):
                    return self._json(409, {"error": "listing unavailable"})
                if len(CHECKOUT_SESSIONS) >= CHECKOUT_CAP:
                    for k in list(CHECKOUT_SESSIONS)[: len(CHECKOUT_SESSIONS) // 10]:
                        CHECKOUT_SESSIONS.pop(k, None)
            sid = "chk-" + secrets.token_hex(16)
            now = time.time()
            sess = {"sid": sid, "listing_id": lid, "qty": qty, "status": "open",
                    "email": "", "name": "", "acct_id": "", "origin": origin,
                    "lang": lang, "terms": _pt, "created": now, "exp": now + CHECKOUT_TTL,
                    "pay_exp": 0, "attempts": 0, "last_code": 0,
                    # E7 rail honesty: paid sessions carry the wallet rail
                    # label (money moves at verify, testnet); free sessions
                    # stay demo (escrow WAIVED, nothing moves).
                    "rail": ("wallet-testnet" if price_c > 0 and PAY_MODE == "testnet"
                             else ("provider-pending" if CHECKOUT_PROVIDER else "demo")),
                    "booking_id": "", "provider_ref": None,
                    "total_c": price_c}
            with LOCK:
                CHECKOUT_SESSIONS[sid] = sess
                _persist_locked()
            return self._json(201, {"ok": True, "sid": sid,
                "url": "/checkout?sid=" + sid, "rail": sess["rail"],
                "exp": sess["exp"], **_checkout_face(sess)})
        _mck = re.match(r"^/checkout/sessions/(chk-[0-9a-f]{32})/(pay|verify)$", path)
        if _mck:
            return self._checkout_session(_mck.group(1), _mck.group(2), data)
        # ---------------- end TRACK E checkout POST routes ----------------

        if path == "/accounts/signup":
            # B3c-accounts v2: PoW-gated. Two kinds:
            #  keypair (default): client generates ed25519 seed OFF-server; we store
            #    ONLY the public key. Nothing stealable on the server, ever.
            #  code (legacy): server-minted code, sha256 at rest (kept for compat).
            agent = str(data.get("agent", "")).strip()
            if not agent or len(agent) > 128 or agent.lower().startswith("acct-"):
                return self._json(400, {"error": "agent name required (max 128 chars, no acct- prefix)"})
            # RTF2: same printable-name law as /access (bidi/CRLF/BEL rejected)
            if _BAD_CHARS_RE.search(agent) or "\n" in agent or "\r" in agent:
                return self._json(400, {"error": "agent name must not contain control characters or bidi overrides"})
            signup_lang = str(data.get("lang", "en")).strip().lower()
            if signup_lang not in ("en", "de"):
                signup_lang = "en"
            pubkey_hex = str(data.get("pubkey", "")).strip().lower()
            if pubkey_hex:
                if len(pubkey_hex) != 64:
                    return self._json(400, {"error": "pubkey must be 64 hex chars (ed25519 raw public key, 32 bytes)"})
                try:
                    bytes.fromhex(pubkey_hex)
                except ValueError:
                    return self._json(400, {"error": "pubkey must be hex"})
            pow_err = None
            with LOCK:
                if len(ACCOUNTS) >= ACCOUNTS_CAP:
                    return self._json(429, {"error": "hub at account capacity; contact the operator"})
                src = _source_of(self)
                if not _auth_allow("signup", src):
                    return self._json(429, {"error": "signup rate limit reached for your source, retry later"})
                pow_err = _pow_spend("signup", data.get("pow"))
                if pow_err:
                    return self._json(400, {"error": pow_err,
                        "hint": "GET /auth/challenge?kind=signup, solve, POST pow={challenge, nonce}"})
                if pubkey_hex and any(v.get("pubkey") == pubkey_hex for v in ACCOUNTS.values()):
                    return self._json(409, {"error": "pubkey already registered — log in instead"})
                aid = "acct-" + secrets.token_hex(4)
                while aid in ACCOUNTS:
                    aid = "acct-" + secrets.token_hex(4)
                acct = {"bound": [agent], "human_verified": False,
                        "verified_by": None, "created": time.time(), "email_lang": signup_lang,
                        "email": None, "email_verified": False,
                        "notify_email": True, "marketing_email": True,
                        "pending_email": None, "pending_code_hash": None,
                        "pending_exp": 0, "recovery_code_hash": None, "recovery_exp": 0,
                        "payout_pk": None, "midnight_credential": None}
                if pubkey_hex:
                    acct["kind"] = "keypair"
                    acct["pubkey"] = pubkey_hex
                else:
                    acct["kind"] = "code"
                    code = "acct-" + secrets.token_hex(8)
                    acct["code_hash"] = hashlib.sha256(code.encode()).hexdigest()
                ACCOUNTS[aid] = acct
                _persist_locked()
            if pubkey_hex:
                return self._json(201, {"account_id": aid, "kind": "keypair", "pubkey": pubkey_hex,
                    "account_code": None,
                    "code_note": "keypair account: the server stores ONLY your public key; your seed never leaves your device — we cannot lose or leak it"})
            return self._json(201, {"account_id": aid, "kind": "code", "account_code": code,
                "human_verified": False,
                "code_note": "shown ONCE — this code OWNS the account; store it like a seed phrase",
                "next": "verify as human: hub operator vouch (pilot) or POST /accounts/verify email code (deploy); login from any chat: POST /accounts/login {account_code, agent}"})
        if path == "/accounts/login":
            agent = str(data.get("agent", "")).strip()
            if not agent or len(agent) > 128 or agent.lower().startswith("acct-"):
                return self._json(400, {"error": "agent required (max 128 chars, no acct- prefix)"})
            code = str(data.get("account_code", "")).strip()
            pubkey_hex = str(data.get("pubkey", "")).strip().lower()
            with LOCK:
                src = _source_of(self)
                if not _auth_allow("login", src):
                    return self._json(429, {"error": "login rate limit reached for your source, retry later"})
                if pubkey_hex:
                    # HARDENING-v2: challenge-response. Server proves nothing secret is needed.
                    aid = next((a for a, v in ACCOUNTS.items() if v.get("pubkey") == pubkey_hex), None)
                    if not aid:
                        return self._json(403, {"error": "unknown pubkey"})
                    lch = LOGIN_CHALLENGES.pop(aid, None)
                    if not lch or time.time() > lch["exp"]:
                        return self._json(403, {"error": "no active login challenge — GET /auth/challenge?kind=login&pubkey=<hex> first"})
                    sig = str(data.get("sig", ""))
                    if len(sig) != 128:
                        return self._json(403, {"error": "sig must be 128 hex chars (ed25519 signature)"})
                    try:
                        vk = _EdPub.from_public_bytes(bytes.fromhex(pubkey_hex))
                        vk.verify(bytes.fromhex(sig), b"everlist-login:" + lch["ch"].encode())
                    except (_InvalidSig, ValueError, binascii.Error):
                        return self._json(403, {"error": "signature invalid"})
                else:
                    # legacy code login (pre-keypair accounts + recovery fallback)
                    if not code:
                        return self._json(400, {"error": "account_code or pubkey required"})
                    ch = hashlib.sha256(code.encode()).hexdigest()
                    aid = next((a for a, v in ACCOUNTS.items() if hmac.compare_digest(v.get("code_hash", ""), ch)), None)
                    if not aid:
                        return self._json(403, {"error": "invalid account code"})
                if agent not in ACCOUNTS[aid]["bound"]:
                    if len(ACCOUNTS[aid]["bound"]) >= 25:  # binding cap: no unbounded list growth
                        return self._json(409, {"error": "agent binding limit (25) reached for this account"})
                    ACCOUNTS[aid]["bound"].append(agent)  # multi-agent binding (agent-led onboarding)
                _persist_locked()
            acts = ["book", "list"]
            gen = ACCOUNTS[aid].get("gen", 0)
            toks = {a: hublib.mint_token(BOOKING_KEY, a, aid, ttl=24*3600,
                                         extra={"gen": gen}) for a in acts}
            return self._json(200, {"account_id": aid, "agent": agent,
                "human_verified": ACCOUNTS[aid]["human_verified"],
                "verified_by": ACCOUNTS[aid].get("verified_by"),
                "payout_pk": ACCOUNTS[aid].get("payout_pk"),
                "midnight_credential": ACCOUNTS[aid].get("midnight_credential"),
                "tokens": toks, "ttl": 24*3600,
                "note": "tokens act AS the account (sub=acct-<id>) for 24h; edit/delete need no per-listing codes"})
        if path == "/branding":
            # Self-service branding write (owner call 2026-10-31). OWNERSHIP LAW:
            # acct- principal ONLY (same law as manage/confirm) - open /access
            # tokens can never rebrand a hub. Validation walls: accent #RRGGBB,
            # length caps, control chars refused (RTF2), lang whitelist.
            # FIXED rails (escrow/testnet labels, attribution, checkout UX) are
            # server-pinned and rejected if present.
            cred = self.headers.get("X-Hub-Token", "")
            p, err = None, "missing X-Hub-Token"
            if cred:
                p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                if p:
                    p, err = _gen_check(p)
            if not p:
                return self._json(401, {"error": err or "missing X-Hub-Token",
                    "hint": "login via POST /accounts/login and send your list token"})
            if not str(p.get("sub", "")).startswith("acct-"):
                return self._json(403, {"error": "branding is owner-only (acct- account required)",
                    "hint": "open /access tokens cannot rebrand a hub; use the organizer account"})
            with LOCK:
                if not _auth_allow("branding", _source_of(self)):
                    return self._json(429, {"error": "branding rate limit reached for your source, retry later"})
            fields = ("brand_name", "tagline", "hero_text", "logo_url", "location", "accent",
                      "accent2", "theme", "about_text", "site_url", "instagram_url", "lang")
            clean = {}
            for k in fields:
                if k not in data:
                    continue
                v = data[k]
                if k == "accent":
                    if not isinstance(v, str) or not BRANDING_COLOR_RE.match(v):
                        return self._json(400, {"error": "accent must be #RRGGBB"})
                    clean[k] = v.lower()
                elif k == "lang":
                    if v not in BRANDING_LANGS:
                        return self._json(400, {"error": "lang must be one of " + ", ".join(BRANDING_LANGS)})
                    clean[k] = v
                elif k == "logo_url":
                    if not isinstance(v, str) or not (v.startswith("https://") or v == ""):
                        return self._json(400, {"error": "logo_url must be an https:// URL (or empty)"})
                    if len(v) > BRANDING_MAX[k]:
                        return self._json(400, {"error": "logo_url too long (max %d)" % BRANDING_MAX[k]})
                    clean[k] = v
                elif k == "accent2":
                    if not isinstance(v, str) or not BRANDING_COLOR_RE.match(v):
                        return self._json(400, {"error": "accent2 must be #RRGGBB"})
                    clean[k] = v.lower()
                elif k == "theme":
                    if v not in BRANDING_THEMES:
                        return self._json(400, {"error": "theme must be one of " + ", ".join(BRANDING_THEMES)})
                    clean[k] = v
                elif k == "site_url":
                    if not isinstance(v, str) or not (v.startswith("https://") or v == ""):
                        return self._json(400, {"error": "site_url must be an https:// URL (or empty)"})
                    if len(v) > BRANDING_MAX[k]:
                        return self._json(400, {"error": "site_url too long (max %d)" % BRANDING_MAX[k]})
                    clean[k] = v
                elif k == "instagram_url":
                    if not isinstance(v, str) or not (v.startswith("https://instagram.com/")
                                                      or v.startswith("https://www.instagram.com/") or v == ""):
                        return self._json(400, {"error": "instagram_url must be an https://instagram.com/ profile URL (or empty)"})
                    if len(v) > BRANDING_MAX[k]:
                        return self._json(400, {"error": "instagram_url too long (max %d)" % BRANDING_MAX[k]})
                    clean[k] = v
                elif k == "about_text":
                    if not isinstance(v, str):
                        return self._json(400, {"error": "about_text must be a string"})
                    CR, LF = chr(13), chr(10)
                    if CR in v or _BAD_CHARS_RE.search(v.replace(LF, "")):
                        return self._json(400, {"error": "about_text must not contain control characters"})
                    if len(v) > BRANDING_MAX[k]:
                        return self._json(400, {"error": "about_text too long (max %d)" % BRANDING_MAX[k]})
                    clean[k] = v.strip()
                elif k in BRANDING_IMG_FIELDS:
                    # clearing only - uploads go through POST /branding/image
                    if v == "":
                        clean[k] = ""
                    else:
                        return self._json(400, {"error": "%s is set via POST /branding/image (multipart-free data URL upload)" % k})
                else:
                    if not isinstance(v, str):
                        return self._json(400, {"error": "%s must be a string" % k})
                    if _BAD_CHARS_RE.search(v) or "\n" in v or "\r" in v:
                        return self._json(400, {"error": "%s must not contain control characters" % k})
                    if len(v) > BRANDING_MAX[k]:
                        return self._json(400, {"error": "%s too long (max %d)" % (k, BRANDING_MAX[k])})
                    clean[k] = v.strip()
            unknown = set(data.keys()) - set(fields)
            if unknown:
                return self._json(400, {"error": "unknown/fixed fields rejected: " + ", ".join(sorted(unknown)),
                    "note": "escrow badges, testnet labels, attribution and checkout UX are server-pinned"})
            with LOCK:
                # v2 MERGE semantics (fixes latent wipe bug): absent field =
                # unchanged, explicit "" = cleared. Old replace-semantics
                # wiped unset fields (e.g. uploaded images) on partial saves.
                BRANDING.update(clean)
                _persist_locked()
            return self._json(200, {"ok": True, "branding": dict(BRANDING)})
        if path == "/branding/image":
            # v2: partner image UPLOAD (logo/hero). Same ownership law as
            # /branding (acct- ONLY). Magic-byte MIME sniffing - SVG refused
            # (script-capable), decoded-size caps per kind. Stored as data URL
            # in BRANDING -> rendered same-origin, no external hosting.
            cred = self.headers.get("X-Hub-Token", "")
            p, err = None, "missing X-Hub-Token"
            if cred:
                p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                if p:
                    p, err = _gen_check(p)
            if not p:
                return self._json(401, {"error": err or "missing X-Hub-Token"})
            if not str(p.get("sub", "")).startswith("acct-"):
                return self._json(403, {"error": "branding images are owner-only (acct- account required)"})
            with LOCK:
                if not _auth_allow("branding", _source_of(self)):
                    return self._json(429, {"error": "branding rate limit reached for your source, retry later"})
            kind = str(data.get("kind", ""))
            if kind not in BRANDING_IMG_CAPS:
                return self._json(400, {"error": "kind must be logo or hero"})
            field, cap = BRANDING_IMG_CAPS[kind]
            du = str(data.get("data_url", ""))
            m = re.match(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$", du)
            if not m:
                return self._json(400, {"error": "data_url must be data:image/png|jpeg|webp;base64,... (SVG refused)"})
            try:
                blob = base64.b64decode(m.group(2), validate=True)
            except (binascii.Error, ValueError):
                return self._json(400, {"error": "data_url base64 malformed"})
            if len(blob) > cap:
                return self._json(400, {"error": "%s image too large: %d bytes (max %d)" % (kind, len(blob), cap)})
            PNGSIG = bytes([0x89]) + b"PNG" + bytes([0x0d, 0x0a, 0x1a, 0x0a])
            JPEGSIG = bytes([0xff, 0xd8, 0xff])
            if blob[:8] == PNGSIG:
                mime = "image/png"
            elif blob[:3] == JPEGSIG:
                mime = "image/jpeg"
            elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                return self._json(400, {"error": "file content is not PNG/JPEG/WebP (magic-byte sniff failed)"})
            with LOCK:
                BRANDING[field] = "data:" + mime + ";base64," + m.group(2)
                _persist_locked()
            return self._json(200, {"ok": True, "field": field, "bytes": len(blob), "mime": mime})
        if path == "/accounts/payout":
            # M9: organizer payout key - a COIN PUBLIC key (64-hex, 32 bytes),
            # NEVER a secret. Escrow releases pay the key fixed at creation;
            # this field is where organizers tell the hub/agents where payouts
            # go. The hub stores public keys only - secrets stay in wallets.
            code = str(data.get("account_code", "")).strip()
            pk = str(data.get("payout_pk", "")).strip().lower()
            if not re.fullmatch(r"[0-9a-f]{64}", pk or ""):
                return self._json(400, {"error": "payout_pk must be a 64-hex coin PUBLIC key (32 bytes); never send secret keys or seeds"})
            ch = hashlib.sha256(code.encode()).hexdigest() if code else None
            cred = self.headers.get("X-Hub-Token", "")
            p, _err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred else (None, None)
            if p:
                p, _err = _gen_check(p)  # stale tokens never prove identity
            with LOCK:
                # S2: limit BEFORE any secret comparison - wrong-code guesses
                # must count toward the source's bucket (was: post-auth shared
                # 'email' kind, letting unlimited account_code brute attempts)
                if not _auth_allow("payout", _source_of(self)):
                    return self._json(429, {"error": "payout rate limit reached for your source, retry later"})
                if p and p["sub"].startswith("acct-") and p["sub"] in ACCOUNTS:
                    aid = p["sub"]
                else:
                    aid = next((a for a, v in ACCOUNTS.items() if ch and v.get("code_hash") and hmac.compare_digest(v["code_hash"], ch)), None)
                if not aid:
                    return self._json(403, {"error": "login token or valid account_code required"})
                replaced = ACCOUNTS[aid].get("payout_pk") not in (None, "", pk)
                ACCOUNTS[aid]["payout_pk"] = pk
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid, "payout_pk": pk,
                "note": "coin PUBLIC key stored - escrow payouts target this key; keep its secret ONLY in your wallet" +
                        (" (previous key replaced)" if replaced else "")})
        if path == "/accounts/notify":
            # B-phase: honest unsubscribe for booking notifications. Same auth
            # law as /accounts/payout (login token or account_code; rate limit
            # BEFORE any secret comparison). Default is ON (only for accounts
            # that bind AND verify an email - no email, no mail, ever).
            code = str(data.get("account_code", "")).strip()
            want = data.get("notify_email")
            if want not in (True, False):
                return self._json(400, {"error": "notify_email must be true or false"})
            ch = hashlib.sha256(code.encode()).hexdigest() if code else None
            cred = self.headers.get("X-Hub-Token", "")
            p, _err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred else (None, None)
            if p:
                p, _err = _gen_check(p)
            with LOCK:
                if not _auth_allow("payout", _source_of(self)):
                    return self._json(429, {"error": "rate limit reached, retry later"})
                if p and p["sub"].startswith("acct-") and p["sub"] in ACCOUNTS:
                    aid = p["sub"]
                else:
                    aid = next((a for a, v in ACCOUNTS.items() if ch and v.get("code_hash") and hmac.compare_digest(v["code_hash"], ch)), None)
                if not aid:
                    return self._json(403, {"error": "login token or valid account_code required"})
                ACCOUNTS[aid]["notify_email"] = bool(want)
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid, "notify_email": bool(want),
                "note": "notifications on: transactional booking mails (created/confirmed/refunded; verified email only; marketing digest has its own opt-out)" if want
                        else "notifications off: no booking mails to this account (security codes always send)"})
        if path == "/accounts/lang":
            # i18n W2: per-account EMAIL language (booking mails, digest, codes).
            # Same auth law as /accounts/notify: login token or account_code;
            # rate limit BEFORE any secret comparison. Affects wording only -
            # amounts, windows and guarantees are identical in both languages.
            want = str(data.get("email_lang", "")).strip().lower()
            if want not in ("en", "de"):
                return self._json(400, {"error": "email_lang must be 'en' or 'de'"})
            code = str(data.get("account_code", "")).strip()
            ch = hashlib.sha256(code.encode()).hexdigest() if code else None
            cred = self.headers.get("X-Hub-Token", "")
            p, _err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred else (None, None)
            if p:
                p, _err = _gen_check(p)
            with LOCK:
                if not _auth_allow("payout", _source_of(self)):
                    return self._json(429, {"error": "rate limit reached, retry later"})
                if p and p["sub"].startswith("acct-") and p["sub"] in ACCOUNTS:
                    aid = p["sub"]
                else:
                    aid = next((a for a, v in ACCOUNTS.items() if ch and v.get("code_hash") and hmac.compare_digest(v["code_hash"], ch)), None)
                if not aid:
                    return self._json(403, {"error": "login token or valid account_code required"})
                ACCOUNTS[aid]["email_lang"] = want
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid, "email_lang": want,
                "note": "email language set: booking mails, weekly digest and codes arrive in "
                        + ("German" if want == "de" else "English")})
        if path == "/accounts/verify-midnight":
            # M14 Tier-2 sign-in: the account presents its Midnight credential
            # (credential.compact, M13). The hub READS the credential contract's
            # public state — admitted + not revoked — and only then sets
            # verified_by: midnight-zk SERVER-SIDE. Fail-closed on every error;
            # the mode (chain|simulated) labels every outcome honestly. A
            # missing verifier is BLOCKED, never a silent success (capability
            # modes). Revocation propagates: a revoked credential DOWNGRADES
            # the account (verified_by -> midnight-zk-revoked) — identity that
            # can be revoked must lose its benefit when revoked.
            code = str(data.get("account_code", "")).strip()
            ch = hashlib.sha256(code.encode()).hexdigest() if code else None
            cred_hdr = self.headers.get("X-Hub-Token", "")
            p, _err = hublib.verify_token(BOOKING_KEY, cred_hdr, "list", single_use=False) if cred_hdr else (None, None)
            if p:
                p, _err = _gen_check(p)  # stale tokens never prove identity
            with LOCK:
                # S2: limit BEFORE account resolution - unauthenticated
                # credential-id enumeration counts toward the source bucket
                if not _auth_allow("verify", _source_of(self)):
                    return self._json(429, {"error": "verify rate limit reached for your source, retry later"})
                if p and p["sub"].startswith("acct-") and p["sub"] in ACCOUNTS:
                    aid = p["sub"]
                else:
                    aid = next((a for a, v in ACCOUNTS.items() if ch and v.get("code_hash") and hmac.compare_digest(v["code_hash"], ch)), None)
                if not aid:
                    return self._json(403, {"error": "login token or valid account_code required"})
            cid_raw = str(data.get("credential_id", "")).strip()
            if not re.fullmatch(r"[1-9][0-9]{0,11}", cid_raw or ""):
                return self._json(400, {"error": "credential_id must be a positive integer (max 12 digits)"})
            hc = str(data.get("holder_commitment", "")).strip().lower()
            if hc and not re.fullmatch(r"[0-9a-f]{64}", hc):
                return self._json(400, {"error": "holder_commitment must be 64-hex (the PUBLIC commitment; never a secret)"})
            from midnight_credential import CredentialVerifier, CredentialError
            verifier = CredentialVerifier(CRED_ADDRESS, url=CRED_INDEXER or None,
                fixture_path=os.environ.get("HUB_CRED_FIXTURE", FIXTURE_DEFAULT))
            try:
                verdict = verifier.verify(int(cid_raw), holder_commitment_hex=hc or None)
            except CredentialError as e:
                return self._json(502, {"error": "credential verifier unavailable: %s" % e,
                    "mode": verifier.mode(), "verified_by": None})
            with LOCK:
                bound = ACCOUNTS[aid].get("midnight_credential")
                if verdict["admitted"] and not verdict["revoked"]:
                    if bound is not None and str(bound) != cid_raw:
                        return self._json(409, {"error": "account already bound to credential %s" % bound,
                            "note": "one credential per account (anti-sybil); ask the operator to rebind"})
                    # anti-sybil other direction: credential already bound to a different account?
                    taken = next((a for a, v in ACCOUNTS.items()
                                  if a != aid and str(v.get("midnight_credential")) == cid_raw), None)
                    if taken:
                        return self._json(409, {"error": "credential %s already bound to another account" % cid_raw})
                    ACCOUNTS[aid]["midnight_credential"] = int(cid_raw)
                    ACCOUNTS[aid]["human_verified"] = True
                    ACCOUNTS[aid]["verified_by"] = "midnight-zk"
                    _persist_locked()
                elif verdict["admitted"] and verdict["revoked"]:
                    if bound is not None and str(bound) == cid_raw:
                        # downgrade: revocation must remove the benefit
                        ACCOUNTS[aid]["human_verified"] = False
                        ACCOUNTS[aid]["verified_by"] = "midnight-zk-revoked"
                        _persist_locked()
            return self._json((200 if verdict["admitted"] and not verdict["revoked"] else 403),
                {"ok": bool(verdict["admitted"] and not verdict["revoked"]),
                 "account_id": aid, "mode": verdict["mode"],
                 "credential_id": cid_raw, "admitted": verdict["admitted"],
                 "revoked": verdict["revoked"], "verified_by": verdict["verified_by"],
                 "evidence_tx": verdict["evidence_tx"],
                 "note": "verification source: Midnight credential contract state (%s mode)" % verdict["mode"]})
        if path == "/accounts/vouch":
            # H5: admin-key brute-force backstop — failed attempts count
            with LOCK:
                if not _auth_allow("admin", _source_of(self)):
                    return self._json(429, {"error": "admin rate limit reached for your source, retry later"})
            # Pilot-grade human proof: hub operator vouches by name (admin-key gated).
            # Production: email 6-digit (deploy) or Midnight zk-personhood (A2).
            admin = self.headers.get("X-Admin-Key", "")
            if not admin or not hmac.compare_digest(admin, ADMIN_KEY):
                return self._json(403, {"error": "admin key required (X-Admin-Key)"})
            aid = str(data.get("account_id", "")).strip()
            with LOCK:
                if aid not in ACCOUNTS:
                    return self._json(404, {"error": f"no account {aid}"})
                ACCOUNTS[aid]["human_verified"] = True
                ACCOUNTS[aid]["verified_by"] = "admin-vouch"
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid,
                "human_verified": True, "verified_by": "admin-vouch"})
        if path == "/accounts/rotate":
            # recovery: a leaked code must never mean a lost account. Current code
            # proves control -> mints a NEW code, invalidates the old (hash swap).
            # Already-issued 24h login tokens stay valid until expiry (documented).
            code = str(data.get("account_code", "")).strip()
            if not code:
                return self._json(400, {"error": "account_code required"})
            ch = hashlib.sha256(code.encode()).hexdigest()
            with LOCK:
                if not _auth_allow("rotate", _source_of(self)):
                    return self._json(429, {"error": "rotate rate limit reached for your source, retry later"})
                aid = next((a for a, v in ACCOUNTS.items() if v.get("code_hash") and hmac.compare_digest(v["code_hash"], ch)), None)
                if not aid:
                    return self._json(403, {"error": "invalid account code"})
                new_code = "acct-" + secrets.token_hex(8)
                ACCOUNTS[aid]["code_hash"] = hashlib.sha256(new_code.encode()).hexdigest()
                ACCOUNTS[aid]["rotated"] = time.time()
                ACCOUNTS[aid]["gen"] = ACCOUNTS[aid].get("gen", 0) + 1  # B1: revoke old tokens
                LOGIN_CHALLENGES.pop(aid, None)
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid, "account_code": new_code,
                "code_note": "OLD CODE IS NOW INVALID and every previously issued login token is REVOKED — new code shown ONCE, store it"})
        if path == "/accounts/logout-all":
            # B1: revoke EVERY login token of this account (all agents, chats, devices).
            cred = self.headers.get("X-Hub-Token", "")
            p, err = None, "missing X-Hub-Token"
            if cred:
                for act in ("list", "book"):
                    p, err = hublib.verify_token(BOOKING_KEY, cred, act, single_use=False)
                    if p: break
            if p:
                p, err = _gen_check(p)
            if not p or not str(p.get("sub", "")).startswith("acct-"):
                return self._json(401, {"error": err or "account token required",
                    "hint": "send a login token as X-Hub-Token"})
            aid = p["sub"]
            with LOCK:
                if aid not in ACCOUNTS:
                    return self._json(404, {"error": "no account"})
                ACCOUNTS[aid]["gen"] = ACCOUNTS[aid].get("gen", 0) + 1
                LOGIN_CHALLENGES.pop(aid, None)
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid,
                "note": "every previously issued login token (all agents/devices) is now revoked — log in again where needed"})
        if path == "/accounts/email/bind":
            # bind/replace the recovery email. Logged-in account OR current code proves control.
            code = str(data.get("account_code", "")).strip()
            email = str(data.get("email", "")).strip().lower()
            if not email or "@" not in email or "." not in email.rsplit("@", 1)[1] or len(email) > 254 or " " in email:
                return self._json(400, {"error": "valid email required (name@domain.tld)"})
            ch = hashlib.sha256(code.encode()).hexdigest() if code else None
            cred = self.headers.get("X-Hub-Token", "")
            p, _err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred else (None, None)
            if p:
                p, _err = _gen_check(p)  # B1: a stale token never proves identity
            with LOCK:
                if p and p["sub"].startswith("acct-") and p["sub"] in ACCOUNTS:
                    aid = p["sub"]
                else:
                    aid = next((a for a, v in ACCOUNTS.items() if ch and v.get("code_hash") and hmac.compare_digest(v["code_hash"], ch)), None)
                if not aid:
                    return self._json(403, {"error": "login token or valid account_code required"})
                if not _auth_allow("email", _source_of(self)):
                    return self._json(429, {"error": "email rate limit reached for your source, retry later"})
                # if another VERIFIED account already holds this email: refuse (no takeover)
                for a, v in ACCOUNTS.items():
                    if a != aid and v["email"] == email and v["email_verified"]:
                        return self._json(409, {"error": "email already bound to another verified account"})
                vcode = secrets.token_hex(3).upper()   # 6 hex chars
                ACCOUNTS[aid]["pending_email"] = email
                ACCOUNTS[aid]["pending_code_hash"] = hashlib.sha256(vcode.encode()).hexdigest()
                ACCOUNTS[aid]["pending_exp"] = time.time() + 900   # 15 min
                _persist_locked()
                try:
                    _vt = emailkit_code("verify", vcode,
                                         loc=('de' if ACCOUNTS[aid].get('email_lang') == 'de' else 'en'))
                    delivery = _send_email(email, _vt["subject"], _vt)
                except Exception as ex:
                    return self._json(502, {"error": f"email delivery failed: {ex}"})
            _note = ("verification code sent - confirm with POST /accounts/email/verify {email, code}"
                     if delivery in ("sent", "logged")
                     else "HUB_EMAIL_MODE=off: no code was delivered and email verification cannot succeed until SMTP or log mode is configured")
            return self._json(200, {"ok": True, "account_id": aid, "email": email,
                "delivery": delivery, "note": _note})
        if path == "/accounts/email/verify":
            email = str(data.get("email", "")).strip().lower()
            vcode = str(data.get("code", "")).strip().upper()
            ch = hashlib.sha256(vcode.encode()).hexdigest() if vcode else None
            with LOCK:
                if not _auth_allow("verify", _source_of(self)):
                    return self._json(429, {"error": "verify rate limit reached for your source, retry later"})
                aid = next((a for a, v in ACCOUNTS.items()
                            if v.get("pending_email") == email and v.get("pending_code_hash")
                            and hmac.compare_digest(v["pending_code_hash"], ch or "x")
                            and time.time() < v["pending_exp"]), None)
                if not aid:
                    return self._json(403, {"error": "invalid or expired verification code"})
                ACCOUNTS[aid]["email"] = email
                ACCOUNTS[aid]["email_verified"] = True
                # owner GO 2026-10-03: a confirmed 6-digit email code IS the
                # Tier-1 human proof (threat-model law: Tier 1 never harder;
                # one email = one account + PoW + rate limits = the economics).
                # Tier-2 (require_verified_buyer) still demands midnight-zk /
                # admin-vouch — verified_by records the source honestly.
                ACCOUNTS[aid]["human_verified"] = True
                ACCOUNTS[aid]["verified_by"] = "email-code"
                ACCOUNTS[aid]["pending_email"] = None
                ACCOUNTS[aid]["pending_code_hash"] = None
                ACCOUNTS[aid]["pending_exp"] = 0
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid, "email": email, "email_verified": True,
                "human_verified": True, "verified_by": "email-code",
                "note": "recovery enabled: POST /accounts/email/recover {email} if you ever lose the account code; one-time human check complete (Tier-1 email proof)"})
        if path == "/accounts/email/recover":
            # request: ALWAYS answer the same way (no account enumeration)
            email = str(data.get("email", "")).strip().lower()
            if not email:
                return self._json(400, {"error": "email required"})
            with LOCK:
                if not _auth_allow("recover", _source_of(self)):
                    return self._json(429, {"error": "recover rate limit reached for your source, retry later"})
                # HARDENING-v2: PoW cost on recovery requests (email sends are expensive)
                pw = _pow_spend("recover", data.get("pow"))
                if pw:
                    return self._json(400, {"error": pw,
                        "hint": "GET /auth/challenge?kind=recover, solve, POST pow={challenge, nonce}"})
                aid = next((a for a, v in ACCOUNTS.items() if v.get("email") == email and v.get("email_verified")), None)
                if not aid:
                    return self._json(200, {"ok": True, "delivery": "suppressed",
                        "note": "if that email is bound to an account, a recovery code was sent"})
                rcode = secrets.token_hex(3).upper()
                ACCOUNTS[aid]["recovery_code_hash"] = hashlib.sha256(rcode.encode()).hexdigest()
                ACCOUNTS[aid]["recovery_exp"] = time.time() + 900
                _persist_locked()
                try:
                    _rt = emailkit_code("recover", rcode,
                                         loc=('de' if ACCOUNTS[aid].get('email_lang') == 'de' else 'en'))
                    delivery = _send_email(email, _rt["subject"], _rt)
                except Exception as ex:
                    return self._json(502, {"error": f"email delivery failed: {ex}"})
            return self._json(200, {"ok": True, "delivery": delivery,
                "note": "if that email is bound to an account, a recovery code was sent"})
        if path == "/accounts/email/recover/confirm":
            email = str(data.get("email", "")).strip().lower()
            rcode = str(data.get("code", "")).strip().upper()
            pubkey_hex = str(data.get("pubkey", "")).strip().lower()
            if pubkey_hex:
                if len(pubkey_hex) != 64:
                    return self._json(400, {"error": "pubkey must be 64 hex chars"})
                try:
                    bytes.fromhex(pubkey_hex)
                except ValueError:
                    return self._json(400, {"error": "pubkey must be hex"})
            new_code = "acct-" + secrets.token_hex(8)
            ch = hashlib.sha256(rcode.encode()).hexdigest() if rcode else None
            nch = hashlib.sha256(new_code.encode()).hexdigest()
            with LOCK:
                if not _auth_allow("recover", _source_of(self)):
                    return self._json(429, {"error": "recover rate limit reached for your source, retry later"})
                aid = next((a for a, v in ACCOUNTS.items()
                            if v.get("email") == email and v.get("email_verified") and v.get("recovery_code_hash")
                            and hmac.compare_digest(v["recovery_code_hash"], ch or "x")
                            and time.time() < v["recovery_exp"]), None)
                if not aid:
                    return self._json(403, {"error": "invalid or expired recovery code"})
                rec = ACCOUNTS[aid]
                LOGIN_CHALLENGES.pop(aid, None)
                if rec.get("kind") == "keypair":
                    # HARDENING-v2: recovery == key rotation — old seed dies, new seed rules
                    if not pubkey_hex:
                        return self._json(400, {"error": "keypair account: send pubkey=<64 hex> of your NEW seed"})
                    if any(a != aid and v.get("pubkey") == pubkey_hex for a, v in ACCOUNTS.items()):
                        return self._json(409, {"error": "pubkey already registered"})
                    rec["pubkey"] = pubkey_hex
                    rec["gen"] = rec.get("gen", 0) + 1  # B1: old seed's tokens die
                    rec["recovery_code_hash"] = None
                    rec["recovery_exp"] = 0
                    _persist_locked()
                    return self._json(200, {"ok": True, "account_id": aid, "kind": "keypair",
                        "code_note": "pubkey rotated — OLD SEED INVALID; sign a fresh challenge with the new seed to log in"})
                rec["code_hash"] = nch          # recovery == rotation: old code dies
                rec["gen"] = rec.get("gen", 0) + 1  # B1: revoke old tokens
                rec["recovery_code_hash"] = None
                rec["recovery_exp"] = 0
                _persist_locked()
                return self._json(200, {"ok": True, "account_id": aid, "account_code": new_code,
                    "code_note": "shown ONCE — store it; OLD CODE INVALID and old login tokens REVOKED"})
        if path == "/merchants" or path.startswith("/merchants/"):
            # CATALOGS P1 (owner GO 2026-11-12): merchant profiles. Create/PUT
            # need a list token (owner = token principal, same law as /listings
            # create); GET is public read. Cap-walled (HUB_MERCHANT_CAP) with
            # slug hygiene: lowercase kebab, no probes via weird names.
            _mslug = path[len("/merchants"):].lstrip("/")
            if path == "/merchants":
                # POST create
                _cred = self.headers.get("X-Hub-Token", "")
                _p, _err = hublib.verify_token(BOOKING_KEY, _cred, "list", single_use=False) if _cred \
                    else (None, "missing X-Hub-Token")
                if _p:
                    _p, _err = _gen_check(_p)
                if not _p:
                    return self._json(401, {"error": _err or "invalid list token"})
                with LOCK:
                    if not _auth_allow("create", _source_of(self)):
                        return self._json(429, {"error": "merchant creation rate limit reached"})
                    if _MERCHANT_CAP > 0:
                        _ownct = sum(1 for m in MERCHANTS.values() if m.get("owner") == _p["sub"])
                        if _ownct >= _MERCHANT_CAP:
                            return self._json(409, {"error": f"merchant cap reached ({_MERCHANT_CAP})"})
                slug = str(data.get("slug", "")).strip().lower()
                name = str(data.get("name", "")).strip()
                if not _MERCH_SLUG_RE.fullmatch(slug):
                    return self._json(400, {"error": "slug must be 2-39 chars: lowercase letters, digits, hyphens"})
                if not name or len(name) > 80:
                    return self._json(400, {"error": "name required (max 80 chars)"})
                locs = data.get("locations") or []
                if not isinstance(locs, list) or len(locs) > 10:
                    return self._json(400, {"error": "locations must be a list (max 10)"})
                _cl = []
                for _lo in locs:
                    if not isinstance(_lo, dict):
                        return self._json(400, {"error": "locations entries must be objects"})
                    _cl.append({"city": str(_lo.get("city", ""))[:60],
                                "address": str(_lo.get("address", ""))[:120],
                                "lat": _lo.get("lat"), "lon": _lo.get("lon")})
                ful = data.get("fulfillment") or []
                if isinstance(ful, str):
                    ful = [ful]
                if not isinstance(ful, list) or any(f not in _MERCH_FULFILL for f in ful):
                    return self._json(400, {"error": f"fulfillment must be a list of {_MERCH_FULFILL}"})
                promos = data.get("promos") or []
                if not isinstance(promos, list) or len(promos) > 5:
                    return self._json(400, {"error": "promos must be a list (max 5)"})
                _cp = []
                for _pr in promos:
                    if not isinstance(_pr, dict):
                        return self._json(400, {"error": "promos entries must be objects"})
                    _cp.append({"label": str(_pr.get("label", ""))[:80],
                                "detail": str(_pr.get("detail", ""))[:200]})
                with LOCK:
                    if slug in MERCHANTS:
                        return self._json(409, {"error": f"merchant slug already taken: {slug}"})
                    MERCHANTS[slug] = {"slug": slug, "name": name, "owner": _p["sub"],
                        "locations": _cl, "fulfillment": ful, "promos": _cp,
                        "description": str(data.get("description", ""))[:500],
                        "created": time.time()}
                    _persist_locked()
                return self._json(201, {"ok": True, "merchant": _pub_merchant(MERCHANTS[slug])})
            if not _mslug or len(_mslug) > 40 or not _MERCH_SLUG_RE.fullmatch(_mslug):
                return self._json(404, {"error": "no merchant"})
            with LOCK:
                _m = MERCHANTS.get(_mslug)
            if not _m:
                return self._json(404, {"error": f"no merchant {_mslug}"})
            # CATALOGS hardening: this hub routes GET/POST/DELETE only, so
            # the old PUT arm was unreachable dead code. Writes = POST + an
            # explicit action; delete gets a real, guarded lifecycle.
            _maction = str(data.get("action", "")).strip()
            if _maction not in ("update", "delete"):
                return self._json(400, {"error": "action must be 'update' or 'delete'"})
            _cred = self.headers.get("X-Hub-Token", "")
            _p, _err = hublib.verify_token(BOOKING_KEY, _cred, "list", single_use=False) if _cred \
                else (None, "missing X-Hub-Token")
            if _p:
                _p, _err = _gen_check(_p)
            if not _p:
                return self._json(401, {"error": _err or "invalid list token"})
            with LOCK:
                if _m.get("owner") != _p["sub"]:
                    return self._json(403, {"error": "not your merchant"})
                if _maction == "delete":
                    _attached = sum(1 for l in LISTINGS
                                    if l.get("merchant") == _mslug and not l.get("archived"))
                    if _attached:
                        return self._json(409, {"error": f"{_attached} active listing(s) still attached",
                            "hint": "detach (manage detach_merchant) or archive them first"})
                    del MERCHANTS[_mslug]
                    for _cid in [c for c, cv in CATALOGS.items() if cv.get("merchant") == _mslug]:
                        del CATALOGS[_cid]
                    _persist_locked()
                    return self._json(200, {"ok": True, "deleted": _mslug})
                # action == "update": bounded field walls (owner verified above)
                for _k, _wall in (("name", 80), ("description", 500)):
                    if _k in data:
                        _m[_k] = str(data[_k]).strip()[:_wall]
                if "locations" in data:
                    _cl = []
                    locs = data.get("locations") or []
                    if not isinstance(locs, list) or len(locs) > 10:
                        return self._json(400, {"error": "locations must be a list (max 10)"})
                    for _lo in locs:
                        if not isinstance(_lo, dict):
                            return self._json(400, {"error": "locations entries must be objects"})
                        _cl.append({"city": str(_lo.get("city", ""))[:60],
                                    "address": str(_lo.get("address", ""))[:120]})
                    _m["locations"] = _cl
                if "fulfillment" in data:
                    ful = data.get("fulfillment") or []
                    if isinstance(ful, str):
                        ful = [ful]
                    if not isinstance(ful, list) or any(f not in _MERCH_FULFILL for f in ful):
                        return self._json(400, {"error": f"fulfillment must be a list of {_MERCH_FULFILL}"})
                    _m["fulfillment"] = ful
                if "promos" in data:
                    promos = data.get("promos") or []
                    if not isinstance(promos, list) or len(promos) > 5:
                        return self._json(400, {"error": "promos must be a list (max 5)"})
                    _m["promos"] = [{"label": str(_pr.get("label", ""))[:80],
                                      "detail": str(_pr.get("detail", ""))[:200]} for _pr in promos
                                     if isinstance(_pr, dict)]
                _persist_locked()
                return self._json(200, {"ok": True, "merchant": _pub_merchant(_m)})
        if path == "/catalogs" or path.startswith("/catalogs/"):
            # CATALOGS P2 (owner GO): versioned catalog trees owned by a
            # merchant (restored: post-tail surgery had swallowed this block).
            # POST creates v1; replace bumps version and REQUIRES a content
            # change (same hash = honest 409). Items never appear in
            # /listings or the feed - they surface via /search catalog_items
            # and the merchant page (leakage guard, spec C-CAT law).
            _crid = path[len("/catalogs"):].lstrip("/")
            _cred = self.headers.get("X-Hub-Token", "")
            _p, _err = hublib.verify_token(BOOKING_KEY, _cred, "list", single_use=False) if _cred \
                else (None, "missing X-Hub-Token")
            if _p:
                _p, _err = _gen_check(_p)
            if not _p:
                return self._json(401, {"error": _err or "invalid list token"})
            with LOCK:
                # H7: every catalog write persists to disk - backstopped like
                # every other mutating route (per-source fixed window).
                if not _auth_allow("create", _source_of(self)):
                    return self._json(429, {"error": "catalog write rate limit reached"})
            if path == "/catalogs":
                mslug = str(data.get("merchant", "")).strip().lower()
                tree = data.get("tree")
                with LOCK:
                    _m = MERCHANTS.get(mslug)
                    if not _m:
                        return self._json(400, {"error": f"unknown merchant: {mslug}"})
                    if _m.get("owner") != _p["sub"]:
                        return self._json(403, {"error": "you don't own that merchant"})
                    if any(c.get("merchant") == mslug for c in CATALOGS.values()):
                        return self._json(409, {"error": "merchant already has a catalog (use /catalogs/<id>/replace)"})
                if not isinstance(tree, dict):
                    return self._json(400, {"error": "tree must be an object"})
                def _tv(node, d=0):
                    if d > 3:
                        return "tree deeper than 3 levels"
                    if not isinstance(node, dict):
                        return "tree nodes must be objects"
                    for it in (node.get("items") or []):
                        if not isinstance(it, dict) or not str(it.get("title", "")).strip():
                            return "every item needs a title"
                        if "price" in it:
                            try:
                                float(it["price"])
                            except (TypeError, ValueError):
                                return "item price must be a number"
                        for ch in (node.get("children") or []):
                            _e = _tv(ch, d + 1)
                            if _e:
                                return _e
                    return None
                _terr = _tv(tree)
                if _terr:
                    return self._json(400, {"error": _terr})
                _h = _catalog_hash(tree)
                with LOCK:
                    _n = ID_COUNTERS.get("cat", 0) + 1
                    ID_COUNTERS["cat"] = _n
                    cid = f"cat-{_n}"
                    CATALOGS[cid] = {"id": cid, "merchant": mslug, "version": 1,
                        "content_hash": _h, "tree": tree, "created": time.time()}
                    _persist_locked()
                return self._json(201, {"ok": True, "id": cid, "version": 1, "content_hash": _h})
            m = re.fullmatch(r"([^/]+)/replace", _crid)
            if m:
                cid = m.group(1)
                tree = data.get("tree")
                with LOCK:
                    c = CATALOGS.get(cid)
                    if not c:
                        return self._json(404, {"error": f"no catalog {cid}"})
                    _m = MERCHANTS.get(c["merchant"])
                    if not _m or _m.get("owner") != _p["sub"]:
                        return self._json(403, {"error": "not your catalog"})
                if not isinstance(tree, dict):
                    return self._json(400, {"error": "tree must be an object"})
                _h = _catalog_hash(tree)
                with LOCK:
                    if c["content_hash"] == _h:
                        return self._json(409, {"error": "no content change (same hash)",
                            "version": c["version"], "content_hash": _h})
                    c["tree"] = tree
                    c["content_hash"] = _h
                    c["version"] = int(c.get("version", 1)) + 1
                    _persist_locked()
                return self._json(200, {"ok": True, "id": cid, "version": c["version"], "content_hash": _h})
            return self._json(405, {"error": "use GET for catalog reads"})

        if path == "/listing/draft":
            # Phase 2 paste-a-flyer: free text -> PREFILLED DRAFT (never
            # creates). Token-gated like creation (write-assist surface, not
            # anonymous parsing); deterministic extraction (enrich.py), no AI
            # in v1; input bounded. The organizer confirms every field before
            # any POST /listings — the draft is advice, never authority.
            cred = self.headers.get("X-Hub-Token", "")
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred \
                else (None, "missing X-Hub-Token")
            if p:
                p, err = _gen_check(p)
            if not p:
                return self._json(401, {"error": err or "invalid list token",
                    "hint": "same list token as POST /listings"})
            text = data.get("text") if isinstance(data, dict) else None
            url = data.get("url") if isinstance(data, dict) else None
            if isinstance(url, str) and url.strip():
                # Import ladder v1 (owner GO 2026-11-12, spec-import-and-badges
                # §3): fetch an EXISTING page (SSRF-walled in enrich.py),
                # JSON-LD -> meta -> text ladder, DRAFT only — advice, never
                # authority. Rate wall: fetching remote pages is expensive
                # and untrusted input.
                if text and text.strip():
                    return self._json(400, {"error": "send text OR url, not both"})
                url = url.strip()
                if not url.lower().startswith(("http://", "https://")) or len(url) > 2048:
                    return self._json(400, {"error": "url must be http(s) and <= 2048 chars"})
                if not _auth_allow("draft", _source_of(self)):
                    return self._json(429, {"error": "import rate limit reached, retry later"})
                _got = enrich.draft_from_url(url)
                if not _got:
                    # fail-open law: honest degrade to the text flow, no fake draft
                    return self._json(422, {"error": "could not read that page",
                        "hint": "paste the event text instead: {\"text\": \"...\"}"})
                return self._json(200, {"ok": True, "draft": _got["draft"],
                    "engine": _got["engine"], "import_source": "url", "source_url": url,
                    "needs_confirm": sorted(k for k in ("date", "price") if k in _got["draft"]),
                    "note": "prefilled draft only — confirm DATE and PRICE, then POST /listings to create"})
            if not isinstance(text, str) or not text.strip():
                return self._json(400, {"error": "text must be a nonempty string"})
            if len(text) > 20000:
                return self._json(400, {"error": "text too long (max 20000 chars)"})
            # v2: LLM-assisted when the enrichment chain is live (owner GO
            # 2026-11-08); deterministic regex stays as the fail-open fallback.
            # The response names its engine + model — advice, never authority.
            _smart = enrich.draft_from_text_smart(text)
            _resp = {"ok": True, "draft": _smart["draft"], "engine": _smart["engine"]}
            if _smart.get("model"):
                _resp["model"] = _smart["model"]
            _resp["note"] = "prefilled draft only — review every field, then POST /listings to create"
            return self._json(200, _resp)
        if path == "/listings":
            cred = self.headers.get("X-Hub-Token", "")  # I2: list token required
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred \
                else (None, "missing X-Hub-Token")
            if p:
                p, err = _gen_check(p)  # B1
            if not p:
                return self._json(401, {"error": err or "invalid list token",
                    "hint": "POST /access {agent: '<your-agent>', acts: ['list']} then send token as X-Hub-Token"})
            # H5: per-source backstop — the per-principal cap (3) is bypassable
            # via freely-minted principals pre-personhood; flooding counts here
            with LOCK:
                if not _auth_allow("create", _source_of(self)):
                    return self._json(429, {"error": "listing creation rate limit reached for your source, retry later"})
            v = data.get("vertical")
            if v not in VERTICAL_SCHEMAS:
                return self._json(400, {"error": f"unknown vertical: {v}",
                    "known": list(VERTICAL_SCHEMAS)})
            schema = VERTICAL_SCHEMAS[v]
            # SEEK (owner GO 2026-11-12): cross-vertical seek fields, handled
            # BEFORE the required-check so the pay alias satisfies price.
            # role is structural (the schema-derived manage-edit allowlist can
            # never touch it). Wording law: seeks say "pay", never "price".
            _role = str(data.get("role", "offer")).strip().lower()
            if _role not in ("offer", "seek"):
                return self._json(400, {"error": "role must be offer or seek"})
            data["role"] = _role
            if "pay" in data:
                if _role != "seek":
                    return self._json(400, {"error": "pay is a seek field; offers set price"})
                if data.get("price") is not None:
                    return self._json(400, {"error": "set pay or price, not both"})
                try:
                    _pay = float(data.pop("pay"))
                except (TypeError, ValueError):
                    return self._json(400, {"error": "pay must be a number"})
                if not (_pay >= 0 and _pay == _pay and _pay not in (float("inf"), float("-inf"))):
                    return self._json(400, {"error": "pay must be a nonnegative finite number"})
                data["price"] = _pay
            if _role == "seek":
                _am = str(data.get("application_mode", "join")).strip().lower()
                if _am not in SEEK_JOB_ROLES:
                    return self._json(400, {"error": "application_mode must be join or vetted"})
                data["application_mode"] = _am
                if data.get("require_verified_worker") is not None:
                    if not isinstance(data["require_verified_worker"], bool):
                        return self._json(400, {"error": "require_verified_worker must be a boolean"})
                else:
                    data.pop("require_verified_worker", None)
            else:
                for _sf in ("application_mode", "require_verified_worker"):
                    data.pop(_sf, None)
            missing = [f for f in schema["required"] if f not in data]
            if missing and _role == "seek" and missing == ["price"]:
                return self._json(400, {"error": "missing fields: pay (the amount the filler receives; 0 = free join)"})
            if missing: return self._json(400, {"error": f"missing fields: {missing}"})
            # H17: required string fields must be nonempty and bounded
            for f in schema["required"]:
                if isinstance(data[f], str):
                    _sv = data[f].strip()
                    if not _sv:
                        return self._json(400, {"error": f"{f} cannot be empty"})
                    data[f] = _sv[:80]
            # I1: reject reserved fields, validate types, strip unknowns
            reserved = [k for k in data if k in RESERVED_LISTING_FIELDS and k != "available"]
            if reserved: return self._json(400, {"error": f"reserved fields: {reserved}"})
            try:
                price = float(data["price"])
                if not (price >= 0 and price == price and price not in (float("inf"), float("-inf"))):
                    raise ValueError("price must be a nonnegative finite number")
                data["price"] = price
                # H15: per-field validation is SCHEMA DATA (field_types), not code —
                # events capacity/date, services duration_minutes, any future field.
                for _f, _t in (schema.get("field_types") or {}).items():
                    if _f not in data:
                        continue
                    if _t == "positive_int":
                        # H18: clean message — never leak Python exception text
                        try:
                            _iv = int(data[_f])
                        except (TypeError, ValueError):
                            return self._json(400, {"error": f"invalid field: {_f} must be an integer"})
                        if _iv <= 0:
                            return self._json(400, {"error": f"invalid field: {_f} must be positive"})
                        data[_f] = _iv
                    elif _t == "nonempty" and not str(data[_f]).strip():
                        return self._json(400, {"error": f"{_f} required for {v}"})
                    elif _t == "time_hhmm":
                        # owner call 2026-09-23: optional start time (HH:MM, 24h)
                        _tm = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$").match(str(data[_f]).strip())
                        if not _tm:
                            return self._json(400, {"error": f"invalid field: {_f} must be HH:MM (24h)"})
                        data[_f] = str(data[_f]).strip()
                    elif _t == "float_latlon":
                        # D1 2026-10-15: lat/lon floats for client-side distance
                        try:
                            _fv = float(data[_f])
                        except (TypeError, ValueError):
                            return self._json(400, {"error": f"invalid field: {_f} must be a number"})
                        if not (-90.0 <= _fv <= 90.0 if _f == "lat" else -180.0 <= _fv <= 180.0):
                            return self._json(400, {"error": f"invalid field: {_f} out of range"})
                        data[_f] = round(_fv, 6)
            except (TypeError, ValueError) as ex:
                return self._json(400, {"error": f"invalid field: {ex}"})
            # C12: payment terms (SPEC §19) — validated object or per-vertical
            # default; stored on the listing so EVERY public payload shows the
            # real terms buyers will accept at booking time.
            pt_raw = data.pop("payment_terms", None)
            _terms, pterr = _normalize_payment_terms(pt_raw, price, v)
            if pterr:
                return self._json(400, {"error": pterr})
            data["payment_terms"] = _terms if _terms is not None else _default_payment_terms(v)
            # EverList taxonomy: category from controlled vocab (optional but
            # must be valid if given); tags free-form but normalized+bounded.
            if "category" in data and data["category"] is not None:
                cat = str(data["category"]).strip().lower()
                if cat not in schema["categories"]:
                    return self._json(400, {"error": f"unknown category: {cat}",
                        "known": schema["categories"]})
                data["category"] = cat
            else:
                data.pop("category", None)
            if "tags" in data and data.get("tags") is not None:
                try:
                    data["tags"] = normalize_tags(data["tags"])
                except ValueError as ex:
                    return self._json(400, {"error": str(ex)})
            else:
                data.pop("tags", None)
            # B3c-rich: optional url (http/https, bounded) + description cap
            if data.get("url") is not None:
                u2 = str(data["url"]).strip()
                if not (u2.startswith("http://") or u2.startswith("https://")) or len(u2) > 300:
                    return self._json(400, {"error": "url must start with http:// or https:// (max 300 chars)"})
                data["url"] = u2
            else:
                data.pop("url", None)
            if data.get("description") is not None:
                desc = str(data["description"]).strip()
                if len(desc) > 500:
                    return self._json(400, {"error": "description too long (max 500 chars)"})
                data["description"] = desc
            else:
                data.pop("description", None)
            # S6-L1: optional merchant receive address for the instant rail - the
            # anchor the self-pay wall compares x402 payers against.
            if data.get("receive_addr") is not None:
                _rx = str(data["receive_addr"]).strip().lower()
                if not re.fullmatch(r"0x[a-f0-9]{40}", _rx):
                    return self._json(400, {"error": "receive_addr must be a 0x + 40-hex EVM address"})
                data["receive_addr"] = _rx
            else:
                data.pop("receive_addr", None)
            # C11: optional verified-buyer gate (SPEC section 22) — booking restricted
            # to Tier-2-verified accounts (server-side proof). Must be a real boolean.
            if data.get("require_verified_buyer") is not None:
                if not isinstance(data["require_verified_buyer"], bool):
                    return self._json(400, {"error": "require_verified_buyer must be a boolean"})
            else:
                data.pop("require_verified_buyer", None)
            # S8: title/location intake hygiene — same discipline as the edit
            # path. These fields flow into SSR pages, email subjects, ICS
            # SUMMARY/LOCATION, JSON-LD and chat frames; strip, cap, and
            # reject control chars/newlines at the door.
            t2 = str(data.get("title", "")).strip()
            if not t2:
                return self._json(400, {"error": "title must not be empty"})
            if len(t2) > 80:
                return self._json(400, {"error": "title too long (max 80 chars)"})
            if re.search(r"[\x00-\x1f\x7f\u202a-\u202e]", t2):
                return self._json(400, {"error": "title must not contain control characters or newlines"})
            data["title"] = t2
            if data.get("location") is not None:
                loc2 = str(data["location"]).strip()
                if len(loc2) > 120:
                    return self._json(400, {"error": "location too long (max 120 chars)"})
                if re.search(r"[\x00-\x1f\x7f\u202a-\u202e]", loc2):
                    return self._json(400, {"error": "location must not contain control characters or newlines"})
                data["location"] = loc2
            # CATALOGS P1: merchant attach - slug must exist and be OWNED by
            # the creating principal (a listing can never hang off someone
            # else's merchant profile).
            if data.get("merchant") is not None:
                _ms = str(data["merchant"]).strip().lower()
                with LOCK:
                    _mown = (MERCHANTS.get(_ms) or {}).get("owner")
                if not _mown:
                    return self._json(400, {"error": f"unknown merchant: {_ms}"})
                if _mown != p["sub"]:
                    return self._json(403, {"error": "you don't own that merchant"})
                data["merchant"] = _ms
            else:
                data.pop("merchant", None)
            allowed = set(schema["required"]) | set(schema.get("optional", [])) | {"vertical", "payment_terms", "visibility", "receive_addr", "require_verified_buyer", "series", "role", "application_mode", "require_verified_worker", "merchant"}
            data = {k: d for k, d in data.items() if k in allowed}  # drop unknowns (payment_terms already server-normalized above)
            # RTF2: create-path hygiene for the remaining text fields — title
            # and location keep their stricter wall above (newlines banned);
            # everything else gets controls/bidi stripped while long-form
            # fields (description) keep legitimate newlines.
            for _k, _v in list(data.items()):
                if isinstance(_v, str) and _k not in ("title", "location"):
                    data[_k] = _BAD_CHARS_RE.sub("", _v)
                elif isinstance(_v, list):
                    data[_k] = [_BAD_CHARS_RE.sub("", x) if isinstance(x, str) else x for x in _v]
            # P2: private deals — 'listed but not public'. visibility=private keeps a
            # listing out of search/suggest/browse; access needs the one-time claim
            # code (or owner auth). Everyone else gets the same answer as unknown (404).
            _vis = str(data.get("visibility", "public")).strip().lower()
            if _vis not in ("public", "private"):
                return self._json(400, {"error": "visibility must be 'public' or 'private'"})
            data["visibility"] = _vis
            # Phase 3 marketplace (owner GO 2026-11-07): recurring series —
            # one POST fans a dated template into bounded child listings
            # (2..12) sharing a server-owned series_id. series is
            # {"every_days": int, "count": int} on the BASE request only;
            # children are plain dated listings (never carry "series" —
            # nested fan-out is structurally impossible).
            _series_every, _series_n, _sid, _series_dates = None, 1, None, []
            _series_child_ids = []
            _series_req = data.pop("series", None)
            if _series_req is not None:
                if (not isinstance(_series_req, dict)
                        or not isinstance(_series_req.get("every_days"), int)
                        or not (1 <= _series_req["every_days"] <= 366)
                        or not isinstance(_series_req.get("count"), int)
                        or not (2 <= _series_req["count"] <= 12)):
                    return self._json(400, {"error": "series must be {every_days: int 1..366, count: int 2..12}"})
                if not str(data.get("date", "")).strip():
                    return self._json(400, {"error": "series requires a base date on the listing"})
                _series_every, _series_n = _series_req["every_days"], _series_req["count"]
            # Phase 2 find-quality: AI write-side compression — runs OUTSIDE the
            # LOCK (a live-mode HTTP call must never hold the hub lock) and
            # AFTER client-field walls (reserved/unknown rejection above), so
            # _enrich_* are server-owned from birth. enrich.extract NEVER
            # raises (fail-open law): no key/timeout/garbage -> None -> the
            # listing indexes on raw text exactly as before.
            _enr = enrich.extract(data.get("title", ""), data.get("description", ""), data.get("tags"))
            if _enr:
                data["_enrich_kw"] = " ".join(str(k) for k in _enr.get("kw", []))[:300]
                data["_enrich"] = {"mode": _enr.get("mode"), "model": _enr.get("model"),
                                    "ts": _enr.get("ts"), "n_kw": len(_enr.get("kw", []))}
            with LOCK:
                # S7-2: duplicate detection — same principal + normalized title
                # + same date + same location as one of their ACTIVE listings.
                # NEVER cross-principal: distinct owners may list similar events.
                # Checked BEFORE the cap: a duplicate must surface as duplicate
                # (actionable: existing id), not as a generic cap 409.
                _s7_norm = " ".join(str(data.get("title", "")).casefold().split())[:80]
                _s7_date = str(data.get("date", "")).strip()
                _s7_loc = str(data.get("location", "")).strip().casefold()
                _s7_admin = p.get("act") == "confirm"
                if not _s7_admin:
                    for l in LISTINGS:
                        if l.get("owner") != p["sub"] or l.get("archived"):
                            continue
                        if " ".join(str(l.get("title", "")).casefold().split())[:80] != _s7_norm:
                            continue
                        if _s7_date and str(l.get("date", "")).strip() != _s7_date:
                            continue
                        if _s7_loc and str(l.get("location", "")).strip().casefold() != _s7_loc:
                            continue
                        return self._json(409, {"error": f"duplicate of your listing {l['id']}",
                            "existing": l["id"]})
                    # S7-1: active-listing soft cap (env HUB_LISTING_CAP, default 20) —
                    # raises the cost of flooding via freely-minted principals
                    # (H5 admits the bypass; S7 makes it economic, not free).
                    # Admin authority (act 'confirm') exempt so seeded demos never break.
                    _s7_cap = int(os.environ.get("HUB_LISTING_CAP", "20") or 20)
                    if _s7_cap > 0:
                        _s7_active = [l for l in LISTINGS
                                      if l.get("owner") == p["sub"] and not l.get("archived")]
                        if len(_s7_active) >= _s7_cap:
                            return self._json(409, {"error": f"listing cap reached ({_s7_cap} active). Archive one to free a slot",
                                "cap": _s7_cap, "active": len(_s7_active)})
                _pref = v[:4]
                _n = ID_COUNTERS.get(_pref, 0)
                if not _n:  # seed once from legacy state (pre-counter listings)
                    _nums = [int(l["id"].rsplit("-", 1)[1]) for l in LISTINGS
                             if l["id"].startswith(_pref + "-") and l["id"].rsplit("-", 1)[1].isdigit()]
                    _n = max(_nums) if _nums else 0
                _n += 1
                # Incident 2026-10-19 layer 2: a stale counter (behind real
                # listing ids) must never mint an existing id — duplicates in
                # RAM would crash every later persist on UNIQUE(listings.id).
                _existing = {str(l["id"]) for l in LISTINGS}
                while f"{_pref}-{_n}" in _existing:
                    _n += 1
                ID_COUNTERS[_pref] = _n
                lid = f"{_pref}-{_n}"  # monotonic: never reused, even after deletes
                data["id"] = lid
                data["owner"] = p["sub"]   # SERVER-OWNED: authenticated principal, never client-set (anti-spoof for /orders)
                manage_code = "mgr-" + secrets.token_hex(8)   # ownership secret (64-bit): shown ONCE, stored as sha256 only — NEVER echoed (H9 _pub_listing)
                data["manage_code_hash"] = hashlib.sha256(manage_code.encode()).hexdigest()
                claim_code = ""
                if data["visibility"] == "private":
                    claim_code = "pvt-" + secrets.token_hex(8)  # shown ONCE, sha256-stored (manage_code pattern)
                    data["claim_code_hash"] = hashlib.sha256(claim_code.encode()).hexdigest()
                else:
                    data.pop("claim_code_hash", None)
                if schema.get("tracks_capacity"):
                    data["registered"] = 0   # server-initialized counter
                    data["available"] = True  # default; SOLD OUT derives from registered>=capacity at booking time
                else:
                    data["available"] = bool(data.get("available", True))
                # Phase 3: series fan-out — the CAP check above sized one
                # listing; re-check atomically for the whole series
                # (all-or-nothing: a mid-series cap trip creates NOTHING).
                if _series_n > 1:
                    _cap_now = int(os.environ.get("HUB_LISTING_CAP", "20") or 20)
                    _fam_active = [l for l in LISTINGS
                                   if l.get("owner") == p["sub"] and not l.get("archived")]
                    if _cap_now > 0 and len(_fam_active) + _series_n > _cap_now:
                        return self._json(409, {"error": f"listing cap reached for a {_series_n}-listing series ({_cap_now} active). Free slots first",
                            "cap": _cap_now, "active": len(_fam_active)})
                    from datetime import date as _dtt, timedelta as _td
                    try:
                        _base_d = _dtt.fromisoformat(str(data["date"]).strip())
                    except ValueError:
                        return self._json(400, {"error": "series base date must be YYYY-MM-DD"})
                    _sid = "series-" + secrets.token_hex(6)
                    data["series_id"] = _sid
                    for _i in range(1, _series_n):
                        _ch = dict(data)
                        _ch.pop("series", None)
                        _ch["date"] = (_base_d + _td(days=_series_every * _i)).isoformat()
                        _cn = ID_COUNTERS.get(_pref, 0) + 1
                        ID_COUNTERS[_pref] = _cn
                        _ch["id"] = f"{_pref}-{_cn}"
                        # one manage code governs the whole series (shown once)
                        LISTINGS.append(_ch)
                        _series_dates.append(_ch["date"])
                        _series_child_ids.append(_ch["id"])
                    _series_dates.insert(0, str(data["date"]))
                LISTINGS.append(data)
                _persist_locked()
            _resp = {"ok": True, "id": lid, "manage_code": manage_code,
                "manage_note": "shown ONCE — required to edit or delete this listing; store it now"}
            if _sid:
                _resp["series"] = {"id": _sid, "created": _series_n, "dates": _series_dates,
                    "note": "one manage code governs the whole series; archive_series/delete_series act on every date"}
            if claim_code:
                _resp["claim_code"] = claim_code
                _resp["claim_note"] = "shown ONCE — the only key to this private deal; without it the deal is invisible"
                _resp["share"] = f"send id {lid} + this claim code; any EverList agent views/books with them"
            # Discovery batch 2026-11-12: IndexNow ping on public listing create.
            # Fire-and-forget daemon thread, fail-open (indexing is best-effort,
            # never a create-latency or create-success dependency); OFF unless
            # EVERLIST_INDEXNOW_PING=1 so tests stay hermetic (no outbound net).
            if os.environ.get("EVERLIST_INDEXNOW_PING") == "1" and not claim_code:
                try:
                    _pub = os.environ.get("EVERLIST_PUBLIC_URL", "https://everlist.network").rstrip("/")
                    _inkey = "8465f3525dbe1925d3f13a5ee36b943e"  # public proof-of-domain key (pages.py INDEXNOW_KEY)
                    _ping_urls = [_pub + "/l/" + lid] + [_pub + "/l/" + _cid for _cid in _series_child_ids]
                    def _in_ping(urls=_ping_urls, key=_inkey, pub=_pub):
                        try:
                            _pd = json.dumps({"host": "everlist.network", "key": key,
                                              "keyLocation": pub + "/.well-known/" + key + ".txt",
                                              "urlList": urls}).encode("utf-8")
                            _preq = urllib.request.Request(
                                "https://api.indexnow.org/indexnow", data=_pd,
                                headers={"Content-Type": "application/json; charset=utf-8"}, method="POST")
                            urllib.request.urlopen(_preq, timeout=6)
                        except Exception:
                            pass  # fail-open: indexing hint only, never a create failure
                    threading.Thread(target=_in_ping, daemon=True).start()
                except Exception:
                    pass
            return self._json(201, _resp)
        if path.startswith("/listings/") and path.endswith("/image"):
            # B2 listing photo: ownership law = /manage (acct- owner OR
            # manage_code), image hygiene = /branding/image (magic-byte sniff,
            # SVG refused, decoded cap). Stored as a data URL on the listing;
            # the public serializer keeps it, so every consumer face renders
            # it same-origin (CSP img-src data:). Upload-only: create/edit
            # can never set it (reserved field).
            lid = path[len("/listings/"):-len("/image")]
            cred = self.headers.get("X-Hub-Token", "")
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred \
                else (None, "missing X-Hub-Token")
            if p:
                p, err = _gen_check(p)  # B1: stale tokens never prove identity
            if not p:
                return self._json(401, {"error": err or "missing X-Hub-Token",
                    "hint": "login via POST /accounts/login as the owning account, or send a list token + manage_code"})
            principal = p["sub"]
            clearing = data.get("clear") is True
            du = str(data.get("data_url", ""))
            m = None
            if not clearing:
                m = re.match(r"^data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=]+)$", du)
                if not m:
                    return self._json(400, {"error": "data_url must be data:image/png|jpeg|webp;base64,... (SVG refused); clear with {clear:true}"})
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "image rate limit reached for your source, retry later"})
                listing = next((l for l in LISTINGS if l["id"] == lid), None)
                if not listing:
                    return self._json(404, {"error": f"no listing {lid}"})
                is_owner = principal.startswith("acct-") and principal == listing.get("owner")
                if not is_owner:
                    code = str(data.get("manage_code", "")).strip()
                    if not code or not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(),
                                                           str(listing.get("manage_code_hash", ""))):
                        return self._json(403, {"error": "invalid manage_code for this listing (or login as the owning account)"})
                if clearing:
                    listing.pop("image", None)
                    _persist_locked()
                    return self._json(200, {"ok": True, "id": lid, "cleared": True})
            blob = base64.b64decode(m.group(2), validate=True)
            if len(blob) > LISTING_IMG_CAP:
                return self._json(400, {"error": "listing image too large: %d bytes (max %d)" % (len(blob), LISTING_IMG_CAP)})
            PNGSIG = bytes([0x89]) + b"PNG" + bytes([0x0d, 0x0a, 0x1a, 0x0a])
            JPEGSIG = bytes([0xff, 0xd8, 0xff])
            if blob[:8] == PNGSIG:
                mime = "image/png"
            elif blob[:3] == JPEGSIG:
                mime = "image/jpeg"
            elif blob[:4] == b"RIFF" and blob[8:12] == b"WEBP":
                mime = "image/webp"
            else:
                return self._json(400, {"error": "file content is not PNG/JPEG/WebP (magic-byte sniff failed)"})
            with LOCK:
                listing["image"] = "data:" + mime + ";base64," + m.group(2)
                _persist_locked()
            return self._json(200, {"ok": True, "id": lid, "bytes": len(blob), "mime": mime})
        if path.startswith("/listings/") and "/applications" in path:
            # SEEK applications (owner GO 2026-11-12): one action-route, B3c
            # owner proof (list token of the owning acct- principal OR the
            # listing manage_code); withdraw is the FILLER's own action with
            # their book/list token. Accept replays the stored booking fields
            # through the SHARED _book_core engine via an internally minted
            # book token (checkout-session precedent: zero drift from /book
            # gates). Paid seeks record the S3 direction flip on the booking.
            m = re.fullmatch(r"/listings/([^/]+)/applications(?:/([^/]+))?", path)
            if not m:
                return self._json(404, {"error": "no route"})
            lid, aid_in = m.group(1), m.group(2)
            action = str(data.get("action", "list")).strip().lower()
            if action not in ("list", "accept", "decline", "withdraw"):
                return self._json(400, {"error": "action must be list, accept, decline or withdraw"})
            cred = self.headers.get("X-Hub-Token", "")
            # applicants authenticate with BOOK tokens (POST /book created
            # the application); owners arrive with list tokens - accept either.
            p, err = (None, "missing X-Hub-Token")
            if cred:
                p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                if not p:
                    p, err = hublib.verify_token(BOOKING_KEY, cred, "book", single_use=False)
            if p:
                p, err = _gen_check(p)  # B1
            if not p:
                return self._json(401, {"error": err or "invalid list token"})
            principal = p["sub"]
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "manage rate limit reached for your source, retry later"})
                listing = next((l for l in LISTINGS if l["id"] == lid), None)
                if not listing:
                    return self._json(404, {"error": f"no listing {lid}"})
                is_owner = principal.startswith("acct-") and principal == listing.get("owner")
                _code_ok = False
                if not is_owner:
                    code = str(data.get("manage_code", "")).strip()
                    _code_ok = bool(code) and hmac.compare_digest(
                        hashlib.sha256(code.encode()).hexdigest(),
                        str(listing.get("manage_code_hash", "")))
                    # manage_code proves the OWNER for list/accept/decline;
                    # withdraw is the FILLER's action - authorized by the
                    # app.filler match below, no owner proof needed.
                    if not _code_ok and action != "withdraw":
                        return self._json(403, {"error": "invalid credentials for this listing's applications"})
            if action == "list":
                with LOCK:
                    apps = [a for a in APPLICATIONS.values() if a["listing_id"] == lid]
                    apps.sort(key=lambda a: a["created"])
                    out = [{"id": a["id"], "filler_ref": a["filler"][:4] + "…",
                            "status": a["status"], "created": a["created"],
                            "message": a.get("message")} for a in apps]
                return self._json(200, {"listing_id": lid, "applications": out,
                    "note": "filler_ref is a truncated principal - full identity stays booking-private until accept"})
            aid = str(data.get("application_id", aid_in or "")).strip()
            with LOCK:
                app = APPLICATIONS.get(aid)
                if not app or app["listing_id"] != lid:
                    return self._json(404, {"error": f"no application {aid} on {lid}"})
            if action == "withdraw":
                if app["filler"] != principal:
                    return self._json(403, {"error": "only the applicant can withdraw"})
                with LOCK:
                    if app["status"] != "pending":
                        return self._json(409, {"error": f"application already {app['status']}"})
                    app["status"] = "withdrawn"; app["decided_ts"] = time.time()
                    _persist_locked()
                return self._json(200, {"ok": True, "application_id": aid, "status": "withdrawn"})
            # owner decisions below (acct ownership or manage_code proof)
            if not (is_owner or _code_ok):
                return self._json(403, {"error": "only the seek owner can accept or decline"})
            if action == "decline":
                with LOCK:
                    if app["status"] != "pending":
                        return self._json(409, {"error": f"application already {app['status']}"})
                    app["status"] = "declined"; app["decided_ts"] = time.time()
                    _persist_locked()
                return self._json(200, {"ok": True, "application_id": aid, "status": "declined"})
            # ACCEPT: capacity re-checked INSIDE the lock before minting;
            # _book_core runs OUTSIDE the lock (it takes the lock itself).
            with LOCK:
                if app["status"] != "pending":
                    return self._json(409, {"error": f"application already {app['status']}"})
                if listing.get("archived"):
                    return self._json(409, {"error": "listing archived - not bookable"})
                sch = VERTICAL_SCHEMAS[listing["vertical"]]
                if sch.get("tracks_capacity"):
                    cap = listing.get("capacity")
                    if cap is not None and listing.get("registered", 0) + 1 > int(cap):
                        return self._json(409, {"error": "seek slot already filled",
                            "note": "pending applications never block capacity; first accept wins"})
                filler = app["filler"]
                tok = hublib.mint_token(BOOKING_KEY, "book", filler, ttl=120)
            bdata = dict(app.get("book_fields") or {})
            bdata["listing_id"] = lid
            # S3 (owner GO): on paid seeks the SEEKER funds at accept -
            # payment evidence rides THIS action into _book_core (same walls
            # as /book; the escrow rail validates verbatim). No evidence on a
            # paid seek = the booking engine's honest payment error.
            if data.get("escrow_ref") is not None:
                bdata["escrow_ref"] = data.get("escrow_ref")
            bcode, bbody, beh = self._book_core(bdata, token=tok, _accept_replay=True)
            if bcode != 201:
                return self._json(bcode, bbody, extra_headers=beh)
            bid = str(bbody.get("id") or bbody.get("bid") or "")
            with LOCK:
                app["status"] = "accepted"; app["decided_ts"] = time.time(); app["bid"] = bid
                bk = next((b for b in BOOKINGS if b["id"] == bid), None)
                if bk is not None:
                    bk["application_id"] = aid
                    if listing.get("role") == "seek":
                        # S3 direction flip (owner GO): on paid seeks the money
                        # flows SEEKER (listing owner) -> FILLER (the accepted
                        # applicant). The escrow rail itself is untouched.
                        bk["money_direction"] = "seeker_to_filler"
                        bk["payee_principal"] = filler
                    # decline other pending applications honestly: slot filled
                    for other in APPLICATIONS.values():
                        if other["listing_id"] == lid and other["id"] != aid and other["status"] == "pending":
                            other["status"] = "declined"; other["decided_ts"] = time.time()
                            other["note"] = "slot filled"
                _persist_locked()
            return self._json(201, {"ok": True, "application_id": aid, "status": "accepted",
                "booking_id": bid, "money_direction": "seeker_to_filler" if listing.get("role") == "seek" else None})
        if path.startswith("/listings/") and path.endswith("/manage"):
            # B3c-ownership: manage code OR logged-in account ownership proves control
            lid = path[len("/listings/"):-len("/manage")]
            code = str(data.get("manage_code", "")).strip()
            action = str(data.get("action", "")).strip().lower()
            if action not in ("edit", "delete", "archive", "unarchive", "make_private", "make_public"):
                if action not in ("edit", "delete", "archive", "unarchive", "make_private", "make_public", "archive_series", "delete_series", "attach_merchant", "detach_merchant"):
                    return self._json(400, {"error": "action must be 'edit', 'delete', 'archive', 'unarchive', 'make_private', 'make_public', 'archive_series', 'delete_series', 'attach_merchant' or 'detach_merchant'"})
            cred = self.headers.get("X-Hub-Token", "")
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False) if cred \
                else (None, "missing X-Hub-Token")
            if p:
                p, err = _gen_check(p)  # B1
            if not p:
                return self._json(401, {"error": err or "missing X-Hub-Token",
                    "hint": "login via POST /accounts/login {account_code, agent} to act as your account, or send a list token + manage_code"})
            principal = p["sub"]
            # H5: manage-code brute-force backstop — every attempt counts,
            # wrong-code guesses included
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "manage rate limit reached for your source, retry later"})
            with LOCK:
                listing = next((l for l in LISTINGS if l["id"] == lid), None)
                if not listing:
                    return self._json(404, {"error": f"no listing {lid}"})
                is_owner = principal.startswith("acct-") and principal == listing.get("owner")
                if not is_owner:
                    if not code or not hmac.compare_digest(hashlib.sha256(code.encode()).hexdigest(),
                                                           str(listing.get("manage_code_hash", ""))):
                        return self._json(403, {"error": "invalid manage_code for this listing (or login as the owning account)"})
                active = [b for b in BOOKINGS
                          if b.get("listing_id") == lid and b.get("escrow") in ("HELD", "WAIVED", "DIRECT")]
                if action in ("archive_series", "delete_series"):
                    _sid = listing.get("series_id")
                    if not _sid:
                        return self._json(400, {"error": "listing is not part of a series"})
                    _fam = [l for l in LISTINGS if l.get("series_id") == _sid]
                    for l in _fam:
                        _act2 = [b for b in BOOKINGS
                                 if b.get("listing_id") == l["id"] and b.get("escrow") in ("HELD", "WAIVED", "DIRECT")]
                        if _act2:
                            return self._json(409, {"error": f"series listing {l['id']} has active booking(s); resolve first",
                                "listing": l["id"], "active": len(_act2)})
                    if action == "archive_series":
                        for l in _fam:
                            l["archived"] = True
                        _persist_locked()
                        return self._json(200, {"ok": True, "series": _sid, "archived": len(_fam),
                            "note": "whole series hidden; unarchive any single date to revive it"})
                    for l in _fam:
                        LISTINGS.remove(l)
                    _persist_locked()
                    return self._json(200, {"ok": True, "series": _sid, "deleted": len(_fam)})
                if action == "delete":
                    if active:
                        return self._json(409, {"error": f"listing has {len(active)} active booking(s); resolve (confirm/cancel) first"})
                    LISTINGS.remove(listing)
                    _persist_locked()
                    return self._json(200, {"ok": True, "deleted": lid})
                if action in ("archive", "unarchive"):
                    listing["archived"] = (action == "archive")
                    _persist_locked()
                    note = ("hidden from search; existing bookings stay fulfillable"
                            if listing["archived"] else "visible again")
                    return self._json(200, {"ok": True, "id": lid, "archived": listing["archived"], "note": note})
                if action in ("make_private", "make_public"):
                    # P2: visibility switch. make_private mints a FRESH claim (the old one dies).
                    if action == "make_private":
                        claim_code = "pvt-" + secrets.token_hex(8)
                        listing["visibility"] = "private"
                        listing["claim_code_hash"] = hashlib.sha256(claim_code.encode()).hexdigest()
                        _persist_locked()
                        return self._json(200, {"ok": True, "id": lid, "visibility": "private",
                            "claim_code": claim_code,
                            "note": "new claim code shown ONCE — the previous claim no longer works"})
                    listing["visibility"] = "public"
                    listing.pop("claim_code_hash", None)
                    _persist_locked()
                    return self._json(200, {"ok": True, "id": lid, "visibility": "public",
                        "note": "deal is public: discoverable in search, no claim needed"})
                if action in ("attach_merchant", "detach_merchant"):
                    if action == "detach_merchant":
                        listing.pop("merchant", None)
                        _persist_locked()
                        return self._json(200, {"ok": True, "id": lid, "merchant": None})
                    _ms = str(data.get("merchant", "")).strip().lower()
                    _m = MERCHANTS.get(_ms)
                    if not _m:
                        return self._json(400, {"error": f"unknown merchant: {_ms}"})
                    if _m.get("owner") != listing.get("owner"):
                        return self._json(403, {"error": "merchant belongs to a different owner"})
                    listing["merchant"] = _ms
                    _persist_locked()
                    return self._json(200, {"ok": True, "id": lid, "merchant": _ms})
                # H17: edit allowlist is SCHEMA-DERIVED (base + owner-name fields
                # + the vertical's optional fields, intersected with the
                # vertical's own fields) so services providers can edit
                # provider/duration_minutes and future verticals inherit editing
                _sch = VERTICAL_SCHEMAS[listing["vertical"]]
                _allowed_fields = set(_sch["required"]) | set(_sch.get("optional", []))
                editable = (({"title", "description", "price", "location", "date",
                              "capacity", "category", "tags", "url",
                              "provider", "merchant"}
                             | set(_sch.get("optional", []))) & _allowed_fields)
                changes = {k: data[k] for k in editable if k in data}
                # RTF2: the edit path must meet the SAME intake bar as create —
                # A3 probe proved title edits accepted bidi/CRLF/BEL/ESC and
                # fed the same email/ICS/SSR sinks the create wall protects.
                for _k in ("title", "location"):
                    if _k in changes:
                        _v = str(changes[_k]).strip()
                        if not _v:
                            return self._json(400, {"error": f"{_k} must not be empty"})
                        if len(_v) > (80 if _k == "title" else 120):
                            return self._json(400, {"error": f"{_k} too long"})
                        if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e]", _v):
                            return self._json(400, {"error": f"{_k} must not contain control characters or bidi overrides"})
                        changes[_k] = _v
                for _k, _v in list(changes.items()):
                    if isinstance(_v, str) and _k not in ("title", "location"):
                        # long-form fields keep newlines; controls/bidi stripped
                        changes[_k] = _BAD_CHARS_RE.sub("", _v)
                _pt_edit = "payment_terms" in data  # C12: terms are owner-editable pre-booking; booked bookings keep their snapshot
                _rvb_edit = "require_verified_buyer" in data  # C11: verified-buyer gate is owner-editable pre-booking
                _promo_edit = "promo" in data  # owner-approved 2026-09-30: promo codes, paid listings only
                if not changes and not _pt_edit and not _rvb_edit and not _promo_edit:
                    return self._json(400, {"error": "no editable fields given",
                                            "editable": sorted(editable | {"require_verified_buyer"})})
                if "price" in changes:
                    try:
                        np = float(changes["price"])
                        if not (np >= 0 and np == np and np not in (float("inf"), float("-inf"))):
                            raise ValueError
                        changes["price"] = np
                    except (TypeError, ValueError):
                        return self._json(400, {"error": "price must be a nonnegative number"})
                if "capacity" in changes:
                    try:
                        nc = int(changes["capacity"])
                    except (TypeError, ValueError):
                        return self._json(400, {"error": "capacity must be an integer"})
                    reg = listing.get("registered", 0) or 0
                    if nc < reg:
                        return self._json(409, {"error": f"capacity below already-registered {reg}"})
                    changes["capacity"] = nc
                if "category" in changes:
                    cat = str(changes["category"]).strip().lower()
                    sch = VERTICAL_SCHEMAS[listing["vertical"]]
                    if cat not in sch["categories"]:
                        return self._json(400, {"error": f"unknown category: {cat}", "known": sch["categories"]})
                    changes["category"] = cat
                if "tags" in changes:
                    try:
                        changes["tags"] = normalize_tags(changes["tags"])
                    except ValueError as ex:
                        return self._json(400, {"error": str(ex)})
                if _pt_edit:  # C12: owner-editable terms (pre-booking); null resets to the vertical default
                    _new_price = changes.get("price", listing.get("price", 0))
                    _nt, _nterr = _normalize_payment_terms(data["payment_terms"], _new_price, listing["vertical"])
                    if _nterr:
                        return self._json(400, {"error": _nterr})
                    changes["payment_terms"] = _nt if _nt is not None else _default_payment_terms(listing["vertical"])
                if _rvb_edit:  # C11: the gate is owner-controlled and must be a real boolean (SPEC section 22)
                    if not isinstance(data["require_verified_buyer"], bool):
                        return self._json(400, {"error": "require_verified_buyer must be a boolean"})
                    changes["require_verified_buyer"] = data["require_verified_buyer"]
                if _promo_edit:  # promo codes (owner-approved 2026-09-30):
                    # promo: null clears; {code, pct, uses} sets. Code stored as
                    # sha256 ONLY (H9 law - same wall as manage codes); the plain
                    # code is echoed ONCE in this response so the organizer can
                    # share it. pct 1-50 (paid stays paid), uses 1-1000.
                    pv = data["promo"]
                    if pv is None:
                        listing.pop("promo_code_hash", None)
                        listing.pop("promo_pct", None)
                        listing.pop("promo_uses_left", None)
                        _persist_locked()
                        return self._json(200, {"ok": True, "id": lid, "promo": None,
                                                "note": "promo code removed"})
                    if not isinstance(pv, dict) or set(pv) != {"code", "pct", "uses"}:
                        return self._json(400, {"error": "promo must be an object with exactly: code, pct, uses (or null to remove)"})
                    code_p = str(pv["code"]).strip().upper()
                    if not re.fullmatch(r"[A-Z0-9]{3,24}", code_p):
                        return self._json(400, {"error": "promo code must be 3-24 letters/digits"})
                    try:
                        pct_p = int(pv["pct"])
                    except (TypeError, ValueError):
                        return self._json(400, {"error": "promo pct must be an integer"})
                    if not (1 <= pct_p <= 50):
                        return self._json(400, {"error": "promo pct must be 1-50 (paid stays paid)"})
                    try:
                        uses_p = int(pv["uses"])
                    except (TypeError, ValueError):
                        return self._json(400, {"error": "promo uses must be an integer"})
                    if not (1 <= uses_p <= 1000):
                        return self._json(400, {"error": "promo uses must be 1-1000"})
                    _new_price_p = changes.get("price", listing.get("price", 0))
                    if not (isinstance(_new_price_p, (int, float)) and float(_new_price_p) > 0):
                        return self._json(400, {"error": "promo needs a paid listing (price > 0)"})
                    listing["promo_code_hash"] = hashlib.sha256(code_p.encode()).hexdigest()
                    listing["promo_pct"] = pct_p
                    listing["promo_uses_left"] = uses_p
                    _persist_locked()
                    return self._json(200, {"ok": True, "id": lid,
                        "promo": {"code": code_p, "pct": pct_p, "uses": uses_p},
                        "note": "promo code shown ONCE - share it with your buyers; the hub stores only its hash"})
                if "url" in changes:
                    u3 = str(changes["url"]).strip()
                    if not (u3.startswith("http://") or u3.startswith("https://")) or len(u3) > 300:
                        return self._json(400, {"error": "url must start with http:// or https:// (max 300 chars)"})
                    changes["url"] = u3
                if "description" in changes:
                    d3 = str(changes["description"]).strip()
                    if len(d3) > 500:
                        return self._json(400, {"error": "description too long (max 500 chars)"})
                    changes["description"] = d3
                if "title" in changes:
                    t3 = str(changes["title"]).strip()
                    if not t3:
                        return self._json(400, {"error": "title cannot be empty"})
                    changes["title"] = t3[:80]
                # H17: schema-derived edit fields get schema validation
                for _f, _t in (_sch.get("field_types") or {}).items():
                    if _f not in changes:
                        continue
                    if _t == "positive_int":
                        try:
                            _iv = int(changes[_f])
                        except (TypeError, ValueError):
                            return self._json(400, {"error": f"{_f} must be an integer"})
                        if _iv <= 0:
                            return self._json(400, {"error": f"{_f} must be positive"})
                        changes[_f] = _iv
                    elif _t == "float_latlon":
                        # D1 2026-10-15: lat/lon floats for client-side distance
                        try:
                            _fv = float(changes[_f])
                        except (TypeError, ValueError):
                            return self._json(400, {"error": f"{_f} must be a number"})
                        if not (-90.0 <= _fv <= 90.0 if _f == "lat" else -180.0 <= _fv <= 180.0):
                            return self._json(400, {"error": f"{_f} out of range"})
                        changes[_f] = round(_fv, 6)
                for _k in ("provider", "merchant"):
                    if _k in changes:
                        _pv = str(changes[_k]).strip()
                        if not _pv:
                            return self._json(400, {"error": f"{_k} cannot be empty"})
                        changes[_k] = _pv[:80]
                listing.update(changes)
                _persist_locked()
                return self._json(200, {"ok": True, "edited": lid, "fields": sorted(changes)})
        if path == "/book":
            # E2/E3 (TRACK E): engine extracted to _book_core (verbatim);
            # this route is now a thin HTTP wrapper over the shared core.
            code, body, eh = self._book_core(data)
            return self._json(code, body, extra_headers=eh)
        if path.startswith("/ticket/") and path.endswith("/name"):
            # T5: door-display name via the ticket capability itself - the
            # holder of the token IS the attendee (capability law). Name is
            # explicit buyer UGC, sanitized; renderers still escape.
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "manage rate limit reached for your source, retry later"})
            _tok = path[len("/ticket/"):-len("/name")]
            tk = ticketing.lookup_by_token(TICKETS, _tok)
            if tk is None:
                return self._json(404, {"error": "no ticket"})
            nm = str(data.get("display_name", ""))
            if _BAD_CHARS_RE.search(nm) or "\n" in nm or "\r" in nm:
                return self._json(400, {"error": "display_name must not contain control characters"})
            ticketing.set_name(tk, nm, str(data.get("display_choice", "full")))
            with LOCK:
                _persist_locked()
            return self._json(200, {"ok": True, "bid": tk["bid"],
                "guest": ticketing.display_name_of(tk),
                "display_choice": tk.get("display_choice")})
        if path.startswith("/ticket/") and path.endswith("/redeem"):
            # T5: ONE-TIME door check-in. Owner proof only (B3c model, same
            # as /confirm): admin confirm token, or a list token whose acct-
            # principal owns the booking's listing, or the listing
            # manage_code. First scan wins; later scans honestly report
            # first_time=false with the ORIGINAL timestamp.
            _tok = path[len("/ticket/"):-len("/redeem")]
            tk = ticketing.lookup_by_token(TICKETS, _tok)
            if tk is None:
                return self._json(404, {"error": "no ticket"})
            bid = tk.get("bid")
            cred = self.headers.get("X-Hub-Token", "")
            manage_code = str(data.get("manage_code", "")).strip()
            p, _perr = None, None
            if cred:
                p, _perr = hublib.verify_token(ADMIN_KEY, cred, "confirm", subject=bid)
                if not p:
                    p, _perr = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                    if p:
                        p, _perr = _gen_check(p)  # B1: stale tokens never prove identity
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "manage rate limit reached for your source, retry later"})
                _cb = next((x for x in BOOKINGS if x["id"] == bid), None)
                _owner_ok = False
                if _cb is not None:
                    _cl = next((x for x in LISTINGS if x["id"] == _cb.get("listing_id")), None)
                    if _cl is not None:
                        if p and str(p.get("sub", "")).startswith("acct-") and p["sub"] == _cl.get("owner"):
                            _owner_ok = True
                        elif manage_code and hmac.compare_digest(
                                hashlib.sha256(manage_code.encode()).hexdigest(),
                                str(_cl.get("manage_code_hash", ""))):
                            _owner_ok = True
            if _cb is None:
                return self._json(404, {"error": "no booking"})
            _admin_tok = bool(p) and p.get("act") == "confirm"
            if not cred and not manage_code:
                return self._json(401, {"error": "missing credentials",
                    "hint": "owner: send your list token as X-Hub-Token, or manage_code in the body"})
            if not _admin_tok and not _owner_ok:
                return self._json(403, {"error": "invalid credentials or not the listing owner"})
            _by = "admin" if _admin_tok else (p["sub"] if (p and _owner_ok) else "manage_code")
            _r = ticketing.redeem(tk, _by)
            with LOCK:
                _persist_locked()
            return self._json(200, {"ok": True, "bid": bid,
                "first_time": _r["first_time"],
                "guest": ticketing.display_name_of(tk),
                "redeemed_ts": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(_r["ts"]))})
        if path.startswith("/book/") and path.endswith("/confirm"):
            bid = path.split("/")[2]
            cred = self.headers.get("X-Hub-Token", "")  # I2: owner token required
            # FED3 (run #5): fulfillment is an OWNER action — but only an
            # admin-minted confirm token worked, so merchants were locked out
            # of their own fulfillment (SDK journey blocker). Accept either an
            # admin confirm token, OR ordinary listing-owner proof (B3c model,
            # same as /manage): a list token whose acct- principal owns the
            # booking's listing, or the listing's manage_code in the body.
            manage_code = str(data.get("manage_code", "")).strip()
            p, _perr = None, None
            if cred:
                p, _perr = hublib.verify_token(ADMIN_KEY, cred, "confirm", subject=bid)
                if not p:
                    p, _perr = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
                    if p:
                        p, _perr = _gen_check(p)  # B1: stale tokens never prove identity
            # H5-consistent backstop: manage_code guesses on confirm count toward
            # the same 'manage' source bucket the /manage route uses
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "manage rate limit reached for your source, retry later"})
                _cb = next((x for x in BOOKINGS if x["id"] == bid), None)
                _owner_ok = False
                if _cb is not None:
                    _cl = next((x for x in LISTINGS if x["id"] == _cb.get("listing_id")), None)
                    if _cl is not None:
                        if p and str(p.get("sub", "")).startswith("acct-") and p["sub"] == _cl.get("owner"):
                            _owner_ok = True
                        elif manage_code and hmac.compare_digest(
                                hashlib.sha256(manage_code.encode()).hexdigest(),
                                str(_cl.get("manage_code_hash", ""))):
                            _owner_ok = True
            if _cb is None:
                return self._json(404, {"error": "no booking"})
            _admin_tok = bool(p) and p.get("act") == "confirm"
            if not cred and not manage_code and not _owner_ok:
                return self._json(401, {"error": "missing credentials",
                    "hint": "owner: POST /accounts/login then send your list token, or send manage_code in the body; ops: admin confirm token via POST /admin/tokens {act: 'confirm', booking_id}"})
            if not _admin_tok and not _owner_ok:
                return self._json(403, {"error": "invalid credentials or not the listing owner",
                    "hint": "send your list token (as the owning account) or the listing manage_code; admin confirm tokens stay valid"})
            # LEVEL-1 chain gate - TERMINAL FLIP (verify-then-flip, dual-source
            # reads that must agree): the hub may flip HELD->RELEASED only
            # when the chain says HELD. Fail-closed on any doubt (D1).
            if CHAIN_GATE:
                with LOCK:
                    _fb = next((x for x in BOOKINGS if x["id"] == bid), None)
                if _fb is None:
                    return self._json(404, {"error": "no booking"})
                if _fb["escrow"] == "HELD":
                    _fr = _fb.get("escrow_ref")
                    if _fr is None:
                        return self._json(409, {"error": "chain gating is on but this HELD booking predates it (no escrow_ref)",
                            "hint": "operator: reconcile legacy bookings (sync or mark) before confirming them"})
                    _flip_v, _ferr = _chain_gate_read(_fr, dual=True)
                    if _flip_v is None:
                        _fcode, _fbody = _ferr
                        return self._json(_fcode, _fbody)
                    if _flip_v["state_name"] != "HELD":
                        _hint = ("buyer-side releaseEscrow on-chain, then POST /admin/sync-escrow to mirror it"
                                 if _flip_v["state_name"] == "RELEASED"
                                 else "POST /admin/sync-escrow to mirror the chain, or wait for autoRelease")
                        return self._json(409, {
                            "error": "chain escrow is %s - hub-first release refused (chain is source of truth)" % _flip_v["state_name"],
                            "chain": {"state": _flip_v["state_name"], "escrow_id": _fr["escrow_id"]},
                            "hint": _hint,
                            "note": "the hub never claims a money state the chain does not back"})
            with LOCK:
                b = next((x for x in BOOKINGS if x["id"] == bid), None)
                if not b: return self._json(404, {"error": "no booking"})
                if b["escrow"] == "DIRECT":  # C12: instant rail — settled at booking, nothing to confirm
                    return self._json(409, {"error": "instant rail: payment settled at booking - nothing to confirm"})
                if b["escrow"] not in ("HELD", "WAIVED"):  # H15: free (WAIVED) bookings confirm too — no money moves
                    return self._json(409, {"error": f"escrow is {b['escrow']}"})
                b["escrow"] = "RELEASED"
                for t in LEDGER:
                    if t.get("booking") == bid: t["escrow"] = "RELEASED"; t["released_to"] = "owner"  # fullflow 2026-10-18: t.get - ledger rows without a booking key (x402_settlement wallet rows) must be skipped, not KeyError the hub
                _earnings_record_locked(b)  # W3.4: payout>0 only; WAIVED no-ops inside
                _persist_locked()
            _notify_booking("released", b, _listing_of(b))
            return self._json(200, {"ok": True, "id": bid, "escrow": "RELEASED",
                "owner_received": b["owner_payout"], "confirmation": f"{bid}-ticket"})
        if path.startswith("/book/") and path.endswith("/transfer"):
            # Transfers (owner-approved 2026-09-30): re-assign a booking to a
            # new attendee name, pre-fulfillment only. Auth = the CURRENT
            # cancel_token (buyer credential). Escrow, fees, rating rights and
            # capacity are untouched - only WHO attends changes. All previous
            # credentials die: booking_secret rotates (old secret cannot view
            # private details anymore) and cred_gen bumps (old cancel_tokens
            # fail the gen check in /cancel and here).
            bid = path.split("/")[2]
            cred = self.headers.get("X-Hub-Token", "")
            if not cred:
                return self._json(401, {"error": "missing X-Hub-Token",
                    "hint": "use the cancel_token returned at booking time (or from your latest transfer)"})
            p, err = hublib.verify_token(BOOKING_KEY, cred, "cancel", subject=bid)
            if not p:
                return self._json(403, {"error": err or "token not valid for this booking"})
            new_name = str((data or {}).get("name") or "").strip()
            if not new_name or len(new_name) > 80:
                return self._json(400, {"error": "name is required (1-80 chars)"})
            with LOCK:
                b = next((x for x in BOOKINGS if x["id"] == bid), None)
                if not b: return self._json(404, {"error": "no booking"})
                if b.get("cred_gen") and p.get("gen") != b.get("cred_gen"):
                    return self._json(403, {"error": "token superseded by a transfer",
                        "hint": "use the cancel_token from the most recent transfer"})
                if b["escrow"] not in ("HELD", "WAIVED"):
                    return self._json(409, {"error": f"cannot transfer after settlement (escrow is {b['escrow']})",
                        "note": "transfers are pre-fulfillment only"})
                v = b.get("vertical")
                _idf = VERTICAL_SCHEMAS[v]["booking"]["identity"]
                # rotate every credential the previous holder had:
                new_secret = secrets.token_hex(16)
                sec = SECRETS.get(bid) or {"private": {}}
                sec["secret"] = new_secret
                sec.setdefault("private", {})[_idf] = new_name[:80]
                SECRETS[bid] = sec
                b[_idf] = anon_ref()  # I5: fresh unlinkable reference
                new_gen = int(b.get("cred_gen", 0) or 0) + 1
                b["cred_gen"] = new_gen
                _ptt = b.get("payment_terms") or {}
                ttl = max(7 * 24 * 3600,
                          int((_ptt or {}).get("refund_window_hours", 0) or 0) * 3600 + 48 * 3600)
                new_cancel = hublib.mint_token(BOOKING_KEY, "cancel", bid, ttl=ttl,
                                               extra={"gen": new_gen})
                LEDGER.append({"kind": "transfer", "ts": time.time(), "booking": bid,
                               "detail": {"to": new_name[:80], "gen": new_gen}})
                _persist_locked()
            _notify_booking("transferred", b, _listing_of(b))
            return self._json(200, {"ok": True, "id": bid, "transferred_to": new_name[:80],
                "booking_secret": new_secret,
                "secret_note": "shown ONCE; the previous secret no longer works",
                "cancel_token": new_cancel,
                "escrow": b["escrow"]})
        if path.startswith("/book/") and path.endswith("/cancel"):
            bid = path.split("/")[2]
            cred = self.headers.get("X-Hub-Token", "")  # I2: buyer cancel_token required
            if not cred:
                return self._json(401, {"error": "missing X-Hub-Token",
                    "hint": "use the cancel_token returned at booking time"})
            p, err = hublib.verify_token(BOOKING_KEY, cred, "cancel", subject=bid)
            if not p:
                return self._json(403, {"error": err or "token not valid for this booking"})
            # LEVEL-1 chain gate - TERMINAL FLIP (verify-then-flip, dual-source
            # reads that must agree): the hub may flip HELD->REFUNDED only
            # while the chain escrow is HELD and inside its claim deadline. The
            # chain deadline is authoritative (D2); the hub terms window below
            # stays as the stricter, human-facing policy. Fail-closed on doubt.
            if CHAIN_GATE:
                with LOCK:
                    _cb = next((x for x in BOOKINGS if x["id"] == bid), None)
                if _cb is None:
                    return self._json(404, {"error": "no booking"})
                if _cb["escrow"] == "HELD":
                    _cr = _cb.get("escrow_ref")
                    if _cr is None:
                        return self._json(409, {"error": "chain gating is on but this HELD booking predates it (no escrow_ref)",
                            "hint": "operator: reconcile legacy bookings (sync or mark) before cancelling them"})
                    _cv, _cv_err = _chain_gate_read(_cr, dual=True)
                    if _cv is None:
                        _cv_code, _cv_body = _cv_err
                        return self._json(_cv_code, _cv_body)
                    if _cv["state_name"] != "HELD":
                        _hint = ("on-chain timeoutRefund / mutualRefund already moved funds - POST /admin/sync-escrow to mirror the chain"
                                 if _cv["state_name"] == "REFUNDED"
                                 else "buyer-side releaseEscrow on-chain, then POST /admin/sync-escrow to mirror it")
                        return self._json(409, {
                            "error": "chain escrow is %s - hub-first refund refused (chain is source of truth)" % _cv["state_name"],
                            "chain": {"state": _cv["state_name"], "escrow_id": _cr["escrow_id"]},
                            "hint": _hint})
                    try:
                        _cdl = float(str(_cv.get("deadline")))
                    except (TypeError, ValueError):
                        _cdl = None
                    if _cdl is not None and time.time() > _cdl:
                        return self._json(409, {
                            "error": "chain claim deadline passed - the escrow contract will not execute this refund",
                            "deadline": _cv.get("deadline"),
                            "hint": "the chain auto-releases to the organizer after the claim deadline; the hub cannot co-sign a refund past it"})
            with LOCK:
                b = next((x for x in BOOKINGS if x["id"] == bid), None)
                if not b: return self._json(404, {"error": "no booking"})
                if b.get("cred_gen") and p.get("gen") != b.get("cred_gen"):
                    return self._json(403, {"error": "token superseded by a transfer",
                        "hint": "use the cancel_token from the most recent transfer"})
                if b["escrow"] == "DIRECT":  # C12: instant rail settles at booking — there is no refund window to cancel inside
                    return self._json(409, {"error": "instant rail: payment settled at booking - no refund window (listing terms)"})
                if b["escrow"] not in ("HELD", "WAIVED"):  # H15: WAIVED (free) bookings are cancellable too
                    return self._json(409, {"error": f"escrow is {b['escrow']}"})
                # S7: enforce the advertised refund window — the hub must never
                # bookkeep a refund the escrow contract will not execute (the
                # chain walls refunds past its claim deadline; sync-escrow
                # refuses the divergent hub REFUNDED / chain RELEASED pair).
                # Deadline = booking creation + the server-owned terms snapshot
                # taken at booking time; pre-C12 bookings get the vertical
                # default. WAIVED moves no money and stays cancellable.
                if b["escrow"] == "HELD":
                    _ptc = b.get("payment_terms") or {}
                    _win = _ptc.get("refund_window_hours")
                    if not isinstance(_win, int) or _win <= 0:
                        _win = _DEFAULT_REFUND_WINDOW_HOURS.get(b.get("vertical"), 72)
                    if time.time() > b["created"] + _win * 3600:
                        return self._json(409, {
                            "error": f"refund window closed ({_win}h after booking)",
                            "note": "the escrow contract auto-releases funds to the organizer after the claim deadline; hub bookkeeping mirrors the chain, so a late hub-side refund is refused",
                            "hint": "on-chain timeoutRefund stays available to the buyer until the chain claim deadline; the hub cannot co-sign a refund past it"})
                b["escrow"] = "REFUNDED"
                # I3: restore capacity exactly once, atomically with the escrow transition
                lst = next((l for l in LISTINGS if l["id"] == b.get("listing_id")), None)
                if lst and VERTICAL_SCHEMAS.get(b["vertical"], {}).get("tracks_capacity"):
                    lst["registered"] = max(0, lst.get("registered", 0) - b.get("quantity", 1))
                for t in LEDGER:  # fullflow 2026-10-18: t.get - ledger rows without a booking key (x402_settlement wallet rows) must be skipped, not KeyError the hub
                    if t.get("booking") == bid: t["escrow"] = "REFUNDED"; t["refunded_to"] = "buyer"
                _persist_locked()
            _notify_booking("refunded", b, _listing_of(b))
            # fullflow 2026-10-18: the response carries the refunded amount so
            # honest clients can show the real money journey (a PAID cancel
            # must never print 'nothing to pay')
            return self._json(200, {"ok": True, "id": bid, "escrow": "REFUNDED",
                                    "amount": b.get("amount", 0)})
        if path.startswith("/book/") and path.endswith("/dispute"):
            # W3.1 dispute path: either party (buyer or organizer) can freeze
            # a HELD booking for arbitration. No money moves - the freeze IS
            # the point. The hub mirrors the on-chain DISPUTED state; the
            # escrow contract walls release/refund while DISPUTED.
            bid = path.split("/")[2]
            with LOCK:
                if not _auth_allow("book", _source_of(self)):
                    return self._json(429, {"error": "rate limit reached, retry later"})
            cred = self.headers.get("X-Hub-Token", "")
            manage_code = (data or {}).get("manage_code", "")
            with LOCK:
                _b = next((x for x in BOOKINGS if x["id"] == bid), None)
            if _b is None:
                return self._json(404, {"error": "no booking"})
            _is_buyer = False
            _is_owner = False
            if cred:
                # W3.1: single_use=False — a dispute is a freeze, not a terminal
                # flip; the buyer's cancel credential must SURVIVE it (the
                # escrow-state walls are the protection, not token burning).
                p, err = hublib.verify_token(BOOKING_KEY, cred, "cancel", subject=bid, single_use=False)
                if p and _gen_check(p)[0]:
                    _is_buyer = True
                else:
                    p2, err2 = hublib.verify_token(BOOKING_KEY, cred, "book", single_use=False)
                    if p2 and _gen_check(p2)[0] and p2.get("sub") == _b.get("booked_by"):
                        _is_buyer = True
            if manage_code and not _is_buyer:
                _cl = next((x for x in LISTINGS if x["id"] == _b.get("listing_id")), None)
                if _cl is not None and hmac.compare_digest(
                        hashlib.sha256(manage_code.encode()).hexdigest(),
                        str(_cl.get("manage_code_hash", ""))):
                    _is_owner = True
            if not _is_buyer and not _is_owner:
                return self._json(401, {"error": "missing or invalid credentials",
                    "hint": "buyer: send your cancel_token as X-Hub-Token; organizer: send manage_code in the body"})
            # LEVEL-1 chain gate - verify-then-flip: hub may flip HELD->DISPUTED
            # only when the chain still says HELD. Fail-closed on any doubt.
            if CHAIN_GATE:
                _cr = _b.get("escrow_ref")
                if _cr is not None:
                    _cv, _cv_err = _chain_gate_read(_cr, dual=True)
                    if _cv is not None and _cv["state_name"] not in ("HELD", "DISPUTED"):
                        return self._json(409, {
                            "error": "chain escrow is %s - dispute refused (chain is source of truth)" % _cv["state_name"],
                            "chain": {"state": _cv["state_name"], "escrow_id": _cr["escrow_id"]}})
            with LOCK:
                b = next((x for x in BOOKINGS if x["id"] == bid), None)
                if b is None:
                    return self._json(404, {"error": "no booking"})
                if b["escrow"] != "HELD":
                    return self._json(409, {"error": "escrow is %s - only HELD bookings can be disputed" % b["escrow"],
                        "hint": "settled (RELEASED/REFUNDED/WAIVED/DIRECT) or already disputed (DISPUTED)"})
                b["escrow"] = "DISPUTED"
                LEDGER.append({"ts": time.time(), "kind": "escrow_sync",
                               "booking": bid, "from": "HELD", "to": "DISPUTED",
                               "dispute_opened_by": "buyer" if _is_buyer else "organizer"})
                _persist_locked()
            return self._json(200, {"ok": True, "id": bid, "escrow": "DISPUTED",
                "note": "funds frozen for arbitration; no release or refund while DISPUTED",
                "liveness": "if the arbiter vanishes, arbiterTimeoutRefund returns buyer funds after the arbiter deadline"})
        if path == "/organizer/earnings-proof":
            # W3.4: revenue-floor proof (pilot). The hub checks its private
            # mirror and answers PASS/FAIL ONLY for the verifier-chosen bar -
            # the honest protocol shape of proveEarningsFloor. On-chain the
            # organizer runs the circuit themselves (M25/M26 wallet-embedded);
            # this endpoint is the demo/agent surface with the same honesty:
            # never returns the actual totals.
            cred = self.headers.get("X-Hub-Token", "")
            if not cred:
                return self._json(401, {"error": "missing X-Hub-Token",
                    "hint": "log in (POST /accounts/login) and send your list token"})
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
            if p:
                p, err = _gen_check(p)
            if not p:
                return self._json(403, {"error": err or "token not valid for earnings proof",
                    "hint": "send your list token (the owning account)"})
            me = p.get("sub", "")
            try:
                mv = float((data or {}).get("min_volume", 0))
                ms = int((data or {}).get("min_settlements", 0))
            except (TypeError, ValueError):
                return self._json(400, {"error": "min_volume must be a number, min_settlements an integer"})
            if ms < 1:
                return self._json(400, {"error": "min_settlements must be >= 1 (a floor over zero history is vacuous)",
                    "hint": "the circuit enforces the same wall"})
            if mv <= 0:
                return self._json(400, {"error": "min_volume must be > 0"})
            with LOCK:
                e = EARNINGS.get(me) or {"settledCount": 0, "totalVolume": 0.0, "events": []}
                cnt = int(e.get("settledCount", 0))
                vol = float(e.get("totalVolume", 0.0))
            met = (cnt >= ms) and (round(vol, 2) >= mv)
            return self._json(200, {"met": met,
                "thresholds": {"min_settlements": ms, "min_volume": round(mv, 2)},
                "protocol": "pass/fail only - actual totals are never disclosed (same honesty as proveEarningsFloor)",
                "zk_contract": "earnings.compact proveEarningsFloor(minSettlements, minVolume) - issuer-walled recorder, Grade-A-at-birth pattern"})
        if path == "/organizer/batch-settle":
            # W3.3 usage surface: settle ALL of an organizer's settleable
            # bookings in ONE call (one chat command, one request). Money
            # honesty is unchanged - this is the confirm path applied N times
            # under the same walls: chain gate verify-then-flip per HELD
            # booking, earnings hook per payout, per-booking results. The
            # on-chain batchRelease2 circuit is the ZK act; this endpoint is
            # the hub pilot surface with the same per-booking walls.
            cred = self.headers.get("X-Hub-Token", "")
            if not cred:
                return self._json(401, {"error": "missing X-Hub-Token",
                    "hint": "log in (POST /accounts/login) and send your list token"})
            p, err = hublib.verify_token(BOOKING_KEY, cred, "list", single_use=False)
            if p:
                p, err = _gen_check(p)
            if not p:
                return self._json(403, {"error": err or "token not valid for batch settle",
                    "hint": "send your list token (the owning account)"})
            me = p.get("sub", "")  # same keying as /organizer/earnings: the token principal IS the organizer identity
            with LOCK:
                if not _auth_allow("manage", _source_of(self)):
                    return self._json(429, {"error": "manage rate limit reached for your source, retry later"})
                my_listings = {x["id"] for x in LISTINGS if x.get("owner") == me}
                mine = [x for x in BOOKINGS
                        if x.get("listing_id") in my_listings and x["escrow"] in ("HELD", "WAIVED")]
                results = []
                released_n = 0
                total_payout = 0.0
                for b in mine:
                    bid = b["id"]
                    try:
                        if b["escrow"] == "HELD" and CHAIN_GATE:
                            _fr = b.get("escrow_ref")
                            if _fr is None:
                                results.append({"id": bid, "ok": False, "error": "predates chain gating (no escrow_ref)"})
                                continue
                            _fv, _fe = _chain_gate_read(_fr, dual=True)
                            if _fv is None:
                                _fc, _fb = _fe
                                results.append({"id": bid, "ok": False, "error": _fb.get("error", "chain gate refused")})
                                continue
                            if _fv["state_name"] != "HELD":
                                results.append({"id": bid, "ok": False,
                                    "error": "chain escrow is %s - not settleable from here" % _fv["state_name"]})
                                continue
                        if b["escrow"] == "HELD":
                            b["escrow"] = "RELEASED"
                            for t in LEDGER:
                                if t.get("booking") == bid:
                                    t["escrow"] = "RELEASED"
                                    t["released_to"] = "owner"
                            _earnings_record_locked(b)
                            released_n += 1
                            total_payout += float(b.get("owner_payout", 0) or 0)
                        else:  # WAIVED: free booking - confirm marks it settled, no money moves
                            b["escrow"] = "RELEASED"
                            released_n += 1
                        results.append({"id": bid, "ok": True, "escrow": "RELEASED",
                                        "owner_received": b.get("owner_payout", 0)})
                        _notify_booking("released", b, _listing_of(b))
                    except Exception as _ex:
                        results.append({"id": bid, "ok": False, "error": "settle failed"})
                _persist_locked()
            return self._json(200, {"ok": True, "settled": released_n,
                "total_payout": round(total_payout, 2), "results": results,
                "note": "per-booking walls all applied (chain gate verify-then-flip; disputes are never touched)"})
        if path.startswith("/book/") and path.endswith("/rate"):
            # S2: mutating route - per-source backstop before any auth work
            with LOCK:
                if not _auth_allow("rate", _source_of(self)):
                    return self._json(429, {"error": "rating rate limit reached for your source, retry later"})
            bid = path.split("/")[2]
            cred = self.headers.get("X-Hub-Token", "")  # I2: buyer token required
            if not cred:
                return self._json(401, {"error": "missing X-Hub-Token",
                    "hint": "send your book token (POST /access acts=['book'], or account login) as X-Hub-Token"})
            p, err = hublib.verify_token(BOOKING_KEY, cred, "book", single_use=False)
            if p:
                p, err = _gen_check(p)  # B1: revoked accounts cannot rate
            if not p:
                return self._json(403, {"error": err or "token not valid for rating"})
            me = p["sub"]
            val = data.get("rating")
            if isinstance(val, bool) or not isinstance(val, int) or not (1 <= val <= 5):
                return self._json(400, {"error": "rating must be an integer in [1, 5]"})
            with LOCK:
                b = next((x for x in BOOKINGS if x["id"] == bid), None)
                if not b: return self._json(404, {"error": "no booking"})
                if b.get("booked_by") != me:  # owner-immutable: only the buyer can rate
                    return self._json(403, {"error": "only the booking's buyer may rate it"})
                if b["escrow"] not in ("RELEASED", "WAIVED", "DIRECT"):
                    return self._json(409, {"error": f"rating opens after settlement (escrow is {b['escrow']})"})
                if "rating" in b:  # once per booking, forever
                    return self._json(409, {"error": "already rated"})
                lst = next((l for l in LISTINGS if l["id"] == b.get("listing_id")), None)
                # S6-L2 channel classifier (run #5 fix): by ECONOMIC VALUE, not the
                # mutable escrow label — owner/admin confirm legitimately flips a
                # free (WAIVED) booking to RELEASED with owner_received 0.0, and
                # its rating must stay in the free-feedback channel, never the
                # amount-weighted paid one.
                try:
                    _bamt = float(b.get("amount", 0) or 0)
                except (TypeError, ValueError):
                    _bamt = 0.0
                free = (_bamt == 0.0)
                if lst is not None:
                    # S6-L1 wall 1: the listing owner can never rate their own listing
                    if b.get("booked_by") == lst.get("owner"):
                        return self._json(403, {"error": "self-review rejected: the listing owner cannot rate their own listing"})
                    # S6-L1 wall 2: x402 self-pay - the paying wallet equals the merchant receive address
                    _pp = str(b.get("payment_payer") or "").lower()
                    _rx = str(lst.get("receive_addr") or "").lower()
                    if _pp and _rx and _pp == _rx:
                        return self._json(403, {"error": "self-review rejected: payment came from the merchant's own receive address"})
                b["rating"] = val
                b["rated_at"] = time.time()  # S6-L4: burst detection (server-only)
                if lst is not None:
                    if free:  # S6-L2: free bookings feed a separate feedback channel, never the paid aggregate
                        lst["free_rating_sum"] = lst.get("free_rating_sum", 0) + val
                        lst["free_rating_count"] = lst.get("free_rating_count", 0) + 1
                    else:     # S6-L3: paid reviews weighted by settled amount (capped)
                        w = _review_weight(b)
                        lst["rating_wsum"] = lst.get("rating_wsum", 0) + val * w
                        lst["rating_wtot"] = lst.get("rating_wtot", 0) + w
                        lst["rating_sum"] = lst.get("rating_sum", 0) + val
                        lst["rating_count"] = lst.get("rating_count", 0) + 1
                        lst["rating_avg"] = round(lst["rating_wsum"] / lst["rating_wtot"], 2)
                        _s6_flag_review(lst)  # S6-L4: interlock heuristics -> manual queue
                _persist_locked()
            agg = _agg_text(lst) if lst is not None else ""
            return self._json(200, {"ok": True, "id": bid, "rating": val,
                "channel": "free-feedback" if free else "paid", "aggregate": agg,
                "note": "public ledger untouched - ratings carry no ledger entries and no new identity data"})
        if path == "/admin/tokens":
            # H5: admin-key brute-force backstop (shared 'admin' kind with vouch)
            with LOCK:
                if not _auth_allow("admin", _source_of(self)):
                    return self._json(429, {"error": "admin rate limit reached for your source, retry later"})
            # I2: restricted token minting - admin bootstrap key required (constant-time compare)
            cred = self.headers.get("X-Hub-Token", "")
            if not hmac.compare_digest(cred, ADMIN_KEY):
                return self._json(403, {"error": "invalid admin key",
                    # FED2 (run #5): never echo the dev-default value in-band —
                    # an unauthenticated 403 must not hand out the bootstrap key.
                    "note": "bootstrap: X-Hub-Token must equal the HUB_ADMIN_KEY env value",
                    "dev_default_in_use": ADMIN_KEY == "dev-admin-key-change-me"})
            act = data.get("act"); sub = data.get("booking_id", "")
            if act not in ("confirm",):  # only confirm minting exposed for now
                return self._json(400, {"error": "act must be 'confirm'"})
            if not sub: return self._json(400, {"error": "booking_id required"})
            tok = hublib.mint_token(ADMIN_KEY, "confirm", sub, ttl=int(data.get("ttl", 3600)))
            return self._json(201, {"ok": True, "token": tok, "act": "confirm", "booking_id": sub})
        if path == "/admin/sponsor":
            # Phase 3 marketplace: sponsored PLACEMENT (owner GO 2026-11-07).
            # Admin-granted only — money never self-serves placement; organic
            # order stays untouched (the sponsored listing rides the page
            # TAIL, capped 1/page, labeled sponsored=true in every payload).
            with LOCK:
                if not _auth_allow("admin", _source_of(self)):
                    return self._json(429, {"error": "admin rate limit reached for your source, retry later"})
            cred = self.headers.get("X-Hub-Token", "")
            if not hmac.compare_digest(cred, ADMIN_KEY):
                return self._json(403, {"error": "invalid admin key"})
            _slid = str(data.get("listing_id", "")).strip()
            _days = data.get("days", 7)
            if not _slid:
                return self._json(400, {"error": "listing_id required"})
            if not isinstance(_days, int) or not (1 <= _days <= 60):
                return self._json(400, {"error": "days must be int 1..60"})
            with LOCK:
                _sl = next((x for x in LISTINGS if x["id"] == _slid), None)
                if not _sl:
                    return self._json(404, {"error": f"no listing {_slid}"})
                if _sl.get("archived") or _sl.get("visibility") == "private":
                    return self._json(409, {"error": "listing must be public and active to be sponsored"})
                _sl["_sponsor"] = {"active": True,
                                    "until_ts": time.time() + _days * 86400,
                                    "granted_by": "admin", "days": _days}
                _persist_locked()
            return self._json(200, {"ok": True, "id": _slid,
                "sponsored_until": time.strftime("%Y-%m-%d", time.gmtime(_sl["_sponsor"]["until_ts"])),
                "law": "organic order untouched; sponsored listing appears LAST per results page, labeled sponsored=true"})
        if path == "/admin/digest/send":
            # Weekly organizer digest (Phase B follow-up, owner-approved polish
            # batch 2026-09-18). Admin-gated; body: {weeks: N (default 1),
            # dry_run: bool}. For every organizer account with a VERIFIED email
            # and notify_email on: counts bookings on their listings created in
            # the window + gross amount, sends ONE branded summary. Returns
            # per-organizer results; dry_run computes but sends nothing.
            cred = self.headers.get("X-Hub-Token", "")
            if not hmac.compare_digest(cred, ADMIN_KEY):
                return self._json(403, {"error": "invalid admin key"})
            with LOCK:
                if not _auth_allow("admin", _source_of(self)):
                    return self._json(429, {"error": "admin rate limit reached for your source, retry later"})
                weeks = data.get("weeks", 1)
                if not isinstance(weeks, int) or weeks < 1 or weeks > 12:
                    return self._json(400, {"error": "weeks must be int 1..12"})
                dry = bool(data.get("dry_run"))
                now = time.time()
                wstart = now - weeks * 7 * 86400
                per = {}
                for b in BOOKINGS:
                    if not isinstance(b.get("created"), (int, float)) or b["created"] < wstart:
                        continue
                    lst = next((l for l in LISTINGS if l["id"] == b.get("listing_id")), None)
                    if not lst:
                        continue
                    o = lst.get("owner")
                    if not (isinstance(o, str) and o.startswith("acct-")):
                        continue
                    d = per.setdefault(o, {"created": 0, "confirmed": 0, "cancelled": 0, "gross": 0.0})
                    d["created"] += 1
                    esc = b.get("escrow")
                    amt = b.get("amount") or 0
                    if esc == "RELEASED":
                        d["confirmed"] += 1
                    elif esc in ("REFUNDED", "CANCELLED"):
                        d["cancelled"] += 1
                    if esc in ("HELD", "RELEASED"):
                        d["gross"] += amt
                active = sum(1 for l in LISTINGS if not l.get("archived"))
                results = []
                for o, d in sorted(per.items()):
                    a = ACCOUNTS.get(o)
                    if not (a and a.get("email_verified") and a.get("email")
                            and a.get("marketing_email") is not False):
                        continue
                    wk_end = time.strftime('%Y-%m-%d', time.gmtime(now))
                    wk_start = time.strftime('%Y-%m-%d', time.gmtime(wstart))
                    _unsub_url = PUBLIC_URL_DIGEST + "/accounts/notify/unsubscribe?u=%s&t=%s" % (
                        urlquote(o), _unsub_token(o))
                    tmpl = emailkit_digest("organizer", wk_start, wk_end,
                                           d["created"], d["confirmed"], d["cancelled"],
                                           d["gross"], active, unsub_url=_unsub_url,
                                           loc=('de' if a.get("email_lang") == "de" else "en"))
                    if dry:
                        results.append({"to": a["email"], "would_send": True, **d})
                    else:
                        _send_email(a["email"], tmpl["subject"], tmpl)
                        results.append({"to": a["email"], "sent": True, **d})
                return self._json(200, {"ok": True, "window_days": weeks * 7,
                    "dry_run": dry, "sent": len(results), "results": results})
        if path == "/admin/sync-escrow":
            # M7: mirror sync - the CHAIN is the source of truth for escrow
            # state. Pulls public escrow state from a Midnight indexer for every
            # booking carrying an escrow_ref and mirrors it 1:1 into the hub:
            #   chain RELEASED/REFUNDED + hub HELD  -> hub updated (forward)
            #   chain HELD + hub RELEASED/REFUNDED  -> REFUSED (never downward)
            #   conflicting final states            -> REFUSED (needs operator)
            # WAIVED bookings are untouched (no escrow rail). Ledger entries
            # carry NO amount key (must not double-count volume totals).
            from midnight_indexer import EscrowIndexerClient, IndexerError
            with LOCK:
                if not _auth_allow("admin", _source_of(self)):
                    return self._json(429, {"error": "admin rate limit reached for your source, retry later"})
            admin = self.headers.get("X-Admin-Key", "")
            if not admin or not hmac.compare_digest(admin, ADMIN_KEY):
                return self._json(403, {"error": "admin key required (X-Admin-Key)"})
            indexer_url = str(data.get("indexer_url", "")).strip()
            if not indexer_url.startswith(("http://", "https://")):
                return self._json(400, {"error": "indexer_url required (http(s)://)"})
            want = data.get("booking_ids")
            if want is not None and (not isinstance(want, list)
                                     or not all(isinstance(x, str) for x in want)):
                return self._json(400, {"error": "booking_ids must be a list of booking ids"})
            with LOCK:
                targets = [dict(b) for b in BOOKINGS
                           if b.get("escrow_ref")
                           and b.get("escrow") in ("HELD", "RELEASED", "REFUNDED")
                           and (want is None or b["id"] in want)]
                if want is not None:
                    found = {b["id"] for b in targets}
                    missing = [x for x in want if x not in found]
                else:
                    missing = []
            results = []
            for snap in targets:  # chain reads happen OUTSIDE the lock
                ref = snap["escrow_ref"]
                client = EscrowIndexerClient(indexer_url, ref["contract"])
                try:
                    chain = client.escrow(ref["escrow_id"])
                except IndexerError as ex:
                    results.append({"booking_id": snap["id"], "action": "error",
                                    "error": str(ex), "hub_state": snap["escrow"]})
                    continue
                hub_state, chain_state = snap["escrow"], chain["state_name"]
                if chain_state == hub_state:
                    results.append({"booking_id": snap["id"], "action": "in-sync",
                                    "hub_state": hub_state, "chain_state": chain_state})
                    continue
                # C7 safety rule: never overwrite downward or across final states.
                # M16 carve-out: chain REFUNDED while hub says RELEASED is a
                # legal forward transition - on-chain, RELEASED -> REFUNDED is
                # reachable ONLY via mutualRefund (both role commitments proven
                # in-circuit), so the chain truth is mirrored, not refused.
                # W3.1 dispute path: HELD -> DISPUTED (either party opens);
                # DISPUTED -> {ARB_RELEASED, ARB_REFUNDED} (arbiter ruling or
                # the arbiter-timeout liveness hatch). ARB_* are terminal.
                # The reverse moves are unreachable by any circuit and remain
                # refused for operator investigation.
                _FWD = {
                    "HELD": {"RELEASED", "REFUNDED", "DISPUTED"},
                    "DISPUTED": {"ARB_RELEASED", "ARB_REFUNDED"},
                    "RELEASED": {"REFUNDED"},  # M16 mutual refund carve-out
                }
                forward_ok = chain_state in _FWD.get(hub_state, set())
                if not forward_ok:
                    results.append({"booking_id": snap["id"], "action": "refused",
                                    "hub_state": hub_state, "chain_state": chain_state,
                                    "reason": "downward/conflicting overwrite refused - divergence needs operator investigation (C7)"})
                    continue
                with LOCK:  # forward transition: chain wins
                    b = next((x for x in BOOKINGS if x["id"] == snap["id"]), None)
                    if b is None or b["escrow"] != hub_state:
                        results.append({"booking_id": snap["id"], "action": "error",
                                        "error": "booking changed during sync"})
                        continue
                    b["escrow"] = chain_state
                    LEDGER.append({"ts": time.time(), "kind": "escrow_sync",
                                   "booking": b["id"], "from": hub_state,
                                   "to": chain_state, "chain_tx": chain["tx"]})
                    _persist_locked()
                results.append({"booking_id": snap["id"], "action": "updated",
                                "hub_state": hub_state, "chain_state": chain_state,
                                "chain_tx": chain["tx"]})
            for x in missing:
                results.append({"booking_id": x, "action": "not-found"})
            return self._json(200, {"synced": sum(1 for r in results if r["action"] == "updated"),
                                    "indexer": indexer_url, "results": results,
                                    "note": "chain is source of truth; downward overwrites refused (C7)"})
        return self._json(404, {"error": "not found"})

    def do_DELETE(self):
        self._t0 = time.time()  # H12: latency start
        # H7: account self-deletion (GDPR-style erasure). The money trail
        # (LEDGER + booking records) survives BY DESIGN — pseudonymous refs,
        # needed for escrow auditability. Owned listings are archived, not
        # destroyed (bookers keep escrow resolution; owner can no longer be
        # relinked because the account is gone).
        path = urlparse(self.path).path
        _g4 = 1200000 if (path == "/branding/image" or (path.startswith("/listings/") and path.endswith("/image"))) else 65536  # G4; exemption: owner image uploads
        if int(self.headers.get("Content-Length", 0)) > _g4:
            return self._json(413, {"error": "request body too large (max %d bytes)" % _g4})
        try:
            n = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(n)
            data = json.loads(raw) if raw.strip() else {}
        except Exception as ex:
            return self._json(400, {"error": str(ex)})
        if path == "/accounts/me":
            # H5 lesson: count the attempt BEFORE validation — failed deletes
            # count, so brute-forcing the token wall dies at the limit.
            with LOCK:
                if not _auth_allow("delete", _source_of(self)):
                    return self._json(429, {"error": "delete rate limit reached for your source, retry later"})
            cred = self.headers.get("X-Hub-Token", "")
            p, err = None, "missing X-Hub-Token"
            if cred:
                for act in ("list", "book"):
                    p, err = hublib.verify_token(BOOKING_KEY, cred, act, single_use=False)
                    if p: break
            if p:
                p, err = _gen_check(p)
            if not p or not str(p.get("sub", "")).startswith("acct-"):
                return self._json(401, {"error": err or "account token required",
                    "hint": "send a login token as X-Hub-Token"})
            aid = p["sub"]
            confirm = str(data.get("confirm", "")).strip()
            with LOCK:
                if aid not in ACCOUNTS:
                    return self._json(404, {"error": "no account"})
                if confirm != aid:
                    return self._json(400, {"error": "deletion needs typed confirmation: send {\"confirm\": \"<your account id>\"} in the body"})
                n_archived = 0
                for l in LISTINGS:
                    if l.get("owner") == aid and not l.get("archived"):
                        l["archived"] = True
                        n_archived += 1
                del ACCOUNTS[aid]
                LOGIN_CHALLENGES.pop(aid, None)
                _persist_locked()
            return self._json(200, {"ok": True, "account_id": aid,
                "listings_archived": n_archived,
                "note": "account erased (incl. recovery email); owned listings archived; "
                        "the public ledger keeps its pseudonymous refs for escrow auditability; "
                        "every token of this account is now invalid"})
        return self._json(404, {"error": "unknown DELETE route"})

    def log_message(self, *a): pass

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    globals()["_MCP_HUB_PORT"] = port  # Phase D: MCP loopback target = the port we actually serve
    # H4: single-instance guard. Two hubs sharing one state.json on different
    # ports would interleave writes and corrupt it (the Makefile port guard
    # cannot catch same-state-different-port starts). Take a non-blocking
    # flock on <state>.lock and HOLD the fd for the process lifetime — closing
    # it would release the lock. tools/restore_backup.py probes this same lock
    # before restoring. Exit 79 (78 = corrupt state fail-closed).
    import fcntl
    _H4_LOCK_FD = open(os.path.abspath(STATE_FILE) + ".lock", "a+")
    try:
        fcntl.flock(_H4_LOCK_FD, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"REFUSING to start: state lock is held — another hub is likely "
              f"running on this state ({STATE_FILE}). Stop it first, or if this "
              f"is a stale lock after a crash, remove the .lock file.",
              file=sys.stderr)
        sys.exit(79)
    _load_state()
    _s6_recompute_aggregates()  # S6: rebuild weighted/channel-split aggregates from history
    print(f"agent-hub-v2 (open/fair) on :{port} - fee {FEE_PCT}%, env {RUN_ENV}, state {STATE_FILE}")
    class HubServer(ThreadingHTTPServer):
        # B6-lesson: default backlog (5) refuses burst connections (B2 caught -1
        # transports at 40 parallel signups). Agentverse/SDK traffic arrives in
        # bursts — a public marketplace hub must queue them instead.
        request_queue_size = 128
        daemon_threads = True

    HubServer(("0.0.0.0", port), Handler).serve_forever()
