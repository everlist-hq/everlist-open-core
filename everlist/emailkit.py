import email.utils
import html as _html
import os
import smtplib
from email.message import EmailMessage

# Phase B+, owner request 2026-09-17: make hub emails look proper and legit.
# Standards used by every serious sender:
#   * multipart/alternative: rich HTML + plain-text fallback (deliverability)
#   * RFC 2369 List-Unsubscribe + RFC 8058 One-Click (Gmail unsubscribe button)
#   * proper From display name, Date, Message-ID, List-Id headers
#   * table-based, inline-styled HTML (email clients strip <style> tags)
# Brand: EverList dark navy + emerald green + cyan accent (site palette).
# Everything is honest: sender identified, escrow explained, easy opt-out.

PUBLIC_URL = os.environ.get("HUB_PUBLIC_URL", "https://everlist.network").rstrip("/")
BRAND = "EverList"
TAGLINE = "a listing is something with a date where a human is needed"

_C = {"bg": "#f2f5f9", "navy": "#0d1b2a", "ink": "#22374d", "mut": "#62788f",
      "green": "#2ecc71", "green_d": "#1f9d55", "cyan": "#38bdf8", "line": "#dde5ee",
      "chipbg": "#e8f8f0", "card": "#ffffff", "foot": "#eef2f7"}


# ------------------------------------------------------------- i18n (W2) ---
# German email layer (2026-09-28). English-as-key like i18n.py; callers that
# pass no loc keep English output. German escrow wording mirrors the EN
# honesty contract 1:1 (no softer promises in German).

