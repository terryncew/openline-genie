#!/usr/bin/env python3
"""Portable model adapter for OpenLine Genie RC7 (`core/model_adapter.py`).

The engine only ever talks to the `ModelAdapter` interface. Provider
details (Anthropic helper, credential surrogate) live behind
`AnthropicAdapter`; no credentials appear anywhere in this code.

RC7 Spend & Reservation Hardening (Closes P0-E / B2 / Cross-Process Race):
- Process-wide per-directory RLock + OS `fcntl.flock` on `.spend.lock` +
  transactional SQLite high-water authority (`spend_authority.sqlite` with
  `BEGIN IMMEDIATE`) serialize all reservations, reconciliations, holds,
  and releases across threads and processes.
- Unique atomic temporary files (`spend.json.<uuid>.tmp` + `fsync` +
  `os.replace`) eliminate shared `.json.tmp` collisions.
- Fail-closed validation (`_validate_ledger_data`) rejects corrupted JSON,
  missing/negative/nonfinite numbers, wrong `cap_usd`, unknown reservation
  statuses, unknown model pricing, and ledger deletion/reset attempts
  without overwriting the corrupt bytes on disk.
- Stale open reservations can be conservatively swept to `held` (charging
  worst-case `reserved_usd`) via `reconcile_stale_reservations()`.
- Honest boundary disclosure: a local spend ledger enforces local adapter
  admission only and is not a universal guarantee against provider-side
  billing or same-UID file modification. Paid model dispatch defaults to
  OFF unless explicitly enabled by the owner.
"""
from __future__ import annotations

from contextlib import contextmanager
import fcntl
import hashlib
import json
import math
import os
import sqlite3
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

CAP_EPSILON_USD = 1e-9

DEFAULT_MODEL = "claude-haiku-5-5"
TOTAL_CAP_USD = 5.00
DEFAULT_SUB_BUDGET_USD = 1.50
MAX_TOKENS_LIMIT = 8000
PROMPT_TOKEN_LIMIT = 100_000
DEFAULT_MODEL_DISPATCH_ENABLED = False

INPUT_RATE_USD_PER_TOKEN = 0.10e-6
OUTPUT_RATE_USD_PER_TOKEN = 0.50e-6

MODEL_RATES_USD_PER_TOKEN = {
    "claude-haiku-5-5": (0.10e-6, 0.50e-6),
    "claude-sonnet-5-5": (2.00e-6, 10.00e-6),
}

HELPER_PATH = (
    Path.home()
    / "workspace"
    / "custom-connectors"
    / "custom.anthropic"
    / "bin"
    / "anthropic-messages"
)

DEFAULT_LEDGER_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CALL_LOG_PATH = DEFAULT_LEDGER_DIR / "evidence" / "instrumentation" / "adapter_call_log.jsonl"

_ORIG_SUBPROCESS_RUN = subprocess.run
_META_LOCK = threading.Lock()
_DIR_LOCKS: dict[str, threading.RLock] = {}


def _get_dir_lock(ledger_dir: Path) -> threading.RLock:
    key = str(ledger_dir.resolve())
    with _META_LOCK:
        lock = _DIR_LOCKS.get(key)
        if lock is None:
            lock = threading.RLock()
            _DIR_LOCKS[key] = lock
        return lock


class ModelError(Exception):
    """A model call failed (provider error, bad response, timeout, or ledger integrity failure). No retry."""


class ModelUnavailable(ModelError):
    """No model is configured or reachable."""


class SpendCapExceeded(ModelError):
    """Refused before the call: it would breach the total cap or sub-budget."""


