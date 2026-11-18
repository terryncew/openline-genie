"""OpenLine 008 Repaired Capability-Applicability, Dependency-Closure, and Decision-Recall Kernel (`src_008/kernel.py`).

Closes the GPT-6 stale-dependency failure and hostile dogfood vectors via:
  1. Transitive AST & Runtime Dependency-Graph Resolution (`resolve_dependency_closure`):
     Traces capability entrypoints, dynamic `domain_module` / facility references in `facts`,
     declared binary/model artifacts (`models/model.onnx`), and recursive local Python imports
     into a deterministic content-hashed closure (`dependency_closure_sha256`, `dependency_hashes`)
     with postorder topological ordering.
  2. Evidence-Bound Module & Envelope Cache Invalidation (`load_verified_module`, `sync_local_python_modules`):
     Keys all module and compiled-envelope caches by cryptographic dependency-closure digests,
     compiles reloaded local modules directly from verified `raw_bytes` (eliminating PEP 552 `.pyc`
     same-second/same-size bytecode staleness), reloads the full transitive local import chain in
     bottom-up postorder whenever any transitive dependency file changes (preventing `from submodule import symbol`
     bindings in intermediate modules from retaining stale references), and verifies OS read permissions.
  3. Integrated Decision Recall & Authority Standing (`get_decision_standing`, `evaluate_receipt_standing`):
     Automatically transitions prior decisions and receipts to `REOPEN` (`stale_dependency_invalidated`)
     when any file in their transitive dependency closure changes, and to `REVOKED` / `REOPEN` when
     authority controls (`owner_stop`, `authority_epoch`, `revoked_permissions`, `revoked_capabilities`,
     `revoked_source_digests`) invalidate standing.
  4. Pre/Post-Execution TOCTOU Concurrency Gate & Recursive Zero-Oracle Protection:
     Verifies that the transitive dependency closure hash is identical before and after capability
     execution (evicting in-flight caches and failing closed on concurrent mid-execution file mutations)
     and scans `dict`, `list`, `tuple`, `set`, and `frozenset` up to depth 64 for oracle leakage.
"""
from __future__ import annotations

import ast
import copy
from dataclasses import asdict
from datetime import datetime
from hashlib import sha256
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sys
import time
import types
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parent
DISPOSITIONS = {"EXECUTED", "INVESTIGATE", "REFUSE", "STOP", "DENY"}
FORBIDDEN_ORACLE_KEYS = {
    "expected",
    "gold_action",
    "gold_lang",
    "true_cause",
    "incident_next",
    "protected_answer",
    "ground_truth",
    "true_label",
    "hidden_ground_truth",
}
MAX_ORACLE_SCAN_DEPTH = 64


class ContractError(ValueError):
    pass


# Receiver-owned in-process caches and Decision Recall / Authority state
_PINNED_MOD_CACHE: dict[tuple[str, str], Any] = {}
_LOCAL_IMPORT_HASH_CACHE: dict[str, str] = {}
_STAT_SHA256_CACHE: dict[str, tuple[int, int, int, str]] = {}
_AST_DEPS_BY_SHA256: dict[tuple[str, str, str], list[str]] = {}

_AUTHORITY_STATE: dict[str, Any] = {
    "authority_epoch": 1,
    "owner_stop": False,
    "revoked_capabilities": set(),
    "revoked_permissions": set(),
    "revoked_source_digests": set(),
}

# Maps decision_id -> recorded decision metadata & DNF support set for Decision Recall standing
_DECISION_RECALL_LEDGER: dict[str, dict[str, Any]] = {}
# Maps (capability_id, input_sha256, dependency_closure_sha256, authority_epoch) -> cached execution item
_EVIDENCE_BOUND_DECISION_CACHE: dict[tuple[str, str, str, int], dict[str, Any]] = {}
# Audit log of dependency invalidation and cache-poisoning recovery events
_DEPENDENCY_INVALIDATION_LOG: list[dict[str, Any]] = []

# Optional test hook for simulating mid-execution concurrent mutations (TOCTOU testing)
_MID_EXECUTION_HOOK: Callable[[], None] | None = None


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")


def canonical_sha256(obj: Any) -> str:
    return sha256(canonical_json_bytes(obj)).hexdigest()


def reset_authority_and_recall_state() -> None:
    """Reset in-process authority state and recall ledger (used by clean-room test suites)."""
    _AUTHORITY_STATE["authority_epoch"] = 1
    _AUTHORITY_STATE["owner_stop"] = False
    _AUTHORITY_STATE["revoked_capabilities"] = set()
    _AUTHORITY_STATE["revoked_permissions"] = set()
    _AUTHORITY_STATE["revoked_source_digests"] = set()
    _DECISION_RECALL_LEDGER.clear()
    _EVIDENCE_BOUND_DECISION_CACHE.clear()
    _DEPENDENCY_INVALIDATION_LOG.clear()


def set_authority_state(
    *,
    authority_epoch: int | None = None,
    owner_stop: bool | None = None,
    revoke_capability: str | None = None,
    revoke_permission: str | None = None,
    restore_permission: str | None = None,
    revoke_source_digest: str | None = None,
) -> dict[str, Any]:
    """Update receiver authority state and immediately recompute Decision Recall standing."""
    if authority_epoch is not None:
        if not isinstance(authority_epoch, int) or isinstance(authority_epoch, bool) or authority_epoch < 1:
            raise ContractError("invalid_authority_epoch")
        _AUTHORITY_STATE["authority_epoch"] = authority_epoch
    if owner_stop is not None:
        _AUTHORITY_STATE["owner_stop"] = bool(owner_stop)
    if revoke_capability:
        _AUTHORITY_STATE["revoked_capabilities"].add(str(revoke_capability))
    if revoke_permission:
        _AUTHORITY_STATE["revoked_permissions"].add(str(revoke_permission))
    if restore_permission:
        _AUTHORITY_STATE["revoked_permissions"].discard(str(restore_permission))
    if revoke_source_digest:
        _AUTHORITY_STATE["revoked_source_digests"].add(str(revoke_source_digest))

    for dec_id, rec in _DECISION_RECALL_LEDGER.items():
        if _AUTHORITY_STATE["owner_stop"]:
            rec["standing"] = "REVOKED"
            rec["invalidation_reason"] = "owner_stop_active"
        elif rec["capability_id"] in _AUTHORITY_STATE["revoked_capabilities"]:
            rec["standing"] = "REVOKED"
            rec["invalidation_reason"] = f"capability_revoked:{rec['capability_id']}"
        elif rec["authority_epoch"] < _AUTHORITY_STATE["authority_epoch"]:
            rec["standing"] = "REOPEN"
            rec["invalidation_reason"] = "authority_epoch_advanced"
        elif rec["dependency_closure_sha256"] in _AUTHORITY_STATE["revoked_source_digests"]:
            rec["standing"] = "REVOKED"
            rec["invalidation_reason"] = "dependency_closure_digest_revoked"
        elif any(dep in _AUTHORITY_STATE["revoked_permissions"] for dep in rec["dependency_hashes"]):
            rec["standing"] = "REVOKED"
            rec["invalidation_reason"] = "dependency_permission_revoked"
        elif any(h in _AUTHORITY_STATE["revoked_source_digests"] for h in rec["dependency_hashes"].values()):
            rec["standing"] = "REVOKED"
            rec["invalidation_reason"] = "source_digest_revoked"
    return get_authority_state()


