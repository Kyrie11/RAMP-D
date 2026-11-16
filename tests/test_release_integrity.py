"""Release preflight behavior, independent of native C++/MPFR imports."""
import hashlib
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / 'scripts' / 'verify_release.py'


def _fixture(tmp_path):
    root = tmp_path / 'src'
    for folder in ('python', 'tests', 'scripts', 'cpp'):
        (root / folder).mkdir(parents=True)
    (root / 'scripts' / 'verify_release.py').write_bytes(SCRIPT.read_bytes())
    (root / 'scripts' / 'validate_phase6b.sh').write_text('#!/bin/sh\nexit 0\n')
    paths = [root / 'scripts' / 'verify_release.py', root / 'scripts' / 'validate_phase6b.sh']
    (root / 'MANIFEST.sha256').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest() + '  ./' + p.relative_to(root).as_posix() + '\n'
        for p in paths))
    return root


def _run(root):
    return subprocess.run([sys.executable, str(root / 'scripts' / 'verify_release.py')],
                          capture_output=True, text=True, check=False)


def test_clean_release_passes(tmp_path):
    root = _fixture(tmp_path)
    p = _run(root)
    assert p.returncode == 0, p.stderr
    assert 'RELEASE_INTEGRITY_PASS' in p.stdout


def test_missing_file_shows_exact_filename(tmp_path):
    root = _fixture(tmp_path)
    (root / 'scripts' / 'validate_phase6b.sh').unlink()
    p = _run(root)
    assert p.returncode == 4
    assert 'MISSING scripts/validate_phase6b.sh' in p.stderr
    assert 'NEW' in p.stderr


def test_edited_file_fails_with_mismatch(tmp_path):
    root = _fixture(tmp_path)
    (root / 'scripts' / 'validate_phase6b.sh').write_text('echo changed\n')
    p = _run(root)
    assert p.returncode == 4
    assert 'MISMATCH scripts/validate_phase6b.sh' in p.stderr


def test_untracked_source_detected(tmp_path):
    root = _fixture(tmp_path)
    (root / 'tests' / 'test_from_old_release.py').write_text('pass\n')
    p = _run(root)
    assert p.returncode == 4
    assert 'UNTRACKED tests/test_from_old_release.py' in p.stderr


def test_manifest_rejects_directory_traversal(tmp_path):
    root = _fixture(tmp_path)
    with (root / 'MANIFEST.sha256').open('a') as stream:
        stream.write('0'*64 + '  ../outside.py\n')
    p = _run(root)
    assert p.returncode == 4
    assert 'unsafe path' in p.stderr


def test_phase6b_lowercase_is_unique_canonical_entry():
    assert (REPO / 'scripts' / 'validate_phase6b.sh').is_file()
    assert not (REPO / 'scripts' / 'validate_phase6B.sh').exists()
    assert 'scripts/validate_phase6B.sh' not in (REPO / 'MANIFEST.sha256').read_text()
