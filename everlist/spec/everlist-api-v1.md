# EverList API — Normative Spec v1

> Derived from the live OpenAPI 3.1.0 contract served at `GET /openapi.json`.
> **This file is generated** by `tools/gen_spec.py` — do not hand-edit. Regenerate and
> commit in the same change as any API modification (no-drift rule).
>
> Versioning: v1.x is additive only (old conformant clients must keep working).
> Breaking changes require a new major version, a migration guide, and a >=6-month
> machine-readable deprecation window on v1. Trust-critical invariants (fee honesty,
> escrow-state validity, arithmetic integrity `fee + payout = amount`, capacity
> atomicity) are version-stable and non-negotiable.
> Governance: docs/api-standard-governance.md (EverList repo docs).

**Title:** EverList Hub API  
**Contract version:** agent-hub/0.2  
**Description:** Open, community-driven commerce hub for AI agents. Credentials travel ONLY in the X-Hub-Token header; writes carry an Idempotency-Key. Normative contract: SPEC.md. Schema note (run #9 H13b): core response schemas live under components/schemas (Listing, Booking, OrderList, LedgerEntry, Error, ...), sampled from live-wire responses; vertical-specific request fields come from /verticals. Error strings remain non-normative.

## Endpoints (64 paths)

### `/openapi.json`

#### `GET /openapi.json` — This contract (OpenAPI 3.1)

**Responses:**

- `200`: This contract document (`application/json`: `OpenAPI`)

### `/manifest.json`

#### `GET /manifest.json` — Legacy manifest alias

### `/registry`

#### `GET /registry` — Open hub registry (self-listed)

### `/verticals`

#### `GET /verticals` — Vertical schema registry

**Responses:**

- `200`: Vertical schema registry (`application/json`: `Verticals`)

### `/search`

#### `GET /search` — Search listings (q, from/to date, min/max_price, tags=, sort, near=lat,lon, radius_km=, after/before=HH:MM, ...)

from/to = YYYY-MM-DD on the listing date (dateless listings excluded); tags=comma,any-of; sort=date|price|newest|distance (newest = creation order reversed); geo: near=lat,lon + optional radius_km= (listings without lat/lon excluded); time: after=/before=HH:MM zero-padded 24h on the listing time (time-less listings excluded); sort=distance requires near=; matched listings carry distance_km; sponsorship: admin-granted listings ride the LAST page position (capped 1), labeled sponsored=true

**Responses:**

- `200`: Search results (`application/json`: `ListingList`)

### `/listings`

#### `GET /listings` — Public listings (query: vertical, archived)

?archived=1 is OWNER-ONLY (auth required)

**Responses:**

- `200`: Listing collection (`application/json`: `ListingList`)

#### `POST /listings` — Create listing (manage_code ONCE; visibility:private adds a one-time claim_code)

optional payment_terms {rail: escrow|instant, refund_window_hours 1-720, deposit_required <= price}; omitted = vertical default (escrow, 72h events/services, 168h food); optional require_verified_buyer: true gates booking to Tier-2-verified accounts (SPEC section 22)

**Responses:**

- `201`: Listing created (manage_code shown once) (`application/json`: `ListingCreated`)
- `409`: cap reached (honest counts: cap, active) or duplicate of an active listing (existing id)

### `/.well-known/agent-hub.json`

#### `GET /.well-known/agent-hub.json` — Discovery manifest

**Responses:**

- `200`: Discovery manifest (`application/json`: `Manifest`)

### `/.well-known/ucp`

#### `GET /.well-known/ucp` — UCP vendor profile (PA-5, spec draft)

UCP business profile declaring ONLY EverList vendor capabilities (network.everlist.events.*); NO dev.ucp.* wire-format claims - UCP checkout adapters are a tracked build item (PA-6). Schemas: /ucp/events-capabilities.json

### `/.well-known/x402.json`

#### `GET /.well-known/x402.json` — x402 payment discovery (DL-1)

machine-readable payment terms at the standard agents-probe location; built from the same constants as the live 402 on /premium/events

### `/access`

#### `POST /access` — Bootstrap tokens for an agent identity (interim open)

acct- principals refused; accounts use /accounts/login

### `/accounts/email/bind`

#### `POST /accounts/email/bind` — Bind recovery email (code sent)

### `/accounts/email/recover`

#### `POST /accounts/email/recover` — Request recovery code (anti-enumeration)

### `/accounts/email/recover/confirm`

#### `POST /accounts/email/recover/confirm` — Confirm recovery -> NEW account code

### `/accounts/email/verify`

#### `POST /accounts/email/verify` — Verify email code

### `/accounts/lang`

#### `POST /accounts/lang` — Email language preference (email_lang: 'en'|'de') - booking mails, digest, codes

### `/accounts/login`

#### `POST /accounts/login` — Login (ed25519 challenge-response or legacy code)

### `/accounts/logout-all`

#### `POST /accounts/logout-all` — Revoke all tokens (generation bump)

### `/accounts/me`

#### `DELETE /accounts/me` — Account self-deletion (GDPR-style; ledger survives pseudonymously)

### `/accounts/notify`

#### `POST /accounts/notify` — Booking-notification preference (notify_email: true|false)

### `/accounts/notify/unsubscribe`

#### `GET /accounts/notify/unsubscribe` — Unsubscribe landing page (signed link from email footer)

#### `POST /accounts/notify/unsubscribe` — One-click unsubscribe (RFC 8058)

### `/accounts/payout`

#### `POST /accounts/payout` — Register organizer payout coin PUBLIC key (64-hex; secrets never accepted)

### `/accounts/rotate`

#### `POST /accounts/rotate` — Rotate account code (old code dies instantly)

### `/accounts/signup`

#### `POST /accounts/signup` — Create account (PoW-gated; keypair or legacy code)

### `/accounts/verify-midnight`

#### `POST /accounts/verify-midnight` — Tier-2 sign-in: verify a Midnight credential (admitted + not revoked) and mark the account verified_by: midnight-zk

fail-closed; mode (chain|simulated) labels the verification source

### `/accounts/vouch`

#### `POST /accounts/vouch` — Operator vouches for a human (pilot-era)

### `/admin/sponsor`

#### `POST /admin/sponsor` — Sponsor a listing (admin): labeled, capped placement — organic order is never for sale

body {listing_id, days 1..60}; sponsored listing appears LAST per results page with sponsored=true; grant is admin-only

### `/admin/sync-escrow`

#### `POST /admin/sync-escrow` — Mirror sync: pull chain escrow state into the hub (admin)

X-Admin-Key required; chain is source of truth; downward overwrites refused (C7)

### `/admin/tokens`

#### `POST /admin/tokens` — Operator: mint action tokens (admin key)

### `/auth/challenge`

#### `GET /auth/challenge` — Signup PoW / login challenges

?kind=signup | ?kind=login&pubkey=<64hex>

### `/book`

#### `POST /book` — Create booking (escrow HELD / WAIVED at price 0 / DIRECT on the instant rail; testnet instant bookings accept an optional X-PAYMENT EIP-3009 header -> verified payer wallet bound for S6 review integrity)

Idempotency-Key supported; verified-human gate applies; optional escrow_ref {contract, escrow_id, tx} links the on-chain escrow (escrow-rail paid bookings only; REQUIRED for escrow-rail paid bookings when chain gating is enabled via HUB_INDEXER_URL - SPEC section 24). Custom payment terms (SPEC §19): paid bookings on listings with non-default terms must echo accepted_payment_terms exactly (409 otherwise; the error returns the terms). Listings with require_verified_buyer accept ONLY Tier-2-verified accounts (server-side; the human_verified stub never counts, SPEC section 22)

**Responses:**

- `201`: Booking created (booking_secret shown once) (`application/json`: `BookingCreated`)

### `/book/{id}`

#### `GET /book/{id}` — Private booking details

credential = booking secret (shown once at creation), via X-Hub-Token header

**Responses:**

- `200`: Private booking details (booking secret) (`application/json`: `PrivateBooking`)

### `/book/{id}/cancel`

#### `POST /book/{id}/cancel` — Buyer cancels pre-fulfillment (full refund)

**Responses:**

- `200`: Buyer cancelled (full refund) (`application/json`: `CancelResponse`)

### `/book/{id}/confirm`

#### `POST /book/{id}/confirm` — Owner confirms booking (escrow RELEASE)

**Responses:**

- `200`: Owner confirmed (escrow RELEASED) (`application/json`: `ConfirmResponse`)

### `/book/{id}/dispute`

#### `POST /book/{id}/dispute` — Either party freezes a HELD booking for arbitration (DISPUTED; no release or refund until resolved)

**Responses:**

- `200`: Dispute opened (funds frozen for arbitration) (`application/json`: `CancelResponse`)

### `/book/{id}/rate`

#### `POST /book/{id}/rate` — Buyer rates a settled booking 1-5 (once)

buyer's own book token; escrow must be RELEASED, WAIVED or DIRECT (instant = settled at booking); free (amount 0; channel set by economic value, not the mutable escrow label - run #5) ratings go to a separate free-feedback channel, paid aggregates are amount-weighted, self-reviews rejected (S6); ledger untouched

**Responses:**

- `200`: Rating recorded (`application/json`: `RateResponse`)

### `/book/{id}/transfer`

#### `POST /book/{id}/transfer` — Buyer transfers booking to a new attendee name (pre-fulfillment; rotates secret + cancel token)

### `/bookings`

#### `GET /bookings` — Your bookings (principal-scoped)

**Responses:**

- `200`: Principal-scoped bookings (`application/json`: `OrderList`)

### `/bookings/{id}`

#### `GET /bookings/{id}` — Booking status (buyer or listing owner)

unknown-or-not-yours = indistinguishable 404 (no existence oracle)

### `/branding`

#### `GET /branding` — Public page branding (partner-editable fields only)

#### `POST /branding` — Update branding (owner acct- token ONLY; fixed rails rejected)

fields: brand_name, tagline, hero_text, logo_url(https), location, accent(#RRGGBB), accent2(#RRGGBB), theme(dark|light), about_text, site_url(https), instagram_url(https, instagram.com host), lang(de|en); MERGE: absent=unchanged, empty=cleared

### `/branding/image`

#### `POST /branding/image` — Upload branding image (owner acct- token ONLY)

body {kind: logo|hero, data_url: data:image/png|jpeg|webp;base64,...}; SVG refused; decoded caps logo 90KB / hero 420KB; stored same-origin as data URL

### `/catalogs`

#### `POST /catalogs` — Create a versioned catalog tree for a merchant (depth<=3, items need title, price numeric)

one catalog per merchant; replace via POST /catalogs/{id}/replace bumps version and REQUIRES content change (same content_hash -> 409); public GET /catalogs/{id} returns version+content_hash+tree, ?fields=summary omits the tree, ?since_hash=<hash> -> 304 when unchanged; catalog items NEVER appear in /listings or /search listing results - they surface as grouped catalog_items

### `/challenge`

#### `GET /challenge` — Registry ownership proof (echo nonce)

### `/checkout/sessions`

#### `POST /checkout/sessions` — Create embeddable checkout session (TRACK E)

Public listings carry checkout:{eligible,mode}, a non-secret UI hint; sessions revalidate all walls. Public, rate-limited. Creates a hosted checkout session (chk- capability URL) for a PUBLIC listing. FREE listings: demo rail, escrow WAIVED at booking (no money moves). PAID listings: wallet rail (E7) on testnet hubs (HUB_PAY_MODE=testnet) - the session face carries payment_request (receiver/units/asset) and the verify step takes the buyer's EIP-3009 signature; money moves exactly when the booking lands. Paid sessions are refused honestly on non-testnet hubs (TRACK E4/E5 fiat deferred). Payment terms + total are snapshotted at create; listing changes stale the session.

**Responses:**

- `201`: Checkout session created (`application/json`: `CheckoutSession`)

### `/checkout/sessions/{sid}`

#### `GET /checkout/sessions/{sid}` — Checkout session status

Capability-URL face: status, masked email, listing snapshot, total. No secrets.

**Responses:**

- `200`: Checkout session status (`application/json`: `CheckoutSession`)

### `/checkout/sessions/{sid}/pay`

#### `POST /checkout/sessions/{sid}/pay` — Checkout pay step

POST {email, name} binds the buyer and emails a 6-digit code (cooldown + per-address mail cap).

**Responses:**

- `200`: Checkout email bound, code sent (`application/json`: `CheckoutPending`)

### `/checkout/sessions/{sid}/verify`

#### `POST /checkout/sessions/{sid}/verify` — Checkout verify step

POST {code} proves mailbox control (bind-or-create account, Tier-1 email law) and books through the shared booking engine. PAID sessions (wallet rail): POST {code, payment} - the buyer's EIP-3009 payment (base64 x402 envelope, signed for the session face's payment_request) is verified by the booking engine itself; money moves exactly when the booking lands (atomic pay+book; a proven code without payment returns honest 402 and burns no attempt). The 201 carries the one-time booking credentials (buyer channel only; merchant postMessage gets booking_id only).

**Responses:**

- `201`: Checkout booking created (`application/json`: `CheckoutBooked`)

### `/escrow/{id}/proof`

#### `GET /escrow/{id}/proof` — Verify-without-trust escrow proof (DL-2)

?contract=<address> (or HUB_ESCROW_CONTRACT); escrow re-read from indexer(s), dual-source when configured, FAIL-CLOSED on disagreement; no booking details, pseudonymous booking_ref only

### `/ledger`

#### `GET /ledger` — Public append-only money ledger (pseudonymous)

**Responses:**

- `200`: Public money ledger (`application/json`: `Ledger`)

### `/listing/draft`

#### `POST /listing/draft` — Paste-a-flyer OR share-a-link: free text or an existing page URL -> prefilled listing DRAFT (never creates; organizer confirms then POSTs /listings); engine: regex always, LLM-assisted when the enrichment chain is live, URL pages read schema.org JSON-LD first (response names engine+model)

body {text} or {url} (not both); deterministic extraction (title/date/time/price/location); URL fetches are SSRF-walled (public hosts only, 1MB cap, html-only) and rate-limited per source; response carries needs_confirm [date,price] — never trust AI-extracted prices without review

### `/listings/{id}`

#### `GET /listings/{id}` — One listing, full rich record (private deals need ?claim= or X-Claim-Code)

404 unknown / 410 archived

**Responses:**

- `200`: Full listing record (`application/json`: `Listing`)

### `/listings/{id}/image`

#### `POST /listings/{id}/image` — Set or clear the listing photo (owning acct- token, or list token + manage_code; clear:true removes)

body {data_url: data:image/png|jpeg|webp;base64,...} or {clear:true}; SVG refused; decoded cap 380KB; stored same-origin as a data URL (CSP img-src data:)

### `/listings/{id}/manage`

#### `POST /listings/{id}/manage` — Edit/archive/unarchive/make_private/make_public/delete a listing (plus archive_series/delete_series on recurring series)

series acts: action=archive_series hides every dated sibling at once; delete_series removes the family — both refuse while any member holds active bookings

### `/mcp`

#### `POST /mcp` — Model Context Protocol endpoint (JSON-RPC 2.0): initialize / tools/list / tools/call over the 15 hub tools (everlist_* protocol family + storefront contract family)

thin adapter onto this same REST contract; auth = X-Hub-Token header only (a token in tool arguments is ignored - MCP-ARGS law)

### `/merchants`

#### `POST /merchants` — Create a merchant profile (unique kebab slug; fulfillment pickup/delivery/shipping/onsite; locations + promos; per-owner cap); update/delete via POST /merchants/{slug} action=update|delete (owner-walled; delete refuses 409 while active listings are attached and cascades the catalog)

owner = token principal; listings attach via {merchant: slug} at create or manage action attach_merchant/detach_merchant (ownership-walled both ways); public GET /merchants/{slug} returns profile + the merchant's OWN uncapped listings + catalog summary; feed quota (default 2/merchant) applies only to the general /listings feed

### `/openapi-actions.json`

#### `GET /openapi-actions.json` — ChatGPT Actions spec (OpenAPI 3.0 subset)

Curated OpenAPI 3.0 subset for ChatGPT Custom GPT Actions (owner order 2026-11-14: fully in ChatGPT); mirrors the REAL hub wire only (search/book/checkout/cancel/proof - same gates, zero drift); auth = static GPT-config token (never in transcripts, M-B law); payment honesty: free listings book fully in-chat (WAIVED), paid listings surface ONE hosted checkout link; rail label from the same PAY_MODE constant as the live x402 face

### `/orders`

#### `GET /orders` — Incoming orders for listings you own

### `/organizer/batch-settle`

#### `POST /organizer/batch-settle` — W3.3: organizer batch settle - release ALL your HELD/WAIVED bookings in ONE call (per-booking chain gate verify-then-flip; DISPUTED untouched)

pilot hub surface for the on-chain batchRelease2 circuit; per-booking walls all applied

**Responses:**

- `200`: Organizer batch settle: release ALL your HELD/WAIVED bookings in one call (per-booking chain gate; disputes untouched) (`application/json`: `BatchSettle`)

### `/organizer/earnings`

#### `GET /organizer/earnings` — W3.4: organizer earnings view (private mirror of settled payouts; owner-only)

totals are exactly what proveEarningsFloor hides - owner token required

**Responses:**

- `200`: Organizer earnings view (private mirror) (`application/json`: `EarningsView`)

### `/organizer/earnings-proof`

#### `POST /organizer/earnings-proof` — W3.4: revenue-floor proof - PASS/FAIL only for verifier-chosen {min_volume, min_settlements}; actual totals never disclosed

pilot mirror check with the honesty of earnings.compact proveEarningsFloor; on-chain proof is the organizer act (M25/M26)

**Responses:**

- `200`: Revenue-floor proof (pass/fail only) (`application/json`: `EarningsProof`)

### `/premium/events`

#### `GET /premium/events` — Premium data (x402 payment)

402 + payment instructions without a valid payment header

### `/ticket/{token}`

#### `GET /ticket/{token}` — T5 door ticket honest status (capability URL)

projection: event, date, qty, door name (buyer-chosen choice), redeemed state; capability law - the token holder IS the attendee (you_are_buyer), you_are_owner only with the listing owner token; page is noindex/no-store

### `/ticket/{token}/name`

#### `POST /ticket/{token}/name` — Door-display name via the ticket capability itself

holder of the ticket token IS the attendee (capability law); body display_name + display_choice full|first|guest; name is explicit UGC, never silently persisted identity

### `/ticket/{token}/redeem`

#### `POST /ticket/{token}/redeem` — ONE-TIME door check-in (owner action)

owner proof like /confirm: admin confirm token, owning acct- list token, or listing manage_code; first scan wins, later scans honestly report first_time=false with the original time

### `/ucp/events-capabilities.json`

#### `GET /ucp/events-capabilities.json` — UCP vendor capability schemas v0.1.0

JSON Schema for the five network.everlist.events.* capabilities; semantics mirror SPEC 19 (booking=agreement, escrow default, permissionless timeout refund, auto-release to a payout key fixed at creation); served fail-closed from the bundled ucp/ file

## Schemas (20)

### `Booking`

object
- `id`: string (required)
- `listing_id`: string (required)
- `vertical`: string (required)
- `escrow`: string (required)
- `amount`: number (required) — total in major units; 0 = free booking
- `hub_fee`: number (required)
- `owner_payout`: number (required)
- `quantity`: integer
- `created`: number (required) — unix epoch seconds
- `booked_by`: string (required) — pseudonymous booking principal
- `payment_terms`: `PaymentTerms` (required)
- `attendee`: string — events identity field: anon- unlinkable ref in public views, real value only in private details
- `buyer`: string — food/p2p identity field: anon- ref in public views, real value only in private details
- `client`: string — services identity field: anon- ref in public views, real value only in private details
- `worker`: string — jobs identity field (community vertical): anon- ref in public views
- `rating`: integer
- `escrow_ref`: object — optional on-chain escrow link {contract, escrow_id, tx}

### `BookingCreated`

POST /book 201: Booking plus one-time credentials (booking_secret shown ONCE).

### `CancelResponse`

object
- `ok`: boolean (required)
- `id`: string (required)
- `escrow`: string (required)

### `ConfirmResponse`

object
- `ok`: boolean (required)
- `id`: string (required)
- `escrow`: string (required)
- `owner_received`: number
- `confirmation`: string

### `EarningsProof`

object
- `met`: boolean (required)
- `thresholds`: object (required)
- `protocol`: string
- `zk_contract`: string

### `EarningsView`

object
- `settledCount`: integer (required)
- `totalVolume`: number (required)
- `events`: integer
- `principal`: string
- `note`: string
- `zk`: string

### `Error`

object
- `error`: string (required)
- `hint`: string
- `note`: string

### `Ledger`

object
- `ledger`: array (required)
- `totals`: object (required)
- `settled_volume`: number
- `settled_hub_fees`: number
- `note`: string
- `privacy`: string

### `LedgerEntry`

object
- `kind`: string — absent = booking entry; else x402_settlement | escrow_sync
- `ts`: number (required) — unix epoch seconds
- `booking`: string
- `amount`: number
- `hub_fee`: number
- `owner_payout`: number
- `escrow`: string
- `released_to`: string
- `detail`: object — x402_settlement: {fingerprint, tx, value, payer (pseudonymized anon-*), network}
- `from`: string — escrow_sync: prior hub state
- `to`: string — escrow_sync: new chain state
- `chain_tx`: string — escrow_sync: chain transaction

### `Listing`

object
- `id`: string (required) — public listing id (even-/food-/srv- prefixed)
- `vertical`: string (required)
- `title`: string (required)
- `price`: number (required) — major units; 0 = free
- `date`: string — YYYY-MM-DD (capacity verticals)
- `location`: string
- `capacity`: integer
- `registered`: integer — server-counted registrations (tracks_capacity verticals)
- `created`: number — server-stamped creation epoch (unix seconds); surfaces publicly as offers.validFrom in Event JSON-LD
- `available`: boolean
- `visibility`: string
- `owner`: string — owner-anonymized: pseudonymous principal (agent name / acct- ref), never personal data
- `category`: string
- `tags`: array
- `image`: string — listing photo as data URL - set ONLY via POST /listings/{id}/image (B2 upload-only law)
- `description`: string
- `url`: string
- `merchant`: string
- `provider`: string
- `preparation_minutes`: integer
- `duration_minutes`: integer
- `payment_terms`: `PaymentTerms`
- `rating_sum`: integer
- `rating_count`: integer
- `free_rating_sum`: integer
- `free_rating_count`: integer
- `checkout`: object — Non-secret UI hint only; session creation and booking revalidate all gates.
- `price_preview`: object — Server-calculated one-place total, same rounding as hosted checkout. Organizer commission is not added to the buyer price.
- `demo`: boolean — true only on seed/curated-example supply (server-derived, never client-claimed) — demo boards must never read as live organizers (A6 2026-11-04)

### `ListingCreated`

object
- `ok`: boolean (required)
- `id`: string (required)
- `manage_code`: string (required)
- `manage_note`: string (required)

### `ListingList`

object
- `count`: integer (required)
- `offset`: integer (required)
- `limit`: integer (required)
- `returned`: integer (required)
- `listings`: array (required)

### `Manifest`

object
- `protocol`: string (required)
- `api_contract`: string (required)
- `hub`: string
- `open_source`: string
- `license_model`: string

### `OpenAPI`

object
- `openapi`: string (required)
- `info`: object (required)
- `paths`: object (required)

### `OrderList`

object
- `bookings`: array (required)
- `principal`: string (required)
- `note`: string (required)

### `PaymentTerms`

object
- `rail`: string (required)
- `refund_window_hours`: integer (required)
- `deposit_required`: number (required)

### `PrivateBooking`

object
- `id`: string (required)
- `private_details`: `Booking` (required)

### `RateResponse`

object
- `ok`: boolean (required)
- `id`: string (required)
- `rating`: integer (required)
- `channel`: string (required)
- `aggregate`: string
- `note`: string

### `VerticalSchema`

object
- `required`: array (required)
- `optional`: array (required)
- `categories`: array (required)
- `tracks_capacity`: boolean
- `field_types`: object
- `booking`: object (required)

### `Verticals`

object
- `verticals`: object (required)
