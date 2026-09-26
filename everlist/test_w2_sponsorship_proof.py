"""W2: abuse-resistant sponsorship + verify-without-trust proof endpoint.

Covers the owner-approved Wave 2 items:
  1. sponsorship.py rules: per-org window limit, pool budget cap, stake
     threshold, window slide - pure-function tests (explicit time).
  2. GET /escrow/{id}/proof - live hub subprocess re-reads chain state from
     a stage-advancing GraphQL-v4 fixture indexer (M6 shape); honest
     fail-closed errors; booking linkage pseudonymous.
  3. GET /sponsorship/stats - honest budget state.
  4. Sponsor gate wired in POST /book (SPONSOR_RELAY env; unit-level via
     sponsorship rules, wiring asserted on app source).
Run: python test_w2_sponsorship_proof.py
"""
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import sponsorship  # noqa: E402

RESULTS = []

def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), name, ('' if cond else detail))

# --- 1. sponsorship rules (pure, explicit time) ---
sponsorship.configure(enabled=True, window=100, per_org=2, pool_cap=3, min_funded=1)
ok, why = sponsorship.check('orgA', 1, now=1);   check('sponsor grant 1st', ok, why)
ok, why = sponsorship.check('orgA', 1, now=2);   check('sponsor grant 2nd', ok, why)
ok, why = sponsorship.check('orgA', 1, now=3)
check('per-org window limit refuses', not ok and 'limit reached' in why, why)
ok, why = sponsorship.check('orgB', 1, now=4);   check('pool accepts 3rd op', ok, why)
ok, why = sponsorship.check('orgC', 1, now=5)
check('pool cap refuses 4th op', not ok and 'budget exhausted' in why, why)
ok, why = sponsorship.check('orgD', 0, now=6)
check('stake threshold refuses unfunded', not ok and 'stake' in why, why)
ok, why = sponsorship.check('orgA', 1, now=200)
check('window slide re-allows', ok, why)
st = sponsorship.stats(now=200)
check('stats honest counters', st['enabled'] is True and st['granted'] >= 4, str(st))
sponsorship.configure(enabled=False)
ok, why = sponsorship.check('orgX', 0, now=300)
check('disabled mode allows (sponsor role not in play)', ok, why)
sponsorship.configure(enabled=True)

# --- 2. live hub + stage-advancing fixture indexer ---
FIX = json.load(open(os.path.join(HERE, 'fixtures', 'escrow-fixture.json')))

def state_hex(stage):
    doc = {'escrows': {'1': {
        'state': FIX[stage]['state'], 'amount': FIX[stage]['amount'],
        'booking_ref': FIX[stage]['booking_ref'], 'deadline': FIX[stage]['deadline']}}}
    return json.dumps(doc).encode('utf-8').hex()

def call_node(stage):
    return {'__typename': 'ContractCall', 'entryPoint': FIX[stage]['entry_point'],
            'state': state_hex(stage), 'transaction': {'id': FIX[stage]['tx']}}

class IH(BaseHTTPRequestHandler):
    stage = ['held']
    def log_message(self, *a): pass
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); self.rfile.read(n)
        body = json.dumps({'data': {'contractActions': {'edges': [
            {'node': call_node(IH.stage[0])}]}}}).encode()
        self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body))); self.end_headers()
        self.wfile.write(body)

s = socket.socket(); s.bind(('127.0.0.1', 0)); IPORT = s.getsockname()[1]; s.close()
iser = ThreadingHTTPServer(('127.0.0.1', IPORT), IH)
threading.Thread(target=iser.serve_forever, daemon=True).start()

s = socket.socket(); s.bind(('127.0.0.1', 0)); HPORT = s.getsockname()[1]; s.close()
TMP = tempfile.mkdtemp(prefix='hub-w2-')
env = dict(os.environ,
           HUB_DATA_DIR=TMP,
           HUB_INDEXER_URL='http://127.0.0.1:%d' % IPORT,
           HUB_ESCROW_CONTRACT='0xtestcontract',
           HUB_SPONSOR_RELAY='1',
           HUB_SPONSOR_WINDOW_SECS='100', HUB_SPONSOR_PER_ORG='2',
           HUB_SPONSOR_POOL_CAP='3', HUB_SPONSOR_MIN_FUNDED='1')
proc = subprocess.Popen([sys.executable, os.path.join(HERE, 'app.py'), str(HPORT)], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
BASE = 'http://127.0.0.1:%d' % HPORT

def get(path):
    try:
        with urllib.request.urlopen(BASE + path, timeout=10) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')
    except Exception as e:
        return 0, {'error': repr(e)}

try:
    # wait for hub
    up = False
    for _ in range(100):
        try:
            c, _b = get('/sponsorship/stats')
            if c in (200, 429):  # any HTTP answer proves liveness
                up = True; break
        except Exception:
            pass
        time.sleep(0.3)
    if not up:
        import time as _t; _t.sleep(1.0)
        if proc.poll() is not None:
            print('HUB DIED rc=%s' % proc.returncode)
            print((proc.stderr.read() or b'').decode()[-2000:])
    check('hub subprocess up', up)

    c, b = get('/escrow/1/proof?contract=0xtestcontract')
    check('proof 200', c == 200, str(b)[:120])
    check('proof says HELD from indexer', b.get('state_name') == 'HELD', str(b)[:160])
    check('proof trust_model present', 'verify-without-trust' in b.get('trust_model', ''), str(b)[:200])
    check('proof sources honest', 'single indexer' in b.get('sources', ''), str(b.get('sources')))
    check('proof leaks no booking details', 'booked_by' not in b and 'attendee' not in b)

    IH.stage[0] = 'released'
    c, b = get('/escrow/1/proof')
    check('proof tracks chain state advance', c == 200 and b.get('state_name') == 'RELEASED', str(b)[:160])

    c, b = get('/escrow/999999/proof')
    check('unknown escrow honest (not 200-fake)', c in (404, 503), '%s %s' % (c, str(b)[:120]))

    c, b = get('/escrow/notanid/proof')
    check('bad id rejected 400', c == 400, str(b)[:120])

    c, b = get('/sponsorship/stats')
    check('sponsorship stats 200 + honest', c == 200 and b.get('enabled') is True
          and b.get('per_org_limit') == 2 and b.get('pool_cap') == 3, str(b)[:160])
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()
    iser.shutdown()
    shutil.rmtree(TMP, ignore_errors=True)

# --- 3. sponsor gate wiring assertions (source-level, the E2E booking flow
#        needs full auth; the gate call itself is unit-covered above) ---
src = open(os.path.join(HERE, 'app.py')).read()
check('POST /book wires sponsorship gate', '_sp.check(listing.get("owner"' in src
      and 'sponsored fee relay refused' in src)
check('gate refusal is honest 402', 'self._json(402, {"error": "sponsored fee relay refused"' in src)
check('sponsor relay default OFF (M18 activates real payment)',
      'HUB_SPONSOR_RELAY", "") == "1"' in src)

print()
print('W2: %d/%d checks passed' % (sum(1 for _, ok in RESULTS if ok), len(RESULTS)))
if all(ok for _, ok in RESULTS):
    print('ALL PASSED')
else:
    sys.exit(1)