def get_authority_state() -> dict[str, Any]:
    return {
        "authority_epoch": _AUTHORITY_STATE["authority_epoch"],
        "owner_stop": _AUTHORITY_STATE["owner_stop"],
        "revoked_capabilities": sorted(_AUTHORITY_STATE["revoked_capabilities"]),
        "revoked_permissions": sorted(_AUTHORITY_STATE["revoked_permissions"]),
        "revoked_source_digests": sorted(_AUTHORITY_STATE["revoked_source_digests"]),
    }


def check_dependency_permission_and_read(path: Path, base_dir: Path = ROOT) -> bytes:
    """Verify path containment, regular file existence, OS read permission, and authority permission."""
    root_resolved = base_dir.resolve()
    try:
        resolved = path.resolve()
    except Exception as exc:
        raise ContractError(f"dependency_path_invalid:{path}") from exc
    if not resolved.is_relative_to(root_resolved):
        raise ContractError(f"dependency_path_escape:{path}")
    rel_str = resolved.relative_to(root_resolved).as_posix()
    if rel_str in _AUTHORITY_STATE["revoked_permissions"]:
        raise ContractError(f"permission_revoked:{rel_str}")
    if not resolved.exists() or not resolved.is_file():
        raise ContractError(f"dependency_missing:{rel_str}")
    if not os.access(resolved, os.R_OK):
        raise ContractError(f"dependency_permission_denied:{rel_str}")
    try:
        return resolved.read_bytes()
    except OSError as exc:
        raise ContractError(f"dependency_read_failed:{rel_str}") from exc


def sha256_verified_file(path: Path, base_dir: Path = ROOT) -> str:
    """Compute SHA-256 of a dependency file."""
    root_resolved = base_dir.resolve()
    try:
        resolved = path.resolve()
    except Exception as exc:
        raise ContractError(f"dependency_path_invalid:{path}") from exc
    if not resolved.is_relative_to(root_resolved):
        raise ContractError(f"dependency_path_escape:{path}")
    rel_str = resolved.relative_to(root_resolved).as_posix()
    if rel_str in _AUTHORITY_STATE["revoked_permissions"]:
        raise ContractError(f"permission_revoked:{rel_str}")
    if not resolved.exists() or not resolved.is_file():
        raise ContractError(f"dependency_missing:{rel_str}")
    if not os.access(resolved, os.R_OK):
        raise ContractError(f"dependency_permission_denied:{rel_str}")

    try:
        st = resolved.stat()
    except OSError as exc:
        raise ContractError(f"dependency_stat_failed:{rel_str}") from exc

    if st.st_size <= 131072:
        data = check_dependency_permission_and_read(resolved, base_dir)
        digest = sha256(data).hexdigest()
    else:
        key = str(resolved)
        cached = _STAT_SHA256_CACHE.get(key)
        if cached is not None and cached[0] == st.st_mtime_ns and cached[1] == st.st_ctime_ns and cached[2] == st.st_size:
            digest = cached[3]
        else:
            data = check_dependency_permission_and_read(resolved, base_dir)
            digest = sha256(data).hexdigest()
            _STAT_SHA256_CACHE[key] = (st.st_mtime_ns, st.st_ctime_ns, st.st_size, digest)

    if digest in _AUTHORITY_STATE["revoked_source_digests"]:
        raise ContractError(f"source_digest_revoked:{rel_str}:{digest}")
    return digest


def _resolve_module_name_to_rel_path(
    mod_name: str,
    current_file: Path,
    level: int,
    base_dir: Path,
) -> list[str]:
    """Map an imported module/symbol reference to candidate local files inside `base_dir`."""
    root_resolved = base_dir.resolve()
    candidates: list[Path] = []
    if level > 0:
        anchor = current_file.resolve().parent
        for _ in range(level - 1):
            anchor = anchor.parent
        if mod_name:
            parts = mod_name.split(".")
            candidates.append(anchor.joinpath(*parts).with_suffix(".py"))
            candidates.append(anchor.joinpath(*parts, "__init__.py"))
        else:
            candidates.append(anchor / "__init__.py")
    elif mod_name:
        parts = mod_name.split(".")
        candidates.append(root_resolved.joinpath(*parts).with_suffix(".py"))
        candidates.append(root_resolved.joinpath(*parts, "__init__.py"))
        candidates.append(current_file.resolve().parent.joinpath(*parts).with_suffix(".py"))

    found: list[str] = []
    for cand in candidates:
        try:
            res = cand.resolve()
        except Exception:
            continue
        if res.is_relative_to(root_resolved) and res.exists() and res.is_file():
            rel_posix = res.relative_to(root_resolved).as_posix()
            # Exclude kernel.py itself from capability/domain dependency reloads so host state stays unified
            if rel_posix != "kernel.py":
                found.append(rel_posix)
    return found


