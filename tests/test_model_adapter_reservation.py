#!/usr/bin/env python3
"""RC6 closeout blocker 2 (R5-B2): reservation-based spend-cap enforcement.

Defect: spend was recorded from response usage fields only. A dispatched
call whose response carried no usage block (or whose failure happened
after dispatch) recorded $0.00, so the ledger total was a lower bound and
the $5.00 cap could be exceeded by spend the ledger never saw.

Fix: before ANY model call the adapter reserves the worst-case cost
(estimated input tokens at the model's published input rate + the full
requested max_tokens at the output rate) against the remaining cap, and
persists that reservation in spend.json BEFORE dispatch. If the
reservation would exceed the remaining cap the call is REFUSED before
dispatch. After the call the reservation is reconciled to actual usage
when usage is present; when usage is missing (or the call fails after
dispatch) the reservation STANDS as the recorded spend -- worst-case
charged, never $0 for a dispatched call. A provider rejection
(_http_error, e.g. 429/529: the request was refused, nothing generated)
RELEASES the reservation at $0.

Mocked helper responses only -- zero model spend. All ledgers are
temporary directories; the real spend.json is never touched.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.model_adapter import (  # noqa: E402
    AnthropicAdapter,
    ModelError,
    SpendCapExceeded,
    SpendLedger,
    cost_usd,
)


def _fake_run_factory(payload):
    def _fake_run(*args, **kwargs):
        return subprocess.CompletedProcess(
            args=args[0] if args else [], returncode=0,
            stdout=json.dumps(payload), stderr="",
        )
    return _fake_run


def _ledger_data(tmp):
    path = Path(tmp) / "spend.json"
    if not path.exists():
        return {"total_usd": 0.0, "cap_usd": 5.0, "calls": [], "reservations": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _open_reserved_usd(tmp):
    data = _ledger_data(tmp)
    return sum(
        float(r.get("reserved_usd", 0.0))
        for r in data.get("reservations", [])
        if r.get("status") == "open"
    )


def _committed_usd(tmp):
    data = _ledger_data(tmp)
    return float(data.get("total_usd", 0.0)) + _open_reserved_usd(tmp)


class TestReservationEnforcement(unittest.TestCase):
    def _adapter(self, tmp, sub_budget=100.0, total_cap=100.0, model="claude-haiku-5-5"):
        helper = Path(tmp) / "anthropic-messages"
        helper.write_text("#!/bin/sh\n", encoding="utf-8")
        return AnthropicAdapter(
            model=model, ledger_dir=tmp, helper_path=helper,
            sub_budget_usd=sub_budget, total_cap_usd=total_cap,
        )

    # (a) normal call with usage present: reservation reconciled to actual.
    def test_a_normal_call_reconciles_reservation_to_actual(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_res_a_001",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hello bakery"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
            # Worst case for "sys"+"hello", max_tokens=100: est_in=2.
            worst = cost_usd(2, 100, "claude-haiku-5-5")
            seen_during_dispatch = {}

            def _fake_run(*args, **kwargs):
                # Reservation must already be durable on disk BEFORE dispatch.
                seen_during_dispatch["data"] = _ledger_data(tmp)
                return subprocess.CompletedProcess(
                    args=args[0] if args else [], returncode=0,
                    stdout=json.dumps(payload), stderr="",
                )

            with mock.patch("subprocess.run", _fake_run):
                out = adapter.complete("sys", "hello", max_tokens=100)
            self.assertEqual(out["text"], "hello bakery")
            # During dispatch an open reservation for the worst case existed.
            during = seen_during_dispatch["data"]
            self.assertEqual(len([r for r in during.get("reservations", [])
                                  if r["status"] == "open"]), 1)
            self.assertAlmostEqual(during["reservations"][0]["reserved_usd"], worst, places=9)
            # After the call: reconciled to actual, ledger exact, nothing open.
            data = _ledger_data(tmp)
            self.assertEqual(len(data["calls"]), 1)
            self.assertAlmostEqual(data["total_usd"], 10 * 0.10e-6 + 5 * 0.50e-6, places=9)
            self.assertEqual(data["calls"][0]["message_id"], "msg_res_a_001")
            self.assertEqual(data["calls"][0]["purpose"], "genie_worker")
            self.assertEqual(len([r for r in data["reservations"]
                                  if r["status"] == "reconciled"]), 1)
            self.assertAlmostEqual(
                data["reservations"][0]["actual_cost_usd"],
                10 * 0.10e-6 + 5 * 0.50e-6, places=9)
            self.assertAlmostEqual(_open_reserved_usd(tmp), 0.0, places=9)
            self.assertAlmostEqual(_committed_usd(tmp), data["total_usd"], places=9)

    # (b) call with usage missing: reservation stands as recorded spend.
    def test_b_text_response_without_usage_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_res_b_001",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "some html"}],
                # No "usage" key at all.
            }
            # Worst case: est_in=2 ("sys"+"user"), max_tokens=8000.
            worst = cost_usd(2, 8000, "claude-haiku-5-5")
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            self.assertIn("usage_missing", str(cm.exception))
            data = _ledger_data(tmp)
            # The dispatched call is charged its worst case, never $0.
            self.assertAlmostEqual(data["total_usd"], worst, places=9)
            self.assertEqual(len(data["calls"]), 1)
            call = data["calls"][0]
            self.assertAlmostEqual(call["cost_usd"], worst, places=9)
            self.assertTrue(call.get("reservation_held"))
            self.assertTrue(call.get("usage_missing"))
            self.assertEqual(call["message_id"], "msg_res_b_001")
            self.assertEqual(
                [r["status"] for r in data["reservations"]], ["held"])
            self.assertAlmostEqual(_open_reserved_usd(tmp), 0.0, places=9)

    def test_b2_empty_text_without_usage_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            payload = {
                "id": "msg_res_b2_001",
                "type": "message",
                "stop_reason": "max_tokens",
                "content": [],
                # No "usage" key at all.
            }
            worst = cost_usd(2, 8000, "claude-haiku-5-5")
            with mock.patch("subprocess.run", _fake_run_factory(payload)):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            self.assertIn("anthropic_empty_text_response", str(cm.exception))
            data = _ledger_data(tmp)
            self.assertAlmostEqual(data["total_usd"], worst, places=9)
            self.assertEqual(len(data["calls"]), 1)
            self.assertEqual(data["calls"][0]["purpose"], "genie_worker_empty_text")
            self.assertTrue(data["calls"][0].get("reservation_held"))

    # (c) worst case exceeds remaining cap: refused before dispatch.
    def test_c_over_cap_refused_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp, sub_budget=0.000001, total_cap=100.0)
            with mock.patch("subprocess.run") as fake_run:
                with self.assertRaises(SpendCapExceeded):
                    adapter.complete("sys", "hello", max_tokens=8000, purpose="build")
                fake_run.assert_not_called()
            data = _ledger_data(tmp)
            self.assertEqual(data["total_usd"], 0.0)
            self.assertEqual(data["calls"], [])
            self.assertEqual(
                [r["status"] for r in data.get("reservations", [])], ["refused"])
            self.assertAlmostEqual(_open_reserved_usd(tmp), 0.0, places=9)

    # (d) boundary: reservation exactly at remaining cap allowed, 1c over refused.
    def test_d_boundary_exact_allowed_one_cent_over_refused(self):
        # Sonnet rates make the numbers large enough for a $0.01 margin to
        # be meaningful. Seed a settled Sonnet call of $0.0702, then a
        # call whose worst case is $0.0802 (est_in=100, max_tokens=8000).
        worst = cost_usd(100, 8000, "claude-sonnet-5-5")  # 0.0802
        self.assertAlmostEqual(worst, 0.0802, places=9)
        system, user = "s" * 200, "u" * 200  # 400 chars -> est_in 100
        payload = {
            "id": "msg_res_d_001",
            "type": "message",
            "stop_reason": "end_turn",
            "content": [{"type": "text", "text": "ok"}],
            "usage": {"input_tokens": 100, "output_tokens": 10},
        }
        for cap_offset, should_allow in (
            # remaining == worst exactly: allowed. The limit is computed
            # from the ledger's own stored seed total (same float ops the
            # adapter performs), so the boundary is exact, not literal.
            (0.0, True),
            # remaining == worst - $0.01: refused.
            (-0.01, False),
        ):
            with tempfile.TemporaryDirectory() as tmp:
                SpendLedger(tmp).record(
                    "claude-sonnet-5-5", "msg_seed_d", 100, 7000,
                    purpose="seed",
                )
                seed_total = SpendLedger(tmp).total_usd()
                self.assertAlmostEqual(seed_total, 0.0702, places=9)
                total_cap = seed_total + worst + cap_offset
                adapter = self._adapter(
                    tmp, sub_budget=100.0, total_cap=total_cap,
                    model="claude-sonnet-5-5",
                )
                dispatch_count = {"n": 0}
                orig_factory = _fake_run_factory(payload)

                def _counting_run(*args, **kwargs):
                    dispatch_count["n"] += 1
                    return orig_factory(*args, **kwargs)

                with mock.patch("subprocess.run", _counting_run):
                    if should_allow:
                        out = adapter.complete(system, user, max_tokens=8000)
                        self.assertEqual(out["text"], "ok")
                        self.assertEqual(dispatch_count["n"], 1)
                    else:
                        with self.assertRaises(SpendCapExceeded):
                            adapter.complete(system, user, max_tokens=8000)
                        self.assertEqual(dispatch_count["n"], 0)
                        self.assertAlmostEqual(
                            SpendLedger(tmp).total_usd(), 0.0702, places=9)

    # (e) double-call racing the cap: only one worst-case reservation fits.
    def test_e_concurrent_calls_cannot_both_reserve(self):
        with tempfile.TemporaryDirectory() as tmp:
            worst = cost_usd(2, 100, "claude-haiku-5-5")
            # A real fake helper script (no mock.patch on the global
            # subprocess.run: mock.patch is not re-entrant across
            # threads, and two concurrent patchers can leak a fake into
            # later tests). The helper sleeps to widen the race window.
            payload = {
                "id": "msg_res_e_001",
                "type": "message",
                "stop_reason": "end_turn",
                "content": [{"type": "text", "text": "hi"}],
                "usage": {"input_tokens": 10, "output_tokens": 5},
            }
            helper = Path(tmp) / "anthropic-messages"
            helper.write_text(
                "import json, time\n"
                "time.sleep(0.05)\n"
                f"print(json.dumps({payload!r}))\n",
                encoding="utf-8",
            )
            adapter = AnthropicAdapter(
                ledger_dir=tmp, helper_path=helper,
                sub_budget_usd=worst, total_cap_usd=100.0,
            )
            barrier = threading.Barrier(2)
            results = {}

            def _call(name):
                barrier.wait(timeout=10)
                try:
                    results[name] = ("ok", adapter.complete("sys", "hello", max_tokens=100))
                except SpendCapExceeded as exc:
                    results[name] = ("refused", str(exc))
                except Exception as exc:  # noqa: BLE001 - record unexpected errors
                    results[name] = ("error", f"{type(exc).__name__}:{exc}")

            threads = [threading.Thread(target=_call, args=(f"t{i}",)) for i in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            outcomes = sorted(v[0] for v in results.values())
            self.assertEqual(outcomes, ["ok", "refused"], results)
            data = _ledger_data(tmp)
            self.assertEqual(len(data["calls"]), 1)
            self.assertAlmostEqual(data["total_usd"], 10 * 0.10e-6 + 5 * 0.50e-6, places=9)
            self.assertAlmostEqual(_committed_usd(tmp), data["total_usd"], places=9)
            self.assertLessEqual(_committed_usd(tmp), worst + 1e-9)

    # (f) crash after dispatch: reservation persisted before dispatch.
    def test_f1_dispatch_exception_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            worst = cost_usd(2, 8000, "claude-haiku-5-5")

            def _fake_run(*args, **kwargs):
                raise KeyboardInterrupt("simulated crash after dispatch")

            with mock.patch("subprocess.run", _fake_run):
                with self.assertRaises(KeyboardInterrupt):
                    adapter.complete("sys", "user")
            data = _ledger_data(tmp)
            self.assertAlmostEqual(data["total_usd"], worst, places=9)
            self.assertEqual(len(data["calls"]), 1)
            self.assertTrue(data["calls"][0].get("reservation_held"))

    def test_f2_true_process_death_leaves_open_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            worst = cost_usd(2, 100, "claude-haiku-5-5")
            child = Path(tmp) / "crash_child.py"
            child.write_text(
                "import os, sys\n"
                "sys.path.insert(0, %r)\n" % str(ROOT)
                + "from pathlib import Path\n"
                "import core.model_adapter as ma\n"
                "helper = Path(sys.argv[2]) / 'anthropic-messages'\n"
                "helper.write_text('#!/bin/sh\\n', encoding='utf-8')\n"
                "adapter = ma.AnthropicAdapter(ledger_dir=sys.argv[2], helper_path=helper,\n"
                "    sub_budget_usd=100.0, total_cap_usd=100.0)\n"
                "ma.subprocess.run = lambda *a, **k: os._exit(3)\n"
                "adapter.complete('sys', 'hello', max_tokens=100)\n",
                encoding="utf-8",
            )
            proc = subprocess.run(
                [sys.executable, str(child), "unused", tmp],
                capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(proc.returncode, 3)
            data = _ledger_data(tmp)
            # No settled call (the process died before any response), but
            # the open reservation accounts for the dispatched worst case.
            self.assertEqual(data["calls"], [])
            self.assertEqual(data["total_usd"], 0.0)
            self.assertEqual(len([r for r in data["reservations"]
                                  if r["status"] == "open"]), 1)
            self.assertAlmostEqual(_open_reserved_usd(tmp), worst, places=9)
            self.assertAlmostEqual(_committed_usd(tmp), worst, places=9)

    def test_f3_helper_timeout_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            worst = cost_usd(2, 8000, "claude-haiku-5-5")

            def _fake_run(*args, **kwargs):
                raise subprocess.TimeoutExpired(cmd="anthropic-messages", timeout=120)

            with mock.patch("subprocess.run", _fake_run):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            self.assertIn("anthropic_helper_timeout", str(cm.exception))
            data = _ledger_data(tmp)
            self.assertAlmostEqual(data["total_usd"], worst, places=9)
            self.assertEqual(len(data["calls"]), 1)
            self.assertTrue(data["calls"][0].get("reservation_held"))

    def test_f4_unparseable_output_holds_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            worst = cost_usd(2, 8000, "claude-haiku-5-5")

            def _fake_run(*args, **kwargs):
                return subprocess.CompletedProcess(
                    args=args[0] if args else [], returncode=0,
                    stdout="Traceback (most recent call last): ... not json ...",
                    stderr="",
                )

            with mock.patch("subprocess.run", _fake_run):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "user")
            self.assertIn("unparseable", str(cm.exception))
            data = _ledger_data(tmp)
            self.assertAlmostEqual(data["total_usd"], worst, places=9)
            self.assertEqual(len(data["calls"]), 1)
            self.assertTrue(data["calls"][0].get("reservation_held"))

    # (g) existing behaviour preserved.
    def test_g_http_error_releases_reservation_no_retry_no_spend(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)

            dispatch_count = {"n": 0}

            def _fake_run(*args, **kwargs):
                dispatch_count["n"] += 1
                return subprocess.CompletedProcess(
                    args=args[0] if args else [], returncode=0,
                    stdout=json.dumps({"_http_error": 429, "_body": "rate limited"}),
                    stderr="",
                )

            with mock.patch("subprocess.run", _fake_run):
                with self.assertRaises(ModelError) as cm:
                    adapter.complete("sys", "hello", max_tokens=100)
            self.assertEqual(dispatch_count["n"], 1)  # no retry
            self.assertIn("anthropic_http_error:429", str(cm.exception))
            data = _ledger_data(tmp)
            # Provider refused the request: nothing generated, $0 spend.
            self.assertEqual(data["total_usd"], 0.0)
            self.assertEqual(data["calls"], [])
            self.assertEqual(
                [r["status"] for r in data["reservations"]], ["released"])
            self.assertAlmostEqual(_open_reserved_usd(tmp), 0.0, places=9)

    def test_g_rates_and_max_tokens_validation(self):
        # Published rates, unchanged.
        self.assertAlmostEqual(
            cost_usd(1000, 1000, "claude-haiku-5-5"), 0.0006, places=9)
        self.assertAlmostEqual(
            cost_usd(1000, 1000, "claude-sonnet-5-5"), 0.012, places=9)
        with tempfile.TemporaryDirectory() as tmp:
            adapter = self._adapter(tmp)
            with mock.patch("subprocess.run") as fake_run:
                with self.assertRaises(ValueError):
                    adapter.complete("sys", "hello", max_tokens=0)
                with self.assertRaises(ValueError):
                    adapter.complete("sys", "hello", max_tokens=8001)
                fake_run.assert_not_called()
            data = _ledger_data(tmp)
            self.assertEqual(data["calls"], [])
            self.assertEqual(data.get("reservations", []), [])

    def test_g_helper_not_found_no_reservation(self):
        with tempfile.TemporaryDirectory() as tmp:
            adapter = AnthropicAdapter(
                ledger_dir=tmp, helper_path=Path(tmp) / "no-such-helper",
                sub_budget_usd=100.0, total_cap_usd=100.0,
            )
            self.assertFalse(adapter.available)
            with self.assertRaises(ModelError):
                adapter.complete("sys", "hello", max_tokens=100)
            data = _ledger_data(tmp)
            self.assertEqual(data["calls"], [])
            self.assertEqual(data.get("reservations", []), [])


if __name__ == "__main__":
    unittest.main()
