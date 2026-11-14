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
        'description': ('Search public listings. q = free text; optional vertical, category, '
                        'tags (comma-separated), from/to (YYYY-MM-DD), min_price/max_price (numbers), sort.'),
        'inputSchema': {
            'type': 'object',
            'properties': {
                'q': {'type': 'string', 'description': 'free-text query'},
                'vertical': {'type': 'string', 'description': 'events|food|services|jobs|classes|p2p'},
                'category': {'type': 'string'},
                'tags': {'type': 'string', 'description': 'comma-separated tags'},
                'from': {'type': 'string', 'description': 'YYYY-MM-DD'},
                'to': {'type': 'string', 'description': 'YYYY-MM-DD'},
                'min_price': {'type': 'number'},
                'max_price': {'type': 'number'},
                'sort': {'type': 'string', 'enum': ['date', 'price', 'newest'],
                         'description': 'date | price | newest (invalid values are rejected)'},
            },
        },
    },
    {
        'name': 'everlist_listing',
        'description': 'One listing, full record: title, date, place, price, escrow terms, capacity, rating.',
        'inputSchema': {
            'type': 'object',
            'required': ['id'],
            'properties': {'id': {'type': 'string', 'description': 'listing id, e.g. even-1 or jobs-1'}},
        },
    },
    {
        'name': 'everlist_book',
        'description': ('Book (or apply+pay for jobs) a listing into escrow. Requires a hub token '
                        'in the X-Hub-Token header on the MCP request (header-only auth; obtain via '
                        'the hub auth contract: POST /accounts/signup + /accounts/login, keypair '
                        'stays client-side). human_verified must be true (interim credential; '
                        'production = zk-personhood). Booking fields depend on the vertical '
                        '(attendee / buyer+quantity / client / worker).'),
        'inputSchema': {
            'type': 'object',
            'required': ['listing_id'],
            'properties': {
                'listing_id': {'type': 'string'},
                'quantity': {'type': 'integer', 'minimum': 1},
                'human_verified': {'type': 'boolean'},
                'attendee': {'type': 'string'},
                'buyer': {'type': 'string'},
                'client': {'type': 'string'},
                'worker': {'type': 'string'},
                # M-B: token removed from the advertised schema — auth is
                # header-only (X-Hub-Token); a token in tool arguments lands
                # in the client LLM's visible transcript (injection/exfil risk)
                'idempotency_key': {'type': 'string'},
            },
        },
    },
    {
        'name': 'everlist_booking',
        'description': 'Booking status for the token holder: escrow state, amount, confirmation code.',
        'inputSchema': {
            'type': 'object',
            'required': ['booking_id'],
            'properties': {
                'booking_id': {'type': 'string'},
            },
        },
    },
]

# ---------------- PA-9 (2026-11-14): storefront-contract face ----------------
# Tool names follow the Claude commerce-agents StorefrontBackend contract so an
# Anthropic Managed Agent can drive this hub via its manifest (the manifest
# default-disables every tool not listed, so the everlist_* family and this
# family coexist on one endpoint). Laws unchanged: translator only; header-only
# auth; checkout NEVER moves money - it stages a Track E hosted-checkout session
# and returns the capability URL with the hub rail label VERBATIM; the cart is
# an ephemeral session draft (TTL 1h), never a booking, never persisted.

STOREFRONT_TOOLS = [
    {'name': 'search_products',
     'description': ('Search EverList listings (events, classes, food, services, jobs, p2p). '
                     'Returns best matches with price, date, location, and spots left.'),
     'inputSchema': {'type': 'object', 'required': ['query'],
                     'properties': {'query': {'type': 'string'},
                                    'limit': {'type': 'integer', 'minimum': 1, 'maximum': 20}}}},
    {'name': 'get_product_details',
     'description': 'One listing in full: description, date, place, price, capacity left, escrow terms.',
     'inputSchema': {'type': 'object', 'required': ['product_id'],
                     'properties': {'product_id': {'type': 'string'}}}},
    {'name': 'get_cart',
     'description': ('The session draft (one item). Nothing is booked and no money has '
                     'moved until the hosted checkout page is completed.'),
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'add_to_cart',
     'description': ('Stage one listing in the session draft (replaces any previous draft: '
                     'EverList books one listing per booking). Does NOT book.'),
     'inputSchema': {'type': 'object', 'required': ['product_id'],
                     'properties': {'product_id': {'type': 'string'},
                                    'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 12}}}},
    {'name': 'update_cart_item',
     'description': 'Change the draft quantity.',
     'inputSchema': {'type': 'object', 'required': ['quantity'],
                     'properties': {'quantity': {'type': 'integer', 'minimum': 1, 'maximum': 12}}}},
    {'name': 'remove_from_cart',
     'description': 'Empty the session draft.',
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'checkout',
     'description': ('Stage the hosted booking page for the draft. Returns checkout_url for the '
                     'customer to open; the rail label states exactly how money moves (or that '
                     'it is a free/demo booking). No order is placed and no money moves here.'),
     'inputSchema': {'type': 'object', 'properties': {}}},
    {'name': 'get_order_status',
     'description': ('Booking and escrow state for the token holder (X-Hub-Token header). '
                     'Includes the wallet-less verify URL when an escrow reference exists.'),
     'inputSchema': {'type': 'object', 'required': ['booking_id'],
                     'properties': {'booking_id': {'type': 'string'}}}},
    {'name': 'search_policies',
     'description': ('Hub commerce policies: fee policy, payment mode, escrow and refund '
                     "rules; optionally one listing's terms via listing_id."),
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
                'the organizer confirms or the refund window lapses.'),
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
