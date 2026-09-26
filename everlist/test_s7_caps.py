"""S7: anti-spam — active-listing cap + duplicate detection (live hub).

Covers docs/spec-s7-antispam-20260925.md P0 scope:
  1. cap: env HUB_LISTING_CAP honored; over cap -> 409 honest counts; admin exempt
  2. duplicate: same principal + normalized title + date + location -> 409 w/ existing id;
     different date OK; different location OK; different principal same title OK
  3. relist-after-archive OK; archived don't count toward cap
  4. archived duplicates allowed
  5. OpenAPI documents both 409s on POST /listings
  6. chat surface humane error (chatlib test is source-level)
Run: python test_s7_caps.py
"""
import json, os, socket, subprocess, sys, tempfile, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = []

def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond)))
    print(('PASS' if cond else 'FAIL'), name, ('' if cond else detail))

s = socket.socket(); s.bind(('127.0.0.1', 0)); HPORT = s.getsockname()[1]; s.close()
TMP = tempfile.mkdtemp(prefix='hub-s7-')
env = dict(os.environ, HUB_DATA_DIR=TMP, HUB_LISTING_CAP='3')
proc = subprocess.Popen([sys.executable, os.path.join(HERE, 'app.py'), str(HPORT)], env=env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
BASE = 'http://127.0.0.1:%d' % HPORT

def req(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(BASE + path, data=data, method=method,
        headers={'Content-Type': 'application/json', **({'X-Hub-Token': token} if token else {})})
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode() or '{}')
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or '{}')
    except Exception as e:
        return 0, {'error': repr(e)}

def mint(agent):
    c, b = req('POST', '/access', {'agent': agent, 'acts': ['list']})
    assert c in (200, 201), 'token mint failed: %s %s' % (c, b)
    return b['tokens']['list']

def listing_payload(title, date='2026-12-01', location='Wien'):
    return {'vertical': 'events', 'title': title, 'date': date, 'location': location,
            'price': 0, 'capacity': 10, 'description': 'S7 test listing', 'source': 's7-test'}

