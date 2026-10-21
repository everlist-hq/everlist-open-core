#!/usr/bin/env python3
"""Derive spec/everlist-api-v1.md from the live OpenAPI contract.

Anti-drift rule (docs/api-standard-governance.md #2.2): the normative spec is
GENERATED from app._openapi_spec() — never hand-edited. After any API change:

    venv/bin/python tools/gen_spec.py

and commit the regenerated spec together with the change (same change, no drift).
Versioning policy lives in spec front matter + docs/api-standard-governance.md #3.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import app  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "spec" / "everlist-api-v1.md"


def deref(spec, node, depth=0):
    """Render a schema node to a compact readable string, resolving one level of $ref."""
    if not isinstance(node, dict) or depth > 2:
        return ""
    if "$ref" in node:
        name = node["$ref"].rsplit("/", 1)[-1]
        return f"`{name}`"
    t = node.get("type", "")
    parts = []
    if t == "array":
        items = deref(spec, node.get("items", {}), depth + 1)
        return f"array of {items}" if items else "array"
    if t == "object" or "properties" in node:
        req = node.get("required", [])
        props = node.get("properties", {})
        if props:
            fields = []
            for pname, pnode in props.items():
                ptype = pnode.get("type", "")
                if ptype == "array":
                    ptype = "array"
                star = " (required)" if pname in req else ""
                desc = (pnode.get("description") or "").strip()
                desc = re.sub(r"\s+", " ", desc)
                line = f"- `{pname}`: {ptype or deref(spec, pnode, depth+1) or 'object'}{star}"
                if desc:
                    line += f" — {desc}"
                fields.append(line)
            parts.append("\n" + "\n".join(fields))
        return "object" + ("".join(parts) if parts else "")
    return t


def main():
    spec = app._openapi_spec()
    info = spec.get("info", {})
    lines = []
    a = lines.append

    a("# EverList API — Normative Spec v1")
    a("")
    a(f"> Derived from the live OpenAPI {spec.get('openapi')} contract served at `GET /openapi.json`.")
    a("> **This file is generated** by `tools/gen_spec.py` — do not hand-edit. Regenerate and")
    a("> commit in the same change as any API modification (no-drift rule).")
    a(">")
    a("> Versioning: v1.x is additive only (old conformant clients must keep working).")
    a("> Breaking changes require a new major version, a migration guide, and a >=6-month")
    a("> machine-readable deprecation window on v1. Trust-critical invariants (fee honesty,")
    a("> escrow-state validity, arithmetic integrity `fee + payout = amount`, capacity")
    a("> atomicity) are version-stable and non-negotiable.")
    a("> Governance: docs/api-standard-governance.md (EverList repo docs).")
    a("")
    a(f"**Title:** {info.get('title', 'EverList Hub API')}  ")
    a(f"**Contract version:** {info.get('version', 'unversioned')}  ")
    if info.get("description"):
        a(f"**Description:** {info.get('description')}")
    a("")

    paths = spec.get("paths", {})
    a(f"## Endpoints ({len(paths)} paths)")
    a("")

    def sort_key(item):
        path, ops = item
        # group: discovery/registry first, then listings/search, bookings, accounts, admin
        order = {"/openapi.json": 0, "/manifest.json": 1, "/registry": 2,
                 "/verticals": 3, "/search": 4, "/listings": 5}
        return (order.get(path, 10), path)

    for path, ops in sorted(paths.items(), key=sort_key):
        a(f"### `{path}`")
        a("")
        for method in sorted(ops):
            op = ops[method]
            summary = op.get("summary", "")
            a(f"#### `{method.upper()} {path}` — {summary}")
            a("")
            if op.get("description"):
                a(re.sub(r"\s+", " ", op["description"]).strip())
                a("")
            params = op.get("parameters", []) or []
            if params:
                a("**Parameters:**")
                a("")
                for p in params:
                    req = " (required)" if p.get("required") else ""
                    pdesc = re.sub(r"\s+", " ", (p.get("description") or "").strip())
                    a(f"- `{p.get('name')}` in `{p.get('in')}`{req}: {p.get('schema', {}).get('type', '')}"
                      + (f" — {pdesc}" if pdesc else ""))
                a("")
            rb = op.get("requestBody", {})
            if rb:
                for ct, media in (rb.get("content") or {}).items():
                    a(f"**Request body** (`{ct}`): {deref(spec, media.get('schema', {}))}")
                    a("")
            responses = op.get("responses", {}) or {}
            if responses:
                a("**Responses:**")
                a("")
                for code, resp in sorted(responses.items()):
                    desc = re.sub(r"\s+", " ", (resp.get("description") or "").strip())
                    body = ""
                    for ct, media in (resp.get("content") or {}).items():
                        body = f" (`{ct}`: {deref(spec, media.get('schema', {}))})"
                        break
                    a(f"- `{code}`: {desc}{body}")
                a("")

    comps = spec.get("components", {}).get("schemas", {})
    if comps:
        a(f"## Schemas ({len(comps)})")
        a("")
        for name, schema in sorted(comps.items()):
            a(f"### `{name}`")
            a("")
            rendered = deref(spec, schema)
            if rendered and rendered != "object":
                a(rendered)
                a("")
            elif schema.get("description"):
                a(re.sub(r"\s+", " ", schema["description"]).strip())
                a("")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {OUT} ({len(lines)} lines, {len(paths)} paths, {len(comps)} schemas)")


if __name__ == "__main__":
    main()