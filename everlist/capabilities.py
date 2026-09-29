"""EverList capability skill - the single source of truth for what EverList
can and cannot do, served DETERMINISTICALLY (owner law 2026-09-29: the LLM
never states policy or invents features; it routes to these answers).

Structure:
  CAN      - real capabilities, each with the standard how-to line
  CANNOT   - honest standard answers (admit -> why -> nearest real alternative)
  SUMMARY  - compact catalog injected into the brain's system prompt
  unknown() - the honest fallback line for anything not in the catalog

Every entry must stay true to the actual command surface in chatlib.py;
new capability added later = one entry here (brain, chat, docs all read it).
"""

# ---------------------------------------------------------------- CAN ----
# (id, trigger-keywords, standard answer)
CAN = [
    ("search",
     ("find", "search", "looking for", "events", "gigs", "jobs", "shows"),
     "Search is what I do best: tell me what you're after ('jazz tonight', "
     "'free yoga this weekend') and the board fills up. Say 'book 1' on any "
     "result."),
    ("transfer_booking",
     ("transfer my booking", "transfer booking", "give my booking",
      "change name on booking", "umbuchen"),
     "Transfers work right in chat: 'transfer <booking-id> <their-name>' "
     "hands the booking to them - the old key stops working, a new one is "
     "shown once. Everything else (payment protection, refund window) stays "
     "the same. Find the id with 'my-bookings'."),
    ("book",
     ("book", "reserve", "signup spot"),
     "Booking works right in chat: pick one from the board ('book 2') or say "
     "'book <listing> <your-name>'. Paid ones settle through escrow - your "
     "money stays locked safely until the event has ended."),
    ("my_bookings",
     ("my bookings", "my booking", "bookings", "where did i book"),
     "'my-bookings' shows everything you've booked - ids, dates, escrow "
     "state."),
    ("list_create",
     ("list", "post", "sell", "offer", "organize", "host"),
     "Posting is a chat flow: say 'list' and we'll build it together (or "
     "'list <title>, price <n>, date <date>, location <city>'). Your listing "
     "is live in seconds; edit/delete/archive anytime."),
    ("list_manage",
     ("edit", "delete", "archive", "unarchive", "change price", "update"),
     "You manage your listings right here: 'edit <id> price: 5', 'delete "
     "<id>', 'archive <id>' (hides it, bookings stay valid), 'unarchive <id>'. "
     "'my-listings' shows what's yours."),
    ("account",
     ("account", "signup", "register", "login", "logout", "password"),
     "Accounts live in the chat: 'signup' creates one (no email forms), "
     "'login <code>' returns to it on any device, 'logout' ends the session. "
     "First bookings get a one-time human check by the operator - just ask."),
    ("escrow",
     ("escrow", "protected", "safe", "scam", "trust"),
     "Protected payment is the point of EverList: your money sits in escrow "
     "until the event has ended - the organizer can't touch it before, and "
     "it auto-refunds if the event doesn't happen."),
    ("fees",
     ("fee", "fees", "cost", "price of everlist", "commission"),
     "Simple fee model: listing and searching are free; bookings carry a flat "
     "fee shown upfront - no surprises."),
    ("notify",
     ("notify", "notification", "email me", "newsletter"),
     "'notify on' emails you about activity on your listings and bookings; "
     "'notify off' stops it."),
    ("rate",
     ("rate", "review", "feedback"),
     "After an event you can rate it ('rate <booking>') - honest reviews keep "
     "the marketplace healthy."),
    ("payout",
     ("payout", "get paid", "money out", "withdraw"),
     "Organizers receive money to a coin key you set once: 'set-payout "
     "<key>'. Payouts then go straight to that key."),
    ("deals",
     ("private deal", "deal", "negotiate", "discount"),
     "Organizers can run private deals for special prices or groups - ask me "
     "about the private-deal flow and I'll walk you through it."),
    ("language",
     ("language", "german", "deutsch", "english", "sprache"),
     "'lang de' or 'lang en' - the chat and the site speak both."),
]

# ------------------------------------------------------------- CANNOT ----
# (id, trigger-keywords, standard honest answer: admit -> why -> alternative)
CANNOT = [
    ("pets",
     ("dog", "pets", "cat", "animals allowed", "haustier", "hund"),
     "That's each organizer's house rule, not a marketplace rule - it's "
     "usually in the listing description. If it isn't stated, the contact "
     "option on the listing page is the way to ask."),
    ("refund_self",
     ("refund me", "get my money back", "r\u00fcckerstattung", "money back"),
     "Refunds follow the escrow: if the event doesn't happen, protected "
     "bookings auto-refund. If you cancel yourself, the organizer's policy "
     "applies - your booking shows it: 'booking <id>'."),
    ("reschedule",
     ("reschedule", "move my booking", "different date", "verschieben"),
     "I can't move a booking yet - but rebooking is instant: 'book <n>' for "
     "the other date."),
    ("direct_payment",
     ("pay directly", "pay cash", "paypal", "cash to organizer", "bar zahlen"),
     "No - payment always runs through escrow; that's what makes the "
     "protection work. Direct deals void your protection."),
    ("resale",
     ("sell my tickets", "resell", "weiterverkaufen", "tickets verkaufen"),
     "Resale isn't built yet. You can edit or delete your own listing and "
     "post a fresh one ('edit <id> ...')."),
    ("group_discount",
     ("group discount", "gruppenrabatt", "discount", "rabatt"),
     "That's between you and the organizer - the contact option on the "
     "listing page is the way to ask. Private deals exist for organizers: "
     "'private deal' flow."),
]

UNKNOWN_LINE = (
    "That's not something EverList does (yet) - here's what I can do: "
    "search and book listings, post and manage your own, accounts, escrow "
    "payments, notifications and more ('help' for the full list)."
)


def summary() -> str:
    """Compact capability summary for the brain's system prompt (routing)."""
    can = ", ".join(c[0] for c in CAN)
    cannot = ", ".join(c[0] for c in CANNOT)
    return (
        "CAPABILITY CATALOG (ground truth - never claim anything beyond it):\n"
        "CAN: " + can + ".\n"
        "CANNOT (answer honestly, offer the alternative if the user asks): "
        + cannot + "."
    )


def answer_for(text: str):
    """Deterministic lookup: returns the standard answer for a capability
    question, or None. CAN entries win only for meta-style questions (the
    chat tiers handle searches/bookings before this ever runs)."""
    low = (text or "").lower()
    best = None
    best_len = 0
    for _cid, kws, ans in CANNOT:
        for k in kws:
            if k in low and len(k) > best_len:
                best, best_len = ans, len(k)
    if best:
        return best
    for _cid, kws, ans in CAN:
        for k in kws:
            if k in low and len(k) > best_len:
                best, best_len = ans, len(k)
    return best
