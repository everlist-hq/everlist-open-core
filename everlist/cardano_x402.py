"""C3c: Cardano x402 instant rail for agent-hub-v2 — STABLECOIN-FIRST.

Owner-pinned policy (spec patch 2026-09-23): the DEFAULT settlement asset is a
Cardano-native stablecoin (tUSDM on preprod / USDM on mainnet). ADA ("lovelace")
is ONLY an explicit per-listing opt-in on the instant rail (seconds of
exposure). Anything holding value across time (escrow, deposits, refund
windows) stays stablecoin-only — Midnight escrow untouched (stablecoin-denominated
by design).

Transport deviation: we keep the hub's existing X-PAYMENT v1 envelope but
embed the Cardano v2 payload {transaction, nonce} inside it (see the spec).

Research notes (recorded from upstream x402 repo, 2026-09-23; resolves spec §8
open questions):

- Networks: cardano:mainnet, cardano:preprod, cardano:preview (human-readable, not
  CAIP-2; CIP-34 aliases accepted and normalized by the facilitator)
- Assets: stablecoin default per SDK DEFAULT_ASSETS — USDM mainnet
  (c48cbb3d5e57ed56e276bc45f99ab39abe94e6cd7ac39fb402da47ad.0014df105553444d,
  6 decimals) and tUSDM preprod
  (e675b46e4d2242c991a8932a99db3044e80515ae14b4c4ccf6b3f4c9.0014df10745553444d,
  6 decimals, faucet tusdm.moneta.global). [§8 Q1 RESOLVED: preprod stablecoin
  float exists. Q2 RESOLVED: 6 decimals confirmed in SDK constants.]
- ADA opt-in: asset "lovelace" — min-UTXO means outputs need ≥ ~1 ADA; never
  used for value held across time
- Facilitator HTTP: POST /verify {paymentPayload,paymentRequirements} →
  {isValid, invalidReason?, payer}; POST /settle (same shape) →
  {success, transaction, network, errorReason?, extra}
- Pending settlement: /settle returns success:false, errorReason:settlement_pending,
  transaction id, extra.status=pending; retry with same payload resumes observation
  (never rebroadcast) → settled
- No hosted Cardano facilitator exists (unlike CDP for EVM); operators self-host
  the TypeScript package. HUB_CARDANO_FACILITATOR_URL points at an operator instance.
- Settlement modes: unknown (timeout/5xx), settled (tx id present), failed (4xx)
- Fingerprint: sha256(payment_id|payer_address|payto_address|amount|asset)[:16]
  - payment_id = the Cardano nonce (txHash#index)
  - bech32 addresses lowercased before hashing
  - amounts as lovelace integers (or string of digits)
  - asset included (lovelace or policyId.assetNameHex)
- Idempotency: Registry.settle() is fingerprint-idempotent; duplicate
  submissions return recorded result without re-calling the facilitator
- Persistence: state snapshot includes cardano_settlements (like C3b's settlements)
- LOCK discipline: pending marker persisted BEFORE leaving for the HTTP call;
  the HTTP round-trip runs unlocked (CHAO 2026-09-20 fix applied)
"""
import hashlib
import json
import threading
import urllib.error
import urllib.request


DEFAULT_FACILITATOR = ""  # operator self-hosted (no hosted CDP-style endpoint yet); HUB_CARDANO_FACILITATOR_URL

# --- hub-side nonce replay wall (crash/restart defense-in-depth; the chain's
# spent-UTXO check is authoritative once observable) ---
_USED_NONCES = set()
_NLOCK = threading.Lock()


def nonce_used(n: str) -> bool:
    with _NLOCK:
        return n in _USED_NONCES


def mark_nonce_used(n: str):
    with _NLOCK:
        _USED_NONCES.add(n)


def snapshot_used_nonces() -> list:
    with _NLOCK:
        return sorted(_USED_NONCES)


def load_used_nonces(arr):
    with _NLOCK:
        _USED_NONCES.update(arr or [])

# --- Stablecoin-first asset table (mirrors SDK defaultAssets.ts, 2026-09-23) ---
# Default USD-pegged asset per network; index-0 default per upstream convention.
# ADA ("lovelace") is NOT USD-pegged: per-listing opt-in only, never a default.
USDM_MAINNET_ASSET = "c48cbb3d5e57ed56e276bc45f99ab39abe94e6cd7ac39fb402da47ad.0014df105553444d"
USDM_PREPROD_ASSET = "e675b46e4d2242c991a8932a99db3044e80515ae14b4c4ccf6b3f4c9.0014df10745553444d"
USDM_DECIMALS = 6
DEFAULT_ASSETS = {
    "cardano:mainnet": [{"asset": USDM_MAINNET_ASSET, "decimals": USDM_DECIMALS, "symbol": "USDM"}],
    "cardano:preprod": [{"asset": USDM_PREPROD_ASSET, "decimals": USDM_DECIMALS, "symbol": "USDM"}],
    # cardano:preview has NO USDM deployment upstream -> no default; explicit asset required
}


