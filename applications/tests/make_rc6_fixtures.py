#!/usr/bin/env python3
"""Generate real RC6 engine bundles (NO model calls) for the Node
projection tests: baseline bakery, accepted-after-oven2, pending
exploratory, rejected, and stopped bundles.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from genie_engine import OpenLineGenieEngine
from core.bakery import apply_path

PROMPT = (
    "Design a small neighborhood bakery — Hearth & Crumb Bakery: a single-file "
    "HTML app to plan daily baking, track batches, and see capacity."
)

OUT = Path(__file__).resolve().parent / "fixtures"
OUT.mkdir(parents=True, exist_ok=True)


def save(name, bundle):
    (OUT / name).write_text(json.dumps(bundle, indent=2, sort_keys=True), encoding="utf-8")
    print("wrote", name, bundle["project_id"], "v" + str(bundle["version"]))


eng = OpenLineGenieEngine(state_dir=tempfile.mkdtemp(prefix="genie-rc6-fix-"))
base = eng.build_from_prompt(PROMPT, use_model=False)
pid = base["project_id"]
save("bundle_baseline.json", base)

patch = {"bakery": {"assumptions": apply_path(
    base["accepted"]["state"]["bakery"]["assumptions"], "oven2")}}
pending = eng.propose_exploratory_change(pid, "Another oven?", patch)
save("bundle_pending_oven2.json", pending)

rejected = eng.reject_exploratory_change(
    pid, pending["exploratory"][0]["proposal_id"], "not_now")
save("bundle_rejected.json", rejected)

# Fresh engine for the accepted-after-oven2 bundle (clean history).
eng2 = OpenLineGenieEngine(state_dir=tempfile.mkdtemp(prefix="genie-rc6-fix2-"))
b2 = eng2.build_from_prompt(PROMPT, use_model=False)
pid2 = b2["project_id"]
p2 = eng2.propose_exploratory_change(pid2, "Another oven?", patch)
accepted = eng2.accept_exploratory_change(pid2, p2["exploratory"][0]["proposal_id"])
save("bundle_accepted_oven2.json", accepted)

eng2.trigger_stop("fixture_stop")
save("bundle_stopped.json", eng2.get_project_bundle(pid2))

# Accept hours on top of oven2 (synergy combo, spent path case).
eng3 = OpenLineGenieEngine(state_dir=tempfile.mkdtemp(prefix="genie-rc6-fix3-"))
b3 = eng3.build_from_prompt(PROMPT, use_model=False)
pid3 = b3["project_id"]
p3a = eng3.propose_exploratory_change(pid3, "Another oven?", patch)
eng3.accept_exploratory_change(pid3, p3a["exploratory"][0]["proposal_id"])
b3b = eng3.get_project_bundle(pid3)
patch_hours = {"bakery": {"assumptions": apply_path(
    b3b["accepted"]["state"]["bakery"]["assumptions"], "hours")}}
p3b = eng3.propose_exploratory_change(pid3, "Adjust shift schedule", patch_hours)
acc_hours = eng3.accept_exploratory_change(pid3, p3b["exploratory"][0]["proposal_id"])
save("bundle_accepted_oven2_hours.json", acc_hours)
print("project_id:", pid)
