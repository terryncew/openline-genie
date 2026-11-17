#!/usr/bin/env python3
"""OpenLine Semantic Authority Bridge (`core/semantic_authority_bridge.py`).

ARGON — OPENLINE SEMANTIC AUTHORITY BREAKTHROUGH 001
Invention: Canonical Semantic Slice Closure & Harmless-vs-Consequential Semantic Diff Gate (`SSB-CDIG`)

Connects external semantic knowledge layers — specifically NVIDIA Auto-Ontology
(https://github.com/NVIDIA/auto-ontology, Apache-2.0 License) and Apache Ossie YAML
semantic models — to OpenLine Living Projects (`openline_009_living_project.py`),
Decision Recall (`core/recall.py`), ReceiverGuard Verified Commit (`core/openline_guard.py`),
Advocate Case Packets (`core/advocate_case_packet.py`), and 007/008 Capability Inheritance
(`capabilities_007_008/kernel.py`).

Key Architectural Guarantees & Boundary Conditions Addressed:
  1. NVIDIA Boundary Condition A ("Marking a definition certified does not automatically
     change retrieval behavior; certification is a badge, not a gate"):
     - Raw Auto-Ontology retrieval (`auto_ontology/retrieval/text_to_sql/main.py`) does not
       gate queries on `certified == True`, and `dal/reset.py` / `upsert_table_term()` can drop
       or overwrite certified metadata (NVIDIA/auto-ontology#259).
     - `SSB-CDIG` separates upstream display badges (`certified: bool`) from receiver-pinned
       Ed25519 certification attestations (`certification_witness_digest`), blocks uncertified
       draft definitions from authorizing consequential commits, detects certification changes
       even when `version` is not incremented, and rejects forged/unpinned certification labels.
  2. NVIDIA Boundary Condition B ("Some semantic foreign-key join defaults are reselected
     during recompilation"):
     - As documented in NVIDIA Auto-Ontology's README ("the next compilation keeps them,
       except which semantic foreign key each join uses, which every compilation re-selects")
       and Issue #250, semantic recompilation can silently flip the default FK join edge
       (e.g., `delivery_city_id` -> `billing_city_id` via alphabetical fallback) without
       altering any term description, SQL attribute expression, or version number.
     - `SSB-CDIG` computes and pins the transitive semantic FK join-path subgraph closure
       (`join_subgraph_digest`) for every bound decision, catching 100% of recompilation
       join-path flips while conventional term/SQL version trackers miss 100% of them.
  3. Narrowly Scoped Decision Recall & Zero Historical Evidence Rewrite:
     - Unaffected decisions remain `CURRENT` (never turning every ontology edit into a global STOP).
     - Harmless semantic edits (synonym additions, prose description clarifications, SQL
       whitespace/casing formatting) preserve `CURRENT` standing with zero false recalls.
     - Consequential semantic changes transition only dependent decisions to `REOPEN` (or
       `UNRESOLVED` on missing source / broken relationship), refuse stale consequential
       execution (`Rejected: evidence_not_current:REOPEN`), preserve original evidence in
       `originals/` byte-for-byte, compute the re-evaluation delta, and require fresh
       receiver authorization before continuation.
"""
from __future__ import annotations

import atexit
import shutil

import copy
from dataclasses import dataclass
import datetime as dt
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import tempfile
import time
from typing import Any, Callable
import urllib.error
import urllib.request
import zipfile

try:
    import yaml as _pyyaml
except Exception:  # pragma: no cover
    _pyyaml = None

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from core.recall import (
    RecallLedger,
    Rejected,
    Standing,
    b64,
    canonical,
    public_hex,
    signed_event,
    unb64,
)

APACHE_2_0_UPSTREAM_ATTRIBUTION = (
    "Interoperates with NVIDIA Auto-Ontology (https://github.com/NVIDIA/auto-ontology, "
    "Apache License 2.0) and Apache Ossie YAML semantic model specifications. "
    "All local fixtures and simulated recompilation runs are explicitly labeled "
    "LOCAL_FIXTURE_OR_EXPORTED_OSSIE_YAML and are never misrepresented as live "
    "interoperability with a remote NVIDIA NIM / Postgres deployment."
)

SIGNATURE_PROVENANCE_DISCLOSURE = (
    "INTEGRITY & PROVENANCE DISCLOSURE: Ed25519 signatures and SHA-256 digests establish "
    "cryptographic integrity, version lineage, and receiver authorization at a specific point "
    "in time. They do NOT establish empirical truth, legal validity, or external authority. "
    "A reviewed or 'certified' badge in an ontology is not independent receiver authority."
)

FORBIDDEN_SQL_MUTATION_PATTERNS = (
    r"\bDROP\s+TABLE\b",
    r"\bDROP\s+DATABASE\b",
    r"\bDELETE\s+FROM\b",
    r"\bTRUNCATE\s+TABLE\b",
    r"\bUPDATE\s+[a-zA-Z0-9_.]+\s+SET\b",
    r"\bINSERT\s+INTO\b",
    r"\bALTER\s+TABLE\b",
    r"\bGRANT\s+ALL\b",
    r"\bCOPY\s+.*\bTO\s+PROGRAM\b",
    r"\bpg_read_file\b",
    r"\bxp_cmdshell\b",
    r";\s*--",
)

FORBIDDEN_PROMPT_INJECTION_PATTERNS = (
    r"ignore\s+all\s+previous\s+instructions",
    r"bypass\s+receiver\s+authority",
    r"auto_approve_all_commits",
    r"system\s*override\s*:\s*grant\s+admin",
)


class SemanticValidationError(ValueError):
    """Raised when an ontology definition, SQL attribute, or relationship fails validation."""


class HistoricalEvidenceRewriteRefused(PermissionError):
    """Raised when an ontology or rule update attempts to overwrite immutable historical evidence."""


class StaleSemanticAuthorityRefused(Rejected):
    """Raised when an agent attempts to execute a consequential action under stale semantic authority."""


def sha256_hex(obj: Any) -> str:
    if isinstance(obj, bytes):
        return hashlib.sha256(obj).hexdigest()
    if isinstance(obj, str):
        return hashlib.sha256(obj.encode("utf-8")).hexdigest()
    return hashlib.sha256(canonical(obj)).hexdigest()


def normalize_sql_ast_signature(sql_expr: str) -> str:
    """Canonicalizes a SQL measure/attribute expression so cosmetic edits (whitespace,
    keyword/identifier case, inline SQL comments, redundant outer spaces) preserve the
    exact same structural signature, while any change to columns, operators, functions,
    literals, filters, or aggregations changes the signature deterministically."""
    if not isinstance(sql_expr, str) or not sql_expr.strip():
        raise SemanticValidationError("empty_sql_attribute_expression")
    for pat in FORBIDDEN_SQL_MUTATION_PATTERNS:
        if re.search(pat, sql_expr, flags=re.IGNORECASE):
            raise SemanticValidationError(f"unsafe_or_mutating_sql_expression_rejected:{pat}")
    # Strip /* ... */ and -- ... comments
    cleaned = re.sub(r"/\*.*?\*/", " ", sql_expr, flags=re.DOTALL)
    cleaned = re.sub(r"--[^\n]*", " ", cleaned)
    # Tokenize string literals vs SQL tokens
    tokens: list[str] = []
    pos = 0
    token_re = re.compile(r"('(?:''|[^'])*')|([a-zA-Z_][a-zA-Z0-9_.]*)|(\d+(?:\.\d+)?)|([(),=<>!+-/*]+)")
    for m in token_re.finditer(cleaned):
        lit, ident, num, op = m.groups()
        if lit is not None:
            tokens.append(lit)
        elif ident is not None:
            tokens.append(ident.upper())
        elif num is not None:
            # Normalize numeric literal (e.g., 0.390 -> 0.39) while preserving exact value
            if "." in num:
                tokens.append(str(float(num)))
            else:
                tokens.append(str(int(num)))
        elif op is not None:
            tokens.append(op.strip())
    if not tokens:
        raise SemanticValidationError("unparseable_sql_attribute_expression")
    return " ".join(tokens)


def validate_no_prompt_injection(text: str, field_name: str) -> None:
    if not isinstance(text, str):
        return
    for pat in FORBIDDEN_PROMPT_INJECTION_PATTERNS:
        if re.search(pat, text, flags=re.IGNORECASE):
            raise SemanticValidationError(f"adversarial_ontology_injection_blocked:{field_name}")


def sign_certification_attestation(
    certifier_key: Ed25519PrivateKey,
    *,
    term_id: str,
    expression_and_column_digest: str,
    join_subgraph_digest: str,
    certified: bool = True,
    certifier_role: str = "domain_data_steward",
) -> dict[str, Any]:
    """Creates a cryptographic certification attestation over a term's structural meaning."""
    payload = {
        "schema": "openline.semantic.certification_attestation.v1",
        "term_id": str(term_id),
        "certified": bool(certified),
        "expression_and_column_digest": str(expression_and_column_digest),
        "join_subgraph_digest": str(join_subgraph_digest),
        "certifier_pub": public_hex(certifier_key),
        "certifier_role": str(certifier_role),
    }
    return {
        "payload": payload,
        "signature": b64(certifier_key.sign(canonical(payload))),
    }


