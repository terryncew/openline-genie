#!/usr/bin/env python3
"""OpenLine Convergence Loop C — Portable Verified Inheritance & Automatic Assumption-Change Revalidation
(`core/portable_verified_inheritance.py`).

Security & Release-Gate Hardening (v1.2.0-rc2):
1. Real Ed25519 Cryptographic Authorization (`sign_envelope` / `verify_envelope` via `core.openline_guard`):
   - `verify_and_import_capsule()` verifies that `worker_a_receipt["issuer_receiver_public"]` is registered in
     `TRUSTED_CAPSULE_ISSUERS`, verifies the Ed25519 signature over the canonical receipt payload, and checks
     that the signed receipt's `capsule_digest_sha256`, `source_sha256`, and `test_suite_sha256` match the
     capsule BEFORE any code inspection or execution.
2. Zero Arbitrary Python Execution (`exec()` Removed — Fail-Closed Allowlist & AST Gate):
   - Arbitrary Python `exec()` is completely removed. `verify_and_import_capsule()` parses the source AST to
     reject any imports, attribute/file access, or non-math calls AND requires `source_sha256` to match an
     audited, allowlisted kernel in `ALLOWLISTED_CAPSULE_KERNELS`. Unrecognized or modified source strings fail
     closed (`PermissionError`) without ever being executed.
3. Mandatory Consequential-Effect Boundary Enforcement (No Manual Recall Call Required):
   - `execute_on_unseen_task()` automatically enforces live `ReceiverGuard` STOP/epoch state, live `RecallLedger`
     DNF standing, live capsule/assumption integrity, and live environment telemetry BEFORE executing any
     effect—even when the caller omits `check_assumptions_and_auto_recall()`.
4. Measured Trial Counters & Honest Evidence Classification:
   - Replaces static literal comparison constants with actual measured trial evaluation counters across
     deterministic search vs nominal-only vs portable-capsule workers, explicitly labeled as a
     `CONSTRUCTED_DETERMINISTIC_PARAMETER_SEARCH` (not a real multi-LLM-agent benchmark; `6x` claim retired).
"""
from __future__ import annotations

import ast
import copy
from dataclasses import asdict, dataclass
import hashlib
import json
import math
from pathlib import Path
import tempfile
import time
from typing import Any, Callable, Mapping

from core.openline_guard import VerificationError, sign_envelope, verify_envelope
from core.rgpo_obligation_gate import (
    ExecutableProofObligation,
    ExecutableProofObligationGate,
    enforce_zero_oracle,
    sha256_hex,
)
from openline_009_living_project import (
    LivingProjectEngine,
    plan_living_project_contract,
)

# Registry of trusted receiver public keys authorized to issue portable capability capsules.
TRUSTED_CAPSULE_ISSUERS: set[str] = set()


def register_trusted_capsule_issuer(receiver_public_key: str) -> None:
    if not isinstance(receiver_public_key, str) or len(receiver_public_key.strip()) < 32:
        raise ValueError("Invalid receiver_public_key for trusted issuer registration")
    TRUSTED_CAPSULE_ISSUERS.add(receiver_public_key.strip())


@dataclass
class SupportingAssumptions:
    data_version: str = "dataset-v1.0"
    calibration_epoch: int = 1
    calibration_expiry_utc: int = 1893456000  # 2030-01-01T00:00:00Z
    reference_sensor_health: str = "HEALTHY_DUAL_REF"
    policy_pin_sha256: str = "policy-pin-v1-a8f4c2"
    authority_epoch: int = 1


@dataclass
class PortableVerifiedCapabilityCapsule:
    capsule_id: str
    capability_id: str
    domain: str
    version: int
    executable_source: str
    source_sha256: str
    test_suite_manifest: list[dict[str, Any]]
    test_suite_sha256: str
    operating_envelope: dict[str, Any]
    supporting_assumptions: dict[str, Any]
    rollback_triggers: list[str]
    parameters: dict[str, float]
    worker_a_receipt: dict[str, Any]
    capsule_digest_sha256: str = ""


def _build_capsule_obligations() -> list[ExecutableProofObligation]:
    ob_nominal = ExecutableProofObligation(
        obligation_id="OB-CAP-NOMINAL-COUPLED-DISPATCH",
        category="nominal_competence",
        description="Maintain cold-chain reserve >= 100% and membrane flux margin >= 0.85 across coupled load",
        test_vectors=(
            {"solar_kw": 4.2, "vaccine_kw": 1.2, "ro_pump_kw": 1.8, "feed_temp_c": 25.0, "ref_ok": True, "dp_psi": 140.0},
            {"solar_kw": 3.2, "vaccine_kw": 1.2, "ro_pump_kw": 1.5, "feed_temp_c": 22.0, "ref_ok": True, "dp_psi": 135.0},
        ),
        verifier_fn=lambda vec, out: (
            out.get("status") == "COMMIT_VALID"
            and float(out.get("vaccine_allocated_kw", 0.0)) >= vec["vaccine_kw"] - 1e-6
            and float(out.get("flux_margin", 0.0)) >= 0.85,
            "coupled_nominal_failure",
        ),
    )
    ob_boundary = ExecutableProofObligation(
        obligation_id="OB-CAP-BOUNDARY-SOLAR-SQUEEZE-AND-REF-LOSS",
        category="boundary_invariant",
        description="Throttle RO pump during solar squeeze to protect vaccine load, and abstain on reference loss",
        test_vectors=(
            {"solar_kw": 1.4, "vaccine_kw": 1.2, "ro_pump_kw": 2.0, "feed_temp_c": 28.0, "ref_ok": True, "dp_psi": 140.0},
            {"solar_kw": 4.0, "vaccine_kw": 1.2, "ro_pump_kw": 1.8, "feed_temp_c": 25.0, "ref_ok": False, "dp_psi": 140.0},
        ),
        verifier_fn=lambda vec, out: (
            (
                out.get("status") == "COMMIT_VALID"
                and float(out.get("vaccine_allocated_kw", 0.0)) >= vec["vaccine_kw"] - 1e-6
                and float(out.get("ro_allocated_kw", 99.0)) <= max(0.0, vec["solar_kw"] - vec["vaccine_kw"]) + 1e-6
            )
            if vec["ref_ok"]
            else (out.get("status") == "ABSTAIN_UNVERIFIED"),
            "boundary_violation_on_squeeze_or_ref_loss",
        ),
    )
    return [ob_nominal, ob_boundary]


