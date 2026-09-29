/* EverList webchat — CSP-safe: no eval, no inline handlers, textContent-only rendering.
   U1: chat-first hero on first visit; after engagement the dock carries the chat.
   A manual Discover grid renders real hub listings via read-only /api/listings. */
"use strict";

/* i18n 2026-09-28: client chrome follows document locale (html lang).
   Chat protocol commands (book/list/show) stay English by design.
   Wordings mirror i18n.py so SSR and client never disagree. */
const LANG = (document.documentElement.lang || "en").toLowerCase().indexOf("de") === 0 ? "de" : "en";
const DE_STRINGS = {
  "Free": "Kostenlos",
  "Untitled": "Ohne Titel",
  "details": "Details",
  "share": "teilen",
  "edit": "bearbeiten",
  "archived": "archiviert",
  "live": "live",
  "offline": "offline",
  "unarchive": "reaktivieren",
  "archive": "archivieren",
  "Book \u00b7 ": "Buchen \u00b7 ",
  "Ask AI to book": "EverList zum Buchen bitten",
  "money held safely": "Geld sicher verwahrt",
  "free (no payment)": "kostenlos (keine Zahlung)",
  "released to owner": "an Veranstalter freigegeben",
  "refunded": "zur\u00fcckerstattet",
  "instant \u2014 settled": "sofort \u2014 abgewickelt",
  "no payment needed": "keine Zahlung n\u00f6tig",
  "payment timeline": "Zahlungszeitlinie",
  "asked": "gefragt",
  "held": "gehalten",
  "happened": "stattgefunden",
  "released": "freigegeben",
  "upcoming happenings \u00b7 dated events & classes": "anstehende Veranstaltungen \u00b7 Events & Kurse mit Datum",
  "0 upcoming happenings": "0 anstehende Veranstaltungen",
  "hub offline": "Hub offline",
  "Your payment stays protected until the event ends": "Ihre Zahlung bleibt gesch\u00fctzt, bis die Veranstaltung vorbei ist",
  "on request": "auf Anfrage",
  " left": " frei",
  "More from this organizer": "Mehr von diesem Veranstalter",
  "Ask EverList to book this": "EverList bitten, dies zu buchen",
  "Add to calendar": "Zum Kalender hinzuf\u00fcgen",
  "Cancel & refund": "Stornieren & Erstattung",
  "Confirm & release": "Best\u00e4tigen & Freigabe",
  "Log in": "Anmelden",
  "a name is required": "Ein Name ist erforderlich",
  "starting\u2026": "starte\u2026",
  "creating account\u2026": "Konto wird erstellt\u2026",
  "signing you in\u2026": "Anmeldung l\u00e4uft\u2026",
  "generating your key in-browser\u2026": "Ihr Schl\u00fcssel wird im Browser erzeugt\u2026",
  "solving proof-of-work\u2026": "Proof-of-Work wird gel\u00f6st\u2026",
  "I've saved it \u2014 continue": "Gesichert \u2014 weiter",
  "signup failed": "Registrierung fehlgeschlagen",
  "signup rejected": "Registrierung abgelehnt",
  "login failed": "Anmeldung fehlgeschlagen",
  "action failed": "Aktion fehlgeschlagen",
  "proof-of-work failed": "Proof-of-Work fehlgeschlagen",
  "challenge unavailable": "Challenge nicht verf\u00fcgbar",
  "No bookings yet \u2014 search in the chat, then say \u201cbook 1\u201d.": "Noch keine Buchungen \u2014 suchen Sie im Chat und sagen Sie dann \u201ebook 1\u201c.",
  "No orders yet \u2014 orders for your listings appear here.": "Noch keine Bestellungen \u2014 Bestellungen f\u00fcr Ihre Inserate erscheinen hier.",
  "Log in to see your bookings.": "Melden Sie sich an, um Ihre Buchungen zu sehen.",
  "Orders for your listings appear here.": "Bestellungen f\u00fcr Ihre Inserate erscheinen hier.",
  "No listings yet \u2014 type 'list Title | category | date | price | City' in the chat to create one.": "Noch keine Inserate \u2014 tippen Sie 'list Titel | Kategorie | Datum | Preis | Stadt' in den Chat, um eines zu erstellen.",
  "your listing \u00b7 preview": "Ihr Inserat \u00b7 Vorschau",
  "confirm in chat to publish \u00b7 edit like 'price: 20' or 'make it free'": "im Chat best\u00e4tigen zum Ver\u00f6ffentlichen \u00b7 bearbeiten wie 'price: 20' oder 'make it free'",
  "No dated happenings on the board right now. Everything else that is listed stays reachable \u2014 just search in the chat below.": "Gerade keine datierten Veranstaltungen auf dem Board. Alles andere Gelistete bleibt erreichbar \u2014 einfach im Chat unten suchen.",
  "Nothing here yet \u2014 be the first. Type \u201clist \u2026\u201d in the chat below, or tap \u201c+ list a thing\u201d.": "Noch nichts hier \u2014 seien Sie der/die Erste. Tippen Sie \u201elist \u2026\u201c in den Chat unten oder auf \u201e+ inserieren\u201c.",
  "That one slipped through my hands \u2014 try again?": "Das ist mir durch die Finger gerutscht \u2014 noch einmal versuchen?",
  "Hmm, the connection hiccuped \u2014 give it another go and I'll pick it up. \ud83d\ude4f": "Huch, die Verbindung hat gestockt \u2014 versuchen Sie es noch einmal, ich nehme es wieder auf. \ud83d\ude4f",
  "Hmm, the connection hiccuped \u2014 give it another go. \ud83d\ude4f": "Huch, die Verbindung hat gestockt \u2014 versuchen Sie es noch einmal. \ud83d\ude4f",
  "Give me ": "Geben Sie mir ",
  "s to catch my breath \u2014 then send that again. \ud83d\ude4f": "s Verschnaufpause \u2014 dann senden Sie das noch einmal. \ud83d\ude4f",
  "account created \u2014 auto sign-in failed; log in with the seed above.": "Konto erstellt \u2014 automatische Anmeldung fehlgeschlagen; melden Sie sich mit dem Seed oben an.",
  "paste your account seed (shown once at signup)": "Ihren Account-Seed hier einf\u00fcgen (bei Registrierung einmalig angezeigt)",
  " \u2014 your key is generated in your browser and the seed is shown once.": " \u2014 Ihr Schl\u00fcssel wird im Browser erzeugt und der Seed einmalig angezeigt.",
  "Log in with your account seed and your bookings + orders appear here. No seed yet? ": "Melden Sie sich mit Ihrem Account-Seed an \u2014 Ihre Buchungen und Bestellungen erscheinen hier. Noch kein Seed? ",
  "Create an account right here": "Hier direkt ein Konto erstellen",
  " \u00b7 human-verified": " \u00b7 menschlich verifiziert",
  "free this weekend": "dieses Wochenende kostenlos",
  "everything I can do": "alles, was ich kann",
  "example \u2014 not a real chat": "Beispiel \u2014 kein echter Chat",
  "show full conversation": "vollst\u00e4ndige Unterhaltung anzeigen",
  "test listing": "Test-Inserat",
  "any date": "beliebiges Datum",
  "any time": "jederzeit",
  "older messages trimmed to keep the session fast": "\u00e4ltere Nachrichten gek\u00fcrzt, damit die Sitzung schnell bleibt",
  "holding your payment\u2026": "Ihre Zahlung wird verwahrt\u2026",
  "money held safely \u2014 released to the organizer after the event": "Geld sicher verwahrt \u2014 nach der Veranstaltung an den Veranstalter freigegeben",
  "Create an account": "Konto erstellen",
  "My bookings": "Meine Buchungen",
  "/5 paid reviews (": "/5 bezahlte Bewertungen (",
  "free-class ": "kostenlose Bewertungen ",
  "Owner receives ": "Veranstalter erh\u00e4lt ",
  "Booking": "Buchung",
  "payment status is now ": "Zahlungsstatus ist jetzt ",
  "updated": "aktualisiert",
  "Money is held safely until it happens": "Ihr Geld wird sicher verwahrt, bis es stattfindet",
  "free cancellation within ": "kostenlose Stornierung innerhalb ",
  "h.": "Std.",
  "Your account SEED \u2014 shown ONCE, store it like a crypto seed phrase. It is your only way to log in elsewhere:": "Ihr Account-SEED \u2014 einmalig angezeigt, bewahren Sie ihn wie eine Seed-Phrase auf. Er ist Ihre einzige M\u00f6glichkeit, sich woanders anzumelden:",
};
function L(s) { return (LANG === "de" && s != null && Object.prototype.hasOwnProperty.call(DE_STRINGS, s)) ? DE_STRINGS[s] : s; }
function fmtEUR(n) {
  const v = Number(n);
  if (isNaN(v)) return String(n);
  if (LANG === "de") return v.toFixed(2).replace(".", ",") + " \u20ac";
  return "\u20ac" + (Number.isInteger(v) ? v : v.toFixed(2));
}
function fmtNum(n) {
  if (LANG !== "de") return n;
  const s = String(n);
  return s.indexOf(".") === -1 ? s : s.replace(".", ",");
}
/* German ghost fixture: the first-visit demo conversation, localized end-to-end */
const DE_GHOST_FIXTURE = {
  q: "irgendwas mit Jazz in Wien dieses Wochenende",
  a: "3 gefunden \u2014 Rooftop Jazz Night passt: Quartett, Sonnenuntergang, 15,00 \u20ac am 3. Okt. Soll ich buchen?",
  card: { title: "Rooftop Jazz Night", when: "3. Okt \u00b7 Wien", price: "15,00 \u20ac" },
  esc: "Geld sicher verwahrt \u2014 nach der Veranstaltung an den Veranstalter freigegeben",
};

const chat = document.getElementById("chat");
const form = document.getElementById("form");
const input = document.getElementById("text");
const sendBtn = document.getElementById("send");
const dot = document.getElementById("dot");
const statusText = document.getElementById("status-text");
const chips = document.getElementById("chips");
const resetBtn = document.getElementById("reset");

const grid = document.getElementById("grid");
const countEl = document.getElementById("count");
const emptyEl = document.getElementById("empty");
const filters = document.getElementById("filters");
const minBtn = document.getElementById("minbtn");
const pill = document.getElementById("pill");
const postBtn = document.getElementById("postBtn") || document.getElementById("postbtn");
const navPost = document.getElementById("nav-post");

/* U1: hero (first-visit chat) + engagement switch */
const heroSec = document.getElementById("hero");
const heroForm = document.getElementById("hero-form");
const heroText = document.getElementById("hero-text");
const heroChips = document.getElementById("hero-chips");
const heroStrip = document.getElementById("hero-strip");
const dock = document.getElementById("dock");

function isEngaged() {
  try { return sessionStorage.getItem("el-engaged") === "1"; } catch (e) { return false; }
}
function setEngaged() {
  try { sessionStorage.setItem("el-engaged", "1"); } catch (e) {}
  document.body.classList.add("engaged");
  if (dock) dock.hidden = false;
  if (heroSec) heroSec.hidden = true;
}

/* Wave 1 item 6 — choreographed handoff: the hero stays until the first agent
   reply STARTS (the think dots are that signal), then fades out while the dock
   scrolls into view. One transition, no FLIP machinery. */
let handoffDone = false;
function beginHandoff() {
  if (handoffDone || document.body.classList.contains("engaged")) { handoffDone = true; return; }
  handoffDone = true;
  if (REDUCE() || !heroSec || !dock) { setEngaged(); return; }
  document.body.classList.add("engaged-leaving");
  if (dock.hidden) dock.hidden = false;
  dock.scrollIntoView({ behavior: "smooth", block: "end" });
  setTimeout(() => {
    document.body.classList.remove("engaged-leaving");
    setEngaged();
    window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
    if (pendingCompact) { pendingCompact = false; enterCompact(); } /* item 7: fold now */
  }, 340);
}
function unengage() {
  /* back to the hero state (new session button) */
  try { sessionStorage.removeItem("el-engaged"); } catch (e) {}
  document.body.classList.remove("engaged");
  if (dock) dock.hidden = true;
  if (heroSec) heroSec.hidden = false;
}

let busy = false;
let ALL = [];           // default board: all live listings
let BOARD = null;       // chat results mode: listing dicts in 'book <n>' order; null = default board
let SIG = "";           // signature of rendered chat results (skips no-op re-renders)

const TRANSCRIPT_CAP = 50000; /* chars of live transcript (~12k tokens; the
  brain itself is stateless per message, so this bounds the DOM session) */
let capNoticeShown = false;

/* U6: transcript persistence — restore on reload, cleared by 'new session' */
const TS_KEY = "el-transcript";
function saveTranscript() {
  try {
    const items = [];
    chat.querySelectorAll(".msg").forEach((m) => {
      const b = m.querySelector(".bubble");
      if (b && !m.classList.contains("think")) items.push(m.className.replace("msg ", "") + "\u0001" + b.textContent);
    });
    sessionStorage.setItem(TS_KEY, JSON.stringify(items));
  } catch (e) {}
}
function restoreTranscript() {
  try {
    const raw = sessionStorage.getItem(TS_KEY);
    if (!raw) return false;
    const items = JSON.parse(raw);
    if (!Array.isArray(items) || !items.length) return false;
    chat.innerHTML = "";
    items.forEach((it) => {
      const [cls, ...rest] = String(it).split("\u0001");
      if (cls && rest.length) addMsg(cls, rest.join("\u0001"));
    });
    return true;
  } catch (e) { return false; }
}

function transcriptChars() {
  let n = 0;
  chat.querySelectorAll(".bubble").forEach((b) => { n += (b.textContent || "").length; });
  return n;
}

