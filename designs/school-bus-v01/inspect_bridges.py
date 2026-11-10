import json
import math
from pathlib import Path
import re
import zipfile


ROOT = Path(__file__).resolve().parent


def inspect(path):
    with zipfile.ZipFile(path) as archive:
        lines = archive.read('Metadata/plate_1.gcode').decode('utf-8').splitlines()
    position = {'X': None, 'Y': None, 'Z': None, 'E': 0.0}
    relative_e = False
    feature = ''
    bridges = []
    support_moves = 0
    for number, raw in enumerate(lines, 1):
        if raw.startswith('; FEATURE:'):
            feature = raw.split(':', 1)[1].strip()
            continue
        command = raw.split(';', 1)[0].strip()
        if command == 'M83':
            relative_e = True
        elif command == 'M82':
            relative_e = False
        values = {key: float(value) for key, value in re.findall(r'([XYZE])(-?\d+(?:\.\d+)?)', command)}
        if command.startswith('G92 '):
            position.update(values)
            continue
        if not re.match(r'^G[0123](?:\s|$)', command):
            continue
        end = dict(position)
        end.update(values)
        extrusion = values.get('E', 0.0) if relative_e else end['E'] - position['E']
        if relative_e:
            end['E'] = position['E'] + values.get('E', 0.0)
        if extrusion > 0 and position['X'] is not None and position['Y'] is not None:
            distance = math.hypot(end['X'] - position['X'], end['Y'] - position['Y'])
            if feature == 'Bridge' and re.match(r'^G[01](?:\s|$)', command) and distance > 0:
                bridges.append({'line': number, 'length_mm': distance, 'from_xy': [position['X'], position['Y']], 'to_xy': [end['X'], end['Y']], 'z_mm': end['Z']})
            if feature.lower().startswith('support'):
                support_moves += 1
        position = end
    return {'file': str(path), 'measurement': 'Longest straight positive-extrusion move marked FEATURE Bridge; not total unsupported span or physical sag measurement', 'bridge_moves': len(bridges), 'support_extrusion_moves': support_moves, 'longest': sorted(bridges, key=lambda b: b['length_mm'], reverse=True)[:5]}


result = {'full_bus': inspect(ROOT / 'print' / 'nekomo-school-bus-v01-two-color-sliced.3mf'), 'rear_window_coupon': inspect(ROOT / 'print' / 'rear-window-bridge-coupon-sliced.3mf')}
(ROOT / 'evidence' / 'bridge-comparison.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
print(json.dumps({name: {'max_bridge_move_mm': data['longest'][0]['length_mm'], 'z_mm': data['longest'][0]['z_mm'], 'support_moves': data['support_extrusion_moves']} for name, data in result.items()}))
