"""Build the one-piece, CAD-only v04 school bus from the preserved v03 baseline.

Run inside FreeCAD's Python environment or with the FreeCAD headless MCP runner.
This build models geometry only. It does not establish FDM bond strength, toy
safety, gauge compliance, or suitability for child use.
"""
from pathlib import Path
import json
import math
import shutil

import FreeCAD as App
import Part
import MeshPart


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "source" / "nekomo-school-bus-v03.FCStd"
CAD = ROOT / "cad" / "nekomo-school-bus-v04.FCStd"
EXPORTS = ROOT / "exports"
EVIDENCE = ROOT / "evidence" / "geometry-report.json"
DOC_NAME = "NekomoSchoolBusV04"
SOURCE_DOC = "nekomo_school_bus_v03"
SCALE = 60.0 / 160.2561472076974
TARGET_WIDTH_MM = 34.0


def mesh_export(shape, path):
    MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=0.06,
        AngularDeflection=0.12,
        Relative=False,
    ).write(str(path))


def box_feature(doc, name, label, x0, y0, z0, x1, y1, z1):
    obj = doc.addObject("Part::Box", name)
    obj.Label = label
    obj.Placement.Base = App.Vector(x0, y0, z0)
    obj.Length = x1 - x0
    obj.Width = y1 - y0
    obj.Height = z1 - z0
    return obj


def shape_stats(shape):
    bb = shape.optimalBoundingBox()
    return {
        "valid": bool(shape.isValid()),
        "closed": bool(shape.isClosed()),
        "solid_count": len(shape.Solids),
        "volume_mm3": float(shape.Volume),
        "optimal_brep_bounds_mm": [float(bb.XMin), float(bb.YMin), float(bb.ZMin),
                                   float(bb.XMax), float(bb.YMax), float(bb.ZMax)],
    }


def pair_geometry(a, b):
    common = a.common(b)
    return {
        "minimum_distance_mm": float(a.distToShape(b)[0]),
        "common_volume_mm3": float(common.Volume),
        "common_area_mm2": float(common.Area),
        "common_face_count": len(common.Faces),
        "common_edge_count": len(common.Edges),
    }


def widened_snapshot(doc, source, name, label, matrix, scale_y):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = source.Shape.copy().transformGeometry(matrix)
    obj.addProperty("App::PropertyString", "SourceFeature", "Provenance")
    obj.SourceFeature = source.Name
    obj.addProperty("App::PropertyFloat", "YScaleFactor", "Provenance")
    obj.YScaleFactor = scale_y
    return obj


