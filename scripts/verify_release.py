#!/usr/bin/env python3
"""Check that this release's files match its immutable published SHA-256 list.

Worktree changes are intentionally NOT accepted as release-integrity PASS.
Generated reports, build output, caches, etc. are excluded from source discovery.
The manifest records every published file except itself (no self-hash cycle).
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "MANIFEST.sha256"
SOURCE_FOLDERS = ("python", "tests", "scripts", "cpp")
EXCLUDE_DIRS = {"__pycache__", ".pytest_cache"}
SOURCE_SUFFIXES = {".py", ".sh", ".cpp", ".h", ".hpp"}


def _is_safe_relative_name(name: str) -> bool:
    # A release manifest is untrusted until its paths have been validated.
    p = PurePosixPath(name)
    return (not p.is_absolute() and bool(p.parts)
            and all(part not in ("", ".", "..") for part in p.parts)
            and "\\" not in name)


def verify(root: Path = ROOT):
    manifest = root / "MANIFEST.sha256"
    if not manifest.is_file():
        return ["MISSING MANIFEST.sha256"], 0, 0
    known: dict[str, str] = {}
    problems: list[str] = []
    for idx, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) != 2:
            problems.append(f"INVALID manifest line {idx}: expected SHA256 and path")
            continue
        digest, name = parts
        name = name.removeprefix("./")
        if not _is_safe_relative_name(name):
            problems.append(f"INVALID manifest line {idx}: unsafe path {name!r}")
            continue
        if name in known:
            problems.append(f"INVALID manifest line {idx}: duplicate path {name}")
            continue
        if len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            problems.append(f"INVALID manifest line {idx}: malformed SHA256 for {name}")
            continue
        known[name] = digest

    # Existence and exact byte content, not timestamps or mtime.
    for name, digest in sorted(known.items()):
        path = root / name
        if path.is_symlink() or not path.is_file():
            problems.append(f"MISSING {name}" if not path.exists()
                            else f"INVALID nonregular file {name}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append(f"MISMATCH {name}")

    found: set[str] = set()
    for folder in SOURCE_FOLDERS:
        srcdir = root / folder
        if not srcdir.is_dir():
            problems.append(f"MISSING SOURCE DIR {folder}/")
            continue
        for path in srcdir.rglob("*"):
            if (path.is_file() and path.suffix in SOURCE_SUFFIXES
                    and not any(part in EXCLUDE_DIRS for part in path.relative_to(root).parts)):
                found.add(path.relative_to(root).as_posix())
    for name in sorted(found - known.keys()):
        problems.append(f"UNTRACKED {name}")
    return problems, len(known), len(found)


def main() -> int:
    problems, known_count, found_count = verify()
    if problems:
        print("RELEASE_INTEGRITY_ERROR: checkout differs from this release.", file=sys.stderr)
        for issue in problems[:100]:
            print("  " + issue, file=sys.stderr)
        if len(problems) > 100:
            print(f"  ... and {len(problems)-100} more", file=sys.stderr)
        print("Recovery: keep the existing worktree; unpack the release ZIP into a NEW",
              "empty directory and run 'python scripts/verify_release.py' there.",
              "Do not remove source folders or edit MANIFEST.sha256 to force PASS.",
              file=sys.stderr)
        print("Note: Phase6B's only supported name is scripts/validate_phase6b.sh.",
              file=sys.stderr)
        return 4
    print(f"RELEASE_INTEGRITY_PASS: {known_count} files hashed, "
          f"{found_count} source files present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
