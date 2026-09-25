"""test_phrase.py — guard + layer battery for AI-authored replies (spec §9).
All hermetic: the author call is mocked; no live LLM in CI.
Run: python test_phrase.py
"""
import json
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.environ.setdefault("EVERLIST_PHRASE", "1")
import phrase  # noqa: E402

TEMPLATE = ("I found 4 matches - they're open on the board for you. "
            "Say 'book <n>' to book one. 2026-10-03, from 15 EUR.")
SECRET_T = ("✅ Booked! 'Jazz' - booking bk-abc1234567890123.\n"
            "🔑 YOUR BOOKING SECRET - shown once: f0e1d2c3b4a5968778695a4b3c2d1e0f\n"
            "This chat resets if you reload.")


class PhraseGuard(unittest.TestCase):
    def setUp(self):
        phrase._ENABLED = True
        phrase._RL.clear()
        phrase._STAT.update({"ok": 0, "retried": 0, "fallback": 0,
                             "outage": 0, "skipped": 0})

    # ---- §9.1 mutation battery: altered/dropped facts FAIL ----

    def test_mutation_altered_price(self):
        ok, v = phrase._guard_ok(TEMPLATE.replace("15 EUR", "18 EUR"), TEMPLATE)
        self.assertFalse(ok)
        self.assertTrue(any(("invented" in x or "missing" in x) for x in v), v)

    def test_mutation_transliterated_number(self):
        ok, _ = phrase._guard_ok(TEMPLATE.replace("15 EUR", "fifteen EUR"), TEMPLATE)
        self.assertFalse(ok)

    def test_mutation_dropped_id(self):
        t = "Booking bk-abc1234567890123 confirmed - 15 EUR held."
        a = "Your booking is confirmed - 15 EUR held!"
        ok, v = phrase._guard_ok(a, t)
        self.assertFalse(ok)
        self.assertTrue(any("bk-" in x for x in v), v)

    def test_mutation_dropped_date(self):
        ok, _ = phrase._guard_ok("See you on the third of October, 15 EUR.",
                                 "2026-10-03, 15 EUR.")
        self.assertFalse(ok)

    # ---- §9.2 invention battery ----

    def test_invention_spots(self):
        ok, v = phrase._guard_ok(TEMPLATE + " Only 12 spots left!", TEMPLATE)
        self.assertFalse(ok)
        self.assertTrue(any("invented" in x for x in v), v)

    def test_invention_price(self):
        ok, _ = phrase._guard_ok(TEMPLATE + " Just $5 more!", TEMPLATE)
        self.assertFalse(ok)

    def test_invention_date(self):
        ok, _ = phrase._guard_ok(TEMPLATE + " See you 2026-12-24!", TEMPLATE)
        self.assertFalse(ok)

    # ---- §9.3 false-positive battery: legit variations PASS ----

    def test_fp_reorder_and_greeting(self):
        good = ("Hey! Great pick - from 15 EUR, on 2026-10-03. "
                "Say 'book <n>' to book one - all 4 are open on the board.")
        self.assertTrue(phrase._guard_ok(good, TEMPLATE)[0])

    def test_fp_currency_equivalence(self):
        self.assertTrue(phrase._guard_ok(TEMPLATE.replace("15 EUR", "€15"),
                                         TEMPLATE)[0])

    def test_fp_math_bold_numbers(self):
        # verified fold: fullwidth digits NFKC-fold to ASCII (４ -> 4)
        good = TEMPLATE.replace("4", "\uff14").replace("15", "\uff11\uff15")
        self.assertTrue(phrase._guard_ok(good, TEMPLATE)[0])

    def test_fp_emoji_and_whitespace(self):
        good = ("✅  4  matches!  They are open.  From  15  EUR  -  2026-10-03. "
                "Say 'book <n>' :-)")
        self.assertTrue(phrase._guard_ok(good, TEMPLATE)[0])

    def test_fp_language_switch(self):
        good = ("Ich habe 4 Treffer gefunden - offen für dich. Sag 'book <n>', "
                "um einen zu buchen. 2026-10-03, ab 15 EUR.")
        self.assertTrue(phrase._guard_ok(good, TEMPLATE)[0])

    # ---- §9.5 secret redact/reinject ----

    def test_secrets_redacted_before_author(self):
        seen = {}

        def _fake(messages):
            seen["content"] = json.dumps(messages, ensure_ascii=False)
            return "Booked! Keep the [[SECRET]] line safe."
        with mock.patch.object(phrase, "_call", _fake):
            out = phrase.phrase(SECRET_T, "book 1", "s-sec")
        self.assertNotIn("f0e1d2c3", seen["content"])   # secret never sent
        self.assertIn("f0e1d2c3", out)                   # byte-identical back

    # ---- §9.6 retry ladder ----

    def test_retry_corrective_then_ship(self):
        bad = TEMPLATE.replace("4", "5")                 # invented fact
        outs = [bad, "Great news - " + TEMPLATE]        # attempt 2 passes
        calls = {"n": 0}

        def _fake(messages):
            calls["n"] += 1
            return outs[calls["n"] - 1]
        with mock.patch.object(phrase, "_call", _fake):
            out = phrase.phrase(TEMPLATE, "search jazz", "s-retry")
        self.assertIn("open on the board", out)
        self.assertEqual(calls["n"], 2)
        self.assertEqual(phrase._STAT["retried"], 1)

    def test_three_strikes_then_template(self):
        bad = TEMPLATE + " invented 99 EUR"
        calls = {"n": 0}

        def _fake(messages):
            calls["n"] += 1
            return bad
        with mock.patch.object(phrase, "_call", _fake):
            out = phrase.phrase(TEMPLATE, "search jazz", "s-fb")
        self.assertEqual(out, TEMPLATE)
        self.assertEqual(calls["n"], 3)
        self.assertEqual(phrase._STAT["fallback"], 1)

    # ---- §9.7 outage path ----

    def test_outage_no_retries(self):
        calls = {"n": 0}

        def _fake(messages):
            calls["n"] += 1
            return None
        with mock.patch.object(phrase, "_call", _fake):
            out = phrase.phrase(TEMPLATE, "search jazz", "s-out")
        self.assertEqual(out, TEMPLATE)
        self.assertEqual(calls["n"], 1)
        self.assertEqual(phrase._STAT["outage"], 1)

    # ---- eligibility ----

    def test_ineligible_pure_replay(self):
        self.assertEqual(phrase.phrase("2-4", "2-4", "s-el"), "2-4")
        self.assertEqual(phrase._STAT["skipped"], 1)

    def test_ineligible_intake_step(self):
        r = "[2/7] What does it cost in EUR? (0 = free)"
        self.assertEqual(phrase.phrase(r, "list", "s-el2"), r)

    def test_disabled_short_circuit(self):
        phrase._ENABLED = False
        try:
            self.assertEqual(phrase.phrase(TEMPLATE, "q", "s-off"), TEMPLATE)
        finally:
            phrase._ENABLED = True

    # ---- §9.8 policy pins ----

    def test_policy_pin(self):
        t = "Your money is held until the event ends - 72h refund window, 5% fee."
        a = ("We hold your money until the event has ended. You get a 72h "
             "refund window, and the fee is 5%.")
        self.assertTrue(phrase._guard_ok(a, t)[0])
        self.assertFalse(phrase._guard_ok(t.replace("72h", "48h"), t)[0])


if __name__ == "__main__":
    unittest.main(verbosity=2)
