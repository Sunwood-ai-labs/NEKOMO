"""Build and inspect a partial floor-opening intermediate.

Run with FreeCAD's headless MCP runner. This builds CAD geometry and exports
meshes only. The current cut removes the floor and three Bench features but leaves
raised seatback geometry. It is not an empty-cabin candidate or print approval.
"""
from pathlib import Path
import hashlib
import json
import math
import struct

import FreeCAD as App
import MeshPart
import Part


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / "school-bus-v04-dr" / "cad" / "nekomo-school-bus-v04.FCStd"
CAD = ROOT / "cad" / "nekomo-school-bus-v06-empty-inverted.FCStd"
EXPORTS = ROOT / "exports"
EVIDENCE = ROOT / "evidence" / "geometry.json"
SCALE_XZ = 60.0 / 160.2561472076974
MESH_LINEAR = 0.06
MESH_ANGULAR = 0.12

# The floor opening stops inside the side rails and fore/aft weld-collar roots.
# It starts above the fixed tyre lateral envelope and spans the cabin floor.
FLOOR_OPENING = (14.0, 2.8, -1.0, 53.0, 25.9, 8.237)
BENCH_NAMES = ("Bench0", "Bench1", "Bench2")
WHEEL_NAMES = ("Wheel00", "Wheel01", "Wheel10", "Wheel11")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def mesh_of(shape, path=None):
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=MESH_LINEAR,
        AngularDeflection=MESH_ANGULAR,
        Relative=False,
    )
    if path is not None:
        mesh.write(str(path))
    bb = mesh.BoundBox
    return mesh, {
        "triangle_count": int(mesh.CountFacets),
        "bounds_mm": [float(bb.XMin), float(bb.YMin), float(bb.ZMin),
                      float(bb.XMax), float(bb.YMax), float(bb.ZMax)],
        "dimensions_mm": [float(bb.XLength), float(bb.YLength), float(bb.ZLength)],
    }


def shape_stats(shape):
    return {
        "valid": bool(shape.isValid()),
        "closed": bool(shape.isClosed()),
        "solid_count": len(shape.Solids),
        "volume_mm3": float(shape.Volume),
        "face_count": len(shape.Faces),
    }


def triangle_topology(path):
    raw = Path(path).read_bytes()
    if len(raw) < 84:
        raise RuntimeError("STL is shorter than its binary header")
    count = struct.unpack_from("<I", raw, 80)[0]
    if len(raw) != 84 + 50 * count:
        raise RuntimeError("STL did not export as a complete binary triangle mesh")
    edge_owners = {}
    parent = list(range(count))

    def find(item):
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for i in range(count):
        values = struct.unpack_from("<12fH", raw, 84 + 50 * i)
        points = [tuple(round(values[k + j], 5) for j in range(3))
                  for k in (3, 6, 9)]
        for a, b in ((points[0], points[1]), (points[1], points[2]),
                     (points[2], points[0])):
            edge = tuple(sorted((a, b)))
            owners = edge_owners.get(edge)
            if owners is None:
                edge_owners[edge] = i
            else:
                union(i, owners)
                edge_owners[edge] = -1 if owners >= 0 else owners
    incidence = {}
    for edge, owner in edge_owners.items():
        # The owner table above keeps the first triangle index. Recount below
        # from the STL once so non-manifold edges remain visible.
        incidence[edge] = 0
    for i in range(count):
        values = struct.unpack_from("<12fH", raw, 84 + 50 * i)
        points = [tuple(round(values[k + j], 5) for j in range(3))
                  for k in (3, 6, 9)]
        for a, b in ((points[0], points[1]), (points[1], points[2]),
                     (points[2], points[0])):
            incidence[tuple(sorted((a, b)))] += 1
    components = len({find(i) for i in range(count)})
    counts = {}
    for n in incidence.values():
        counts[str(n)] = counts.get(str(n), 0) + 1
    return {
        "triangle_count": count,
        "connected_components": components,
        "edge_incidence_histogram": counts,
        "closed_two_manifold": bool(incidence) and all(n == 2 for n in incidence.values()),
    }