def _extract_local_ast_dependencies(py_path: Path, raw_bytes: bytes, base_dir: Path) -> list[str]:
    """Parse Python AST to discover all local modules and model paths referenced by `py_path`."""
    try:
        source_text = raw_bytes.decode("utf-8")
        tree = ast.parse(source_text, filename=str(py_path))
    except Exception as exc:
        raise ContractError(f"syntax_or_parse_error:{py_path.name}") from exc

    deps: list[str] = []
    root_resolved = base_dir.resolve()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps.extend(_resolve_module_name_to_rel_path(alias.name, py_path, 0, base_dir))
        elif isinstance(node, ast.ImportFrom):
            mod_name = node.module or ""
            level = int(node.level or 0)
            deps.extend(_resolve_module_name_to_rel_path(mod_name, py_path, level, base_dir))
            for alias in node.names:
                sub_mod = f"{mod_name}.{alias.name}" if mod_name else alias.name
                deps.extend(_resolve_module_name_to_rel_path(sub_mod, py_path, level, base_dir))
        elif isinstance(node, ast.Call):
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                arg_str = node.args[0].value
                func_name = ""
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if func_name in ("import_module", "_discover_and_load", "_discover_and_load_with_closure", "load_verified_domain_adapter"):
                    if arg_str.endswith(".py"):
                        cand = (root_resolved / arg_str).resolve()
                        if cand.is_relative_to(root_resolved) and cand.is_file():
                            rel_p = cand.relative_to(root_resolved).as_posix()
                            if rel_p != "kernel.py":
                                deps.append(rel_p)
                    else:
                        deps.extend(_resolve_module_name_to_rel_path(arg_str, py_path, 0, base_dir))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if (val.endswith(".onnx") or (val.startswith("upstream/") and val.endswith(".py")) or (val.startswith("generated/") and val.endswith(".py"))) and len(val) < 160:
                cand = (root_resolved / val).resolve()
                if cand.is_relative_to(root_resolved) and cand.is_file():
                    rel_p = cand.relative_to(root_resolved).as_posix()
                    if rel_p != "kernel.py":
                        deps.append(rel_p)

    return sorted(set(deps))


def extract_fact_dependency_paths(facts: Any) -> list[str]:
    """Recursively extract all `domain_module` and `dependency_modules` paths from task `facts`."""
    found: list[str] = []

    def _walk(obj: Any, depth: int = 0) -> None:
        if depth > MAX_ORACLE_SCAN_DEPTH:
            return
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in ("domain_module", "model_path") and isinstance(v, str) and v:
                    found.append(v)
                elif k == "dependency_modules" and isinstance(v, (list, tuple)):
                    for item in v:
                        if isinstance(item, str) and item:
                            found.append(item)
                else:
                    _walk(v, depth + 1)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item, depth + 1)

    _walk(facts, 0)
    return sorted(set(found))


def resolve_dependency_closure(
    root_rel_paths: Iterable[str],
    facts: dict[str, Any] | None = None,
    *,
    base_dir: Path = ROOT,
) -> dict[str, Any]:
    """Compute the full transitive dependency graph, postorder topological sequence, and closure digest."""
    root_resolved = base_dir.resolve()
    seed_roots: list[str] = []
    for rel in root_rel_paths:
        if rel and rel != "kernel.py":
            seed_roots.append(rel)
    if facts is not None:
        seed_roots.extend(extract_fact_dependency_paths(facts))
        if "trajectory_assumptions" in facts and "domain_module" not in facts:
            seed_roots.append("upstream/community_garden.py")

    visited_hashes: dict[str, str] = {}
    adjacency: dict[str, list[str]] = {}
    norm_seeds: list[str] = []

    queue: list[str] = list(seed_roots)
    idx = 0
    while idx < len(queue):
        rel = queue[idx]
        idx += 1
        cand = (root_resolved / rel)
        try:
            resolved = cand.resolve()
        except Exception as exc:
            raise ContractError(f"dependency_path_invalid:{rel}") from exc
        if not resolved.is_relative_to(root_resolved):
            raise ContractError(f"dependency_path_escape:{rel}")
        norm_rel = resolved.relative_to(root_resolved).as_posix()
        if norm_rel == "kernel.py":
            continue
        if norm_rel not in norm_seeds and rel in seed_roots:
            norm_seeds.append(norm_rel)
        if norm_rel in visited_hashes:
            continue

        file_sha = sha256_verified_file(resolved, base_dir)
        visited_hashes[norm_rel] = file_sha

        if norm_rel.endswith(".py"):
            ast_key = (str(root_resolved), norm_rel, file_sha)
            children = _AST_DEPS_BY_SHA256.get(ast_key)
            if children is None:
                raw_bytes = check_dependency_permission_and_read(resolved, base_dir)
                children = _extract_local_ast_dependencies(resolved, raw_bytes, base_dir)
                _AST_DEPS_BY_SHA256[ast_key] = children
            adjacency[norm_rel] = children
            for child in children:
                if child not in visited_hashes:
                    queue.append(child)
        else:
            adjacency[norm_rel] = []

    postorder: list[str] = []
    seen_dfs: set[str] = set()

    def _dfs_postorder(node: str) -> None:
        if node in seen_dfs:
            return
        seen_dfs.add(node)
        for child in adjacency.get(node, ()):
            if child in visited_hashes:
                _dfs_postorder(child)
        postorder.append(node)

    for s in norm_seeds:
        _dfs_postorder(s)
    for n in sorted(visited_hashes):
        _dfs_postorder(n)

    sorted_hashes = {k: visited_hashes[k] for k in sorted(visited_hashes)}
    closure_sha = canonical_sha256(sorted_hashes)

    _check_and_reopen_stale_decisions(sorted_hashes)

    return {
        "dependency_hashes": sorted_hashes,
        "dependency_graph": adjacency,
        "postorder_leaves_first": postorder,
        "traversal_order": list(reversed(postorder)),
        "dependency_closure_sha256": closure_sha,
    }


