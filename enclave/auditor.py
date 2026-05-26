#!/usr/bin/env python3
# SPDX-
"""
Audit a Python script inside an SGX enclave and emit an SGX quote.

Usage:
    python3 auditor.py <input.py> <output_dir>

Output:
    <output_dir>/audit_result.json  -- canonical JSON of AuditResult
    <output_dir>/quote.bin          -- SGX DCAP quote whose report_data
                                       is SHA-384(audit_result.json) padded
                                       to 64 bytes with trailing zeros.
"""

from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path

from bandit.core import config as b_config
from bandit.core import manager as b_manager

ATTESTATION_DIR = Path("/dev/attestation")
USER_REPORT_DATA = ATTESTATION_DIR / "user_report_data"
QUOTE = ATTESTATION_DIR / "quote"
REPORT_DATA_SIZE = 64  # SGX user_report_data is fixed 64 bytes

BANNED_CALLS = {"eval", "exec", "compile", "__import__"}
BANNED_MODULES = {"os", "subprocess", "ctypes", "socket", "shutil", "pickle"}

# Bandit severities >= this rank cause "fail".
SEVERITY_RANK = {"UNDEFINED": 0, "LOW": 1, "MEDIUM": 2, "HIGH": 3}
BANDIT_FAIL_THRESHOLD = SEVERITY_RANK["MEDIUM"]


def _is_banned_import(name: str | None) -> bool:
    if not name:
        return False
    return name.split(".", 1)[0] in BANNED_MODULES


def ast_check(code: str) -> bool:
    """Return True if the script passes the AST-based policy check."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name) and fn.id in BANNED_CALLS:
                return False
        elif isinstance(node, ast.Import):
            if any(_is_banned_import(a.name) for a in node.names):
                return False
        elif isinstance(node, ast.ImportFrom):
            if _is_banned_import(node.module):
                return False
    return True


def bandit_check(code_bytes: bytes) -> bool:
    """Return True iff bandit finds no issues at >= BANDIT_FAIL_THRESHOLD."""
    # Bandit's BanditManager operates on file paths, so spill to tmpfs.
    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="wb", delete=False, dir="/tmp"
    ) as tmp:
        tmp.write(code_bytes)
        tmp_path = tmp.name
    try:
        mgr = b_manager.BanditManager(b_config.BanditConfig(), agg_type="file")
        mgr.discover_files([tmp_path])
        mgr.run_tests()
        for issue in mgr.get_issue_list():
            sev = str(getattr(issue, "severity", "")).upper()
            if SEVERITY_RANK.get(sev, 0) >= BANDIT_FAIL_THRESHOLD:
                return False
        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def audit(code_bytes: bytes) -> str:
    """Run AST policy + bandit; success iff both pass."""
    code = code_bytes.decode("utf-8", errors="replace")
    if not ast_check(code):
        return "fail"
    if not bandit_check(code_bytes):
        return "fail"
    return "success"


def canonical_json(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def get_quote(report_data: bytes) -> bytes:
    if len(report_data) != REPORT_DATA_SIZE:
        raise ValueError(f"report_data must be {REPORT_DATA_SIZE} bytes")
    with open(USER_REPORT_DATA, "wb") as f:
        f.write(report_data)
    return QUOTE.read_bytes()


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(f"usage: {argv[0]} <input.py> <output_dir>", file=sys.stderr)
        return 2

    input_path = Path(argv[1])
    output_dir = Path(argv[2])
    output_dir.mkdir(parents=True, exist_ok=True)

    code_bytes = input_path.read_bytes()
    code_hash_hex = hashlib.sha384(code_bytes).hexdigest()

    audit_result = {
        "hashed": {"code": code_hash_hex},
        "raw": {"result": audit(code_bytes)},
    }
    audit_bytes = canonical_json(audit_result)
    audit_hash = hashlib.sha384(audit_bytes).digest()

    report_data = audit_hash.ljust(REPORT_DATA_SIZE, b"\x00")
    quote = get_quote(report_data)

    (output_dir / "audit_result.json").write_bytes(audit_bytes)
    (output_dir / "quote.bin").write_bytes(quote)

    print(audit_bytes.decode())
    print(f"audit_result_sha384={audit_hash.hex()}", file=sys.stderr)
    print(f"quote_size={len(quote)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
