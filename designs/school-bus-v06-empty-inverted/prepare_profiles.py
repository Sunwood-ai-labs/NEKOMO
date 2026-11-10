"""Prepare file-only comparison profiles; never connects to a printer."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parent
SOURCE=ROOT.parent/'school-bus-v05-dfam/evidence/time-investigation/experiments/mono-boat-like.json'
base=json.loads(SOURCE.read_text(encoding='utf-8'))
for name,changes in {
    'same-62min-no-support':{},
    'pla-support':{'enable_support':'1','support_interface_spacing':'0.5','support_top_z_distance':'0.2','support_interface_filament':'1','support_on_build_plate_only':'0'},
}.items():
    profile=dict(base);profile.update(changes);profile['name']='NEKOMO v06 empty '+name
    (ROOT/'print'/('profile-'+name+'.json')).write_text(json.dumps(profile,indent=2),encoding='utf-8')
print('Prepared matching no-support baseline and removable PLA-support profiles.')