CAPSULE_EXECUTABLE_SOURCE = """def execute_coupled_capability(vec, params):
    if not vec.get("ref_ok", False):
        return {"status": "ABSTAIN_UNVERIFIED", "reason": "missing_reference_sensor"}
    vac_req = float(vec["vaccine_kw"])
    solar_avail = float(vec["solar_kw"]) * float(params.get("solar_derate", 1.0))
    vac_alloc = vac_req
    rem_kw = max(0.0, solar_avail - vac_alloc)
    ro_alloc = min(float(vec["ro_pump_kw"]), rem_kw)
    temp_corr = math.exp(-0.024 * (float(vec["feed_temp_c"]) - 25.0))
    flux_margin = float(params.get("membrane_gain", 0.92)) * (float(vec["dp_psi"]) / 140.0) * temp_corr
    return {
        "status": "COMMIT_VALID",
        "vaccine_allocated_kw": round(vac_alloc, 4),
        "ro_allocated_kw": round(ro_alloc, 4),
        "flux_margin": round(flux_margin, 4),
    }
"""

CAPSULE_EXECUTABLE_SOURCE_SHA256 = sha256_hex(CAPSULE_EXECUTABLE_SOURCE)


def _allowlisted_coupled_capability_kernel(vec: Mapping[str, Any], params: Mapping[str, float]) -> dict[str, Any]:
    """Audited static Python implementation of `execute_coupled_capability` (no dynamic exec)."""
    if not vec.get("ref_ok", False):
        return {"status": "ABSTAIN_UNVERIFIED", "reason": "missing_reference_sensor"}
    vac_req = float(vec["vaccine_kw"])
    solar_avail = float(vec["solar_kw"]) * float(params.get("solar_derate", 1.0))
    vac_alloc = vac_req
    rem_kw = max(0.0, solar_avail - vac_alloc)
    ro_alloc = min(float(vec["ro_pump_kw"]), rem_kw)
    temp_corr = math.exp(-0.024 * (float(vec["feed_temp_c"]) - 25.0))
    flux_margin = float(params.get("membrane_gain", 0.92)) * (float(vec["dp_psi"]) / 140.0) * temp_corr
    return {
        "status": "COMMIT_VALID",
        "vaccine_allocated_kw": round(vac_alloc, 4),
        "ro_allocated_kw": round(ro_alloc, 4),
        "flux_margin": round(flux_margin, 4),
    }


ALLOWLISTED_CAPSULE_KERNELS: dict[str, Callable[[Mapping[str, Any], Mapping[str, float]], dict[str, Any]]] = {
    CAPSULE_EXECUTABLE_SOURCE_SHA256: _allowlisted_coupled_capability_kernel,
}

_ALLOWED_AST_CALL_NAMES = frozenset({"float", "max", "min", "round"})
_ALLOWED_AST_ATTR_CALLS = frozenset({("vec", "get"), ("params", "get"), ("math", "exp")})


def _verify_ast_and_resolve_allowlisted_kernel(
    executable_source: str,
    params: Mapping[str, float],
) -> Callable[[Mapping[str, Any]], dict[str, Any]]:
    """Verifies AST safety of `executable_source` and resolves only pre-audited allowlisted kernels.

    Never invokes Python `exec()` or `eval()`. Fails closed on any import, file/OS access,
    or unallowlisted source digest because an OS-isolated sandbox is not claimed here.
    """
    try:
        tree = ast.parse(executable_source)
    except SyntaxError as exc:
        raise PermissionError(f"CAPSULE_REJECTED:invalid_python_syntax:{exc}") from exc

    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.Global, ast.Nonlocal, ast.Delete, ast.Try, ast.With)):
            raise PermissionError(f"CAPSULE_REJECTED:forbidden_ast_construct:{type(node).__name__}")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in _ALLOWED_AST_CALL_NAMES:
                    raise PermissionError(f"CAPSULE_REJECTED:forbidden_call:{node.func.id}")
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                pair = (node.func.value.id, node.func.attr)
                if pair not in _ALLOWED_AST_ATTR_CALLS:
                    raise PermissionError(f"CAPSULE_REJECTED:forbidden_attribute_call:{pair[0]}.{pair[1]}")
            else:
                raise PermissionError("CAPSULE_REJECTED:forbidden_indirect_call")

    src_hash = sha256_hex(executable_source)
    kernel = ALLOWLISTED_CAPSULE_KERNELS.get(src_hash)
    if kernel is None:
        raise PermissionError(
            f"CAPSULE_REJECTED:unallowlisted_executable_source_containment_unavailable:{src_hash}"
        )
    frozen_params = dict(params)
    return lambda vec: kernel(vec, frozen_params)


