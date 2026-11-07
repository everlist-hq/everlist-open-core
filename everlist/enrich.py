"""enrich.py — Phase 2 find-quality: AI write-side compression (owner GO 2026-11-07).

Law (docs/reviews/2026-11-07-universal-listings-gap-analysis.md section 4):
- Expensive AI ONCE at write time; reads stay cheap and deterministic.
- FAIL-OPEN: no key, timeout, or garbage output NEVER blocks or fails a
  create — the listing indexes on its raw text exactly as before.
- Server-owned: output lands in _enrich_kw / _enrich (server-only fields,
  stripped from every public projection); derived keywords are merged into
  the sqlite FTS tags CELL at index time only — the public tags list is
  never touched by AI output.
- Provenance: every block carries mode + model + timestamp (replayable,
  auditable, principle-17 style).

Modes via EVERLIST_ENRICH:
  off  (default) — no-op, zero behavior change.
  stub           — deterministic offline extractor (tests / airgapped).
  live           — ONE OpenAI-compatible chat call, bounded by
                   EVERLIST_ENRICH_TIMEOUT_S (default 2.5).

Optional live knobs: EVERLIST_ENRICH_URL (chat-completions endpoint),
EVERLIST_ENRICH_API_KEY (bearer), EVERLIST_ENRICH_MODEL.
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

_WORD = re.compile(r"[a-zäöüß][a-zäöüß-]{2,}")
# Deterministic stopword wall for the stub extractor (EN+DE small core).
_STOP = {"the", "and", "for", "with", "from", "this", "that", "are", "all",
         "our", "your", "their", "have", "will", "can", "who", "what",
         "when", "where", "how", "und", "der", "die", "das", "ein", "eine",
         "mit", "für", "auf", "ist", "sich", "werden", "bei", "aus"}
_KW_MAX = 12


def _cfg():
    mode = os.environ.get("EVERLIST_ENRICH", "off").strip().lower()
    if mode not in ("off", "stub", "live"):
        mode = "off"
    return {"mode": mode,
            "url": os.environ.get("EVERLIST_ENRICH_URL",
                                  "https://api.openai.com/v1/chat/completions"),
            "key": os.environ.get("EVERLIST_ENRICH_API_KEY", ""),
            "model": os.environ.get("EVERLIST_ENRICH_MODEL", "gpt-4o-mini"),
            "timeout": min(5.0, max(0.2, float(
                os.environ.get("EVERLIST_ENRICH_TIMEOUT_S", "2.5") or 2.5)))}


def _clean_words(text):
    return [w for w in _WORD.findall(str(text or "").lower())
            if w not in _STOP and len(w) <= 24]


def _stub_extract(title, description, tags):
    words = _clean_words(title) + _clean_words(description)
    seen, kw = set(), []
    for w in words:
        if w not in seen:
            seen.add(w)
            kw.append(w)
        if len(kw) >= _KW_MAX:
            break
    return {"kw": kw, "mode": "stub", "model": "stub-regex-v1",
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def _live_extract(cfg, title, description, tags):
    prompt = ("Extract up to 12 lowercase search keywords (single words or "
              "short hyphenated compounds, EN or DE) that a buyer might search "
              "for but that are MISSING from this listing text. Reply with "
              "ONLY a JSON object {\"kw\": [...]}.\n"
              f"Title: {title}\nDescription: {description}\n"
              f"Tags: {', '.join(str(t) for t in (tags or []))}")
    body = json.dumps({"model": cfg["model"], "temperature": 0,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(
        cfg["url"], data=body, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {cfg['key']}"})
    with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
        payload = json.loads(resp.read().decode())
    content = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
    m = re.search(r"\{[^{}]*\}", str(content), re.S)
    if not m:
        return None
    kw = json.loads(m.group(0)).get("kw") or []
    kw = [str(k).strip().lower() for k in kw
          if isinstance(k, str) and 1 <= len(str(k).strip()) <= 24][:_KW_MAX]
    if not kw:
        return None
    return {"kw": kw, "mode": "live", "model": cfg["model"],
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}


def extract(title, description, tags):
    """Returns a provenance block {kw, mode, model, ts} or None.
    NEVER raises — every failure mode returns None (fail-open law)."""
    cfg = _cfg()
    if cfg["mode"] == "off":
        return None
    try:
        if cfg["mode"] == "stub":
            return _stub_extract(title, description, tags)
        if not cfg["key"]:
            return None
        return _live_extract(cfg, title, description, tags)
    except Exception:
        return None


# ---- paste-a-flyer draft extraction (deterministic, no AI in v1) ----------

_DATE_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_PRICE_RE = re.compile(r"(?:€|EUR\s?|EUR)(\d+(?:[.,]\d{1,2})?)", re.I)
_LOC_RE = re.compile(r"(?:^|\n)\s*(?:ort|location|venue|wo)\s*:\s*(.{3,80})",
                     re.I | re.M)


def draft_from_text(text):
    """Paste-a-flyer v1: deterministic prefill from free text. Returns a
    DRAFT dict (never creates anything); unknown fields stay unset so the
    organizer fills the gaps. Bounded: first 8000 chars considered."""
    text = str(text or "")[:8000]
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    title = lines[0][:80] if lines else ""
    dm = _DATE_RE.search(text)
    tm = _TIME_RE.search(text)
    pm = _PRICE_RE.search(text)
    lm = _LOC_RE.search(text)
    price = None
    if pm:
        try:
            price = round(float(pm.group(1).replace(",", ".")), 2)
        except ValueError:
            price = None
    loc = lm.group(1).strip().rstrip(".,;")[:120] if lm else None
    d = {"title": title, "date": dm.group(1) if dm else None,
         "time": f"{int(tm.group(1)):02d}:{tm.group(2)}" if tm else None,
         "price": price, "location": loc,
         "description": "\n".join(lines[1:])[:500] or None}
    return {k: v for k, v in d.items() if v is not None}