function trimTranscript() {
  let total = transcriptChars();
  if (total <= TRANSCRIPT_CAP) return;
  for (const m of Array.from(chat.children)) {
    if (total <= TRANSCRIPT_CAP) break;
    const b = m.querySelector(".bubble");
    total -= (b && b.textContent ? b.textContent.length : 0) + 16;
    m.remove();
  }
  if (!capNoticeShown) {
    capNoticeShown = true;
    const wrap = document.createElement("div");
    wrap.className = "msg think";
    const b = document.createElement("div");
    b.className = "bubble";
    b.textContent = "\u00b7 " + L("older messages trimmed to keep the session fast");
    wrap.appendChild(b);
    chat.insertBefore(wrap, chat.firstChild);
  }
}

/* ---------- chat (unchanged brain wiring) ---------- */
function addMsg(cls, text) {
  const wrap = document.createElement("div");
  wrap.className = "msg " + cls;
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text; /* XSS-safe by construction */
  wrap.appendChild(bubble);
  chat.appendChild(wrap);
  trimTranscript();
  chat.scrollTop = chat.scrollHeight;
  return bubble;
}

function setBusy(b) { busy = b; sendBtn.disabled = b; input.disabled = b; }

let morphUntil = 0; /* morph guard: while a close/open animation runs, re-triggers are ignored (oscillation fix) */
function openChat() {
  if (Date.now() < morphUntil) return;
  const wasMin = document.body.classList.contains("min");
  /* origin fix (owner retest): measure the pill WHILE it is still visible.
     After .min is removed the pill is display:none and its rect collapses
     to zeros — the pop-out vector then pointed at the viewport top-left
     corner instead of the pill. */
  let pr = null;
  if (wasMin && pill) pr = pill.getBoundingClientRect();
  document.body.classList.remove("min");
  /* Owner call: restoring from the pill ALWAYS comes back in the non-expanded
     (compact) size — only an explicit tap on the chat itself expands the
     full panel again. Must run BEFORE the panel rect is measured. */
  if (wasMin && !compact) enterCompact();
  /* Owner ask 2026-09-24: cinematic open — the panel pops out of the pill
     with elastic overshoot (from a tiny circle at the pill's position). */
  if (wasMin && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    morphUntil = Date.now() + 520;   /* oscillation fix: block re-triggers until the pop-out settles */
    if (pr) {
      const panel = dock.querySelector(".panel");
      if (panel) {
        const r = panel.getBoundingClientRect();
        dock.style.setProperty("--sx", ((pr.left + pr.width / 2) - (r.left + r.width / 2)).toFixed(1) + "px");
        dock.style.setProperty("--sy", ((pr.top + pr.height / 2) - (r.top + r.height / 2)).toFixed(1) + "px");
      }
      pill.classList.remove("pop");
      void pill.offsetWidth;
      pill.classList.add("pop");
      setTimeout(() => pill.classList.remove("pop"), 380);
    }
    dock.classList.remove("popout");
    void dock.offsetWidth;
    dock.classList.add("popout");
    setTimeout(() => dock.classList.remove("popout"), 480);
  }
  setEngaged(); /* U1: any explicit chat use = engaged */
}

/* Owner ask 2026-09-24: cinematic close — the panel deforms (squash + skew,
   border-radius morphing to a circle) and gets sucked into the chat pill's
   exact position, then the dock hides. Reduced motion: instant hide. */
function minimizeChat() {
  if (document.body.classList.contains("min")) return;
  if (Date.now() < morphUntil) return;   /* oscillation fix: no re-trigger mid-morph */
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    document.body.classList.add("min");
    return;
  }
  const panel = dock.querySelector(".panel");
  if (!panel || !pill) { document.body.classList.add("min"); return; }
  /* measure the hidden pill without a visible flash */
  document.body.classList.add("min");
  pill.style.visibility = "hidden";
  const pr = pill.getBoundingClientRect();
  document.body.classList.remove("min");
  pill.style.visibility = "";
  const r = panel.getBoundingClientRect();
  const dx = (pr.left + pr.width / 2) - (r.left + r.width / 2);
  const dy = (pr.top + pr.height / 2) - (r.top + r.height / 2);
  dock.style.setProperty("--sx", dx.toFixed(1) + "px");
  dock.style.setProperty("--sy", dy.toFixed(1) + "px");
  dock.classList.add("sucking");
  morphUntil = Date.now() + 430;   /* oscillation fix: block re-triggers until the suck-in settles */
  setTimeout(() => {
    dock.classList.remove("sucking");
    document.body.classList.add("min");
  }, 390);
}

async function send(text) {
  text = (text || "").trim();
  if (!text || busy) return;
  try { sessionStorage.setItem("el-engaged", "1"); } catch (e) {} /* U1: engaged, hero fades on reply (Wave 1) */
  addMsg("user", text);
  input.value = "";
  autosize();
  setBusy(true);
  /* U6: typing indicator — three dots while the brain works */
  const think = addMsg("think", "");
  think.innerHTML = "<span class=\"typing\"><span></span><span></span><span></span></span>";
  const t0 = Date.now();
  try {
    /* W3 item 20: try the SSE stream first; on any failure fall back to the
       classic JSON POST — the reply never depends on the stream working. */
    const streamed = await sendStream(text, think);
    if (!streamed) {
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const dt = ((Date.now() - t0) / 1000).toFixed(1);
      if (res.status === 429) {
        const wait = parseInt(res.headers.get("Retry-After") || "5", 10);
        think.remove();
        beginHandoff();
        addMsg("err", L("Give me ") + wait + L("s to catch my breath \u2014 then send that again. \ud83d\ude4f"));
      } else {
        const data = await res.json().catch(() => ({}));
        think.remove();
        beginHandoff(); /* Wave 1: hero fades now that the first reply starts */
        addMsg("agent", data.reply || L("That one slipped through my hands \u2014 try again?"));
        saveTranscript(); /* U6 */
        applyEnvelope(data);
        afterReply(data, dt);
        if (data.payment_request) renderPayButton(data.payment_request, null);
      }
    } else {
      const dt = ((Date.now() - t0) / 1000).toFixed(1);
      saveTranscript(); /* U6 */
      afterReply(streamed, dt);
    }
    setStatus(true);
  } catch (e) {
    think.remove();
    beginHandoff();
    addMsg("err", L("Hmm, the connection hiccuped \u2014 give it another go and I'll pick it up. \ud83d\ude4f"));
    setStatus(false);
  } finally {
    setBusy(false);
    input.focus();
  }
}

/* W3 item 20: consume POST /api/chat/stream (text/event-stream) and render
   progressively. Resolves null when streaming is unavailable or fails so the
   caller falls back to the classic JSON POST; resolves the final payload on
   success after rendering everything the JSON path would have. */
async function sendStream(text, think) {
  let res;
  try {
    res = await fetch("/api/chat/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
  } catch (e) {
    return null;
  }
  if (!res.ok || !res.body
      || !(res.headers.get("Content-Type") || "").includes("text/event-stream")) {
    return null;
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  const frames = [];
  for (;;) {
    try {
      const rd = await reader.read();
      if (rd.done) break;
      buf += dec.decode(rd.value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const frame = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        let evname = "message";
        const dataLines = [];
        for (const ln of frame.split("\n")) {
          if (ln.startsWith("event:")) evname = ln.slice(6).trim();
          else if (ln.startsWith("data:")) dataLines.push(ln.slice(5).trim());
        }
        if (dataLines.length) {
          try { frames.push({ event: evname, data: JSON.parse(dataLines.join("\n")) }); } catch (e2) {}
        }
      }
    } catch (e) {
      return null; /* transport died mid-stream -> caller falls back */
    }
  }
  const deltas = frames.filter((f) => f.event === "delta");
  const fin = frames.find((f) => f.event === "final");
  const errFrame = frames.find((f) => f.event === "error");
  if (errFrame || !fin) return null;
  think.remove();
  beginHandoff(); /* Wave 1: hero fades now that the first reply starts */
  const bubble = addMsg("agent", "");
  const full = deltas.map((d) => String(d.data.t || "")).join("") || fin.data.reply || L("That one slipped through my hands \u2014 try again?");
  if (REDUCE() || deltas.length <= 1) {
    bubble.textContent = fin.data.reply || full;
  } else {
    await revealText(bubble, full);
  }
  applyEnvelope(fin.data);
  if (fin.data.payment_request) renderPayButton(fin.data.payment_request, bubble);
  return fin.data;
}

/* reveal reply text progressively (W3 item 20); step-capped so a long reply
   never reveals slower than ~0.6s total */
async function revealText(bubble, full) {
  const step = Math.max(8, Math.ceil(full.length / 24));
  for (let i = step; i <= full.length; i += step) {
    bubble.textContent = full.slice(0, i);
    chat.scrollTop = chat.scrollHeight;
    await new Promise((r) => setTimeout(r, 24));
  }
  bubble.textContent = full;
}

/* W3: shared post-reply intake envelope (identical to the JSON path) */
function applyEnvelope(data) {
  /* W2 item 11: the pinned preview card is driven purely by the latest reply
     (honest under a stateless brain); confirm swaps it for the real card,
     cancel/negative replies clear the slot. */
  if (data.card) {
    setDraft(data.card);
  } else if (data.draft) {
    /* active intake without card fields yet (title not answered) */
  } else if (/cancelled|don't have a listing in progress/.test(String(data.reply || ""))) {
    clearDraft();
  }
  if (/^\u2705 Listed!/.test(String(data.reply || ""))) swapDraftToReal();
}

/* W3: shared post-reply side effects (board, nav, meta line) */
function afterReply(data, dt) {
  // chat-first board: search replies open their results on screen
  if (Array.isArray(data.results)) {
    const sig = data.results.map((l) => l.id).join(",");
    if (sig !== SIG || BOARD == null) {
      SIG = sig;
      BOARD = data.results.length ? data.results : null;
      renderGrid();
      if (BOARD) {
        grid.classList.remove("boardin");
        void grid.offsetWidth; // restart entrance animation
        grid.classList.add("boardin");
        /* Alive chat (owner bundle 2026-09-24): board tether — the answer
           bubble pings toward freshly rendered cards, the cards ping back.
           One-time, subtle, reduced-motion guarded in CSS. */
        requestAnimationFrame(() => {
          grid.querySelectorAll(".card").forEach((c) => {
            c.classList.remove("cardping");
            void c.offsetWidth;
            c.classList.add("cardping");
          });
          const bubble = chat.querySelector(".chat .msg.agent .bubble");
          if (bubble) {
            bubble.classList.remove("bubbleping");
            void bubble.offsetWidth;
            bubble.classList.add("bubbleping");
          }
        });
      }
    }
    /* W2 item 6 (owner intent 2026-09-21): results live on the board now —
       the transcript folds to the compact pair (latest bubble + one-line
       composer) after EVERY reply, result-carrying or not. */
  }
  /* Breathing chat (spec 2026-09-23): the reply envelope carries a layout
     hint. 'open' = the panel must show context (listing wizard in progress,
     booking secret shown once, rejections/errors, long-form help); 'small'
     = the compact pair carries it. Client-side guard: a reply that shows
     the booking secret must NEVER live only in the small state — defense
     in depth alongside the server hint (old replies without the hint that
     contain a secret still force open). */
  const replyText = String(data.reply || "");
  const forceOpen = data.panel === "open"
    || /\ud83d\udd11|booking secret/i.test(replyText);
  if (forceOpen) {
    pendingCompact = false;
    if (document.body.classList.contains("engaged")) exitCompact();
  } else if (document.body.classList.contains("engaged")) enterCompact();
  else pendingCompact = true;   /* handoff not finished yet — fold on landing */
  /* Alive chat (owner bundle 2026-09-24): success bloom — a booking
     confirmation answer emits a one-time soft ring. Subtle celebration,
     reduced-motion guarded in CSS. */
  if (/\bbk-[0-9a-f]+/i.test(replyText) && !/rejected|failed/i.test(replyText)) {
    const bubbles = chat.querySelectorAll(".msg.agent .bubble");
    const last = bubbles[bubbles.length - 1];
    if (last) {
      last.classList.remove("bloom");
      void last.offsetWidth;
      last.classList.add("bloom");
    }
  }
  /* Owner call 2026-09-24: the keyboard must go away as soon as the answer
     arrives — the reply is for reading, not typing. Mobile only. */
  if (isMobile() && document.activeElement === input) input.blur();
  /* Item 6 (owner pick 2026-09-24): inline preview — search answers carry a
     tiny tappable row of the first 3 results INSIDE the answer bubble, so
     the two-bubble state is glanceable without touching the board. Tap =
     expand that card on the board (same openDetail path as card clicks). */
  if (Array.isArray(data.results) && data.results.length && data.panel !== "open") {
    const bubbles = chat.querySelectorAll(".msg.agent .bubble");
    const last = bubbles[bubbles.length - 1];
    if (last && !last.querySelector(".prevrow")) {
      const row = document.createElement("div");
      row.className = "prevrow";
      data.results.slice(0, 3).forEach((l) => {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "prevchip";
        const price = priceOf(l);
        chip.textContent = (l.title || L("Untitled")).slice(0, 26) + (String(l.title || "").length > 26 ? "\u2026" : "") + " \u00b7 " + price.txt;
        chip.addEventListener("click", (ev) => {
          ev.stopPropagation();
          const target = grid.querySelector('.card[data-listing]') && Array.from(grid.querySelectorAll('.card')).find((c) => {
            try { return (JSON.parse(c.dataset.listing || "{}").id) === l.id; } catch { return false; }
          });
          if (target) { openChat(); target.click(); }
        });
        row.appendChild(chip);
      });
      last.appendChild(row);
    }
    /* Item 2: ambient echo — matched cards keep a faint glow tint. */
    grid.classList.add("echo");
  }
  /* Item 9: smart expand hint — a force-open reply arriving while minimised
     bounces the pill once to invite you back in (currently it waits silently). */
  if (forceOpen && document.body.classList.contains("min") && pill) {
    pill.classList.remove("bounce");
    void pill.offsetWidth;
    pill.classList.add("bounce");
  }
  // Brain v2 nav: the chat can move you around the site for real
  if (data.nav === "dash") {
    showView(true);
  } else if (data.nav === "home") {
    BOARD = null; SIG = "";
    renderGrid();
    showView(false);
  } else if (data.nav === "results" && openDetailCard) {
    closeDetail(false);
  }
  const meta = document.createElement("div");
  meta.className = "msg think";
  const m = document.createElement("div");
  m.className = "bubble";
  m.textContent = "\u00b7 " + dt + "s";
  meta.appendChild(m);
  chat.appendChild(meta);
  chat.scrollTop = chat.scrollHeight;
}

function setStatus(ok) {
  dot.className = "dot " + (ok ? "ok" : "down");
  statusText.textContent = ok ? "online" : "offline";
}

async function pollHealth() {
  try {
    const r = await fetch("/api/health", { cache: "no-store" });
    const d = await r.json();
    setStatus(!!d.ok);
  } catch (e) { setStatus(false); }
}

function autosize() {
  input.style.height = "auto";
  input.style.height = Math.min(input.scrollHeight, 180) + "px";
}

form.addEventListener("submit", (e) => { e.preventDefault(); send(input.value); });
input.addEventListener("input", autosize);
input.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input.value); }
});
chips.addEventListener("click", (e) => {
  const b = e.target.closest(".chip");
  if (b && b.dataset.q) { openChat(); send(b.dataset.q); }
});
resetBtn.addEventListener("click", async () => {
  try { await fetch("/api/reset", { method: "POST" }); } catch (e) {}
  try { sessionStorage.removeItem("el-engaged"); sessionStorage.removeItem(TS_KEY); } catch (e2) {}
  /* bug fix 2026-09-23: after expanding a card the URL is /l/{id} (pushState);
     reloading THAT path re-opens the standalone detail page ("one box grows
     then closes"). Reset always goes to the clean home URL. */
  if (location.pathname !== "/") location.href = "/";
  else location.reload();
});

