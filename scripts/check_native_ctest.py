#!/usr/bin/env python3
"""Mandatory native regression discovery: ctest returning 0 with 0 tests is ERROR."""
from __future__ import annotations
import argparse
import json
import re
import subprocess
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('build_dir', type=Path)
    p.add_argument('--log', type=Path, required=True)
    args = p.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    build_dir = args.build_dir.resolve()
    if not (build_dir / 'CTestTestfile.cmake').is_file():
        args.log.write_text('ERROR: CTestTestfile.cmake missing; native tests NOT run\n')
        return 2
    cache = build_dir / 'CMakeCache.txt'
    if not cache.is_file() or 'RAMPD_BUILD_TESTS:BOOL=ON' not in cache.read_text(errors='replace'):
        args.log.write_text('ERROR: no configured RAMPD_BUILD_TESTS=ON in build cache\n')
        return 2
    def run(*rest):
        # CTest --test-dir was introduced only in CMake 3.20. Running within
        # the build directory works on both old and new versions, and prevents
        # accidentally scanning the repository root (Total Tests: 0).
        return subprocess.run(['ctest', *rest], cwd=build_dir,
                              capture_output=True, text=True, check=False)
    disc = run('-N')
    text = disc.stdout + disc.stderr
    match = re.search(r'Total Tests:\s*(\d+)', text)
    names = {'interval_cpp', 'picard_cpp', 'abi_cpp'}
    okay = (disc.returncode == 0 and match is not None and int(match.group(1)) >= 3
            and all(name in text for name in names))
    if not okay:
        args.log.write_text('ERROR: missing mandatory native tests\n' + text)
        return 2
    result = run('--output-on-failure')
    whole = text + '\n--- Execution ---\n' + result.stdout + result.stderr
    args.log.write_text(whole)
    summary = re.search(r'(\d+)%\s+tests passed,\s*(\d+)\s+tests failed out of\s*(\d+)',
                        result.stdout)
    if (result.returncode != 0 or summary is None or int(summary.group(1)) != 100
            or int(summary.group(2)) != 0 or int(summary.group(3)) < 3):
        return 2
    print(json.dumps({'status':'PASS', 'native_tests': int(match.group(1)),
                      'passed':int(summary.group(3)), 'log':str(args.log)}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