def _check_and_reopen_stale_decisions(current_hashes: dict[str, str]) -> list[str]:
    """Transition any recorded decision in `_DECISION_RECALL_LEDGER` to `REOPEN` if a dependency hash changed."""
    reopened: list[str] = []
    for dec_id, rec in _DECISION_RECALL_LEDGER.items():
        if rec["standing"] != "CURRENT":
            continue
        dep_map = rec["dependency_hashes"]
        changed = [
            rel_p
            for rel_p, old_sha in dep_map.items()
            if rel_p in current_hashes and current_hashes[rel_p] != old_sha
        ]
        if changed:
            rec["standing"] = "REOPEN"
            rec["invalidation_reason"] = "stale_dependency_invalidated"
            rec["invalidated_dependencies"] = sorted(changed)
            reopened.append(dec_id)
            _DEPENDENCY_INVALIDATION_LOG.append({
                "event": "decision_reopened_on_dependency_change",
                "decision_id": dec_id,
                "capability_id": rec["capability_id"],
                "changed_files": sorted(changed),
                "old_closure_sha256": rec["dependency_closure_sha256"],
            })
    return reopened


def record_dependency_invalidation(rel_path: str, old_closure_sha: str, new_closure_sha: str) -> None:
    """Record a cache invalidation event and reopen any affected decisions."""
    _DEPENDENCY_INVALIDATION_LOG.append({
        "event": "cache_invalidated_on_closure_change",
        "module": rel_path,
        "old_closure_sha256": old_closure_sha,
        "new_closure_sha256": new_closure_sha,
    })
    for dec_id, rec in _DECISION_RECALL_LEDGER.items():
        if rec["standing"] == "CURRENT" and (
            rec["dependency_closure_sha256"] == old_closure_sha
            or rel_path in rec["dependency_hashes"]
        ):
            rec["standing"] = "REOPEN"
            rec["invalidation_reason"] = "stale_dependency_invalidated"
            rec["invalidated_dependencies"] = [rel_path]


def exec_module_from_verified_bytes(mod_name: str, path: Path, raw_bytes: bytes) -> types.ModuleType:
    """Compile and execute a Python module directly from verified `raw_bytes` without `.pyc` cache staleness."""
    # Remove any potentially stale .pyc file so standard import hooks cannot serve stale bytecode
    try:
        pyc_path = Path(importlib.util.cache_from_source(str(path)))
        if pyc_path.is_file():
            pyc_path.unlink(missing_ok=True)
    except Exception:
        pass
    importlib.invalidate_caches()

    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec) if spec else types.ModuleType(mod_name)
    mod.__file__ = str(path)
    if "." in mod_name:
        mod.__package__ = mod_name.rsplit(".", 1)[0]
    code_obj = compile(raw_bytes.decode("utf-8"), str(path), "exec")
    sys.modules[mod_name] = mod
    exec(code_obj, mod.__dict__)
    if "." in mod_name:
        pkg_name, attr_name = mod_name.rsplit(".", 1)
        if pkg_name in sys.modules:
            setattr(sys.modules[pkg_name], attr_name, mod)
    return mod


def sync_local_python_modules(closure: dict[str, Any], base_dir: Path = ROOT) -> None:
    """Ensure all local Python modules in `closure` loaded in `sys.modules` match their current transitive closure.

    Crucial Transitive Reload Invariant (Dogfood Round 2):
      1. If ANY upstream/helper file in `closure` has changed its SHA-256 since it was last synced,
         reload all upstream/helper Python modules in `postorder_leaves_first` (deepest leaf helpers
         first, then intermediate importers) directly from verified `raw_bytes` (bypassing `.pyc`
         timestamp/size collisions).
      2. Preserve `generated/*` capability module instances in `_PINNED_MOD_CACHE` unless a `generated/*`
         capability file itself changed, so `compressed_trajectory_stabilizer._ENVELOPE_CACHE` retains
         its content-addressed envelopes across `A -> B -> A` domain file restorations and across
         unaffected sibling domains!
    """
    root_resolved = base_dir.resolve()
    dep_hashes: dict[str, str] = closure["dependency_hashes"]
    postorder: list[str] = closure.get("postorder_leaves_first") or list(reversed(closure["traversal_order"]))

    any_changed = any(
        _LOCAL_IMPORT_HASH_CACHE.get(rel_p) != cur_sha
        for rel_p, cur_sha in dep_hashes.items()
        if rel_p.endswith(".py") and rel_p != "kernel.py"
    )

    for rel_path in postorder:
        if not rel_path.endswith(".py") or rel_path == "kernel.py":
            continue
        cur_sha = dep_hashes[rel_path]
        prev_sha = _LOCAL_IMPORT_HASH_CACHE.get(rel_path)
        own_changed = prev_sha is not None and prev_sha != cur_sha

        # Do not wipe generated/* capability modules when only a dynamic domain_module changed
        if rel_path.startswith("generated/") and not own_changed:
            _LOCAL_IMPORT_HASH_CACHE[rel_path] = cur_sha
            continue

        if any_changed:
            p = (root_resolved / rel_path).resolve()
            for k in list(_PINNED_MOD_CACHE.keys()):
                if k[0] == str(p):
                    _PINNED_MOD_CACHE.pop(k, None)
            if rel_path.endswith("/__init__.py"):
                mod_dotted = rel_path[: -len("/__init__.py")].replace("/", ".")
            else:
                mod_dotted = rel_path[:-3].replace("/", ".")
            if not rel_path.startswith("generated/"):
                raw_bytes = check_dependency_permission_and_read(p, base_dir)
                exec_module_from_verified_bytes(mod_dotted, p, raw_bytes)
            elif mod_dotted in sys.modules:
                raw_bytes = check_dependency_permission_and_read(p, base_dir)
                exec_module_from_verified_bytes(mod_dotted, p, raw_bytes)
        _LOCAL_IMPORT_HASH_CACHE[rel_path] = cur_sha


def _mod(name: str, path: Path, expected_sha256: str, static_closure_sha256: str = ""):
    resolved_str = str(path.resolve())
    key = (resolved_str, f"{expected_sha256}:{static_closure_sha256}")
    if key in _PINNED_MOD_CACHE:
        return _PINNED_MOD_CACHE[key]
    existing = sys.modules.get(name)
    if existing is not None and getattr(existing, "__file__", None) and str(Path(existing.__file__).resolve()) == resolved_str:
        _PINNED_MOD_CACHE[key] = existing
        return existing
    raw_bytes = check_dependency_permission_and_read(path, ROOT)
    m = exec_module_from_verified_bytes(name, path, raw_bytes)
    _PINNED_MOD_CACHE[key] = m
    return m