/* ---------- W2 item 6 (owner directive A): compact chat after results ----------
   When a reply carries results opened on the board, the transcript collapses to
   a compact pair: latest answer bubble + the one-line composer. Older replies
   fold into a subtle history line; expanding (affordance or history tap)
   restores the full dock; Esc collapses again. The board is never overlaid. */
let compact = false;

/* Item 7 (owner fixes 2026-09-21): the compact state must SURVIVE. The old
   version died twice: (a) the composer's focusin listener re-expanded the
   panel the instant send() refocused the input, and (b) enterCompact was
   fire-once, so follow-up replies never re-folded. Now enterCompact is an
   idempotent refresher called after EVERY reply, nothing auto-expands, and
   only an explicit user gesture (history line, bubble tap, expand) or the
   pill restores the full panel. */
function expandBtnEl() {
  let b = document.getElementById("expandbtn");
  if (!b) {
    b = document.createElement("button");
    b.id = "expandbtn";
    b.className = "expandbtn";
    b.type = "button";
    b.textContent = "\u25b4 " + L("show full conversation");
    b.addEventListener("click", exitCompact);
    form.parentNode.insertBefore(b, form);
  }
  return b;
}
function enterCompact() {
  compact = true;
  document.body.classList.add("chatcompact");
  /* Owner call 2026-09-23 v3: exactly TWO things in the minimal state — the
     answer bubble and the reply input. No history line, no expand button:
     tapping the answer bubble expands the full conversation instead. */
  const real = Array.from(chat.querySelectorAll(".msg"))
    .filter((m) => !m.classList.contains("think"));
  real.slice(0, -1).forEach((m) => m.classList.add("folded"));
  Array.from(chat.querySelectorAll(".msg.think")).forEach((m) => m.classList.add("folded"));
  const n = real.length - 1;
  let line = chat.querySelector(".historyline");
  if (n > 0) {
    if (!line) {
      line = document.createElement("div");
      line.className = "historyline";
      line.setAttribute("role", "button");
      line.tabIndex = 0;
      line.addEventListener("click", exitCompact);
      line.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); exitCompact(); } });
      chat.insertBefore(line, chat.firstChild);
    }
    line.textContent = "\u25b8 " + n + (LANG === "de" ? " \u00e4ltere Nachricht" + (n === 1 ? "" : "en") : " earlier message" + (n === 1 ? "" : "s"));
  } else if (line) {
    line.remove();
  }
  chat.scrollTop = chat.scrollHeight;
}

function exitCompact() {
  if (!compact) return;
  compact = false;
  document.body.classList.remove("chatcompact");
  chat.querySelectorAll(".msg.folded").forEach((m) => m.classList.remove("folded"));
  const line = chat.querySelector(".historyline");
  if (line) line.remove();
}
/* Item 7: the hero handoff adds .engaged ~340ms after the first reply starts;
   a fast reply can finish BEFORE that. Record the intent and fold as soon as
   engagement lands — the compact state must never be lost to a race. */
let pendingCompact = false;

input.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && !openDetailCard) {
    if (compact) {
      /* W3 item 20: Esc again minimises the dock entirely */
      minimizeChat();
      return;
    }
    if (document.body.classList.contains("engaged")) enterCompact();
  } else if (e.key === "ArrowUp" && !input.value
             && !e.metaKey && !e.ctrlKey && !e.altKey) {
    /* W3 item 20: ↑ recalls the user's last message for editing/resending */
    try {
      const last = sessionStorage.getItem("el-lastmsg");
      if (last) { input.value = last; autosize(); }
    } catch (e2) {}
  }
});
/* Item 7: Esc works from anywhere in the page, not just the composer —
   collapsed by default, expand gesture re-collapses it again. */
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape" || e.target === input || e.target === heroText) return;
  if (openDetailCard) return;
  if (!compact && document.body.classList.contains("engaged")
      && !document.body.classList.contains("min")) enterCompact();
  else if (compact) exitCompact();
});
/* Owner call 2026-09-21: clicking OUTSIDE the expanded detail box shrinks it
   again. Clicks inside the panel and on cards (own toggle/navigation handling)
   are ignored — those have their own behavior. Hero-strip cards are ignored
   too: their click OPENS a detail panel (bug fix 2026-09-23 — the old check
   let this handler close the panel in the same click that opened it). */
document.addEventListener("click", (e) => {
  if (!openDetailCard || !detailPanel) return;
  const t = e.target;
  if (detailPanel.contains(t)) return;          /* inside the panel: keep open */
  if (t.closest && t.closest(".card, .hero-card")) return; /* own handlers act */
  if (t.closest && t.closest(".dock, #dock, .chatdock")) return; /* chat stays */
  closeDetail(false);
});
/* expand affordance: tapping any visible bubble (or the composer area)
   restores the full transcript while compact. The composer itself is NOT an
   expand trigger (item 7): typing/sending must never re-expand the panel. */
chat.addEventListener("click", (e) => {
  if (compact && e.target.closest(".msg")) exitCompact();
});
/* Item 10: time-of-day warmth — the day's first load tints the glow */
(function () {
  const h = new Date().getHours();
  document.documentElement.classList.add(h >= 6 && h < 18 ? "day-warm" : "day-cool");
})();

/* ---------- chat dock minimise / pill ---------- */
if (minBtn) minBtn.addEventListener("click", () => { minimizeChat(); });
if (pill) pill.addEventListener("click", () => { openChat(); input.focus(); });
/* Owner call 2026-09-24: on phones, interacting with the page minimises the
   chat to the pill — the pair must never fight the content for attention.
   Scroll past a threshold or tap anywhere outside the dock/pill -> min.
   Desktop keeps explicit control (Esc / minimise button) only. */
const isMobile = () => window.matchMedia("(max-width: 860px)").matches;
/* Owner fix 2026-09-24: scrolling must NOT minimize — the answer stays pinned
   while you read the board. The pair dims after 7s idle (any touch restores
   full opacity) and only a tap outside dock/pill minimizes. */
let idleTimer = null;
function armIdleFade() {
  if (!isMobile() || !compact || document.body.classList.contains("min")) return;
  document.body.classList.remove("chatdim");
  clearTimeout(idleTimer);
  idleTimer = setTimeout(() => {
    if (isMobile() && compact && !document.body.classList.contains("min")) document.body.classList.add("chatdim");
  }, 5000);   /* owner call: ~5s of not interacting -> fades out */
}
window.addEventListener("scroll", armIdleFade, { passive: true });
document.addEventListener("pointerdown", (e) => {
  /* owner call 2026-09-24: interacting with the page (detail panel, cards,
     buttons) auto-shrinks the chat on EVERY device. Expanded -> folds to the
     compact pair; compact pair -> tucks into the pill. */
  if (!document.body.classList.contains("engaged")) return;   /* hero state: nothing to shrink */
  if (e.target.closest("#dock") || e.target.closest("#pill")) { if (compact) armIdleFade(); return; }
  if (document.body.classList.contains("min")) return;
  if (compact) minimizeChat();   /* compact pair -> pill (with the suck-in) */
  else enterCompact();           /* expanded panel -> shrink to the compact pair */
}, true);
window.addEventListener("resize", armIdleFade, { passive: true });
/* Desktop extras (items 3+4): cursor-follow tilt on the pair, and a gentle
   settle when you scroll deep into the board. Both reduced-motion aware. */
if (window.matchMedia("(min-width: 861px)").matches) {
  const dockEl = document.getElementById("dock");
  dockEl.addEventListener("pointermove", (e) => {
    if (!compact || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const r = dockEl.getBoundingClientRect();
    const dx = e.clientX / Math.max(1, r.width) - 0.5;
    const dy = (e.clientY - r.top) / Math.max(1, r.height) - 0.5;
    dockEl.style.setProperty("--tiltX", (-dy * 1.6).toFixed(2) + "deg");
    dockEl.style.setProperty("--tiltY", (dx * 1.6).toFixed(2) + "deg");
  });
  dockEl.addEventListener("pointerleave", () => {
    dockEl.style.setProperty("--tiltX", "0deg"); dockEl.style.setProperty("--tiltY", "0deg");
  });
  window.addEventListener("scroll", () => {
    document.body.classList.toggle("chatlow", window.scrollY > 420);
  }, { passive: true });
}
/* Item 1: category-hue glow — hovering a card tints the answer bubble's
   border/glow with that card's family hue (the chat speaks the board's
   color language). */
grid.addEventListener("pointerover", (e) => {
  const card = e.target.closest(".card"); if (!card) return;
  const tag = card.querySelector(".vtag"); if (!tag) return;
  document.documentElement.style.setProperty("--livehue", getComputedStyle(tag).color);
});
grid.addEventListener("pointerout", (e) => {
  if (e.target.closest(".card")) document.documentElement.style.removeProperty("--livehue");
});

/* ---------- post-a-listing affordances ---------- */
/* ---------- U2: listing by conversation (wizard deleted) ----------
   All listing creation goes through the chat brain's guided intake:
   one field at a time, live preview card on the board, confirm to create. */
function startPost(prefill) {
  /* prefill (legacy edit button): compose an edit command for the brain */
  if (prefill && prefill.id) {
    openChat();
    send("edit " + prefill.id + " title: " + (prefill.title || ""));
    return;
  }
  openChat();
  send("list");
}
if (postBtn) postBtn.addEventListener("click", () => startPost());
if (navPost) navPost.addEventListener("click", (e) => { e.preventDefault(); startPost(); });

/* ---------- Discover grid (real data, CSP-safe DOM) ---------- */
const MONTHS = LANG === "de" ? ["Jan","Feb","M\u00e4r","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"] : ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function fmtDate(d) {
  if (!d) return null;
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(d));
  if (!m) return { big: String(d).slice(0, 6), small: "" };
  return { big: m[3], small: MONTHS[(+m[2]) - 1] || "" };
}

function priceOf(l) {
  const p = (l.price != null ? l.price : l.amount);
  const n = parseFloat(p);
  if (isNaN(n)) return { txt: p ? String(p) : "\u2014", esc: false, free: false };
  /* F6: price 0 books WAIVED — nothing is held, so no lock/escrow copy */
  if (n === 0) return { txt: L("Free"), esc: false, free: true };
  if (LANG === "de") return { txt: n.toFixed(2).replace(".", ",") + " \u20ac", esc: true, free: false };
  return { txt: "\u20ac" + (Number.isInteger(n) ? n : n.toFixed(2)), esc: true, free: false };
}

function spotsLeft(l) {
  const cap = parseInt(l.capacity, 10);
  const reg = parseInt(l.registered != null ? l.registered : l.booked, 10);
  if (!isNaN(cap) && cap > 0) {
    const left = (!isNaN(reg) ? Math.max(0, cap - reg) : cap);
    /* F15/Wave1: capacity is noise on a healthy card — surface it ONLY when
       <=20% is left, in the warm urgency hue (real counts, I9-safe). */
    const urgent = left > 0 && left <= Math.max(1, Math.ceil(cap * 0.2));
    return { txt: left + L(" left"), urgent, low: urgent, left, cap };
  }
  if (!isNaN(cap) && cap === 0) return { txt: L("on request"), urgent: false, low: false };
  return null;
}

