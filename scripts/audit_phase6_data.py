#!/usr/bin/env python3
"""Run the Phase 6A read-only dataset manifest audit."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import sys

try:
    # Normal installed checkout.  The native interval backend is intentionally
    # fail-closed for the numerical package, but a directory manifest audit
    # must still be runnable before that backend is built.
    from rampd_core.dataset_audit import audit_from_config
except FileNotFoundError:
    module_path = Path(__file__).resolve().parents[1] / "python" / "rampd_core" / "dataset_audit.py"
    spec = importlib.util.spec_from_file_location("rampd_phase6_dataset_audit", module_path)
    if spec is None or spec.loader is None:
        raise
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    audit_from_config = module.audit_from_config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-files", type=int, default=10)
    parser.add_argument("--strict", action="store_true",
                        help="return nonzero for missing splits or parser dependencies")
    args = parser.parse_args()
    if args.max_files <= 0:
        parser.error("--max-files must be positive")
    try:
        config = json.loads(args.config.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        print(f"CONFIG_ERROR:{type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    report = audit_from_config(config, max_files=args.max_files)
    payload = report.to_dict()
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered)
    print(rendered, end="")
    if args.strict and report.status != "PASS":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