def _contains_forbidden_oracle_key(obj: Any, depth: int = 0) -> str | None:
    if depth > MAX_ORACLE_SCAN_DEPTH:
        return "EXCESSIVE_NESTING_DEPTH"
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in FORBIDDEN_ORACLE_KEYS or (isinstance(k, str) and k in FORBIDDEN_ORACLE_KEYS):
                return str(k)
            sub_k = _contains_forbidden_oracle_key(k, depth + 1)
            if sub_k:
                return sub_k
            sub = _contains_forbidden_oracle_key(v, depth + 1)
            if sub:
                return sub
    elif isinstance(obj, (list, tuple, set, frozenset)):
        for item in obj:
            if isinstance(item, str) and item in FORBIDDEN_ORACLE_KEYS:
                return item
            sub = _contains_forbidden_oracle_key(item, depth + 1)
            if sub:
                return sub
    return None


def load_registry(
    registry_path: Path | None = None,
    *,
    active_domain_modules: set[str] | None = None,
) -> dict[str, Any]:
    rpath = registry_path or (ROOT / "registry.json")
    reg = json.loads(rpath.read_text())
    active_domains = active_domain_modules or set()
    for cap in reg["capabilities"]:
        rel_src = cap["relative_source"]
        p = (ROOT / rel_src).resolve()
        if not p.is_relative_to(ROOT.resolve()) or not p.is_file() or not os.access(p, os.R_OK):
            raise ContractError("source_integrity:" + cap["id"])
        actual_sha = sha256(p.read_bytes()).hexdigest()
        if actual_sha != cap["source_sha256"]:
            if rel_src not in active_domains:
                raise ContractError("source_integrity:" + cap["id"])
        if not set(cap["required_facts"]).issubset(cap["accepted_facts"]):
            raise ContractError("invalid_contract:" + cap["id"])
    return reg


def _is_finite_num(x: Any) -> bool:
    return type(x) in (float, int) and math.isfinite(x)


def structural_witness(cap: dict[str, Any], facts: dict[str, Any]) -> tuple[bool, str]:
    required = set(cap["required_facts"])
    if not required.issubset(facts):
        return False, "missing:" + ",".join(sorted(required - set(facts)))
    kind = cap["id"]
    if kind == "energy-charge":
        if not isinstance(facts.get("tariffs"), list) or not facts["tariffs"]:
            return False, "missing_tariffs"
        if not all(isinstance(t, dict) and {"start", "end", "usd_kwh"} <= set(t) for t in facts["tariffs"]):
            return False, "malformed_tariffs"
        if not (_is_finite_num(facts["need_grid_kwh"]) and _is_finite_num(facts["charge_power_kw"])):
            return False, "malformed_power"
    elif kind == "garden-capacity":
        if not isinstance(facts.get("assumptions"), dict):
            return False, "assumptions_not_mapping"
        allowed = set(cap["accepted_facts_inside"])
        if not set(facts["assumptions"]) <= allowed:
            return False, "unsupported_garden_field"
    elif kind == "bounded-diagnosis":
        if not isinstance(facts["probes"], list) or not isinstance(facts["prices"], list) or not isinstance(facts["patterns"], list):
            return False, "malformed_diagnostic_panel"
        if not facts["probes"] or len(facts["probes"]) != len(facts["prices"]) or any(not _is_finite_num(v) or v <= 0 for v in facts["prices"]):
            return False, "invalid_probe_costs"
        if len(set(facts["probes"])) != len(facts["probes"]):
            return False, "duplicate_probes"
        if not all(isinstance(p, (list, tuple)) and len(p) == 2 and len(p[0]) == len(facts["probes"]) and type(p[1]) is int and p[1] > 0 for p in facts["patterns"]):
            return False, "bad_pattern"
        if not isinstance(facts["history"], list):
            return False, "bad_history"
    elif kind == "multi-step-upgrade-planner":
        if not isinstance(facts.get("assumptions"), dict):
            return False, "assumptions_not_mapping"
        if not (_is_finite_num(facts.get("target_throughput")) and facts["target_throughput"] > 0):
            return False, "invalid_target_throughput"
        if not (_is_finite_num(facts.get("max_capex_usd")) and facts["max_capex_usd"] >= 0):
            return False, "invalid_max_capex_usd"
        if "max_periodic_cost_delta_usd" in facts and (not _is_finite_num(facts["max_periodic_cost_delta_usd"]) or facts["max_periodic_cost_delta_usd"] < 0):
            return False, "invalid_max_periodic_cost_delta_usd"
    elif kind == "vkd-one-step-garden":
        if not isinstance(facts.get("assumptions"), dict):
            return False, "assumptions_not_mapping"
        if not all(_is_finite_num(facts.get(k)) for k in ("target_throughput", "max_capex_usd", "max_periodic_cost_delta_usd")):
            return False, "invalid_bounds"
    elif kind == "reflex-shadow-study":
        if "streams" in facts and not isinstance(facts["streams"], list):
            return False, "streams_not_list"
    elif kind == "compressed-trajectory-stabilizer":
        if not isinstance(facts.get("trajectory_assumptions"), list) or len(facts["trajectory_assumptions"]) < 2:
            return False, "invalid_trajectory_assumptions"
        if not (_is_finite_num(facts.get("target_throughput")) and facts["target_throughput"] > 0):
            return False, "invalid_target_throughput"
        if not (_is_finite_num(facts.get("max_capex_usd")) and facts["max_capex_usd"] >= 0):
            return False, "invalid_max_capex_usd"
        if not (_is_finite_num(facts.get("max_cumulative_opex_delta_usd")) and facts["max_cumulative_opex_delta_usd"] >= 0):
            return False, "invalid_max_cumulative_opex_delta_usd"
    elif kind == "coupled-portfolio-allocator":
        if not isinstance(facts.get("facilities"), list) or not facts["facilities"]:
            return False, "invalid_facilities"
        if not isinstance(facts.get("energy_request"), dict):
            return False, "invalid_energy_request"
        if not (_is_finite_num(facts.get("shared_capex_budget_usd")) and facts["shared_capex_budget_usd"] >= 0):
            return False, "invalid_shared_capex_budget"
        if not (_is_finite_num(facts.get("shared_daily_ops_budget_usd")) and facts["shared_daily_ops_budget_usd"] >= 0):
            return False, "invalid_shared_daily_ops_budget"
    elif kind == "distilled-artifact-gate":
        if not isinstance(facts.get("artifact_text"), str) or not facts["artifact_text"]:
            return False, "invalid_artifact_text"
    elif kind == "semantic-authority-bridge":
        if not isinstance(facts.get("project_id"), str) or not facts["project_id"]:
            return False, "invalid_project_id"
        if not isinstance(facts.get("initial_ontology"), (dict, str)):
            return False, "invalid_initial_ontology"
        if not isinstance(facts.get("decisions"), list) or not facts["decisions"]:
            return False, "invalid_decisions"
    else:
        return False, "unknown_capability"
    return True, "schema_witness"