function makeCard(l, featured, n) {
  const card = document.createElement("article");
  const sp0 = spotsLeft(l);
  card.className = "card" + (featured ? " feat" : "")
    + (sp0 && sp0.low ? " lowcap" : "");
  card.dataset.listing = JSON.stringify(l);
  if (n != null) card.dataset.idx = String(n);
  if (l.preview) card.classList.add("draftcard", "heartbeat"); // W2 item 11 + alive chat: dashed preview card, pulsing in sync with the bubble glow (item 7, pure CSS — no speech involved)

  const r1 = document.createElement("div"); r1.className = "r1";
  const dt = fmtDate(l.date);
  if (dt) {
    const date = document.createElement("span"); date.className = "date";
    const b = document.createElement("b"); b.textContent = dt.big;
    const s = document.createElement("s"); s.textContent = fmtTime(l.time) ? dt.small + " · " + fmtTime(l.time) : dt.small;
    date.appendChild(b); date.appendChild(s); r1.appendChild(date);
  } else {
    /* U4/F6: 'any time' wording instead of the cryptic infinity symbol */
    const date = document.createElement("span"); date.className = "date";
    const b = document.createElement("b"); b.textContent = LANG === "de" ? "jeder" : "any";
    const s = document.createElement("s"); s.textContent = LANG === "de" ? "Zeit" : "time";
    date.appendChild(b); date.appendChild(s); r1.appendChild(date);
  }
  const vtag = document.createElement("span");
  const cat = String(l.category || l.vertical || "listing").toLowerCase();
  vtag.className = "vtag c-" + cat.replace(/[^a-z0-9-]/g, "");
  vtag.textContent = ((l.category || l.vertical || "listing").toUpperCase());
  r1.appendChild(vtag);
  if (n != null) {
    const bN = document.createElement("span"); bN.className = "bkn";
    bN.textContent = "book " + n;
    r1.appendChild(bN);
  }
  if (featured) {
    const sp = spotsLeft(l);
    if (sp && sp.low) { const cap = document.createElement("span"); cap.className = "cap urgent"; cap.textContent = sp.txt; r1.appendChild(cap); }
  }
  card.appendChild(r1);

  const h3 = document.createElement("h3"); h3.textContent = l.title || L("Untitled"); card.appendChild(h3);

  if (l.description) {
    const desc = document.createElement("p"); desc.className = "desc";
    desc.textContent = String(l.description).slice(0, 220) + (String(l.description).length > 220 ? "\u2026" : "");
    card.appendChild(desc);
  }

  const metaBits = [];
  if (l.location) metaBits.push(l.location);
  const sp2 = spotsLeft(l);
  if (!featured && sp2 && sp2.low) metaBits.push(sp2.txt); /* only when <=20% left */
  if (l.owner_public) metaBits.push(l.owner_public);
  if (metaBits.length) { const meta = document.createElement("div"); meta.className = "meta"; meta.textContent = metaBits.join(" \u00b7 "); card.appendChild(meta); }

  /* W4: honest ratings from the hub's S6 aggregates — paid reviews are
     amount-weighted server-side, free-class feedback is a separate channel.
     No reviews -> render nothing; we never fake stars. */
  const rateBits = [];
  if ((l.rating_count | 0) > 0) {
    let avg = 0;
    if ((l.rating_wtot || 0) > 0) avg = (l.rating_wsum || 0) / l.rating_wtot;
    else avg = (l.rating_avg != null) ? l.rating_avg : ((l.rating_sum || 0) / l.rating_count);
    rateBits.push("\u2605 " + fmtNum(Math.round(avg * 10) / 10) + "/5 (" + l.rating_count + ")");
  }
  if ((l.free_rating_count | 0) > 0) {
    rateBits.push(L("free-class ") + fmtNum(Math.round((l.free_rating_sum || 0) / l.free_rating_count * 10) / 10) + "/5 (" + l.free_rating_count + ")");
  }
  if (rateBits.length) { const rl = document.createElement("div"); rl.className = "rline"; rl.textContent = rateBits.join(" \u00b7 "); card.appendChild(rl); }

  const foot = document.createElement("div"); foot.className = "foot";
  const pr = priceOf(l);
  const price = document.createElement("span");
  price.className = "price" + (pr.free ? " free" : "");
  price.textContent = pr.txt; foot.appendChild(price);
  /* W2: shareable, indexable detail page (server-rendered, no-JS surface) */
  if (l.id) {
    const dl = document.createElement("a"); dl.className = "dlink";
    dl.href = "/l/" + encodeURIComponent(l.id);
    dl.target = "_blank"; dl.rel = "noopener";
    dl.textContent = L("details");
    foot.appendChild(dl);
  }
  /* U4/F7: escrow becomes a lock glyph with tooltip — one glance, no clutter */
  const esc = document.createElement("span"); esc.className = "esc";
  esc.textContent = pr.esc ? "\u272a" : "";
  if (pr.esc) esc.title = L("Your payment stays protected until the event ends");
  foot.appendChild(esc);
  /* U4/F16: share button (Web Share API, clipboard fallback) */
  if (l.id && navigator.share) {
    const sh = document.createElement("button"); sh.className = "linkbtn"; sh.type = "button";
    sh.textContent = L("share");
    sh.addEventListener("click", (ev) => {
      ev.stopPropagation();
      navigator.share({ title: l.title || "EverList", url: location.origin + "/l/" + encodeURIComponent(l.id) }).catch(() => {});
    });
    foot.appendChild(sh);
  }
  if (featured || n != null) {
    const flex = document.createElement("span"); flex.className = "flex"; foot.appendChild(flex);
    const cta = document.createElement("button"); cta.className = "cta"; cta.type = "button";
    cta.textContent = n != null ? (L("Book \u00b7 ") + n) : L("Ask AI to book");
    cta.addEventListener("click", (ev) => {
      ev.stopPropagation();
      openChat();
      if (n != null) {
        send("book " + n);
      } else {
        /* featured card: prefill with the listing id — the brain resolves ids,
           not titles; the user just adds their name and sends */
        input.value = "book " + (l.id || "") + " ";
        input.focus();
        autosize();
      }
    });
    foot.appendChild(cta);
  }
  card.appendChild(foot);
  return card;
}

/* Item 4 (owner fixes 2026-09-21): the FIRST screen is curated to happenings —
   dated events/classes/things that make sense as happenings. Mundane goods
   (dateless services, food items) stay reachable via search and chips. The
   rule is honest and mechanical: a real calendar date + an events-like
   vertical. No fake curation labels; the count line states the rule. */
const HAPPENING_VERTICALS = new Set(["events", "classes", "community", "workshops", "wellness"]);
function hasRealDate(l) {
  return /^\d{4}-\d{2}-\d{2}/.test(String(l.date || "").trim());
}
function isPast(l) {
  /* owner call 2026-09-23: archive everything past today — nothing with a
     past date shows as bookable/"live" anywhere in the UI. */
  const d = String(l.date || "").slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d)) return false;
  const now = new Date();
  const today = now.getFullYear() + "-" + String(now.getMonth() + 1).padStart(2, "0") + "-" + String(now.getDate()).padStart(2, "0");
  return d < today;
}

function isHappening(l) {
  const v = String(l.vertical || l.category || "").toLowerCase();
  return HAPPENING_VERTICALS.has(v) && hasRealDate(l) && !isPast(l);
}

function renderGrid() {
  resetBoardState();
  grid.innerHTML = "";
  if (BOARD) {
    BOARD.forEach((l, i) => grid.appendChild(makeCard(l, false, i + 1)));
    countEl.textContent = BOARD.length + (LANG === "de" ? (BOARD.length === 1 ? " Ergebnis" : " Ergebnisse") + " \u00b7 aus Ihrem Chat" : " result" + (BOARD.length === 1 ? "" : "s") + " \u00b7 from your chat");
  } else {
    /* Item 4: default (first-screen) board shows happenings only; search
       results (BOARD) always show everything the brain found. */
    const happening = ALL.filter(isHappening).filter((l) => !isPast(l));
    if (happening.length) {
      happening.forEach((l, i) => grid.appendChild(makeCard(l, i === 0)));
      countEl.textContent = happening.length + " " + L("upcoming happenings \u00b7 dated events & classes");
      emptyEl.textContent = "";
      emptyEl.hidden = true;
      grid.hidden = false;
      return;
    }
    /* honest empty state: the curated set is empty — say so, and say the
       rest is still reachable. Never pad with mundane goods. */
    countEl.textContent = L("0 upcoming happenings");
    emptyEl.textContent = (ALL.length
      ? L("No dated happenings on the board right now. Everything else that is listed stays reachable \u2014 just search in the chat below.")
      : L("Nothing here yet \u2014 be the first. Type \u201clist \u2026\u201d in the chat below, or tap \u201c+ list a thing\u201d."));
    emptyEl.hidden = false;
    grid.hidden = true;
    return;
  }
  const list = BOARD || ALL;
  emptyEl.hidden = list.length > 0;
  grid.hidden = list.length === 0;
}

/* ---------- W2 item 11: durable draft preview slot ---------- */
let DRAFT = null;          // current draft card dict (envelope-driven)

function draftSlotEl() {
  let slot = document.getElementById("draft-slot");
  if (!slot) {
    slot = document.createElement("div");
    slot.id = "draft-slot";
    slot.className = "draftslot";
    const label = document.createElement("div");
    label.className = "draftlabel";
    label.textContent = L("your listing \u00b7 preview");
    slot.appendChild(label);
    const holder = document.createElement("div");
    holder.className = "draftholder";
    slot.appendChild(holder);
    grid.parentNode.insertBefore(slot, grid);
  }
  return slot;
}

function renderDraft() {
  const slot = draftSlotEl();
  const holder = slot.querySelector(".draftholder");
  holder.innerHTML = "";
  if (!DRAFT) { slot.remove(); return; }
  holder.appendChild(makeCard(DRAFT, false, null));
  const note = document.createElement("div");
  note.className = "draftnote";
  note.textContent = L("confirm in chat to publish \u00b7 edit like 'price: 20' or 'make it free'");
  holder.appendChild(note);
  slot.hidden = false;
}

function setDraft(card) {
  const had = !!DRAFT;
  DRAFT = card || null;
  if (DRAFT) {
    window.DRAFT_LAST_TITLE = DRAFT.title || "";
    renderDraft();
    const slot = document.getElementById("draft-slot");
    if (slot && !had && !REDUCE()) slot.classList.add("draftin");
  }
}

function clearDraft() {
  const slot = document.getElementById("draft-slot");
  DRAFT = null;
  if (slot) {
    if (REDUCE()) { slot.remove(); return; }
    slot.classList.add("draftbye");
    setTimeout(() => { const s = document.getElementById("draft-slot"); if (s) s.remove(); }, 320);
  }
}

async function swapDraftToReal() {
  /* confirm success: the preview glides away; a fresh fetch shows the real
     published card on the board (one-shot spotlight on the new listing) */
  clearDraft();
  BOARD = null; SIG = "";
  await loadListings();
  renderGrid();
  const fresh = Array.from(grid.querySelectorAll("[data-listing]"))
    .find((c) => { try { return JSON.parse(c.dataset.listing).title === (DRAFT_LAST_TITLE || ""); } catch (e) { return false; } });
  if (fresh && !REDUCE()) {
    fresh.classList.add("spotlight");
    setTimeout(() => fresh.classList.remove("spotlight"), 1600);
  }
}

async function loadListings() {
  try {
    const r = await fetch("/api/listings?limit=48", { cache: "no-store" });
    const d = await r.json();
    ALL = d.listings || d.results || (Array.isArray(d) ? d : []);
    renderGrid();
  } catch (e) {
    countEl.textContent = L("hub offline");
    emptyEl.hidden = false;
  }
}

if (filters) filters.addEventListener("click", (e) => {
  const b = e.target.closest(".chip");
  if (!b) return;
  if (b.dataset.reset) {
    BOARD = null;
    SIG = "";
    grid.classList.remove("boardin");
    renderGrid();
    return;
  }
  if (b.dataset.q) { openChat(); send(b.dataset.q); }
});

/* ---------- board motion: everything slides, nothing fades ----------
   No card may ever appear or disappear during a reflow: every moving card
   is one rigid translate. Transform-only (compositor) — no width/height
   animation anywhere, so a reflow never touches layout per frame. */
/* Unified motion language (owner bundle 2026-09-25 #1): one decelerate
   curve everywhere; role-based durations — panel grow 380ms, card slides
   and close retreat 300ms. Cascade step (#3): 12ms per moved card. */
const EASE = "cubic-bezier(.2,.7,.2,1)";
const DUR_PANEL = 380, DUR_SLIDE = 300;
const CASCADE_MS = 12;
const REDUCE = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function slideBack(f, l, c, delay) {
  const dx = f.left - l.left, dy = f.top - l.top;
  if (Math.abs(dx) < 1 && Math.abs(dy) < 1) return false;
  if (REDUCE()) return false;
  c.animate(
    [{ transform: "translate(" + dx + "px," + dy + "px)" },
     { transform: "none" }],
    /* fill:backwards holds the start position through the cascade delay —
       without it the card would flash its final slot before sliding. */
    { duration: DUR_SLIDE, easing: EASE, delay: delay || 0, fill: "backwards" }
  );
  return true;
}

function cancelBoardAnimations() {
  /* FLIP hygiene (owner: "shifts them weirdly, some boxes stay alone in a
     row"): getBoundingClientRect() INCLUDES in-flight transform animations —
     a rapid panel switch measures mid-slide positions, so cards animate to
     wrong rows and only snap back when the old transforms expire. Cancel
     every animation targeting a grid child first: measurements then read
     true layout positions, and one clean slide follows. */
  if (!document.getAnimations) return;
  document.getAnimations().forEach((a) => {
    const el = a.effect && a.effect.target;
    if (el && grid.contains(el)) a.cancel();
  });
}

function animateBoardChange(mutate, dir) {
  cancelBoardAnimations();
  const before = new Map();
  Array.from(grid.children).forEach((c) => before.set(c, c.getBoundingClientRect()));
  mutate();
  /* Cascading slides (#3): moved cards animate in a wave that FOLLOWS the
     motion — top-first when rows slide down (open), bottom-first when they
     slide up (close). 12ms per card; unmoved cards skip a step. */
  const moved = [];
  Array.from(grid.children).forEach((c) => {
    const f = before.get(c);
    if (!f) return;                 // inserted node: panel animates itself
    if (f.width < 1 || f.height < 1) return;   /* newly revealed (one-object model): appears in place — never slides in from the top-left corner */
    const now = c.getBoundingClientRect();
    if (now.width < 1 || now.height < 1) return;  /* just hidden: its panel takes over the row */
    if (Math.abs(f.left - now.left) >= 1 || Math.abs(f.top - now.top) >= 1) moved.push([f, now, c]);
  });
  moved.sort((a, b) => (dir === -1 ? b[1].top - a[1].top : a[1].top - b[1].top));
  moved.forEach((m, i) => slideBack(m[0], m[1], m[2], i * CASCADE_MS));
}

