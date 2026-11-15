'''EverList MerchantBackend (PA-11, 2026-11-15): the blueprint's MerchantBackend
contract implemented over the EverList hub organizer API. Laws carried:
- every write is STAGED until the human operator approves; apply_change stamps
  applied_by = the operator principal (the blueprint gives applied_by no
  assistant variant, matching our human-confirm law)
- reads degrade honestly: a system the hub does not have raises
  ChangeNotApplicable or returns None/empty WITH a note - never a stand-in zero
- the model never sees the hub token

Hub wire mapped (verified against app.py):
- GET /listings/{id}          public detail (owner principal exposed)
- GET /listings?limit=500     feed; owner filter applied client-side
- GET /orders                 merchant-scoped incoming bookings (pseudonymous)
- POST /listings/{id}/manage  owner acct- token; actions edit/delete/archive/
                              unarchive/make_private/make_public; edit allowlist
                              is schema-derived; promo fields (promo_pct /
                              promo_code) are the real P1/P8 promo system
Systems the hub does NOT have: analytics time series, ad campaigns ->
honest ChangeNotApplicable / empty-with-note.
'''
from __future__ import annotations

import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

from merchant_agent import MerchantBackend, MerchantSessionContext
from merchant_agent.changes import ChangeNotApplicable
from merchant_agent.types import (
    ActorKind,
    AlertCounts,
    BusinessSnapshot,
    CampaignDraft,
    ChangeItem,
    ChangeKind,
    ChangeStatus,
    InventoryActionItem,
    InventoryAlert,
    Listing,
    ListingDetails,
    ListingFilters,
    MetricSeries,
    OrderIssue,
    PriceUpdateItem,
    PricingContext,
    PromotionDraft,
    StagedChange,
)

_HUB = os.environ.get("EVERLIST_HUB_URL", "http://127.0.0.1:8951").rstrip("/")
_TOKEN = os.environ.get("EVERLIST_HUB_TOKEN", "")  # organizer list token; server-side only


def _api(method: str, path: str, body: dict | None = None, token: str | None = None,
         hub: str | None = None):
    url = (hub or _HUB) + path
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
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception as e:
        return 0, {"error": str(e)}


