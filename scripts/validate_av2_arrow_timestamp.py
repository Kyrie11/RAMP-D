#!/usr/bin/env python3
"""Real Arrow/Parquet fixture, separate from mandatory dependency-free gate."""
import argparse, json, sys, tempfile, types
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
# Isolate data adapter; never mock Arrow or time arithmetic.
pkg=types.ModuleType('rampd_core');pkg.__path__=[str(ROOT/'python/rampd_core')];sys.modules['rampd_core']=pkg
from rampd_core.record_adapters import parse_av2_parquet

def main():
    p=argparse.ArgumentParser();p.add_argument('--parquet',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();o={'status':'ERROR','scope':'REAL_ARROW_FIXTURE_AND_OPTIONAL_SINGLE_REAL_AV2_FILE'}
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        cases=[]
        with tempfile.TemporaryDirectory() as d:
            for unit,scale in [('ns',1),('us',1000),('ms',1000000)]:
                start=1700000000000000123 if unit=='ns' else 1700000000000000000
                end=start+200000000;rows=[]
                for tid,cat in [('AV',0),('focal',3)]:
                    for t in range(3):
                        rows.append(dict(scenario_id='fixture',track_id=tid,object_type='vehicle',object_category=cat,observed=t<2,timestep=t,position_x=float(t),position_y=0.,heading=0.,velocity_x=1.,velocity_y=0.,start_timestamp=start//scale,end_timestamp=end//scale,num_timestamps=3,focal_track_id='focal'))
                tbl=pa.Table.from_pylist(rows)
                for key in ('start_timestamp','end_timestamp'):
                    i=tbl.schema.get_field_index(key);tbl=tbl.set_column(i,key,tbl.column(i).cast(pa.timestamp(unit)))
                path=Path(d)/'scenario_fixture.parquet';pq.write_table(tbl,path)
                r=parse_av2_parquet(path,require_map=False);m=r.scene.manifest.metadata
                assert m['source_timestamps_start_ns']==start and m['source_timestamps_end_ns']==end
                assert r.scene.manifest.timestamps==(0.,0.1,0.2)
                cases.append({'unit':unit,'start_ns':start,'end_ns':end})
        o['fixtures']=cases;o['pyarrow']=pa.__version__
        if a.parquet:
            o['real_schema']=str(pq.ParquetFile(a.parquet).schema_arrow);r=parse_av2_parquet(a.parquet);o['real_scenario_id']=r.scene.manifest.scenario_id
        o['status']='PASS'
    except Exception as exc:o.update(reason=f'{type(exc).__name__}: {exc}')
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(o,indent=2)+'\n');print(json.dumps(o,indent=2));return 0 if o['status']=='PASS' else 4
if __name__=='__main__':raise SystemExit(main())