_DE = {
    "New booking: ": "Neue Buchung: ",
    "Confirmed: ": "Best\u00e4tigt: ",
    "Refunded: ": "Erstattet: ",
    "Cancelled: ": "Storniert: ",
    "New booking - escrow is holding the payment": "Neue Buchung \u2013 Escrow verwahrt die Zahlung",
    "Your booking is confirmed": "Ihre Buchung ist best\u00e4tigt",
    "Booking cancelled - full refund on its way": "Buchung storniert \u2013 volle Erstattung unterwegs",
    "A booking was cancelled": "Eine Buchung wurde storniert",
    "Listing": "Inserat",
    "Booking": "Buchung",
    "Amount held": "Verwahrter Betrag",
    "Amount": "Betrag",
    "Confirmation": "Best\u00e4tigung",
    "Refunded": "Erstattet",
    "Refunded to buyer": "An K\u00e4ufer erstattet",
    "Week": "Woche",
    "Active listings": "Aktive Inserate",
    "New bookings": "Neue Buchungen",
    "Confirmed (escrow released)": "Best\u00e4tigt (Escrow freigegeben)",
    "Cancelled (auto-refunded)": "Storniert (autom. erstattet)",
    "Gross booked": "Gebucht (brutto)",
    "Open EverList": "EverList \u00f6ffnen",
    "View on EverList": "Auf EverList ansehen",
    "Find something else": "Etwas anderes finden",
    "Review bookings": "Buchungen ansehen",
    "Go to EverList": "Zu EverList",
    "Someone just booked <b>%s</b>. The money is already sitting in escrow - it moves to you when you confirm the booking.":
        "Jemand hat soeben <b>%s</b> gebucht. Das Geld liegt bereits im Escrow \u2013 es wandert zu Ihnen, sobald Sie die Buchung best\u00e4tigen.",
    "Confirm it in your EverList dashboard under <b>my-listings</b> (or reply to your agent). Unconfirmed bookings auto-refund when the refund window lapses.":
        "Best\u00e4tigen Sie sie in Ihrem EverList-Dashboard unter <b>my-listings</b> (oder antworten Sie Ihrem Agenten). Unbest\u00e4tigte Buchungen werden automatisch erstattet, wenn das Erstattungsfenster abl\u00e4uft.",
    "New booking for: %s (booking %s)\nAmount: %s (escrow: %s)\n\nConfirm it in the EverList chat (my-listings) or via POST /book/%s/confirm.\nUnconfirmed bookings auto-refund when the refund window lapses.":
        "Neue Buchung f\u00fcr: %s (Buchung %s)\nBetrag: %s (Escrow: %s)\n\nBest\u00e4tigen Sie sie im EverList-Chat (my-listings) oder via POST /book/%s/confirm.\nUnbest\u00e4tigte Buchungen werden automatisch erstattet, wenn das Erstattungsfenster abl\u00e4uft.",
    "The organizer confirmed <b>%s</b>. Escrow released the payment - you are all set.":
        "Der Veranstalter hat <b>%s</b> best\u00e4tigt. Escrow hat die Zahlung freigegeben \u2013 alles erledigt.",
    "Your booking for: %s (booking %s) is confirmed.\nEscrow released to the organizer. Amount: %s.\nConfirmation: %s-ticket":
        "Ihre Buchung f\u00fcr: %s (Buchung %s) ist best\u00e4tigt.\nEscrow an den Veranstalter freigegeben. Betrag: %s.\nBest\u00e4tigung: %s-ticket",
    "Your booking for <b>%s</b> was cancelled. Escrow refunded you in full - no money was lost.":
        "Ihre Buchung f\u00fcr <b>%s</b> wurde storniert. Escrow hat Ihnen den vollen Betrag erstattet \u2013 kein Geld verloren.",
    "Your booking for: %s (booking %s) was cancelled.\nFull refund. Amount: %s.":
        "Ihre Buchung f\u00fcr: %s (Buchung %s) wurde storniert.\nVolle Erstattung. Betrag: %s.",
    "Booking <b>%s</b> for <b>%s</b> was cancelled by the buyer. Escrow refunded the buyer automatically.":
        "Die Buchung <b>%s</b> f\u00fcr <b>%s</b> wurde vom K\u00e4ufer storniert. Escrow hat dem K\u00e4ufer automatisch erstattet.",
    "Booking %s for: %s was cancelled by the buyer.\nEscrow refunded to the buyer. Amount: %s.":
        "Buchung %s f\u00fcr: %s wurde vom K\u00e4ufer storniert.\nEscrow an den K\u00e4ufer erstattet. Betrag: %s.",
    "\n\nTurn notifications off: say notify off in the EverList chat.":
        "\n\nBenachrichtigungen aus: sagen Sie notify off im EverList-Chat.",
    "Your week on EverList": "Ihre Woche auf EverList",
    "%s to %s": "%s bis %s",
    "Your week on EverList: %d booking": "Ihre Woche auf EverList: %d Buchung",
    "Here is your week at a glance. Nothing to do unless something needs confirming - unconfirmed bookings auto-refund when the refund window lapses.":
        "Ihre Woche im \u00dcberblick. Nichts zu tun \u2013 au\u00dfer etwas braucht Best\u00e4tigung: Unbest\u00e4tigte Buchungen werden automatisch erstattet, wenn das Erstattungsfenster abl\u00e4uft.",
    "A quiet week - no new bookings. Your listings stay up and bookable; agents can find them around the clock.":
        "Eine ruhige Woche \u2013 keine neuen Buchungen. Ihre Inserate bleiben online und buchbar; Agenten finden sie rund um die Uhr.",
    "Your week on EverList (%s)\nActive listings: %d\nNew bookings: %d\nConfirmed: %d\nCancelled: %d\nGross booked: %s\n\nTurn notifications off: say notify off in the EverList chat.":
        "Ihre Woche auf EverList (%s)\nAktive Inserate: %d\nNeue Buchungen: %d\nBest\u00e4tigt: %d\nStorniert: %d\nGebucht (brutto): %s\n\nBenachrichtigungen aus: sagen Sie notify off im EverList-Chat.",
    "EverList email verification": "EverList E-Mail-Best\u00e4tigung",
    "EverList account recovery": "EverList Konto-Wiederherstellung",
    "Verify your email": "E-Mail best\u00e4tigen",
    "Account recovery": "Konto-Wiederherstellung",
    "Enter this code in EverList to link and verify your email address. It works for <b>%d minutes</b>.":
        "Geben Sie diesen Code in EverList ein, um Ihre E-Mail-Adresse zu verkn\u00fcpfen und zu best\u00e4tigen. Er gilt <b>%d Minuten</b>.",
    "Your EverList verification code: %s\nValid %d minutes. If you did not request this, ignore it.":
        "Ihr EverList-Best\u00e4tigungscode: %s\nG\u00fcltig f\u00fcr %d Minuten. Falls Sie dies nicht angefordert haben, ignorieren Sie ihn.",
    "Use this code together with your email and a new account code to recover access. It works for <b>%d minutes</b>.":
        "Nutzen Sie diesen Code zusammen mit Ihrer E-Mail und einem neuen Account-Code, um den Zugriff wiederherzustellen. Er gilt <b>%d Minuten</b>.",
    "Your EverList recovery code: %s\nValid %d minutes.\nConfirm with email + code + a new code at /accounts/email/recover/confirm.":
        "Ihr EverList-Wiederherstellungscode: %s\nG\u00fcltig f\u00fcr %d Minuten.\nBest\u00e4tigen Sie mit E-Mail + Code + einem neuen Code unter /accounts/email/recover/confirm.",
    '<span style="color:%s;font-size:12px;">If you did not request this, ignore this email - nothing changes.</span>':
        '<span style="color:%s;font-size:12px;">Falls Sie dies nicht angefordert haben, ignorieren Sie diese E-Mail \u2013 nichts \u00e4ndert sich.</span>',
    "Sent by the %s hub (%s) - you have booking notifications enabled.":
        "Gesendet vom %s-Hub (%s) \u2013 Buchungsbenachrichtigungen sind aktiviert.",
    '<a href="%s" style="color:%s;">Unsubscribe from promotional emails</a> (weekly digest; booking + security emails unaffected) &nbsp;or say <b>notify off</b> in the EverList chat for booking mails.':
        '<a href="%s" style="color:%s;">Werbe-E-Mails abbestellen</a> (w\u00f6chentlicher Digest; Buchungs- und Sicherheits-Mails bleiben unber\u00fchrt) &nbsp;oder sagen Sie <b>notify off</b> im EverList-Chat f\u00fcr Buchungsmails.',
    "Say <b>notify off</b> in the EverList chat to turn these off.":
        "Sagen Sie <b>notify off</b> im EverList-Chat, um diese auszuschalten.",
    "You're unsubscribed": "Abbestellt",
    "Link expired": "Link abgelaufen",
    "You will no longer receive the weekly promotional digest. <b>Booking notifications and security codes are NOT affected</b> - those are service messages and keep arriving. To also silence booking mails, say <b>notify off</b> in the EverList chat.":
        "Sie erhalten den w\u00f6chentlichen Werbe-Digest nicht mehr. <b>Buchungsbenachrichtigungen und Sicherheitscodes sind NICHT betroffen</b> \u2013 das sind Servicemeldungen und bleiben aktiv. Um auch Buchungsmails stummzuschalten, sagen Sie <b>notify off</b> im EverList-Chat.",
    "That unsubscribe link is not valid. Say <b>notify off</b> in the EverList chat instead.":
        "Dieser Abbestell-Link ist nicht g\u00fcltig. Sagen Sie stattdessen <b>notify off</b> im EverList-Chat.",
    "No changes were needed - notifications were already off.":
        "Keine \u00c4nderungen n\u00f6tig \u2013 Benachrichtigungen waren bereits aus.",
}