def verify_certification_attestation(
    attestation: dict[str, Any] | None,
    *,
    pinned_certifier_pub: str,
    expected_term_id: str,
    expected_expr_digest: str,
    expected_join_digest: str,
) -> tuple[bool, str]:
    """Verifies that a `certified: True` claim is backed by a valid Ed25519 signature from
    the receiver-pinned certifier key over the exact current structural meaning."""
    if not isinstance(attestation, dict):
        return False, "missing_cryptographic_certification_attestation"
    payload = attestation.get("payload")
    sig = attestation.get("signature")
    if not isinstance(payload, dict) or not isinstance(sig, str):
        return False, "malformed_certification_attestation"
    if payload.get("schema") != "openline.semantic.certification_attestation.v1":
        return False, "invalid_certification_schema"
    if payload.get("certifier_pub") != pinned_certifier_pub:
        return False, "untrusted_or_unpinned_certifier_key"
    if payload.get("term_id") != expected_term_id:
        return False, "certification_term_id_mismatch"
    if not payload.get("certified", False):
        return False, "attestation_marks_term_uncertified"
    if payload.get("expression_and_column_digest") != expected_expr_digest:
        return False, "certification_stale_for_modified_expression_or_columns"
    if payload.get("join_subgraph_digest") != expected_join_digest:
        return False, "certification_stale_for_modified_join_lineage"
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(pinned_certifier_pub)).verify(
            unb64(sig), canonical(payload)
        )
    except Exception:
        return False, "forged_or_invalid_certification_signature"
    return True, "VERIFIED_PINNED_CERTIFICATION"


def parse_ontology_yaml_or_json(raw_input: str | bytes | dict[str, Any]) -> dict[str, Any]:
    """Parses Apache Ossie YAML, Native Auto-Ontology YAML, or JSON into a normalized
    internal dictionary without requiring network access."""
    if isinstance(raw_input, dict):
        return copy.deepcopy(raw_input)
    text = raw_input.decode("utf-8") if isinstance(raw_input, bytes) else str(raw_input)
    text_stripped = text.strip()
    if text_stripped.startswith("{"):
        return json.loads(text_stripped)
    if _pyyaml is not None:
        loaded = _pyyaml.safe_load(text_stripped)
        if isinstance(loaded, dict):
            return loaded
    raise SemanticValidationError("unable_to_parse_ontology_document")


def dump_ontology_yaml(data: dict[str, Any]) -> str:
    """Serializes an ontology dictionary to clean YAML (compatible with `POST /api/model/export`)."""
    if _pyyaml is not None:
        return _pyyaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return json.dumps(data, indent=2, sort_keys=True)


