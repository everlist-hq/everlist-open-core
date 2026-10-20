#!/usr/bin/env python3
'''W3.4: organizer earnings mirror + revenue-floor proof (hub).

Covered:
- GET /organizer/earnings without token -> 401; book token -> 403
- paid HELD booking + owner confirm (RELEASED) -> earnings recorded
- second settlement accumulates; WAIVED (payout 0) never earns
- isolation: second organizer sees zeros
- proof met=true below actuals / met=false above / exact boundary passes
- HONESTY: proof response never carries actual totals
- vacuous walls: min_settlements=0 -> 400; min_volume=0 -> 400
- earnings survive a hub restart (persistence)

Not covered (needs testnet settlement mocking): DIRECT-at-booking hook
(same code shape as the confirm hook; WAIVED no-op asserted instead).

Run: python test_w34_earnings_hub.py
'''
import atexit
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), name, ('' if cond else detail))


def free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0)); p = s.getsockname()[1]; s.close(); return p


def _kill(p):
    if p:
        p.terminate()
        try:
            p.wait(timeout=5)
        except Exception:
            p.kill()


_ACTIVE = []
atexit.register(lambda: [_kill(p) for p in _ACTIVE])


def wait_ready(port, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _req(base, method, path, body=None, token=None):
    headers = {}
    data = None
    if body is not None:
        headers['Content-Type'] = 'application/json'
        data = json.dumps(body).encode()
    if token:
        headers['X-Hub-Token'] = token
    rq = urllib.request.Request(base + path, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(rq, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except Exception:
        return -1, {}


def post(base, path, body, token=None):
    return _req(base, 'POST', path, body, token)


def get(base, path, token=None):
    return _req(base, 'GET', path, None, token)


def spawn(state_file):
    port = free_port()
    logdir = os.path.dirname(state_file)
    env = {**os.environ, 'HUB_STATE_FILE': state_file,
           'HUB_POW_SIGNUP_BITS': '8', 'PYTHONUNBUFFERED': '1'}
    logf = open(os.path.join(logdir, 'hub-earnings.log'), 'a')
    p = subprocess.Popen([sys.executable, os.path.join(HERE, 'app.py'), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), 'hub did not start'
    return 'http://127.0.0.1:%d' % port, p


def tokens(base, agent, acts):
    _, r = post(base, '/access', {'agent': agent, 'acts': acts})
    return r.get('tokens', {})


TMP = tempfile.mkdtemp(prefix='hub-earnings-')
STATE = os.path.join(TMP, 'state.json')
HUB, P1 = spawn(STATE)
LT = tokens(HUB, 'earn-merchant', ['list'])['list']
LT2 = tokens(HUB, 'earn-merchant-2', ['list'])['list']
BT = tokens(HUB, 'earn-buyer', ['book'])['book']


def mk(price):
    body = {'vertical': 'events', 'title': 'W3.4 earnings %s %s' % (time.time(), price),
            'price': price, 'location': 'Vienna', 'capacity': 10, 'date': '2026-12-01'}
    st, r = post(HUB, '/listings', body, token=LT)
    assert st == 201, 'seed failed: %s' % r
    return r['id'], r.get('manage_code', '')


def book(lid):
    return post(HUB, '/book', {'listing_id': lid, 'attendee': 'W3.4 Buyer',
                               'human_verified': True}, token=BT)


def confirm(bid, manage_code):
    return post(HUB, '/book/%s/confirm' % bid, {'manage_code': manage_code})


# --- T1/T2: walls -----------------------------------------------------------
st, r = get(HUB, '/organizer/earnings')
check('T1 no token -> 401', st == 401, 'got %s' % st)
st, r = get(HUB, '/organizer/earnings', token=BT)
check('T2 book token -> 403 (owner-only)', st == 403, 'got %s' % st)
st, r = post(HUB, '/organizer/earnings-proof', {'min_volume': 1, 'min_settlements': 1})
check('T2b proof without token -> 401', st == 401, 'got %s' % st)

# --- T3: empty view is honest zeros ----------------------------------------
st, r = get(HUB, '/organizer/earnings', token=LT)
check('T3 fresh organizer sees zeros',
      st == 200 and r.get('settledCount') == 0 and r.get('totalVolume') == 0,
      '%s: %s' % (st, r))

# --- T4: paid HELD -> confirm -> recorded ----------------------------------
LID1, MC1 = mk(100)
st, r = book(LID1)
check('T4 booking created (HELD)', st == 201 and r.get('escrow') == 'HELD', 'got %s: %s' % (st, r))
BID1 = r.get('id', '')
PAYOUT1 = float(r.get('owner_payout', 0))
st, r = confirm(BID1, MC1)
check('T4 confirm -> RELEASED', st == 200 and r.get('escrow') == 'RELEASED', 'got %s: %s' % (st, r))
st, r = get(HUB, '/organizer/earnings', token=LT)
check('T4 earnings recorded (1 settlement, payout exact)',
      st == 200 and r.get('settledCount') == 1 and abs(r.get('totalVolume', 0) - PAYOUT1) < 0.01,
      '%s: %s vs payout %s' % (st, r, PAYOUT1))

# --- T5: WAIVED never earns -------------------------------------------------
LID2, MC2 = mk(0)
st, r = book(LID2)
check('T5 free booking created (WAIVED)', st == 201 and r.get('escrow') == 'WAIVED', 'got %s: %s' % (st, r))
BID2 = r.get('id', '')
st, r = confirm(BID2, MC2)
check('T5 free confirm ok', st == 200, 'got %s: %s' % (st, r))
st, r = get(HUB, '/organizer/earnings', token=LT)
check('T5 WAIVED booking did NOT earn', r.get('settledCount') == 1, 'count moved: %s' % r)

# --- T6: second settlement accumulates -------------------------------------
LID3, MC3 = mk(50)
st, r = book(LID3)
BID3 = r.get('id', '')
PAYOUT3 = float(r.get('owner_payout', 0))
st, r = confirm(BID3, MC3)
check('T6 second confirm ok', st == 200, 'got %s: %s' % (st, r))
st, r = get(HUB, '/organizer/earnings', token=LT)
check('T6 earnings accumulated',
      r.get('settledCount') == 2 and abs(r.get('totalVolume', 0) - (PAYOUT1 + PAYOUT3)) < 0.01,
      '%s vs %s+%s' % (r, PAYOUT1, PAYOUT3))
TOTAL = round(PAYOUT1 + PAYOUT3, 2)

# --- T7: isolation ----------------------------------------------------------
st, r = get(HUB, '/organizer/earnings', token=LT2)
check('T7 second organizer isolated (zeros)',
      st == 200 and r.get('settledCount') == 0 and r.get('totalVolume') == 0, '%s' % r)

# --- T8: proof pass/fail + honesty -----------------------------------------
st, r = post(HUB, '/organizer/earnings-proof',
             {'min_volume': TOTAL - 1, 'min_settlements': 2}, token=LT)
check('T8 proof met=true below actuals', st == 200 and r.get('met') is True, '%s: %s' % (st, r))
st, r = post(HUB, '/organizer/earnings-proof',
             {'min_volume': TOTAL + 1, 'min_settlements': 1}, token=LT)
check('T8 proof met=false above actuals', st == 200 and r.get('met') is False, '%s: %s' % (st, r))
st, r = post(HUB, '/organizer/earnings-proof',
             {'min_volume': TOTAL, 'min_settlements': 2}, token=LT)
check('T8 boundary: exact floor passes', st == 200 and r.get('met') is True, '%s: %s' % (st, r))
st, r = post(HUB, '/organizer/earnings-proof', {'min_volume': 1, 'min_settlements': 1}, token=LT)
body_str = json.dumps(r)
check('T8 HONESTY: proof response carries no actual totals',
      str(TOTAL) not in body_str and 'totalVolume' not in body_str and 'settledCount' not in body_str,
      'leaked: %s' % body_str)

# --- T9: vacuous walls ------------------------------------------------------
st, r = post(HUB, '/organizer/earnings-proof', {'min_volume': 10, 'min_settlements': 0}, token=LT)
check('T9 min_settlements=0 -> 400 (vacuous)', st == 400, 'got %s' % st)
st, r = post(HUB, '/organizer/earnings-proof', {'min_volume': 0, 'min_settlements': 1}, token=LT)
check('T9b min_volume=0 -> 400', st == 400, 'got %s' % st)

# --- T10: persistence across restart ---------------------------------------
_kill(P1)
HUB, P2 = spawn(STATE)
st, r = get(HUB, '/organizer/earnings', token=LT)
check('T10 earnings survive restart',
      st == 200 and r.get('settledCount') == 2 and abs(r.get('totalVolume', 0) - TOTAL) < 0.01,
      '%s: %s' % (st, r))

# --- summary ----------------------------------------------------------------
failed = [n for n, ok in RESULTS if not ok]
print()
if failed:
    print('FAILURES: %s  (%d/%d passed)' % (', '.join(failed), len(RESULTS) - len(failed), len(RESULTS)))
else:
    print('ALL PASSED  (%d/%d)' % (len(RESULTS), len(RESULTS)))
sys.exit(1 if failed else 0)