def _L(s, loc="en"):
    if loc == "de" and s in _DE:
        return _DE[s]
    return s


def _fmt_amt(amount, loc="en"):
    if isinstance(amount, (int, float)):
        s = '%.2f' % amount
        return s.replace('.', ',') if loc == 'de' else s
    return str(amount)


def _esc(s):
    return _html.escape(str(s), quote=True)


def _detail_rows(rows):
    trs = []
    for k, v in rows:
        trs.append(
            '<tr>'
            '<td style="padding:8px 0;color:%s;font-size:13px;width:38%%;">%s</td>'
            '<td style="padding:8px 0;color:%s;font-size:13px;font-weight:600;text-align:right;">%s</td>'
            '</tr>' % (_C["mut"], _esc(k), _C["ink"], _esc(v)))
    return ('<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" '
            'style="background:%s;border-radius:8px;padding:6px 16px;margin:0 0 20px;">'
            % _C["bg"]) + "".join(trs) + '</table>'


def _btn(label, url):
    return ('<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
            '<td style="background:%s;border-radius:8px;">'
            '<a href="%s" style="display:inline-block;padding:11px 26px;color:#ffffff;'
            'font-size:14px;font-weight:700;text-decoration:none;">%s</a>'
            '</td></tr></table>' % (_C["green_d"], _esc(url), _esc(label)))