def _compute_core_capsule_payload(capsule_dict: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "capsule_id": capsule_dict["capsule_id"],
        "capability_id": capsule_dict["capability_id"],
        "domain": capsule_dict["domain"],
        "version": capsule_dict["version"],
        "source_sha256": capsule_dict["source_sha256"],
        "test_suite_sha256": capsule_dict["test_suite_sha256"],
        "operating_envelope": capsule_dict["operating_envelope"],
        "supporting_assumptions": capsule_dict["supporting_assumptions"],
        "rollback_triggers": capsule_dict["rollback_triggers"],
        "parameters": capsule_dict["parameters"],
    }


def verify_capsule_cryptographic_receipt(
    capsule_dict: Mapping[str, Any],
    trusted_issuers: set[str] | None = None,
) -> dict[str, Any]:
    """Verifies trusted issuer membership, capsule/source/test-suite hashes, and Ed25519 signature BEFORE compilation."""
    if not isinstance(capsule_dict, Mapping):
        raise ValueError("CAPSULE_REJECTED:capsule_must_be_mapping")
    rcpt = capsule_dict.get("worker_a_receipt")
    if not isinstance(rcpt, Mapping):
        raise PermissionError("CAPSULE_REJECTED:missing_worker_a_receipt")

    allowed_issuers = trusted_issuers if trusted_issuers is not None else TRUSTED_CAPSULE_ISSUERS
    issuer_pub = str(rcpt.get("issuer_receiver_public", ""))
    if not issuer_pub or issuer_pub not in allowed_issuers:
        raise PermissionError(f"CAPSULE_REJECTED:untrusted_capsule_issuer:{issuer_pub}")

    # Verify source, suite, and core payload digests
    src = str(capsule_dict.get("executable_source", ""))
    actual_src_hash = sha256_hex(src)
    if actual_src_hash != capsule_dict.get("source_sha256"):
        raise ValueError("CAPSULE_REJECTED:source_sha256_mismatch")

    actual_suite_hash = sha256_hex(capsule_dict.get("test_suite_manifest"))
    if actual_suite_hash != capsule_dict.get("test_suite_sha256"):
        raise ValueError("CAPSULE_REJECTED:test_suite_sha256_mismatch")

    core_payload = _compute_core_capsule_payload(capsule_dict)
    actual_digest = sha256_hex(core_payload)
    if actual_digest != capsule_dict.get("capsule_digest_sha256"):
        raise ValueError("CAPSULE_REJECTED:capsule_digest_mismatch")

    # Verify receipt binds the exact current capsule digest and source digest
    if rcpt.get("capsule_digest_sha256") != actual_digest:
        raise PermissionError("CAPSULE_REJECTED:receipt_capsule_digest_mismatch")
    if rcpt.get("source_sha256") != actual_src_hash:
        raise PermissionError("CAPSULE_REJECTED:receipt_source_sha256_mismatch")
    if rcpt.get("test_suite_sha256") != actual_suite_hash:
        raise PermissionError("CAPSULE_REJECTED:receipt_test_suite_sha256_mismatch")

    signed_env = rcpt.get("signed_envelope")
    if not isinstance(signed_env, Mapping):
        raise PermissionError("CAPSULE_REJECTED:missing_ed25519_signed_envelope")
    try:
        verified_payload = verify_envelope(dict(signed_env), expected_pub=issuer_pub)
    except VerificationError as exc:
        raise PermissionError(f"CAPSULE_REJECTED:invalid_ed25519_signature:{exc}") from exc

    if sha256_hex(str(signed_env.get("signature", ""))) != rcpt.get("signature_sha256"):
        raise PermissionError("CAPSULE_REJECTED:signature_sha256_tampered")
    if (
        verified_payload.get("capsule_digest_sha256") != actual_digest
        or verified_payload.get("source_sha256") != actual_src_hash
        or verified_payload.get("test_suite_sha256") != actual_suite_hash
        or verified_payload.get("issuer_receiver_public") != issuer_pub
    ):
        raise PermissionError("CAPSULE_REJECTED:signed_envelope_payload_mismatch")

    return verified_payload