class EverlistMerchantBackend(MerchantBackend):
    """MerchantBackend fronting one EverList organizer account. The credential
    (list token) is held server-side by the host and never shown to the model."""

    def __init__(self, hub_url: str | None = None, token: str | None = None):
        self._hub = (hub_url or _HUB).rstrip("/")
        self._token = token or _TOKEN
        self._staged: dict[str, StagedChange] = {}
        self._payloads: dict[str, dict] = {}

    # -- wire helpers --------------------------------------------------------

    def _api2(self, method: str, path: str, body: dict | None = None):
        return _api(method, path, body, self._token, self._hub)

    def _whoami(self) -> str | None:
        """The operator principal. The hub API face has no /accounts/me; the
        merchant-scoped /orders projection stamps the caller as 'merchant'
        (verified: merchant=owner acct, booked_by=buyer acct) - that IS the
        owner field the feed carries."""
        st, orders = self._api2("GET", "/orders")
        if st == 200 and orders.get("merchant"):
            return orders["merchant"]
        return None

    def _get_listing(self, listing_id: str) -> dict | None:
        st, d = self._api2("GET", "/listings/" + str(listing_id))
        return d if st == 200 else None

    def _own_listings(self, session: MerchantSessionContext) -> list[dict]:
        st, feed = self._api2("GET", "/listings?limit=500")
        if st != 200:
            return []
        me = self._whoami()
        if not me:
            return []
        return [l for l in feed.get("listings", []) if l.get("owner") == me]

    @staticmethod
    def _to_listing(l: dict) -> Listing:
        status = "paused" if (l.get("archived") or l.get("visibility") == "private") else "active"
        tags = l.get("tags")
        return Listing(
            listing_id=str(l["id"]),
            title=str(l.get("title", "")),
            status=status,
            price=float(l.get("price") or 0.0),
            currency="EUR",
            stock=int(l.get("capacity") or 0),
            category=l.get("category"),
            attributes={str(k): str(v) for k, v in tags.items()} if isinstance(tags, dict) else {},
            short_description=(str(l.get("description") or "")[:120]) or None,
        )

    def _stage(self, session: MerchantSessionContext, kind: ChangeKind, summary: str,
               items: list[ChangeItem], payload: dict, note: str | None = None) -> StagedChange:
        ch = StagedChange(
            change_id="chg-" + secrets.token_hex(6),
            kind=kind,
            status=ChangeStatus.STAGED,
            summary=(note or summary)[:200],
            items=items,
            created_at=datetime.now(timezone.utc),
            created_by=session.operator,
            created_by_kind=ActorKind.AGENT,
            currency="EUR",
        )
        self._staged[ch.change_id] = ch
        self._payloads[ch.change_id] = payload
        return ch

    # -- Performance (honest limits) ------------------------------------------

    async def get_business_snapshot(self, session: MerchantSessionContext,
                                    period: str | None = None) -> BusinessSnapshot:
        st, orders = self._api2("GET", "/orders")
        mine = orders.get("orders", []) if st == 200 else []
        active = [b for b in mine if b.get("escrow") in ("HELD", "WAIVED", "DIRECT")]
        return BusinessSnapshot(
            period=period or "all-time",
            sales=float(sum(b.get("amount") or 0 for b in active)),
            orders=len(active),
            currency="EUR",
            note=("From merchant-scoped /orders; no analytics system: "
                  "traffic/conversion stay None, never zero."),
        )

    async def query_metrics(self, session: MerchantSessionContext, metric: str,
                            period: str | None = None, granularity: str = "day",
                            segment: str | None = None) -> MetricSeries:
        return MetricSeries(metric=metric, granularity=granularity, points=[],
                            note=("The hub keeps no time-series analytics; per-metric "
                                  "history is unavailable rather than zero."))

    async def get_campaign_performance(self, session: MerchantSessionContext,
                                       campaign_id: str | None = None):
        raise ChangeNotApplicable(
            "EverList has no ad-campaign system; campaign performance is not a "
            "managed system here")

    # -- Catalog ----------------------------------------------------------------

    async def search_listings(self, session: MerchantSessionContext, query: str,
                              filters: ListingFilters | None = None,
                              limit: int = 8) -> list[Listing]:
        q = (query or "").lower()
        out: list[Listing] = []
        for l in self._own_listings(session):
            hay = (str(l.get("title", "")) + " " + str(l.get("description") or "")).lower()
            if q and q not in hay:
                continue
            if filters and filters.status and self._to_listing(l).status != filters.status:
                continue
            out.append(self._to_listing(l))
            if len(out) >= limit:
                break
        return out

    async def get_listing(self, session: MerchantSessionContext,
                          listing_id: str) -> ListingDetails | None:
        l = self._get_listing(listing_id)
        if not l:
            return None
        base = self._to_listing(l)
        return ListingDetails(**base.model_dump(),
                              long_description=str(l.get("description") or "") or None)

    # -- Inventory and order health (derived honestly) ---------------------------

    async def get_inventory_alerts(self, session: MerchantSessionContext) -> list[InventoryAlert]:
        alerts: list[InventoryAlert] = []
        for l in self._own_listings(session):
            cap = int(l.get("capacity") or 0)
            if cap and cap <= 2:
                alerts.append(InventoryAlert(
                    listing_id=str(l["id"]), title=str(l.get("title", "")),
                    kind="low_stock", stock=cap, threshold=2,
                    storefront_visible=not bool(l.get("archived"))))
        return alerts

    async def get_order_issues(self, session: MerchantSessionContext) -> list[OrderIssue]:
        st, orders = self._api2("GET", "/orders")
        mine = orders.get("orders", []) if st == 200 else []
        today = datetime.now(timezone.utc).date().isoformat()
        out: list[OrderIssue] = []
        for b in mine:
            if b.get("escrow") == "HELD" and str(b.get("date") or "") < today:
                out.append(OrderIssue(
                    issue_id="issue-" + str(b.get("id")), order_id=str(b.get("id")),
                    kind="delayed",
                    summary=("Service date passed while escrow is still HELD - "
                             "release or refund pending"),
                    listing_id=b.get("listing_id")))
        return out

    async def get_pricing_context(self, session: MerchantSessionContext,
                                  listing_id: str) -> PricingContext | None:
        l = self._get_listing(listing_id)
        if not l:
            return None
        return PricingContext(
            listing_id=listing_id,
            current_price=float(l.get("price") or 0.0),
            currency="EUR",
            note=("EverList shows the full price before payment (C12 law); "
                  "buyer fee is currently zero."))

    # -- Staged writes (propose -> preview -> approve -> apply) --------------------

    async def stage_listing_update(self, session: MerchantSessionContext, listing_id: str,
                                   fields: dict[str, Any], note: str | None = None) -> StagedChange:
        l = self._get_listing(listing_id)
        if not l:
            raise ChangeNotApplicable("no listing " + str(listing_id))
        allowed = {"title", "description", "price", "location", "date", "capacity"}
        clean = {k: v for k, v in fields.items() if k in allowed}
        if not clean:
            raise ChangeNotApplicable(
                "no editable field in the proposal (EverList edit allowlist: "
                "title/description/price/location/date/capacity)")
        items = [ChangeItem(target=listing_id, field=k, before=l.get(k), after=v)
                 for k, v in clean.items()]
        return self._stage(session, ChangeKind.LISTING_UPDATE,
                           note or ("Edit listing " + str(listing_id)), items,
                           {"kind": "edit", "listing_id": listing_id, "fields": clean})

    async def stage_price_update(self, session: MerchantSessionContext,
                                 items_in: list[PriceUpdateItem],
                                 note: str | None = None) -> StagedChange:
        items: list[ChangeItem] = []
        updates = []
        for it in items_in:
            l = self._get_listing(it.listing_id)
            if not l:
                raise ChangeNotApplicable("no listing " + str(it.listing_id))
            before = float(l.get("price") or 0.0)
            items.append(ChangeItem(target=it.listing_id, field="price",
                                    before=before, after=it.new_price))
            updates.append({"listing_id": it.listing_id, "price": it.new_price})
        return self._stage(session, ChangeKind.PRICE_UPDATE,
                           note or ("Price update on " + str(len(items)) + " listing(s)"),
                           items, {"kind": "price", "updates": updates})

    async def stage_inventory_action(self, session: MerchantSessionContext,
                                     items_in: list[InventoryActionItem],
                                     note: str | None = None) -> StagedChange:
        items: list[ChangeItem] = []
        ops = []
        for it in items_in:
            l = self._get_listing(it.listing_id)
            if not l:
                raise ChangeNotApplicable("no listing " + str(it.listing_id))
            if it.action == "pause":
                action, field, after = "make_private", "availability", "paused"
                before = "active"
            elif it.action == "activate":
                action, field, after = "make_public", "availability", "active"
                before = "paused"
            else:  # restock = capacity bump
                action, field = "edit", "capacity"
                before = int(l.get("capacity") or 0)
                after = before + int(it.quantity or 0)
            items.append(ChangeItem(target=it.listing_id, field=field,
                                    before=before, after=after))
            op_ = {"listing_id": it.listing_id, "action": action}
            if action == "edit":
                op_["fields"] = {"capacity": after}
            ops.append(op_)
        return self._stage(session, ChangeKind.INVENTORY_ACTION,
                           note or ("Inventory action on " + str(len(ops)) + " listing(s)"),
                           items, {"kind": "inventory", "ops": ops})

    async def stage_promotion(self, session: MerchantSessionContext,
                              promotion: PromotionDraft) -> StagedChange:
        items: list[ChangeItem] = []
        ops = []
        pct = round(promotion.discount_pct)
        for lid in promotion.listing_ids:
            l = self._get_listing(lid)
            if not l:
                raise ChangeNotApplicable("no listing " + str(lid))
            if float(l.get("price") or 0) <= 0:
                raise ChangeNotApplicable(
                    lid + ": promo setup is refused on free listings (hub P7 law)")
            stem = "".join(c for c in promotion.name.lower() if c.isalnum())[:12] or "promo"
            code = stem + secrets.token_hex(3)  # 3-24 letters/digits only (hub wire law)
            items.append(ChangeItem(target=lid, field="promo", before=None,
                                    after={"pct": pct, "code": code, "uses": 100}))
            ops.append({"listing_id": lid, "action": "edit",
                        "fields": {"promo": {"code": code, "pct": pct, "uses": 100}}})
        return self._stage(session, ChangeKind.PROMOTION,
                           "Promotion '" + promotion.name + "' on "
                           + str(len(ops)) + " listing(s)",
                           items, {"kind": "promo", "ops": ops})

    async def stage_campaign(self, session: MerchantSessionContext,
                             campaign: CampaignDraft) -> StagedChange:
        raise ChangeNotApplicable(
            "EverList has no ad-campaign system; promotions map onto per-listing "
            "promo codes instead")

    async def get_pending_changes(self, session: MerchantSessionContext) -> list[StagedChange]:
        return [c for c in self._staged.values() if c.status == ChangeStatus.STAGED]

    async def apply_change(self, session: MerchantSessionContext,
                           change_id: str) -> StagedChange:
        ch = self._staged.get(change_id)
        if not ch or ch.status != ChangeStatus.STAGED:
            raise ChangeNotApplicable("change " + change_id + " is not staged")
        p = self._payloads.get(change_id, {})
        results = []
        if p.get("kind") == "edit":
            st, r = self._api2("POST", "/listings/" + p["listing_id"] + "/manage",
                               {"action": "edit", **p["fields"]})
            results.append((st, r))
        elif p.get("kind") == "price":
            for u in p["updates"]:
                st, r = self._api2("POST", "/listings/" + u["listing_id"] + "/manage",
                                   {"action": "edit", "price": u["price"]})
                results.append((st, r))
        elif p.get("kind") in ("inventory", "promo"):
            for op_ in p["ops"]:
                body = {"action": op_["action"]}
                body.update(op_.get("fields") or {})
                st, r = self._api2("POST", "/listings/" + op_["listing_id"] + "/manage", body)
                results.append((st, r))
        else:
            raise ChangeNotApplicable("unsupported change kind")
        failed = [r for st, r in results if st not in (200, 201)]
        if failed:
            # the write failed: the change STAYS staged (blueprint law)
            raise RuntimeError("hub write failed, change stays staged: " + json.dumps(failed[0])[:200])
        ch.status = ChangeStatus.APPLIED
        ch.applied_at = datetime.now(timezone.utc)
        # human-only law: applied_by is the operator principal, never the assistant
        ch.applied_by = session.operator
        return ch

    async def discard_change(self, session: MerchantSessionContext, change_id: str,
                             actor_kind: ActorKind = ActorKind.OPERATOR) -> StagedChange:
        ch = self._staged.get(change_id)
        if not ch or ch.status != ChangeStatus.STAGED:
            raise ChangeNotApplicable("change " + change_id + " is not staged")
        ch.status = ChangeStatus.DISCARDED
        ch.discarded_at = datetime.now(timezone.utc)
        ch.discarded_by = session.operator
        ch.discarded_by_kind = actor_kind
        return ch

    async def get_merchant_context(self, session: MerchantSessionContext) -> dict[str, Any]:
        return {
            "merchant_id": session.merchant_id,
            "limitations": [
                "No analytics history: traffic/conversion/metric series are "
                "unavailable, never zero.",
                "No ad campaigns: promotion works via per-listing promo codes "
                "(percentage + code).",
                "Escrow law: buyers hold a per-listing refund window; releases "
                "follow /how and /transparency.",
            ],
            "rail_note": ("Payment rails are reported verbatim; demo listings may "
                          "say testnet - never upgrade the label."),
        }