def _shell(heading, body_html, footer_html):
    return (
        '<!DOCTYPE html><html><body style="margin:0;padding:0;background:%s;">'
        '<table role="presentation" width="100%%" cellpadding="0" cellspacing="0" '
        'style="background:%s;padding:28px 12px;"><tr><td align="center">'
        '<table role="presentation" width="600" cellpadding="0" cellspacing="0" '
        'style="max-width:600px;width:100%%;font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;">'
        '<tr><td style="background:%s;padding:22px 32px;border-radius:10px 10px 0 0;">'
        '<a href="%s" style="text-decoration:none;">'
        '<span style="color:%s;font-size:21px;font-weight:800;letter-spacing:.4px;">Ever</span>'
        '<span style="color:%s;font-size:21px;font-weight:800;letter-spacing:.4px;">List</span></a>'
        '<div style="color:#9fb3c8;font-size:11px;margin-top:5px;">%s</div>'
        '</td></tr>'
        '<tr><td style="background:%s;padding:30px 32px 26px;">'
        '<h1 style="margin:0 0 14px;color:%s;font-size:20px;line-height:1.3;">%s</h1>'
        '%s'
        '</td></tr>'
        '<tr><td style="background:%s;padding:16px 32px;border-radius:0 0 10px 10px;">'
        '<div style="color:#7a8ca0;font-size:11px;line-height:1.7;">%s</div>'
        '</td></tr>'
        '</table></td></tr></table></body></html>'
        % (_C["bg"], _C["bg"], _C["navy"], PUBLIC_URL, _C["green"], _C["cyan"],
           _esc(TAGLINE), _C["card"], _C["navy"], _esc(heading), body_html,
           _C["foot"], footer_html))


def _p(text):
    return ('<p style="margin:0 0 18px;color:%s;font-size:14px;line-height:1.6;">%s</p>'
            % (_C["ink"], text))


def _footer_lines(unsub_url, note=None, loc="en"):
    lines = [_L('Sent by the %s hub (%s) - you have booking notifications enabled.', loc)
             % (_esc(BRAND), _esc(PUBLIC_URL.replace("https://", "")))]
    if note:
        lines.append(_esc(note))
    if unsub_url:
        lines.append(_L('<a href="%s" style="color:%s;">Unsubscribe from promotional emails</a>'
                     ' (weekly digest; booking + security emails unaffected)'
                     ' &nbsp;or say <b>notify off</b> in the EverList chat for booking mails.',
                     loc)
                     % (_esc(unsub_url), _C["cyan"]))
    else:
        lines.append(_L('Say <b>notify off</b> in the EverList chat to turn these off.', loc))
    return "<br>".join(lines)


# ---------------------------------------------------------------- booking ---