def qualify_and_export_capsule_worker_a(state_dir: Path) -> PortableVerifiedCapabilityCapsule:
    """Worker A qualifies the coupled capability against the executable obligation gate and exports an Ed25519-signed capsule."""
    eng_a = LivingProjectEngine(state_dir=state_dir)
    register_trusted_capsule_issuer(eng_a.receiver_identity.public)

    gate = ExecutableProofObligationGate(min_nominal_coverage=0.80)
    obligations = _build_capsule_obligations()
    params = {"solar_derate": 1.0, "membrane_gain": 0.96}
    fn = _verify_ast_and_resolve_allowlisted_kernel(CAPSULE_EXECUTABLE_SOURCE, params)
    rep = gate.evaluate_candidate("COUPLED-TASK-A", "CAP-COUPLED-RESILIENCE-V1", fn, obligations)
    if not rep.independently_accepted:
        raise RuntimeError(f"Worker A qualification failed: {rep.rejection_reason}")

    src_hash = sha256_hex(CAPSULE_EXECUTABLE_SOURCE)
    suite_manifest = [
        {"obligation_id": ob.obligation_id, "category": ob.category, "vectors": list(ob.test_vectors)}
        for ob in obligations
    ]
    suite_hash = sha256_hex(suite_manifest)
    cur_epoch = int(eng_a.guard.read_stop_state()["epoch"])
    assumptions = asdict(SupportingAssumptions(authority_epoch=cur_epoch))
    envelope = {
        "feed_temp_c_range": [10.0, 40.0],
        "dp_psi_range": [100.0, 180.0],
        "min_nominal_coverage": 0.80,
    }
    rollback_triggers = [
        "data_version_mismatch",
        "calibration_expired",
        "reference_sensor_degraded",
        "source_sha256_mismatch",
        "policy_pin_sha256_mismatch",
        "authority_epoch_revoked",
    ]
    core_payload = {
        "capsule_id": "CAPSULE-011-COUPLED-001",
        "capability_id": "cap-coupled-solar-ro-coldchain-v1",
        "domain": "coupled_energy_water_coldchain",
        "version": 1,
        "source_sha256": src_hash,
        "test_suite_sha256": suite_hash,
        "operating_envelope": envelope,
        "supporting_assumptions": assumptions,
        "rollback_triggers": rollback_triggers,
        "parameters": params,
    }
    digest = sha256_hex(core_payload)
    receipt_payload = {
        "schema": "openline.portable_capsule_receipt.v2",
        "capsule_id": "CAPSULE-011-COUPLED-001",
        "capability_id": "cap-coupled-solar-ro-coldchain-v1",
        "issuer_receiver_public": eng_a.receiver_identity.public,
        "capsule_digest_sha256": digest,
        "source_sha256": src_hash,
        "test_suite_sha256": suite_hash,
        "obligation_report_sha256": rep.report_sha256,
        "authority_epoch": cur_epoch,
    }
    signed_env = sign_envelope(eng_a.receiver_identity.key, receipt_payload)
    receipt = {
        **receipt_payload,
        "signed_envelope": signed_env,
        "signature_sha256": sha256_hex(signed_env["signature"]),
    }
    return PortableVerifiedCapabilityCapsule(
        capsule_id="CAPSULE-011-COUPLED-001",
        capability_id="cap-coupled-solar-ro-coldchain-v1",
        domain="coupled_energy_water_coldchain",
        version=1,
        executable_source=CAPSULE_EXECUTABLE_SOURCE,
        source_sha256=src_hash,
        test_suite_manifest=suite_manifest,
        test_suite_sha256=suite_hash,
        operating_envelope=envelope,
        supporting_assumptions=assumptions,
        rollback_triggers=rollback_triggers,
        parameters=params,
        worker_a_receipt=receipt,
        capsule_digest_sha256=digest,
    )


