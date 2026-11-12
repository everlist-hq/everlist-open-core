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
import zlib
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


def pdf_text(data: bytes) -> str | None:
    """A3 flyer branch (owner GO 2026-11-12): extract readable text from a
    PDF's FlateDecode content streams with the STDLIB ONLY (zlib) — no pypdf
    install exists and none is approved. Bounded and fail-open: returns None
    on anything non-PDF, undecodable, or oversized; NEVER raises. Extracted
    text feeds draft_from_text() — the DRAFT is advice, never authority
    (organizer confirms every field, same as the photo/text paths)."""
    try:
        if not isinstance(data, (bytes, bytearray)) or not data.startswith(b"%PDF-"):
            return None
        if len(data) > 10_000_000:  # 10 MB — a flyer PDF is never bigger
            return None
        out = []
        for m in re.finditer(rb"stream\r?\n(.*?)endstream", data, re.S):
            raw = m.group(1)
            try:
                dec = zlib.decompress(raw)
            except Exception:
                dec = raw  # uncompressed stream — try as-is
            # PDF text operators: strings live in (...) Tj and [...] TJ arrays
            for tm in re.finditer(rb"\((?:[^()\\]|\\.)*\)", dec):
                s = tm.group(0)[1:-1]
                # unescape the minimal PDF string escapes
                s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\\\", b"\\")
                try:
                    out.append(s.decode("latin-1"))
                except Exception:
                    continue
        # PDF text ops are per-line visual runs — join with NEWLINES so the
        # line-based draft logic below (title = first line, Ort: anchor,
        # description = rest) sees the flyer's real layout.
        txt = "\n".join(out).strip()
        if not txt or len(txt) < 20:
            return None
        return txt[:8000]
    except Exception:
        return None


def draft_from_flyer(data: bytes) -> dict | None:
    """Flyer dispatcher (PDF or plain text bytes): returns the SAME shape as
    draft_from_text_smart() plus "source" (pdf|text), or None when nothing
    readable. Fail-open everywhere; the draft is advice, never authority."""
    try:
        if not isinstance(data, (bytes, bytearray)) or not data:
            return None
        if data.startswith(b"%PDF-"):
            txt = pdf_text(data)
            if not txt:
                return None
            out = draft_from_text_smart(txt)
            out["source"] = "pdf"
            return out
        # plain text (UTF-8 with latin-1 fallback)
        try:
            txt = data.decode("utf-8")
        except Exception:
            txt = data.decode("latin-1", errors="ignore")
        txt = txt.strip()
        if not txt:
            return None
        out = draft_from_text_smart(txt)
        out["source"] = "text"
        return out
    except Exception:
        return None


# ---- URL import (owner GO 2026-11-12, spec-import-and-badges §3) ---------
# Laws: fail-open (any failure -> None, caller degrades to the text flow);
# SSRF walls BEFORE any request (scheme allowlist + resolved-IP blocklist on
# EVERY redirect hop); never executes fetched content; prices/dates land in a
# DRAFT only — the organizer confirms everything (advice, never authority).

import ipaddress  # noqa: E402  (module-local import, mirrors urllib usage above)
import socket  # noqa: E402

_IMPORT_MAX_BYTES = 1_000_000   # 1 MB — a listing page is never bigger
_IMPORT_TIMEOUT_S = 8
_IMPORT_MAX_HOPS = 3
_JSONLD_RE = re.compile(
    r"<script[^>]+type\s*=\s*[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.I | re.S)
_META_RE = re.compile(
    r"<meta[^>]+(?:property|name)\s*=\s*[\"']([^\"']+)[\"'][^>]*content\s*=\s*[\"']([^\"']*)[\"']",
    re.I)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


def _import_blocked_host(host: str) -> bool:
    """True when host resolves to a private/loopback/link-local/reserved IP.
    EVERLIST_IMPORT_ALLOW_PRIVATE=1 exists for TESTS only (fixture servers
    bind loopback); production never sets it."""
    if os.environ.get("EVERLIST_IMPORT_ALLOW_PRIVATE", "") == "1":
        return False
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        return True  # unresolvable = blocked (fail-closed on the network side)
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return True
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_reserved or ip.is_multicast or ip.is_unspecified):
            return True
    return False