def booking_email(event, *, title, booking_id, amount, escrow, role, note=None,
                   unsub_url=None, loc="en"):
    """event: created|released|refunded|cancelled; role: owner|buyer.
    loc: "en"|"de" (i18n W2) — callers without locale keep English.
    Returns dict(subject, text, html)."""
    amt = _fmt_amt(amount, loc)
    view = PUBLIC_URL + "/booking/" + _esc(booking_id)

    if event == "created" and role == "owner":
        heading = _L("New booking - escrow is holding the payment", loc)
        intro = (_p(_L('Someone just booked <b>%s</b>. The money is already sitting in escrow - '
                    'it moves to you when you confirm the booking.', loc) % _esc(title))
                 + _detail_rows([(_L("Listing", loc), title), (_L("Booking", loc), booking_id),
                                 (_L("Amount held", loc), amt), (_L("Escrow", loc), escrow)])
                 + _p(_L('Confirm it in your EverList dashboard under <b>my-listings</b> '
                      '(or reply to your agent). Unconfirmed bookings auto-refund when '
                      'the refund window lapses.', loc))
                 + _btn(_L("Open EverList", loc), PUBLIC_URL))
        text = (_L("New booking for: %s (booking %s)\n"
                "Amount: %s (escrow: %s)\n\n"
                "Confirm it in the EverList chat (my-listings) or via POST /book/%s/confirm.\n"
                "Unconfirmed bookings auto-refund when the refund window lapses.", loc)
                % (title, booking_id, amt, escrow, booking_id))
        return {"subject": _L("New booking: ", loc) + title, "text": _with_unsub(text, loc) + (("\n\n" + note) if note else ""), "unsub_url": unsub_url, "html": _shell(heading, intro,
                _footer_lines(unsub_url, note=note, loc=loc))}

    if event == "released" and role == "buyer":
        heading = _L("Your booking is confirmed", loc)
        intro = (_p(_L('The organizer confirmed <b>%s</b>. Escrow released the payment - '
                    'you are all set.', loc) % _esc(title))
                 + _detail_rows([(_L("Listing", loc), title), (_L("Booking", loc), booking_id),
                                 (_L("Amount", loc), amt), (_L("Confirmation", loc), booking_id + "-ticket")])
                 + _btn(_L("View on EverList", loc), view))
        text = (_L("Your booking for: %s (booking %s) is confirmed.\n"
                "Escrow released to the organizer. Amount: %s.\n"
                "Confirmation: %s-ticket", loc) % (title, booking_id, amt, booking_id))
        return {"subject": _L("Confirmed: ", loc) + title, "text": _with_unsub(text, loc) + (("\n\n" + note) if note else ""), "unsub_url": unsub_url, "html": _shell(heading, intro,
                _footer_lines(unsub_url, note=note, loc=loc))}

    if event == "refunded" and role == "buyer":
        heading = _L("Booking cancelled - full refund on its way", loc)
        intro = (_p(_L('Your booking for <b>%s</b> was cancelled. Escrow refunded you in full - '
                    'no money was lost.', loc) % _esc(title))
                 + _detail_rows([(_L("Listing", loc), title), (_L("Booking", loc), booking_id),
                                 (_L("Refunded", loc), amt)])
                 + _btn(_L("Find something else", loc), PUBLIC_URL))
        text = (_L("Your booking for: %s (booking %s) was cancelled.\n"
                "Full refund. Amount: %s.", loc) % (title, booking_id, amt))
        return {"subject": _L("Refunded: ", loc) + title, "text": _with_unsub(text, loc) + (("\n\n" + note) if note else ""), "unsub_url": unsub_url, "html": _shell(heading, intro,
                _footer_lines(unsub_url, note=note, loc=loc))}

    if event == "cancelled" and role == "owner":
        heading = _L("A booking was cancelled", loc)
        intro = (_p(_L('Booking <b>%s</b> for <b>%s</b> was cancelled by the buyer. '
                    'Escrow refunded the buyer automatically.', loc) % (_esc(booking_id), _esc(title)))
                 + _detail_rows([(_L("Listing", loc), title), (_L("Booking", loc), booking_id),
                                 (_L("Refunded to buyer", loc), amt)])
                 + _btn(_L("Open EverList", loc), PUBLIC_URL))
        text = (_L("Booking %s for: %s was cancelled by the buyer.\n"
                "Escrow refunded to the buyer. Amount: %s.", loc) % (booking_id, title, amt))
        return {"subject": _L("Cancelled: ", loc) + title, "text": _with_unsub(text, loc) + (("\n\n" + note) if note else ""), "unsub_url": unsub_url, "html": _shell(heading, intro,
                _footer_lines(unsub_url, note=note, loc=loc))}

    raise ValueError("unknown event/role: %s/%s" % (event, role))


def _with_unsub(text, loc="en"):
    return text + _L("\n\nTurn notifications off: say notify off in the EverList chat.", loc)


# ------------------------------------------------------------------ digest ---

def organizer_digest(*, org_name, week_start, week_end, created=0, confirmed=0,
                     cancelled=0, gross=0.0, listings_active=0, unsub_url=None,
                     loc="en"):
    """Weekly summary for an organizer. Amounts in hub currency. Returns
    dict(subject, text, html). loc: "en"|"de" (i18n W2)."""
    span = _L('%s to %s', loc) % (week_start, week_end)
    heading = _L('Your week on EverList', loc)
    gross_s = _fmt_amt(gross, loc)
    n = created + confirmed + cancelled
    rows = [(_L("Week", loc), span), (_L("Active listings", loc), listings_active)]
    if created:
        rows.append((_L("New bookings", loc), created))
    if confirmed:
        rows.append((_L("Confirmed (escrow released)", loc), confirmed))
    if cancelled:
        rows.append((_L("Cancelled (auto-refunded)", loc), cancelled))
    rows.append((_L("Gross booked", loc), gross_s))
    intro = _p(_L('Here is your week at a glance. Nothing to do unless something '
               'needs confirming - unconfirmed bookings auto-refund when the '
               'refund window lapses.', loc))
    if n == 0:
        intro = _p(_L('A quiet week - no new bookings. Your listings stay up and '
                   'bookable; agents can find them around the clock.', loc))
        body = intro + _detail_rows(rows) + _btn(_L('Open EverList', loc), PUBLIC_URL)
    else:
        body = intro + _detail_rows(rows) + _btn(_L('Review bookings', loc), PUBLIC_URL)
    text = (_L('Your week on EverList (%s)\n'
            'Active listings: %d\nNew bookings: %d\nConfirmed: %d\n'
            'Cancelled: %d\nGross booked: %s\n\n'
            'Turn notifications off: say notify off in the EverList chat.', loc)
            % (span, listings_active, created, confirmed, cancelled, gross_s))
    plural = '' if n == 1 else ('en' if loc == 'de' else 's')
    return {"subject": _L("Your week on EverList: %d booking", loc) % n + plural,
            "text": text, "html": _shell(heading, body, _footer_lines(unsub_url, loc=loc))}