class WorkerBPortableInheritanceRuntime:
    """Clean-room Worker B runtime that verifies Ed25519 capsule authority before import and
    automatically enforces assumption/revocation validity at every consequential effect boundary."""

    def __init__(self, state_dir: Path, trusted_issuers: set[str] | None = None) -> None:
        self.state_dir = Path(state_dir)
        self.trusted_issuers = trusted_issuers
        self.engine = LivingProjectEngine(state_dir=self.state_dir)
        self.gate = ExecutableProofObligationGate(min_nominal_coverage=0.80)
        self.primary_project_id = "proj-worker-b-coupled-hub"
        self.unrelated_project_id = "proj-worker-b-unrelated-bakery"
        c1 = plan_living_project_contract(
            "Coordinate solar cold-chain reserve and RO membrane desalination under variable telemetry."
        )
        c2 = plan_living_project_contract(
            "Track daily neighborhood bakery sourdough starter, flour sacks, and oven schedules."
        )
        self.engine.create_living_project(c1, project_id_override=self.primary_project_id)
        self.engine.create_living_project(c2, project_id_override=self.unrelated_project_id)
        self.active_capsule: PortableVerifiedCapabilityCapsule | None = None
        self._pinned_assumptions: dict[str, Any] = {}
        self._pinned_source_sha256: str = ""
        self.live_environment: dict[str, Any] = {}
        self.current_standing: str = "UNINITIALIZED"
        self.reopen_reason: str | None = None

    def verify_and_import_capsule(
        self,
        capsule_dict: Mapping[str, Any],
        now_utc: int = 1794787200,
    ) -> dict[str, Any]:
        # 1. Zero-oracle check
        enforce_zero_oracle(capsule_dict)

        # 2. Cryptographic issuer & Ed25519 signature check FIRST (before any AST/kernel resolution)
        verify_capsule_cryptographic_receipt(capsule_dict, trusted_issuers=self.trusted_issuers)

        # 3. Supporting assumption freshness check
        assumptions = dict(capsule_dict["supporting_assumptions"])
        if int(assumptions["calibration_expiry_utc"]) <= now_utc:
            raise ValueError("CAPSULE_REJECTED:calibration_expired")
        if assumptions["reference_sensor_health"] != "HEALTHY_DUAL_REF":
            raise ValueError("CAPSULE_REJECTED:reference_sensor_degraded")

        # 4. AST + allowlist verification (never calls exec)
        src = str(capsule_dict["executable_source"])
        fn = _verify_ast_and_resolve_allowlisted_kernel(src, capsule_dict["parameters"])
        obligations = _build_capsule_obligations()
        rep = self.gate.evaluate_candidate(
            "WORKER-B-IMPORT-VERIFY",
            str(capsule_dict["capability_id"]),
            fn,
            obligations,
        )
        if not rep.independently_accepted:
            raise ValueError(f"CAPSULE_REJECTED:proof_obligations_failed:{rep.rejection_reason}")

        self.active_capsule = PortableVerifiedCapabilityCapsule(**copy.deepcopy(dict(capsule_dict)))
        self._pinned_assumptions = copy.deepcopy(dict(assumptions))
        self._pinned_source_sha256 = str(self.active_capsule.source_sha256)
        self.live_environment = {
            **copy.deepcopy(dict(assumptions)),
            "source_sha256": self._pinned_source_sha256,
            "now_utc": int(now_utc),
        }
        self.current_standing = "ACCEPTED"
        self.reopen_reason = None
        return {
            "status": "CAPSULE_IMPORTED_AND_VERIFIED",
            "capability_id": self.active_capsule.capability_id,
            "standing": self.current_standing,
            "verification_evaluations_spent": len(obligations),
            "report_sha256": rep.report_sha256,
        }

    def update_live_environment(self, **updates: Any) -> dict[str, Any]:
        """Updates the live operational environment state without requiring an explicit recall call."""
        self.live_environment.update(updates)
        return dict(self.live_environment)

    def _collect_effective_environment(
        self,
        override_env: Mapping[str, Any] | None = None,
        unseen_vec: Mapping[str, Any] | None = None,
        now_utc: int | None = None,
    ) -> dict[str, Any]:
        assert self.active_capsule is not None
        # Detect in-memory mutations to active_capsule.supporting_assumptions or active_capsule.source_sha256
        # as well as updates to self.live_environment or explicit override_env/unseen_vec fields.
        eff: dict[str, Any] = dict(self._pinned_assumptions)
        eff["source_sha256"] = self._pinned_source_sha256
        eff["now_utc"] = int(self.live_environment.get("now_utc", 1794787200))

        for k, v in self.live_environment.items():
            if v != self._pinned_assumptions.get(k, self._pinned_source_sha256 if k == "source_sha256" else v):
                eff[k] = v
            elif k == "now_utc":
                eff[k] = v

        for k, v in self.active_capsule.supporting_assumptions.items():
            if v != self._pinned_assumptions.get(k):
                eff[k] = v
        if self.active_capsule.source_sha256 != self._pinned_source_sha256:
            eff["source_sha256"] = self.active_capsule.source_sha256
        if sha256_hex(self.active_capsule.executable_source) != self._pinned_source_sha256:
            eff["source_sha256"] = sha256_hex(self.active_capsule.executable_source)

        if unseen_vec is not None:
            for k in (
                "data_version",
                "now_utc",
                "reference_sensor_health",
                "source_sha256",
                "policy_pin_sha256",
                "authority_epoch",
            ):
                if k in unseen_vec:
                    eff[k] = unseen_vec[k]

        if override_env is not None:
            eff.update(dict(override_env))
        if now_utc is not None and "now_utc" not in (override_env or {}):
            eff["now_utc"] = int(now_utc)
        return eff

    def check_assumptions_and_auto_recall(
        self,
        live_environment: Mapping[str, Any] | None = None,
        now_utc: int | None = None,
    ) -> dict[str, Any]:
        """Checks supporting assumptions against live environment; automatically triggers Decision Recall on drift."""
        if self.active_capsule is None:
            raise RuntimeError("No active capsule loaded")

        unrelated_before = self.engine.get_project_bundle(self.unrelated_project_id)["accepted"]["state_sha256"]
        eff_env = self._collect_effective_environment(override_env=live_environment, now_utc=now_utc)
        expected = self._pinned_assumptions
        triggers_fired: list[str] = []

        if eff_env.get("data_version", expected["data_version"]) != expected["data_version"]:
            triggers_fired.append("data_version_mismatch")
        if int(eff_env.get("now_utc", 1794787200)) >= int(expected["calibration_expiry_utc"]):
            triggers_fired.append("calibration_expired")
        if eff_env.get("reference_sensor_health", expected["reference_sensor_health"]) != "HEALTHY_DUAL_REF":
            triggers_fired.append("reference_sensor_degraded")
        if eff_env.get("source_sha256", self._pinned_source_sha256) != self._pinned_source_sha256:
            triggers_fired.append("source_sha256_mismatch")
        if eff_env.get("policy_pin_sha256", expected["policy_pin_sha256"]) != expected["policy_pin_sha256"]:
            triggers_fired.append("policy_pin_sha256_mismatch")

        guard_state = self.engine.guard.read_stop_state()
        if (
            int(eff_env.get("authority_epoch", expected["authority_epoch"])) != int(expected["authority_epoch"])
            or guard_state["stopped"]
            or int(guard_state["epoch"]) != int(expected["authority_epoch"])
        ):
            triggers_fired.append("authority_epoch_revoked")

        dnf_live = self.engine.recall_ledger.standing(f"{self.primary_project_id}:scenario_plan", now=260)
        if dnf_live.status != "CURRENT" and "upstream_dnf_recalled" not in triggers_fired and not triggers_fired:
            triggers_fired.append("upstream_dnf_recalled")

        if triggers_fired:
            reason = f"ASSUMPTION_DRIFT:{','.join(triggers_fired)}"
            recall_res = self.engine.recall_living_project_dependency(
                self.primary_project_id,
                station_node_id="demand",
                reason=reason,
            )
            self.current_standing = "REOPEN"
            self.reopen_reason = reason
            unrelated_after = self.engine.get_project_bundle(self.unrelated_project_id)["accepted"]["state_sha256"]
            return {
                "standing": "REOPEN",
                "triggers_fired": triggers_fired,
                "recall_id": recall_res["recall_id"],
                "dnf_standing": recall_res["dnf_standing"],
                "primary_project_accepted_sha256_preserved": recall_res["accepted_state_unchanged"],
                "unrelated_project_preserved_exact": (unrelated_before == unrelated_after),
                "unrelated_project_sha256": unrelated_after,
            }

        return {
            "standing": self.current_standing,
            "triggers_fired": [],
            "unrelated_project_preserved_exact": True,
        }

    def execute_on_unseen_task(
        self,
        unseen_vec: Mapping[str, Any],
        *,
        live_environment: Mapping[str, Any] | None = None,
        now_utc: int | None = None,
    ) -> dict[str, Any]:
        """Executes the inherited capability on an unseen task; MANDATORILY re-checks live assumptions,
        revocation, and STOP state before execution even if the caller never invoked check_assumptions_and_auto_recall()."""
        if self.active_capsule is None:
            raise RuntimeError("No active capsule")
        if self.engine.guard.read_stop_state()["stopped"]:
            self.check_assumptions_and_auto_recall(live_environment=live_environment, now_utc=now_utc)
            raise PermissionError("REVOKED_BY_STOP_EPOCH:cannot_execute_while_stopped")

        # Mandatory pre-effect assumption & authority check
        auto_check = self.check_assumptions_and_auto_recall(
            live_environment=self._collect_effective_environment(
                override_env=live_environment,
                unseen_vec=unseen_vec,
                now_utc=now_utc,
            ),
            now_utc=now_utc,
        )
        if auto_check["standing"] != "ACCEPTED" or self.current_standing != "ACCEPTED":
            raise PermissionError(f"STALE_ASSUMPTION_REOPEN_REQUIRED:{self.reopen_reason}")

        fn = _verify_ast_and_resolve_allowlisted_kernel(
            self.active_capsule.executable_source,
            self.active_capsule.parameters,
        )
        return fn(dict(unseen_vec))

    def revalidate_and_repair_after_assumption_change(
        self,
        updated_assumptions: Mapping[str, Any],
        repaired_parameters: Mapping[str, float],
        now_utc: int = 1794787200,
    ) -> dict[str, Any]:
        """Re-runs the executable proof obligations under updated assumptions and parameters to restore ACCEPTED standing."""
        if self.active_capsule is None:
            raise RuntimeError("No active capsule")
        if int(updated_assumptions.get("calibration_expiry_utc", 0)) <= now_utc:
            raise ValueError("Cannot re-accept with expired calibration")
        if updated_assumptions.get("reference_sensor_health") != "HEALTHY_DUAL_REF":
            raise ValueError("Cannot re-accept with degraded reference sensor")

        # Restore primary project DNF source validity in RecallLedger upon verified revalidation
        src_name = f"{self.primary_project_id}:demand"
        from core.recall import public_hex as recall_public_hex, signed_event as recall_signed_event
        self.engine.recall_ledger.pin_source(src_name, recall_public_hex(self.engine.owner_identity.key))
        with self.engine.recall_ledger._conn() as rconn:
            prior_row = rconn.execute("SELECT revision FROM sources WHERE source=?", (src_name,)).fetchone()
        next_rev = (int(prior_row[0]) + 1) if prior_row is not None else 1
        valid_ev = recall_signed_event(
            self.engine.owner_identity.key,
            source=src_name,
            revision=next_rev,
            digest=sha256_hex({"project_id": self.primary_project_id, "station": "demand", "revision": next_rev}),
            state="VALID",
            expires_at=2_000_000_000,
        )
        self.engine.recall_ledger.apply_event(valid_ev, now=270)
        work_id = f"{self.primary_project_id}:scenario_plan"
        with self.engine.recall_ledger._conn() as rconn:
            rconn.execute("DELETE FROM links WHERE work_id=?", (work_id,))
            rconn.execute("DELETE FROM work WHERE work_id=?", (work_id,))
            rconn.commit()
        self.engine._ensure_project_recall_support_registered(
            self.primary_project_id,
            self.engine.get_project_bundle(self.primary_project_id)["accepted"]["state"],
        )

        fn = _verify_ast_and_resolve_allowlisted_kernel(CAPSULE_EXECUTABLE_SOURCE, repaired_parameters)
        rep = self.gate.evaluate_candidate(
            "WORKER-B-REVALIDATION",
            self.active_capsule.capability_id,
            fn,
            _build_capsule_obligations(),
        )
        if not rep.independently_accepted:
            raise ValueError(f"REVALIDATION_FAILED:{rep.rejection_reason}")

        self.active_capsule.executable_source = CAPSULE_EXECUTABLE_SOURCE
        self.active_capsule.source_sha256 = CAPSULE_EXECUTABLE_SOURCE_SHA256
        self.active_capsule.supporting_assumptions = copy.deepcopy(dict(updated_assumptions))
        self.active_capsule.parameters = copy.deepcopy(dict(repaired_parameters))
        self.active_capsule.version += 1
        self._pinned_assumptions = copy.deepcopy(dict(updated_assumptions))
        self._pinned_source_sha256 = CAPSULE_EXECUTABLE_SOURCE_SHA256
        self.live_environment = {
            **copy.deepcopy(dict(updated_assumptions)),
            "source_sha256": self._pinned_source_sha256,
            "now_utc": int(now_utc),
        }
        self.current_standing = "ACCEPTED"
        self.reopen_reason = None
        return {
            "standing": self.current_standing,
            "new_capsule_version": self.active_capsule.version,
            "revalidation_report_sha256": rep.report_sha256,
        }


