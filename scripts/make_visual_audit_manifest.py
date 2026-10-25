#!/usr/bin/env python3
"""Create a CSV checklist for auditing a small set of RAPID-AD diagnostic frames."""
from __future__ import annotations
import argparse, csv, json
from pathlib import Path

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data-root", default="/data0/senzeyu2/dataset/RAPID-AD")
    ap.add_argument("--run-tag", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    root = Path(args.data_root).expanduser().resolve() / "runs" / args.run_tag
    rows = []
    for path in sorted(root.glob("**/rapid_ad_metrics.json")):
        try:
            m = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        case = m.get("case") or {}
        frames = {str(f.get("label")): str(f.get("path", "")) for f in (m.get("diagnostic_frames") or [])}
        rows.append({
            "run_tag": args.run_tag, "controller": m.get("controller"), "case_id": case.get("case_id"),
            "task": case.get("task"), "transition_expected": m.get("transition_expected"),
            "gap_timing": case.get("gap_timing"), "transition_time_s": m.get("transition_time_s"),
            "anchor_time_s": m.get("anchor_time_s"), "mask_start_s": m.get("input_mask_start_time_s"),
            "mask_end_s": m.get("input_mask_end_time_s"), "evidence_available_time_s": m.get("evidence_available_time_s"),
            "first_raw_frame": frames.get("first_raw_frame", ""),
            "transition_raw": frames.get("transition_raw", ""),
            "transition_delivered": frames.get("transition_delivered", ""),
            "first_mask_raw": frames.get("first_mask_raw", ""),
            "first_mask_delivered": frames.get("first_mask_delivered", ""),
            "first_fresh_raw": frames.get("first_fresh_raw", ""),
            "first_fresh_delivered": frames.get("first_fresh_delivered", ""),
            "officer_visible": "", "control_line_visible": "",
            "new_directive_visible_in_first_fresh_frame": "",
            "delivered_frame_is_stale_during_mask": "",
            "audit_pass": "", "notes": "",
        })
    if not rows:
        print(f"No metrics found under {root}")
        return 1
    out = Path(args.out).expanduser().resolve() if args.out else (Path(args.data_root).expanduser().resolve() / "analysis" / args.run_tag / "visual_audit_manifest.csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader(); writer.writerows(rows)
    print(f"Wrote {len(rows)} audit rows: {out}")
    print("Fill audit fields with yes/no/uncertain; set audit_pass=yes only if the cue, control line, and requested frame-hold behavior are visually verified.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
