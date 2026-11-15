'''EverList deployment config (PA-11). Real MerchantAgentConfig fields.
Laws: every write staged, host approval required; campaigns OFF (no ad system);
brand voice carries the honesty laws verbatim.'''
from merchant_agent import MerchantAgentConfig


def build_config() -> MerchantAgentConfig:
    return MerchantAgentConfig(
        brand_name="EverList",
        assistant_name="EverList Merchant Assistant",
        brand_voice=("warm, concise, and plain about trade-offs. Your operator is a human "
                     "organizer on everlist.network. EverList is listing-first agent commerce: "
                     "a listing is something with a date where a human is needed or wanted. "
                     "Bookings settle in escrow - buyers hold a per-listing refund window, and "
                     "releases follow /how and /transparency. Report payment rail labels "
                     "verbatim; if one says testnet, say testnet. The hub has no analytics "
                     "history and no ad-campaign system: figures that don't exist are None, "
                     "never zero - say so plainly."),
        model="claude-sonnet-5",
        thinking_effort="high",
        enable_listing_edits=True,
        enable_inventory=True,
        enable_pricing=True,
        enable_campaigns=False,          # no ad system: honest refusal
        require_host_approval=True,      # human-only apply law
        max_items_per_change=5,
        max_price_delta_pct=50,
        max_promotion_discount_pct=50,   # hub wire: pct 1-50
    )