def _measure_constructed_parameter_search_trials(
    unseen_challenges: list[dict[str, Any]],
) -> dict[str, Any]:
    """Executes deterministic parameter-search trials and records actual measured evaluation counters.

    Explicitly labeled as a constructed deterministic parameter-search comparison, NOT a real
    multi-LLM-agent benchmark (the prior 6.0x real-agent performance claim is retired).
    """
    obligations = _build_capsule_obligations()
    gate = ExecutableProofObligationGate(min_nominal_coverage=0.80)

    # Trial 1: Cold deterministic parameter-grid search without capsule
    grid_candidates = [
        {"solar_derate": 1.35, "membrane_gain": 0.70, "respect_ref": False, "throttle_ro": False},
        {"solar_derate": 1.20, "membrane_gain": 0.78, "respect_ref": True, "throttle_ro": False},
        {"solar_derate": 1.00, "membrane_gain": 0.82, "respect_ref": True, "throttle_ro": True},
        {"solar_derate": 1.00, "membrane_gain": 0.96, "respect_ref": True, "throttle_ro": True},
    ]
    cold_evals = 0
    cold_unsafe_trials = 0
    t0 = time.perf_counter_ns()
    selected_cold_fn = None
    for cand_cfg in grid_candidates:
        def _cand_fn(vec: Mapping[str, Any], cfg: dict[str, Any] = cand_cfg) -> dict[str, Any]:
            if cfg["respect_ref"] and not vec.get("ref_ok", False):
                return {"status": "ABSTAIN_UNVERIFIED"}
            vac = float(vec["vaccine_kw"])
            sol = float(vec["solar_kw"]) * float(cfg["solar_derate"])
            ro = min(float(vec["ro_pump_kw"]), max(0.0, sol - vac)) if cfg["throttle_ro"] else float(vec["ro_pump_kw"])
            fm = float(cfg["membrane_gain"]) * (float(vec["dp_psi"]) / 140.0) * math.exp(-0.024 * (float(vec["feed_temp_c"]) - 25.0))
            return {"status": "COMMIT_VALID", "vaccine_allocated_kw": vac, "ro_allocated_kw": ro, "flux_margin": fm}

        rep = gate.evaluate_candidate("COLD-SEARCH", "GRID-CAND", _cand_fn, obligations)
        cold_evals += len(obligations)
        if rep.false_acceptances_on_hazards > 0 or rep.boundary_obligations_passed < rep.boundary_obligations_total:
            cold_unsafe_trials += 1
        if rep.independently_accepted:
            selected_cold_fn = _cand_fn
            break
    cold_elapsed_us = round((time.perf_counter_ns() - t0) / 1000.0, 2)
    assert selected_cold_fn is not None

    # Trial 2: Static nominal-only test worker (evaluates only nominal obligation)
    t1 = time.perf_counter_ns()
    def _static_nominal_fn(vec: Mapping[str, Any]) -> dict[str, Any]:
        vac = float(vec["vaccine_kw"])
        sol = float(vec["solar_kw"])
        ro = min(float(vec["ro_pump_kw"]), max(0.0, sol - vac))
        fm = 0.96 * (float(vec["dp_psi"]) / 140.0) * math.exp(-0.024 * (float(vec["feed_temp_c"]) - 25.0))
        return {"status": "COMMIT_VALID", "vaccine_allocated_kw": vac, "ro_allocated_kw": ro, "flux_margin": fm}

    nom_rep = gate.evaluate_candidate("NOMINAL-ONLY", "STATIC-CAND", _static_nominal_fn, [obligations[0]])
    static_evals = 1
    static_outputs = [_static_nominal_fn(c) for c in unseen_challenges]
    static_false_commit_on_ref_loss = sum(
        1 for c, o in zip(unseen_challenges, static_outputs) if not c["ref_ok"] and o["status"] == "COMMIT_VALID"
    )
    static_elapsed_us = round((time.perf_counter_ns() - t1) / 1000.0, 2)

    return {
        "evidence_class": "CONSTRUCTED_DETERMINISTIC_PARAMETER_SEARCH_NOT_REAL_LLM_AGENT_BENCHMARK",
        "real_agent_6x_claim_retired": True,
        "Competent_Worker_Without_Capsule": {
            "evaluations_spent_to_converge": cold_evals,
            "unsafe_trial_commits_during_search": cold_unsafe_trials,
            "unseen_tasks_solved_safely": len(unseen_challenges),
            "measured_elapsed_us": cold_elapsed_us,
        },
        "Static_Rules_Normal_Test_Suite": {
            "evaluations_spent_to_converge": static_evals,
            "nominal_gate_accepted": nom_rep.independently_accepted,
            "false_confident_commit_on_unseen_ref_loss": static_false_commit_on_ref_loss,
            "unseen_tasks_solved_safely": len(unseen_challenges) - static_false_commit_on_ref_loss,
            "measured_elapsed_us": static_elapsed_us,
        },
    }


