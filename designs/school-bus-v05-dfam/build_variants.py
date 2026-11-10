"""Build bounded, CAD-only open-underside alternatives from v04 snapshots.

Run with FreeCAD's headless `freecadcmd` Python environment. This does not slice,
print, or assess toy safety. v04 stays immutable; the candidate is a frozen BRep.
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys

import FreeCAD as App
import Part
import MeshPart


ROOT = Path(__file__).resolve().parent
V04_CAD = ROOT.parent / "school-bus-v04-dr" / "cad" / "nekomo-school-bus-v04.FCStd"
CAD_DIR = ROOT / "cad"
EXPORT_DIR = ROOT / "exports"
EVIDENCE_DIR = ROOT / "evidence"
SOURCE_COPY = CAD_DIR / "source-nekomo-school-bus-v04.FCStd"
OUT_CAD = CAD_DIR / "nekomo-school-bus-v05-open-underside.FCStd"
REPORT = EVIDENCE_DIR / "geometry-variants.json"

DOC_NAME = "NekomoSchoolBusV04"
BUS_HEIGHT = 35.568
MESH_LINEAR = 0.06
MESH_ANGULAR = 0.12
DECK_BOTTOM = 3.744
DECK_TOP = 8.237
CORNER_RADIUS = 1.2
LIP_CHAMFER = 0.6

# Windows keep the center bench support strip and both side rails. Their X
# placement follows the original scaled seat rows, with a 2.4 mm crossbar.
OPENINGS = [
    {"name": "front_window", "x": [22.3, 31.0], "y": [5.414, 23.414]},
    {"name": "rear_window", "x": [33.4, 42.85], "y": [5.414, 23.414]},
]


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def rounded_wire(x0, y0, x1, y1, radius, z):
    v = lambda x, y: App.Vector(float(x), float(y), float(z))
    k = 2 ** -0.5
    edges = [
        Part.makeLine(v(x0 + radius, y0), v(x1 - radius, y0)),
        Part.Arc(v(x1 - radius, y0), v(x1 - radius + radius*k, y0 + radius - radius*k), v(x1, y0 + radius)).toShape(),
        Part.makeLine(v(x1, y0 + radius), v(x1, y1 - radius)),
        Part.Arc(v(x1, y1 - radius), v(x1 - radius + radius*k, y1 - radius + radius*k), v(x1 - radius, y1)).toShape(),
        Part.makeLine(v(x1 - radius, y1), v(x0 + radius, y1)),
        Part.Arc(v(x0 + radius, y1), v(x0 + radius - radius*k, y1 - radius + radius*k), v(x0, y1 - radius)).toShape(),
        Part.makeLine(v(x0, y1 - radius), v(x0, y0 + radius)),
        Part.Arc(v(x0, y0 + radius), v(x0 + radius - radius*k, y0 + radius - radius*k), v(x0 + radius, y0)).toShape(),
    ]
    return Part.Wire(edges)


def rounded_cutter(window):
    x0, x1 = window["x"]
    y0, y1 = window["y"]
    z_low = DECK_BOTTOM - 0.1
    z_lip = DECK_BOTTOM + LIP_CHAMFER
    z_high = DECK_TOP + 0.2
    low = rounded_wire(x0 - LIP_CHAMFER, y0 - LIP_CHAMFER,
                       x1 + LIP_CHAMFER, y1 + LIP_CHAMFER,
                       CORNER_RADIUS + LIP_CHAMFER, z_low)
    nominal = rounded_wire(x0, y0, x1, y1, CORNER_RADIUS, z_lip)
    bevel = Part.makeLoft([low, nominal], True, True)
    shaft = Part.Face(nominal).extrude(App.Vector(0, 0, z_high - z_lip))
    tool = bevel.fuse(shaft).removeSplitter()
    if not tool.isValid() or len(tool.Solids) != 1:
        raise RuntimeError("Rounded aperture tool is not one valid solid")
    return tool


def mesh_stats(shape):
    mesh = MeshPart.meshFromShape(
        Shape=shape, LinearDeflection=MESH_LINEAR,
        AngularDeflection=MESH_ANGULAR, Relative=False,
    )
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
    }


def export_mesh(shape, path):
    mesh, stats = mesh_stats(shape)
    path.parent.mkdir(parents=True, exist_ok=True)
    mesh.write(str(path))
    return stats


def add_feature(doc, name, label, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape.copy()
    obj.addProperty("App::PropertyString", "SourceCAD", "Provenance")
    obj.SourceCAD = str(SOURCE_COPY)
    # Headless FreeCAD has no ViewObject; geometry export is the deliverable.
    view = getattr(obj, "ViewObject", None)
    if view is not None:
        view.Visibility = True
    return obj


def main():
    for directory in (CAD_DIR, EXPORT_DIR, EVIDENCE_DIR):
        directory.mkdir(parents=True, exist_ok=True)
    if not V04_CAD.is_file():
        raise FileNotFoundError("Preserved v04 CAD is missing: %s" % V04_CAD)
    source_hash = sha256(V04_CAD)
    shutil.copy2(V04_CAD, SOURCE_COPY)

    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    source_doc = App.openDocument(str(V04_CAD))
    physical_obj = source_doc.getObject("PhysicalBus")
    red_obj = source_doc.getObject("RedModel")
    white_obj = source_doc.getObject("WhiteModel")
    if any(obj is None for obj in (physical_obj, red_obj, white_obj)):
        raise RuntimeError("v04 must contain PhysicalBus, RedModel and WhiteModel")
    physical = physical_obj.Shape.copy()
    source_red = red_obj.Shape.copy()
    cutters = [rounded_cutter(window) for window in OPENINGS]
    cutter_union = cutters[0].fuse(cutters[1]).removeSplitter()
    print("OPENING_TOOLS_READY", flush=True)

    candidate = physical.cut(cutter_union).removeSplitter()
    print("PHYSICAL_CUT_COMPLETE", flush=True)
    if not candidate.isValid() or not candidate.isClosed() or len(candidate.Solids) != 1:
        raise RuntimeError("Candidate must remain one valid closed solid; stats=%s" % shape_stats(candidate))

    red = source_red.common(candidate).removeSplitter()
    white = candidate.cut(red).removeSplitter()
    if not red.isValid() or not white.isValid():
        raise RuntimeError("Color partition contains invalid BRep geometry")
    print("COLOR_PARTITION_COMPLETE", flush=True)

    # Use actual BRep differences/intersections, not raw volume subtraction, to
    # check color coverage and partition disjointness.
    removed_material = physical.cut(candidate).removeSplitter()
    intended_removal = physical.common(cutter_union).removeSplitter()
    checks = {
        "red_outside_physical_mm3": float(red.cut(candidate).Volume),
        "red_white_intersection_mm3": float(red.common(white).Volume),
        "uncovered_physical_mm3": float(candidate.cut(red.fuse(white)).Volume),
        "removed_outside_aperture_tools_mm3": float(removed_material.cut(intended_removal).Volume),
        "aperture_tool_volume_not_removed_mm3": float(intended_removal.cut(removed_material).Volume),
        "candidate_outside_source_physical_mm3": float(candidate.cut(physical).Volume),
    }
    if any(value != 0.0 for value in checks.values()):
        raise RuntimeError("Boolean difference/intersection checks must evaluate to zero: %s" % checks)

    physical_mesh_stats = export_mesh(candidate, EXPORT_DIR / "bus-v05-open-underside-physical.stl")
    white_mesh_stats = export_mesh(white, EXPORT_DIR / "bus-v05-open-underside-white.stl")
    red_mesh_stats = export_mesh(red, EXPORT_DIR / "bus-v05-open-underside-red.stl")

    # Measure the retained side rails from a mesh of the final deck at x=25 mm,
    # z=5.0..5.4 mm. This avoids using the conservative BRep control-point box.
    deck_band = candidate.common(Part.makeBox(0.4, 80.0, 0.4,
                                               App.Vector(24.8, -20.0, 5.0)))
    deck_band_mesh = MeshPart.meshFromShape(
        Shape=deck_band, LinearDeflection=0.02,
        AngularDeflection=0.06, Relative=False,
    )
    deck_bb = deck_band_mesh.BoundBox
    deck_y_min, deck_y_max = float(deck_bb.YMin), float(deck_bb.YMax)
    rail_widths = [OPENINGS[0]["y"][0] - deck_y_min,
                   deck_y_max - OPENINGS[0]["y"][1]]

    out_doc = App.newDocument("NekomoSchoolBusV05OpenUnderside")
    out_doc.Label = "NEKOMO school bus v05 open underside geometry candidate"
    final_physical = add_feature(out_doc, "PhysicalBusOpenUnderside", "One-piece physical bus with open underside", candidate)
    final_red = add_feature(out_doc, "RedModel", "Red color regions clipped to open-underside physical bus", red)
    final_white = add_feature(out_doc, "WhiteModel", "White color remainder for open-underside physical bus", white)
    out_doc.recompute()
    out_doc.saveAs(str(OUT_CAD))

    for obj, name in ((final_physical, "physical"), (final_white, "white"), (final_red, "red")):
        Part.export([obj], str(EXPORT_DIR / ("bus-v05-open-underside-%s.step" % name)))

    difference = removed_material
    # Reconstruct each source bench from the source document's frozen feature,
    # then apply the same X/Z scale and Y widening used for v04. Intersections
    # verify exactly how much bench material the aperture removes and whether
    # the remaining bench stays one valid closed component.
    scale_y = float(source_doc.getObject("WidenedChassisInput").YScaleFactor)
    chassis_mesh, _ = mesh_stats(source_doc.getObject("MiniChassis").Shape)
    chassis_y_center = (chassis_mesh.BoundBox.YMin + chassis_mesh.BoundBox.YMax) / 2.0
    bench_matrix = App.Matrix()
    bench_matrix.A11 = 60.0 / 160.2561472076974
    bench_matrix.A22 = bench_matrix.A11 * scale_y
    bench_matrix.A24 = chassis_y_center * (1.0 - scale_y)
    bench_matrix.A33 = bench_matrix.A11
    bench_deltas = []
    for bench_name in ("Bench0", "Bench1", "Bench2"):
        source_bench = source_doc.getObject(bench_name).Shape.copy().transformGeometry(bench_matrix)
        outside_v04 = float(source_bench.cut(physical).Volume)
        remaining_bench = source_bench.common(candidate).removeSplitter()
        removed_bench = source_bench.cut(candidate).removeSplitter()
        if outside_v04 != 0.0:
            raise RuntimeError("Reconstructed %s does not match the v04 physical shape: %s mm3" % (bench_name, outside_v04))
        if not remaining_bench.isValid() or not remaining_bench.isClosed() or len(remaining_bench.Solids) != 1:
            raise RuntimeError("Remaining %s must stay one valid closed solid" % bench_name)
        bench_deltas.append({
            "source_feature": bench_name,
            "original_valid": bool(source_bench.isValid()),
            "original_solid_count": len(source_bench.Solids),
            "outside_v04_mm3": outside_v04,
            "removed_by_candidate_mm3": float(removed_bench.Volume),
            "remaining_valid": bool(remaining_bench.isValid()),
            "remaining_closed": bool(remaining_bench.isClosed()),
            "remaining_solid_count": len(remaining_bench.Solids),
        })

    report = {
        "revision": "v05-dfam-open-underside-candidate",
        "basis": "Headless FreeCAD/OCCT BRep and STL mesh geometry only. No slicing, printer, T13 finger-gauge, structural, or child-safety assessment was performed.",
        "source_cad_relative_path": "cad/source-nekomo-school-bus-v04.FCStd",
        "source_original_path": str(V04_CAD),
        "source_sha256": source_hash,
        "source_original_sha256_after_build": sha256(V04_CAD),
        "source_unchanged": source_hash == sha256(V04_CAD),
        "candidate_cad_relative_path": "cad/nekomo-school-bus-v05-open-underside.FCStd",
        "candidate_cad_sha256": sha256(OUT_CAD),
        "candidate_physical": shape_stats(candidate),
        "candidate_stl_mesh": physical_mesh_stats,
        "color_regions": {
            "red": {**shape_stats(red), "stl_mesh": red_mesh_stats},
            "white": {**shape_stats(white), "stl_mesh": white_mesh_stats},
        },
        "openings": [
            {
                "name": w["name"], "x_bounds_mm": w["x"], "y_bounds_mm": w["y"],
                "clear_size_mm": [w["x"][1] - w["x"][0], w["y"][1] - w["y"][0]],
                "plan_corner_radius_mm": CORNER_RADIUS,
                "underside_lip": {"type": "45-degree chamfer", "radial_and_vertical_size_mm": LIP_CHAMFER},
                "permanent_opening": True,
                "detachable_cover_or_hardware": False,
            }
            for w in OPENINGS
        ],
        "retained_structure": {
            "center_crossbar_x_mm": [31.0, 33.4],
            "center_crossbar_nominal_width_mm": 2.4,
            "crossbar_spans_full_deck_width": True,
            "deck_y_bounds_at_x25_z5_mm": [deck_y_min, deck_y_max],
            "side_rails_y_mm": [[deck_y_min, OPENINGS[0]["y"][0]],
                                [OPENINGS[0]["y"][1], deck_y_max]],
            "measured_min_side_rail_mm": min(rail_widths),
            "wheel_center_x_mm": [13.85, 46.05],
            "seat_base_rows_x_mm": [[15.35, 22.1], [29.2, 35.94], [43.06, 49.8]],
            "bench_base_geometry_delta": bench_deltas,
            "note": "Bench1 loses material only at the lower interface beneath the two windows. The remaining bench is one valid closed solid. The full-width retained floor crossbar and side rails keep it connected to the bus. Bench0 and Bench2 remain geometrically unchanged. This is a geometry check, not a structural or child-safety assessment.",
        },
        "boolean_partition_checks_mm3": checks,
        "intended_removed_material_mm3": float(removed_material.Volume),
        "print_orientation": {
            "candidate_stl_export": "upright source orientation",
            "inversion_exported_here": False,
            "physical_bounds_basis": "STL mesh vertices from MeshPart at 0.06 mm linear / 0.12 rad angular deflection; BRep optimal bounds are not used for outside dimensions.",
        },
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("V05_VARIANT_COMPLETE", flush=True)
    print(json.dumps({"candidate": report["candidate_physical"], "mesh": physical_mesh_stats,
                      "openings": report["openings"], "checks": checks,
                      "source_unchanged": report["source_unchanged"],
                      "candidate_cad": str(OUT_CAD), "report": str(REPORT)}, indent=2), flush=True)


if __name__ == "__main__":
    main()
