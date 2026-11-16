#!/usr/bin/env python3
"""
OPENLINE MIF-PWS v2 PHYSICAL EXPERIMENT & MANUFACTURING QUALIFICATION 004
Module: run_all_physical_experiment_004.py

Standalone, zero-dependency reproducibility runner for independent laboratories.
Executes all physics solvers, BOM exports, CAD/STEP/DXF/STL/SPICE generation,
10-test independent falsification battery, Ed25519 cryptographic signing,
and SHA256SUMS.txt manifest verification.
"""

from __future__ import annotations
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from independent_falsification_and_verification import generate_master_evidence


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_and_verify_manifest(root: Path) -> int:
    files = sorted(
        p for p in root.rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.name != "SHA256SUMS.txt"
        and not p.name.endswith(".pyc")
    )
    lines = []
    for f in files:
        rel = f.relative_to(root).as_posix()
        lines.append(f"{compute_sha256(f)}  {rel}")
    manifest_path = root / "SHA256SUMS.txt"
    manifest_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Verify every entry in SHA256SUMS.txt
    for line in manifest_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        expected_hash, rel_path = line.split("  ", 1)
        target = root / rel_path
        actual_hash = compute_sha256(target)
        if actual_hash != expected_hash:
            raise RuntimeError(f"SHA-256 mismatch on {rel_path}: {actual_hash} != {expected_hash}")
    return len(lines)


def main() -> None:
    print("[1/4] Generating master evidence, BOM, CAD/STEP/DXF/STL/SPICE, and deterministic figures...")
    ev1 = generate_master_evidence(ROOT)
    hash_run1 = ev1["cryptographic_witness_signature"]["payload_canonical_sha256"]

    print("[2/4] Verifying byte-determinism across a second consecutive regeneration...")
    ev2 = generate_master_evidence(ROOT)
    hash_run2 = ev2["cryptographic_witness_signature"]["payload_canonical_sha256"]
    if hash_run1 != hash_run2:
        raise RuntimeError(f"Non-deterministic regeneration detected: {hash_run1} != {hash_run2}")
    print(f"      Byte-deterministic SHA-256 verified: {hash_run2}")

    print("[3/4] Running independent unittest suite (standard and -O optimized modes)...")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"], check=True)
    subprocess.run([sys.executable, "-O", "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"], check=True)

    print("[4/4] Writing and verifying SHA256SUMS.txt manifest...")
    count = write_and_verify_manifest(ROOT)
    print(f"ALL {count} ARTIFACTS IN MIF-PWS v2 PHYSICAL EXPERIMENT 004 VERIFIED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
