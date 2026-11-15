'''EverList StorefrontBackend (PA-10, 2026-11-15): the blueprint's StorefrontBackend
contract implemented over the EverList hub REST API. Reuses the PA-9 storefront
mappings (mcp.py); laws carried: rail labels verbatim, checkout never moves money,
no credential handling by the model. Orders are NotOffered without customer auth
(the blueprint's own pattern for systems the store does not offer);
fulfillment is NotOffered - events have no shipping.

The Agent SDK runtime drives this backend; a hosted UI consumes its event stream.
'''
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

from shopping_agent import (
    Cart,
    CartItem,
    CheckoutHandoff,
    Disclosure,
    DisclosureRow,
    Order,
    OrderItem,
    OrderStatus,
    Policy,
    Product,
    ProductDetails,
    SearchFilters,
    ShoppingSessionContext,
    StorefrontBackend,
    NotOffered,
    Unavailable,
    UserPreferences,
)

PUBLIC_URL = os.environ.get("EVERLIST_PUBLIC_URL", "https://everlist.network").rstrip("/")
_HUB = os.environ.get("EVERLIST_HUB_URL", "http://127.0.0.1:8951")
_TOKEN = os.environ.get("EVERLIST_HUB_TOKEN", "")
_CARTS: dict[str, dict[str, Any]] = {}
_CART_TTL = 3600.0
_CART_MAX_QTY = 12


def _api(method: str, path: str, body: dict | None = None, token: str | None = None):
    url = _HUB + path
    data = None
    headers = {"Accept": "application/json"}
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    if token:
        headers["X-Hub-Token"] = token
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode() or "{}")
        except Exception:
            return e.code, {}


def _product(l: dict) -> Product:
    left = None
    try:
        if l.get("capacity") is not None:
            left = max(int(l["capacity"]) - int(l.get("registered") or 0), 0)
    except (TypeError, ValueError):
        left = None
    attrs: dict[str, str] = {}
    if l.get("date"):
        attrs["date"] = str(l["date"])
    if l.get("time"):
        attrs["time"] = str(l["time"])
    if l.get("location"):
        attrs["location"] = str(l["location"])
    if l.get("vertical"):
        attrs["vertical"] = str(l["vertical"])
    if left is not None:
        attrs["spots_left"] = str(left)
    demo = "Curated example listing" if str(l.get("owner", "")).startswith("everlist-org-") else ""
    if demo:
        attrs["note"] = demo
    return Product(
        product_id=str(l.get("id") or l.get("slug")),
        title=str(l.get("title") or ""),
        price=float(l.get("price") or 0),
        currency="EUR",
        category=l.get("category"),
        attributes=attrs,
        in_stock=(left is None or left > 0),
        short_description=(l.get("description") or "")[:200] or None,
    )


def _cart_view(cart: dict | None) -> Cart:
    items = []
    if cart and cart.get("items"):
        for it in cart["items"]:
            items.append(CartItem(
                product_id=str(it["product_id"]),
                title=str(it.get("title") or ""),
                price=float(it.get("price") or 0),
                quantity=int(it.get("quantity") or 1),
                option_values={k: str(v) for k, v in (it.get("option_values") or {}).items()},
            ))
    return Cart(items=items, currency="EUR")


def _escrow_disclosure_body(l: dict) -> str:
    terms = l.get("payment_terms") or {}
    rail = str(terms.get("rail") or "")
    rw = terms.get("refund_window_days") or terms.get("refund_window")
    parts = ["Bookings settle in escrow: funds are held safely until the organizer "
             "confirms the service happened, or the refund window lapses."]
    if rw is not None:
        parts.append("Refund window: %s days." % rw)
    parts.append("After the claim deadline the booking auto-releases to the organizer.")
    if rail:
        parts.append("Payment rail (hub label, verbatim): %s" % rail)
    return " ".join(str(p) for p in parts)


