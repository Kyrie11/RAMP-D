#!/usr/bin/env python3
"""Summarize infrastructure, exposure, and behavior validity for a RAPID-AD run."""
from __future__ import annotations
import argparse, csv, json, re
from pathlib import Path

PATTERNS = [
    ("rpc_timeout", re.compile(r"time.?out.*simulator|RPC.*timeout|time-out of .*ms", re.I)),
    ("ego_spawn_failure", re.compile(r"Failed to spawn ego|could not spawn.*vehicle|spawn.*failed", re.I)),
    ("client_server_mismatch", re.compile(r"version mismatch|client_version.*server_version", re.I)),
    ("native_crash", re.compile(r"returncode.?=.?-6|SIGABRT|Aborted \(core dumped\)", re.I)),
    ("model_or_controller_error", re.compile(r"CUDA out of memory|model load|controller.*exception|Traceback", re.I)),
]

def read_json(path: Path):
    try: return json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception: return {}

def main() -> int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", default="/data0/senzeyu2/dataset/RAPID-AD")
    ap.add_argument("--run-tag", required=True)
    ap.add_argument("--out", default=None)
    args=ap.parse_args()
    root=Path(args.data_root).expanduser().resolve()/"runs"/args.run_tag
    if not root.exists():
        print(f"Run directory not found: {root}"); return 1
    rows=[]
    for status_path in sorted(root.glob("**/parent_status.json")):
        status=read_json(status_path)
        epdir=status_path.parent
        metrics=read_json(epdir/"rapid_ad_metrics.json")
        text="\n".join((epdir/n).read_text(encoding="utf-8",errors="replace") for n in ("episode_stdout.log","episode_stderr.log") if (epdir/n).exists())
        cats=[name for name,pat in PATTERNS if pat.search(text)]
        if status.get("returncode",0)!=0 and not cats: cats.append("nonzero_exit_other")
        if not (epdir/"rapid_ad_metrics.json").exists(): cats.append("missing_metrics")
        if metrics and not metrics.get("setup_valid",False): cats.append("invalid_setup")
        if metrics and not metrics.get("exposure_valid",False): cats.append("invalid_exposure")
        rows.append({
            "run_tag":args.run_tag,"controller":status.get("controller"),"case_id":status.get("case_id"),
            "returncode":status.get("returncode"),"wall_timeout":status.get("wall_timeout"),
            "metrics_present":(epdir/"rapid_ad_metrics.json").exists(),
            "setup_valid":metrics.get("setup_valid"),"exposure_valid":metrics.get("exposure_valid"),
            "valid_for_causal_analysis":metrics.get("valid_for_causal_analysis"),
            "failure_type":metrics.get("failure_type"),"error_categories":";".join(sorted(set(cats))),
            "episode_dir":str(epdir),
        })
    out=Path(args.out).expanduser().resolve() if args.out else Path(args.data_root).expanduser().resolve()/"analysis"/args.run_tag/"run_health_summary.csv"
    out.parent.mkdir(parents=True,exist_ok=True)
    with out.open("w",newline="",encoding="utf-8") as fh:
        fields=list(rows[0].keys()) if rows else ["run_tag","controller","case_id","returncode","error_categories","episode_dir"]
        w=csv.DictWriter(fh,fieldnames=fields); w.writeheader(); w.writerows(rows)
    print(f"Episodes summarized: {len(rows)}")
    print(f"Summary: {out}")
    print("Infrastructure failures and invalid exposures are not policy failures; inspect them before outcome aggregation.")
    return 0
if __name__=="__main__": raise SystemExit(main())
