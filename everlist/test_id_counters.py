"""Incident regression 2026-10-19 (prod 502 writes).

Stale id_counters behind real listing ids (even:36 while even-71 existed)
let the mint collide with an existing id; the duplicate rode into RAM and
EVERY persist then crashed on UNIQUE(listings.id) -> 502 on all writes.

Pins both durable layers:
  1. boot reconcile: restored counters rise to real listing-id maxima
  2. mint guard: even a stale counter can never mint an existing id

Run: ./venv/bin/python test_id_counters.py
"""
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
PY = os.path.join(HERE, "venv", "bin", "python")

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL"), name, ("" if cond else str(detail)[:160]))


def free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def wait_ready(port, timeout=20):
    end = time.time() + timeout
    while time.time() < end:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def post(port, path, obj, tok=None):
    h = {"Content-Type": "application/json"}
    if tok:
        h["X-Hub-Token"] = tok
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (port, path),
                                data=json.dumps(obj).encode(), headers=h, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


TMP = tempfile.mkdtemp(prefix="hub-idctr-")
STATE = os.path.join(TMP, "state.json")
PORT = free_port()
env = dict(os.environ, HUB_STATE_FILE=STATE, HUB_STORAGE_MODE="sqlite",
           HUB_STATE_DB=os.path.join(TMP, "hub.db"))
logf = open(os.path.join(TMP, "hub.log"), "w")
proc = subprocess.Popen([PY, os.path.join(HERE, "app.py"), str(PORT)],
                       stdout=logf, stderr=subprocess.STDOUT, env=env)
atexit.register(lambda: proc.terminate())
assert wait_ready(PORT)

st, acc = post(PORT, "/access", {"agent": "idctr-suite", "acts": ["list"]})
tok = acc.get("tokens", {}).get("list", "")


def create(title):
    st, r = post(PORT, "/listings", {
        "vertical": "events", "title": title, "description": "incident regression fixture",
        "date": "2099-01-01", "location": "Vienna", "price": 0, "capacity": 5}, tok)
    return st, r


# 1. two normal creates (also proves the write path works on sqlite mode)
st1, r1 = create("Counter A")
st2, r2 = create("Counter B")
id1, id2 = str(r1.get("id")), str(r2.get("id"))
check("baseline creates OK", st1 == 201 and st2 == 201, (st1, st2))
check("baseline no id dup", id1 != id2, (id1, id2))

# 2. corrupt persisted state EXACTLY like prod: rewind id_counters in the
# sqlite meta snap (sqlite mode keeps no state.json; hub.db is the truth)
proc.terminate(); proc.wait(timeout=10)
import sqlite3
conn = sqlite3.connect(os.path.join(TMP, "hub.db"))
snap = json.loads(conn.execute("select v from meta where k='snap'").fetchone()[0])
snap["id_counters"] = {k: 0 for k in (snap.get("id_counters") or {})}
conn.execute("BEGIN IMMEDIATE")
conn.execute("INSERT OR REPLACE INTO meta(k, v) VALUES('snap', ?)", (json.dumps(snap),))
conn.commit()
conn.close()
check("corruption injected: counters rewound to 0", True)

# 3. restart on the corrupted state
proc = subprocess.Popen([PY, os.path.join(HERE, "app.py"), str(PORT)],
                       stdout=logf, stderr=subprocess.STDOUT, env=env)
assert wait_ready(PORT)
st, acc = post(PORT, "/access", {"agent": "idctr-suite2", "acts": ["list"]})
tok = acc.get("tokens", {}).get("list", "")

# 4. creates after the rewind must never collide (mint guard + boot reconcile)
st3, r3 = create("Counter C")
st4, r4 = create("Counter D")
id3, id4 = str(r3.get("id")), str(r4.get("id"))
check("post-corruption creates OK (no 5xx)", st3 == 201 and st4 == 201, (st3, st4))
check("post-corruption ids unique",
      len({id1, id2, id3, id4}) == 4, (id1, id2, id3, id4))

# 5. restart again; verify the committed snap is duplicate-free and counters >= maxima
proc.terminate(); proc.wait(timeout=10)
import sqlite3
conn = sqlite3.connect(os.path.join(TMP, "hub.db"))
row = conn.execute("select v from meta where k='snap'").fetchone()
conn.close()
snap2 = json.loads(row[0])
ids = [str(l.get("id")) for l in (snap2.get("listings") or [])]
from collections import Counter
c = Counter(ids)
check("committed snap has zero duplicate ids", not [k for k, n in c.items() if n > 1])
maxes = {}
for i in ids:
    if "-" in i and i.rsplit("-", 1)[1].isdigit():
        p = i.rsplit("-", 1)[0]
        maxes[p] = max(maxes.get(p, 0), int(i.rsplit("-", 1)[1]))
counters = snap2.get("id_counters") or {}
check("committed counters >= real maxima",
      all(int(counters.get(p, 0)) >= m for p, m in maxes.items()),
      (counters, maxes))

n_pass = sum(1 for _, ok in RESULTS if ok)
n_fail = len(RESULTS) - n_pass
print("\nid-counter incident suite: %d passed, %d failed" % (n_pass, n_fail))
print("IDCTR_ALL_PASSED" if not n_fail else "IDCTR_FAILURES")
sys.exit(1 if n_fail else 0)