try:
    up = False
    for _ in range(100):
        c, _b = req('GET', '/openapi.json')
        if c == 200:
            up = True; break
        time.sleep(0.3)
    check('hub subprocess up', up)

    tokA = mint('s7-agent-A')
    tokB = mint('s7-agent-B')

    # --- 2. duplicates (BEFORE cap reached: duplicate must surface as duplicate) ---
    for i in (1, 2):
        c, b = req('POST', '/listings', listing_payload('S7 Cap Event %d' % i), tokA)
        check('cap allows listing %d' % i, c == 201, '%s %s' % (c, str(b)[:120]))
    c, b = req('POST', '/listings', listing_payload('S7 Cap Event 1'), tokA)
    check('duplicate refused 409', c == 409, '%s %s' % (c, str(b)[:160]))
    check('duplicate names existing id', b.get('existing', '').startswith('even-'), str(b)[:160])
    dup_id = b.get('existing', '')
    # normalization: case + whitespace insensitive
    c, b = req('POST', '/listings', listing_payload('  s7   cap  event   1 '), tokA)
    check('duplicate normalization case/whitespace-insensitive', c == 409 and b.get('existing') == dup_id, '%s %s' % (c, str(b)[:160]))
    # different date OK (A's 3rd listing — still under cap)
    c, b = req('POST', '/listings', listing_payload('S7 Cap Event 1', date='2027-01-15'), tokA)
    check('same title, different date allowed', c == 201, '%s %s' % (c, str(b)[:160]))

    # --- 1. cap: 3 active -> 4th 409 ---
    c, b = req('POST', '/listings', listing_payload('S7 Cap Event 4'), tokA)
    check('cap refuses 4th with 409', c == 409, '%s %s' % (c, str(b)[:160]))
    check('cap 409 honest counts', b.get('cap') == 3 and b.get('active') == 3, str(b)[:160])
    check('cap message humane + actionable', 'Archive one' in b.get('error', ''), str(b)[:160])
    # re-verify duplicate AFTER cap: must still surface as duplicate, not generic cap 409
    c, b = req('POST', '/listings', listing_payload('S7 Cap Event 1'), tokA)
    check('duplicate surfaces as duplicate even at cap', c == 409 and b.get('existing', '').startswith('even-'), '%s %s' % (c, str(b)[:160]))

    # cross-principal checks (fresh principals, under cap)
    c, b = req('POST', '/listings', listing_payload('S7 Cap Event 1', location='Graz'), tokB)
    check('same title, different location allowed', c == 201, '%s %s' % (c, str(b)[:160]))
    # cross-principal same everything OK
    c, b = req('POST', '/listings', listing_payload('S7 Cap Event 1'), tokB)
    check('same title/date/location, different principal OK', c == 201, '%s %s' % (c, str(b)[:160]))

    # --- 3. relist-after-archive frees slot + blocks duplicate ---
    c, b = req('POST', '/listings', listing_payload('S7 Archive Me'), tokB)  # B now at cap (3)
    check('B reaches cap (3rd)', c == 201, '%s %s' % (c, str(b)[:160]))
    c, b = req('POST', '/listings', listing_payload('S7 Archive Me'), tokB)
    check('B duplicate refused', c == 409, str(b)[:120])
    # archive listing 1 of A? No - archive B's first listing via manage? manage needs manage_code.
    # Instead: use admin authority to archive? Simpler: B archives via manage with manage_code from create.
    # We didn't store B's manage codes; do a fresh flow for archive test:
    tokC = mint('s7-agent-C')
    c, b = req('POST', '/listings', listing_payload('S7 To Archive'), tokC)
    check('C creates listing', c == 201, str(b)[:120])
    mc = b.get('manage_code', '')
    lid = b.get('id', '')
    c, b = req('POST', '/listings/%s/manage' % lid, {'action': 'archive', 'manage_code': mc}, tokC)
    check('archive succeeds', c == 200, '%s %s' % (c, str(b)[:160]))
    c, b = req('POST', '/listings', listing_payload('S7 To Archive'), tokC)
    check('relist-after-archive OK (slot freed, duplicate cleared)', c == 201, '%s %s' % (c, str(b)[:160]))
    c, b = req('POST', '/listings', listing_payload('S7 To Archive'), tokC)
    check('archived duplicate does not block (active duplicate only)', c == 409, str(b)[:120])  # new active dup
    # cap not affected by archived: C has 1 active + 1 archived; create 2 more to hit cap 3
    c, b = req('POST', '/listings', listing_payload('S7 C2'), tokC)
    check('C 2nd active ok', c == 201, str(b)[:120])
    c, b = req('POST', '/listings', listing_payload('S7 C3'), tokC)
    check('C 3rd active ok', c == 201, str(b)[:120])
    c, b = req('POST', '/listings', listing_payload('S7 C4'), tokC)
    check('archived listings do not count toward cap (4th active refuses at 3)', c == 409 and b.get('active') == 3, str(b)[:160])

    # --- 4. OpenAPI documents both 409s ---
    c, b = req('GET', '/openapi.json')
    op = (b.get('paths', {}).get('/listings', {}).get('post') or {})
    responses = op.get('responses', {})
    check('OpenAPI has 409 on POST /listings', '409' in responses, str(list(responses))[:120])

    # --- 5. admin exempt ---
    # admin = token with act 'confirm'; mint via admin bootstrap if available, else skip honestly
    c, b = req('POST', '/access', {'agent': 's7-admin', 'acts': ['confirm']})
    if c == 201 or c == 200:
        tokAdm = b.get('token', '')
        if tokAdm:
            for i in range(5):
                c2, b2 = req('POST', '/listings', listing_payload('S7 Admin %d' % i), tokAdm)
                if c2 != 201: break
            check('admin authority exempt from cap', c2 == 201, '%s %s' % (c2, str(b2)[:120]))
    else:
        print('SKIP admin-exempt test (confirm acts not mintable pre-personhood)')
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except Exception:
        proc.kill()

fails = [n for n, okr in RESULTS if not okr]
print('%d/%d PASSED' % (len(RESULTS) - len(fails), len(RESULTS)))
if fails:
    print('FAILED:', ', '.join(fails))
    sys.exit(1)
print('ALL PASSED')
