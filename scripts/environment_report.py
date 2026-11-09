#!/usr/bin/env python3
"""Record selected reproducibility metadata, never the full environment."""
import argparse
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
from rampd_core import backend_name,build_info,__version__
from rampd_core.interval import LIBRARY_PATH

def command(args):
    try:
        r=subprocess.run(args,capture_output=True,text=True,timeout=10,check=False)
        return (r.stdout+r.stderr).strip()
    except (OSError,subprocess.TimeoutExpired) as e: return str(e)

def source_hashes(root):
    files=[]
    for base in ['cpp','python','tests','scripts','configs']:
        files += [p for p in (root/base).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [root/'CMakeLists.txt',root/'pyproject.toml']
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);args=ap.parse_args()
    root=Path(__file__).resolve().parents[1]
    d=dict(version=__version__,python=sys.version,python_executable=sys.executable,
           platform=platform.platform(),machine=platform.machine(),backend=backend_name(),
           native_build=build_info(),library_path=LIBRARY_PATH,
           library_sha256=hashlib.sha256(Path(LIBRARY_PATH).read_bytes()).hexdigest(),
           compiler=command(['c++','--version']),cmake=command(['cmake','--version']),
           ctest=command(['ctest','--version']),linked_libraries=command(['ldd',LIBRARY_PATH]),
           pytest=importlib.metadata.version('pytest'),mpmath=importlib.metadata.version('mpmath'),
           source_sha256=source_hashes(root))
    p=Path(args.output);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(d,indent=2)+'\n',encoding='utf-8')
    print('environment metadata:',p)