def main():
    for folder in (CAD.parent, EXPORTS, EVIDENCE.parent):
        folder.mkdir(parents=True, exist_ok=True)
    if not SOURCE.exists():
        fallback = ROOT.parent / "school-bus-v03-mini" / "cad" / "nekomo-school-bus-v03.FCStd"
        if not fallback.exists():
            raise FileNotFoundError("The preserved v03 source CAD was not found")
        SOURCE.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fallback, SOURCE)
    if DOC_NAME in App.listDocuments():
        App.closeDocument(DOC_NAME)
    if SOURCE_DOC in App.listDocuments():
        App.closeDocument(SOURCE_DOC)

    doc = App.openDocument(str(SOURCE))
    doc.Label = "NEKOMO school bus v04 one-piece geometry"

    body = doc.getObject("MiniBody")
    chassis = doc.getObject("MiniChassis")
    roof = doc.getObject("MiniRoof")
    colour_names = ["MiniColour%d" % i for i in range(6)]
    source_colors = [doc.getObject(n) for n in colour_names]
    if any(o is None for o in [body, chassis, roof] + source_colors):
        raise RuntimeError("The v03 native link/color feature names do not match the reviewed source")

    # Freeze source geometry before building v04. Only these copies are widened;
    # the editable v03 link tree remains an unchanged baseline in the saved file.
    base_shape = Part.makeCompound([body.Shape, chassis.Shape, roof.Shape])
    base_bb = base_shape.optimalBoundingBox()
    scale_y = TARGET_WIDTH_MM / base_bb.YLength
    y_center = (base_bb.YMin + base_bb.YMax) / 2.0
    y_shift = y_center * (1.0 - scale_y)
    matrix = App.Matrix()
    matrix.A11 = 1.0
    matrix.A22 = scale_y
    matrix.A24 = y_shift
    matrix.A33 = 1.0
    body_input = widened_snapshot(doc, body, "WidenedBodyInput", "Y-widened body source", matrix, scale_y)
    chassis_input = widened_snapshot(doc, chassis, "WidenedChassisInput", "Y-widened chassis source", matrix, scale_y)
    roof_input = widened_snapshot(doc, roof, "WidenedRoofInput", "Y-widened roof source", matrix, scale_y)
    red_source_features = [
        widened_snapshot(doc, source_colors[i], "RedSource%d" % i,
                         "Y-widened source red region %d" % i, matrix, scale_y)
        for i in (1, 3, 5)
    ]
    doc.recompute()

    # These internal side rails bridge the 0.30 mm design locating clearance.
    # Their 2.06 mm vertical and 2.53 mm radial sections overlap both parts.
    # Placement stays above the floor-level windows or below their openings,
    # and away from the seat-row footprints.
    x_left = (30.0 - 0.55) * SCALE
    x_left_end = 36.2 * SCALE
    x_right_start = (150.0 - 36.2 + 30.0) * SCALE  # mirrored 36.2 mm inner edge
    x_right_end = (150.0 + 0.55) * SCALE
    def widened_y(value):
        return y_center + (value - y_center) * scale_y
    y0, y1 = widened_y(13.0 * SCALE), widened_y(64.0 * SCALE)
    chassis_z0, chassis_z1 = 22.4 * SCALE, 27.9 * SCALE
    # The roof rail starts above the front windshield's z=78 mm cutter top.
    roof_z0, roof_z1 = 78.4 * SCALE, 83.9 * SCALE
    collar_defs = [
        ("BodyChassisWeldCollarLeft", "Body to chassis weld collar, left", x_left, y0, chassis_z0, x_left_end, y1, chassis_z1),
        ("BodyChassisWeldCollarRight", "Body to chassis weld collar, right", x_right_start, y0, chassis_z0, x_right_end, y1, chassis_z1),
        ("BodyRoofWeldCollarLeft", "Body to roof weld collar, left", x_left, y0, roof_z0, x_left_end, y1, roof_z1),
        ("BodyRoofWeldCollarRight", "Body to roof weld collar, right", x_right_start, y0, roof_z0, x_right_end, y1, roof_z1),
    ]
    collars = [box_feature(doc, *definition) for definition in collar_defs]
    doc.recompute()

    # Preserve source links/baselines inside this same document and add native booleans.
    physical = doc.addObject("Part::MultiFuse", "PhysicalBus")
    physical.Label = "Physical bus, one-piece fused union"
    physical.Shapes = [body_input, chassis_input, roof_input] + collars
    if "Refine" in physical.PropertiesList:
        physical.Refine = True
    doc.recompute()
    whole = physical.Shape.removeSplitter()
    if not whole.isValid() or not whole.isClosed() or len(whole.Solids) != 1:
        raise RuntimeError("Physical fusion must be one valid closed solid; got valid=%s closed=%s solids=%d" % (whole.isValid(), whole.isClosed(), len(whole.Solids)))
    print("PHYSICAL_FUSION_COMPLETE", flush=True)
    whole_mesh = MeshPart.meshFromShape(Shape=whole, LinearDeflection=0.06, AngularDeflection=0.12, Relative=False)
    whole_mesh.write(str(EXPORTS / "bus-v04-solid.stl"))
    step_shape = doc.addObject("Part::Feature", "StepPhysicalExport")
    step_shape.Label = "Temporary wrapper for one-solid STEP export"
    step_shape.Shape = whole
    doc.recompute()
    Part.export([step_shape], str(EXPORTS / "bus-v04.step"))
    doc.removeObject(step_shape.Name)
    print("PHYSICAL_STL_STEP_EXPORTED", flush=True)

    # Source color 1/3/5 are red regions. The collars continue the roof/chassis
    # red material internally; white is computed as the exact remainder.
    red_input = doc.addObject("Part::MultiFuse", "RedInputUnion")
    red_input.Label = "Source red regions plus internal weld collars"
    red_input.Shapes = red_source_features + collars
    if "Refine" in red_input.PropertiesList:
        red_input.Refine = True
    doc.recompute()
    red = doc.addObject("Part::Common", "RedModel")
    red.Label = "Red color regions, clipped to physical bus"
    red.Base = red_input
    red.Tool = physical
    doc.recompute()
    if "Refine" in red.PropertiesList:
        red.Refine = True
    white = doc.addObject("Part::Cut", "WhiteModel")
    white.Label = "White color regions, exact physical remainder"
    white.Base = physical
    white.Tool = red
    doc.recompute()
    if "Refine" in white.PropertiesList:
        white.Refine = True
    # Headless FreeCAD has no ViewObject. Distinct native region objects and
    # color-specific STLs carry the material split for downstream review.
    for obj, color in ((red, "#C12E1F"), (white, "#FFFFFF")):
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None:
            view_object.ShapeColor = as_color(color)

    red_shape = red.Shape.removeSplitter()
    white_shape = white.Shape.removeSplitter()
    overlap = red_shape.common(white_shape)
    color_union = red_shape.fuse(white_shape).removeSplitter()
    missing = whole.cut(color_union).removeSplitter()
    extra = color_union.cut(whole).removeSplitter()
    volume_delta = abs(color_union.Volume - whole.Volume)
    if overlap.Volume > 0.001:
        raise RuntimeError("Red/white regions overlap by %.9f mm^3" % overlap.Volume)
    if missing.Volume > 0.05 or extra.Volume > 0.05:
        raise RuntimeError("Red+white set difference exceeds 0.05 mm^3: missing=%.9f extra=%.9f" % (missing.Volume, extra.Volume))

    # Explicitly verify the collar roots, rather than treating fuzzy edge contact
    # as meaningful material overlap.
    source_shapes = [body_input.Shape, chassis_input.Shape, roof_input.Shape]
    attachment_pairs = []
    for name, label, *bounds in collar_defs:
        c = doc.getObject(name).Shape
        host_a, host_b = (source_shapes[0], source_shapes[1]) if "BodyChassis" in name else (source_shapes[0], source_shapes[2])
        attachment_pairs.append({
            "feature": name,
            "label": label,
            "section_thickness_mm": [float((bounds[3] - bounds[0])), float(bounds[5] - bounds[2])],
            "collar_volume_mm3": float(c.Volume),
            "body_overlap_volume_mm3": float(c.common(host_a).Volume),
            ("chassis_overlap_volume_mm3" if "BodyChassis" in name else "roof_overlap_volume_mm3"): float(c.common(host_b).Volume),
        })
    if any(x["body_overlap_volume_mm3"] <= 0.0 or x.get("chassis_overlap_volume_mm3", x.get("roof_overlap_volume_mm3", 0.0)) <= 0.0 for x in attachment_pairs):
        raise RuntimeError("Every collar must have positive-volume overlap with both joined source parts")

    source_pair_contact = {
        "body_chassis": pair_geometry(body_input.Shape, chassis_input.Shape),
        "body_roof": pair_geometry(body_input.Shape, roof_input.Shape),
        "chassis_roof": pair_geometry(chassis_input.Shape, roof_input.Shape),
    }
    source_parts = {"body": body_input.Shape, "chassis": chassis_input.Shape, "roof": roof_input.Shape}
    bb = whole.optimalBoundingBox()
    report = {
        "revision": "v04-dr",
        "basis": "FreeCAD/OCCT geometry analysis only; not a physical toy safety or FDM bond-strength validation",
        "source_cad_relative_path": "source/nekomo-school-bus-v03.FCStd",
        "source_revision_untouched": True,
        "physical_assembly": {
            **shape_stats(whole),
            "brep_optimal_dimensions_mm": [float(bb.XLength), float(bb.YLength), float(bb.ZLength)],
            "brep_optimal_bounds_mm": [float(bb.XMin), float(bb.YMin), float(bb.ZMin), float(bb.XMax), float(bb.YMax), float(bb.ZMax)],
        },
        "source_components": {name: shape_stats(shape) for name, shape in source_parts.items()},
        "source_pair_contact": source_pair_contact,
        "structural_features": {
            "collar_features": attachment_pairs,
            "design_change": "The three v03 parts are fused into one physical CAD solid. Two internal 2.06 mm-high by 2.53 mm-wide collars bridge the body/chassis floor-guide clearance, and two 2.06 mm-high by 2.53 mm-wide collars bridge the body/roof guide. All collars overlap both joined parts volumetrically. The Y envelope is widened to 34.0 mm about the centerline; length and height remain at the v03 dimensions.",
            "surface_contact_vs_overlap": "Original v03 interfaces include zero-volume contact at some locations; v04 relies on the named collars' positive volumetric overlaps and verifies the final native union is one valid closed solid.",
            "external_appearance_change": "The external envelope is widened in Y from 31.824 mm to 34.0 mm per the hull-insphere candidate screen. X length and Z height remain at v03 dimensions. Collars remain inside the body.",
            "windows_seats_cleanup": "Collars stay outside the seat footprints. Chassis collars sit below the side-window openings; roof collars begin 0.150 mm above the front-window cutter top and above the side-window tops. No window-cutter volume is intentionally filled by the collars.",
        },
        "color_regions": {
            "white": shape_stats(white_shape),
            "red": shape_stats(red_shape),
            "white_volume_mm3": float(white_shape.Volume),
            "red_volume_mm3": float(red_shape.Volume),
            "white_plus_red_minus_whole_volume_mm3": float(white_shape.Volume + red_shape.Volume - whole.Volume),
            "raw_union_mass_integration_delta_mm3": float(volume_delta),
            "volume_sum_tolerance_mm3": 0.05,
            "volume_sum_tolerance_passed": bool(volume_delta <= 0.05),
            "missing_from_whole_volume_mm3": float(missing.Volume),
            "extra_beyond_whole_volume_mm3": float(extra.Volume),
            "symmetric_difference_volume_mm3": float(missing.Volume + extra.Volume),
            "set_difference_tolerance_mm3": 0.05,
            "overlap_volume_mm3": float(overlap.Volume),
            "overlap_tolerance_mm3": 0.001,
            "partition_assessment": "Set coverage is measured by missing/extra boolean differences and red/white common volume. The raw sum-of-volumes delta is retained separately because OCCT integration of transformed B-spline shapes can differ from set coverage.",
        },
        "scale_factor": SCALE,
        "y_width_scale_factor": scale_y,
        "y_center_translation_mm": y_shift,
        "fabrication_status": "No printer connection, slicing, FDM bond-strength test, stress analysis, or child-use approval was performed.",
    }

    # Write the physical one-solid formats plus exact color partitions.
    mesh_export(white_shape, EXPORTS / "bus-v04-white.stl")
    mesh_export(red_shape, EXPORTS / "bus-v04-red.stl")
    mesh_bb = whole_mesh.BoundBox
    mesh_dimensions = [float(mesh_bb.XLength), float(mesh_bb.YLength), float(mesh_bb.ZLength)]
    mesh_bounds = [float(mesh_bb.XMin), float(mesh_bb.YMin), float(mesh_bb.ZMin), float(mesh_bb.XMax), float(mesh_bb.YMax), float(mesh_bb.ZMax)]
    report["physical_assembly"]["bounds_mm"] = mesh_bounds
    report["physical_assembly"]["dimensions_mm"] = [round(v, 3) for v in mesh_dimensions]
    report["physical_assembly"]["bounds_basis"] = "STL vertex bounds (0.06 mm linear, 0.12 rad angular deflection); BRep optimal bounds are reported separately because affine-transformed B-spline control bounds can be conservative."
    report["physical_assembly"]["stl_mesh_vertex_bounds_mm"] = mesh_bounds
    report["physical_assembly"]["stl_mesh_dimensions_mm"] = mesh_dimensions
    if abs(mesh_dimensions[0] - 60.0) > 0.05 or abs(mesh_dimensions[1] - TARGET_WIDTH_MM) > 0.05 or abs(mesh_dimensions[2] - base_bb.ZLength) > 0.05:
        raise RuntimeError("STL bounds do not match the 60 x 34 mm Y-widened envelope: %r" % mesh_dimensions)
    # Headless FreeCAD has no ViewObject. Hide link objects through their native
    # Visibility property where available; GUI display colors are set on open.
    for obj in doc.Objects:
        if "Visibility" in obj.PropertiesList:
            obj.Visibility = False
    for obj in (white, red):
        if "Visibility" in obj.PropertiesList:
            obj.Visibility = True
        view_object = getattr(obj, "ViewObject", None)
        if view_object is not None:
            view_object.Visibility = True
    doc.recompute()
    doc.saveAs(str(CAD))
    report["saved_cad_relative_path"] = "cad/nekomo-school-bus-v04.FCStd"
    report["exports"] = ["exports/bus-v04-solid.stl", "exports/bus-v04-white.stl", "exports/bus-v04-red.stl", "exports/bus-v04.step"]
    EVIDENCE.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False), flush=True)


main()