/* ---------- detail panel: one click = the full /l/{id} detail, row ABOVE ----------
   Owner call (2026-09-17, v3): in-grid full-row panel like the previous
   implementation — but it opens in a row ABOVE the clicked card, not below.
   Rows above stay put; the clicked row (and everything below it) slides
   down; the clicked slot becomes a dashed ghost hole. The panel grows
   straight out of the clicked card into its slot above. On close it fades
   FAST (half gone by 40% of the run) BEFORE shrinking back into the card —
   the end-of-shrink flash is structurally impossible. Close paths: x
   button, Escape, click on the hole, click on empty panel background,
   browser back. Switching listings swaps the panel inside ONE FLIP step
   and replaces the history entry so the back stack stays clean. /l/{id}
   stays a real server page for crawlers, no-JS visitors and deep links —
   in-app we never navigate. */
let openDetailCard = null;   // card currently holed
let detailPanel = null;      // panel element (in flow while open)

function cardListing(card) {
  try { return JSON.parse(card.dataset.listing || "null"); } catch (e) { return null; }
}

function killStrayPanels() {
  /* Bulletproof hygiene: no frozen/animating panel may ever survive a state
     change — it would float over the board and swallow clicks. */
  document.querySelectorAll(".detail-panel").forEach((p) => p.remove());
  detailPanel = null;
}

function resetBoardState() {
  /* Board re-rendered (search/filter): any open detail is torn down silently
     and the URL returns home. Called by renderGrid BEFORE innerHTML clears. */
  openDetailCard = null;
  killStrayPanels();
  if (history.state && history.state.detail) history.replaceState(null, "", "/");
}

function rowsOfGrid() {
  /* 40px row band (owner repro 2026-09-25: "click the second item in a row
     and the first item stays on top / boxes alone in a row"). The old 2px
     tolerance split visual rows whenever same-row offsetTops drifted apart
     (fractional zoom / DPI / grid subpixel rounding in the owner's browser) —
     the panel then landed mid-row and orphaned cards. Real grid rows sit
     200px+ apart; same-row drift is a few px. 40px absorbs any drift and can
     never merge two real rows. Hidden cards (display:none while their panel
     is open) report offsetTop 0 — skipped via offsetParent. */
  const rows = [];
  let cur = null, top = -1e9;
  Array.from(grid.children).forEach((el) => {
    if (el.classList && el.classList.contains("card") && el.offsetParent) {
      const t = el.offsetTop;
      if (!cur || Math.abs(t - top) > 40) { cur = []; rows.push(cur); top = t; }
      cur.push(el);
    }
  });
  return rows;
}

function boardData() {
  return (typeof BOARD !== "undefined" && BOARD ? BOARD : (typeof ALL !== "undefined" ? ALL : []));
}

function fmtTime(t) {
  const m = /^\d{1,2}:\d{2}$/.exec(String(t || ""));
  return m ? String(t) : "";
}

function fmtDateLong(d) {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(String(d || ""));
  if (!m) return String(d || L("any date"));
  return (+m[3]) + " " + (MONTHS[(+m[2]) - 1] || m[2]) + " " + m[1];
}

/* Content parity with the SSR /l/{id} page (pages.py listing_html): same
   data, same classes (.lmeta .chip .esc.note .lcta .lnote), so the shared
   stylesheet renders both identically. CSP-safe: textContent everywhere. */
function buildDetailPanel(l) {
  const d = document.createElement("article");
  d.className = "detail-panel ldetail";

  const close = document.createElement("button");
  close.className = "dclose"; close.type = "button"; close.setAttribute("aria-label", "close");
  close.textContent = "\u00d7";
  close.addEventListener("click", (ev) => { ev.stopPropagation(); closeDetail(false); });
  d.appendChild(close);

  const price = priceOf(l);
  const metaBits = [l.vertical || l.category || "", [fmtDateLong(l.date), fmtTime(l.time)].filter(Boolean).join(" · "), price.txt, l.location || ""].filter(Boolean);
  const meta = document.createElement("div"); meta.className = "lmeta"; meta.textContent = metaBits.join(" \u00b7 "); d.appendChild(meta);

  const h2 = document.createElement("h2"); h2.className = "dtitle"; h2.textContent = l.title || L("Untitled"); d.appendChild(h2);

  const cap = parseInt(l.capacity, 10);
  if (!isNaN(cap) && cap > 0) {
    const reg = parseInt(l.registered != null ? l.registered : l.booked, 10) || 0;
    const left = Math.max(0, cap - reg);
    const spots = document.createElement("div"); spots.className = "lmeta";
    spots.textContent = left + (LANG === "de" ? " von " : " of ") + cap + (LANG === "de" ? " frei" : " spots left");
    d.appendChild(spots);
  }

  if (l.description) { const de = document.createElement("p"); de.className = "ldesc"; de.textContent = String(l.description); d.appendChild(de); }

  const tags = l.tags || [];
  if (tags.length) {
    const tw = document.createElement("div");
    tags.slice(0, 8).forEach((t) => { const c = document.createElement("span"); c.className = "chip stat"; c.textContent = t; tw.appendChild(c); });
    d.appendChild(tw);
  }

  const rateBits = [];
  if ((l.rating_count | 0) > 0) {
    let avg = (l.rating_wtot || 0) > 0 ? (l.rating_wsum || 0) / l.rating_wtot
            : (l.rating_avg != null ? l.rating_avg : (l.rating_sum || 0) / l.rating_count);
    rateBits.push("\u2605 " + fmtNum(Math.round(avg * 10) / 10) + L("/5 paid reviews (") + l.rating_count + ")");
  }
  if ((l.free_rating_count | 0) > 0) {
    rateBits.push(L("free-class ") + fmtNum(Math.round((l.free_rating_sum || 0) / l.free_rating_count * 10) / 10) + "/5 (" + l.free_rating_count + ")");
  }
  if (rateBits.length) { const rl = document.createElement("div"); rl.className = "lmeta rline"; rl.textContent = rateBits.join(" \u00b7 "); d.appendChild(rl); }

  const pt = l.payment_terms || {};
  if ((pt.rail || "") === "escrow" && price.esc) {
    const note = document.createElement("div"); note.className = "esc note";
    note.textContent = "\u272a " + L("Money is held safely until it happens") + " \u00b7 " + L("free cancellation within ") + (pt.refund_window_hours != null ? pt.refund_window_hours : 24) + L("h.");
    d.appendChild(note);
  }
  /* owner call 2026-09-23: the test/demo flag is small print ONLY — the
     listing itself must look normal. Keyed off the seed source field. */
  if (String(l.source || "").startsWith("demo-seed") || String(l.owner || "").startsWith("demo-test")) {
    const tn = document.createElement("div"); tn.className = "lsmall";
    tn.textContent = L("test listing");
    d.appendChild(tn);
  }

  const cta = document.createElement("div"); cta.className = "lcta";
  const book = document.createElement("button"); book.className = "btn"; book.type = "button";
  book.textContent = "\ud83d\udcac " + L("Ask EverList to book this");
  book.addEventListener("click", (ev) => {
    ev.stopPropagation();
    closeDetail(false);   /* clear the panel before handing over to the chat */
    openChat();
    input.value = "book " + (l.id || "") + " ";
    input.focus(); autosize();
  });
  cta.appendChild(book);
  if (l.id) {
    const ics = document.createElement("a"); ics.className = "chip";
    ics.href = "/l/" + encodeURIComponent(l.id) + ".ics";
    ics.target = "_blank"; ics.rel = "noopener";
    ics.textContent = "\ud83d\udcc5 " + L("Add to calendar");
    ics.addEventListener("click", (ev) => ev.stopPropagation());
    cta.appendChild(ics);
  }
  d.appendChild(cta);

  if (l.url) {
    /* owner call 2026-09-23: organizer link is a designed pill showing the
       domain, never a raw URL line */
    let host = "";
    try { host = new URL(l.url).hostname.replace(/^www\./, ""); } catch (e) { host = String(l.url).slice(0, 40); }
    const un = document.createElement("div"); un.className = "orglink";
    const ua = document.createElement("a"); ua.className = "orglink-btn";
    ua.href = l.url; ua.rel = "noopener nofollow"; ua.target = "_blank";
    ua.textContent = "\u2197 " + host;
    ua.title = l.url;
    ua.addEventListener("click", (ev) => ev.stopPropagation());
    un.appendChild(ua);
    d.appendChild(un);
  }

  /* Same board data the SSR page uses for "More from this organizer":
     switches straight to that listing's panel. */
  const own = String(l.owner || "");
  if (own && l.id) {
    const sibs = boardData()
      .filter((x) => String(x.id) !== String(l.id) && String(x.owner || "") === own).slice(0, 3);
    if (sibs.length) {
      const sec = document.createElement("section"); sec.className = "drel";
      const sh = document.createElement("div"); sh.className = "lmeta"; sh.textContent = L("More from this organizer"); sec.appendChild(sh);
      const row = document.createElement("div"); row.className = "drelrow";
      sibs.forEach((x) => {
        const b = document.createElement("button"); b.className = "drelitem"; b.type = "button";
        b.textContent = x.title || L("Untitled");
        b.addEventListener("click", (ev) => {
          ev.stopPropagation();
          const target = Array.from(grid.querySelectorAll(".card")).find((c) => {
            const xl = cardListing(c); return xl && String(xl.id) === String(x.id);
          });
          if (target) openDetail(target);
        });
        row.appendChild(b);
      });
      sec.appendChild(row);
      d.appendChild(sec);
    }
  }
  return d;
}

function openDetail(card) {
  if (openDetailCard === card) { closeDetail(false); return; }
  const l = cardListing(card);
  if (!l) return;
  // direct swap: old panel (if any) is replaced inside the same FLIP step,
  // so the board moves once — never collapse-then-reexpand
  const prevCard = openDetailCard;
  const prevPanel = detailPanel;
  // insert the panel in a row ABOVE the clicked card (owner call v3):
  // rows above stay, the clicked row and everything below slide down.
  // Row geometry is measured INSIDE animateBoardChange on the clean layout.
  // capture the card's rect BEFORE the board mutates (owner 2026-09-25:
  // "when they grow it shifts them weirdly"). Measuring after insertion
  // returned the card's POST-SLIDE layout rect — the panel then grew out
  // of the spot the card was sliding DOWN INTO, so the two crossed paths
  // mid-flight and the grow read as a weird shift. The click-time rect is
  // where the card visually IS: the panel hands off from there while the
  // card slides away — one coherent motion, chat-morph language.
  const hole = card.getBoundingClientRect();
  // #4 instant click ack: ring pulse the SAME frame the click lands — the
  // board answers before the grow starts. Removed after the run; harmless
  // if a re-render beats the timer.
  card.classList.remove("pulse");
  void card.offsetWidth;              /* restart the animation on rapid re-clicks */
  card.classList.add("pulse");
  setTimeout(() => card.classList.remove("pulse"), 320);
  animateBoardChange(() => {
    /* ONE-object model (owner 2026-09-25: "one details box and one small box
       of the same article … one should just grow and shrink"). The clicked
       card IS the detail: it leaves the grid and the panel takes over its
       whole row. No dimmed duplicate beside the panel anymore. */
    if (prevCard) prevCard.style.display = "";   /* previous card returns … */
    if (prevPanel) prevPanel.remove();           /* … as its panel swaps */
    // rows are measured on the CLEAN board — the old panel is gone and the
    // previous card is restored before this runs (owner repro 2026-09-25:
    // "first item stays on top / boxes alone in a row"). Measuring clean
    // means even a board left mid-row by an older click HEALS on the next
    // one: the panel always lands on a true row boundary.
    const rows = rowsOfGrid();
    let rowIdx = -1;
    for (let i = 0; i < rows.length; i++) {
      if (rows[i].indexOf(card) !== -1) { rowIdx = i; break; }
    }
    card.style.display = "none";                 /* the card becomes the panel */
    detailPanel = buildDetailPanel(l);
    if (rowIdx <= 0) grid.insertBefore(detailPanel, grid.firstChild);
    else rows[rowIdx][0].before(detailPanel);    /* panel takes the whole row */
  });
  // transform-only morph (GPU, zero reflow): grow out of the clicked card
  // into the slot directly above it. UNIFORM scale (owner 2026-09-25: the
  // x/y stretch read as a rubber band) — the panel keeps its aspect and
  // emerges from the card's center, like the chat morph language. The rect
  // is the click-time capture above — where the card visually WAS — so the
  // grow starts on the card the user actually clicked, not its post-slide
  // resting slot.
  const pr = detailPanel.getBoundingClientRect();
  /* Center-scroll (owner 2026-09-25, PC) BEFORE the grow animation applies
     its transform: scrollIntoView centered the transformed START rect (the
     panel's from-position near the card) and landed ~70px off true center.
     pr is the pre-animation layout rect — document-coords math here is
     pixel-exact. Instant, so no double motion with the grow (transforms
     never move layout). */
  {
    const targetY = pr.top + (window.scrollY || 0) + pr.height / 2 - window.innerHeight / 2;
    window.scrollTo(0, Math.max(0, targetY));
  }
  if (!REDUCE() && pr.width > 0 && pr.height > 0) {
    const s = Math.max(0.25, Math.min(hole.width / pr.width, 1));
    const cx = hole.left + hole.width / 2 - (pr.left + pr.width / 2);
    const cy = hole.top + hole.height / 2 - (pr.top + pr.height / 2);
    detailPanel.style.transformOrigin = "center";
    detailPanel.animate(
      [{ transform: "translate(" + cx + "px," + cy + "px) scale(" + s + ")", opacity: 0.55 },
       { transform: "none", opacity: 1 }],
      { duration: DUR_PANEL, easing: EASE }
    );
    /* #2 content stagger: after the frame lands, content ARRIVES — meta,
       title, desc, CTAs fade + rise 6px with a 35ms step. Starts partway
       through the grow (content rises while the frame still glides) so the
       panel never reads as an empty box. Panel children only — the close
       button is absolutely positioned and would visibly drift. */
    Array.from(detailPanel.children).filter((ch) => !ch.classList.contains("dclose")).forEach((ch, i) => {
      ch.animate(
        [{ opacity: 0, transform: "translateY(6px)" }, { opacity: 1, transform: "none" }],
        { duration: 260, easing: EASE, delay: 120 + i * 35, fill: "backwards" }
      );
    });
  }
  openDetailCard = card;
  // push once per detail session; a switch replaces the entry (clean stack)
  const url = "/l/" + encodeURIComponent(l.id);
  if (history.state && history.state.detail) history.replaceState({ detail: l.id }, "", url);
  else if (location.pathname !== url) history.pushState({ detail: l.id }, "", url);
  // (center-scroll happens above, before the grow transform exists — the
  // old scrollIntoView here was removed: it centered the panel's TRANSFORMED
  // mid-animation rect instead of its layout slot and landed ~70px off.)
}