def _import_fetch(url: str) -> str | None:
    """Fetch an HTML page with SSRF walls. Returns text or None. NEVER raises."""
    try:
        u = urllib.parse.urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname or u.username:
            return None
        host = u.hostname.strip("[]")
        if _import_blocked_host(host):
            return None
        req = urllib.request.Request(
            url, method="GET",
            headers={"User-Agent": "EverListImport/1 (+https://everlist.network)",
                     "Accept": "text/html"})
        hops = 0
        while True:
            with urllib.request.urlopen(req, timeout=_IMPORT_TIMEOUT_S) as resp:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if "text/html" not in ctype and "application/xhtml" not in ctype:
                    return None
                body = resp.read(_IMPORT_MAX_BYTES + 1)
                if len(body) > _IMPORT_MAX_BYTES:
                    return None
                final_url = resp.geturl()
            # every redirect hop re-resolves through urlopen; re-check the
            # FINAL host too (DNS rebinding shield for the simple case)
            fu = urllib.parse.urlsplit(final_url)
            if fu.hostname and fu.hostname.strip("[]") != host:
                if _import_blocked_host(fu.hostname.strip("[]")):
                    return None
            return body.decode("utf-8", "replace")
    except Exception:
        return None


def _jsonld_event(html_text: str) -> dict | None:
    """First Event-ish JSON-LD block -> normalized draft fields (or None).
    Reads ONLY obvious public facts; never trusts nested junk (validated)."""
    for m in _JSONLD_RE.finditer(html_text[:_IMPORT_MAX_BYTES]):
        try:
            data = json.loads(m.group(1).strip())
        except Exception:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            t = str(node.get("@type") or "")
            if t.split(":")[-1].lower() not in ("event", "eventseries", "businessevent"):
                continue
            d = {}
            name = node.get("name")
            if isinstance(name, str) and name.strip():
                d["title"] = name.strip()[:80]
            desc = node.get("description")
            if isinstance(desc, str) and desc.strip():
                d["description"] = desc.strip()[:500]
            sd = node.get("startDate")
            if isinstance(sd, str):
                dm = re.match(r"(\d{4}-\d{2}-\d{2})", sd.strip())
                if dm:
                    d["date"] = dm.group(1)
                tm2 = re.search(r"T(\d{2}:\d{2})", sd.strip())
                if tm2:
                    d["time"] = tm2.group(1)
            loc = node.get("location")
            if isinstance(loc, dict):
                loc = loc.get("name") or loc.get("address")
            if isinstance(loc, dict):
                loc = loc.get("name") or loc.get("streetAddress")
            if isinstance(loc, str) and loc.strip():
                d["location"] = loc.strip()[:120]
            offers = node.get("offers")
            if isinstance(offers, list):
                offers = offers[0] if offers and isinstance(offers[0], dict) else None
            if isinstance(offers, dict):
                pr = offers.get("price")
                try:
                    if pr is not None and float(pr) >= 0:
                        d["price"] = round(float(pr), 2)
                except (TypeError, ValueError):
                    pass
            if d.get("title"):
                return d
    return None


def _meta_draft(html_text: str) -> dict:
    """og:/twitter: meta fallback -> best-effort draft (may be sparse)."""
    metas = {}
    for m in _META_RE.finditer(html_text[:_IMPORT_MAX_BYTES]):
        k, v = m.group(1).strip().lower(), m.group(2).strip()
        if k and v and k not in metas:
            metas[k] = v
    d = {}
    t = metas.get("og:title") or metas.get("twitter:title")
    if t:
        d["title"] = t[:80]
    de = metas.get("og:description") or metas.get("twitter:description") or metas.get("description")
    if de:
        d["description"] = de[:500]
    if not d.get("title"):
        tm2 = _TITLE_RE.search(html_text[:_IMPORT_MAX_BYTES])
        if tm2:
            d["title"] = re.sub(r"\s+", " ", tm2.group(1)).strip()[:80]
    return {k: v for k, v in d.items() if v}


def draft_from_url(url: str) -> dict | None:
    """Import ladder (spec §3): JSON-LD (high confidence) -> meta tags ->
    text fallback. Returns {"draft", "engine" (jsonld|meta|text),
    "source_url", "model"?} or None when the fetch/parse yields NOTHING
    usable (fail-open: caller offers the paste-text flow instead).
    NEVER raises; never creates; the draft is advice."""
    url = str(url or "").strip()
    if not url or len(url) > 2048:
        return None
    html_text = _import_fetch(url)
    if not html_text:
        return None
    d = _jsonld_event(html_text)
    engine = "jsonld"
    if not d:
        d = _meta_draft(html_text)
        engine = "meta"
    if not d:
        # last resort: visible text through the existing flyer parser
        visible = re.sub(r"<script.*?</script>|<style.*?</style>", " ",
                         html_text, flags=re.I | re.S)
        visible = re.sub(r"<[^>]+>", "\n", visible)
        visible = re.sub(r"\n{2,}", "\n", visible)
        d = draft_from_text(visible)
        engine = "text"
    if not d:
        return None
    return {"draft": d, "engine": engine, "source_url": url}