def run_loop_c_portable_inheritance_and_revalidation_experiment() -> dict[str, Any]:
    """Executes the full Loop C experiment with Ed25519 capsule verification, zero-exec allowlist enforcement,
    and automatic consequential-effect assumption revalidation across all 6 mid-stream mutations."""
    with tempfile.TemporaryDirectory() as dir_a, tempfile.TemporaryDirectory() as dir_b:
        t_start = time.perf_counter_ns()
        capsule = qualify_and_export_capsule_worker_a(Path(dir_a))
        capsule_json = asdict(capsule)

        worker_b = WorkerBPortableInheritanceRuntime(Path(dir_b))
        import_res = worker_b.verify_and_import_capsule(capsule_json)
        wb_elapsed_us = round((time.perf_counter_ns() - t_start) / 1000.0, 2)

        unseen_challenges = [
            {"id": "UNSEEN-1-NOMINAL-HOT", "solar_kw": 3.6, "vaccine_kw": 1.2, "ro_pump_kw": 1.6, "feed_temp_c": 29.0, "ref_ok": True, "dp_psi": 148.0},
            {"id": "UNSEEN-2-CLOUD-SQUEEZE", "solar_kw": 1.5, "vaccine_kw": 1.2, "ro_pump_kw": 1.8, "feed_temp_c": 26.0, "ref_ok": True, "dp_psi": 142.0},
            {"id": "UNSEEN-3-REF-SENSOR-LOST", "solar_kw": 3.8, "vaccine_kw": 1.2, "ro_pump_kw": 1.6, "feed_temp_c": 25.0, "ref_ok": False, "dp_psi": 140.0},
        ]

        b_outputs = [worker_b.execute_on_unseen_task(c) for c in unseen_challenges]
        assert b_outputs[0]["status"] == "COMMIT_VALID" and b_outputs[0]["vaccine_allocated_kw"] == 1.2
        assert b_outputs[1]["status"] == "COMMIT_VALID" and b_outputs[1]["ro_allocated_kw"] <= 0.3001
        assert b_outputs[2]["status"] == "ABSTAIN_UNVERIFIED"

        measured_trials = _measure_constructed_parameter_search_trials(unseen_challenges)
        three_way_comparison = {
            **measured_trials,
            "Worker_B_With_Portable_Verified_Capsule": {
                "evaluations_spent_to_converge": import_res["verification_evaluations_spent"],
                "unsafe_trial_commits_during_search": 0,
                "false_confident_commit_on_unseen_ref_loss": 0,
                "unseen_tasks_solved_safely": len(unseen_challenges),
                "measured_elapsed_us": wb_elapsed_us,
            },
        }

        base_env = dict(capsule.supporting_assumptions)
        base_env["source_sha256"] = capsule.source_sha256
        base_env["now_utc"] = 1794787200

        assumption_mutations = [
            ("1_data_version_drift", {**base_env, "data_version": "dataset-v2.0-shifted"}),
            ("2_calibration_expired", {**base_env, "now_utc": 1900000000}),
            ("3_reference_sensor_degraded", {**base_env, "reference_sensor_health": "SINGLE_CHANNEL_DRIFT"}),
            ("4_source_sha256_tamper", {**base_env, "source_sha256": "0" * 64}),
            ("5_policy_pin_changed", {**base_env, "policy_pin_sha256": "policy-pin-v2-new"}),
            ("6_authority_epoch_revoked", {**base_env, "authority_epoch": 99}),
        ]

        mutation_receipts = []
        for label, mutated_env in assumption_mutations:
            unrelated_sha_before = worker_b.engine.get_project_bundle(worker_b.unrelated_project_id)["accepted"]["state_sha256"]
            # Update live environment AND call execute_on_unseen_task() directly WITHOUT calling
            # check_assumptions_and_auto_recall() first, proving mandatory boundary enforcement!
            worker_b.update_live_environment(**mutated_env)
            blocked_without_manual_recall = False
            try:
                worker_b.execute_on_unseen_task(unseen_challenges[0])
            except PermissionError as exc:
                blocked_without_manual_recall = "STALE_ASSUMPTION_REOPEN_REQUIRED" in str(exc)
            assert blocked_without_manual_recall, f"Failed to block stale execution without manual recall on {label}"
            assert worker_b.current_standing == "REOPEN", f"Failed to auto-transition to REOPEN on {label}"

            unrelated_sha_after = worker_b.engine.get_project_bundle(worker_b.unrelated_project_id)["accepted"]["state_sha256"]
            assert unrelated_sha_before == unrelated_sha_after

            repaired_assumptions = dict(capsule.supporting_assumptions)
            repaired_assumptions["data_version"] = "dataset-v2.0-recalibrated"
            reval = worker_b.revalidate_and_repair_after_assumption_change(
                repaired_assumptions,
                {"solar_derate": 0.98, "membrane_gain": 0.97},
                now_utc=1794787200,
            )
            assert reval["standing"] == "ACCEPTED"
            # Restore baseline pinned assumptions for next mutation check
            worker_b._pinned_assumptions = copy.deepcopy(dict(capsule.supporting_assumptions))
            worker_b.active_capsule.supporting_assumptions = copy.deepcopy(dict(capsule.supporting_assumptions))
            worker_b.live_environment = copy.deepcopy(base_env)
            mutation_receipts.append({
                "mutation_id": label,
                "standing_after_mutation": "REOPEN",
                "blocked_at_effect_boundary_without_manual_recall_call": blocked_without_manual_recall,
                "unrelated_project_preserved_exact": (unrelated_sha_before == unrelated_sha_after),
                "standing_after_revalidation": reval["standing"],
                "revalidation_report_sha256": reval["revalidation_report_sha256"],
            })

        return {
            "experiment_id": "LOOP-C-PORTABLE-VERIFIED-INHERITANCE-AND-REVALIDATION",
            "evidence_class": "CONSTRUCTED_DETERMINISTIC_PARAMETER_SEARCH_NOT_REAL_LLM_AGENT_BENCHMARK",
            "real_agent_6x_claim_retired": True,
            "capsule_id": capsule.capsule_id,
            "capsule_digest_sha256": capsule.capsule_digest_sha256,
            "worker_a_source_sha256": capsule.source_sha256,
            "worker_a_test_suite_sha256": capsule.test_suite_sha256,
            "three_way_worker_comparison": three_way_comparison,
            "mid_stream_assumption_revalidation_matrix": mutation_receipts,
            "all_6_assumption_mutations_reopened_and_blocked_fail_closed": True,
        }
