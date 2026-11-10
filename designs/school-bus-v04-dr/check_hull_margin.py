"""Conservative CAD containment screen; not a physical small-parts test."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import numpy as np
from scipy.spatial import ConvexHull
from scipy.optimize import linprog

def vertices(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0] if len(data) >= 84 else -1
    if len(data) == 84 + count * 50:
        dtype = np.dtype([('normal','<f4',3),('v','<f4',(3,3)),('a','<u2')])
        return np.frombuffer(data, dtype=dtype, count=count, offset=84)['v'].reshape(-1,3).astype(float)
    return np.asarray(re.findall(rb'vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)',data), dtype=float)

def screen(points):
    hull = ConvexHull(np.unique(points,axis=0))
    planes = hull.equations
    normals = planes[:,:3]
    lengths = np.linalg.norm(normals,axis=1)
    constraints = np.column_stack([normals,lengths])
    result = linprog([0,0,0,-1], A_ub=constraints, b_ub=-planes[:,3], bounds=[(None,None)]*3+[(0,None)],method='highs')
    if not result.success:
        raise RuntimeError(result.message)
    residual = constraints @ result.x + planes[:,3]
    assert residual.max() < 1e-6
    return {'inscribed_sphere_diameter_mm':2*float(result.x[3]), 'centre_mm':result.x[:3].tolist(), 'maximum_constraint_violation_mm':float(residual.max()), 'hull_planes':len(planes)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('sources',nargs='+',type=Path)
    parser.add_argument('--widths',nargs='*',type=float,default=[])
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    points = np.concatenate([vertices(p) for p in args.sources])
    dimensions = np.ptp(points,axis=0)
    rows=[]
    for width in args.widths or [float(dimensions[1])]:
        transformed=points.copy(); transformed[:,1]*=width/dimensions[1]
        row={'target_width_mm':width,'y_scale':width/float(dimensions[1]),**screen(transformed)}
        row['internal_33mm_diameter_screen_pass']=row['inscribed_sphere_diameter_mm']>=33.0
        rows.append(row)
    report={'method':'Chebyshev insphere of STL vertex convex hull, linear programming against normalized hull halfspaces',
        'logic':'A rigid object fitting inside a convex cylinder implies its convex hull fits; a hull containing a sphere wider than the cylinder cannot fit in any orientation.',
        'limitation':'CAD-only ideal rigid shape. Not physical gauge, print tolerance, deformation or abuse/fracture testing; no child-use approval.',
        'gauge_opening_mm':31.75,'internal_screen_diameter_mm':33.0,
        'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in args.sources},
        'source_dimensions_mm':dimensions.tolist(),'candidates':rows}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(rows))

if __name__=='__main__':
    main()