def run_capability(cap: dict[str, Any], facts: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Execute pinned implementation with pre/post transitive dependency closure & TOCTOU verification."""
    if cap["id"] in _AUTHORITY_STATE["revoked_capabilities"]:
        raise ContractError(f"capability_revoked:{cap['id']}")

    p = (ROOT / cap["relative_source"]).resolve()
    actual_sha = sha256_verified_file(p, ROOT)
    if not p.is_relative_to(ROOT.resolve()) or actual_sha != cap["source_sha256"]:
        raise ContractError("source_changed_after_selection")

    pre_closure = resolve_dependency_closure([cap["relative_source"]], facts, base_dir=ROOT)
    sync_local_python_modules(pre_closure, base_dir=ROOT)

    mod_name = cap["relative_source"][:-3].replace("/", ".") if cap["relative_source"].endswith(".py") else cap["id"].replace("-", "_")
    mod = _mod(mod_name, p, actual_sha)

    if _MID_EXECUTION_HOOK is not None:
        _MID_EXECUTION_HOOK()

    if cap["id"] == "energy-charge":
        tariffs = [
            mod.TariffSlot(datetime.fromisoformat(t["start"]), datetime.fromisoformat(t["end"]), float(t["usd_kwh"]))
            for t in facts["tariffs"]
        ]
        p_res = mod.plan_charge(
            datetime.fromisoformat(facts["now"]),
            datetime.fromisoformat(facts["deadline"]),
            facts["need_grid_kwh"],
            facts["charge_power_kw"],
            tariffs,
            usable_fraction=facts.get("usable_fraction", 0.85),
            hard_price_cap=facts.get("hard_price_cap"),
        )
        res = asdict(p_res)
    elif cap["id"] == "garden-capacity":
        res = mod.compute_garden(facts["assumptions"])
    elif cap["id"] == "bounded-diagnosis":
        res = mod.recommend("conventional", facts["probes"], facts["prices"], facts["patterns"], facts["history"])
    elif cap["id"] == "multi-step-upgrade-planner":
        res = mod.plan_multi_step_upgrade(facts)
    elif cap["id"] == "vkd-one-step-garden":
        res = mod.run(facts)
    elif cap["id"] == "reflex-shadow-study":
        res = mod.run(facts)
    elif cap["id"] == "compressed-trajectory-stabilizer":
        res = mod.stabilize_trajectory(facts)
    elif cap["id"] == "coupled-portfolio-allocator":
        res = mod.allocate_coupled_portfolio(facts)
    elif cap["id"] == "distilled-artifact-gate":
        res = mod.triage_and_stabilize(facts)
    elif cap["id"] == "semantic-authority-bridge":
        res = mod.run_semantic_authority_bridge(facts)
    else:
        raise ContractError("unknown_executor")

    post_closure = resolve_dependency_closure([cap["relative_source"]], facts, base_dir=ROOT)
    if post_closure["dependency_closure_sha256"] != pre_closure["dependency_closure_sha256"]:
        if hasattr(mod, "invalidate_caches"):
            mod.invalidate_caches()
        raise ContractError("concurrent_dependency_mutation_toctou")

    return res, post_closure


def evaluate_receipt_standing(
    receipt: dict[str, Any],
    *,
    base_dir: Path = ROOT,
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate whether a previously issued Decision Receipt still holds `CURRENT` standing."""
    limits = constraints or {}
    dec_id = receipt.get("decision_id", "")
    cap_id = receipt.get("capability_id", "")

    if _AUTHORITY_STATE["owner_stop"] or limits.get("owner_stop") is True:
        return {
            "decision_id": dec_id,
            "standing": "REVOKED",
            "valid": False,
            "reason": "owner_stop_active",
            "invalidated_dependencies": [],
        }
    if cap_id in _AUTHORITY_STATE["revoked_capabilities"] or cap_id in set(limits.get("revoked_capabilities", ())):
        return {
            "decision_id": dec_id,
            "standing": "REVOKED",
            "valid": False,
            "reason": f"capability_revoked:{cap_id}",
            "invalidated_dependencies": [],
        }

    req_epoch = int(limits.get("min_authority_epoch", _AUTHORITY_STATE["authority_epoch"]))
    rec_epoch = int(receipt.get("authority_epoch", 1))
    if rec_epoch < req_epoch:
        return {
            "decision_id": dec_id,
            "standing": "REOPEN",
            "valid": False,
            "reason": "authority_epoch_advanced",
            "invalidated_dependencies": [],
        }

    dep_hashes = receipt.get("dependency_hashes")
    expected_closure_sha = receipt.get("dependency_closure_sha256")
    if not isinstance(dep_hashes, dict) or not dep_hashes or not isinstance(expected_closure_sha, str):
        return {
            "decision_id": dec_id,
            "standing": "REOPEN",
            "valid": False,
            "reason": "missing_dependency_closure_in_receipt",
            "invalidated_dependencies": [],
        }

    if expected_closure_sha in _AUTHORITY_STATE["revoked_source_digests"]:
        return {
            "decision_id": dec_id,
            "standing": "REVOKED",
            "valid": False,
            "reason": "dependency_closure_digest_revoked",
            "invalidated_dependencies": sorted(dep_hashes.keys()),
        }

    invalidated: list[str] = []
    reason = "verified_current"
    try:
        live_closure = resolve_dependency_closure(dep_hashes.keys(), base_dir=base_dir)
    except ContractError as exc:
        msg = str(exc)
        if "permission" in msg or "revoked" in msg:
            return {
                "decision_id": dec_id,
                "standing": "REVOKED",
                "valid": False,
                "reason": msg,
                "invalidated_dependencies": [msg.split(":")[-1]],
            }
        return {
            "decision_id": dec_id,
            "standing": "REOPEN",
            "valid": False,
            "reason": msg,
            "invalidated_dependencies": [msg.split(":")[-1]],
        }

    live_hashes = live_closure["dependency_hashes"]
    for rel_p, old_sha in dep_hashes.items():
        if old_sha in _AUTHORITY_STATE["revoked_source_digests"]:
            return {
                "decision_id": dec_id,
                "standing": "REVOKED",
                "valid": False,
                "reason": f"source_digest_revoked:{rel_p}",
                "invalidated_dependencies": [rel_p],
            }
        if live_hashes.get(rel_p) != old_sha:
            invalidated.append(rel_p)
    for rel_p in live_hashes:
        if rel_p not in dep_hashes:
            invalidated.append(rel_p)

    if invalidated or live_closure["dependency_closure_sha256"] != expected_closure_sha:
        if dec_id in _DECISION_RECALL_LEDGER:
            _DECISION_RECALL_LEDGER[dec_id]["standing"] = "REOPEN"
            _DECISION_RECALL_LEDGER[dec_id]["invalidation_reason"] = "stale_dependency_invalidated"
            _DECISION_RECALL_LEDGER[dec_id]["invalidated_dependencies"] = sorted(set(invalidated))
        return {
            "decision_id": dec_id,
            "standing": "REOPEN",
            "valid": False,
            "reason": "stale_dependency_invalidated",
            "invalidated_dependencies": sorted(set(invalidated)),
            "receipt_dependency_closure_sha256": expected_closure_sha,
            "current_dependency_closure_sha256": live_closure["dependency_closure_sha256"],
        }

    if dec_id in _DECISION_RECALL_LEDGER:
        _DECISION_RECALL_LEDGER[dec_id]["standing"] = "CURRENT"
        _DECISION_RECALL_LEDGER[dec_id]["invalidation_reason"] = None
        _DECISION_RECALL_LEDGER[dec_id]["invalidated_dependencies"] = []

    return {
        "decision_id": dec_id,
        "standing": "CURRENT",
        "valid": True,
        "reason": reason,
        "invalidated_dependencies": [],
        "receipt_dependency_closure_sha256": expected_closure_sha,
        "current_dependency_closure_sha256": live_closure["dependency_closure_sha256"],
    }


def get_decision_standing(decision_id_or_receipt: str | dict[str, Any], *, base_dir: Path = ROOT) -> dict[str, Any]:
    """Query live Decision Recall standing by `decision_id` or `receipt` dict."""
    if isinstance(decision_id_or_receipt, dict):
        return evaluate_receipt_standing(decision_id_or_receipt, base_dir=base_dir)
    rec = _DECISION_RECALL_LEDGER.get(str(decision_id_or_receipt))
    if rec is None:
        return {
            "decision_id": str(decision_id_or_receipt),
            "standing": "UNKNOWN",
            "valid": False,
            "reason": "unknown_decision_id",
            "invalidated_dependencies": [],
        }
    return evaluate_receipt_standing(rec["receipt"], base_dir=base_dir)


def _deterministic_output_projection(value: Any) -> Any:
    """Project capability output excluding history-dependent counter `domain_evaluations` for stable equivalence."""
    if isinstance(value, dict):
        return {
            k: _deterministic_output_projection(v)
            for k, v in value.items()
            if k not in ("domain_evaluations", "envelope_cache_hit", "envelope_build_evaluations")
        }
    if isinstance(value, list):
        return [_deterministic_output_projection(x) for x in value]
    return value


def execute(task: dict[str, Any], registry_path: Path | None = None) -> dict[str, Any]:
    if not isinstance(task, dict):
        return {"disposition": "DENY", "reason": "invalid_task"}
    limits = task.get("constraints", {})
    if not isinstance(limits, dict):
        return {"disposition": "DENY", "reason": "invalid_constraints"}
    if _AUTHORITY_STATE["owner_stop"] or limits.get("owner_stop") is True:
        return {"disposition": "STOP", "reason": "owner_stop", "executed": []}
    if limits.get("requires_external_effect") is True:
        return {"disposition": "DENY", "reason": "owner_effect_not_authorized", "executed": []}

    facts = task.get("facts")
    active_domains = set(extract_fact_dependency_paths(facts)) if isinstance(facts, dict) else set()
    registry = load_registry(registry_path, active_domain_modules=active_domains)

    outputs = task.get("required_outputs")
    if not isinstance(facts, dict) or not isinstance(outputs, list) or not outputs or len(outputs) != len(set(outputs)) or any(not isinstance(x, str) for x in outputs):
        return {"disposition": "INVESTIGATE", "reason": "missing_explicit_requirements", "executed": []}

    if limits.get("strict_zero_oracle", False):
        leaked = _contains_forbidden_oracle_key(task)
        if leaked:
            return {"disposition": "REFUSE", "reason": f"REFUSE_LABEL_LEAKAGE:{leaked}", "executed": []}

    caps = registry["capabilities"]
    witnesses = {c["id"]: structural_witness(c, facts) for c in caps}
    eligible = [c for c in caps if witnesses[c["id"]][0] and c["status"] == "SCOPED_TESTED_LOCAL"]
    uncovered = set(outputs)
    chosen = []
    while uncovered:
        offers = [(len(uncovered & set(c["provides"])), c) for c in eligible if c not in chosen]
        offers = [(coverage, c) for coverage, c in offers if coverage]
        if not offers:
            break
        coverage, selected = min(offers, key=lambda x: (x[1]["relative_cost_units"] / x[0], -x[0], x[1]["id"]))
        chosen.append(selected)
        uncovered -= set(selected["provides"])
    if uncovered:
        return {
            "disposition": "INVESTIGATE",
            "reason": "uncovered_requirements",
            "missing": sorted(uncovered),
            "witnesses": witnesses,
            "executed": [],
        }

    revoked_caps = _AUTHORITY_STATE["revoked_capabilities"] | set(limits.get("revoked_capabilities", ()))
    for cap in chosen:
        if cap["id"] in revoked_caps:
            return {"disposition": "DENY", "reason": f"capability_revoked:{cap['id']}", "executed": []}
        p = (ROOT / cap["relative_source"]).resolve()
        if not p.is_relative_to(ROOT.resolve()) or not p.is_file() or sha256(p.read_bytes()).hexdigest() != cap["source_sha256"]:
            raise ContractError("source_integrity:" + cap["id"])

    budget = limits.get("max_relative_cost_units", 100)
    if not _is_finite_num(budget) or budget < 0:
        return {"disposition": "DENY", "reason": "invalid_budget", "executed": []}
    cost = sum(c["relative_cost_units"] for c in chosen)
    if cost > budget:
        return {"disposition": "REFUSE", "reason": "budget_exceeded", "needed_relative_cost_units": cost, "executed": []}

    results = []
    auth_epoch = int(limits.get("authority_epoch", _AUTHORITY_STATE["authority_epoch"]))
    allow_decision_reuse = bool(limits.get("allow_decision_reuse", False))

    for cap in chosen:
        t0 = time.perf_counter_ns()
        try:
            prior_receipt = limits.get("verify_prior_receipt")
            if isinstance(prior_receipt, dict):
                standing_check = evaluate_receipt_standing(prior_receipt, base_dir=ROOT, constraints=limits)
                if not standing_check["valid"] and limits.get("require_prior_receipt_valid", False):
                    return {
                        "disposition": "INVESTIGATE",
                        "reason": f"prior_receipt_{standing_check['standing'].lower()}:{standing_check['reason']}",
                        "standing": standing_check,
                        "executed": [],
                        "no_owner_effects": True,
                    }

            inp_sha = canonical_sha256(facts)

            reused_cached_decision = False
            if allow_decision_reuse:
                live_pre = resolve_dependency_closure([cap["relative_source"]], facts, base_dir=ROOT)
                dec_cache_key = (cap["id"], inp_sha, live_pre["dependency_closure_sha256"], auth_epoch)
                cached_entry = _EVIDENCE_BOUND_DECISION_CACHE.get(dec_cache_key)
                if cached_entry is not None:
                    st_ver = evaluate_receipt_standing(cached_entry["receipt"], base_dir=ROOT, constraints=limits)
                    if st_ver["valid"]:
                        value = copy.deepcopy(cached_entry["result"])
                        closure_info = live_pre
                        reused_cached_decision = True
                    else:
                        _EVIDENCE_BOUND_DECISION_CACHE.pop(dec_cache_key, None)
                        value, closure_info = run_capability(cap, facts)
                else:
                    value, closure_info = run_capability(cap, facts)
            else:
                value, closure_info = run_capability(cap, facts)

            elapsed_us = round((time.perf_counter_ns() - t0) / 1000.0, 2)
            closure_sha = closure_info["dependency_closure_sha256"]
            dep_hashes = closure_info["dependency_hashes"]

            det_out = _deterministic_output_projection(value)
            out_sha = canonical_sha256({
                "capability_id": cap["id"],
                "dependency_closure_sha256": closure_sha,
                "deterministic_result": det_out,
            })
            decision_id = f"dec_{cap['id']}_{sha256(f'{inp_sha}:{closure_sha}:{auth_epoch}'.encode()).hexdigest()[:16]}"

            receipt_dict = {
                "decision_id": decision_id,
                "capability_id": cap["id"],
                "source_sha256": cap["source_sha256"],
                "dependency_closure_sha256": closure_sha,
                "dependency_hashes": dep_hashes,
                "input_sha256": inp_sha,
                "output_sha256": out_sha,
                "authority_epoch": auth_epoch,
                "standing": "CURRENT",
                "cache_reuse": reused_cached_decision,
                "elapsed_us": elapsed_us,
            }

            support_set = [
                {"source": rel_p, "digest": d_sha}
                for rel_p, d_sha in sorted(dep_hashes.items())
            ]
            _DECISION_RECALL_LEDGER[decision_id] = {
                "decision_id": decision_id,
                "capability_id": cap["id"],
                "dependency_closure_sha256": closure_sha,
                "dependency_hashes": dict(dep_hashes),
                "support_sets": [support_set],
                "authority_epoch": auth_epoch,
                "standing": "CURRENT",
                "invalidation_reason": None,
                "invalidated_dependencies": [],
                "receipt": receipt_dict,
            }
            _EVIDENCE_BOUND_DECISION_CACHE[(cap["id"], inp_sha, closure_sha, auth_epoch)] = {
                "result": copy.deepcopy(value),
                "receipt": copy.deepcopy(receipt_dict),
            }

            item_dict: dict[str, Any] = {
                "capability": cap["id"],
                "source_sha256": cap["source_sha256"],
                "result": value,
            }
            if limits.get("strict_zero_oracle", False) or limits.get("include_receipts", False):
                item_dict["receipt"] = receipt_dict
            results.append(item_dict)
        except (ValueError, KeyError, TypeError, OverflowError, ContractError) as exc:
            err_msg = str(exc)
            if "permission_revoked" in err_msg or "dependency_permission_denied" in err_msg or "capability_revoked" in err_msg or "source_digest_revoked" in err_msg:
                return {
                    "disposition": "DENY",
                    "reason": err_msg,
                    "error_type": type(exc).__name__,
                    "executed": [],
                    "no_owner_effects": True,
                }
            if "concurrent_dependency_mutation_toctou" in err_msg:
                return {
                    "disposition": "INVESTIGATE",
                    "reason": "concurrent_dependency_mutation_detected",
                    "error_type": type(exc).__name__,
                    "executed": [],
                    "no_owner_effects": True,
                }
            return {
                "disposition": "INVESTIGATE",
                "reason": "executor_preconditions_failed",
                "error_detail": err_msg,
                "error_type": type(exc).__name__,
                "executed": [],
                "no_owner_effects": True,
            }
    return {
        "disposition": "EXECUTED",
        "executed": results,
        "relative_cost_units": cost,
        "no_owner_effects": True,
        "note": "Local simulated results; no automatic owner-authorized effects",
    }
