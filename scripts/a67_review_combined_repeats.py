#!/usr/bin/env python3
"""Compare independent CARLA combined smoke JSON files, without certifying bounds."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from rampd_core.a67_repeat_campaign import review_combined_repeats

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--run',action='append',required=True,help='RUN_ID=/path/to/unique_raw.json; repeat')
    p.add_argument('--required',type=int,default=3)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    if a.output.exists():raise FileExistsError('REFUSE_OVERWRITE_EXISTING_REVIEW')
    runs={};paths=[]
    for item in a.run:
        if '=' not in item:raise ValueError('RUN_ID=PATH required')
        ident,path=item.split('=',1)
        file=Path(path).resolve()
        if not ident or ident in runs or file in paths or not file.is_file():
            raise ValueError('UNIQUE_RUN_ID_AND_EXISTING_DISTINCT_FILE_REQUIRED')
        if file==a.output.resolve():raise ValueError('REFUSE_OUTPUT_AS_INPUT')
        runs[ident]=file.read_bytes();paths.append(file)
    result=review_combined_repeats(runs,required=a.required)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    print(result['status'],result['reasons'])
    return 0 if result['status']=='DESCRIPTIVE_REPEAT_PROTOCOL_COMPLETE_UNCALIBRATED' else 4
if __name__=='__main__':raise SystemExit(main())
