"""Collect actual slicer outputs; runtime predictions are not print tests."""
import hashlib,json,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sources=[ROOT.parent/'school-bus-v05-dfam/evidence/time-investigation/experiments/mono-boat-like-result.json']
sources+=sorted((ROOT/'evidence').glob('slice-*.json'))
records=[]
for source in sources:
    data=json.loads(source.read_text(encoding='utf-8'))
    result=data.get('slicer_result',{})
    if result.get('return_code')!=0:
        records.append({'case':source.stem,'success':False,'source_result':str(source)});continue
    p=result['sliced_plates'][0]
    case=source.stem.replace('slice-','')
    local=ROOT/'print'/(case+'-sliced.3mf')
    if case=='mono-boat-like-result':local=source.parent/'mono-boat-like-sliced.3mf'
    assert local.is_file(),local
    records.append({'case':case,'status':'superseded-seat-remnants' if case.startswith('empty-') else 'current-comparison','success':True,'seconds':p['total_predication'],'filament_g':sum(f['total_used_g'] for f in p['filaments']),'changes':p['filament_change_times'],'warning':p.get('warning_message',''),'features':p.get('feature_type_times',{}),'source_result':str(source),'sliced_file':str(local),'sha256':hashlib.sha256(local.read_bytes()).hexdigest()})
    with zipfile.ZipFile(local) as z:
        for name in ('Metadata/plate_1.png','Metadata/top_1.png'):
            if name in z.namelist():(ROOT/'images'/(case+'-'+Path(name).name)).write_bytes(z.read(name))
(ROOT/'evidence/comparison.json').write_text(json.dumps({'scope':'Single-white PLA. One slicer run per condition. Predictions, not observed print runtimes. No printer dispatch.','records':records},indent=2),encoding='utf-8')
print(json.dumps([{k:r[k] for k in ('case','seconds','filament_g','changes','warning') if k in r} for r in records],indent=2))
