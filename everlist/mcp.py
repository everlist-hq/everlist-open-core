import json
import os
import time
import urllib.request
import urllib.error
import uuid

# Phase D (owner-approved 2026-09-17): MCP face over the hub's own REST API.
# Hand-rolled Model Context Protocol (streamable-HTTP shape, JSON-RPC 2.0).
# Why no SDK: the box runs system Python with zero extra deps; the protocol
# surface we need (initialize / tools/list / tools/call / ping) is small and
# stable. Why loopback: EVERY tool call is forwarded to this same process's
# real REST endpoint, so all hub laws apply unchanged - auth (X-Hub-Token),
# per-source rate limits, validation, idempotency, escrow accounting. The MCP
# layer owns NO logic of its own; it is a translator, nothing more.

PROTOCOL_VERSION = '2025-03-26'
SUPPORTED = {'2025-03-26', '2024-11-05'}
SERVER_INFO = {'name': 'everlist-hub', 'version': 'agent-hub/0.2-mcp'}

TOOLS = [
    {
        'name': 'everlist_contract',
        'description': ('Discovery: the EverList hub manifest - payment mode, fee policy, '
                        'identity requirements, verticals, and endpoint map. Call this first.'),
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'everlist_verticals',
        'description': 'Vertical schema registry: required/optional fields, categories, and booking shape per vertical (events, food, services, jobs, classes, p2p).',
        'inputSchema': {'type': 'object', 'properties': {}},
    },
    {
        'name': 'everlist_search',
        'description': ('Search the public EverList catalog of bookable listings (events, classes, '
                        'food, services, jobs, p2p). Free-text q plus optional filters: vertical, '
                        'category, tags (comma-separated), date window from/to (YYYY-MM-DD), '
                        'min_price/max_price, sort (date|price|newest). Returns matches with id, '
                        'title, date, location, price, spots left. Next step: everlist_listing for '
                        'one full record, then everlist_book. Storefront twin: search_products '
                        '(same handler, Claude commerce contract name).'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string', 'description': 'free-text query'},
                'vertical': {'type': 'string', 'description': 'events|food|services|jobs|classes|p2p'},
                'category': {'type': 'string', 'description': 'vertical-specific category (see everlist_verticals)'},
                'tags': {'type': 'string', 'description': 'comma-separated tags'},
                'from': {'type': 'string', 'description': 'window start, YYYY-MM-DD (inclusive)'},
                'to': {'type': 'string', 'description': 'window end, YYYY-MM-DD (inclusive)'},
                'min_price': {'type': 'number', 'description': 'minimum price in major units (0 = free included)'},
                'max_price': {'type': 'number', 'description': 'maximum price in major units'},
                'sort': {'type': 'string', 'enum': ['date', 'price', 'newest'],
                         'description': 'date | price | newest (invalid values are rejected)'},
            },
        },
    },
    {
        'name': 'everlist_listing',
        'description': ('Fetch ONE full listing record by id: title, description, '
                        'date/time, location, price, escrow payment terms (rail + refund window), '
                        'capacity and spots left, rating. Use after everlist_search to inspect '
                        'before everlist_book. Storefront twin: get_product_details (same handler).'),
        'inputSchema': {
            'type': 'object',
            'required': ['id'],
            'properties': {'id': {'type': 'string', 'description': 'listing id, e.g. even-1 or jobs-1'}},
        },
    },
    {
        'name': 'everlist_book',
        'description': ('CREATE a booking (or apply+pay for jobs) holding funds in Midnight-blockchain '
                        'escrow; read status afterward with everlist_booking. Requires a hub token '
                        'in the X-Hub-Token header on the MCP request (header-only auth; obtain via '
                        'the hub auth contract: POST /accounts/signup + /accounts/login, keypair '
                        'stays client-side). human_verified must be true (interim credential; '
                        'production = zk-personhood). Booking fields depend on the vertical '
                        '(attendee / buyer+quantity / client / worker).'),
        'inputSchema': {
            'type': 'object',
            'required': ['listing_id'],
            'properties': {
                'listing_id': {'type': 'string', 'description': 'listing id from everlist_search/everlist_listing, e.g. even-1'},
                'quantity': {'type': 'integer', 'minimum': 1, 'description': 'seats/units to book (capacity verticals)'},
                'human_verified': {'type': 'boolean', 'description': 'must be true: interim human-attestation (production = zk-personhood)'},
                'attendee': {'type': 'string', 'description': 'events vertical: attendee identity ref'},
                'buyer': {'type': 'string', 'description': 'food/p2p vertical: buyer identity ref'},
                'client': {'type': 'string', 'description': 'services vertical: client identity ref'},
                'worker': {'type': 'string', 'description': 'jobs vertical: worker identity ref (the human who takes the job)'},
                # M-B: token removed from the advertised schema — auth is
                # header-only (X-Hub-Token); a token in tool arguments lands
                # in the client LLM's visible transcript (injection/exfil risk)
                'idempotency_key': {'type': 'string', 'description': 'optional client key: retry-safe booking (same key = same booking, never a duplicate)'},
            },
        },
    },
    {
        'name': 'everlist_booking',
        'description': ('READ the status of ONE booking you created: escrow state (HELD/RELEASED/'
                        'REFUNDED/...), amount, confirmation code. Naming: everlist_book CREATES, '
                        'everlist_booking READS - booking_id comes from the everlist_book response. '
                        'Auth: same X-Hub-Token header as everlist_book. Storefront twin: '
                        'get_order_status.'),
        'inputSchema': {
            'type': 'object',
            'required': ['booking_id'],
            'properties': {
                'booking_id': {'type': 'string', 'description': 'booking id from the everlist_book response, e.g. bk-...'},
            },
        },
    },
    {'description': 'LIST YOUR bookings: every booking made with your principal, with escrow '
                    'state, amount and listing. Use it to find booking_ids before everlist_booking '
                    '/ everlist_cancel. Auth: your usual X-Hub-Token header (book or list token). '
                    'Principal-scoped: you see only your own.',
     'inputSchema': {'properties': {}, 'type': 'object'},
     'name': 'everlist_bookings'},
    {'description': 'CANCEL a booking before fulfillment: full refund out of escrow (escrow flips '
                    'to REFUNDED). Works while escrow is HELD and inside the listing refund window '
                    '(free/WAIVED bookings cancel too; instant-rail DIRECT bookings have no refund '
                    "window). Auth for THIS call: THIS booking's cancel_token as the X-Hub-Token "
                    'header. The chain claim deadline is authoritative - past it only the contract '
                    'auto-release applies.',
     'inputSchema': {'properties': {'booking_id': {'description': 'booking id to cancel, e.g. '
                                                                  'bk-...',
                                                   'type': 'string'}},
                     'required': ['booking_id'],
                     'type': 'object'},
     'name': 'everlist_cancel'},
    {'description': 'ORGANIZER action: confirm fulfillment - escrow RELEASES to the organizer '
                    '(owner_received reports the payout; free/WAIVED bookings confirm too and no '
                    'money moves). Buyers correctly get a 403 - fulfillment belongs to the listing '
                    'owner. Auth: your organizer list token as the X-Hub-Token header (or an admin '
                    'confirm token). Instant-rail (DIRECT) bookings settled at booking and have '
                    'nothing to confirm.',
     'inputSchema': {'properties': {'booking_id': {'description': 'booking id to confirm, e.g. '
                                                                  'bk-...',
                                                   'type': 'string'}},
                     'required': ['booking_id'],
                     'type': 'object'},
     'name': 'everlist_confirm'},
    {'description': 'FREEZE a HELD booking for arbitration (DISPUTED): no release and no refund '
                    'while frozen; if the arbiter vanishes, arbiterTimeoutRefund returns buyer '
                    'funds after the deadline. Buyer side via MCP: your cancel_token (or book '
                    'token) as the X-Hub-Token header. Organizer side stays on REST (manage_code '
                    'never belongs in tool arguments - MCP-ARGS law). Only HELD bookings can be '
                    'disputed.',
     'inputSchema': {'properties': {'booking_id': {'description': 'booking id to freeze, e.g. '
                                                                  'bk-...',
                                                   'type': 'string'}},
                     'required': ['booking_id'],
                     'type': 'object'},
     'name': 'everlist_dispute'},
    {'description': 'RATE a settled booking 1-5 (once, buyer-only, owner-immutable). Opens after '
                    'settlement (escrow RELEASED / WAIVED / DIRECT). Paid reviews are '
                    'amount-weighted, self-reviews rejected; ratings touch no ledger entries. '
                    'Auth: your book token as the X-Hub-Token header.',
     'inputSchema': {'properties': {'booking_id': {'description': 'your settled booking id, e.g. '
                                                                  'bk-...',
                                                   'type': 'string'},
                                    'rating': {'description': '1-5 (integer)',
                                               'maximum': 5,
                                               'minimum': 1,
                                               'type': 'integer'}},
                     'required': ['booking_id', 'rating'],
                     'type': 'object'},
     'name': 'everlist_rate'},
    {'description': 'VERIFY-WITHOUT-TRUST: read the escrow straight from the Midnight indexer '
                    '(dual-source when configured, fail-closed) and get the raw chain projection + '
                    'verification metadata. No booking details, no identities - only what the '
                    'chain itself says. Public: no token needed. escrow_id and contract come from '
                    'a booking escrow_ref (everlist_booking / get_order_status responses) or the '
                    '/verify link.',
     'inputSchema': {'properties': {'contract': {'description': 'escrow contract address (optional '
                                                                'when the hub has '
                                                                'HUB_ESCROW_CONTRACT configured)',
                                                 'type': 'string'},
                                    'escrow_id': {'description': 'chain escrow id from the booking '
                                                                 'escrow_ref',
                                                  'minimum': 1,
                                                  'type': 'integer'}},
                     'required': ['escrow_id'],
                     'type': 'object'},
     'name': 'everlist_escrow_proof'},
]

