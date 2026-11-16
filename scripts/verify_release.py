#!/usr/bin/env python3
"""Reject incomplete/overlaid Phase6C trees before expensive regressions.

The SHA-256 manifest freezes this release's Python, C++ and test source.
Extra source files (often from overlaying Phase6C-A2 on the old release) are
not silently ignored. Generated build/reports are outside the manifest scope.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'MANIFEST.sha256'
SOURCE_FOLDERS = ('python', 'tests', 'scripts', 'cpp')
EXCLUDE_DIRS = {'__pycache__', '.pytest_cache'}


def main():
    if not MANIFEST.is_file():
        print('RELEASE_INTEGRITY_ERROR: MANIFEST.sha256 missing', file=sys.stderr)
        return 4
    known = {}
    for line in MANIFEST.read_text().splitlines():
        if not line.strip():
            continue
        try:
            digest, name = line.split(maxsplit=1)
        except ValueError:
            print('RELEASE_INTEGRITY_ERROR: malformed manifest entry', file=sys.stderr)
            return 4
        name = name.removeprefix('./')
        if name in known or not (len(digest) == 64 and all(c in '0123456789abcdef' for c in digest)):
            print('RELEASE_INTEGRITY_ERROR: duplicate/bad hash', file=sys.stderr)
            return 4
        known[name] = digest
    problems=[]
    for name, digest in known.items():
        path=ROOT/name
        if not path.is_file():
            problems.append('MISSING ' + name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            problems.append('MISMATCH ' + name)
    found=set()
    for folder in SOURCE_FOLDERS:
        for path in (ROOT/folder).rglob('*'):
            if path.is_file() and not any(part in EXCLUDE_DIRS for part in path.parts) and path.suffix in ('.py', '.sh', '.cpp', '.h', '.hpp'):
                found.add(path.relative_to(ROOT).as_posix())
    for name in sorted(found - known.keys()):
        problems.append('UNTRACKED ' + name)
    if problems:
        print('RELEASE_INTEGRITY_ERROR: source tree is mixed/corrupt; extract into a NEW empty directory.',file=sys.stderr)
        print('\n'.join(problems[:50]),file=sys.stderr)
        return 4
    print(f'RELEASE_INTEGRITY_PASS: {len(known)} files hashed, {len(found)} source files present')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
