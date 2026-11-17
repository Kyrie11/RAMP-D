#!/usr/bin/env python3
"""Fail-closed native test discovery and execution (including old CTest)."""
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
from pathlib import Path

MANDATORY = {'interval_cpp', 'picard_cpp', 'abi_cpp'}
DISCOVERY_ROW = re.compile(r'^\s*Test\s+#\d+:\s*(.*?)\s*$', re.M)
EXECUTION_ROW = re.compile(r'^\s*\d+\s*/\s*\d+\s+Test\s+#\d+:\s*(\S+)\s+\.+\s+Passed\b', re.M)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('build_dir', type=Path)
    p.add_argument('--log', type=Path, required=True)
    args = p.parse_args()
    args.log.parent.mkdir(parents=True, exist_ok=True)
    build_dir = args.build_dir.resolve()

    def fail(reason, details=''):
        args.log.write_text('ERROR: ' + reason + '\n' + details)
        return 2

    if not (build_dir / 'CTestTestfile.cmake').is_file():
        return fail('CTestTestfile.cmake missing; native tests NOT run')
    cache = build_dir / 'CMakeCache.txt'
    if not cache.is_file() or not re.search(
            r'^RAMPD_BUILD_TESTS:BOOL=ON\s*$', cache.read_text(errors='replace'), re.M):
        return fail('no configured RAMPD_BUILD_TESTS=ON in build cache')

    def run(*rest):
        # CTest --test-dir was introduced in CMake 3.20. Using cwd also
        # prevents accidental discovery in the repository root.
        return subprocess.run(['ctest', *rest], cwd=build_dir,
                              env={**os.environ, 'LC_ALL': 'C'},
                              capture_output=True, text=True, check=False)
    try:
        disc = run('-N')
    except OSError as exc:
        return fail('CTest discovery could not start', str(exc))
    text = disc.stdout + disc.stderr
    matches = re.findall(r'^\s*Total Tests:\s*(\d+)\s*$', text, re.M)
    names = DISCOVERY_ROW.findall(text)
    if (disc.returncode != 0 or len(matches) != 1 or
            int(matches[0]) != len(names) or len(names) != len(set(names)) or
            not MANDATORY.issubset(names)):
        return fail('missing mandatory native tests', text)
    try:
        result = run('--output-on-failure')
    except OSError as exc:
        return fail('CTest execution could not start', text + '\n' + str(exc))
    whole = text + '\n--- Execution ---\n' + result.stdout + result.stderr
    summary = re.search(r'(\d+)%\s+tests passed,\s*(\d+)\s+tests failed out of\s*(\d+)',
                        result.stdout)
    passed = EXECUTION_ROW.findall(result.stdout)
    # 100% alone is not sufficient: CTest can omit disabled/skipped tests.
    # Require every discovered test to actually have a Passed record.
    if (result.returncode != 0 or summary is None or int(summary.group(1)) != 100
            or int(summary.group(2)) != 0 or int(summary.group(3)) != len(names)
            or len(passed) != len(names) or set(passed) != set(names)):
        return fail('native test execution incomplete or failed', whole)
    args.log.write_text(whole)
    print(json.dumps({'status': 'PASS', 'native_tests': len(names),
                      'passed': len(passed), 'log': str(args.log)}))
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
