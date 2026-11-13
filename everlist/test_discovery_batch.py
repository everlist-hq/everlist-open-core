'''Discovery batch 2026-11-12: llms.txt + AI-crawler robots + IndexNow key face.

Pins (in-process webchat against an isolated hub state, like test_webchat):
  - /robots.txt: allow-all + explicit AI-crawler groups + Sitemap line
  - /llms.txt: llmstxt.org shape (H1, blockquote, sections) with PUBLIC
    base links only (never loopback hosts)
  - /.well-known/<key>.txt: IndexNow proof-of-domain file, exact key match
  - hermetic law: no outbound net is attempted in tests (ping is env-gated OFF)

Run: ./venv/bin/python test_discovery_batch.py
'''
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
import urllib.error

# Hermetic law (same as test_webchat): no LLM, no outbound pings.
os.environ["EVERLIST_BRAIN_DISABLED"] = "1"
os.environ.pop("EVERLIST_INDEXNOW_PING", None)
os.environ.setdefault("WEBCHAT_RL_S_BURST", "200")
os.environ.setdefault("WEBCHAT_RL_S_PER_MIN", "200")
os.environ.setdefault("WEBCHAT_RL_IP_BURST", "500")
os.environ.setdefault("WEBCHAT_RL_IP_PER_MIN", "500")

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import webchat  # noqa: E402
import pages  # noqa: E402

CHECKS = []


def check(name, cond):
    CHECKS.append((name, bool(cond)))
    print(("PASS" if cond else "FAIL") + " - " + name)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


WC_PORT = free_port()
HUB_PORT = free_port()
TMP = tempfile.mkdtemp(prefix="hub-discovery-")
STATE = os.path.join(TMP, "state.json")
os.environ["EVERLIST_STATS_FILE"] = os.path.join(TMP, "pageviews.json")

# Isolated hub subprocess (same pattern as test_webchat) so webchat globals resolve.
HUB_ENV = dict(os.environ, HUB_STATE_FILE=STATE, PYTHONFAULTHANDLER="1",
               HUB_EMAIL_MODE="log", HUB_LIMIT_EMAIL="100")
hub_proc = subprocess.Popen(
    [sys.executable, "app.py", str(HUB_PORT)],
    cwd=HERE, env=HUB_ENV,
    stdout=subprocess.DEVNULL, stderr=open(os.path.join(TMP, "hub-stderr.log"), "w"),
)

webchat.PORT = WC_PORT
webchat.HUB_URL = "http://localhost:%d" % HUB_PORT
webchat.BIND = "127.0.0.1"
srv = webchat.ThreadingHTTPServer(("127.0.0.1", WC_PORT), webchat.Handler)
srv.daemon_threads = True
threading.Thread(target=srv.serve_forever, daemon=True).start()
BASEL = "http://127.0.0.1:%d" % WC_PORT

# Wait for webchat to accept connections (robust against slow CI starts).
for _ in range(50):
    try:
        get(BASEL + "/robots.txt")
        break
    except Exception:
        time.sleep(0.2)

# 1. robots.txt: allow-all, AI groups, sitemap
code, body = get(BASEL + "/robots.txt")
txt = body.decode("utf-8", "replace")
check("robots 200", code == 200)
check("robots allow-all + sitemap", "User-agent: *" in txt and "Sitemap:" in txt)
for ua in ("OAI-SearchBot", "ChatGPT-User", "GPTBot", "PerplexityBot",
           "ClaudeBot", "Google-Extended", "Applebot-Extended"):
    check("robots welcomes " + ua, ("User-agent: " + ua) in txt)

# 2. llms.txt: spec shape + public-base links
code, body = get(BASEL + "/llms.txt")
txt = body.decode("utf-8", "replace")
check("llms.txt 200", code == 200)
check("llms.txt H1", txt.startswith("# EverList"))
check("llms.txt blockquote after H1", "\n> " in txt or txt.split("\n", 1)[-1].strip().startswith(">"))
check("llms.txt links manifest+openapi", "/.well-known/agent-hub.json" in txt and "/openapi.json" in txt)
check("llms.txt links public base only", "everlist.network" in txt and "127.0.0.1" not in txt and "localhost" not in txt)
check("llms.txt pages section", "/how" in txt and "/transparency" in txt)

# 3. IndexNow key file: exact match at the well-known location
code, body = get(BASEL + "/.well-known/" + pages.INDEXNOW_KEY + ".txt")
check("indexnow key file 200", code == 200)
check("indexnow key exact", body.decode("utf-8", "replace").strip() == pages.INDEXNOW_KEY)
code, _ = get(BASEL + "/.well-known/wrongkey.txt")
check("indexnow wrong key 404", code == 404)

code, _ = get(BASEL + "/.well-known/agent-card.json")
check("agent-card 200", code == 200)
code, body = get(BASEL + "/.well-known/agent-card.json")
check("agent-card valid json + name", b'"EverList Hub"' in body)
code, _ = get(BASEL + "/.well-known/nope-card.json")
check("agent-card wrong path 404", code == 404)

# 4. hermetic law: default env leaves ping OFF (documented; no net attempted)
check("indexnow ping env-gated off by default", os.environ.get("EVERLIST_INDEXNOW_PING") != "1")

print("")
failed = [n for n, ok in CHECKS if not ok]
print("%d/%d PASSED" % (len(CHECKS) - len(failed), len(CHECKS)))
sys.exit(1 if failed else 0)
