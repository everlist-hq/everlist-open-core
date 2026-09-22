#!/usr/bin/env python3
'''MED-fix regression: facilitator settlement must NOT hold the global LOCK.

If the settle HTTP round-trip runs under the hub's LOCK again, a concurrent
/search stalls for the full facilitator latency (measured 7s with an 8s
facilitator - chaos run 2026-09-20). This test fails fast on regression:

  L1  paid request settles fine (SETTLED) against a slow (2s) facilitator
  L2  concurrent /search during settle completes in < 1s (LOCK not held)
  L3  settled record is durable on disk after restart (D4 evidence)

Run with the experiment venv.
'''
import base64
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from eth_account import Account

HERE = os.path.dirname(os.path.abspath(__file__))
PY = os.path.join(HERE, 'venv', 'bin', 'python')
STATE = os.path.join('/tmp', f'hub_lockfix_{uuid.uuid4().hex[:8]}.json')
RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL') + f' | {name}' + (f' | {detail}' if detail and not cond else ''))


class SlowFacil:
    def __init__(self, delay):
        self.delay = delay
        self.port = self._free()
        self.calls = 0
        srv = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                ln = int(self.headers.get('Content-Length', 0))
                json.loads(self.rfile.read(ln) or b'{}')
                if not self.path.endswith('/settle'):
                    return self._send(404, {'error': 'not found'})
                srv.calls += 1
                time.sleep(srv.delay)
                tx = '0x' + hashlib.sha256(str(srv.delay).encode()).hexdigest()
                self._send(200, {'success': True, 'transaction': tx, 'network': 'base-sepolia'})

            def _send(self, code, obj):
                data = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        self.httpd = ThreadingHTTPServer(('127.0.0.1', self.port), H)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @staticmethod
    def _free():
        s = socket.socket()
        s.bind(('127.0.0.1', 0))
        p = s.getsockname()[1]
        s.close()
        return p


def _free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


def start_hub(facil_base):
    env = {**os.environ, 'HUB_PAY_MODE': 'testnet', 'HUB_SETTLE_MODE': 'auto',
           'HUB_STATE_FILE': STATE, 'HUB_FACILITATOR_URL': facil_base}
    port = _free_port()
    p = subprocess.Popen([PY, os.path.join(HERE, 'app.py'), str(port)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT, env=env)
    end = time.time() + 15
    while time.time() < end:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.5):
                return p, port
        except OSError:
            time.sleep(0.2)
    raise RuntimeError('hub not ready')


def req(port, method, path, body=None, headers=None):
    r = urllib.request.Request(f'http://127.0.0.1:{port}' + path, method=method,
                               data=json.dumps(body).encode() if body is not None else None,
                               headers={'Content-Type': 'application/json', **(headers or {})})
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def build_payment(terms, acct):
    acc = terms['accepts'][0]
    now = int(time.time())
    auth = {'from': acct.address, 'to': acc['payTo'], 'value': int(acc['maxAmountRequired']),
            'validAfter': now - 60, 'validBefore': now + 600,
            'nonce': '0x' + uuid.uuid4().hex + uuid.uuid4().hex[:32]}
    domain = {'name': 'USD Coin', 'version': '2', 'chainId': 84532, 'verifyingContract': acc['asset']}
    types = {'TransferWithAuthorization': [
        {'name': 'from', 'type': 'address'}, {'name': 'to', 'type': 'address'},
        {'name': 'value', 'type': 'uint256'}, {'name': 'validAfter', 'type': 'uint256'},
        {'name': 'validBefore', 'type': 'uint256'}, {'name': 'nonce', 'type': 'bytes32'}]}
    signed = acct.sign_typed_data(domain_data=domain, message_types=types, message_data=auth)
    payload = {'scheme': 'exact', 'network': 'base-sepolia', 'x402Version': 1,
               'payload': {'authorization': auth, 'signature': signed.signature.hex()}}
    return base64.b64encode(json.dumps(payload).encode()).decode()


def main():
    if os.path.exists(STATE):
        os.remove(STATE)
    stub = SlowFacil(2.0)  # 2s facilitator latency
    hub, port = start_hub(f'http://127.0.0.1:{stub.port}/slow')
    try:
        st, terms = req(port, 'GET', '/premium/events')
        pay = build_payment(terms, Account.from_key(os.urandom(32)))

        result = {}

        def pay_bg():
            st, body = req(port, 'GET', '/premium/events', None, {'X-PAYMENT': pay})
            result['st'] = st
            result['settle'] = body.get('payment', {}).get('settlement', {})

        t = threading.Thread(target=pay_bg)
        t.start()
        time.sleep(0.5)  # request is now inside the facilitator call

        t0 = time.perf_counter()
        st, _ = req(port, 'GET', '/search?q=x')
        search_dur = time.perf_counter() - t0
        t.join()

        check('L1: paid request settles with tx',
              result.get('st') == 200 and result['settle'].get('status') == 'SETTLED',
              str(result))
        check('L2: concurrent /search NOT blocked by settle (< 1s)',
              st == 200 and search_dur < 1.0, f'st={st} dur={search_dur:.2f}s')

        # L3: D4 evidence - settlement record durable on disk after restart
        hub.send_signal(signal.SIGTERM)
        hub.wait(timeout=10)
        snap = json.load(open(STATE))
        recs = snap.get('settlements', {})
        ours = [r for r in recs.values() if r.get('status') == 'settled']
        check('L3: settled record durable on disk (D4 evidence)',
              bool(ours) and all(r.get('tx', '').startswith('0x') for r in ours),
              f'records={list(recs.values())}')
    finally:
        try:
            hub.send_signal(signal.SIGTERM)
            hub.wait(timeout=10)
        except Exception:
            pass
        stub.httpd.shutdown()
        if os.path.exists(STATE):
            os.remove(STATE)

    failed = [n for n, ok in RESULTS if not ok]
    print(f'\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed')
    if failed:
        print('FAILED:', failed)
        sys.exit(1)
    print('LOCKFIX_ALL_PASSED')


if __name__ == '__main__':
    main()