class EverlistStorefrontBackend(StorefrontBackend):
    """StorefrontBackend over the EverList hub REST API.

    Honesty mapping:
      - checkout_handoff -> the hub's hosted checkout page (rail label verbatim,
        escrow state displayed); the URL never reaches the model.
      - get_orders -> NotOffered (no customer order history without credentials;
        order STATUS stays available by booking id).
      - get_fulfillment_options -> NotOffered (events have no shipping).
      - demo listings carry the 'Curated example listing' attribute.
    """

    async def search_products(self, session, query, filters=None, limit=8):
        q = urllib.parse.quote(str(query or ""), safe="")
        st, res = _api("GET", "/search?q=%s" % q)
        if st != 200:
            raise RuntimeError("search failed (HTTP %s)" % st)
        ls = res.get("listings") or []
        return [_product(l) for l in ls[: max(1, min(int(limit), 20))]]

    async def get_product_details(self, session, product_id):
        pid = str(product_id).strip()
        if not pid or "/" in pid or ".." in pid:
            raise ValueError("invalid product id")
        st, res = _api("GET", "/listings/" + pid)
        if st == 404:
            return None
        if st != 200:
            raise RuntimeError("listing fetch failed (HTTP %s)" % st)
        p = _product(res)
        det = ProductDetails(
            **p.model_dump(),
            long_description=(res.get("description") or None),
            specs={k: str(v) for k, v in {
                "date": res.get("date"), "time": res.get("time"),
                "location": res.get("location"), "category": res.get("category"),
                "vertical": res.get("vertical"),
            }.items() if v},
        )
        return det

    async def get_cart(self, session):
        return _cart_view(_CARTS.get(session.session_id))

    async def add_to_cart(self, session, product_id, quantity):
        pid = str(product_id).strip()
        if not pid or "/" in pid or ".." in pid:
            raise ValueError("invalid product id")
        qty = int(quantity)
        if qty < 1 or qty > _CART_MAX_QTY:
            raise ValueError("quantity must be 1..%d" % _CART_MAX_QTY)
        st, res = _api("GET", "/listings/" + pid)
        if st == 404:
            raise LookupError("no such listing: %s" % pid)
        if st != 200:
            raise RuntimeError("listing fetch failed (HTTP %s)" % st)
        p = _product(res)
        if not p.in_stock:
            raise Unavailable("%s has no spots left" % pid)
        _CARTS[session.session_id] = {
            "items": [{"product_id": p.product_id, "title": p.title,
                       "price": p.price, "quantity": qty,
                       "option_values": dict(p.option_values)}],
            "ts": time.time(),
        }
        return _cart_view(_CARTS[session.session_id])

    async def update_cart_item(self, session, product_id, quantity):
        cart = _CARTS.get(session.session_id)
        if not cart or not cart.get("items"):
            return _cart_view(None)
        pid = str(product_id).strip()
        qty = int(quantity)
        if qty < 1 or qty > _CART_MAX_QTY:
            raise ValueError("quantity must be 1..%d" % _CART_MAX_QTY)
        for it in cart["items"]:
            if it["product_id"] == pid:
                it["quantity"] = qty
                break
        cart["ts"] = time.time()
        return _cart_view(cart)

    async def remove_from_cart(self, session, product_id):
        cart = _CARTS.get(session.session_id)
        if cart:
            cart["items"] = [it for it in cart["items"] if it["product_id"] != str(product_id)]
            cart["ts"] = time.time()
        return _cart_view(cart)

    async def get_preferences(self, session):
        return UserPreferences(user_id=session.user_id)

    async def checkout_handoff(self, session, cart):
        if not cart.items:
            return []
        it = cart.items[0]
        payload = {"listing_id": it.product_id, "quantity": int(it.quantity)}
        st, res = _api("POST", "/checkout/sessions", payload)
        if st == 409:
            raise Unavailable(str(res.get("error") or "checkout refused"))
        if st != 201:
            raise RuntimeError("checkout staging failed (HTTP %s)" % st)
        url = str(res.get("url") or "")
        if not url.startswith("http"):
            url = PUBLIC_URL + url
        return [CheckoutHandoff(url=url,
                                label="Complete booking on everlist.network (escrow held)")]

    async def get_orders(self, session, limit=5):
        raise NotOffered("EverList does not keep customer order history for anonymous agent sessions")

    async def get_order(self, session, order_id):
        bid = str(order_id).strip()
        if not bid or "/" in bid or ".." in bid:
            return None
        st, res = _api("GET", "/bookings/" + bid, token=_TOKEN or None)
        if st != 200:
            return None
        ref = res.get("escrow_ref") or {}
        verify = None
        if ref.get("contract") and ref.get("escrow_id"):
            verify = PUBLIC_URL + "/verify?contract=%s&escrow=%s" % (ref["contract"], ref["escrow_id"])
        status_map = {"held": OrderStatus.PROCESSING, "released": OrderStatus.DELIVERED,
                      "refunded": OrderStatus.CANCELLED}
        return Order(
            order_id=bid,
            status=status_map.get(str(res.get("status") or "held"), OrderStatus.PROCESSING),
            placed_at=datetime_utc(),
            items=[OrderItem(product_id=str(res.get("listing_id") or bid),
                             title=str(res.get("listing_title") or "listing"),
                             quantity=int(res.get("quantity") or 1),
                             price=float(res.get("total") or 0))],
            total=float(res.get("total") or 0),
            currency="EUR",
            tracking_url=verify,
        )

    async def search_policies(self, session, query):
        st, c = _api("GET", "/.well-known/agent-hub.json")
        if st != 200:
            raise RuntimeError("policy source unavailable (HTTP %s)" % st)
        q = str(query or "").lower()
        pols = []
        escrow_txt = ("Funds are held in escrow until the organizer confirms the service "
                      "happened, or the refund window lapses (permissionless timeout refund). "
                      "After the claim deadline the booking auto-releases to the organizer.")
        if any(w in q for w in ("escrow", "refund", "money", "payment", "protect", "trust")):
            pols.append(Policy(policy_id="escrow", title="How escrow protects you",
                               category="payments", content=escrow_txt))
        fees = c.get("fees") or c.get("fee_policy")
        if fees and any(w in q for w in ("fee", "fees", "cost", "price")):
            pols.append(Policy(policy_id="fees", title="Fees", category="payments",
                               content=json_text(fees)))
        pay = c.get("payment") or c.get("payment_mode")
        if pay and any(w in q for w in ("pay", "payment", "rail", "card", "wallet")):
            pols.append(Policy(policy_id="payment", title="Payment rails",
                               category="payments", content=json_text(pay)))
        pols.append(Policy(policy_id="agent-honesty", title="How this assistant books",
                           category="about",
                           content=("Bookings are agreements with the organizer. The assistant "
                                    "stages a booking; you confirm on the hosted everlist.network "
                                    "page, where the escrow state is displayed. The rail label is "
                                    "reported verbatim - if it says testnet, it says testnet.")))
        return pols

    async def get_fulfillment_options(self, product_ids):
        raise NotOffered("Listings are events and in-person services; there is nothing to ship")

    async def get_disclosure(self, session, product_id):
        pid = str(product_id).strip()
        if not pid or "/" in pid or ".." in pid:
            return None
        st, res = _api("GET", "/listings/" + pid)
        if st != 200:
            return None
        return Disclosure(
            title="Booking facts",
            product_id=pid,
            rows=[
                DisclosureRow(label="Escrow", value="Funds held until service confirmed or refund window lapses"),
                DisclosureRow(label="Refund", value="Permissionless timeout refund before the claim deadline"),
                DisclosureRow(label="Rail", value=str((res.get("payment_terms") or {}).get("rail") or "see hosted page")),
                DisclosureRow(label="Confirmation", value="You confirm on the hosted everlist.network page"),
            ],
            sources=[PUBLIC_URL + "/how"],
        )


def datetime_utc() -> datetime:
    return datetime.now(timezone.utc)


def json_text(o) -> str:
    return json.dumps(o, ensure_ascii=False) if not isinstance(o, str) else o
