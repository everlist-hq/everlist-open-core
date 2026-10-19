# Embed EverList checkout on any website

Two lines. Your site stays the storefront; EverList stays the register
(listing, escrow, credentials, emails). No account, no API key, no backend
changes on your side.

## The snippet

```html
<script src="https://everlist.network/book.js" async></script>
<button data-everlist-book="LISTING-ID" data-qty="1">Book with EverList</button>
```

- `LISTING-ID` — your listing's id (`even-…`, `cls-…`; it's in every listing
  URL and in your listing's manage reply).
- `data-qty` — optional, spots to book (default 1).

Clicking opens the hosted EverList checkout window (popup; if the browser
blocks it, checkout opens in the same tab — nobody loses the flow).

Multiple buttons? Works out of the box — one per listing:

```html
<button data-everlist-book="even-12">Book Saturday</button>
<button data-everlist-book="even-13">Book Sunday</button>
```

## What the buyer sees

1. Checkout window: your listing's facts, total, payment terms (fee honesty —
   the full quote is shown before anything happens).
2. Name + email → 6-digit code arrives by email (one email = one EverList
   account, reusable everywhere).
3. Code confirmed → booking created through the real EverList engine
   (escrow semantics identical to booking in chat or via API).
4. One-time booking credentials are shown once in the window AND emailed —
   the buyer is never locked out.

## What you (the merchant) see

Your booking surfaces show the buyer's email + booking id + escrow status,
same as any other booking. Your site itself receives an origin-checked
postMessage `{type:'everlist:checkout', event:'booked', booking_id}` —
**booking secrets never touch your page**, so embedding adds zero liability.

Prefer JavaScript? Skip the markup:

```js
EverListBook.open("even-12", {
  qty: 2,
  onBooked: (msg) => console.log("booked:", msg.booking_id)
});
```

## Testing locally

Run a hub (`make up` → `http://localhost:8802`), then point the script at it:

```html
<script src="http://localhost:8802/book.js" async></script>
<button data-everlist-book="even-1">Book (local)</button>
```

`book.js` derives the hub origin from its own script URL — production and
local use the same embed.

## Honest limits today (v1, demo rail)

- **Free listings** book end-to-end (escrow WAIVED — nothing to pay).
- **Paid listings refuse checkout for now** with a clear pointer: real
  card/Apple Pay arrives with the licensed fiat-provider rail (checkout
  never moves money it can't settle). Paid bookings keep working via chat,
  SDK, and direct API in the meantime.
- The window labels the rail honestly in-product; no surprises for buyers.

## Troubleshooting

| Symptom | Meaning |
| --- | --- |
| Window shows "listing changed" | The listing was archived/edited/re-priced after the session opened — start checkout again |
| "event full" at confirm | Someone took the last spot mid-checkout (races resolve through the real engine; retry if the organizer frees a spot) |
| Code rejected | Codes expire after 15 min — tap **Resend** (watch the cooldown) |
| Wrong email typo'd | Start checkout again with the right address; sessions are single-email |

Normative API contract: [SPEC.md §25](../../SPEC.md) · status endpoint:
`GET /checkout/sessions/{sid}`.
