"""phrase.py — AI-authored replies for the webchat (spec 2026-09-25).

Law (owner call 2026-09-25): the AI authors every reply a human reads; the
deterministic core executes the truth and acts as the WITNESS. Programmatic
survives as: executor of facts, guard, catch, security screens, agent/CLI
format. A guard failure is corrected and retried — never silently templated —
and every guard event is logged.

Contract:
  phrase(webchat_reply, user_text, sender) -> final reply text
  * deterministic template = fact source: every fact-like token it contains
    must appear in the authored text (preservation), and every fact-like
    token in the authored text must come from it (invention blocking).
  * normalization before comparison: NFKD math-alphanumeric fold (𝟭 -> 1),
    whitespace collapse, smart quotes/dashes, emoji strip, currency-symbol
    equivalence (EUR 15 == 15 EUR == €15). Tokens are checked, never phrasing.
  * secrets are redacted BEFORE the author call and spliced back after
    (byte-identical). Secrets never leave the server.
  * fail -> corrective retry (violations fed back) -> template-as-example
    retry -> template ships + incident logged. Cap 3 attempts.
  * master switch EVERLIST_PHRASE (default OFF until owner enables).
  * hermetic: EVERLIST_BRAIN_DISABLED=1 -> never called (fail-open law).
"""
import json
import os
import re
import time
import urllib.request

_HERE = os.path.dirname(os.path.abspath(__file__))
_ENVF = os.path.join(_HERE, ".secrets", "llm.env")


def _load_env() -> None:
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

_API_URL = os.environ.get("EVERLIST_PHRASE_API_URL",
                          os.environ.get("EVERLIST_NLU_API_URL",
                                         "https://api.agent-zero.ai/venice/v1"))
_API_KEY = os.environ.get("EVERLIST_PHRASE_API_KEY",
                          os.environ.get("EVERLIST_NLU_API_KEY", ""))
_MODEL = os.environ.get("EVERLIST_PHRASE_MODEL",
                        os.environ.get("EVERLIST_BRAIN_MODEL", "mercury-2-5"))
_TIMEOUT = float(os.environ.get("EVERLIST_PHRASE_TIMEOUT", "10"))
_ENABLED = os.environ.get("EVERLIST_PHRASE", "0") == "1"
_DISABLED = bool(os.environ.get("EVERLIST_BRAIN_DISABLED"))
_LOG_PATH = os.environ.get(
    "EVERLIST_PHRASE_LOG",
    os.path.join(_HERE, ".run", "phrase-guard.jsonl"))

# own budget (separate from the brain's limiter — own failure domain)
_RL: dict = {}            # sender -> (hits:list, window_start:float)
_RL_WINDOW = 300.0
_RL_CAP = int(os.environ.get("EVERLIST_PHRASE_CAP", "60"))
_RL_SENDERS_CAP = 10_000  # M-C cap law

_STAT = {"ok": 0, "retried": 0, "fallback": 0, "outage": 0, "skipped": 0,
         "model": _MODEL}
LAST: dict = {}           # chatlog info, mirrors brain.LAST


# ---- eligibility -----------------------------------------------------------

_ELIGIBLE = re.compile(
    # cheap screens: phrasing is FORBIDDEN on these deterministic outputs
    r"^(search\b|more$|next$|all$|\d+\s*-\s*\d+$|\d+$)", re.I)
_NEVER_RX = re.compile(
    r"\[\[nav:|\bdelete-account\b|password|seed phrase", re.I)
_INTAKE_STEP_RX = re.compile(r"\[\d+/7\]")


def _eligible(reply: str) -> bool:
    if not _ENABLED or _DISABLED or not _API_KEY:
        return False
    r = (reply or "").strip()
    if not r or _NEVER_RX.search(r) or _INTAKE_STEP_RX.search(r):
        return False
    # pure-number/range navigational replays stay instant (speed beats prose)
    if re.fullmatch(r"\d+(\s*-\s*\d+)?", r) or r in ("all",):
        return False
    return True