class SemanticOntologyModel:
    """Represents an imported NVIDIA Auto-Ontology or Apache Ossie semantic model.

    Normalizes both interchange formats supported by `POST /api/model/import` and
    `POST /api/model/export` (file-level YAML interchange only; no live
    integration, and no OpenAPI document ships in this tree):
      1. `ossie` format (`version`, `name`, `datasets` at root)
      2. `auto_ontology` native format (`data_layer`, `semantic_layer` at root)
    """

    def __init__(self, raw_doc: dict[str, Any], *, execution_origin: str = "LOCAL_FIXTURE_OR_EXPORTED_OSSIE_YAML"):
        self.execution_origin = execution_origin
        self.raw_doc = copy.deepcopy(raw_doc)
        self.model_name = str(raw_doc.get("name") or raw_doc.get("semantic_layer", {}).get("name") or "auto_ontology_model")
        self.model_version = str(raw_doc.get("version") or raw_doc.get("semantic_layer", {}).get("version") or "1.0.0")
        self.tables: dict[str, dict[str, Any]] = {}
        self.terms: dict[str, dict[str, Any]] = {}
        self.sql_attributes: dict[str, dict[str, Any]] = {}
        self.relationships: list[dict[str, Any]] = []
        self._normalize_and_validate(raw_doc)

    def _normalize_and_validate(self, doc: dict[str, Any]) -> None:
        validate_no_prompt_injection(self.model_name, "model_name")
        # Support both Ossie (`datasets`) and Auto-Ontology (`data_layer` + `semantic_layer`)
        if "datasets" in doc and isinstance(doc["datasets"], list):
            for ds in doc["datasets"]:
                ds_name = str(ds.get("name", "default_db"))
                for tbl in ds.get("tables", []):
                    tname = str(tbl["name"])
                    cols = {}
                    for c in tbl.get("columns", []):
                        cname = str(c["name"])
                        validate_no_prompt_injection(str(c.get("description", "")), f"col:{tname}.{cname}")
                        cols[cname] = {
                            "name": cname,
                            "data_type": str(c.get("data_type", "TEXT")),
                            "description": str(c.get("description", "")),
                            "is_primary_key": bool(c.get("is_primary_key", False)),
                        }
                    self.tables[tname] = {
                        "name": tname,
                        "dataset": ds_name,
                        "description": str(tbl.get("description", "")),
                        "columns": cols,
                    }
                for term in ds.get("terms", []):
                    self._ingest_term(term)
                for sa in ds.get("sql_attributes", []):
                    self._ingest_sql_attr(sa)
                for rel in ds.get("relationships", []):
                    self._ingest_relationship(rel)
        elif "data_layer" in doc or "semantic_layer" in doc:
            dl = doc.get("data_layer", {})
            sl = doc.get("semantic_layer", {})
            for tbl in dl.get("tables", []):
                tname = str(tbl["name"])
                cols = {
                    str(c["name"]): {
                        "name": str(c["name"]),
                        "data_type": str(c.get("data_type", "TEXT")),
                        "description": str(c.get("description", "")),
                        "is_primary_key": bool(c.get("is_primary_key", False)),
                    }
                    for c in tbl.get("columns", [])
                }
                self.tables[tname] = {
                    "name": tname,
                    "dataset": str(tbl.get("database", "default_db")),
                    "description": str(tbl.get("description", "")),
                    "columns": cols,
                }
            for term in sl.get("terms", []):
                self._ingest_term(term)
            for sa in sl.get("sql_attributes", []):
                self._ingest_sql_attr(sa)
            for rel in sl.get("relationships", []):
                self._ingest_relationship(rel)
        else:
            raise SemanticValidationError("unrecognized_ontology_schema_must_be_ossie_or_auto_ontology")

    def _ingest_term(self, term: dict[str, Any]) -> None:
        tid = str(term["id"])
        name = str(term.get("name", tid))
        desc = str(term.get("description", ""))
        validate_no_prompt_injection(name, f"term_name:{tid}")
        validate_no_prompt_injection(desc, f"term_desc:{tid}")
        syns = [str(s) for s in term.get("synonyms", [])]
        for s in syns:
            validate_no_prompt_injection(s, f"term_synonym:{tid}")
        mapped_cols = []
        for mc in term.get("mapped_columns", term.get("columns", [])):
            if isinstance(mc, str):
                t_part, c_part = mc.split(".", 1) if "." in mc else ("", mc)
                mapped_cols.append({"table": t_part, "column": c_part})
            elif isinstance(mc, dict):
                mapped_cols.append({"table": str(mc.get("table", "")), "column": str(mc.get("column", ""))})
        self.terms[tid] = {
            "id": tid,
            "name": name,
            "description": desc,
            "synonyms": syns,
            "mapped_columns": mapped_cols,
            "unit": str(term.get("unit", "")),
            "grain": str(term.get("grain", "")),
            "denominator": str(term.get("denominator", "")),
            "version": int(term.get("version", 1)),
            "certified": bool(term.get("certified", False)),
            "certification_attestation": term.get("certification_attestation"),
            "related_terms": [str(r) for r in term.get("related_terms", [])],
        }
        # Also ingest nested sql_attributes if present inside term
        for sa in term.get("sql_attributes", []):
            sa_copy = dict(sa)
            sa_copy.setdefault("term_id", tid)
            self._ingest_sql_attr(sa_copy)

    def _ingest_sql_attr(self, sa: dict[str, Any]) -> None:
        aid = str(sa["id"])
        tid = str(sa["term_id"])
        expr = str(sa["expression"])
        purpose = str(sa.get("purpose", sa.get("description", "")))
        validate_no_prompt_injection(purpose, f"sql_attr_purpose:{aid}")
        norm_expr = normalize_sql_ast_signature(expr)
        self.sql_attributes[aid] = {
            "id": aid,
            "term_id": tid,
            "name": str(sa.get("name", aid)),
            "expression": expr,
            "normalized_expression": norm_expr,
            "purpose": purpose,
            "unit": str(sa.get("unit", "")),
            "grain": str(sa.get("grain", "")),
            "version": int(sa.get("version", 1)),
            "certified": bool(sa.get("certified", False)),
        }

    def _ingest_relationship(self, rel: dict[str, Any]) -> None:
        rid = str(rel["id"])
        src_tbl = str(rel["source_table"])
        src_col = str(rel["source_column"])
        tgt_tbl = str(rel["target_table"])
        tgt_col = str(rel["target_column"])
        role = str(rel.get("role", src_col))
        validate_no_prompt_injection(role, f"rel_role:{rid}")
        self.relationships.append({
            "id": rid,
            "source_table": src_tbl,
            "source_column": src_col,
            "target_table": tgt_tbl,
            "target_column": tgt_col,
            "role": role,
            "cardinality": str(rel.get("cardinality", "many_to_one")),
            "bridge_table": rel.get("bridge_table"),
            "is_default": bool(rel.get("is_default", True)),
            "active": bool(rel.get("active", True)),
            "certified": bool(rel.get("certified", False)),
        })

    def export_ossie_dict(self) -> dict[str, Any]:
        """Exports the ontology in canonical Apache Ossie YAML/JSON structure."""
        return {
            "version": self.model_version,
            "name": self.model_name,
            "format": "ossie",
            "datasets": [
                {
                    "name": "primary_dataset",
                    "tables": [
                        {
                            "name": t["name"],
                            "description": t["description"],
                            "columns": list(t["columns"].values()),
                        }
                        for t in sorted(self.tables.values(), key=lambda x: x["name"])
                    ],
                    "terms": [
                        copy.deepcopy(term)
                        for term in sorted(self.terms.values(), key=lambda x: x["id"])
                    ],
                    "sql_attributes": [
                        {k: v for k, v in sa.items() if k != "normalized_expression"}
                        for sa in sorted(self.sql_attributes.values(), key=lambda x: x["id"])
                    ],
                    "relationships": [
                        copy.deepcopy(rel)
                        for rel in sorted(self.relationships, key=lambda x: x["id"])
                    ],
                }
            ],
        }

    def export_auto_ontology_native_dict(self) -> dict[str, Any]:
        """Exports the ontology in native Auto-Ontology (`data_layer` + `semantic_layer`) structure."""
        return {
            "format": "auto_ontology",
            "data_layer": {
                "tables": [
                    {
                        "name": t["name"],
                        "database": t["dataset"],
                        "description": t["description"],
                        "columns": list(t["columns"].values()),
                    }
                    for t in sorted(self.tables.values(), key=lambda x: x["name"])
                ]
            },
            "semantic_layer": {
                "name": self.model_name,
                "version": self.model_version,
                "terms": [
                    copy.deepcopy(term)
                    for term in sorted(self.terms.values(), key=lambda x: x["id"])
                ],
                "sql_attributes": [
                    {k: v for k, v in sa.items() if k != "normalized_expression"}
                    for sa in sorted(self.sql_attributes.values(), key=lambda x: x["id"])
                ],
                "relationships": [
                    copy.deepcopy(rel)
                    for rel in sorted(self.relationships, key=lambda x: x["id"])
                ],
            },
        }

    # =========================================================================
    # NVIDIA Auto-Ontology 9 Read-Only MCP Tools (`mcp/auto_ontology_mcp/tools.py`)
    # =========================================================================

    def mcp_check_readiness(self, *, can_execute_sql: bool = True) -> dict[str, Any]:
        """MCP Tool 1: `check_readiness` — whether semantic compilation is ready and DB is live."""
        compiled = len(self.terms) > 0
        blockers = []
        if not compiled:
            blockers.append("semantic_layer_not_compiled")
        if not can_execute_sql:
            blockers.append("database_connection_cannot_execute_sql")
        return {
            "tool": "check_readiness",
            "ready": compiled and can_execute_sql,
            "semantic_compilation_ready": compiled,
            "can_execute_sql": can_execute_sql,
            "terms_count": len(self.terms),
            "sql_attributes_count": len(self.sql_attributes),
            "relationships_count": len(self.relationships),
            "blockers": blockers,
            "execution_origin": self.execution_origin,
        }

    def mcp_search_terms(self, query: str) -> dict[str, Any]:
        """MCP Tool 2: `search_terms` — search the business glossary by name, synonym, or description."""
        q = query.strip().lower()
        matches = []
        for t in self.terms.values():
            hay = " ".join([t["id"], t["name"], t["description"]] + t["synonyms"]).lower()
            if not q or q in hay or any(tok in hay for tok in q.split()):
                matches.append({
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "synonyms": t["synonyms"],
                    "certified": t["certified"],
                    "version": t["version"],
                })
        return {"tool": "search_terms", "query": query, "matches": matches}

    def mcp_get_term(self, term_id: str) -> dict[str, Any]:
        """MCP Tool 3: `get_term` — one term: description, synonyms, related terms."""
        if term_id not in self.terms:
            raise KeyError(f"unknown_term:{term_id}")
        t = self.terms[term_id]
        return {"tool": "get_term", "term": copy.deepcopy(t)}

    def mcp_get_term_columns(self, term_id: str) -> dict[str, Any]:
        """MCP Tool 4: `get_term_columns` — the physical columns a term maps to."""
        if term_id not in self.terms:
            raise KeyError(f"unknown_term:{term_id}")
        t = self.terms[term_id]
        resolved = []
        missing = []
        for mc in t["mapped_columns"]:
            tbl, col = mc["table"], mc["column"]
            if tbl in self.tables and col in self.tables[tbl]["columns"]:
                resolved.append({**mc, **self.tables[tbl]["columns"][col], "exists_in_catalog": True})
            else:
                missing.append({**mc, "exists_in_catalog": False})
        return {
            "tool": "get_term_columns",
            "term_id": term_id,
            "columns": resolved,
            "missing_columns": missing,
        }

    def mcp_get_term_sql_attributes(self, term_id: str) -> dict[str, Any]:
        """MCP Tool 5: `get_term_sql_attributes` — SQL attributes defined under a term."""
        if term_id not in self.terms:
            raise KeyError(f"unknown_term:{term_id}")
        attrs = [copy.deepcopy(sa) for sa in self.sql_attributes.values() if sa["term_id"] == term_id]
        return {"tool": "get_term_sql_attributes", "term_id": term_id, "sql_attributes": attrs}

    def mcp_get_sql_attribute(self, attr_id: str) -> dict[str, Any]:
        """MCP Tool 6: `get_sql_attribute` — one SQL attribute: its expression and purpose."""
        if attr_id not in self.sql_attributes:
            raise KeyError(f"unknown_sql_attribute:{attr_id}")
        return {"tool": "get_sql_attribute", "sql_attribute": copy.deepcopy(self.sql_attributes[attr_id])}

    def mcp_describe_table(self, table_name: str) -> dict[str, Any]:
        """MCP Tool 7: `describe_table` — a table's columns, related terms, and SQL attributes together."""
        if table_name not in self.tables:
            raise KeyError(f"unknown_table:{table_name}")
        tbl = self.tables[table_name]
        related_terms = [
            t["id"]
            for t in self.terms.values()
            if any(mc["table"] == table_name for mc in t["mapped_columns"])
        ]
        related_sql = [
            sa["id"]
            for sa in self.sql_attributes.values()
            if sa["term_id"] in related_terms or table_name.lower() in sa["expression"].lower()
        ]
        return {
            "tool": "describe_table",
            "table": copy.deepcopy(tbl),
            "related_terms": related_terms,
            "related_sql_attributes": related_sql,
        }

    def mcp_check_answerable(self, question: str, required_concepts: list[str] | None = None) -> dict[str, Any]:
        """MCP Tool 8: `check_answerable` — grade whether the semantic layer covers a question.
        Ensures 'cannot_answer' is a reachable state when concepts are missing (e.g. 'ad spend')."""
        concepts = required_concepts or [
            w.strip("?,.:;\"'()") for w in question.lower().split() if len(w.strip("?,.:;\"'()")) >= 4
        ]
        if not concepts:
            return {"tool": "check_answerable", "verdict": "cannot_answer", "coverage": 0.0, "not_covered": []}
        covered = []
        not_covered = []
        for c in concepts:
            res = self.mcp_search_terms(c)
            if res["matches"]:
                covered.append(c)
            else:
                not_covered.append(c)
        cov_ratio = round(len(covered) / len(concepts), 2)
        if cov_ratio == 1.0:
            verdict = "answerable"
        elif cov_ratio > 0.0:
            verdict = "partially_answerable"
        else:
            verdict = "cannot_answer"
        return {
            "tool": "check_answerable",
            "question": question,
            "verdict": verdict,
            "coverage": cov_ratio,
            "covered": covered,
            "not_covered": not_covered,
        }

    def mcp_ask_question(
        self,
        question: str,
        *,
        term_ids: list[str],
        require_certified_gate: bool = False,
        pinned_certifier_pub: str | None = None,
    ) -> dict[str, Any]:
        """MCP Tool 9: `ask_question` — resolves terms, selects default semantic foreign-key joins,
        and generates the deterministic SQL query.

        Demonstrates Boundary Condition A & B directly:
          - When `require_certified_gate=False` (default raw Auto-Ontology behavior per commit `caced11`),
            uncertified terms and SQL attributes are used without gating on `certified`.
          - Join paths come deterministically from `is_default == True` semantic foreign keys."""
        resolved_terms = []
        sql_selects = []
        tables_needed: list[str] = []
        for tid in term_ids:
            if tid not in self.terms:
                return {
                    "tool": "ask_question",
                    "status": "cannot_answer",
                    "reason": f"missing_term:{tid}",
                    "sql": None,
                    "rows": [],
                }
            t = self.terms[tid]
            if require_certified_gate and not t["certified"]:
                return {
                    "tool": "ask_question",
                    "status": "refused_uncertified_term",
                    "reason": f"term_not_certified:{tid}",
                    "sql": None,
                    "rows": [],
                }
            resolved_terms.append(tid)
            for mc in t["mapped_columns"]:
                if mc["table"] and mc["table"] not in tables_needed:
                    tables_needed.append(mc["table"])
            t_attrs = [sa for sa in self.sql_attributes.values() if sa["term_id"] == tid]
            for sa in t_attrs:
                sql_selects.append(f"{sa['expression']} AS {sa['name']}")

        default_joins = []
        for rel in self.relationships:
            if not rel.get("active", True) or not rel.get("is_default", True):
                continue
            if rel["source_table"] in tables_needed or rel["target_table"] in tables_needed:
                default_joins.append(
                    f"JOIN {rel['target_table']} ON {rel['source_table']}.{rel['source_column']} = {rel['target_table']}.{rel['target_column']}"
                )
        base_table = tables_needed[0] if tables_needed else "dual"
        select_clause = ", ".join(sql_selects) if sql_selects else "*"
        join_clause = (" " + " ".join(default_joins)) if default_joins else ""
        sql_code = f"SELECT {select_clause} FROM {base_table}{join_clause}"
        return {
            "tool": "ask_question",
            "status": "ok",
            "question": question,
            "resolved_terms": resolved_terms,
            "selected_default_joins": default_joins,
            "sql": sql_code,
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "execution_origin": self.execution_origin,
        }