function closeDetail(viaPop) {
  if (!openDetailCard || !detailPanel) return;
  const card = openDetailCard, panel = detailPanel;
  openDetailCard = null; detailPanel = null;
  cancelBoardAnimations();   /* FLIP hygiene: before-positions must be true layout, not mid-slide transforms */
  // capture BEFORE-positions while the panel still holds the row open
  const before = new Map();
  Array.from(grid.children).forEach((c) => { if (c !== panel) before.set(c, c.getBoundingClientRect()); });
  // freeze the panel OUT of the grid — in DOCUMENT coordinates (absolute,
  // not fixed) so page scroll during the retreat keeps it glued to the hole
  const pr = panel.getBoundingClientRect();
  const sx = window.scrollX || 0, sy = window.scrollY || 0;
  panel.style.position = "absolute";
  panel.style.left = (pr.left + sx) + "px";
  panel.style.top = (pr.top + sy) + "px";
  panel.style.width = pr.width + "px";
  panel.style.height = pr.height + "px";
  panel.style.boxSizing = "border-box";   /* rect.width == style.width exactly */
  panel.style.margin = "0";
  panel.style.zIndex = "40";
  panel.style.pointerEvents = "none";
  document.body.appendChild(panel);
  // the card RETURNS — it was display:none while its panel was open. The
  // panel shrinks back into the card's revealed rect: one object that grew
  // and now shrinks (owner 2026-09-25), no dimmed duplicate anywhere.
  card.style.display = "";
  // hole FINAL resting rect — measured BEFORE any slide transform runs.
  // getBoundingClientRect includes transforms: measuring after the slides
  // start would target the animated START position and mis-dock by a row.
  const hole = card.getBoundingClientRect();
  // board closes NOW and every compensating slide starts in THIS task, so
  // the first painted frame is already the sliding state (no 1-frame jump)
  /* #3 mirrored cascade: on close the rows slide UP, so the wave travels
     bottom-first — the mirror of the open ripple. Same 12ms step. */
  const moved = [];
  Array.from(grid.children).forEach((c) => {
    const f = before.get(c);
    if (!f) return;
    const now = c.getBoundingClientRect();
    if (Math.abs(f.left - now.left) >= 1 || Math.abs(f.top - now.top) >= 1) moved.push([f, now, c]);
  });
  moved.sort((a, b) => b[1].top - a[1].top);
  moved.forEach((m, i) => slideBack(m[0], m[1], m[2], i * CASCADE_MS));
  if (REDUCE()) {
    panel.remove();
  } else {
    // fade FAST first (half gone by 40% of the run), then shrink into the
    // hole's FINAL position — same 340ms/easing as the board slide, so the
    // panel and the cards land together, pixel-exact
    const frames = [
      { transform: "none", opacity: 1, offset: 0 },
      { transform: "none", opacity: 0.5, offset: 0.4 }
    ];
    if (pr.width > 0 && hole.width > 0) {
      panel.style.transformOrigin = "top left";
      frames.push({ transform: "translate(" + (hole.left - pr.left) + "px," + (hole.top - pr.top) + "px) scale(" + (hole.width / pr.width) + "," + (hole.height / pr.height) + ")", opacity: 0 });
    } else {
      frames.push({ transform: "translateY(8px) scale(.97)", opacity: 0 });
    }
    /* fill BOTH pins the final frame (opacity 0) after the animation ends.
       WITHOUT it, WAAPI reverts the panel to its natural style (opacity 1,
       full size) the instant the animation finishes — a 1-2 frame full-panel
       flash before the removal timer fires. That was the "briefly opens up
       again" glitch at the very end of the close. */
    const retreat = panel.animate(frames, { duration: DUR_SLIDE, easing: EASE, fill: "both" });
    retreat.finished.then(() => panel.remove()).catch(() => {});
  }
  // unconditional cleanup: the floating panel can never outlive its exit.
  // Window covers the mirrored cascade (12ms x moved cards + DUR_SLIDE).
  setTimeout(() => panel.remove(), 700);
  if (!viaPop && history.state && history.state.detail) history.back();
  // NOTE: no scrollIntoView here — scrolling during the retreat moves the
  // hole relative to the frozen panel and was a prime glitch source
}

window.addEventListener("popstate", () => {
  if (openDetailCard && !(history.state && history.state.detail)) closeDetail(true);
  else if (!openDetailCard && history.state && history.state.detail) {
    // forward button: re-open the panel for the listing in the URL
    const id = history.state.detail;
    const card = Array.from(grid.querySelectorAll(".card")).find((c) => {
      const l = cardListing(c); return l && String(l.id) === String(id);
    });
    if (card) openDetail(card);
  }
});

/* One handler, ordered: chat CTA first, then detail-close gestures, then
   card click = FULL detail. The details link is folded in here — a second
   listener would open+close in the same click dispatch (net: nothing).
   Modifier-clicked links keep native /l/ navigation. */
grid.addEventListener("click", (e) => {
  if (e.target.closest(".cta")) return;             /* CTA routes to chat itself */
  const dl = e.target.closest(".dlink");
  if (dl && !(e.metaKey || e.ctrlKey || e.shiftKey || e.altKey)) e.preventDefault(); /* panel, not navigation */
  if (e.target.closest(".detail-panel")) {
    if (e.target === detailPanel) closeDetail(false); /* bg/padding click = close; content stays interactive */
    return;
  }
  const card = e.target.closest(".card");
  if (!card) { if (openDetailCard) closeDetail(false); return; }
  if (openDetailCard === card) { closeDetail(false); return; }  /* hole click = close */
  openDetail(card);
});
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && openDetailCard) closeDetail(false); });

/* ---------- W3: browser signup (PoW + keygen in-page; seed shown ONCE) ---------- */
/* The keypair is generated IN THE BROWSER (vendored tweetnacl): the seed is
   displayed once and never leaves this tab — the hub stores only the pubkey.
   Crypto contract cross-checked against the hub's Python ed25519. */
const _hex = (buf) => Array.from(new Uint8Array(buf)).map((b) => b.toString(16).padStart(2, "0")).join("");

async function solvePoW(challenge, difficulty, onTick) {
  const enc = new TextEncoder();
  const t0 = Date.now();
  for (let nonce = 0; nonce <= 1e15; nonce++) {
    const digest = await crypto.subtle.digest("SHA-256", enc.encode(challenge + nonce));
    const b = new Uint8Array(digest);
    let bits = 0;
    for (let i = 0; i < 32; i++) {
      if (b[i] === 0) { bits += 8; continue; }
      bits += Math.clz32(b[i]) - 24;
      break;
    }
    if (bits >= difficulty) return nonce;
    if (onTick && (nonce & 16383) === 0 && Date.now() - t0 > 1500) onTick(nonce);
  }
  throw new Error("proof-of-work failed");
}

async function browserSignupFlow(name, statusEl) {
  const ch = await fetch("/api/signup-challenge").then((r) => r.json());
  if (!ch.challenge) throw new Error(ch.error || "challenge unavailable");
  statusEl.textContent = L("solving proof-of-work\u2026");
  const nonce = await solvePoW(ch.challenge, ch.difficulty, (n) => {
    statusEl.textContent = L("solving proof-of-work\u2026") + " " + n.toLocaleString();
  });
  statusEl.textContent = L("generating your key in-browser\u2026");
  const seed = crypto.getRandomValues(new Uint8Array(32));
  const kp = nacl.sign.keyPair.fromSeed(seed);
  const pubHex = _hex(kp.publicKey);
  statusEl.textContent = L("creating account\u2026");
  const res = await fetch("/api/signup", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ agent: name, pubkey: pubHex, pow: { challenge: ch.challenge, nonce: nonce }, lang: LANG }),
  });
  const data = await res.json().catch(() => ({}));
  if (res.status !== 201) throw new Error(data.error || "signup rejected");
  statusEl.textContent = L("signing you in\u2026");
  let logged = false;
  try {
    const lch = await fetch("/api/login-challenge?pubkey=" + pubHex).then((r) => r.json());
    if (lch.challenge) {
      const msg = new TextEncoder().encode("everlist-login:" + lch.challenge);
      const sig = nacl.sign.detached(msg, kp.secretKey);
      const lres = await fetch("/api/login-pubkey", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ agent: name, pubkey: pubHex, sig: _hex(sig) }),
      });
      logged = !!((await lres.json().catch(() => ({}))).ok);
    }
  } catch (e2) { /* account created; seed login still works */ }
  return { seedHex: _hex(seed), logged: logged };
}

const signupArea = document.getElementById("signup-area");
const signupForm = document.getElementById("signup");
const signupBtn = document.getElementById("s-go");
const signupStatus = document.getElementById("s-status");

function toggleSignup(show) { if (signupArea) signupArea.hidden = !show; }

if (signupForm) signupForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  if (signupBtn.disabled) return;
  const name = document.getElementById("s-name").value.trim();
  if (!name) { signupStatus.textContent = L("a name is required"); return; }
  signupBtn.disabled = true;
  signupStatus.textContent = L("starting\u2026");
  try {
    const out = await browserSignupFlow(name, signupStatus);
    signupStatus.textContent = "";
    signupForm.textContent = "";
    const warn = el("p", null, "\ud83d\udd11 " + L("Your account SEED \u2014 shown ONCE, store it like a crypto seed phrase. It is your only way to log in elsewhere:"));
    const seedBox = document.createElement("pre");
    seedBox.className = "seedbox";
    seedBox.textContent = out.seedHex;
    const ok = el("button", "cta", L("I've saved it \u2014 continue"));
    ok.type = "button";
    ok.addEventListener("click", () => { toggleSignup(false); loadDashboard(); });
    signupForm.appendChild(warn);
    signupForm.appendChild(seedBox);
    signupForm.appendChild(ok);
    if (out.logged) loadDashboard();
    else addMsg("err", L("account created \u2014 auto sign-in failed; log in with the seed above."));
  } catch (err) {
    signupStatus.textContent = "⚠️ " + (err && err.message ? L(err.message) : L("signup failed"));
  }
  signupBtn.disabled = false;
});

/* ---------- W1 dashboard: bookings + orders (tokens stay server-side) ---------- */
const browseSec = document.getElementById("browse");
const dashSec = document.getElementById("dash");
const navBrowse = document.getElementById("nav-browse");
const navDash = document.getElementById("nav-dash");
const dashAcct = document.getElementById("dash-acct");
const dashLogin = document.getElementById("dash-login");
const myBookings = document.getElementById("mybookings");
const myOrders = document.getElementById("myorders");
const dashRefresh = document.getElementById("dash-refresh");
const dashLogout = document.getElementById("dash-logout");

const ESCROW_LABEL = { HELD: "money held safely", WAIVED: "free (no payment)", RELEASED: "released to owner", REFUNDED: "refunded", DIRECT: "instant — settled" };

function el(tag, cls, text) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text != null) n.textContent = text;
  return n;
}

function showView(name) {
  // normalize legacy boolean callers (true = dashboard, false = browse)
  // — the Bookings button and brain nav both used booleans.
  if (name === true) name = "dash";
  else if (name === false) name = "browse";
  const dash = name === "dash", post = name === "post";
  browseSec.hidden = dash || post;
  const postSec = document.getElementById("post");
  if (postSec) postSec.hidden = !post;
  dashSec.hidden = !dash;
  navBrowse.classList.toggle("on", !dash);
  navDash.classList.toggle("on", dash);
  /* U5: mobile tab bar active states */
  const tb = document.getElementById("tabbar");
  if (tb) {
    document.getElementById("tab-browse").classList.toggle("on", !dash);
    document.getElementById("tab-dash").classList.toggle("on", dash);
  }
  if (dash) loadDashboard();
}
/* U5: mobile tab bar wiring (Browse/Bookings/List/Chat) */
if (document.getElementById("tabbar")) {
  document.getElementById("tab-browse").addEventListener("click", () => showView(false));
  document.getElementById("tab-dash").addEventListener("click", () => showView(true));
  document.getElementById("tab-list").addEventListener("click", () => startPost());
  document.getElementById("tab-chat").addEventListener("click", () => { openChat(); input.focus(); });
}
if (navBrowse) navBrowse.addEventListener("click", (e) => { e.preventDefault(); showView(false); });
if (navDash) navDash.addEventListener("click", (e) => { e.preventDefault(); showView(true); });

function escBadge(state) {
  return el("span", "escbadge e-" + String(state || "x").toLowerCase(), L(ESCROW_LABEL[state] || String(state || "?")));
}

/* W2 item 12: compact 4-step escrow strip per booking (asked → held →
   happened → released/refunded). Real states only; WAIVED/DIRECT honestly
   show 'no payment needed' with no fake timeline. DOM-built, CSP-safe. */
function escTimeline(state, amount) {
  const tl = el("div", "btl btl-mini");
  tl.setAttribute("aria-label", L("payment timeline"));
  const st = String(state || "HELD").toUpperCase();
  if (st === "WAIVED" || st === "DIRECT" || !(parseFloat(amount) > 0)) {
    tl.appendChild(el("span", "btl-step now", L("no payment needed")));
    return tl;
  }
  let steps, nowIdx;
  if (st === "REFUNDED") {
    steps = [L("asked"), L("held"), L("refunded")];
    nowIdx = 2;
  } else if (st === "RELEASED") {
    steps = [L("asked"), L("held"), L("happened"), L("released")];
    nowIdx = 3;
  } else if (st === "HELD") {
    steps = [L("asked"), L("held"), L("happened"), L("released")];
    nowIdx = 1;
  } else {
    steps = [L(String(st).toLowerCase())];
    nowIdx = 0;
  }
  steps.forEach((s, i) => {
    const cls = "btl-step" + (i === nowIdx ? " now" : (i < nowIdx ? " done" : ""));
    tl.appendChild(el("span", cls, s));
  });
  return tl;
}