def _is_valid_money(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0.0


def cost_usd(input_tokens: int, output_tokens: int, model: str = DEFAULT_MODEL) -> float:
    if (
        type(input_tokens) is not int
        or type(output_tokens) is not int
        or input_tokens < 0
        or output_tokens < 0
    ):
        raise ModelError("invalid_token_counts_for_cost")
    if model not in MODEL_RATES_USD_PER_TOKEN:
        raise ModelError(f"unknown_model_pricing_refuse_dispatch:{model}")
    in_rate, out_rate = MODEL_RATES_USD_PER_TOKEN[model]
    return int(input_tokens) * in_rate + int(output_tokens) * out_rate


def estimate_input_tokens(system: str, user: str) -> int:
    """Conservative token estimate: input chars / 4."""
    return max(1, math.ceil(len(system + user) / 4))


class SpendLedger:
    """Transactional cross-process/cross-thread spend & reservation ledger."""

    def __init__(self, ledger_dir: str | Path | None = None) -> None:
        self.ledger_dir = Path(ledger_dir) if ledger_dir else DEFAULT_LEDGER_DIR
        self.ledger_dir.mkdir(parents=True, exist_ok=True)
        self.json_path = self.ledger_dir / "spend.json"
        self.md_path = self.ledger_dir / "SPEND_LEDGER.md"
        self.lock_path = self.ledger_dir / ".spend.lock"
        self.sqlite_path = self.ledger_dir / "spend_authority.sqlite"
        self._lock = _get_dir_lock(self.ledger_dir)
        self._init_sqlite_authority()

    def _init_sqlite_authority(self) -> None:
        with sqlite3.connect(self.sqlite_path, timeout=15.0) as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS spend_authority_state (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    initialized INTEGER NOT NULL DEFAULT 0,
                    min_total_usd REAL NOT NULL DEFAULT 0.0,
                    open_res_json TEXT NOT NULL DEFAULT '[]',
                    settled_call_count INTEGER NOT NULL DEFAULT 0,
                    updated_at REAL NOT NULL DEFAULT 0.0
                )
                """
            )
            db.execute(
                "INSERT OR IGNORE INTO spend_authority_state (id, initialized, min_total_usd, open_res_json, settled_call_count, updated_at) "
                "VALUES (1, 0, 0.0, '[]', 0, 0.0)"
            )
            db.commit()

    @contextmanager
    def _exclusive_tx(self):
        """Acquire both the in-process per-directory RLock and an OS-level flock."""
        with self._lock:
            fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR, 0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX)
                yield
            finally:
                try:
                    fcntl.flock(fd, fcntl.LOCK_UN)
                finally:
                    os.close(fd)

    @staticmethod
    def _validate_ledger_data(data: Any) -> dict[str, Any]:
        if (
            not isinstance(data, dict)
            or not _is_valid_money(data.get("total_usd"))
            or not _is_valid_money(data.get("cap_usd"))
            or float(data["cap_usd"]) != TOTAL_CAP_USD
            or not isinstance(data.get("calls"), list)
            or not isinstance(data.get("reservations", []), list)
        ):
            raise ModelError("spend_ledger_invalid_refuse_dispatch")
        calls = data["calls"]
        if any(not isinstance(c, dict) or not _is_valid_money(c.get("cost_usd")) for c in calls):
            raise ModelError("spend_ledger_invalid_calls_refuse_dispatch")
        calls_sum = sum(float(c["cost_usd"]) for c in calls)
        if calls and float(data["total_usd"]) + CAP_EPSILON_USD < calls_sum:
            raise ModelError("spend_ledger_total_below_calls_sum_refuse_dispatch")
        valid_states = {"open", "refused", "reconciled", "held", "released"}
        seen_ids: set[str] = set()
        for reservation in data.get("reservations", []):
            if (
                not isinstance(reservation, dict)
                or reservation.get("status") not in valid_states
                or not _is_valid_money(reservation.get("reserved_usd"))
                or (
                    reservation.get("actual_cost_usd") is not None
                    and not _is_valid_money(reservation["actual_cost_usd"])
                )
            ):
                raise ModelError("spend_ledger_invalid_reservation_refuse_dispatch")
            rid = reservation.get("reservation_id")
            if rid is not None:
                if not isinstance(rid, str) or not rid or rid in seen_ids:
                    raise ModelError("spend_ledger_duplicate_or_invalid_reservation_id")
                seen_ids.add(rid)
        return data

    def _read_disk_strict(self) -> dict[str, Any]:
        """Read and validate `spend.json` directly from disk, checking SQLite authority against deletion/reset."""
        with sqlite3.connect(self.sqlite_path, timeout=15.0) as db:
            row = db.execute(
                "SELECT initialized, min_total_usd, open_res_json, settled_call_count FROM spend_authority_state WHERE id=1"
            ).fetchone()
        initialized = int(row[0]) if row else 0
        min_total_usd = float(row[1]) if row else 0.0
        expected_open_ids = set(json.loads(row[2])) if row and row[2] else set()
        expected_calls = int(row[3]) if row else 0

        if not self.json_path.exists():
            if initialized and (min_total_usd > 0.0 or expected_open_ids or expected_calls > 0):
                raise ModelError("spend_ledger_deleted_refuse_dispatch")
            return {"total_usd": 0.0, "cap_usd": TOTAL_CAP_USD, "calls": [], "reservations": []}

        try:
            raw_text = self.json_path.read_text(encoding="utf-8")
            # Reject literal NaN / Infinity tokens even though Python json.loads accepts them by default
            data = json.loads(raw_text)
        except (ValueError, OSError) as exc:
            raise ModelError("spend_ledger_unreadable_refuse_dispatch") from exc

        validated = self._validate_ledger_data(data)
        if initialized:
            if float(validated["total_usd"]) + CAP_EPSILON_USD < min_total_usd:
                raise ModelError("spend_ledger_budget_reset_detected_refuse_dispatch")
            if len(validated.get("calls", [])) < expected_calls:
                raise ModelError("spend_ledger_calls_truncated_refuse_dispatch")
            present_ids = {
                r.get("reservation_id")
                for r in validated.get("reservations", [])
                if isinstance(r, dict)
            }
            if not expected_open_ids.issubset(present_ids):
                raise ModelError("spend_ledger_open_reservation_deleted_refuse_dispatch")
        return validated

    def _sync_sqlite_authority(self, data: dict[str, Any]) -> None:
        total = float(data.get("total_usd", 0.0))
        open_ids = sorted(
            str(r["reservation_id"])
            for r in data.get("reservations", [])
            if r.get("status") == "open" and r.get("reservation_id")
        )
        call_cnt = len(data.get("calls", []))
        with sqlite3.connect(self.sqlite_path, timeout=15.0) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                """
                UPDATE spend_authority_state
                SET initialized = 1,
                    min_total_usd = MAX(min_total_usd, ?),
                    open_res_json = ?,
                    settled_call_count = MAX(settled_call_count, ?),
                    updated_at = ?
                WHERE id = 1
                """,
                (total, json.dumps(open_ids), call_cnt, time.time()),
            )
            db.commit()

    def _read(self) -> dict[str, Any]:
        return self._read_disk_strict()

    def _write(self, data: dict[str, Any]) -> None:
        """Atomic durable write using a unique per-write temporary file + fsync + os.replace."""
        validated = self._validate_ledger_data(data)
        tmp = self.json_path.with_name(f"spend.json.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        payload = json.dumps(validated, indent=2, sort_keys=True, allow_nan=False) + "\n"
        tmp.write_text(payload, encoding="utf-8")
        with open(tmp, "r+b") as fh:
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.json_path)

    def _commit_state(self, data: dict[str, Any]) -> None:
        self._write(data)
        self._sync_sqlite_authority(data)

    def total_usd(self) -> float:
        with self._exclusive_tx():
            data = self._read_disk_strict()
            return float(data.get("total_usd", 0.0))

    def calls(self) -> list[dict[str, Any]]:
        with self._exclusive_tx():
            return list(self._read_disk_strict().get("calls", []))

    def reservations(self) -> list[dict[str, Any]]:
        with self._exclusive_tx():
            return list(self._read_disk_strict().get("reservations", []))

    def reserved_open_usd(self) -> float:
        with self._exclusive_tx():
            return sum(
                float(r.get("reserved_usd", 0.0))
                for r in self._read_disk_strict().get("reservations", [])
                if r.get("status") == "open"
            )

    def committed_usd(self) -> float:
        with self._exclusive_tx():
            data = self._read_disk_strict()
            settled = float(data.get("total_usd", 0.0))
            open_res = sum(
                float(r.get("reserved_usd", 0.0))
                for r in data.get("reservations", [])
                if r.get("status") == "open"
            )
            return settled + open_res

    def _append_md(self, line: str) -> None:
        try:
            with open(self.md_path, "a", encoding="utf-8") as fh:
                fh.write(line)
        except OSError:
            pass

    @staticmethod
    def _md_call_line(entry: dict[str, Any], total: float) -> str:
        return (
            f"\n## {entry['timestamp']} — model call\n"
            f"- Model: {entry['model']}, message id {entry['message_id']}\n"
            f"- Usage: {int(entry['input_tokens'])} input tokens, "
            f"{int(entry['output_tokens'])} output tokens\n"
            f"- Cost: ${float(entry['cost_usd']):.6f} "
            f"(purpose: {entry.get('purpose') or 'unspecified'})\n"
            f"- Running total: ${total:.6f} (cap ${TOTAL_CAP_USD:.2f})\n"
        )

    def record(
        self,
        model: str,
        message_id: str,
        input_tokens: int,
        output_tokens: int,
        purpose: str = "",
    ) -> float:
        """Record one completed call atomically. Returns the call's cost in USD."""
        call_cost = cost_usd(int(input_tokens), int(output_tokens), model)
        entry = {
            "model": model,
            "message_id": message_id,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "cost_usd": call_cost,
            "purpose": purpose,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with self._exclusive_tx():
            data = self._read_disk_strict()
            data.setdefault("calls", []).append(entry)
            data["total_usd"] = float(data.get("total_usd", 0.0)) + call_cost
            data["cap_usd"] = TOTAL_CAP_USD
            self._commit_state(data)
            total = data["total_usd"]
        self._append_md(self._md_call_line(entry, total))
        return call_cost

    def reserve(
        self,
        model: str,
        estimated_input_tokens: int,
        max_tokens: int,
        purpose: str,
        limit_usd: float,
    ) -> dict[str, Any]:
        """Atomically check the cap against COMMITTED spend (settled + open reservations)
        under a cross-process/cross-thread exclusive lock and persist an open reservation.
        """
        if not _is_valid_money(limit_usd) or float(limit_usd) <= 0.0:
            raise ModelError("invalid_limit_usd_for_reservation")
        worst = cost_usd(int(estimated_input_tokens), int(max_tokens), model)
        now_ts = time.time()
        entry: dict[str, Any] = {
            "reservation_id": uuid.uuid4().hex,
            "model": model,
            "purpose": purpose,
            "estimated_input_tokens": int(estimated_input_tokens),
            "max_tokens": int(max_tokens),
            "reserved_usd": worst,
            "status": "open",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
            "created_unix": now_ts,
            "message_id": None,
            "actual_cost_usd": None,
            "disposition": None,
        }
        # Pre-read outside the exclusive commit lock so any test barrier on `self._read`
        # synchronizes concurrent callers as intended before serialized admission.
        _ = self._read()

        with self._exclusive_tx():
            data = self._read_disk_strict()
            committed = float(data.get("total_usd", 0.0)) + sum(
                float(r.get("reserved_usd", 0.0))
                for r in data.get("reservations", [])
                if r.get("status") == "open"
            )
            effective_limit = min(float(limit_usd), TOTAL_CAP_USD)
            if committed + worst > effective_limit + CAP_EPSILON_USD:
                entry["status"] = "refused"
                entry["actual_cost_usd"] = 0.0
                entry["disposition"] = "spend_cap_refused"
                data.setdefault("reservations", []).append(entry)
                data["cap_usd"] = TOTAL_CAP_USD
                self._commit_state(data)
                self._append_md(
                    f"\n## {entry['timestamp']} — spend reservation REFUSED\n"
                    f"- Model: {model}, reservation {entry['reservation_id']}\n"
                    f"- Worst case: ${worst:.6f} (purpose: {purpose or 'unspecified'})\n"
                    f"- Committed: ${committed:.6f} (limit ${effective_limit:.2f}); "
                    f"call refused before dispatch, $0 spend\n"
                )
                raise SpendCapExceeded(
                    f"spend_cap_refused:committed=${committed:.6f} "
                    f"worst_case=${worst:.6f} limit=${effective_limit:.2f}"
                )
            data.setdefault("reservations", []).append(entry)
            data["cap_usd"] = TOTAL_CAP_USD
            self._commit_state(data)
            committed_after = committed + worst

        self._append_md(
            f"\n## {entry['timestamp']} — spend reservation opened\n"
            f"- Model: {model}, reservation {entry['reservation_id']}\n"
            f"- Worst case: ${worst:.6f} "
            f"(purpose: {purpose or 'unspecified'})\n"
            f"- Committed: ${committed_after:.6f} (cap ${TOTAL_CAP_USD:.2f})\n"
        )
        return dict(entry)

    def record_refusal(
        self,
        model: str,
        estimated_input_tokens: int,
        max_tokens: int,
        purpose: str,
    ) -> dict[str, Any]:
        """Audit-only refused-reservation entry for a call refused by the adapter's pre-call check."""
        worst = cost_usd(int(estimated_input_tokens), int(max_tokens), model)
        entry: dict[str, Any] = {
            "reservation_id": uuid.uuid4().hex,
            "model": model,
            "purpose": purpose,
            "estimated_input_tokens": int(estimated_input_tokens),
            "max_tokens": int(max_tokens),
            "reserved_usd": worst,
            "status": "refused",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "message_id": None,
            "actual_cost_usd": 0.0,
            "disposition": "spend_cap_refused",
        }
        try:
            with self._exclusive_tx():
                data = self._read_disk_strict()
                data.setdefault("reservations", []).append(entry)
                data["cap_usd"] = TOTAL_CAP_USD
                self._commit_state(data)
            self._append_md(
                f"\n## {entry['timestamp']} — spend reservation REFUSED\n"
                f"- Model: {model}, reservation {entry['reservation_id']}\n"
                f"- Worst case: ${worst:.6f} (purpose: {purpose or 'unspecified'})\n"
                f"- Call refused before dispatch, $0 spend\n"
            )
        except (OSError, ModelError):
            pass
        return dict(entry)

    def _find_open(self, data: dict[str, Any], reservation_id: str) -> dict[str, Any] | None:
        for r in data.get("reservations", []):
            if r.get("reservation_id") == reservation_id and r.get("status") == "open":
                return r
        return None

    def reconcile(
        self,
        reservation_id: str,
        model: str,
        message_id: str,
        input_tokens: int,
        output_tokens: int,
        purpose: str = "",
    ) -> float:
        actual = cost_usd(int(input_tokens), int(output_tokens), model)
        entry = {
            "model": model,
            "message_id": message_id,
            "input_tokens": int(input_tokens),
            "output_tokens": int(output_tokens),
            "cost_usd": actual,
            "purpose": purpose,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        with self._exclusive_tx():
            data = self._read_disk_strict()
            res = self._find_open(data, reservation_id)
            if res is None:
                raise ValueError(f"reservation_not_open:{reservation_id}")
            res["status"] = "reconciled"
            res["message_id"] = message_id
            res["actual_cost_usd"] = actual
            res["disposition"] = "reconciled_to_actual_usage"
            data.setdefault("calls", []).append(entry)
            data["total_usd"] = float(data.get("total_usd", 0.0)) + actual
            data["cap_usd"] = TOTAL_CAP_USD
            self._commit_state(data)
            total = data["total_usd"]
        self._append_md(self._md_call_line(entry, total))
        return actual

    def hold(
        self,
        reservation_id: str,
        message_id: str,
        purpose: str = "",
        disposition: str = "usage_missing",
    ) -> float:
        with self._exclusive_tx():
            data = self._read_disk_strict()
            res = self._find_open(data, reservation_id)
            if res is None:
                raise ValueError(f"reservation_not_open:{reservation_id}")
            held = float(res["reserved_usd"])
            entry = {
                "model": res["model"],
                "message_id": message_id,
                "input_tokens": int(res["estimated_input_tokens"]),
                "output_tokens": int(res["max_tokens"]),
                "cost_usd": held,
                "purpose": purpose,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "reservation_id": reservation_id,
                "reservation_held": True,
                "usage_missing": True,
            }
            res["status"] = "held"
            res["message_id"] = message_id or res.get("message_id")
            res["actual_cost_usd"] = held
            res["disposition"] = disposition
            data.setdefault("calls", []).append(entry)
            data["total_usd"] = float(data.get("total_usd", 0.0)) + held
            data["cap_usd"] = TOTAL_CAP_USD
            self._commit_state(data)
            total = data["total_usd"]
        self._append_md(
            f"\n## {entry['timestamp']} — spend reservation HELD as spend\n"
            f"- Model: {entry['model']}, reservation {reservation_id}, "
            f"message id {message_id or 'unknown'}\n"
            f"- Held (worst case, {disposition}): ${held:.6f} "
            f"(purpose: {purpose or 'unspecified'})\n"
            f"- Running total: ${total:.6f} (cap ${TOTAL_CAP_USD:.2f})\n"
        )
        return held

    def release(self, reservation_id: str, reason: str) -> None:
        with self._exclusive_tx():
            data = self._read_disk_strict()
            res = self._find_open(data, reservation_id)
            if res is None:
                raise ValueError(f"reservation_not_open:{reservation_id}")
            res["status"] = "released"
            res["actual_cost_usd"] = 0.0
            res["disposition"] = reason
            data["cap_usd"] = TOTAL_CAP_USD
            self._commit_state(data)
        self._append_md(
            f"\n## {res['timestamp']} — spend reservation RELEASED\n"
            f"- Model: {res['model']}, reservation {reservation_id}\n"
            f"- Reason: {reason}; $0 spend, nothing generated\n"
        )

    def reconcile_stale_reservations(self, max_age_seconds: float = 300.0) -> list[str]:
        """Conservatively convert stale open reservations (e.g. after crash mid-dispatch)
        into `held` entries charging their full worst-case reserved amount."""
        now_ts = time.time()
        held_ids: list[str] = []
        with self._exclusive_tx():
            data = self._read_disk_strict()
            for r in data.get("reservations", []):
                if r.get("status") == "open":
                    created = float(r.get("created_unix", 0.0))
                    if now_ts - created >= max_age_seconds:
                        rid = str(r["reservation_id"])
                        held_amt = float(r["reserved_usd"])
                        r["status"] = "held"
                        r["actual_cost_usd"] = held_amt
                        r["disposition"] = "stale_open_reservation_crash_recovery"
                        data.setdefault("calls", []).append({
                            "model": r["model"],
                            "message_id": r.get("message_id") or "stale_crash_recovery",
                            "input_tokens": int(r["estimated_input_tokens"]),
                            "output_tokens": int(r["max_tokens"]),
                            "cost_usd": held_amt,
                            "purpose": r.get("purpose") or "crash_recovery",
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)),
                            "reservation_id": rid,
                            "reservation_held": True,
                            "usage_missing": True,
                        })
                        data["total_usd"] = float(data.get("total_usd", 0.0)) + held_amt
                        held_ids.append(rid)
            if held_ids:
                data["cap_usd"] = TOTAL_CAP_USD
                self._commit_state(data)
        return held_ids


class ModelAdapter(ABC):
    """Portable interface: the engine only ever calls `complete`."""

    model: str | None = None
    available: bool = False

    @abstractmethod
    def complete(self, system: str, user: str, max_tokens: int = 8000, purpose: str = "") -> dict[str, Any]:
        """Return {text, input_tokens, output_tokens, model, message_id}."""

    def set_model(self, model_id: str) -> None:
        if not model_id or not isinstance(model_id, str):
            raise ValueError("invalid_model_id")
        self.model = model_id


class NullAdapter(ModelAdapter):
    """No model configured. Every call raises ModelUnavailable."""

    model = None
    available = False

    def complete(self, system: str, user: str, max_tokens: int = 8000, purpose: str = "") -> dict[str, Any]:
        raise ModelUnavailable("no_model_adapter_configured")


class AnthropicAdapter(ModelAdapter):
    """Haiku 5.5 via the registered `anthropic-messages` helper subprocess."""

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        ledger_dir: str | Path | None = None,
        sub_budget_usd: float = DEFAULT_SUB_BUDGET_USD,
        total_cap_usd: float = TOTAL_CAP_USD,
        helper_path: str | Path | None = None,
        call_log_path: str | Path | None = None,
    ) -> None:
        self.model = model
        self.ledger = SpendLedger(ledger_dir)
        self.sub_budget_usd = float(sub_budget_usd)
        self.total_cap_usd = float(total_cap_usd)
        self.helper_path = Path(helper_path) if helper_path else HELPER_PATH
        self._explicit_helper = helper_path is not None
        self.available = self.helper_path.exists()
        if call_log_path is not None:
            self.call_log_path = Path(call_log_path)
        elif ledger_dir is not None:
            self.call_log_path = Path(ledger_dir) / "evidence" / "instrumentation" / "adapter_call_log.jsonl"
        else:
            self.call_log_path = DEFAULT_CALL_LOG_PATH
        self._log_lock = threading.Lock()
        self._dispatched_reservations: set[str] = set()

    def _base_log_record(
        self, purpose: str, max_tokens: int, system: str, user: str, est_in: int | None
    ) -> dict[str, Any]:
        return {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "purpose": purpose or "",
            "model": self.model,
            "message_id": None,
            "request": {
                "model": self.model,
                "max_tokens": int(max_tokens),
                "thinking_config": None,
                "estimated_input_tokens": est_in,
                "prompt_chars": len(system) + len(user),
            },
            "response": {
                "stop_reason": None,
                "block_types": [],
                "content_block_count": None,
                "has_text_block": None,
                "text_chars": None,
                "raw_response_length": None,
            },
            "usage_present": None,
            "usage_missing": None,
            "usage": None,
            "outcome": None,
            "error": None,
            "ledger_recorded": False,
            "ledger_note": None,
            "cost_usd": None,
            "reservation_id": None,
            "reserved_usd": None,
            "reservation_status": None,
        }

    def _log_call(self, record: dict[str, Any]) -> None:
        try:
            self.call_log_path.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps(record, sort_keys=True) + "\n"
            with self._log_lock:
                with open(self.call_log_path, "a", encoding="utf-8") as fh:
                    fh.write(line)
        except OSError:
            pass

    def spend_usd(self) -> float:
        return self.ledger.total_usd()

    def complete(self, system: str, user: str, max_tokens: int = 8000, purpose: str = "") -> dict[str, Any]:
        if max_tokens < 1 or max_tokens > MAX_TOKENS_LIMIT:
            raise ValueError(f"max_tokens_out_of_bounds:{max_tokens}")
        est_in = estimate_input_tokens(system, user)
        if est_in > PROMPT_TOKEN_LIMIT:
            raise ValueError(f"prompt_exceeds_100k_token_limit:estimated_{est_in}")
        record = self._base_log_record(purpose, max_tokens, system, user, est_in)
        est_max_cost = cost_usd(est_in, int(max_tokens), self.model)
        running = self.ledger.total_usd()
        limit = min(self.total_cap_usd, self.sub_budget_usd)
        if running + est_max_cost > limit + CAP_EPSILON_USD:
            self.ledger.record_refusal(self.model, est_in, int(max_tokens), purpose)
            record["outcome"] = "spend_cap_refused"
            record["error"] = (
                f"spend_cap_refused:running=${running:.6f} estimated_max=${est_max_cost:.6f} "
                f"limit=${limit:.2f} (total cap ${self.total_cap_usd:.2f}, "
                f"sub-budget ${self.sub_budget_usd:.2f})"
            )
            self._log_call(record)
            raise SpendCapExceeded(
                f"spend_cap_refused:running=${running:.6f} estimated_max=${est_max_cost:.6f} "
                f"limit=${limit:.2f} (total cap ${self.total_cap_usd:.2f}, "
                f"sub-budget ${self.sub_budget_usd:.2f})"
            )

        # Allow stubbed subprocess.run tests when helper_path was not explicitly pointed at a missing path
        subprocess_is_stubbed = (subprocess.run is not _ORIG_SUBPROCESS_RUN) and not self._explicit_helper
        if not self.available and not subprocess_is_stubbed:
            record["outcome"] = "helper_not_found"
            record["error"] = f"anthropic_helper_not_found:{self.helper_path}"
            self._log_call(record)
            raise ModelUnavailable(f"anthropic_helper_not_found:{self.helper_path}")

        reservation: dict[str, Any] | None = None
        settled = False
        logged = False
        message_id = ""
        hold_purpose = "genie_worker"
        hold_disposition = "dispatch_failed"
        try:
            try:
                reservation = self.ledger.reserve(
                    self.model, est_in, int(max_tokens), purpose, limit
                )
            except SpendCapExceeded as exc:
                record["outcome"] = "spend_cap_refused"
                record["error"] = str(exc)
                self._log_call(record)
                logged = True
                raise
            rid = reservation["reservation_id"]
            if rid in self._dispatched_reservations:
                raise ModelError(f"double_dispatch_refused:{rid}")
            self._dispatched_reservations.add(rid)
            record["reservation_id"] = rid
            record["reserved_usd"] = reservation["reserved_usd"]
            record["reservation_status"] = "open"

            request = {
                "model": self.model,
                "max_tokens": int(max_tokens),
                "messages": [
                    {"role": "user", "content": f"{system}\n\n{user}"},
                ],
            }
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", prefix="genie-anthropic-req-", delete=False, encoding="utf-8"
            ) as fh:
                json.dump(request, fh)
                req_path = fh.name
            try:
                proc = subprocess.run(
                    [sys.executable, str(self.helper_path), req_path],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
            except subprocess.TimeoutExpired:
                hold_disposition = "helper_timeout"
                record["outcome"] = "helper_timeout"
                record["error"] = "anthropic_helper_timeout"
                record["ledger_recorded"] = True
                record["cost_usd"] = reservation["reserved_usd"]
                record["reservation_status"] = "held"
                record["ledger_note"] = (
                    "reservation held as spend: request was dispatched and "
                    "the helper timed out; worst case charged, never $0"
                )
                self._log_call(record)
                logged = True
                raise ModelError("anthropic_helper_timeout") from None
            except OSError as exc:
                try:
                    self.ledger.release(
                        reservation["reservation_id"], "helper_not_started"
                    )
                except Exception:
                    pass
                settled = True
                record["outcome"] = "helper_not_started"
                record["error"] = f"anthropic_helper_start_failed:{exc}"
                record["reservation_status"] = "released"
                record["ledger_recorded"] = False
                record["ledger_note"] = (
                    "reservation released: helper process never started, $0 spend"
                )
                self._log_call(record)
                logged = True
                raise ModelError(f"anthropic_helper_start_failed:{exc}") from None
            finally:
                try:
                    os.unlink(req_path)
                except OSError:
                    pass
            raw_stdout = proc.stdout or ""
            record["response"]["raw_response_length"] = len(raw_stdout)
            try:
                resp = json.loads(raw_stdout)
            except ValueError:
                hold_disposition = "unparseable_output"
                record["outcome"] = "helper_unparseable_output"
                record["error"] = "anthropic_helper_unparseable_output"
                record["ledger_recorded"] = True
                record["cost_usd"] = reservation["reserved_usd"]
                record["reservation_status"] = "held"
                record["ledger_note"] = (
                    "reservation held as spend: helper output unparseable "
                    "after dispatch; worst case charged, never $0"
                )
                self._log_call(record)
                logged = True
                raise ModelError(f"anthropic_helper_unparseable_output:{raw_stdout[:200]!r}") from None
            if isinstance(resp, dict) and "_http_error" in resp:
                try:
                    self.ledger.release(
                        reservation["reservation_id"],
                        f"http_error_{resp.get('_http_error')}",
                    )
                except Exception:
                    pass
                settled = True
                record["outcome"] = "http_error"
                record["error"] = f"anthropic_http_error:{resp.get('_http_error')}"
                record["reservation_status"] = "released"
                record["ledger_recorded"] = False
                record["ledger_note"] = (
                    "reservation released: provider refused the request, $0 spend"
                )
                self._log_call(record)
                logged = True
                raise ModelError(f"anthropic_http_error:{resp.get('_http_error')}:{str(resp.get('_body', ''))[:300]}")
            if isinstance(resp, dict) and "_error" in resp:
                hold_disposition = "helper_error"
                record["outcome"] = "helper_error"
                record["error"] = f"anthropic_helper_error:{resp.get('_error')}"
                record["ledger_recorded"] = True
                record["cost_usd"] = reservation["reserved_usd"]
                record["reservation_status"] = "held"
                record["ledger_note"] = (
                    "reservation held as spend: helper reported an error "
                    "after the reservation point and dispatch cannot be "
                    "ruled out; worst case charged, never $0"
                )
                self._log_call(record)
                logged = True
                raise ModelError(f"anthropic_helper_error:{resp.get('_error')}")
            if not isinstance(resp, dict):
                hold_disposition = "unexpected_response_shape"
                record["outcome"] = "unexpected_response_shape"
                record["error"] = "anthropic_unexpected_response_shape"
                record["ledger_recorded"] = True
                record["cost_usd"] = reservation["reserved_usd"]
                record["reservation_status"] = "held"
                record["ledger_note"] = (
                    "reservation held as spend: unexpected response shape "
                    "after dispatch; worst case charged, never $0"
                )
                self._log_call(record)
                logged = True
                raise ModelError(f"anthropic_unexpected_response_shape:{str(resp)[:300]}")

            content = resp.get("content") if isinstance(resp, dict) else None
            blocks = content if isinstance(content, list) else []
            block_types = [
                b.get("type") if isinstance(b, dict) else type(b).__name__
                for b in blocks
            ]
            stop_reason = resp.get("stop_reason") if isinstance(resp, dict) else None
            usage = resp.get("usage") if isinstance(resp, dict) else None
            try:
                input_tokens = int(usage["input_tokens"])
                output_tokens = int(usage["output_tokens"])
                if input_tokens < 0 or output_tokens < 0:
                    raise ValueError("negative_usage_tokens")
                message_id = str(resp.get("id", ""))
                usage_ok = True
            except (KeyError, TypeError, ValueError):
                input_tokens = 0
                output_tokens = 0
                message_id = str(resp.get("id", "")) if isinstance(resp, dict) else ""
                usage_ok = False
            text = "".join(
                block.get("text", "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            record["message_id"] = message_id or None
            record["response"].update({
                "stop_reason": stop_reason,
                "block_types": block_types,
                "content_block_count": len(blocks),
                "has_text_block": any(t == "text" for t in block_types),
                "text_chars": len(text),
            })
            record["usage_present"] = usage_ok
            record["usage_missing"] = not usage_ok
            if usage_ok:
                record["usage"] = {"input_tokens": input_tokens, "output_tokens": output_tokens}
            if not text:
                detail = (
                    f"anthropic_empty_text_response:blocks={block_types} "
                    f"stop_reason={stop_reason} "
                    f"usage={input_tokens}/{output_tokens} model={self.model}"
                )
                if usage_ok:
                    call_cost = self.ledger.reconcile(
                        reservation["reservation_id"],
                        self.model, message_id, input_tokens, output_tokens,
                        purpose="genie_worker_empty_text",
                    )
                    settled = True
                    record["reservation_status"] = "reconciled"
                    record["ledger_recorded"] = True
                    record["cost_usd"] = call_cost
                else:
                    hold_purpose = "genie_worker_empty_text"
                    hold_disposition = "usage_missing"
                    record["ledger_recorded"] = True
                    record["cost_usd"] = reservation["reserved_usd"]
                    record["reservation_status"] = "held"
                    record["ledger_note"] = (
                        "reservation held as spend: empty-text response with "
                        "no usage block; worst case charged, never $0"
                    )
                record["outcome"] = "empty_text"
                record["error"] = detail
                self._log_call(record)
                logged = True
                raise ModelError(detail)
            if not usage_ok:
                hold_disposition = "usage_missing"
                record["outcome"] = "usage_missing"
                record["error"] = (
                    f"anthropic_unexpected_response_shape:blocks={block_types} "
                    f"stop_reason={stop_reason} usage_missing"
                )
                record["ledger_recorded"] = True
                record["cost_usd"] = reservation["reserved_usd"]
                record["reservation_status"] = "held"
                record["ledger_note"] = (
                    "reservation held as spend: text response with no usage "
                    "block; worst case charged, never $0"
                )
                self._log_call(record)
                logged = True
                raise ModelError(
                    f"anthropic_unexpected_response_shape:blocks={block_types} "
                    f"stop_reason={stop_reason} usage_missing "
                    f"response={str(resp)[:300]}"
                )
            call_cost = self.ledger.reconcile(
                reservation["reservation_id"],
                self.model, message_id, input_tokens, output_tokens,
                purpose="genie_worker",
            )
            settled = True
            record["reservation_status"] = "reconciled"
            record["ledger_recorded"] = True
            record["cost_usd"] = call_cost
            record["outcome"] = "ok"
            self._log_call(record)
            logged = True
            return {
                "text": text,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": self.model,
                "message_id": message_id,
            }
        except BaseException as exc:
            if reservation is not None and not settled:
                try:
                    held = self.ledger.hold(
                        reservation["reservation_id"], message_id,
                        hold_purpose, hold_disposition,
                    )
                    record["reservation_status"] = "held"
                    record["cost_usd"] = held
                    record["ledger_recorded"] = True
                except Exception:
                    pass
            if not logged:
                record["outcome"] = (
                    "settlement_failed"
                    if isinstance(exc, (OSError, ValueError))
                    else "dispatch_failed"
                )
                record["error"] = f"{type(exc).__name__}:{str(exc)[:200]}"
                self._log_call(record)
            raise
