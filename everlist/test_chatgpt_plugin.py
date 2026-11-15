#!/usr/bin/env python3
"""PA-8: ChatGPT portable plugin package contract.
Pins: portable manifest fields, honest review cases, no secrets,
canonical MCP URL, skill frontmatter, logo constraints."""
import json, os, re, struct

ROOT = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.join(ROOT, "chatgpt", "plugin")


def _json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def test_manifest_portable_identity():
    m = _json(os.path.join(PKG, "plugin.json"))
    assert m["$schema"].startswith("https://agent-plugins.org/schemas/")
    assert re.fullmatch(r"[a-z0-9-]+", m["name"]) and m["name"] == "everlist"
    assert m["version"] and m["description"]
    assert m["repository"].startswith("https://github.com/everlist-hq/")


def test_mcp_remote_no_auth():
    c = _json(os.path.join(PKG, "mcp.json"))
    servers = c["mcpServers"]
    assert len(servers) == 1
    s = servers["everlist"]
    assert s["type"] == "streamable-http"
    assert s["url"] == "https://everlist.network/mcp"
    assert s["extensions"]["com.openai"]["auth"]["type"] == "none"


def test_review_cases_honest_and_complete():
    m = _json(os.path.join(PKG, "plugin.json"))
    rev = m["extensions"]["com.openai"]["review"]
    assert len(rev["test_cases"]["positive"]) == 5
    assert len(rev["test_cases"]["negative"]) == 3
    for c in rev["test_cases"]["positive"]:
        assert c["prompt"] and c["tools_triggered"] and c["expected_behavior"]
    blob = json.dumps(rev)
    assert "testnet" in blob  # rail honesty pinned in the commerce description
    assert rev["commerce"] is True and rev["commerce_description"]


def test_listing_urls_live_on_prod():
    m = _json(os.path.join(PKG, "plugin.json"))
    it = m["extensions"]["com.openai"]["interface"]
    assert it["websiteURL"].startswith("https://everlist.network")
    assert it["privacyPolicyURL"] == "https://everlist.network/privacy"
    # terms + support are legal-data-gated (WEBCHAT_LEGAL_FILE) — the package
    # points at them; they go live when the owner approves real data.
    assert it["termsOfServiceURL"] == "https://everlist.network/terms"
    assert it["supportURL"] == "https://everlist.network/support"


def test_skill_frontmatter():
    raw = open(os.path.join(PKG, "skills", "get-started", "SKILL.md"), encoding="utf-8").read()
    assert raw.startswith("---\n")
    assert "name: get-started" in raw.split("---")[1]
    assert "testnet" in raw and "never handle credentials" in raw.lower()


def test_logo_square_min48():
    p = os.path.join(PKG, "assets", "logo.png")
    d = open(p, "rb").read()
    assert d[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", d[16:24])
    assert w == h and w >= 48


def test_no_secrets_in_package():
    for r, _d, fs in os.walk(PKG):
        for f in fs:
            t = open(os.path.join(r, f), encoding="utf-8", errors="ignore").read()
            for bad in ("sk-ant-", "sk-proj-", "BEGIN PRIVATE KEY", "password\":"):
                assert bad not in t, f"secret-like string in {f}"


def test_tools_referenced_exist_in_mcp_surface():
    src = open(os.path.join(ROOT, "mcp.py"), encoding="utf-8").read()
    m = _json(os.path.join(PKG, "plugin.json"))
    for c in m["extensions"]["com.openai"]["review"]["test_cases"]["positive"]:
        for tool in c["tools_triggered"].replace(" ", "").split(","):
            assert (f'"{tool}"' in src) or (f"'{tool}'" in src), f"tool {tool} not in mcp.py"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)}/{len(fns)} PASS")
