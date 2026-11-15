'''EverList deployment config (PA-10). Orders + fulfillment are OFF (the store
honestly does not have those systems for anonymous agent sessions); cart + policies
are on. Brand voice carries the honesty laws.'''
from shopping_agent import ShoppingAgentConfig


def build_config() -> ShoppingAgentConfig:
    return ShoppingAgentConfig(
        brand_name="EverList",
        assistant_name="EverList Booking Assistant",
        brand_voice=("warm, concise, and plain about trade-offs. EverList is listing-first "
                     "agent commerce: a listing is something with a date where a human is "
                     "needed or wanted. Bookings settle in escrow - say so plainly. Report "
                     "payment rail labels verbatim; if one says testnet, say testnet. "
                     "Never claim a booking happened: the customer confirms on the hosted "
                     "everlist.network page where the escrow state is displayed."),
        enable_orders=False,
        enable_fulfillment=False,
        enable_cart=True,
        enable_policies=True,
        enable_disclosures=True,
        max_quantity_per_item=12,
        max_cart_lines=3,
        domain_search_notes=("Listings are dated events and in-person services: always state "
                             "the date, time, and location from the product attributes before "
                             "recommending one; spots_left is capacity still open."),
    )