# ---------------- PA-9 (2026-11-14): storefront-contract face ----------------
# Tool names follow the Claude commerce-agents StorefrontBackend contract so an
# Anthropic Managed Agent can drive this hub via its manifest (the manifest
# default-disables every tool not listed, so the everlist_* family and this
# family coexist on one endpoint).
# NOTE (Glama TDQS 2026-11-14): on a raw tools/list both families are visible
# and score as 'duplicates'. DO NOT collapse them: everlist_* = native hub
# protocol, storefront names = contract-mandated by the Claude commerce-agents
# StorefrontBackend spec. Every description cross-references its twin so
# agents never have to guess the boundary. Laws unchanged: translator only; header-only
# auth; checkout NEVER moves money - it stages a Track E hosted-checkout session
# and returns the capability URL with the hub rail label VERBATIM; the cart is
# an ephemeral session draft (TTL 1h), never a booking, never persisted.

STOREFRONT_TOOLS = [
    {'name': 'search_products',
     'description': ('Search EverList listings (events, classes, food, services, jobs, p2p). '
                     'Returns best matches with price, date, location, and spots left. '
                     'Storefront-contract alias of everlist_search (same handler) - use '
                     'whichever family your manifest enabled.'),
     'inputSchema': {'type': 'object', 'required': ['query'],
                     'properties': {'query': {'type': 'string', 'description': 'free-text search, e.g. "yoga class Vienna"'},
                                    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20, 'description': 'max matches to return'}}}},
    {'name': 'get_product_details',
     'description': ('Storefront-contract alias of everlist_listing (same handler): one listing in '
                     'full - description, date/time, place, price, capacity left, escrow terms '
                     '(rail + refund window). Inspect before add_to_cart.'),
     'inputSchema': {'type': 'object', 'required': ['product_id'],
                     'properties': {'product_id': {'type': 'string', 'description': 'listing id from search_products, e.g. even-1'}}}},
    {'name': 'get_cart',
     'description': ('The session draft (at most ONE staged listing). Nothing is booked and no '
                     'money has moved until the hosted checkout page is completed. Pair: '
                     'add_to_cart stages, update_cart_item edits quantity, remove_from_cart '
                     'empties, checkout hands off.'),
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'add_to_cart',
     'description': ('Stage one listing in the session draft (replaces any previous draft: '
                     'EverList books one listing per booking). Does NOT book. Follow with '
                     'checkout when the customer is ready.'),
     'inputSchema': {'type': 'object', 'required': ['product_id'],
                     'properties': {'product_id': {'type': 'string', 'description': 'listing id from search_products, e.g. even-1'},
                                    'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 12, 'description': 'seats/units (capped at 12)'}}}},
    {'name': 'update_cart_item',
     'description': ('Change the quantity (1-12) of the staged draft item. EverList carts hold '
                     'exactly ONE listing, so quantity is the only editable field; get_cart '
                     'shows the draft. Session-local (TTL 1h) - nothing is booked and no money '
                     'moves until checkout completes.'),
     'inputSchema': {'type': 'object', 'required': ['quantity'],
                     'properties': {'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 12, 'description': 'new seats/units for the staged listing'}}}},
    {'name': 'remove_from_cart',
     'description': ('Empty the session draft cart (EverList drafts hold at most one listing). '
                     'Nothing is booked and no money has moved; add_to_cart can stage a '
                     'different listing afterward.'),
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'checkout',
     'description': ('Stage the hosted booking page for the draft. Returns checkout_url for the '
                     'customer to open; the rail label states exactly how money moves (or that '
                     'it is a free/demo booking). No order is placed and no money moves here.'),
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'get_order_status',
     'description': ('Storefront-contract alias of everlist_booking (same handler): booking and '
                     'escrow state for the token holder (X-Hub-Token header), including the '
                     'wallet-less verify URL when an escrow reference exists. Create a booking '
                     'via everlist_book or the cart flow (add_to_cart -> checkout).'),
     'inputSchema': {'type': 'object', 'required': ['booking_id'],
                     'properties': {'booking_id': {'type': 'string', 'description': 'booking id from the booking/checkout response, e.g. bk-...'}}}},
    {'name': 'search_policies',
     'description': ('Hub commerce policies: fee policy, payment mode, escrow and refund '
                     "rules; optionally one listing's terms via listing_id (e.g. refund window "
                     'before you book).'),
     'inputSchema': {'type': 'object', 'properties': {'listing_id': {'type': 'string'}}}},
]

TOOLS = TOOLS + STOREFRONT_TOOLS


class MCPError(Exception):
    def __init__(self, code, message, rid=None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.rid = rid


def _api(hub_port, method, path, payload=None, token=None, idem=None, timeout=10):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['X-Hub-Token'] = token
    if idem:
        headers['Idempotency-Key'] = idem
    r = urllib.request.Request(
        'http://127.0.0.1:%d%s' % (hub_port, path),
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or '{}')
        except Exception:
            return e.code, {}


def _rpc(result, rid):
    return {'jsonrpc': '2.0', 'id': rid, 'result': result}


def _rpc_err(code, message, rid):
    return {'jsonrpc': '2.0', 'id': rid, 'error': {'code': code, 'message': message}}


def _handle_one(handler, data, hub_port):
    if not isinstance(data, dict) or data.get('jsonrpc') != '2.0':
        return _rpc_err(-32600, 'not a JSON-RPC 2.0 request', data.get('id') if isinstance(data, dict) else None), None
    method = data.get('method', '')
    rid = data.get('id')
    params = data.get('params') or {}

    if method == 'initialize':
        ver = params.get('protocolVersion')
        use = ver if ver in SUPPORTED else PROTOCOL_VERSION
        result = {
            'protocolVersion': use,
            'capabilities': {'tools': {}},
            'serverInfo': SERVER_INFO,
            'instructions': (
                'EverList: a listing = something with a date where a human is needed or wanted. '
                'Call everlist_contract first (payment mode + fees are declared, never hidden). '
                'Search, inspect, then book with everlist_book; escrow holds the funds until '
                'the organizer confirms or the refund window lapses. The full booking lifecycle lives on this face: everlist_bookings lists yours; everlist_cancel (buyer, cancel_token as header) refunds; everlist_confirm (organizer) releases; everlist_dispute freezes; everlist_rate rates after settlement; everlist_escrow_proof verifies the chain without trusting this hub.'),
        }
        handler._mcp_session = getattr(handler, '_mcp_session', None) or ('mcp-' + uuid.uuid4().hex)
        return _rpc(result, rid), {'Mcp-Session-Id': handler._mcp_session}

    if method == 'notifications/initialized':
        return None, None  # notification: no response

    if method == 'ping':
        return _rpc({}, rid), None

    if method == 'tools/list':
        return _rpc({'tools': TOOLS}, rid), None

    if method == 'tools/call':
        name = params.get('name', '')
        args = params.get('arguments') or {}
        try:
            result = _call_tool(handler, hub_port, name, args)
            return _rpc({'content': [{'type': 'text', 'text': json.dumps(result, ensure_ascii=False)}],
                         'isError': bool(result.get('isError'))}, rid), None
        except MCPError as e:
            # FED5 (run #5): request-SHAPE problems (unknown tool, bad id format)
            # are JSON-RPC protocol errors (-32602), not isError results;
            # tool EXECUTION failures (hub 4xx/5xx, missing auth) stay isError
            # results per the MCP spec.
            if e.code == -32602:
                return _rpc_err(-32602, e.message, rid), None
            return _rpc({'content': [{'type': 'text', 'text': e.message}], 'isError': True}, rid), None
        except Exception as e:  # never leak a traceback to the wire
            return _rpc({'content': [{'type': 'text', 'text': 'internal error: %s' % type(e).__name__}],
                         'isError': True}, rid), None

    if rid is None:
        return None, None  # unknown notification: ignore per spec
    return _rpc_err(-32601, 'unknown method: %s' % method, rid), None


def _call_tool(handler, hub_port, name, args):
    if name == 'everlist_contract':
        st, m = _api(hub_port, 'GET', '/.well-known/agent-hub.json')
        if st != 200:
            raise MCPError(-32000, 'contract unavailable (HTTP %s)' % st)
        return m
    if name == 'everlist_verticals':
        st, v = _api(hub_port, 'GET', '/verticals')
        if st != 200:
            raise MCPError(-32000, 'verticals unavailable (HTTP %s)' % st)
        return v
    if name == 'everlist_search':
        qs = '&'.join('%s=%s' % (k, urllib.request.quote(str(v), safe=''))
                      for k, v in args.items()
                      if k in ('q', 'vertical', 'category', 'tags', 'from', 'to',
                               'min_price', 'max_price', 'sort') and v not in (None, ''))
        st, res = _api(hub_port, 'GET', '/search' + (('?' + qs) if qs else ''))
        if st != 200:
            raise MCPError(-32000, 'search failed (HTTP %s): %s' % (st, res.get('error', '')))
        return res
    if name == 'everlist_listing':
        lid = str(args.get('id', '')).strip()
        if not lid or '/' in lid or '..' in lid:
            raise MCPError(-32602, 'invalid listing id')
        st, res = _api(hub_port, 'GET', '/listings/' + lid)
        if st == 404:
            raise MCPError(-32000, 'no such listing: %s' % lid)
        if st == 410:
            raise MCPError(-32000, 'listing archived: %s' % lid)
        if st != 200:
            raise MCPError(-32000, 'fetch failed (HTTP %s)' % st)
        return res
    if name == 'everlist_book':
        # M-B: header-only auth — never accept a token from tool arguments
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass the X-Hub-Token header (see everlist_contract auth)')
        payload = {'listing_id': args.get('listing_id'), 'human_verified': bool(args.get('human_verified'))}
        if args.get('quantity') is not None:
            payload['quantity'] = args.get('quantity')
        for f in ('attendee', 'buyer', 'client', 'worker'):
            if args.get(f):
                payload[f] = args[f]
        idem = args.get('idempotency_key') or ('mcp-' + uuid.uuid4().hex)
        st, res = _api(hub_port, 'POST', '/book', payload, token=token, idem=idem)
        if st in (200, 201):
            return res
        return {'isError': True, 'http_status': st, 'error': res.get('error', 'booking failed'),
                'hint': res.get('hint', res.get('note', ''))}
    if name == 'everlist_booking':
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass the X-Hub-Token header')
        bid = str(args.get('booking_id', '')).strip()
        if not bid or '/' in bid or '..' in bid:
            raise MCPError(-32602, 'invalid booking id')
        st, res = _api(hub_port, 'GET', '/bookings/' + bid, token=token)
        if st != 200:
            raise MCPError(-32000, 'booking lookup failed (HTTP %s): %s' % (st, res.get('error', '')))
        return res
    if name == 'everlist_bookings':
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass the X-Hub-Token header')
        st, res = _api(hub_port, 'GET', '/bookings', token=token)
        if st != 200:
            raise MCPError(-32000, 'bookings lookup failed (HTTP %s): %s' % (st, res.get('error', '')))
        return res
    if name == 'everlist_cancel':
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass THIS booking cancel_token as the X-Hub-Token header')
        bid = str(args.get('booking_id', '')).strip()
        if not bid or '/' in bid or '..' in bid:
            raise MCPError(-32602, 'invalid booking id')
        st, res = _api(hub_port, 'POST', '/book/%s/cancel' % bid, {}, token=token)
        if st != 200:
            return {'isError': True, 'http_status': st, 'error': res.get('error', 'cancel refused'),
                    'hint': res.get('hint', res.get('note', ''))}
        return res
    if name == 'everlist_confirm':
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass your organizer list token as the X-Hub-Token header')
        bid = str(args.get('booking_id', '')).strip()
        if not bid or '/' in bid or '..' in bid:
            raise MCPError(-32602, 'invalid booking id')
        st, res = _api(hub_port, 'POST', '/book/%s/confirm' % bid, {}, token=token)
        if st != 200:
            return {'isError': True, 'http_status': st, 'error': res.get('error', 'confirm refused'),
                    'hint': res.get('hint', res.get('note', ''))}
        return res
    if name == 'everlist_dispute':
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass your cancel_token (or book token) as the X-Hub-Token header')
        bid = str(args.get('booking_id', '')).strip()
        if not bid or '/' in bid or '..' in bid:
            raise MCPError(-32602, 'invalid booking id')
        st, res = _api(hub_port, 'POST', '/book/%s/dispute' % bid, {}, token=token)
        if st != 200:
            return {'isError': True, 'http_status': st, 'error': res.get('error', 'dispute refused'),
                    'hint': res.get('hint', res.get('note', ''))}
        return res
    if name == 'everlist_rate':
        token = handler.headers.get('X-Hub-Token', '')
        if not token:
            raise MCPError(-32001, 'missing hub token: pass your book token as the X-Hub-Token header')
        bid = str(args.get('booking_id', '')).strip()
        if not bid or '/' in bid or '..' in bid:
            raise MCPError(-32602, 'invalid booking id')
        val = args.get('rating')
        if isinstance(val, bool) or not isinstance(val, int) or not (1 <= val <= 5):
            raise MCPError(-32602, 'rating must be an integer in [1, 5]')
        st, res = _api(hub_port, 'POST', '/book/%s/rate' % bid, {'rating': val}, token=token)
        if st != 200:
            return {'isError': True, 'http_status': st, 'error': res.get('error', 'rating refused'),
                    'hint': res.get('hint', res.get('note', ''))}
        return res
    if name == 'everlist_escrow_proof':
        eid = str(args.get('escrow_id', '')).strip()
        if not (eid.isdigit() and 1 <= int(eid) <= 999999999999):
            raise MCPError(-32602, 'escrow_id must be a positive integer (from the booking escrow_ref)')
        contract = str(args.get('contract', '')).strip()
        qs = ('?contract=' + urllib.request.quote(contract, safe='')) if contract else ''
        st, res = _api(hub_port, 'GET', '/escrow/%s/proof%s' % (eid, qs))
        if st != 200:
            raise MCPError(-32000, 'escrow proof unavailable (HTTP %s): %s' % (st, res.get('error', '')))
        return res
    sf_fn = _SF_HANDLERS.get(name)
    if sf_fn is not None:
        return sf_fn(handler, hub_port, args)
    raise MCPError(-32602, 'unknown tool: %s' % name)


# ---------------- PA-9 storefront implementations ----------------
_CARTS = {}  # Mcp-Session-Id -> draft; ephemeral, TTL-pruned, never persisted
_CART_TTL = 3600.0
_CART_MAX_QTY = 12
_PUBLIC_URL = os.environ.get('EVERLIST_PUBLIC_URL', 'https://everlist.network').rstrip('/')
_SF_CART_NOTE = ('Draft only - nothing is booked and no money has moved. '
                 'Call checkout to stage the hosted booking page.')


def _sf_session(handler):
    sid = handler.headers.get('Mcp-Session-Id', '') or getattr(handler, '_mcp_session', '')
    if not sid:
        sid = 'mcp-' + uuid.uuid4().hex
    handler._mcp_session = sid
    now = time.time()
    for k in [k for k, v in _CARTS.items() if now - v.get('ts', 0) > _CART_TTL]:
        _CARTS.pop(k, None)
    return sid


def _sf_token(handler):
    tok = handler.headers.get('X-Hub-Token', '')
    if not tok:
        auth = handler.headers.get('Authorization', '') or ''
        if auth.startswith('Bearer '):
            tok = auth[len('Bearer '):].strip()
    return tok


def _sf_product(l):
    left = None
    try:
        if l.get('capacity') is not None:
            left = max(int(l['capacity']) - int(l.get('registered') or 0), 0)
    except (TypeError, ValueError):
        left = None
    return {'product_id': l.get('id'), 'title': l.get('title'),
            'price': l.get('price'), 'currency': 'EUR',
            'date': l.get('date'), 'location': l.get('location'),
            'vertical': l.get('vertical'), 'category': l.get('category'),
            'description': (l.get('description') or '')[:200],
            'spots_left': left}


def _sf_cart_view(cart):
    if not cart or not cart.get('items'):
        return {'items': [], 'draft': True,
                'note': 'Draft empty. Nothing is booked; no money has moved.'}
    return {'items': [dict(cart['items'][0])], 'draft': True, 'note': _SF_CART_NOTE}


def _sf_search_products(handler, hub_port, args):
    q = urllib.request.quote(str(args.get('query', '')), safe='')
    limit = int(args.get('limit') or 8)
    st, res = _api(hub_port, 'GET', '/search?q=%s' % q)
    if st != 200:
        raise MCPError(-32000, 'search failed (HTTP %s): %s' % (st, res.get('error', '')))
    ls = res.get('listings') or []
    return {'products': [_sf_product(l) for l in ls[:max(1, min(limit, 20))]],
            'count': len(ls)}


def _sf_get_product_details(handler, hub_port, args):
    pid = str(args.get('product_id', '')).strip()
    if not pid or '/' in pid or '..' in pid:
        raise MCPError(-32602, 'invalid product id')
    st, res = _api(hub_port, 'GET', '/listings/' + pid)
    if st == 404:
        raise MCPError(-32000, 'no such listing: %s' % pid)
    if st != 200:
        raise MCPError(-32000, 'fetch failed (HTTP %s)' % st)
    res['product'] = _sf_product(res)
    return res


def _sf_get_cart(handler, hub_port, args):
    return _sf_cart_view(_CARTS.get(_sf_session(handler)))


def _sf_add_to_cart(handler, hub_port, args):
    pid = str(args.get('product_id', '')).strip()
    if not pid or '/' in pid or '..' in pid:
        raise MCPError(-32602, 'invalid product id')
    qty = int(args.get('quantity') or 1)
    if qty < 1 or qty > _CART_MAX_QTY:
        raise MCPError(-32602, 'quantity must be 1..%d' % _CART_MAX_QTY)
    st, l = _api(hub_port, 'GET', '/listings/' + pid)
    if st == 404:
        raise MCPError(-32000, 'no such listing: %s' % pid)
    if st != 200:
        raise MCPError(-32000, 'fetch failed (HTTP %s)' % st)
    sid = _sf_session(handler)
    _CARTS[sid] = {'items': [dict(_sf_product(l), quantity=qty)], 'ts': time.time()}
    return _sf_cart_view(_CARTS[sid])


def _sf_update_cart_item(handler, hub_port, args):
    sid = _sf_session(handler)
    cart = _CARTS.get(sid)
    if not cart or not cart.get('items'):
        raise MCPError(-32000, 'cart is empty: add a listing first')
    qty = int(args.get('quantity') or 1)
    if qty < 1 or qty > _CART_MAX_QTY:
        raise MCPError(-32602, 'quantity must be 1..%d' % _CART_MAX_QTY)
    cart['items'][0]['quantity'] = qty
    cart['ts'] = time.time()
    return _sf_cart_view(cart)


def _sf_remove_from_cart(handler, hub_port, args):
    _CARTS.pop(_sf_session(handler), None)
    return _sf_cart_view(None)


def _sf_checkout(handler, hub_port, args):
    sid = _sf_session(handler)
    cart = _CARTS.get(sid)
    if not cart or not cart.get('items'):
        raise MCPError(-32000, 'cart is empty: add a listing with add_to_cart first')
    it = cart['items'][0]
    payload = {'listing_id': it['product_id'], 'quantity': int(it.get('quantity') or 1)}
    st, res = _api(hub_port, 'POST', '/checkout/sessions', payload)
    if st == 409:
        return {'isError': True, 'error': res.get('error', 'checkout refused'),
                'hint': res.get('hint', ''), 'left': res.get('left'),
                'note': 'The hub refused this checkout; nothing was staged.'}
    if st != 201:
        raise MCPError(-32000, 'checkout staging failed (HTTP %s): %s' % (st, res.get('error', '')))
    _CARTS.pop(sid, None)
    url = res.get('url', '')
    return {'status': 'staged',
            'checkout_url': (url if url.startswith('http') else _PUBLIC_URL + url),
            'rail': res.get('rail', ''), 'exp': res.get('exp'),
            'listing_id': it['product_id'], 'quantity': payload['quantity'],
            'note': ('No money has moved. The customer completes booking (and payment, if '
                     'any) on the hosted page, where the escrow state is displayed. The rail '
                     "label above is the hub's own, verbatim.")}


def _sf_get_order_status(handler, hub_port, args):
    tok = _sf_token(handler)
    if not tok:
        raise MCPError(-32001, 'missing hub token: pass the X-Hub-Token header')
    bid = str(args.get('booking_id', '')).strip()
    if not bid or '/' in bid or '..' in bid:
        raise MCPError(-32602, 'invalid booking id')
    st, res = _api(hub_port, 'GET', '/bookings/' + bid, token=tok)
    if st != 200:
        raise MCPError(-32000, 'booking lookup failed (HTTP %s): %s' % (st, res.get('error', '')))
    ref = res.get('escrow_ref')
    if isinstance(ref, dict) and ref.get('contract') and ref.get('escrow_id'):
        res['verify_url'] = (_PUBLIC_URL + '/verify?contract=%s&escrow=%s'
                             % (ref['contract'], ref['escrow_id']))
    return res


def _sf_search_policies(handler, hub_port, args):
    st, c = _api(hub_port, 'GET', '/.well-known/agent-hub.json')
    if st != 200:
        raise MCPError(-32000, 'policy source unavailable (HTTP %s)' % st)
    out = {'fee_policy': c.get('fees') or c.get('fee_policy'),
           'payment': c.get('payment') or c.get('payment_mode'),
           'escrow': ('Funds are held in escrow until the organizer confirms the service '
                      'happened, or the refund window lapses (permissionless timeout '
                      'refund). After the claim deadline the booking auto-releases to '
                      'the organizer.'),
           'source': _PUBLIC_URL + '/how'}
    lid = str(args.get('listing_id', '')).strip()
    if lid and '/' not in lid and '..' not in lid:
        st2, l = _api(hub_port, 'GET', '/listings/' + lid)
        if st2 == 200:
            out['listing_terms'] = l.get('payment_terms') or l.get('terms')
    return out


_SF_HANDLERS = {
    'search_products': _sf_search_products,
    'get_product_details': _sf_get_product_details,
    'get_cart': _sf_get_cart,
    'add_to_cart': _sf_add_to_cart,
    'update_cart_item': _sf_update_cart_item,
    'remove_from_cart': _sf_remove_from_cart,
    'checkout': _sf_checkout,
    'get_order_status': _sf_get_order_status,
    'search_policies': _sf_search_policies,
}


def handle(handler, data, hub_port):
    """Entry point from app.py do_POST. Returns (status, body, extra_headers)."""
    t0 = time.time()
    if isinstance(data, list):  # JSON-RPC batching
        out = []
        for item in data:
            try:
                resp, hdrs = _handle_one(handler, item, hub_port)
                if resp is not None:
                    out.append(resp)
            except Exception:
                out.append(_rpc_err(-32603, 'internal error', item.get('id') if isinstance(item, dict) else None))
        if not out:
            return 202, {}, {}
        return 200, out, {}
    try:
        resp, hdrs = _handle_one(handler, data, hub_port)
    except Exception:
        rid = data.get('id') if isinstance(data, dict) else None
        resp, hdrs = _rpc_err(-32603, 'internal error', rid), None
    if resp is None:
        return 202, {}, (hdrs or {})
    return 200, resp, (hdrs or {})
