import hashlib
import json
from pathlib import Path
import re
import struct

import numpy as np


ROOT = Path(__file__).resolve().parent


def inspect_stl(path):
    data = path.read_bytes()
    count = struct.unpack_from('<I', data, 80)[0] if len(data) >= 84 else -1
    if len(data) == 84 + 50 * count:
        dtype = np.dtype([('normal', '<f4', 3), ('vertices', '<f4', (3, 3)), ('attribute', '<u2')])
        triangles = np.frombuffer(data, dtype=dtype, count=count, offset=84)['vertices'].astype(np.float64)
    else:
        pattern = rb'vertex\s+([-+\d.eE]+)\s+([-+\d.eE]+)\s+([-+\d.eE]+)'
        rows = re.findall(pattern, data)
        if not rows or len(rows) % 3:
            raise ValueError(f'Not a complete STL: {path.name}')
        triangles = np.asarray(rows, dtype=np.float64).reshape(-1, 3, 3)
        count = len(triangles)
    vertices, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    faces = inverse.reshape(-1, 3)
    edges = np.sort(np.concatenate([faces[:, [0, 1]], faces[:, [1, 2]], faces[:, [2, 0]]]), axis=1)
    unique_edges, multiplicity = np.unique(edges, axis=0, return_counts=True)
    parents = list(range(len(vertices)))

    def find(v):
        while parents[v] != v:
            parents[v] = parents[parents[v]]
            v = parents[v]
        return v

    for a, b in unique_edges:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parents[rb] = ra
    area2 = np.linalg.norm(np.cross(triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]), axis=1)
    signed_volume = float(np.einsum('ij,ij->i', triangles[:, 0], np.cross(triangles[:, 1], triangles[:, 2])).sum() / 6)
    report = {
        'file': str(path), 'sha256': hashlib.sha256(data).hexdigest(),
        'triangles': count, 'vertices': len(vertices),
        'bounds_mm': [vertices.min(axis=0).tolist(), vertices.max(axis=0).tolist()],
        'dimensions_mm': (vertices.max(axis=0) - vertices.min(axis=0)).tolist(),
        'boundary_edges': int((multiplicity == 1).sum()),
        'nonmanifold_edges': int((multiplicity > 2).sum()),
        'degenerate_triangles': int((area2 < 1e-9).sum()),
        'connected_vertex_components': len({find(i) for i in range(len(vertices))}),
        'signed_volume_mm3': signed_volume,
    }
    report['closed_two_manifold_edges'] = bool(np.all(multiplicity == 2))
    return report


def main():
    meshes = [inspect_stl(p) for p in sorted((ROOT / 'exports').glob('*.stl'))]
    if not meshes:
        raise RuntimeError('No exported STL exists.')
    failures = []
    for mesh in meshes:
        if not mesh['closed_two_manifold_edges'] or mesh['degenerate_triangles']:
            failures.append(f"Invalid mesh topology: {mesh['file']}")
        if min(mesh['bounds_mm'][0][2:]) < -0.01:
            failures.append(f"Geometry below print bed: {mesh['file']}")
        if max(mesh['dimensions_mm']) > 180:
            failures.append(f"Model exceeds A1 mini envelope: {mesh['file']}")
        if mesh['file'].endswith('-solid.stl') and mesh['connected_vertex_components'] != 1:
            failures.append('Whole bus STL is not a single connected component.')
    report = {'method': 'Independent binary STL edge incidence and geometry checks; not physical safety testing', 'meshes': meshes, 'failures': failures}
    (ROOT / 'evidence' / 'mesh-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'mesh_count': len(meshes), 'failures': failures, 'report': str(ROOT / 'evidence' / 'mesh-report.json')}))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