# ------------------------------------------------------------------- codes ---

def code_email(kind, code, minutes=15, loc="en"):
    """kind: verify|recover. loc: "en"|"de" (i18n W2).
    Returns dict(subject, text, html)."""
    if kind == "verify":
        subject = _L("EverList email verification", loc)
        heading = _L("Verify your email", loc)
        intro = _p(_L('Enter this code in EverList to link and verify your email address. '
                   'It works for <b>%d minutes</b>.', loc) % minutes)
        text = (_L("Your EverList verification code: %s\nValid %d minutes. "
                "If you did not request this, ignore it.", loc) % (code, minutes))
    else:
        subject = _L("EverList account recovery", loc)
        heading = _L("Account recovery", loc)
        intro = _p(_L('Use this code together with your email and a new account code to '
                   'recover access. It works for <b>%d minutes</b>.', loc) % minutes)
        text = (_L("Your EverList recovery code: %s\nValid %d minutes.\n"
                "Confirm with email + code + a new code at /accounts/email/recover/confirm.",
                loc) % (code, minutes))
    code_html = ('<div style="background:%s;border:1px solid %s;border-radius:8px;'
                 'padding:16px 20px;margin:0 0 20px;text-align:center;">'
                 '<span style="font-family:Menlo,Consolas,monospace;font-size:26px;'
                 'letter-spacing:6px;color:%s;font-weight:700;">%s</span></div>'
                 % (_C["bg"], _C["line"], _C["navy"], _esc(code)))
    warn = _p(_L('<span style="color:%s;font-size:12px;">If you did not request this, '
              'ignore this email - nothing changes.</span>', loc) % _C["mut"])
    html = _shell(heading, intro + code_html + warn, _footer_lines(None, loc=loc))
    return {"subject": subject, "text": text, "html": html}


# ------------------------------------------------------------------- MIME ---

def mime_message(from_addr, to_addr, subject, text, html=None,
                 unsub_url=None, list_id=None):
    msg = EmailMessage()
    disp = "%s <%s>" % (BRAND, from_addr)
    msg["From"] = disp
    msg["To"] = to_addr
    # RTF2 sink guard (red-team 2026-09-19): titles flow into subjects via
    # booking_email(); strip CRLF (header folding/smuggling) + bidi overrides
    # and other controls at the single chokepoint. Newlines have no place in
    # a subject line; legacy poisoned titles in old state get cleaned here too.
    import re as _re
    subject = _re.sub("[\\x00-\\x08\\x0b\\x0c\\x0e-\\x1f\\x7f\\u202a-\\u202e]", "", str(subject))
    subject = subject.replace("\r", " ").replace("\n", " ")
    msg["Subject"] = subject
    msg["Date"] = email.utils.formatdate(localtime=False)
    msg["Message-ID"] = email.utils.make_msgid(domain=from_addr.split("@", 1)[-1])
    if list_id:
        msg["List-Id"] = "%s notifications <%s.%s>" % (
            BRAND, list_id, from_addr.split("@", 1)[-1])
    if unsub_url:
        msg["List-Unsubscribe"] = "<%s>" % unsub_url
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")
    return msg


def send_smtp(host, port, user, password, from_addr, to, msg, timeout=15):
    with smtplib.SMTP(host, int(port), timeout=timeout) as srv:
        srv.starttls()
        srv.login(user, password)
        srv.send_message(msg)


# ------------------------------------------------------- unsubscribe page ---

def unsub_page(ok=True, already=False, loc="en"):
    if ok:
        head = _L("You're unsubscribed", loc)
        body = _p(_L('You will no longer receive the weekly promotional digest. '
                  '<b>Booking notifications and security codes are NOT affected</b> - '
                  'those are service messages and keep arriving. To also silence '
                  'booking mails, say <b>notify off</b> in the EverList chat.', loc))
    elif already is not None and not ok:
        head = _L("Link expired", loc)
        body = _p(_L('That unsubscribe link is not valid. Say <b>notify off</b> '
                  'in the EverList chat instead.', loc))
    else:
        head = _L("You're unsubscribed", loc)
        body = _p(_L('No changes were needed - notifications were already off.', loc))
    return _shell(head, body + _btn(_L("Go to EverList", loc), PUBLIC_URL),
                  _footer_lines(None, loc=loc))