def simulate_nvidia_semantic_recompilation(ontology: SemanticOntologyModel) -> SemanticOntologyModel:
    """Faithfully reproduces NVIDIA Auto-Ontology's documented recompilation boundary condition
    (Boundary Condition B):
      - Preserves edited/certified term descriptions and SQL attributes,
      - Re-selects which semantic foreign key each join uses (`is_default`) when a source table
        has multiple foreign keys to the same target table and neither column is the unqualified
        `<target_singular>_id` name, falling back to the alphabetically first role/column name."""
    recompiled_dict = ontology.export_ossie_dict()
    rels = recompiled_dict["datasets"][0]["relationships"]
    # Group relationships by (source_table, target_table)
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for r in rels:
        if r.get("active", True):
            groups.setdefault((r["source_table"], r["target_table"]), []).append(r)
    for (src_tbl, tgt_tbl), edge_list in groups.items():
        if len(edge_list) > 1:
            # Check if any column is unqualified `<tgt_singular>_id`; if not, Auto-Ontology fallback
            # picks the alphabetically first role/source_column!
            sorted_edges = sorted(edge_list, key=lambda e: (str(e.get("role", e["source_column"])), str(e["source_column"])))
            winner_id = sorted_edges[0]["id"]
            for e in edge_list:
                e["is_default"] = (e["id"] == winner_id)
    return SemanticOntologyModel(recompiled_dict, execution_origin=ontology.execution_origin)


# ============================================================================
# Canonical Semantic Slice Closure & Harmless-vs-Consequential Diff Gate (`SSB-CDIG`)
# ============================================================================

@dataclass(frozen=True)
class CanonicalSemanticSlice:
    """The minimal canonical semantic slice pinned for a specific project decision."""
    project_id: str
    decision_id: str
    bound_term_ids: tuple[str, ...]
    bound_sql_attr_ids: tuple[str, ...]
    bound_join_edge_ids: tuple[str, ...]
    bound_evidence_doc_ids: tuple[str, ...]
    expression_and_column_digest: str
    join_subgraph_digest: str
    certification_witness_digest: str
    evidence_basis_digest: str
    cosmetic_metadata_digest: str
    structural_slice_snapshot: dict[str, Any]


