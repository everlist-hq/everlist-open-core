"""Voice banks (S1/S2/S3, owner call 2026-09-25 'make the chat smart').
Laws tested:
  * bank[0] is byte-identical to the legacy string on a sender's FIRST voice turn
    (fresh senders = tests + agents keep the canonical experience);
  * real sessions rotate — the same stamp never repeats verbatim twice in a row;
  * every footer variant keeps the 'book <n>' marker (webchat board-rewrite
    detector depends on it) and the 'Nothing matched' prefix survives rotation;
  * S2 insights state ONLY true facts computed from the actual result set;
  * S3: a say line with an ungrounded price is dropped (facts law).
Run: python test_voice_banks.py
"""
import os
import sys
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import chatlib  # noqa: E402


def _ls(n, price=10):
    return [{"id": "even-%d" % i, "title": "Event %d" % i, "category": "concert",
             "date": "2026-10-03", "price": price, "vertical": "events",
             "description": "Description %d" % i} for i in range(1, n + 1)]


class VoiceBanks(unittest.TestCase):
    def setUp(self):
        chatlib._LAST_RESULTS.clear()
        chatlib._LAST_SEARCH.clear()
        chatlib._VOICE_TURN.clear()

    def test_first_turn_canonical_footer(self):
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": _ls(3)}):
            r = chatlib.handle_text("http://hub", "search concert", sender="v1")
        self.assertIn("\nTo book one, say 'book <n>' - $0 listings book without payment.", r)

    def test_footer_rotates_within_session(self):
        outs = []
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": _ls(3)}):
            for i in range(4):
                outs.append(chatlib.handle_text("http://hub", "search concert", sender="vrot"))
        tails = [o.split("\n")[-1] for o in outs]
        self.assertEqual(len(set(tails)), len(tails), "footer must not repeat verbatim")
        for t in tails:
            self.assertIn("book <n>", t)

    def test_no_match_prefix_stable(self):
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": []}):
            r = chatlib.handle_text("http://hub", "search zzzqqq", sender="vnm")
        self.assertTrue(r.startswith("Nothing matched"), r[:80])

    def test_insight_only_true_facts(self):
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": _ls(3, price=5)}):
            chatlib.handle_text("http://hub", "search concert", sender="vins")
            chatlib._VOICE_TURN["vins"] = 2  # even tick -> insight path
            r = chatlib.handle_text("http://hub", "search concert", sender="vins")
        self.assertNotIn("free", r)     # nothing is free -> no free claim, ever
        self.assertIn("cheapest $5", r)  # but the true cheapest price is stated

    def test_insight_free_count(self):
        ls = _ls(4)
        for i, l in enumerate(ls):
            l["price"] = 0 if i < 2 else 8
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": ls}):
            chatlib.handle_text("http://hub", "search concert", sender="vfree")
            chatlib._VOICE_TURN["vfree"] = 2  # even tick -> insight path
            r = chatlib.handle_text("http://hub", "search concert", sender="vfree")
        self.assertIn("2 free", r)
        self.assertIn("cheapest $8", r)

    def test_board_line_canonical_first(self):
        r = chatlib.board_line("vb1", 3)
        self.assertTrue(r.startswith("I found 3 matches"), r)
        self.assertIn("open on the board", r)

    def test_board_line_rotates(self):
        a = chatlib.board_line("vb2", 3)
        b = chatlib.board_line("vb2", 3)
        self.assertNotEqual(a, b)
        self.assertIn("open on the board", b)

    def test_board_line_singular(self):
        r = chatlib.board_line("vb3", 1)
        self.assertIn("I found 1 match —", r)

    def test_say_price_guard_drops_invented_price(self):
        act = {"action": "search", "q": "concert", "say": "Tickets from $99!"}
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": _ls(2, price=5)}):
            r = chatlib.brain_search("http://hub", "vg1", act, "concert")
        self.assertNotIn("$99", r)
        self.assertIn("book <n>", r)

    def test_say_price_guard_keeps_grounded_price(self):
        act = {"action": "search", "q": "concert", "say": "From $5 — nice and cheap."}
        with mock.patch.object(chatlib, "_hub_get", return_value={"listings": _ls(2, price=5)}):
            chatlib._LAST_RESULTS.clear()
            r = chatlib.brain_search("http://hub", "vg2", act, "concert")
        # $5 IS a real result price -> say survives (grounded)
        self.assertIn("$5", r)

    def test_say_price_guard_off_switch(self):
        act = {"action": "search", "q": "concert", "say": "Tickets from $99!"}
        os.environ["EVERLIST_SAY_UNGUARDED"] = "1"
        try:
            with mock.patch.object(chatlib, "_hub_get", return_value={"listings": _ls(2, price=5)}):
                r = chatlib.brain_search("http://hub", "vg3", act, "concert")
        finally:
            os.environ.pop("EVERLIST_SAY_UNGUARDED", None)
        self.assertIn("$99", r)


if __name__ == "__main__":
    unittest.main()
