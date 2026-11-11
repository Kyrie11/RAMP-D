#!/usr/bin/env python3
"""Replay a Phase 2 finite abstraction candidate certificate.

For this standalone command, evidence references are intentionally not trusted.
Use --allow-prefix only for synthetic fixtures. Production replay must import
an evidence verifier bound to the Phase 4 validated proof artifacts.
"""
import argparse
from pathlib import Path
from rampd_core import replay_invariant_certificate

if __name__ == '__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('certificate',type=Path)
    ap.add_argument('--allow-prefix',default=None,
        help='TEST ONLY: accept evidence refs with this prefix (e.g. demo-)')
    args=ap.parse_args()
    verifier=None if args.allow_prefix is None else lambda context: bool(
        context.evidence_ref and context.evidence_ref.startswith(args.allow_prefix))
    result=replay_invariant_certificate(args.certificate,verifier)
    print({'ok':result.ok,'message':result.message})
    if not result.ok: raise SystemExit(2)