function when(ts) {
  const d = new Date((ts || 0) * 1000);
  return isNaN(d.getTime()) ? "" : d.toLocaleDateString(LANG === "de" ? "de-DE" : undefined, { day: "numeric", month: "short" });
}

function bookingCard(b) {
  const card = el("div", "card dashcard");
  const r1 = el("div", "r1");
  r1.appendChild(el("span", "vtag", String(b.vertical || "booking").toUpperCase()));
  r1.appendChild(escBadge(b.escrow));
  r1.appendChild(el("span", "flex"));
  r1.appendChild(el("span", "meta", when(b.created)));
  card.appendChild(r1);
  card.appendChild(el("h3", null, b.title || b.listing_id));
  card.appendChild(escTimeline(b.escrow, b.amount));
  const foot = el("div", "foot");
  foot.appendChild(el("span", "price", b.amount ? fmtEUR(b.amount) : L("Free")));
  const idLink = el("a", "esc", "#" + b.id);
  idLink.href = "/booking/" + encodeURIComponent(b.id);
  foot.appendChild(idLink);
  if (b.can_cancel) {
    foot.appendChild(el("span", "flex"));
    const btn = el("button", "cta danger", L("Cancel & refund"));
    btn.type = "button";
    btn.addEventListener("click", () => act("/api/cancel", b.id));
    foot.appendChild(btn);
  }
  card.appendChild(foot);
  return card;
}

function orderCard(o) {
  const card = el("div", "card dashcard");
  const r1 = el("div", "r1");
  r1.appendChild(el("span", "vtag", LANG === "de" ? "BESTELLUNG" : "ORDER"));
  r1.appendChild(escBadge(o.escrow));
  r1.appendChild(el("span", "flex"));
  r1.appendChild(el("span", "meta", when(o.created)));
  card.appendChild(r1);
  card.appendChild(el("h3", null, o.title || o.listing_id));
  card.appendChild(escTimeline(o.escrow, o.amount));
  const foot = el("div", "foot");
  foot.appendChild(el("span", "price", o.amount ? fmtEUR(o.amount) : L("Free")));
  const idLink = el("a", "esc", "#" + o.id);
  idLink.href = "/booking/" + encodeURIComponent(o.id);
  foot.appendChild(idLink);
  if (o.can_confirm) {
    foot.appendChild(el("span", "flex"));
    const btn = el("button", "cta", L("Confirm & release"));
    btn.type = "button";
    btn.addEventListener("click", () => act("/api/confirm", o.id));
    foot.appendChild(btn);
  }
  card.appendChild(foot);
  return card;
}

async function act(url, id) {
  openChat();
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ booking_id: id }),
    });
    const data = await res.json().catch(() => ({}));
    if (data.ok) {
      addMsg("agent", "\u2705 " + L("Booking") + " " + id + " \u2014 " + L("payment status is now ") + (data.escrow || "updated")
        + (data.owner_received != null ? (". " + L("Owner receives ") + fmtEUR(data.owner_received)) : "."));
    } else {
      addMsg("err", "\u26a0\ufe0f " + (data.error ? L(data.error) : L("action failed")));
    }
  } catch (e) {
    addMsg("err", L("Hmm, the connection hiccuped \u2014 give it another go. \ud83d\ude4f"));
  }
  loadDashboard();
}

function renderLogin() {
  dashLogin.innerHTML = "";
  const p = el("p", null, L("Log in with your account seed and your bookings + orders appear here. No seed yet? "));
  const su = el("a", null, L("Create an account right here"));
  su.href = "#";
  su.addEventListener("click", (e) => { e.preventDefault(); toggleSignup(true); });
  p.appendChild(su);
  p.appendChild(document.createTextNode(L(" \u2014 your key is generated in your browser and the seed is shown once.")));
  const form = el("form", "loginrow");
  form.setAttribute("autocomplete", "off");
  const inp = el("input", "loginseed");
  inp.type = "password"; /* masked; the seed is never displayed or echoed */
  inp.placeholder = L("paste your account seed (shown once at signup)");
  inp.maxLength = 80;
  const btn = el("button", "cta", L("Log in"));
  btn.type = "submit";
  form.appendChild(inp);
  form.appendChild(btn);
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const seed = inp.value.trim();
    if (!seed || btn.disabled) return;
    btn.disabled = true;
    try {
      const res = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ seed }),
      });
      const data = await res.json().catch(() => ({}));
      if (data.ok) {
        inp.value = "";
        loadDashboard();
      } else {
        addMsg("err", "\u26a0\ufe0f " + (data.error ? L(data.error) : L("login failed")));
      }
    } catch (e2) {
      addMsg("err", L("Hmm, the connection hiccuped \u2014 give it another go. \ud83d\ude4f"));
    }
    btn.disabled = false;
  });
  dashLogin.appendChild(p);
  dashLogin.appendChild(form);
}

/* ---------- W3: my listings (dashboard manage) ---------- */
async function loadMyListings() {
  const box = document.getElementById("my-listings");
  if (!box) return;
  box.textContent = "";
  let data;
  try {
    const r = await fetch("/api/my-listings", { cache: "no-store" });
    data = await r.json();
  } catch (e) { return; }
  if (!data.listings || !data.listings.length) {
    box.appendChild(el("p", "empty", L("No listings yet \u2014 type 'list Title | category | date | price | City' in the chat to create one.")));
    return;
  }
  data.listings.forEach((l) => {
    const row = el("div", "myrow");
    row.appendChild(el("span", "t", l.title || l.id));
    row.appendChild(el("span", "m", (l.id || "") + " · " + priceOf(l).txt + (l.date ? " · " + l.date : "")));
    row.appendChild(el("span", "m", l.available === false ? L("archived") : L("live")));
    row.appendChild(el("span", "grow"));
    const det = document.createElement("a"); det.className = "linkbtn"; det.href = "/l/" + encodeURIComponent(l.id); det.target = "_blank"; det.rel = "noopener"; det.textContent = L("details");
    row.appendChild(det);
    const arc = document.createElement("button"); arc.className = "linkbtn"; arc.type = "button";
    arc.textContent = l.available === false ? L("unarchive") : L("archive");
    arc.addEventListener("click", () => { openChat(); send((l.available === false ? "unarchive " : "archive ") + l.id); setTimeout(loadMyListings, 1500); });
    row.appendChild(arc);
    const ed = document.createElement("button"); ed.className = "linkbtn"; ed.type = "button"; ed.textContent = L("edit");
    ed.addEventListener("click", () => startPost({ id: l.id, title: l.title }));
    row.appendChild(ed);
    box.appendChild(row);
  });
}

async function loadDashboard() {
  let data;
  try {
    const r = await fetch("/api/dashboard", { cache: "no-store" });
    data = await r.json();
  } catch (e) {
    dashAcct.textContent = L("offline");
    return;
  }
  myBookings.innerHTML = "";
  myOrders.innerHTML = "";
  const acct = data.account;
  dashLogout.hidden = !acct;
  if (!acct || data.expired) {
    dashAcct.textContent = "";
    if (!dashLogin.childNodes.length) renderLogin();
    dashLogin.hidden = false;
    myBookings.appendChild(el("p", "empty", L("Log in to see your bookings.")));
    myOrders.appendChild(el("p", "empty", L("Orders for your listings appear here.")));
    return;
  }
  dashLogin.hidden = true;
  dashAcct.textContent = acct.account_id + (acct.verified ? L(" \u00b7 human-verified") : "");
  if (!data.bookings.length) myBookings.appendChild(el("p", "empty", L("No bookings yet \u2014 search in the chat, then say \u201cbook 1\u201d.")));
  data.bookings.forEach((b) => myBookings.appendChild(bookingCard(b)));
  if (!data.orders.length) myOrders.appendChild(el("p", "empty", L("No orders yet \u2014 orders for your listings appear here.")));
  data.orders.forEach((o) => myOrders.appendChild(orderCard(o)));
  loadMyListings();
}

if (dashRefresh) dashRefresh.addEventListener("click", loadDashboard);
if (dashLogout) dashLogout.addEventListener("click", async () => {
  try { await fetch("/api/logout", { method: "POST" }); } catch (e) {}
  loadDashboard();
});

/* ---------- boot ---------- */
/* Owner call 2026-09-21: the chat is ALWAYS on top of the landing page —
   every load of / starts with the hero chat (no dock boot, no engagement
   check). The handoff (hero fades on first reply) + compact chat still apply
   within the session. /?home=1 additionally resets the transcript view. */
/* Item 3 (owner fixes 2026-09-21): the brand link carries /?home=1. Arriving
   with that param resets to the pristine first screen — hero visible, dock NOT
   engaged. The stored transcript stays in sessionStorage (kept, not rendered). */
const HOME_RESET = (() => { try { return new URL(location.href).searchParams.has("home"); } catch (e) { return false; } })();
if (HOME_RESET) {
  try { sessionStorage.removeItem("el-engaged"); } catch (e) {}
}
if (dock) dock.hidden = true;
if (heroSec) heroSec.hidden = false;
if (!HOME_RESET) restoreTranscript(); /* U6: mid-conversation reload keeps history (dock hidden until handoff) */
if (heroText) heroText.focus();
pollHealth();
setInterval(pollHealth, 15000);
loadListings();

/* U1: hero form + chips route through the same send() — one brain everywhere */
if (heroForm) {
  heroForm.addEventListener("submit", (e) => {
    e.preventDefault();
    send(heroText.value);
    heroText.value = "";
  });
  heroText.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(heroText.value); heroText.value = ""; }
  });
  heroText.addEventListener("input", () => {
    heroText.style.height = "auto";
    heroText.style.height = Math.min(heroText.scrollHeight, 160) + "px";
  });
}
if (heroChips) heroChips.addEventListener("click", (e) => {
  const b = e.target.closest(".chip");
  if (b && b.dataset.q) send(b.dataset.q);
});

/* U1: hero live strip — happenings only (item 4), honest (no fake data).
   Item 1: hero cards do NOT navigate to /l/{id} — clicking one expands the
   matching board card in place via the grid's detail panel. */
async function loadHeroStrip() {
  if (!heroStrip) return;
  try {
    const r = await fetch("/api/listings?limit=48", { cache: "no-store" });
    const d = await r.json();
    const all = d.listings || d.results || (Array.isArray(d) ? d : []);
    const list = all.filter(isHappening).slice(0, 4);
    heroStrip.textContent = "";
    /* W3 item 16: the pulse signals REAL live listings only — no listings,
       no pulse (honest, never decorative). */
    const heroLive = document.getElementById("hero-live");
    if (heroLive) heroLive.classList.toggle("has-live", list.length > 0);
    if (!list.length) {
      heroLive.hidden = true;
      return;
    }
    list.forEach((l) => {
      const a = document.createElement("button");
      a.className = "hero-card";
      a.type = "button";
      const top = document.createElement("div"); top.className = "hc-top";
      const dt = fmtDate(l.date);
      top.textContent = (dt ? dt.big + " " + dt.small : L("any time")) + " \u00b7 " + String(l.category || l.vertical || "").toUpperCase();
      const t = document.createElement("div"); t.className = "hc-title"; t.textContent = l.title || L("Untitled");
      const bot = document.createElement("div"); bot.className = "hc-bottom";
      const loc = document.createElement("span"); loc.textContent = l.location || "";
      const pr = document.createElement("span"); pr.className = "hc-price"; pr.textContent = priceOf(l).txt;
      bot.appendChild(loc); bot.appendChild(pr);
      a.appendChild(top); a.appendChild(t); a.appendChild(bot);
      a.addEventListener("click", () => {
        /* expand in place: if the board is showing the default curated set
           the card exists in the grid; otherwise re-render the default board
           first so the card is present, then open its detail panel. */
        if (BOARD) { BOARD = null; SIG = ""; renderGrid(); }
        const card = Array.from(grid.querySelectorAll(".card")).find((c) => {
          const xl = cardListing(c); return xl && String(xl.id) === String(l.id);
        });
        if (card) openDetail(card);
      });
      heroStrip.appendChild(a);
    });
  } catch (e) { /* hero strip is decoration; silent */ }
}
loadHeroStrip();

/* ---------- W3 item 19: taxonomy-driven chips (from /api/verticals) ------
   Real vocabulary only; honest cold-start fallback to generic starters.
   Applies to the hero chips and the Discover filter chips (reset preserved). */
const GENERIC_CHIPS = [
  { q: "free this weekend", label: L("free this weekend") },
  { q: "help", label: L("everything I can do") },
];
function chipBtn(q, label) {
  const b = document.createElement("button");
  b.className = "chip";
  b.type = "button";
  b.dataset.q = q;
  b.textContent = label;
  return b;
}
function fillChips(container, items, keepReset) {
  if (!container) return;
  const reset = keepReset ? container.querySelector("[data-reset]") : null;
  container.textContent = "";
  items.forEach((it) => container.appendChild(chipBtn(it.q, it.label)));
  if (reset) container.appendChild(reset);
}
async function loadTaxoChips() {
  let items = [];
  try {
    const r = await fetch("/api/verticals", { cache: "no-store" });
    if (r.ok) {
      const d = await r.json();
      const verts = d.verticals || {};
      Object.keys(verts).forEach((v) => {
        (verts[v].categories || []).slice(0, 2).forEach((c) => {
          items.push({ q: c, label: c });
        });
      });
    }
  } catch (e) { /* cold start: fall through to honest generic starters */ }
  items = items.slice(0, 4);
  if (!items.length) items = GENERIC_CHIPS.slice();
  else items.push({ q: "help", label: L("everything I can do") });
  fillChips(heroChips, items, false);
  fillChips(filters, items, true);
  /* SSR dock chips (dock.js pages get the same via their own fetch) */
  const dockChips = document.getElementById("chips");
  if (dockChips && !dockChips.dataset.keep) {
    fillChips(dockChips, items.concat([{ q: "signup", label: L("Create an account") },
                                       { q: "my-bookings", label: L("My bookings") }]), false);
  }
}
loadTaxoChips();

