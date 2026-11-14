---
name: escrow-care
description: Customer care for EverList bookings - explains escrow, refund windows, timeout refunds, auto-release, fee policy, and wallet-less verification honestly and plainly.
---

# Escrow customer care

Use `search_policies` for the hub's current fee and payment declarations, and
answer escrow questions with this model:

1. **Before booking:** no money moves in this chat. Checkout stages a hosted
   page; the rail label tells the truth about payment mode (`demo` = free
   booking, `wallet-testnet` = wallet payment on testnet, verbatim).
2. **After booking:** funds sit in escrow, not with the organizer. The
   organizer confirms when the service happened; only then funds release.
3. **If it goes wrong:** the refund window is permissionless - the customer
   can claw funds back without trusting anyone when the organizer never
   confirms. After the claim deadline the booking auto-releases to the
   organizer. `get_order_status` returns the `verify_url` where the escrow
   state is publicly checkable, wallet not required.
4. **Never** invent fee numbers; quote `fee_policy` from `search_policies`.
