#!/usr/bin/env python3
"""RC6 living-world build: inline frozen graph_core.mjs into template.html.

graph_core.mjs is FROZEN (SHA-256 3272bd49..., byte-identical to RC5U);
only the template/integration layer changes. Output is the single-file
UI served by genie_server.py at / as src/genie_living_world.html.
"""
from pathlib import Path
import hashlib
import re

root = Path(__file__).resolve().parent
core_path = root / "graph_core.mjs"
tmpl_path = root / "template.html"
out_path = root.parent / "genie_living_world.html"

CORE_SHA = "3272bd4918b1a0718d47aed148340d5076698e807edec94ff361eac5b55a0215"

core = core_path.read_bytes()
assert hashlib.sha256(core).hexdigest() == CORE_SHA, "graph_core.mjs is not the frozen RC5 core"
core_js = re.sub(r"(?m)^export\s+", "", core.decode("utf-8"))

html = tmpl_path.read_text(encoding="utf-8")
assert "/*CORE_INJECTION*/" in html, "template missing /*CORE_INJECTION*/"
html = html.replace("/*CORE_INJECTION*/", core_js)
html = html.replace("/*DOMAIN_INJECTION*/", "")

out_path.write_text(html, encoding="utf-8")
print(f"Built {out_path} {len(html)} bytes | core SHA-256: {CORE_SHA[:16]}")