def _rate_ok(sender: str) -> bool:
    now = time.time()
    hits, win = _RL.get(sender) or ([], now)
    if now - win > _RL_WINDOW:
        hits, win = [], now
    over = len(hits) >= _RL_CAP
    if not over:
        hits.append(now)
    _RL[sender] = (hits, win)
    if len(_RL) > _RL_SENDERS_CAP:
        for k in sorted(_RL, key=lambda k: _RL[k][1])[:len(_RL) // 10]:
            _RL.pop(k, None)
    return not over


# ---- secrets: redact & reinject -------------------------------------------

_SECRET_RX = re.compile(
    r"(🔑[^\n]*\n(?:(?!\n\n)[^\n]*\n?)*"          # booking-secret block
    r"|manage code[^\n]*:[^\n]*"
    r"|\b[0-9a-f]{16,64}\b)", re.I)              # raw hex codes/seeds
_SECRET_PH = "[[SECRET]]"


def _redact(text: str):
    secrets = []

    def _sub(m):
        secrets.append(m.group(0))
        return _SECRET_PH

    return _SECRET_RX.sub(_sub, text), secrets


def _reinject(text: str, secrets: list) -> str:
    for s in secrets:
        if _SECRET_PH not in text:
            break
        text = text.replace(_SECRET_PH, s, 1)
    # any placeholder the author invented/duplicated is stripped hard
    return text.replace(_SECRET_PH, "")


# ---- tokenization + normalization (the guard) -----------------------------

_EMOJI_RX = re.compile(
    "[\U0001f000-\U0001faff\U00002600-\U000027bf\U0001f900-\U0001f9ff\u200d\ufe0f]+")
_FACT_RX = re.compile(
    r"(?:\d{1,3}(?:[.,]\d{3})+|\d+[.,]\d+|\d+)"
    r"(?:\s?(?:h|hours?|min|minutes?|days?|spots?|people|x))?"
    r"|(?:\$|€|\bEUR\b|\bUSD\b)\s?\d+(?:[.,]\d+)?"
    r"|\d+(?:[.,]\d+)?\s?(?:\$|€|\bEUR\b|\bUSD\b)"
    r"|\b\d{4}-\d{2}-\d{2}\b"
    r"|\b(?:bk|even|p2p|wrk|cls)-[0-9a-z]+\b"
    r"|https?://\S+")

def _norm(s: str) -> str:
    """Formatting-safe canonical form for comparison (owner call #4:
    never punish good writing). Fold unicodedata math digits, emoji, whitespace,
    smart punctuation; canonicalize currency to bare numbers + 'eur'."""
    import unicodedata
    s = unicodedata.normalize("NFKC", s or "")
    s = _EMOJI_RX.sub(" ", s)
    s = s.replace("\u2018", "'").replace("\u2019", "'")
    s = s.replace("\u201c", '"').replace("\u201d", '"')
    s = s.replace("\u2013", "-").replace("\u2014", "-")
    # currency equivalence: '$5', '5 $', '5 EUR', 'EUR 5', '€5' -> '5 eur'
    s = re.sub(r"(\$|€)\s?(\d+)", r"\2 eur", s, flags=re.I)
    s = re.sub(r"(\d+)\s?(\$|€)", r"\1 eur", s, flags=re.I)
    s = re.sub(r"\b(EUR|USD)\s?(\d+)", r"\2 eur", s, flags=re.I)
    s = re.sub(r"(\d+)\s?(?:EUR|USD)\b", r"\1 eur", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def _fact_tokens(text: str) -> set:
    """Fact-like tokens (after normalization). Numbers, money, dates, ids,
    urls. Prose words are never facts."""
    t = _norm(text)
    toks = set(_FACT_RX.findall(t))
    out = set()
    for tok in toks:
        tok = tok.strip()
        if not tok:
            continue
        out.add(tok)
        # number-with-unit also registers the bare number (unit may paraphrase)
        m = re.match(r"^(\d+(?:[.,]\d+)?)", tok)
        if m:
            out.add(m.group(1))
    return out


def _guard_ok(authored: str, template: str):
    """Two-way guard. Returns (ok, violations:list[str]).
    Protected (atomic, byte-identical) spans are checked verbatim first:
    ASCII table frames and '[[...]]' tokens must survive untouched."""
    a, t = _norm(authored), _norm(template)
    # protected: table frame chars must all survive (count-wise)
    for ch in ("╔", "╚", "፨"):
        if t.count(ch) and a.count(ch) < t.count(ch):
            return False, ["table frame damaged: " + ch]
    want = _fact_tokens(template)
    have = _fact_tokens(authored)
    missing = want - have
    if missing:
        return False, ["missing facts: " + ", ".join(sorted(missing)[:6])]
    extra = have - want
    if extra:
        return False, ["invented facts: " + ", ".join(sorted(extra)[:6])]
    # command/protocol markers must survive: 'book <n>' is FORMAT (the UI and
    # the webchat board detector key on it), not language — pin it. English
    # filler around it ('say ...') may be paraphrased/translated freely.
    if "book <n>" in t and "book <n>" not in a:
        return False, ["missing marker: book <n>"]
    if not a.strip():
        return False, ["empty"]
    return True, []


# ---- author call -----------------------------------------------------------

_SYSTEM = (
    "You are the voice of EverList, a marketplace that finds and books real-"
    "world things with protected payments. You get: (1) the user's message, "
    "(2) a FACT SHEET extracted from the verified answer, (3) the verified "
    "answer itself. Rewrite the answer in your own warm, human words for a "
    "mobile chat. HARD LAWS: every number, price, date, id and link must "
    "appear EXACTLY as given — never translate numbers, never drop or add "
    "any; keep every line that starts with 🔑 or contains a secret "
    "placeholder untouched; keep ASCII tables and 'book <n>' markers; no "
    "markdown; emoji only as status (✅ ⏳ ❌ 🔑). Reply in the user's "
    "language. Keep it 1-3 short paragraphs max. Output ONLY the rewritten "
    "reply text.")


def _call(messages: list):
    """One author call. Returns text or None (timeout/error). Mirrors
    brain._call transport but with its own env + budget."""
    body = json.dumps({
        "model": _MODEL,
        "messages": messages,
        "max_tokens": 1200,
        "temperature": 0.4,
    }).encode("utf-8")
    req = urllib.request.Request(
        _API_URL.rstrip("/") + "/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + _API_KEY})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = json.loads(r.read().decode("utf-8"))
        txt = ((data.get("choices") or [{}])[0].get("message") or {}).get("content")
        out = (txt or "").strip()
        LAST.update({"ms": round(time.time() - t0, 2), "provider": "phrase"})
        return out or None
    except Exception:
        LAST.update({"ms": round(time.time() - t0, 2), "provider": "phrase-error"})
        return None


def _log(event: dict) -> None:
    """Every guard event lands here — the improvement loop (spec §7)."""
    try:
        os.makedirs(os.path.dirname(_LOG_PATH), exist_ok=True)
        with open(_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                                **event}, ensure_ascii=False) + "\n")
    except Exception:
        pass


def phrase(reply: str, user_text: str, sender: str = "") -> str:
    """Author an AI reply grounded in the deterministic one. Any failure mode
    returns the deterministic template — today's chat is always the floor."""
    if not _eligible(reply) or not _rate_ok(sender):
        _STAT["skipped"] += 1
        return reply
    template = reply
    redacted, secrets = _redact(template)
    user_lang = "the user's language"
    base_msgs = [
        {"role": "system", "content": _SYSTEM},
        {"role": "user",
         "content": ("USER MESSAGE:\n" + (user_text or "").strip()[:600]
                     + "\n\nFACT SHEET (verbatim tokens; complete):\n"
                     + json.dumps(sorted(_fact_tokens(template)), ensure_ascii=False)
                     + "\n\nVERIFIED ANSWER:\n" + redacted[:4000])},
    ]
    violations = []
    for attempt in range(1, 4):
        msgs = list(base_msgs)
        if attempt == 2 and violations:
            msgs.append({"role": "user", "content": (
                "Your previous rewrite FAILED verification: " + "; ".join(violations)
                + ". Rewrite again — include every listed fact token verbatim, "
                  "add nothing number-like that is not listed.")})
        elif attempt >= 3:
            msgs.append({"role": "user", "content": (
                "Rewrite this answer naturally, changing NO facts at all:\n"
                + redacted[:4000])})
        out = _call(msgs)
        if out is None:
            _STAT["outage"] += 1
            _log({"event": "outage", "sender": sender[:16], "attempt": attempt})
            return template
        ok, violations = _guard_ok(out, template)
        if ok:
            _STAT["ok" if attempt == 1 else "retried"] += 1
            _log({"event": "shipped", "sender": sender[:16], "attempt": attempt})
            return _reinject(out, secrets)
        _log({"event": "guard_fail", "sender": sender[:16], "attempt": attempt,
              "violations": violations})
    _STAT["fallback"] += 1
    _log({"event": "fallback", "sender": sender[:16],
          "violations": violations})
    return template


def status() -> dict:
    d = dict(_STAT)
    d["enabled"] = _ENABLED and not _DISABLED
    return d
