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
  live           — OpenAI-compatible chat calls, bounded by
                   EVERLIST_ENRICH_TIMEOUT_S per provider (default 8).

Provider chain (owner call 2026-11-07: use the key you already have):
  1) explicit EVERLIST_ENRICH_URL / EVERLIST_ENRICH_API_KEY / EVERLIST_ENRICH_MODEL
  2) the hub OWN .secrets/llm.env providers (NLU proxy, then ZAI) — gated by
     EVERLIST_ENRICH_USE_LLM_ENV=1 so test gates stay hermetic. No new
     secrets anywhere: the file brain.py/phrase.py already read carries
     every key this module needs.
The first provider that returns parseable keywords wins; every failure mode
stays fail-open (extract NEVER raises, returns None).
"""
import json
import os
import re
import time
import urllib.error
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENVF = os.path.join(_HERE, ".secrets", "llm.env")


def _load_env() -> None:
    """Load .secrets/llm.env into os.environ (never overriding real env)."""
    try:
        with open(_ENVF) as f:
            for ln in f:
                ln = ln.strip()
                if not ln or ln.startswith("#") or "=" not in ln:
                    continue
                k, _, v = ln.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except OSError:
        pass


_load_env()

_WORD = re.compile(r"[a-zäöüß][a-zäöüß-]{2,}")
_STOP = {"the", "and", "for", "with", "from", "this", "that", "are", "all",
         "our", "your", "their", "have", "will", "can", "who", "what",
         "when", "where", "how", "und", "der", "die", "das", "ein", "eine",
         "mit", "für", "auf", "ist", "sich", "werden", "bei", "aus"}
_KW_MAX = 12


def _cfg():
    mode = os.environ.get("EVERLIST_ENRICH", "off").strip().lower()
    if mode not in ("off", "stub", "live"):
        mode = "off"
    # Provider chain: (1) explicit knobs (tests / bespoke providers),
    # (2) llm.env providers NLU then ZAI when EVERLIST_ENRICH_USE_LLM_ENV=1.
    chain = []
    _ek = os.environ.get("EVERLIST_ENRICH_API_KEY", "").strip()
    if _ek:
        chain.append((os.environ.get("EVERLIST_ENRICH_URL",
                                     "https://api.openai.com/v1/chat/completions").strip(),
                      _ek,
                      os.environ.get("EVERLIST_ENRICH_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"))
    if os.environ.get("EVERLIST_ENRICH_USE_LLM_ENV", "") == "1":
        for base_k, key_k, model_k, _dm in (
                ("EVERLIST_NLU_API_URL", "EVERLIST_NLU_API_KEY", "EVERLIST_NLU_MODEL",
                 "z-ai-glm-5-3-flash"),
                ("EVERLIST_ZAI_API_URL", "EVERLIST_ZAI_API_KEY", "EVERLIST_ZAI_MODEL",
                 "glm-5.3-flash"),
                ("EVERLIST_OPENROUTER_API_URL", "EVERLIST_OPENROUTER_API_KEY",
                 "EVERLIST_OPENROUTER_MODEL", "openai/gpt-4o-mini"),
                # a0 shared router: quota resets daily (owner 2026-11-08) —
                # LAST in the chain so daily-exhausted windows fail over first
                ("EVERLIST_A0_API_URL", "EVERLIST_A0_API_KEY", "EVERLIST_A0_MODEL",
                 "z-ai-glm-5-3-flash")):
            _defaults = {"EVERLIST_OPENROUTER_API_URL": "https://openrouter.ai/api/v1",
                         "EVERLIST_A0_API_URL": "https://llm.agent-zero.ai/v1"}
            _k = os.environ.get(key_k, "").strip()
            if _k:
                chain.append((os.environ.get(base_k, _defaults.get(base_k,
                              "https://api.agent-zero.ai/venice/v1")).strip().rstrip("/")
                              + "/chat/completions",
                              _k,
                              os.environ.get(model_k, _dm).strip() or _dm))
    return {"mode": mode, "chain": chain,
            "timeout": min(12.0, max(0.2, float(
                os.environ.get("EVERLIST_ENRICH_TIMEOUT_S", "8") or 8)))}


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
    # max_tokens 1200 ON PURPOSE (brain.py lesson): reasoning models spend
    # internal reasoning BEFORE the answer — small budgets return empty
    # content with finish_reason=length.
    payload_base = {"temperature": 0, "max_tokens": 1200,
                    "messages": [{"role": "user", "content": prompt}]}
    last = None
    for url, key, model in cfg["chain"]:
        try:
            req = urllib.request.Request(
                url, data=json.dumps(dict(payload_base, model=model)).encode(),
                method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                payload = json.loads(resp.read().decode())
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
            m = re.search(r"\{[^{}]*\}", str(content), re.S)
            if not m:
                last = "unparseable reply"
                continue
            kw = json.loads(m.group(0)).get("kw") or []
            kw = [str(k).strip().lower() for k in kw
                  if isinstance(k, str) and 1 <= len(str(k).strip()) <= 24][:_KW_MAX]
            if not kw:
                last = "empty keyword list"
                continue
            return {"kw": kw, "mode": "live", "model": model,
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        except Exception as _ex:
            last = str(_ex)[:80]
            continue
    if last:
        print(f"[enrich] live extraction failed ({last}); fail-open", flush=True)
    return None


def extract(title, description, tags):
    """Returns a provenance block {kw, mode, model, ts} or None.
    NEVER raises — every failure mode returns None (fail-open law)."""
    cfg = _cfg()
    if cfg["mode"] == "off":
        return None
    try:
        if cfg["mode"] == "stub":
            return _stub_extract(title, description, tags)
        if not cfg["chain"]:
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


_DRAFT_PROMPT = ("You parse EVENT/SERVICE FLYER text into strict JSON. Reply ONLY "
                 "with a JSON object, no prose. Allowed keys: title (string, "
                 "max 80 chars), date (YYYY-MM-DD or null), time (HH:MM 24h or "
                 "null), price (number >=0 or null), location (string max 120 "
                 "or null), description (string max 500 or null). Omit keys you "
                 "cannot support from the text. Never invent facts.\n\nFlyer:\n")


def _draft_llm(cfg, text, max_providers=2):
    """LLM flyer parse over the provider chain (first parseable reply wins).
    Returns {"draft": {...}, "model": model} or None. NEVER raises."""
    body_base = {"temperature": 0, "max_tokens": 1200,
                 "messages": [{"role": "user",
                               "content": _DRAFT_PROMPT + str(text)[:8000]}]}
    for url, key, model in cfg["chain"][:max(1, int(max_providers))]:
        try:
            req = urllib.request.Request(
                url, data=json.dumps(dict(body_base, model=model)).encode(),
                method="POST",
                headers={"Content-Type": "application/json",
                         "Authorization": f"Bearer {key}"})
            with urllib.request.urlopen(req, timeout=cfg["timeout"]) as resp:
                payload = json.loads(resp.read().decode())
            content = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
            m = re.search(r"\{[^{}]*\}", str(content), re.S)
            if not m:
                continue
            raw = json.loads(m.group(0))
            if not isinstance(raw, dict):
                continue
            d = {}
            t = raw.get("title")
            if isinstance(t, str) and t.strip():
                d["title"] = t.strip()[:80]
            dt = raw.get("date")
            if isinstance(dt, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", dt.strip()):
                d["date"] = dt.strip()
            tm2 = raw.get("time")
            if isinstance(tm2, str):
                mm = re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", tm2.strip())
                if mm:
                    d["time"] = f"{int(mm.group(1)):02d}:{mm.group(2)}"
            pr = raw.get("price")
            if isinstance(pr, (int, float)) and pr == pr and 0 <= pr < 10**7:
                d["price"] = round(float(pr), 2)
            lc = raw.get("location")
            if isinstance(lc, str) and lc.strip():
                d["location"] = lc.strip()[:120]
            de = raw.get("description")
            if isinstance(de, str) and de.strip():
                d["description"] = de.strip()[:500]
            if not d:
                continue
            return {"draft": d, "model": model}
        except Exception:
            continue
    return None


def draft_from_text_smart(text):
    """Paste-a-flyer v2: LLM-assisted parse when live+chain available,
    deterministic regex otherwise (fail-open law). Returns
    {"draft", "engine" (regex|llm), "model"?}. NEVER raises; the draft is
    ADVICE — it never creates anything (the organizer confirms every field)."""
    out = {"draft": draft_from_text(text), "engine": "regex"}
    cfg = _cfg()
    if cfg["mode"] != "live" or not cfg["chain"]:
        return out
    got = _draft_llm(cfg, text)
    if got and got.get("draft"):
        out["draft"] = got["draft"]
        out["engine"] = "llm"
        out["model"] = got.get("model")
    return out
