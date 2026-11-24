#!/usr/bin/env python3
"""Fail-closed, scalable export with per-row quarantine, not whole-batch deletion.

The normalized A71 511NY source stream may contain missing event types (real
uploaded record 961). Preserve these in quarantine, do not invent a type or
promote report times to rule effective/receipt times. ROADWork input MUST be
actual group-disjoint templates, not a file listing/roadwork_files.json.
"""
import argparse,hashlib,json,os,sys,types
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root/'python'))
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(root/'python'/'rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.a71_event_auxiliary import adapt_511ny_report,adapt_roadwork_scene


def export_sources(inputs,output,quarantine):
    output=Path(output);quarantine=Path(quarantine)
    if output==quarantine or output.exists() or quarantine.exists():
        raise ValueError('REFUSE_OVERWRITE_OR_COLLIDING_OUTPUTS')
    if not inputs:raise ValueError('at least one source required')
    output.parent.mkdir(parents=True,exist_ok=True);quarantine.parent.mkdir(parents=True,exist_ok=True)
    tmpout=output.with_name(output.name+'.a72_tmp');tmpbad=quarantine.with_name(quarantine.name+'.a72_tmp')
    if tmpout.exists() or tmpbad.exists():raise ValueError('REFUSE_STALE_TEMPFILES')
    counts={'source_rows':0,'accepted':0,'quarantined':0,'accepted_511ny':0,'accepted_roadwork':0}
    try:
        with tmpout.open('w',encoding='utf8') as good,tmpbad.open('w',encoding='utf8') as bad:
            for source,kind in inputs:
                if kind not in ('511ny','roadwork'):raise ValueError('unsupported source kind')
                with Path(source).open(encoding='utf8') as f:
                    for n,line in enumerate(f,1):
                        if not line.strip():continue
                        counts['source_rows']+=1
                        try:
                            row=json.loads(line,parse_constant=lambda x: (_ for _ in ()).throw(ValueError('non-finite JSON')))
                            if type(row) is not dict:raise ValueError('object JSONL required')
                            item=adapt_511ny_report(row) if kind=='511ny' else adapt_roadwork_scene(row)
                            if item['status'] not in ('DESCRIPTIVE_REPORT_TIMES_ONLY','DESCRIPTIVE_WORKZONE_OBJECTS_ONLY'):
                                raise ValueError('source record has uncertain or inverted timestamp')
                            good.write(json.dumps(item,ensure_ascii=False,allow_nan=False)+'\n')
                            counts['accepted']+=1;counts['accepted_'+kind]+=1
                        except (ValueError,TypeError,KeyError,IndexError) as exc:
                            bad.write(json.dumps(dict(kind=kind,input_path=str(source),input_line=n,
                                raw_line_sha256=hashlib.sha256(line.encode()).hexdigest(),
                                reason=f'{type(exc).__name__}:{exc}',
                                formal_labels_authorized=False),ensure_ascii=False)+'\n')
                            counts['quarantined']+=1
        os.replace(tmpout,output);os.replace(tmpbad,quarantine)
    finally:
        for p in (tmpout,tmpbad):
            if p.exists():p.unlink()
    return dict(schema='rampd.a72.auxiliary_export.v1',status=('DESCRIPTIVE_PARTIAL_WITH_QUARANTINE'
        if counts['quarantined'] and counts['accepted'] else 'DESCRIPTIVE_AUXILIARY_EXPORT'
        if counts['accepted'] else 'REVIEW'),counts=counts,
        no_missing_type_imputation=True,physical_rule_effectivity_known=False,
        metric_closure_geometry_known=False,official_sign_authority_verified=False,
        all_formal_label_masks_zero=True)

def main():
    a=argparse.ArgumentParser();a.add_argument('--normalized-511ny',type=Path)
    a.add_argument('--roadwork-templates',type=Path)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--quarantine',type=Path,required=True);args=a.parse_args()
    sources=[(p,k) for p,k in ((args.normalized_511ny,'511ny'),(args.roadwork_templates,'roadwork')) if p]
    r=export_sources(sources,args.output,args.quarantine)
    args.output.with_suffix(args.output.suffix+'.audit.json').write_text(json.dumps(r,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps(r,ensure_ascii=False));return 0 if r['counts']['accepted'] else 4
if __name__=='__main__':raise SystemExit(main())