def payment_fingerprint_c(auth: dict) -> str:
    """Stable id for a Cardano payment.

    Fields:
      payment_id      = nonce (txHash#index)
      payer_address   = buyer payment credential address (bech32, lowercased)
      payto_address   = recipient address (bech32, lowercased)
      amount          = lovelace int or str
      asset           = lovelace or policyId.assetNameHex
    """
    basis = (f"{auth.get('payment_id', '').lower()}|{auth.get('payer_address', '').lower()}|"
             f"{auth.get('payto_address', '').lower()}|{auth.get('amount', '')}|{auth.get('asset', '')}")
    return hashlib.sha256(basis.encode()).hexdigest()[:16]


class CardanoFacilitatorClient:
    def __init__(self, base_url: str, api_key: str | None = None, timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.key = api_key
        self.timeout = timeout

    def _call(self, path: str, body: dict) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["X-API-KEY"] = self.key
        req = urllib.request.Request(f"{self.base}/{path}", method="POST",
                                     data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                return r.status, json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode())
            except Exception:
                return e.code, {}
        except Exception:
            # timeout / connection error -> UNKNOWN outcome (may have gone through!)
            return 0, {"error": "timeout or unreachable - settlement outcome UNKNOWN"}


class CardanoSettlementRegistry:
    """Idempotent settlement records keyed by Cardano payment fingerprint."""

    def __init__(self):
        self._s = {}   # fingerprint -> record
        self._lock = threading.Lock()

    def load(self, snap: dict):
        with self._lock:
            self._s.update(snap)

    def snapshot(self) -> dict:
        with self._lock:
            return dict(self._s)

    def get(self, fp: str) -> dict | None:
        with self._lock:
            return self._s.get(fp)

    def mark_pending(self, fp: str, nonce: str = "", payer: str = ""):
        """Durable pending marker BEFORE leaving for the HTTP call (crash evidence).

        nonce/payer are stored on the record so a same-payload retry can find
        its non-terminal record and resume observation (upstream protocol).
        """
        with self._lock:
            if fp not in self._s:
                self._s[fp] = {"fingerprint": fp, "status": "pending",
                               "nonce": nonce, "payer": payer,
                               "ts": __import__("time").time()}

    def settle(self, fp: str, payload: dict, requirements: dict,
               client: CardanoFacilitatorClient) -> dict:
        """Settle once. Duplicate submission NEVER re-calls the facilitator.

        Returns the settlement record. Caller persists it (G1).
        """
        with self._lock:
            prior = self._s.get(fp)
            if prior is not None and prior.get("status") != "pending":
                rec = dict(prior)
                rec["duplicate"] = True
                return rec
        # call OUTSIDE lock (pending marker already persisted; upstream nonce/tx guard)
        st, resp = client._call("settle", {"paymentPayload": payload,
                                            "paymentRequirements": requirements})
        rec = {"fingerprint": fp, "http_status": st, "ts": __import__("time").time()}
        if st == 200 and resp.get("success") is True:
            rec["status"] = "settled"
            rec["tx"] = resp.get("transaction", "")
            rec["network"] = resp.get("network", "cardano:preprod")
        elif st == 0:
            rec["status"] = "unknown"
        elif st == 200 and resp.get("errorReason") == "settlement_pending":
            rec["status"] = "pending"
            rec["tx"] = resp.get("transaction", "")
        elif 400 <= st < 500:
            rec["status"] = "failed"
            rec["error"] = resp.get("errorReason", "facilitator rejected")
        else:
            rec["status"] = "unknown"
        with self._lock:
            existing = self._s.get(fp)
            if existing is not None and existing.get("status") != "pending":
                out = dict(existing)
                out["duplicate"] = True
                return out
            # preserve nonce/payer from the pending marker (pending-resume lookup)
            if existing is not None:
                rec.setdefault("nonce", existing.get("nonce", ""))
                rec.setdefault("payer", existing.get("payer", ""))
            self._s[fp] = rec
        return dict(rec)


def reconcile(registry: CardanoSettlementRegistry, ledger: list) -> dict:
    """Cross-check settlement records vs ledger entries (D1 accounting)."""
    led_fps = {e.get("detail", {}).get("fingerprint") for e in ledger
               if e.get("kind") == "x402_settlement"}
    settled = {fp for fp, r in registry.snapshot().items() if r["status"] == "settled"}
    unknown = {fp for fp, r in registry.snapshot().items() if r["status"] == "unknown"}
    pending = {fp for fp, r in registry.snapshot().items() if r["status"] == "pending"}
    failed = {fp for fp, r in registry.snapshot().items() if r["status"] == "failed"}
    missing = sorted(settled - led_fps)
    return {"ok": not missing, "missing_in_ledger": missing,
            "settled": sorted(settled), "pending": sorted(pending),
            "failed": sorted(failed), "unknown": sorted(unknown)}