/* ---------- W3 item 18: type-ahead suggest under the hero input ----------
   Real listings only (hub /search via /api/suggest), debounced, abortable,
   graceful empty state. Click fills the input and sends. */
const heroSuggest = document.getElementById("hero-suggest");
let suggestTimer = null;
let suggestCtl = null;
function hideSuggest() {
  if (!heroSuggest) return;
  heroSuggest.hidden = true;
  heroSuggest.textContent = "";
}
function suggestRow(l) {
  const b = document.createElement("button");
  b.className = "sugg";
  b.type = "button";
  const dt = fmtDate(l.date);
  b.textContent = [l.title || L("Untitled"),
                   dt ? dt.big + " " + dt.small : "any time",
                   l.location || "",
                   priceOf(l).txt].filter(Boolean).join(" \u00b7 ");
  b.addEventListener("click", () => {
    hideSuggest();
    send("search " + (l.title || ""));
  });
  return b;
}
async function runSuggest(term) {
  if (!heroSuggest || term.length < 2) { hideSuggest(); return; }
  if (suggestCtl) suggestCtl.abort();
  suggestCtl = new AbortController();
  try {
    const r = await fetch("/api/suggest?q=" + encodeURIComponent(term),
                          { signal: suggestCtl.signal, cache: "no-store" });
    if (!r.ok) { hideSuggest(); return; }
    const d = await r.json();
    heroSuggest.textContent = "";
    const list = (d.listings || []).slice(0, 3);
    list.forEach((l) => heroSuggest.appendChild(suggestRow(l)));
    heroSuggest.hidden = list.length === 0; /* graceful empty state: nothing */
  } catch (e) {
    if (e.name !== "AbortError") hideSuggest();
  }
}
if (heroText && heroSuggest) {
  heroText.addEventListener("input", () => {
    if (suggestTimer) clearTimeout(suggestTimer);
    const term = heroText.value.trim();
    if (term.length < 2) { hideSuggest(); return; }
    suggestTimer = setTimeout(() => runSuggest(term), 250); /* debounced */
  });
  heroText.addEventListener("keydown", (e) => { if (e.key === "Escape") hideSuggest(); });
  heroForm.addEventListener("submit", hideSuggest);
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".hero-suggest") && e.target !== heroText) hideSuggest();
  });
}

/* ---------- W3 item 17: ghost example conversation (honestly labeled) ----
   Plays ONCE on the first visit inside the hero; skips instantly on any real
   engagement; reduced-motion renders it statically. Every part carries the
   visible 'example' tag — it is a fixture, never live activity (I9). */
const GHOST_KEY = "el-ghost-done";
const GHOST_FIXTURE = LANG === "de" ? DE_GHOST_FIXTURE : {
  q: "a jazz thing in Vienna this weekend",
  a: "Found 3 \u2014 Rooftop Jazz Night fits: quartet, sunset, \u20ac15 on Oct 3. Want me to book it?",
  card: { title: "Rooftop Jazz Night", when: "Oct 3 \u00b7 Vienna", price: "\u20ac15" },
  esc: "money held safely \u2014 released to the organizer after the event",
};
function ghostShell() {
  const wrap = document.createElement("div");
  wrap.className = "hero-ghost-inner";
  const tag = document.createElement("span");
  tag.className = "ghost-tag";
  tag.textContent = L("example \u2014 not a real chat");
  wrap.appendChild(tag);
  return wrap;
}
function ghostStatic() {
  /* reduced-motion / instant variant: everything visible at once */
  const wrap = ghostShell();
  const u = document.createElement("div"); u.className = "msg user";
  const ub = document.createElement("div"); ub.className = "bubble"; ub.textContent = GHOST_FIXTURE.q;
  u.appendChild(ub);
  const a = document.createElement("div"); a.className = "msg agent";
  const ab = document.createElement("div"); ab.className = "bubble"; ab.textContent = GHOST_FIXTURE.a;
  a.appendChild(ab);
  wrap.appendChild(u); wrap.appendChild(a);
  wrap.appendChild(ghostCard(true));
  return wrap;
}
function ghostCard(closed) {
  const c = document.createElement("div"); c.className = "ghostcard" + (closed ? " closed" : "");
  const t = document.createElement("div"); t.className = "gc-title"; t.textContent = GHOST_FIXTURE.card.title;
  const m = document.createElement("div"); m.className = "gc-meta"; m.textContent = GHOST_FIXTURE.card.when + " \u00b7 " + GHOST_FIXTURE.card.price;
  const s = document.createElement("div"); s.className = "gc-esc";
  s.textContent = (closed ? "\u272a " : "") + (closed ? GHOST_FIXTURE.esc : L("holding your payment\u2026"));
  c.appendChild(t); c.appendChild(m); c.appendChild(s);
  return c;
}
async function playGhost() {
  if (!heroSec || heroSec.hidden) return;
  if (isEngaged()) return;
  try { if (localStorage.getItem(GHOST_KEY)) return; } catch (e) { return; }
  const host = document.getElementById("hero-ghost");
  if (!host) return;
  /* skip instantly on any real input or engagement */
  const skip = () => { stopGhost(); };
  let stopped = false;
  function stopGhost() {
    if (stopped) return;
    stopped = true;
    host.hidden = true;
    host.textContent = "";
    heroText.removeEventListener("focus", skip);
    heroForm.removeEventListener("submit", skip);
    document.removeEventListener("keydown", skip);
  }
  heroText.addEventListener("focus", skip);
  heroForm.addEventListener("submit", skip);
  document.addEventListener("keydown", skip);
  try { localStorage.setItem(GHOST_KEY, "1"); } catch (e2) {}
  if (REDUCE()) {
    host.textContent = "";
    host.appendChild(ghostStatic());
    host.hidden = false;
    return;
  }
  host.hidden = false;
  const wrap = ghostShell();
  host.textContent = "";
  host.appendChild(wrap);
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  /* 1: the query types itself */
  const u = document.createElement("div"); u.className = "msg user";
  const ub = document.createElement("div"); ub.className = "bubble"; ub.textContent = "";
  u.appendChild(ub); wrap.appendChild(u);
  for (let i = 1; i <= GHOST_FIXTURE.q.length; i++) {
    if (stopped) return;
    ub.textContent = GHOST_FIXTURE.q.slice(0, i);
    await sleep(38);
  }
  await sleep(350);
  if (stopped) return;
  /* 2: the brain-style reply */
  const a = document.createElement("div"); a.className = "msg agent";
  const ab = document.createElement("div"); ab.className = "bubble"; ab.textContent = "";
  a.appendChild(ab); wrap.appendChild(a);
  for (let i = 1; i <= GHOST_FIXTURE.a.length; i += 2) {
    if (stopped) return;
    ab.textContent = GHOST_FIXTURE.a.slice(0, i);
    await sleep(24);
  }
  ab.textContent = GHOST_FIXTURE.a;
  await sleep(350);
  if (stopped) return;
  /* 3: the mini booking card forms */
  const card = ghostCard(false);
  wrap.appendChild(card);
  await sleep(650);
  if (stopped) return;
  /* 4: the escrow lock closes */
  card.classList.add("closed");
  const s = card.querySelector(".gc-esc");
  s.textContent = "\u272a " + GHOST_FIXTURE.esc;
}
try { if (!localStorage.getItem(GHOST_KEY)) setTimeout(playGhost, 1400); } catch (e) {}

/* U6: '/' focuses the chat from anywhere (hero text or dock input) */
document.addEventListener("keydown", (e) => {
  if (e.key === "/" && !e.metaKey && !e.ctrlKey && !e.altKey
      && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
    e.preventDefault();
    openChat();
    input.focus();
  }
});
/* W2 deep links: /?book=<id> from detail pages -> prefill (never auto-send:
   booking stays a human confirm); /?q=<search> -> run the search in chat. */
try {
  const u = new URL(location.href);
  const bid = u.searchParams.get("book");
  const q = u.searchParams.get("q");
  const view = u.searchParams.get("view");
  if (view === "dash") { showView("dash"); loadDashboard(); }
  if (bid) {
    openChat();
    input.value = "book " + bid + " ";
    input.focus();
    autosize();
  } else if (q) {
    openChat();
    send(q.slice(0, 200));
  }
} catch (e) {}

/* ============ P0 human paid bookings (spec 2026-09-29) ============
   The reply carries payment_request {listing_id, amount, asset, network,
   scheme, receiver, units}. A Pay button renders under the reply; tapping
   it connects an injected wallet (MetaMask/Coinbase), signs the EIP-3009
   TransferWithAuthorization via eth_signTypedData_v4, and submits it to
   /api/pay/submit. The hub verifies the signature itself (x402verify) and
   settles via the facilitator. Pilot: real flow, test money (testnet). */
let PAY_REQ = null;

function renderPayButton(req, bubble) {
  if (!req || !req.listing_id || !req.receiver) return;
  PAY_REQ = req;
  const bar = document.createElement("div");
  bar.className = "paybar";
  const b = document.createElement("button");
  b.className = "paybtn";
  b.textContent = "\ud83d\udcb3 Pay " + (req.amount || "") + " USDC (pilot test money)";
  b.onclick = startPayFlow;
  bar.appendChild(b);
  const hint = document.createElement("div");
  hint.className = "payhint";
  hint.textContent = "\ud83d\udd10 wallet \u2192 escrow \u00b7 verified by the hub \u00b7 refund window per listing terms";
  bar.appendChild(hint);
  (bubble || chat).appendChild(bar);
  chat.scrollTop = chat.scrollHeight;
}

async function startPayFlow() {
  if (!PAY_REQ) return;
  const req = PAY_REQ;
  if (!window.ethereum) {
    addMsg("err", L("No wallet found \u2014 install MetaMask or Coinbase Wallet, then tap Pay again. (Pilot: test money, real flow.)"));
    return;
  }
  let addr;
  try {
    addMsg("agent", "Connecting your wallet \u2026");
    const accs = await window.ethereum.request({ method: "eth_requestAccounts" });
    addr = (accs || [])[0];
    if (!addr) throw new Error("no account");
  } catch (e) {
    addMsg("err", L("Wallet connection was cancelled \u2014 tap Pay again when you're ready."));
    return;
  }
  const now = Math.floor(Date.now() / 1000);
  const auth = {
    from: addr,
    to: req.receiver,
    value: String(req.units || String(Math.round(parseFloat(req.amount || "0") * 1000000))),
    validAfter: now - 60,
    validBefore: now + 600,
    nonce: "0x" + Array.from(crypto.getRandomValues(new Uint8Array(32)))
      .map((b) => b.toString(16).padStart(2, "0")).join(""),
  };
  const domain = { name: "USD Coin", version: "2", chainId: 84532, verifyingContract: "0x036CbD53842c5426634e7929541eC2318f3dCF7e" };
  const types = { TransferWithAuthorization: [
    { name: "from", type: "address" }, { name: "to", type: "address" },
    { name: "value", type: "uint256" }, { name: "validAfter", type: "uint256" },
    { name: "validBefore", type: "uint256" }, { name: "nonce", type: "bytes32" }] };
  let sig;
  try {
    const status = addMsg("agent", "Your wallet asks for one signature \u2014 check amount and recipient, then confirm.");
    const res = await window.ethereum.request({
      method: "eth_signTypedData_v4",
      params: [addr, JSON.stringify({ domain, types, primaryType: "TransferWithAuthorization", message: auth })],
    });
    sig = res;
    status.remove();
  } catch (e) {
    addMsg("err", L("Signature was declined \u2014 nothing was paid. Tap Pay again anytime."));
    return;
  }
  const payload = { x402Version: 1, scheme: "exact", network: req.network || "base-sepolia",
    payload: { authorization: auth, signature: sig.startsWith("0x") ? sig : "0x" + sig } };
  const b64 = btoa(unescape(encodeURIComponent(JSON.stringify(payload))));
  const wait = addMsg("agent", "\u23f3 Payment sent \u2014 the hub is verifying your signature and settling \u2026");
  try {
    const r = await fetch("/api/pay/submit", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payment: b64, listing_id: req.listing_id }),
    });
    const d = await r.json().catch(() => ({}));
    wait.remove();
    if (r.ok && d.ok) {
      const conf = "\u2705 Booked and paid! Booking " + d.booking_id +
        "\n\n\ud83d\udcb3 Money: " + (d.escrow === "HELD" ? "your payment is locked safely in escrow \u2014 the organizer can't touch it until the event has ended" :
          d.escrow === "DIRECT" ? "instant rail \u2014 settled at booking (no refund window)" : "payment recorded") +
        (d.refund_window_hours ? " \u00b7 refund window " + d.refund_window_hours + "h" : "") +
        "\n\n\ud83d\udd11 YOUR BOOKING SECRET \u2014 shown once, only here. Copy it NOW:\n" + d.booking_secret +
        "\n(It unlocks your private booking details \u2014 check status anytime by asking: booking " + d.booking_id + ")" +
        "\n\n\ud83e\uddea Pilot money \u2014 real flow, test funds.";
      addMsg("agent", conf);
      PAY_REQ = null;
      saveTranscript();
    } else {
      addMsg("err", L("Payment didn't go through \u2014 " + (d.error || "the hub rejected it") + ". Nothing was booked; try again or pick a free one."));
    }
  } catch (e) {
    wait.remove();
    addMsg("err", L("The connection hiccuped mid-payment \u2014 nothing was booked. Tap Pay again."));
  }
}


/* Copy to clipboard helper */
function copyText(text) {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(text).then(() => {
      addMsg("agent", "✅ Copied to clipboard");
    }).catch(() => {
      addMsg("err", "Failed to copy");
    });
  } else {
    addMsg("err", "Clipboard not available");
  }
}
