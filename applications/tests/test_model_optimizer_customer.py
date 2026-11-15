#!/usr/bin/env python3
"""Customer-facing neural optimizer tests (`test_model_optimizer_customer.py`).

Re-homed in Phase C2 from a removed research test file (the removed file
is preserved privately): test_01–test_03 are the direct
tests of the RETAINED customer-facing optimizer (`core/model_optimizer.py`)
— analytical gradients, checkpoint roundtrip + evaluator signing authority,
and the full multi-generation campaign. The research-surface assertions
were dropped with the F-21 research surface (that outcome no longer exists);
test_04 (research endpoints) was NOT re-homed — it exercised removed code.

F-22 (v0.7.1): `EvaluatorHoldoutAuthority` now generates a fresh
cryptographically random per-run Ed25519 key (`secrets.token_bytes(32)`)
unless an explicit `seed_bytes` is passed by the caller for a test.
test_02 asserts the new properties: fresh key per run, the receipt signature
verifies under the published per-run public key, and an explicit seed
reproduces a key. Receipts are lab-internal research fingerprints, not
independent evaluation authority.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
import sys
import unittest

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model_optimizer import (
    EvaluatorHoldoutAuthority,
    ExecutableNeuralCheckpoint,
    build_optimization_task_dataset,
    run_genuine_model_optimization_campaign,
)
from core.openline_guard import VerificationError, verify_envelope


class NeuralModelOptimizationCustomerSuite(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_01_analytical_gradients_match_numerical_finite_differences(self) -> None:
        """Proves the neural network engine computes true analytical backprop gradients."""
        ds = build_optimization_task_dataset("primary_sensor_reasoning_v1", seed=20261111)
        ckpt = ds["baseline_checkpoint"].copy()
        X = ds["X_train"][:16]
        y = ds["y_train"][:16]
        _, grads = ckpt.compute_gradients(X, y, l2_reg=1e-4)

        eps = 1e-3
        for layer in ("W1", "W2", "W3"):
            idx = (0, 0)
            orig_val = float(ckpt.weights[layer][idx])
            ckpt.weights[layer][idx] = orig_val + eps
            loss_plus, _ = ckpt.compute_gradients(X, y, l2_reg=1e-4)
            ckpt.weights[layer][idx] = orig_val - eps
            loss_minus, _ = ckpt.compute_gradients(X, y, l2_reg=1e-4)
            ckpt.weights[layer][idx] = orig_val
            num_grad = (loss_plus - loss_minus) / (2.0 * eps)
            ana_grad = float(grads[layer][idx])
            self.assertAlmostEqual(num_grad, ana_grad, places=2, msg=f"Gradient mismatch on {layer}")

    def test_02_checkpoint_roundtrip_and_evaluator_signing_authority(self) -> None:
        """Verifies checkpoint save/load SHA-256 identity and lab-internal evaluator receipt signing."""
        ds = build_optimization_task_dataset("primary_sensor_reasoning_v1", seed=20261111)
        ckpt = ds["baseline_checkpoint"]
        saved = ckpt.save(self.tmp_path / "test_ckpt.npz")
        loaded = ExecutableNeuralCheckpoint.load(saved["path"])
        self.assertEqual(ckpt.sha256(), loaded.sha256())
        self.assertEqual(saved["weights_sha256"], loaded.sha256())

        evaluator = EvaluatorHoldoutAuthority(ds)
        cert = evaluator.certify_on_sealed_holdout(loaded)
        body = verify_envelope(cert["evaluator_receipt"], expected_pub=cert["evaluator_public_key"])
        self.assertEqual(body["checkpoint_sha256"], loaded.sha256())
        self.assertEqual(body["status"], "CERTIFIED_PASS")
        # Receipt is explicitly research-scoped, not independent verification.
        self.assertIn("research-only", body["scope"])
        self.assertIn("not independent evaluation authority", body["scope"])

        # Optimizer / untrusted key cannot verify as evaluator
        with self.assertRaises(VerificationError):
            verify_envelope(cert["evaluator_receipt"], expected_pub="0" * 43)

        # F-22: fresh random key per run — two evaluators on the same dataset
        # have different public keys, and neither equals a deterministic
        # task-id-derived key.
        evaluator2 = EvaluatorHoldoutAuthority(ds)
        self.assertNotEqual(
            evaluator.evaluator_identity.public,
            evaluator2.evaluator_identity.public,
            "evaluator key must be fresh per run, not derived from the task id",
        )
        cert2 = evaluator2.certify_on_sealed_holdout(loaded)
        body2 = verify_envelope(cert2["evaluator_receipt"], expected_pub=cert2["evaluator_public_key"])
        self.assertEqual(body2["checkpoint_sha256"], loaded.sha256())
        # Same checkpoint fingerprint under a different per-run key: the
        # fingerprint is reproducible, the signature is not.
        self.assertEqual(cert["metrics"]["checkpoint_sha256"], cert2["metrics"]["checkpoint_sha256"])

        # Explicit seed_bytes (test-only path) reproduces a key.
        seeded_a = EvaluatorHoldoutAuthority(ds, seed_bytes=b"\x01" * 32)
        seeded_b = EvaluatorHoldoutAuthority(ds, seed_bytes=b"\x01" * 32)
        self.assertEqual(seeded_a.evaluator_identity.public, seeded_b.evaluator_identity.public)
        self.assertNotEqual(seeded_a.evaluator_identity.public, evaluator.evaluator_identity.public)

    def test_03_multi_generation_optimization_transfer_overfit_and_three_outcomes(self) -> None:
        """Runs the full 3-generation optimization campaign, transfer task, overfit falsifier, and outcome classification."""
        report = run_genuine_model_optimization_campaign(self.tmp_path / "campaign")
        gens = report["generations"]
        self.assertEqual(len(gens), 4)  # Gen 0, Gen 1, Gen 2, Gen 3

        m0 = gens[0]["certification"]["metrics"]
        m1 = gens[1]["certification"]["metrics"]
        m2 = gens[2]["certification"]["metrics"]
        m3 = gens[3]["certification"]["metrics"]

        # Non-regression holds across every accepted generation
        self.assertTrue(m0["non_regression_passed"])
        self.assertTrue(m1["non_regression_passed"])
        self.assertTrue(m2["non_regression_passed"])
        self.assertTrue(m3["non_regression_passed"])

        # Monotonic composite frontier progression
        self.assertLess(m0["composite_frontier_score"], m1["composite_frontier_score"])
        self.assertLess(m1["composite_frontier_score"], m2["composite_frontier_score"])
        self.assertLess(m2["composite_frontier_score"], m3["composite_frontier_score"])

        # Substantial capability, calibration, robustness, and memory-footprint gains
        self.assertGreater(m3["clean_accuracy"] - m0["clean_accuracy"], 0.20)
        self.assertGreater(m3["reasoning_accuracy"] - m0["reasoning_accuracy"], 0.20)
        self.assertGreater(m3["shifted_accuracy"] - m0["shifted_accuracy"], 0.20)
        self.assertLess(m3["ece_calibration_error"], m0["ece_calibration_error"])
        self.assertLess(
            m3["parameter_stats"]["effective_checkpoint_bytes"],
            m0["parameter_stats"]["effective_checkpoint_bytes"] * 0.30,
        )

        # Beats competent conventional SGD comparator
        conv_m = report["conventional_comparator"]["certification"]["metrics"]
        self.assertGreater(m3["composite_frontier_score"], conv_m["composite_frontier_score"] + 0.08)

        # Adverse naive pruning before spectral repair fails non-regression
        prune_m = report["adverse_clamped_pruning_probe"]["certification"]["metrics"]
        self.assertFalse(prune_m["non_regression_passed"])

        # Validation overfitting probe is caught and quarantined
        overfit = report["validation_overfitting_probe"]
        self.assertTrue(overfit["overfit_detected"])
        self.assertGreater(overfit["val_holdout_gap"], 0.12)
        self.assertEqual(overfit["certification_status"], "REFUSED_REGRESSION_OR_OVERFIT")
        self.assertEqual(overfit["action_taken"], "STOP_AND_QUARANTINE_OVERFIT_CANDIDATE")

        # Outcome classification: better_model, better_optimizer,
        # transferable_optimizer all True. (The removed research outcome
        # is NOT asserted here; the assertNotIn below confirms its absence.)
        outcomes = report["four_outcome_classification"]
        self.assertTrue(outcomes["better_model"]["achieved"])
        self.assertTrue(outcomes["better_optimizer"]["achieved"])
        self.assertTrue(outcomes["transferable_optimizer"]["achieved"])
        self.assertNotIn("durable_competitive_advantage", outcomes)

        # F-22: campaign publishes a fresh per-run evaluator public key and
        # states its research scope; receipts verify under it.
        self.assertIn("research-only", report["evaluator_scope"])
        self.assertIn("not establish independent evaluation authority", report["evaluator_scope"])
        gen3_receipt = gens[3]["certification"]["evaluator_receipt"]
        gen3_body = verify_envelope(
            gen3_receipt, expected_pub=report["evaluator_public_key"]
        )
        self.assertEqual(gen3_body["checkpoint_sha256"], gens[3]["certification"]["metrics"]["checkpoint_sha256"])


if __name__ == "__main__":
    unittest.main()
