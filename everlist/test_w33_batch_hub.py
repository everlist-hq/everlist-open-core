#!/usr/bin/env python3
'''W3.3 usage surface: organizer batch settle (hub).

Covered:
- POST /organizer/batch-settle without token -> 401; book token -> 403
- paid HELD booking batch -> RELEASED, earnings recorded, payout reported
- WAIVED (free) booking settles with no money movement
- second batch call -> settled:0 (honest empty result)
- organizer isolation: another organizer's token settles nothing of mine
- disputed booking is NOT touched by batch settle
- OpenAPI advertises /organizer/batch-settle (paths + ops)

Run: python test_w33_batch_hub.py
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
    env = {**os.environ, 'HUB_STATE_FILE': state_file,
           'HUB_POW_SIGNUP_BITS': '8', 'PYTHONUNBUFFERED': '1'}
    logf = open(os.path.join(os.path.dirname(state_file), 'hub-batch.log'), 'a')
    p = subprocess.Popen([sys.executable, os.path.join(HERE, 'app.py'), str(port)],
                         stdout=logf, stderr=subprocess.STDOUT, env=env)
    _ACTIVE.append(p)
    assert wait_ready(port), 'hub did not start'
    return 'http://127.0.0.1:%d' % port, p


def tokens(base, agent, acts):
    _, r = post(base, '/access', {'agent': agent, 'acts': acts})
    return r.get('tokens', {})


TMP = tempfile.mkdtemp(prefix='hub-batch-')
STATE = os.path.join(TMP, 'state.json')
HUB, P1 = spawn(STATE)
LT = tokens(HUB, 'batch-merchant', ['list'])['list']
LT2 = tokens(HUB, 'batch-merchant-2', ['list'])['list']
BT = tokens(HUB, 'batch-buyer', ['book'])['book']


def mk(price):
    body = {'vertical': 'events', 'title': 'W3.3 batch %s %s' % (time.time(), price),
            'price': price, 'location': 'Vienna', 'capacity': 10, 'date': '2026-12-01'}
    st, r = post(HUB, '/listings', body, token=LT)
    assert st == 201, 'seed failed: %s' % r
    return r['id']


def book(lid):
    return post(HUB, '/book', {'listing_id': lid, 'attendee': 'W3.3 Buyer',
                               'human_verified': True}, token=BT)


# --- walls ------------------------------------------------------------------
st, r = post(HUB, '/organizer/batch-settle', {})
check('T1 no token -> 401', st == 401, 'got %s' % st)

st, r = post(HUB, '/organizer/batch-settle', {}, token=BT)
check('T2 book token -> 403', st == 403, 'got %s' % st)

# --- happy path: paid HELD booking settles in the batch -----------------------
L1 = mk(25)
st, b1 = book(L1)
assert st == 201, b1

st, r = post(HUB, '/organizer/batch-settle', {}, token=LT)
ok1 = [x for x in r.get('results', []) if x.get('id') == b1.get('id')]
check('T3 paid HELD settles -> RELEASED + payout reported',
      st == 200 and r.get('settled', 0) >= 1 and ok1 and ok1[0].get('ok')
      and ok1[0].get('escrow') == 'RELEASED' and float(ok1[0].get('owner_received', 0)) > 0,
      'got %s %s' % (st, r))

# earnings hook fired for the settled payout (W3.4 integration)
st, ev = get(HUB, '/organizer/earnings', token=LT)
check('T3b earnings recorded by batch settle',
      st == 200 and int(ev.get('settledCount', 0)) >= 1, 'got %s %s' % (st, ev))

# --- WAIVED (free) listing settles with no money -----------------------------
LF = mk(0)
st, bf = book(LF)
assert st == 201, bf
st, r = post(HUB, '/organizer/batch-settle', {}, token=LT)
fw = [x for x in r.get('results', []) if x.get('id') == bf.get('id')]
check('T4 WAIVED settles free (no payout)',
      st == 200 and fw and fw[0].get('ok') and float(fw[0].get('owner_received', 0)) == 0,
      'got %s %s' % (st, r))

# --- honest empty: everything already settled --------------------------------
st, r = post(HUB, '/organizer/batch-settle', {}, token=LT)
check('T5 second batch -> settled:0 (honest empty)',
      st == 200 and r.get('settled', -1) == 0, 'got %s %s' % (st, r))

# --- organizer isolation -----------------------------------------------------
L3 = mk(10)
st, b3 = book(L3)
assert st == 201, b3
st, r = post(HUB, '/organizer/batch-settle', {}, token=LT2)
ids2 = {x.get('id') for x in r.get('results', [])}
check('T6 other organizer settles nothing of mine',
      st == 200 and b3.get('id') not in ids2, 'got %s' % ids2)

# --- disputed booking untouched ----------------------------------------------
L4 = mk(15)
st, b4 = book(L4)
assert st == 201, b4
# buyer opens a dispute (freeze)
st, dr = post(HUB, '/book/%s/dispute' % b4['id'], {}, token=BT)
check('T7a dispute opened on HELD booking', st in (200, 409), 'got %s %s' % (st, dr))
st, r = post(HUB, '/organizer/batch-settle', {}, token=LT)
got = [x for x in r.get('results', []) if x.get('id') == b4['id']]
check('T7b disputed booking NOT in settle results (DISPUTED not settleable)',
      not got, 'got %s' % got)

# --- OpenAPI advertises the route -------------------------------------------
st, api = get(HUB, '/openapi.json')
paths = (api.get('paths') or {}) if isinstance(api, dict) else {}
check('T8 OpenAPI lists /organizer/batch-settle', '/organizer/batch-settle' in paths,
      'got %s' % (list(paths)[-5:] if isinstance(paths, dict) else api))

# --- summary -----------------------------------------------------------------
n_pass = sum(1 for _, okk in RESULTS if okk)
print('')
print('=== w33 batch hub: %d/%d passed ===' % (n_pass, len(RESULTS)))
if n_pass != len(RESULTS):
    sys.exit(1)
print('W33_BATCH_HUB_ALL_PASSED')