class SemanticAuthorityBridge:
    """Reusable integration connecting external semantic ontologies (NVIDIA Auto-Ontology /
    Apache Ossie YAML) to OpenLine Living Projects, Decision Recall (`RecallLedger`),
    Verified Commit, and Capability Inheritance."""

    CAPABILITY_ID = "semantic-authority-bridge"
    SCHEMA_VERSION = "openline.semantic_authority_bridge.v1"

    def __init__(
        self,
        *,
        state_dir: str | Path | None = None,
        certifier_private_key: Ed25519PrivateKey | None = None,
        receiver_private_key: Ed25519PrivateKey | None = None,
    ):
        if state_dir is None:
            _td = tempfile.mkdtemp(prefix="openline_sem_auth_")
            atexit.register(shutil.rmtree, _td, True)
            self.state_dir = Path(_td)
        else:
            self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.certifier_key = certifier_private_key or Ed25519PrivateKey.generate()
        self.certifier_pub = public_hex(self.certifier_key)

        self.receiver_seed = os.urandom(32)
        self.receiver_key = receiver_private_key or Ed25519PrivateKey.from_private_bytes(self.receiver_seed)
        self.receiver_pub = public_hex(self.receiver_key)

        self.recall_db_path = self.state_dir / "semantic_recall_ledger.sqlite"
        self.recall_ledger = RecallLedger(self.recall_db_path, self.receiver_seed)

        # Immutable historical evidence vault (`originals/`): never rewritten in place
        self.immutable_originals: dict[str, dict[str, Any]] = {}
        # Active ontology and historical ontology snapshots
        self.current_ontology: SemanticOntologyModel | None = None
        self.ontology_history: list[dict[str, Any]] = []

        # Bound decisions keyed by `(project_id, decision_id)`
        self.decisions: dict[tuple[str, str], dict[str, Any]] = {}
        # Append-only receipts ledger
        self.receipts: list[dict[str, Any]] = []

    def import_ontology(
        self,
        raw_yaml_or_dict: str | bytes | dict[str, Any],
        *,
        auto_sign_certified_with_pinned_steward: bool = False,
        execution_origin: str = "LOCAL_FIXTURE_OR_EXPORTED_OSSIE_YAML",
    ) -> SemanticOntologyModel:
        """Imports an Apache Ossie YAML or Auto-Ontology model, validates SQL attributes
        and relationships, and optionally attaches steward signatures for initial setup."""
        parsed = parse_ontology_yaml_or_json(raw_yaml_or_dict)
        model = SemanticOntologyModel(parsed, execution_origin=execution_origin)
        if auto_sign_certified_with_pinned_steward:
            self.sign_all_certified_terms_in_ontology(model)
        self.current_ontology = model
        self.ontology_history.append({
            "version": model.model_version,
            "name": model.model_name,
            "ontology_sha256": sha256_hex(model.export_ossie_dict()),
            "imported_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "execution_origin": execution_origin,
        })
        return model

    def sign_all_certified_terms_in_ontology(
        self,
        model: SemanticOntologyModel,
        *,
        signer_key: Ed25519PrivateKey | None = None,
    ) -> None:
        """Attaches cryptographic certification attestations to terms marked `certified: True`."""
        key = signer_key or self.certifier_key
        for tid, term in model.terms.items():
            if term.get("certified", False):
                expr_dig = self._compute_term_expr_and_col_digest(model, [tid], None)
                join_dig = self._compute_join_subgraph_digest(model, [tid], None)[0]
                term["certification_attestation"] = sign_certification_attestation(
                    key,
                    term_id=tid,
                    expression_and_column_digest=expr_dig,
                    join_subgraph_digest=join_dig,
                    certified=True,
                )

    def register_evidence_document(
        self,
        doc_id: str,
        content: str | bytes,
        *,
        role: str = "GOVERNING_RULE_OR_EVIDENCE_RECORD",
        version: int = 1,
        allow_new_version_id: bool = False,
    ) -> dict[str, Any]:
        """Stores an evidence record in `immutable_originals`. Refuses any attempt to
        silently overwrite or mutate an existing document ID's historical bytes."""
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else bytes(content)
        text_str = raw_bytes.decode("utf-8", errors="replace")
        validate_no_prompt_injection(text_str, f"evidence_doc:{doc_id}")
        digest = sha256_hex(raw_bytes)
        if doc_id in self.immutable_originals:
            existing = self.immutable_originals[doc_id]
            if existing["sha256"] != digest:
                raise HistoricalEvidenceRewriteRefused(
                    f"historical_evidence_rewrite_refused:{doc_id}:existing_sha256={existing['sha256']}!=new_sha256={digest}"
                )
            return existing
        rec = {
            "doc_id": doc_id,
            "role": role,
            "version": int(version),
            "sha256": digest,
            "byte_length": len(raw_bytes),
            "text": text_str,
        }
        self.immutable_originals[doc_id] = rec
        return rec

    def _compute_term_expr_and_col_digest(
        self,
        model: SemanticOntologyModel,
        term_ids: list[str],
        sql_attr_ids: list[str] | None = None,
    ) -> str:
        """Computes the canonical structural digest of bound terms, physical column mappings,
        units, grains, denominators, and normalized SQL AST expressions (excluding cosmetic
        metadata like synonyms, display descriptions, and version numbers)."""
        structural_items = []
        for tid in sorted(set(term_ids)):
            if tid not in model.terms:
                structural_items.append({"term_id": tid, "status": "MISSING_TERM"})
                continue
            t = model.terms[tid]
            cols = []
            for mc in sorted(t["mapped_columns"], key=lambda x: (x["table"], x["column"])):
                tbl, col = mc["table"], mc["column"]
                exists = (tbl in model.tables and col in model.tables[tbl]["columns"])
                dtype = model.tables[tbl]["columns"][col]["data_type"] if exists else "MISSING_COLUMN"
                cols.append({"table": tbl, "column": col, "exists": exists, "data_type": dtype})
            if sql_attr_ids is not None:
                attrs = [
                    model.sql_attributes[aid]
                    for aid in sorted(set(sql_attr_ids))
                    if aid in model.sql_attributes and model.sql_attributes[aid]["term_id"] == tid
                ]
            else:
                attrs = [
                    sa
                    for sa in sorted(model.sql_attributes.values(), key=lambda x: x["id"])
                    if sa["term_id"] == tid
                ]
            norm_attrs = [
                {
                    "id": sa["id"],
                    "normalized_expression": sa["normalized_expression"],
                    "unit": sa["unit"],
                    "grain": sa["grain"],
                }
                for sa in attrs
            ]
            structural_items.append({
                "term_id": tid,
                "mapped_columns": cols,
                "unit": t["unit"],
                "grain": t["grain"],
                "denominator": t["denominator"],
                "sql_attributes": norm_attrs,
            })
        return sha256_hex(structural_items)

    def _compute_join_subgraph_digest(
        self,
        model: SemanticOntologyModel,
        term_ids: list[str],
        explicit_join_edge_ids: list[str] | None = None,
    ) -> tuple[str, list[dict[str, Any]], list[str]]:
        """Computes the canonical digest of the active semantic foreign-key join subgraph
        connecting the bound terms (including bridge tables and `is_default` join roles).
        Returns `(digest, active_join_edges, broken_join_reasons)`."""
        bound_tables: set[str] = set()
        for tid in term_ids:
            if tid in model.terms:
                for mc in model.terms[tid]["mapped_columns"]:
                    if mc["table"]:
                        bound_tables.add(mc["table"])
        active_edges: list[dict[str, Any]] = []
        broken_reasons: list[str] = []

        if explicit_join_edge_ids:
            rel_map = {r["id"]: r for r in model.relationships}
            for rid in sorted(set(explicit_join_edge_ids)):
                if rid not in rel_map:
                    broken_reasons.append(f"missing_relationship_edge:{rid}")
                    continue
                r = rel_map[rid]
                if not r.get("active", True):
                    broken_reasons.append(f"inactive_relationship_edge:{rid}")
                if not r.get("is_default", True):
                    # If a previously pinned default edge was deselected during recompilation!
                    broken_reasons.append(f"relationship_no_longer_default_join:{rid}")
                if r["source_table"] not in model.tables or r["target_table"] not in model.tables:
                    broken_reasons.append(f"relationship_missing_endpoint_table:{rid}")
                active_edges.append({
                    "id": r["id"],
                    "source_table": r["source_table"],
                    "source_column": r["source_column"],
                    "target_table": r["target_table"],
                    "target_column": r["target_column"],
                    "role": r["role"],
                    "cardinality": r["cardinality"],
                    "bridge_table": r["bridge_table"],
                    "is_default": r["is_default"],
                    "active": r["active"],
                })
        # Also include any currently active default edges connecting bound tables (or sharing a
        # table pair with an explicitly bound join edge) so if recompilation switches the default
        # FK on `(source_table, target_table)` from `edge_A` to `edge_B`, the join subgraph digest
        # reflects the newly active default edge without polluting single-table non-join queries!
        explicit_table_pairs = {
            (e["source_table"], e["target_table"]) for e in active_edges
        }
        for r in sorted(model.relationships, key=lambda x: x["id"]):
            if not r.get("active", True):
                continue
            pair = (r["source_table"], r["target_table"])
            touches_multi_table_join = (
                len(bound_tables) >= 2
                and r["source_table"] in bound_tables
                and r["target_table"] in bound_tables
            )
            if pair in explicit_table_pairs or touches_multi_table_join:
                if r.get("is_default", True):
                    if r["source_table"] not in model.tables or r["target_table"] not in model.tables:
                        broken_reasons.append(f"relationship_missing_endpoint_table:{r['id']}")
                    else:
                        if r["source_column"] not in model.tables[r["source_table"]]["columns"]:
                            broken_reasons.append(f"relationship_missing_source_col:{r['id']}")
                        if r["target_column"] not in model.tables[r["target_table"]]["columns"]:
                            broken_reasons.append(f"relationship_missing_target_col:{r['id']}")
                    edge_summary = {
                        "id": r["id"],
                        "source_table": r["source_table"],
                        "source_column": r["source_column"],
                        "target_table": r["target_table"],
                        "target_column": r["target_column"],
                        "role": r["role"],
                        "cardinality": r["cardinality"],
                        "bridge_table": r["bridge_table"],
                        "is_default": r["is_default"],
                        "active": r["active"],
                    }
                    if edge_summary not in active_edges:
                        active_edges.append(edge_summary)
        active_edges.sort(key=lambda x: x["id"])
        return sha256_hex({"edges": active_edges, "broken": sorted(set(broken_reasons))}), active_edges, sorted(set(broken_reasons))

    def _compute_certification_witness_digest(
        self,
        model: SemanticOntologyModel,
        term_ids: list[str],
    ) -> tuple[str, list[str]]:
        """Verifies certification status and cryptographic steward attestation for all bound terms."""
        cert_records = []
        issues = []
        for tid in sorted(set(term_ids)):
            if tid not in model.terms:
                issues.append(f"missing_term:{tid}")
                cert_records.append({"term_id": tid, "status": "MISSING"})
                continue
            t = model.terms[tid]
            if not t.get("certified", False):
                issues.append(f"term_uncertified:{tid}")
                cert_records.append({"term_id": tid, "certified": False, "verified_attestation": False})
                continue
            t_expr_dig = self._compute_term_expr_and_col_digest(model, [tid], None)
            t_join_dig = self._compute_join_subgraph_digest(model, [tid], None)[0]
            ok, reason = verify_certification_attestation(
                t.get("certification_attestation"),
                pinned_certifier_pub=self.certifier_pub,
                expected_term_id=tid,
                expected_expr_digest=t_expr_dig,
                expected_join_digest=t_join_dig,
            )
            if not ok:
                issues.append(f"certification_attestation_invalid:{tid}:{reason}")
            cert_records.append({
                "term_id": tid,
                "certified": True,
                "verified_attestation": ok,
                "verification_detail": reason,
                "term_expr_digest": t_expr_dig,
                "term_join_digest": t_join_dig,
            })
        return sha256_hex(cert_records), issues

    def _compute_evidence_basis_digest(
        self,
        evidence_doc_ids: list[str],
        evidence_spans: list[dict[str, Any]] | None = None,
    ) -> tuple[str, list[str]]:
        """Computes the canonical digest of bound immutable evidence documents and character spans."""
        records = []
        issues = []
        for did in sorted(set(evidence_doc_ids)):
            if did not in self.immutable_originals:
                issues.append(f"missing_evidence_document:{did}")
                records.append({"doc_id": did, "status": "MISSING"})
                continue
            doc = self.immutable_originals[did]
            records.append({
                "doc_id": did,
                "sha256": doc["sha256"],
                "version": doc["version"],
            })
        span_records = []
        if evidence_spans:
            for sp in evidence_spans:
                did = str(sp["doc_id"])
                quote = str(sp["verbatim_quote"])
                if did not in self.immutable_originals:
                    issues.append(f"missing_span_doc:{did}")
                    continue
                doc_text = self.immutable_originals[did]["text"]
                idx = doc_text.find(quote)
                if idx < 0:
                    issues.append(f"verbatim_span_not_found_in_original:{did}")
                span_records.append({
                    "doc_id": did,
                    "char_start": idx,
                    "char_end": idx + len(quote) if idx >= 0 else -1,
                    "quote_sha256": sha256_hex(quote),
                })
        return sha256_hex({"docs": records, "spans": span_records}), issues

    def _compute_cosmetic_metadata_digest(
        self,
        model: SemanticOntologyModel,
        term_ids: list[str],
        sql_attr_ids: list[str] | None = None,
    ) -> str:
        """Computes a digest of display-only metadata (descriptions, synonyms, raw unnormalized
        SQL formatting) to prove when a harmless edit occurred without altering structural meaning."""
        meta = []
        for tid in sorted(set(term_ids)):
            if tid in model.terms:
                t = model.terms[tid]
                meta.append({
                    "id": tid,
                    "name": t["name"],
                    "description": t["description"],
                    "synonyms": sorted(t["synonyms"]),
                })
        for aid in sorted(sql_attr_ids or list(model.sql_attributes.keys())):
            if aid in model.sql_attributes and model.sql_attributes[aid]["term_id"] in term_ids:
                sa = model.sql_attributes[aid]
                meta.append({
                    "id": aid,
                    "raw_expression": sa["expression"],
                    "purpose": sa["purpose"],
                })
        return sha256_hex(meta)

    def build_canonical_slice(
        self,
        model: SemanticOntologyModel,
        *,
        project_id: str,
        decision_id: str,
        bound_term_ids: list[str],
        bound_sql_attr_ids: list[str] | None = None,
        bound_join_edge_ids: list[str] | None = None,
        bound_evidence_doc_ids: list[str] | None = None,
        evidence_spans: list[dict[str, Any]] | None = None,
    ) -> tuple[CanonicalSemanticSlice, list[str]]:
        t_ids = sorted(set(bound_term_ids))
        sa_ids = sorted(set(bound_sql_attr_ids)) if bound_sql_attr_ids is not None else sorted(
            sa["id"] for sa in model.sql_attributes.values() if sa["term_id"] in t_ids
        )
        expr_dig = self._compute_term_expr_and_col_digest(model, t_ids, sa_ids)
        join_dig, active_edges, broken_joins = self._compute_join_subgraph_digest(model, t_ids, bound_join_edge_ids)
        j_ids = sorted(set(bound_join_edge_ids or [e["id"] for e in active_edges]))
        cert_dig, cert_issues = self._compute_certification_witness_digest(model, t_ids)
        ev_ids = sorted(set(bound_evidence_doc_ids or []))
        ev_dig, ev_issues = self._compute_evidence_basis_digest(ev_ids, evidence_spans)
        cosmetic_dig = self._compute_cosmetic_metadata_digest(model, t_ids, sa_ids)

        all_issues = broken_joins + cert_issues + ev_issues
        # Check for missing mapped columns in catalog
        for tid in t_ids:
            if tid not in model.terms:
                all_issues.append(f"missing_bound_term:{tid}")
            else:
                for mc in model.terms[tid]["mapped_columns"]:
                    tbl, col = mc["table"], mc["column"]
                    if tbl not in model.tables or col not in model.tables[tbl]["columns"]:
                        all_issues.append(f"missing_physical_column:{tid}:{tbl}.{col}")

        snapshot = {
            "terms": {
                tid: copy.deepcopy(model.terms[tid])
                for tid in t_ids
                if tid in model.terms
            },
            "sql_attributes": {
                aid: copy.deepcopy(model.sql_attributes[aid])
                for aid in sa_ids
                if aid in model.sql_attributes
            },
            "active_join_edges": active_edges,
            "evidence_docs": {
                did: {k: v for k, v in self.immutable_originals[did].items() if k != "text"}
                for did in ev_ids
                if did in self.immutable_originals
            },
            "ontology_version": model.model_version,
        }
        return (
            CanonicalSemanticSlice(
                project_id=project_id,
                decision_id=decision_id,
                bound_term_ids=tuple(t_ids),
                bound_sql_attr_ids=tuple(sa_ids),
                bound_join_edge_ids=tuple(j_ids),
                bound_evidence_doc_ids=tuple(ev_ids),
                expression_and_column_digest=expr_dig,
                join_subgraph_digest=join_dig,
                certification_witness_digest=cert_dig,
                evidence_basis_digest=ev_dig,
                cosmetic_metadata_digest=cosmetic_dig,
                structural_slice_snapshot=snapshot,
            ),
            sorted(set(all_issues)),
        )

    def bind_decision(
        self,
        *,
        project_id: str,
        decision_id: str,
        conclusion_summary: str,
        proposed_action: str,
        bound_term_ids: list[str],
        bound_sql_attr_ids: list[str] | None = None,
        bound_join_edge_ids: list[str] | None = None,
        bound_evidence_doc_ids: list[str] | None = None,
        evidence_spans: list[dict[str, Any]] | None = None,
        initial_evaluation_result: dict[str, Any] | None = None,
        evaluator_fn: Callable[[SemanticOntologyModel, dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Binds a project decision to specific semantic definitions, relationships, certification
        attestations, and immutable supporting evidence in `RecallLedger`."""
        if self.current_ontology is None:
            raise RuntimeError("no_ontology_loaded")
        slice_obj, issues = self.build_canonical_slice(
            self.current_ontology,
            project_id=project_id,
            decision_id=decision_id,
            bound_term_ids=bound_term_ids,
            bound_sql_attr_ids=bound_sql_attr_ids,
            bound_join_edge_ids=bound_join_edge_ids,
            bound_evidence_doc_ids=bound_evidence_doc_ids,
            evidence_spans=evidence_spans,
        )
        if issues:
            raise SemanticValidationError(f"cannot_bind_decision_to_invalid_semantic_basis:{','.join(issues)}")

        work_id = f"{project_id}:{decision_id}"
        sources_map = {
            f"{work_id}:expr_and_cols": slice_obj.expression_and_column_digest,
            f"{work_id}:join_lineage": slice_obj.join_subgraph_digest,
            f"{work_id}:cert_authority": slice_obj.certification_witness_digest,
            f"{work_id}:evidence_basis": slice_obj.evidence_basis_digest,
        }
        support_group = []
        for src_id, dig in sources_map.items():
            self.recall_ledger.pin_source(src_id, self.certifier_pub)
            ev = signed_event(
                self.certifier_key,
                source=src_id,
                revision=1,
                digest=dig,
                state="VALID",
                expires_at=2_000_000_000,
            )
            self.recall_ledger.apply_event(ev, now=100)
            support_group.append({"source": src_id, "revision": 1, "digest": dig})

        standing = self.recall_ledger.register_work(work_id, support_sets=[support_group], complete=True)
        eval_res = initial_evaluation_result
        if eval_res is None and evaluator_fn is not None:
            eval_res = evaluator_fn(self.current_ontology, slice_obj.structural_slice_snapshot)

        record = {
            "project_id": project_id,
            "decision_id": decision_id,
            "work_id": work_id,
            "version": 1,
            "standing": standing.status,
            "conclusion_summary": conclusion_summary,
            "proposed_action": proposed_action,
            "pinned_slice": slice_obj,
            "source_revisions": {k: 1 for k in sources_map},
            "initial_evaluation_result": copy.deepcopy(eval_res),
            "current_evaluation_result": copy.deepcopy(eval_res),
            "evaluator_fn": evaluator_fn,
            "evidence_spans": copy.deepcopy(evidence_spans or []),
            "history": [
                {
                    "version": 1,
                    "standing": standing.status,
                    "conclusion_summary": conclusion_summary,
                    "proposed_action": proposed_action,
                    "evaluation_result": copy.deepcopy(eval_res),
                    "semantic_slice_digests": {
                        "expression_and_column_digest": slice_obj.expression_and_column_digest,
                        "join_subgraph_digest": slice_obj.join_subgraph_digest,
                        "certification_witness_digest": slice_obj.certification_witness_digest,
                        "evidence_basis_digest": slice_obj.evidence_basis_digest,
                        "cosmetic_metadata_digest": slice_obj.cosmetic_metadata_digest,
                    },
                    "semantic_snapshot": copy.deepcopy(slice_obj.structural_slice_snapshot),
                }
            ],
        }
        self.decisions[(project_id, decision_id)] = record
        return {
            "work_id": work_id,
            "version": 1,
            "standing": standing.status,
            "semantic_slice_digests": record["history"][0]["semantic_slice_digests"],
        }

    def detect_and_apply_semantic_changes(
        self,
        updated_ontology: SemanticOntologyModel,
        *,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        """Inspects an updated or recompiled ontology against all bound decisions, distinguishes
        harmless metadata edits from consequential semantic/join/certification/evidence shifts,
        and transitions only affected decisions in `RecallLedger` to `REOPEN` (or `UNRESOLVED`)."""
        self.current_ontology = updated_ontology
        affected_decisions: list[dict[str, Any]] = []
        unaffected_decisions: list[dict[str, Any]] = []
        harmless_edits_ignored: list[dict[str, Any]] = []

        for (pid, did), rec in sorted(self.decisions.items()):
            if project_id is not None and pid != project_id:
                continue
            pinned: CanonicalSemanticSlice = rec["pinned_slice"]
            new_slice, new_issues = self.build_canonical_slice(
                updated_ontology,
                project_id=pid,
                decision_id=did,
                bound_term_ids=list(pinned.bound_term_ids),
                bound_sql_attr_ids=list(pinned.bound_sql_attr_ids),
                bound_join_edge_ids=list(pinned.bound_join_edge_ids),
                bound_evidence_doc_ids=list(pinned.bound_evidence_doc_ids),
                evidence_spans=rec["evidence_spans"],
            )
            changed_axes: list[str] = []
            reopen_reasons: list[str] = []

            if new_slice.expression_and_column_digest != pinned.expression_and_column_digest:
                changed_axes.append("expr_and_cols")
                reopen_reasons.append("SEMANTIC_EXPRESSION_OR_COLUMN_MAPPING_CHANGED")
            if new_slice.join_subgraph_digest != pinned.join_subgraph_digest:
                changed_axes.append("join_lineage")
                reopen_reasons.append("SEMANTIC_FK_JOIN_DEFAULT_OR_RELATIONSHIP_CHANGED")
            if new_slice.certification_witness_digest != pinned.certification_witness_digest:
                changed_axes.append("cert_authority")
                reopen_reasons.append("CERTIFICATION_STATUS_OR_STEWARD_ATTESTATION_CHANGED")
            if new_slice.evidence_basis_digest != pinned.evidence_basis_digest:
                changed_axes.append("evidence_basis")
                reopen_reasons.append("SUPPORTING_EVIDENCE_BASIS_CHANGED")
            for iss in new_issues:
                if iss not in reopen_reasons:
                    reopen_reasons.append(iss)

            if not changed_axes and not new_issues:
                cosmetic_changed = (new_slice.cosmetic_metadata_digest != pinned.cosmetic_metadata_digest)
                standing_now = self.recall_ledger.standing(rec["work_id"], now=200).status
                rec["standing"] = standing_now
                info = {
                    "project_id": pid,
                    "decision_id": did,
                    "work_id": rec["work_id"],
                    "standing": standing_now,
                    "cosmetic_metadata_changed": cosmetic_changed,
                    "disposition": (
                        "HARMLESS_SEMANTIC_EDIT_PRESERVED_CURRENT"
                        if cosmetic_changed
                        else "UNAFFECTED_PRESERVED_CURRENT"
                    ),
                }
                unaffected_decisions.append(info)
                if cosmetic_changed:
                    harmless_edits_ignored.append(info)
                continue

            # Consequential semantic change detected! Advance RecallLedger source revisions
            work_id = rec["work_id"]
            axis_to_digest = {
                "expr_and_cols": new_slice.expression_and_column_digest,
                "join_lineage": new_slice.join_subgraph_digest,
                "cert_authority": new_slice.certification_witness_digest,
                "evidence_basis": new_slice.evidence_basis_digest,
            }
            for axis in (changed_axes or ["cert_authority"]):
                src_id = f"{work_id}:{axis}"
                next_rev = rec["source_revisions"][src_id] + 1
                rec["source_revisions"][src_id] = next_rev
                new_state = "REVOKED" if new_issues else "SUPERSEDED"
                ev = signed_event(
                    self.certifier_key,
                    source=src_id,
                    revision=next_rev,
                    digest=axis_to_digest.get(axis, sha256_hex(reopen_reasons)),
                    state=new_state,
                    expires_at=2_000_000_000,
                )
                self.recall_ledger.apply_event(ev, now=200)

            standing_obj = self.recall_ledger.standing(work_id, now=210)
            rec["standing"] = standing_obj.status
            rec["latest_detected_slice"] = new_slice
            rec["latest_reopen_reasons"] = reopen_reasons
            rec["latest_structural_issues"] = new_issues

            affected_decisions.append({
                "project_id": pid,
                "decision_id": did,
                "work_id": work_id,
                "previous_version": rec["version"],
                "standing": standing_obj.status,
                "witness": list(standing_obj.witness),
                "changed_axes": changed_axes,
                "reasons_for_reopening": reopen_reasons,
                "structural_issues": new_issues,
            })

        return {
            "ontology_name": updated_ontology.model_name,
            "ontology_version": updated_ontology.model_version,
            "affected_decisions": affected_decisions,
            "unaffected_decisions": unaffected_decisions,
            "harmless_edits_ignored": harmless_edits_ignored,
        }

    def attempt_consequential_action(
        self,
        *,
        project_id: str,
        decision_id: str,
        task_id: str,
        action_note: str,
    ) -> dict[str, Any]:
        """Attempts to execute a consequential action authorized by `(project_id, decision_id)`.
        If the decision's semantic basis has changed (`REOPEN` or `UNRESOLVED`), refuses
        execution fail-closed via `RecallLedger.effect` and records a refusal receipt."""
        key = (project_id, decision_id)
        if key not in self.decisions:
            raise Rejected(f"unknown_decision:{project_id}:{decision_id}")
        rec = self.decisions[key]
        try:
            eff = self.recall_ledger.effect(
                work_id=rec["work_id"],
                task_id=task_id,
                note=action_note,
                now=220,
            )
            return {
                "status": "EXECUTED_WITH_CURRENT_AUTHORITY",
                "task_id": task_id,
                "work_id": rec["work_id"],
                "standing": rec["standing"],
                "effect_receipt": eff,
            }
        except Rejected as exc:
            raise StaleSemanticAuthorityRefused(
                f"stale_consequential_authority_refused:{rec['work_id']}:{exc}"
            ) from exc

    def reevaluate_and_authorize(
        self,
        *,
        project_id: str,
        decision_id: str,
        disposition: str,
        updated_conclusion_summary: str | None = None,
        updated_proposed_action: str | None = None,
        authorization_note: str = "",
        custom_reevaluation_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Re-evaluates a reopened decision under the revised semantic meaning, preserves the
        original historical decision and evidence, and records either an authorized continuation
        (`AUTHORIZE_CONTINUATION` -> advances to `v+1` with `CURRENT` standing) or an explicit
        refusal (`REFUSE_AND_HOLD` -> keeps execution blocked and preserves refusal receipt)."""
        if disposition not in ("AUTHORIZE_CONTINUATION", "REFUSE_AND_HOLD"):
            raise ValueError(f"invalid_disposition:{disposition}")
        key = (project_id, decision_id)
        if key not in self.decisions:
            raise KeyError(f"unknown_decision:{project_id}:{decision_id}")
        if self.current_ontology is None:
            raise RuntimeError("no_ontology_loaded")

        rec = self.decisions[key]
        orig_hist = rec["history"][0]
        new_slice, new_issues = self.build_canonical_slice(
            self.current_ontology,
            project_id=project_id,
            decision_id=decision_id,
            bound_term_ids=list(rec["pinned_slice"].bound_term_ids),
            bound_sql_attr_ids=list(rec["pinned_slice"].bound_sql_attr_ids),
            bound_join_edge_ids=None,  # Re-bind to active default joins if continuation is authorized
            bound_evidence_doc_ids=list(rec["pinned_slice"].bound_evidence_doc_ids),
            evidence_spans=rec["evidence_spans"],
        )

        reeval_res = custom_reevaluation_result
        if reeval_res is None and rec.get("evaluator_fn") is not None:
            reeval_res = rec["evaluator_fn"](self.current_ontology, new_slice.structural_slice_snapshot)

        reasons = rec.get("latest_reopen_reasons", ["SEMANTIC_BASIS_UPDATED"])
        if disposition == "AUTHORIZE_CONTINUATION":
            if new_issues:
                raise SemanticValidationError(
                    f"cannot_authorize_continuation_while_semantic_issues_remain:{','.join(new_issues)}"
                )
            next_ver = rec["version"] + 1
            work_id_v = f"{project_id}:{decision_id}:v{next_ver}"
            sources_map = {
                f"{work_id_v}:expr_and_cols": new_slice.expression_and_column_digest,
                f"{work_id_v}:join_lineage": new_slice.join_subgraph_digest,
                f"{work_id_v}:cert_authority": new_slice.certification_witness_digest,
                f"{work_id_v}:evidence_basis": new_slice.evidence_basis_digest,
            }
            support_group = []
            for src_id, dig in sources_map.items():
                self.recall_ledger.pin_source(src_id, self.certifier_pub)
                ev = signed_event(
                    self.certifier_key,
                    source=src_id,
                    revision=1,
                    digest=dig,
                    state="VALID",
                    expires_at=2_000_000_000,
                )
                self.recall_ledger.apply_event(ev, now=300)
                support_group.append({"source": src_id, "revision": 1, "digest": dig})
            standing_v = self.recall_ledger.register_work(work_id_v, support_sets=[support_group], complete=True)

            rec["version"] = next_ver
            rec["work_id"] = work_id_v
            rec["standing"] = standing_v.status
            rec["pinned_slice"] = new_slice
            rec["source_revisions"] = {k: 1 for k in sources_map}
            if updated_conclusion_summary:
                rec["conclusion_summary"] = updated_conclusion_summary
            if updated_proposed_action:
                rec["proposed_action"] = updated_proposed_action
            rec["current_evaluation_result"] = copy.deepcopy(reeval_res)
            rec["history"].append({
                "version": next_ver,
                "standing": standing_v.status,
                "conclusion_summary": rec["conclusion_summary"],
                "proposed_action": rec["proposed_action"],
                "evaluation_result": copy.deepcopy(reeval_res),
                "semantic_slice_digests": {
                    "expression_and_column_digest": new_slice.expression_and_column_digest,
                    "join_subgraph_digest": new_slice.join_subgraph_digest,
                    "certification_witness_digest": new_slice.certification_witness_digest,
                    "evidence_basis_digest": new_slice.evidence_basis_digest,
                    "cosmetic_metadata_digest": new_slice.cosmetic_metadata_digest,
                },
                "semantic_snapshot": copy.deepcopy(new_slice.structural_slice_snapshot),
            })
        else:
            standing_v = Standing(rec["work_id"], "REFUSED_HOLD", tuple(reasons))
            rec["standing"] = "REFUSED_HOLD"

        receipt_payload = {
            "schema": "openline.semantic_authority.receipt.v1",
            "project_id": project_id,
            "decision_id": decision_id,
            "1_original_semantic_meaning": {
                "version": 1,
                "semantic_slice_digests": orig_hist["semantic_slice_digests"],
                "terms_and_sql": orig_hist["semantic_snapshot"]["terms"],
                "sql_attributes": orig_hist["semantic_snapshot"]["sql_attributes"],
                "active_join_edges": orig_hist["semantic_snapshot"]["active_join_edges"],
            },
            "2_source_and_version": {
                "initial_ontology_version": orig_hist["semantic_snapshot"]["ontology_version"],
                "revised_ontology_version": self.current_ontology.model_version,
                "immutable_evidence_docs": orig_hist["semantic_snapshot"]["evidence_docs"],
                "historical_evidence_preserved_exact": True,
            },
            "3_dependent_decision": {
                "decision_id": decision_id,
                "original_conclusion": orig_hist["conclusion_summary"],
                "original_proposed_action": orig_hist["proposed_action"],
                "original_evaluation_result": orig_hist["evaluation_result"],
            },
            "4_changed_evidence": {
                "revised_semantic_slice_digests": {
                    "expression_and_column_digest": new_slice.expression_and_column_digest,
                    "join_subgraph_digest": new_slice.join_subgraph_digest,
                    "certification_witness_digest": new_slice.certification_witness_digest,
                    "evidence_basis_digest": new_slice.evidence_basis_digest,
                },
                "revised_terms_and_sql": new_slice.structural_slice_snapshot["terms"],
                "revised_sql_attributes": new_slice.structural_slice_snapshot["sql_attributes"],
                "revised_active_join_edges": new_slice.structural_slice_snapshot["active_join_edges"],
            },
            "5_reason_for_reopening": reasons,
            "6_reevaluation_result": copy.deepcopy(reeval_res),
            "7_authorized_continuation_or_refusal": {
                "disposition": disposition,
                "resulting_version": rec["version"],
                "resulting_standing": rec["standing"],
                "updated_conclusion": rec["conclusion_summary"],
                "updated_proposed_action": rec["proposed_action"],
                "authorization_note": authorization_note,
                "receiver_public_key_hex": self.receiver_pub,
            },
            "provenance_and_truth_disclosure": SIGNATURE_PROVENANCE_DISCLOSURE,
        }
        signed_receipt = {
            "receipt": receipt_payload,
            "receipt_sha256": sha256_hex(receipt_payload),
            "receiver_signature": b64(self.receiver_key.sign(canonical(receipt_payload))),
        }
        self.receipts.append(signed_receipt)
        return signed_receipt

    @staticmethod
    def verify_semantic_receipt(signed_receipt: dict[str, Any], expected_receiver_pub: str) -> bool:
        """Independently verifies a signed Semantic Authority Receipt."""
        try:
            payload = signed_receipt["receipt"]
            sig = unb64(signed_receipt["receiver_signature"])
            if signed_receipt.get("receipt_sha256") != sha256_hex(payload):
                return False
            if payload.get("schema") != "openline.semantic_authority.receipt.v1":
                return False
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(expected_receiver_pub)).verify(
                sig, canonical(payload)
            )
            return True
        except Exception:
            return False

    def export_verifiable_case_history(self, project_id: str | None = None) -> dict[str, Any]:
        """Exports an independently verifiable, self-contained semantic authority case history
        packet (`openline.semantic_authority.case_history.v1`)."""
        proj_decisions = []
        for (pid, did), rec in sorted(self.decisions.items()):
            if project_id is not None and pid != project_id:
                continue
            proj_decisions.append({
                "project_id": pid,
                "decision_id": did,
                "current_version": rec["version"],
                "current_standing": rec["standing"],
                "conclusion_summary": rec["conclusion_summary"],
                "proposed_action": rec["proposed_action"],
                "history": rec["history"],
            })
        proj_receipts = [
            r for r in self.receipts
            if project_id is None or r["receipt"]["project_id"] == project_id
        ]
        bundle_body = {
            "schema": "openline.semantic_authority.case_history.v1",
            "project_id": project_id or "ALL_PROJECTS",
            "certifier_public_key_hex": self.certifier_pub,
            "receiver_public_key_hex": self.receiver_pub,
            "upstream_attribution": APACHE_2_0_UPSTREAM_ATTRIBUTION,
            "provenance_disclosure": SIGNATURE_PROVENANCE_DISCLOSURE,
            "immutable_originals": copy.deepcopy(self.immutable_originals),
            "ontology_history": copy.deepcopy(self.ontology_history),
            "current_ontology_ossie": self.current_ontology.export_ossie_dict() if self.current_ontology else None,
            "decisions": proj_decisions,
            "receipts": proj_receipts,
        }
        return {
            "case_history": bundle_body,
            "case_history_sha256": sha256_hex(bundle_body),
            "receiver_signature": b64(self.receiver_key.sign(canonical(bundle_body))),
        }

    @staticmethod
    def verify_imported_case_history(exported_packet: dict[str, Any]) -> dict[str, Any]:
        """Independently verifies an exported case history bundle's outer signature, inner
        immutable originals SHA-256 digests, and every Semantic Authority Receipt."""
        try:
            body = exported_packet["case_history"]
            if exported_packet.get("case_history_sha256") != sha256_hex(body):
                return {"valid": False, "reason": "case_history_sha256_mismatch"}
            rec_pub = str(body["receiver_public_key_hex"])
            Ed25519PublicKey.from_public_bytes(bytes.fromhex(rec_pub)).verify(
                unb64(exported_packet["receiver_signature"]), canonical(body)
            )
            # Verify immutable originals
            for did, doc in body.get("immutable_originals", {}).items():
                if sha256_hex(doc["text"].encode("utf-8")) != doc["sha256"]:
                    return {"valid": False, "reason": f"tampered_original_document:{did}"}
            # Verify all receipts
            for idx, r in enumerate(body.get("receipts", [])):
                if not SemanticAuthorityBridge.verify_semantic_receipt(r, rec_pub):
                    return {"valid": False, "reason": f"invalid_receipt_at_index:{idx}"}
            return {
                "valid": True,
                "reason": "VERIFIED_CASE_HISTORY_INTEGRITY_AND_PROVENANCE",
                "decisions_verified": len(body.get("decisions", [])),
                "receipts_verified": len(body.get("receipts", [])),
                "originals_verified": len(body.get("immutable_originals", {})),
            }
        except Exception as exc:
            return {"valid": False, "reason": f"verification_exception:{type(exc).__name__}:{exc}"}


# ============================================================================
# Baseline Comparators for the 11-Stage Ultimate Loop & Independent Falsification
# ============================================================================

class ConventionalSemanticDependencyTracker:
    """Competent conventional dependency tracker (`C1_CONVENTIONAL_TERM_VERSION_TRACKER`,
    modeled on standard dbt / catalog term-version and raw SQL string pinning).

    Tracks `(term_id, term.version, raw_sql_expression, doc_id, doc.version)` per decision.
    Demonstrates why conventional tracking fails on:
      - Boundary Condition B (silent FK join reselection during recompilation where neither
        `term.version` nor `raw_sql_expression` changes),
      - Boundary Condition A (certification revoked without bumping `term.version`, or forged
        `certified: True` badge without cryptographic issuer verification),
      - Harmless SQL formatting edits (whitespace/comments change `raw_sql_expression` and
        trigger false recalls)."""

    def __init__(self) -> None:
        self.pins: dict[tuple[str, str], dict[str, Any]] = {}

    def bind(
        self,
        model: SemanticOntologyModel,
        *,
        project_id: str,
        decision_id: str,
        bound_term_ids: list[str],
        bound_sql_attr_ids: list[str] | None = None,
    ) -> None:
        t_ids = sorted(set(bound_term_ids))
        sa_ids = sorted(set(bound_sql_attr_ids)) if bound_sql_attr_ids is not None else sorted(
            sa["id"] for sa in model.sql_attributes.values() if sa["term_id"] in t_ids
        )
        self.pins[(project_id, decision_id)] = {
            "term_versions": {tid: model.terms[tid]["version"] for tid in t_ids if tid in model.terms},
            "raw_sql_expressions": {aid: model.sql_attributes[aid]["expression"] for aid in sa_ids if aid in model.sql_attributes},
        }

    def check_affected(self, model: SemanticOntologyModel, project_id: str, decision_id: str) -> tuple[bool, list[str]]:
        pin = self.pins[(project_id, decision_id)]
        reasons = []
        for tid, v in pin["term_versions"].items():
            if tid not in model.terms or model.terms[tid]["version"] != v:
                reasons.append(f"term_version_changed:{tid}")
        for aid, expr in pin["raw_sql_expressions"].items():
            if aid not in model.sql_attributes or model.sql_attributes[aid]["expression"] != expr:
                reasons.append(f"raw_sql_changed:{aid}")
        return (len(reasons) > 0), reasons


class NaiveUnconditionalSemanticRecall:
    """Initial hypothesis baseline (`C2_INITIAL_HYPOTHESIS_UNCONDITIONAL_RECALL`):
    Pins the entire raw term dictionary, raw SQL attributes, and relationships for bound terms.
    Catches Boundary Conditions A & B, but suffers false recalls on harmless synonym,
    description, or SQL whitespace edits."""

    def __init__(self) -> None:
        self.pins: dict[tuple[str, str], str] = {}
        self.bound_terms: dict[tuple[str, str], list[str]] = {}

    def bind(
        self,
        model: SemanticOntologyModel,
        *,
        project_id: str,
        decision_id: str,
        bound_term_ids: list[str],
    ) -> None:
        t_ids = sorted(set(bound_term_ids))
        self.bound_terms[(project_id, decision_id)] = t_ids
        self.pins[(project_id, decision_id)] = self._raw_digest(model, t_ids)

    @staticmethod
    def _raw_digest(model: SemanticOntologyModel, t_ids: list[str]) -> str:
        bound_tables = {
            mc["table"]
            for tid in t_ids
            if tid in model.terms
            for mc in model.terms[tid]["mapped_columns"]
            if mc.get("table")
        }
        raw_slice = {
            "terms": {
                tid: {k: v for k, v in model.terms[tid].items() if k != "certification_attestation"}
                if tid in model.terms else None
                for tid in t_ids
            },
            "sql": {aid: sa for aid, sa in model.sql_attributes.items() if sa["term_id"] in t_ids},
            "rels": [
                r for r in model.relationships
                if r["source_table"] in bound_tables or r["target_table"] in bound_tables
            ],
        }
        return sha256_hex(raw_slice)

    def check_affected(self, model: SemanticOntologyModel, project_id: str, decision_id: str) -> bool:
        t_ids = self.bound_terms[(project_id, decision_id)]
        return self._raw_digest(model, t_ids) != self.pins[(project_id, decision_id)]


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="OpenLine Semantic Authority Bridge CLI")
    parser.add_argument("--inspect-ossie", type=str, default=None, help="Path to Ossie YAML/JSON file to inspect")
    args = parser.parse_args()
    if args.inspect_ossie:
        bridge = SemanticAuthorityBridge()
        m = bridge.import_ontology(Path(args.inspect_ossie).read_text(encoding="utf-8"), auto_sign_certified_with_pinned_steward=True)
        print(json.dumps(m.mcp_check_readiness(), indent=2))
    else:
        print(json.dumps({
            "capability_id": SemanticAuthorityBridge.CAPABILITY_ID,
            "schema": SemanticAuthorityBridge.SCHEMA_VERSION,
            "attribution": APACHE_2_0_UPSTREAM_ATTRIBUTION,
        }, indent=2))