def add_shape(doc, name, label, shape, color):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyColor", "DisplayColor", "Presentation")
    obj.DisplayColor = color
    view = getattr(obj, "ViewObject", None)
    if view is not None:
        view.ShapeColor = color
    return obj


def main():
    for folder in (CAD.parent, EXPORTS, EVIDENCE.parent):
        folder.mkdir(parents=True, exist_ok=True)
    source_hash = sha256(SOURCE)
    source_doc = App.openDocument(str(SOURCE))
    physical_obj = source_doc.getObject("PhysicalBus")
    red_obj = source_doc.getObject("RedModel")
    if physical_obj is None or red_obj is None:
        raise RuntimeError("v04 CAD must contain PhysicalBus and RedModel")
    physical = physical_obj.Shape.copy()
    source_red = red_obj.Shape.copy()

    scale_y = float(source_doc.getObject("WidenedChassisInput").YScaleFactor)
    chassis_mesh, _ = mesh_of(source_doc.getObject("MiniChassis").Shape)
    chassis_center_y = (chassis_mesh.BoundBox.YMin + chassis_mesh.BoundBox.YMax) / 2.0
    transform = App.Matrix()
    transform.A11 = SCALE_XZ
    transform.A22 = SCALE_XZ * scale_y
    transform.A24 = chassis_center_y * (1.0 - scale_y)
    transform.A33 = SCALE_XZ

    benches = []
    for name in BENCH_NAMES:
        source_obj = source_doc.getObject(name)
        if source_obj is None:
            raise RuntimeError("Missing source bench feature: " + name)
        bench = source_obj.Shape.copy().transformGeometry(transform)
        if not bench.isValid() or not bench.isClosed() or len(bench.Solids) != 1:
            raise RuntimeError("Source bench is not one closed solid: " + name)
        outside_v04 = bench.cut(physical).Volume
        if abs(outside_v04) > 0.01:
            raise RuntimeError("Transformed bench extends beyond v04 physical shape: %s %.6f mm3" % (name, outside_v04))
        benches.append((name, bench))

    x0, y0, z0, x1, y1, z1 = FLOOR_OPENING
    floor_tool = Part.makeBox(x1 - x0, y1 - y0, z1 - z0, App.Vector(x0, y0, z0))
    bench_union = benches[0][1].fuse(benches[1][1]).fuse(benches[2][1]).removeSplitter()
    cutter = floor_tool.fuse(bench_union).removeSplitter()
    candidate = physical.cut(cutter).removeSplitter()
    if not candidate.isValid() or not candidate.isClosed() or len(candidate.Solids) != 1:
        raise RuntimeError("Candidate must stay one valid closed solid: %r" % shape_stats(candidate))

    removed = physical.cut(candidate).removeSplitter()
    unintended = removed.cut(cutter).Volume
    uncut_tool = physical.common(cutter).cut(removed).Volume
    cavity_residual = candidate.common(floor_tool).Volume
    bench_residuals = {name: float(candidate.common(bench).Volume) for name, bench in benches}
    clearance_box = Part.makeBox(53.0 - 14.0, 22.0 - 6.0, 29.3 - 8.247,
                                 App.Vector(14.0, 6.0, 8.247))
    clearance_common = candidate.common(clearance_box).removeSplitter()
    central_clearance = {
        "bounds_mm": [14.0, 6.0, 8.247, 53.0, 22.0, 29.3],
        "occupancy_volume_mm3": float(clearance_common.Volume),
        "solid_count": len(clearance_common.Solids),
        "passed": bool(clearance_common.Volume <= 0.05),
        "remaining_bounds_mm": [
            [float(s.BoundBox.XMin), float(s.BoundBox.YMin), float(s.BoundBox.ZMin),
             float(s.BoundBox.XMax), float(s.BoundBox.YMax), float(s.BoundBox.ZMax)]
            for s in clearance_common.Solids
        ],
    }
    if max(unintended, uncut_tool, cavity_residual, *(bench_residuals.values())) > 0.05:
        raise RuntimeError("Cut checks failed: unintended=%g uncut_tool=%g cavity=%g benches=%r" %
                           (unintended, uncut_tool, cavity_residual, bench_residuals))

    wheel_checks = {}
    for name in WHEEL_NAMES:
        wheel_obj = source_doc.getObject(name)
        wheel = wheel_obj.Shape.copy().transformGeometry(transform)
        if wheel.cut(physical).Volume > 0.05:
            raise RuntimeError("Transformed fixed wheel does not lie inside v04 physical: " + name)
        removed_wheel = wheel.cut(candidate).Volume
        wheel_checks[name] = {
            "source_inside_v04": True,
            "removed_volume_mm3": float(removed_wheel),
            "remaining_volume_mm3": float(wheel.common(candidate).Volume),
        }
        if removed_wheel > 0.05:
            raise RuntimeError("Floor cutter removes fixed tyre geometry: %s %.6f mm3" % (name, removed_wheel))

    # Export the one-piece inverted mesh first so it is available for slicing.
    upright_stl = EXPORTS / "bus-v06-empty-upright.stl"
    inverted_stl = EXPORTS / "bus-v06-empty-inverted.stl"
    upright_mesh, physical_mesh_stats = mesh_of(candidate, upright_stl)
    height = float(upright_mesh.BoundBox.ZMax)
    rotation = App.Matrix()
    rotation.A11 = 1.0
    rotation.A22 = -1.0
    rotation.A33 = -1.0
    rotation.A34 = height
    inverted_shape = candidate.copy().transformGeometry(rotation)
    inverted_mesh, inverted_mesh_stats = mesh_of(inverted_shape, inverted_stl)
    z_min = float(inverted_mesh.BoundBox.ZMin)
    if abs(z_min) > 0.02:
        translate = App.Matrix()
        translate.A11 = 1.0
        translate.A22 = 1.0
        translate.A33 = 1.0
        translate.A34 = -z_min
        inverted_shape = inverted_shape.copy().transformGeometry(translate)
        inverted_mesh, inverted_mesh_stats = mesh_of(inverted_shape, inverted_stl)
    if abs(inverted_mesh.BoundBox.ZMin) > 0.02:
        raise RuntimeError("Inverted STL does not sit at z=0")
    mono_topology = triangle_topology(inverted_stl)
    if not mono_topology["closed_two_manifold"] or mono_topology["connected_components"] != 1:
        raise RuntimeError("Inverted physical STL must be a closed, one-component mesh: %r" % mono_topology)
    dimensions = physical_mesh_stats["dimensions_mm"]
    if (abs(dimensions[0] - 60.0) > 0.05 or abs(dimensions[1] - 34.0) > 0.05
            or abs(dimensions[2] - 35.568) > 0.05):
        raise RuntimeError("Candidate dimensions changed: %r" % dimensions)

    # Partition the candidate using the exact source red mask, then export both
    # orientations from the same rigid transform used by the mono mesh.
    red = source_red.common(candidate).removeSplitter()
    white = candidate.cut(red).removeSplitter()
    overlap = red.common(white).Volume
    missing = candidate.cut(red.fuse(white)).Volume
    extra = red.fuse(white).cut(candidate).Volume
    if max(overlap, missing, extra) > 0.05:
        raise RuntimeError("Color partition does not cover physical candidate: %g %g %g" %
                           (overlap, missing, extra))

    color_meshes = {}
    for color_name, shape in (("red", red), ("white", white)):
        mesh_of(shape, EXPORTS / ("bus-v06-empty-%s.stl" % color_name))
        turned = shape.copy().transformGeometry(rotation)
        turned.translate(App.Vector(0, 0, -z_min))
        _, turned_stats = mesh_of(turned, EXPORTS / ("bus-v06-empty-inverted-%s.stl" % color_name))
        color_meshes[color_name] = turned_stats
    Part.export([add_shape(source_doc, "TemporaryCandidateExport", "Temporary candidate", candidate, (0.7, 0.7, 0.7))],
                str(EXPORTS / "bus-v06-empty.step"))
    source_doc.removeObject("TemporaryCandidateExport")

    out_doc = App.newDocument("NekomoSchoolBusV06EmptyInverted")
    out_doc.Label = "NEKOMO school bus v06 floorless empty-cabin candidate"
    physical_native = add_shape(out_doc, "PhysicalBus", "Floorless, seatless one-piece bus", candidate, (0.75, 0.75, 0.75))
    red_native = add_shape(out_doc, "RedModel", "Red regions clipped to candidate", red, (0.76, 0.18, 0.12))
    white_native = add_shape(out_doc, "WhiteModel", "White regions clipped to candidate", white, (0.95, 0.95, 0.95))
    tool_native = add_shape(out_doc, "FloorOpeningTool", "Open underside floor cutter", floor_tool, (0.2, 0.8, 0.2))
    for obj in (physical_native, red_native, white_native, tool_native):
        view = getattr(obj, "ViewObject", None)
        if view is not None:
            view.Visibility = obj in (red_native, white_native)
    out_doc.recompute()
    out_doc.saveAs(str(CAD))
    cad_hash = sha256(CAD)
    App.closeDocument(out_doc.Name)
    reopened = App.openDocument(str(CAD))
    reopened_physical = reopened.getObject("PhysicalBus").Shape
    reopened_color = {
        "physical": shape_stats(reopened_physical),
        "red": shape_stats(reopened.getObject("RedModel").Shape),
        "white": shape_stats(reopened.getObject("WhiteModel").Shape),
    }
    if not reopened_physical.isValid() or not reopened_physical.isClosed() or len(reopened_physical.Solids) != 1:
        raise RuntimeError("Reopened native CAD failed the one-solid check")

    report = {
        "revision": "v06-partial-cavity-intermediate",
        "completion_status": "Superseded: central cabin clearance failed; do not treat as an empty-cabin candidate.",
        "basis": "Headless FreeCAD/OCCT geometry and STL topology only. No slicing, printer connection, print-strength, or toy-safety validation was performed.",
        "source_cad_relative_path": "../school-bus-v04-dr/cad/nekomo-school-bus-v04.FCStd",
        "source_sha256_before": source_hash,
        "source_sha256_after": sha256(SOURCE),
        "source_unchanged": source_hash == sha256(SOURCE),
        "candidate_cad_relative_path": "cad/nekomo-school-bus-v06-empty-inverted.FCStd",
        "candidate_cad_sha256": cad_hash,
        "physical": shape_stats(candidate),
        "physical_mesh_upright": physical_mesh_stats,
        "physical_mesh_inverted": inverted_mesh_stats,
        "inverted_stl_topology": mono_topology,
        "removed_features": {
            "benches": [{"feature": name, "source_valid_one_solid": True,
                         "residual_in_candidate_mm3": bench_residuals[name]} for name, _ in benches],
            "floor_opening_bounds_mm": list(FLOOR_OPENING),
            "opening_volume_remaining_mm3": float(cavity_residual),
            "unintended_removed_material_mm3": float(unintended),
        },
        "central_cabin_clearance_validation": central_clearance,
        "retained_geometry": {
            "fixed_wheels": wheel_checks,
            "fixed_wheels_removed_volume_max_mm3": max(x["removed_volume_mm3"] for x in wheel_checks.values()),
            "side_rail_inner_clearance_mm": [2.8 - 0.0, 34.0 - 2.8 - 25.9],
            "front_rear_cavity_end_margins_mm": [14.0, 60.0 - 53.0],
        },
        "color_partition": {
            "red": shape_stats(red), "white": shape_stats(white),
            "red_white_intersection_mm3": float(overlap),
            "uncovered_physical_mm3": float(missing),
            "extra_beyond_physical_mm3": float(extra),
            "inverted_meshes": color_meshes,
        },
        "reopened_native_cad": reopened_color,
        "exports": [
            "exports/bus-v06-empty-upright.stl",
            "exports/bus-v06-empty-inverted.stl",
            "exports/bus-v06-empty-red.stl",
            "exports/bus-v06-empty-white.stl",
            "exports/bus-v06-empty-inverted-red.stl",
            "exports/bus-v06-empty-inverted-white.stl",
            "exports/bus-v06-empty.step",
        ],
    }
    EVIDENCE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


main()
