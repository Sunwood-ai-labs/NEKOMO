"""Build the editable NEKOMO school bus model in FreeCAD headless mode."""

import FreeCAD as App
import Part
import Sketcher
import MeshPart
import json
import math
import os
import shutil
import struct
import tempfile
from pathlib import Path


DOC_NAME = "NekomoSchoolBusV01"
ROOT_DEFAULT = Path(r"C:\Prj\NEKOMO\designs\school-bus-v01")
DETAILS = {
    "wheel_rim_fillet": 1.2,
    "seat_fillet": 3.0,
    "side_band": {"x": 24.0, "length": 121.0, "z": 33.0, "height": 4.0,
                   "y_ranges": [[-0.4, 1.3], [62.7, 64.4]], "corner_radius": 1.5},
    "grille": {"x_range": [-2.0, 2.0], "y_range": [23.0, 41.0],
               "z_range": [25.0, 36.0], "corner_radius": 2.0},
    "grille_slots": {"y_range": [26.0, 38.0], "z_centers": [28.0, 32.0],
                     "height": 1.4, "corner_radius": 0.6},
    "headlights": {"x_range": [-2.0, 2.0], "centers_y": [14.0, 50.0],
                    "center_z": 29.0, "outer_radius": 8.0,
                    "lens_x_range": [-2.5, -1.5], "lens_radius": 6.0},
    "rear_lights": {"x_range": [149.0, 151.0], "y_ranges": [[10.0, 18.0], [46.0, 54.0]],
                     "z_range": [27.0, 35.0], "corner_radius": 2.0},
    "hub_radius": 8.0,
    "hub_thickness": 0.9,
    "roof_end_fillet": 2.0,
    "roof_eave_rise": 4.0,
    "mesh_linear_deflection": 0.08,
    "mesh_angular_deflection": 0.15,
}


def log(message):
    print("[NEKOMO school bus] " + str(message))


def stage(name, action):
    log("START: " + name)
    try:
        result = action()
    except Exception as exc:
        log("FAILED: " + name + ": " + str(exc))
        raise RuntimeError("Build stage failed: " + name + ": " + str(exc)) from exc
    log("DONE: " + name)
    return result


def root_directory():
    override = os.environ.get("NEKOMO_BUS_ROOT")
    if override:
        return Path(override).resolve()
    script_path = globals().get("__file__")
    if script_path:
        candidate = Path(script_path).resolve().parent
        if candidate.name == "school-bus-v01" and (candidate / "design-spec.json").is_file():
            return candidate
    return ROOT_DEFAULT


def wheel_side_y_ranges(spec):
    body_width = float(spec["dimensions_mm"]["body_width"])
    total_width = float(spec["dimensions_mm"]["overall_width"])
    side_projection = (total_width - body_width) / 2.0
    if side_projection <= 0.0:
        raise ValueError("overall_width must exceed body_width for the fixed wheels")
    return [[-side_projection, side_projection],
            [body_width - side_projection, body_width + side_projection]]


def vector(x, y, z):
    return App.Vector(float(x), float(y), float(z))


def v2(point):
    return App.Vector(float(point[0]), float(point[1]), 0.0)


def rounded_profile(points, radius):
    """Round the corners of a simple counter-clockwise outline, including the hood recess."""
    if radius <= 0.0:
        return [Part.LineSegment(v2(points[i]), v2(points[(i + 1) % len(points)]))
                for i in range(len(points))]
    if len(points) < 3:
        raise ValueError("A rounded profile needs at least three vertices")

    corners = []
    count = len(points)
    for index, point in enumerate(points):
        previous = points[(index - 1) % count]
        following = points[(index + 1) % count]
        incoming = (point[0] - previous[0], point[1] - previous[1])
        outgoing = (following[0] - point[0], following[1] - point[1])
        in_length = math.hypot(incoming[0], incoming[1])
        out_length = math.hypot(outgoing[0], outgoing[1])
        if in_length <= 1e-9 or out_length <= 1e-9:
            raise ValueError("Profile contains a zero-length edge")
        in_unit = (incoming[0] / in_length, incoming[1] / in_length)
        out_unit = (outgoing[0] / out_length, outgoing[1] / out_length)
        cross = in_unit[0] * out_unit[1] - in_unit[1] * out_unit[0]
        dot = in_unit[0] * out_unit[0] + in_unit[1] * out_unit[1]
        turn = math.atan2(cross, dot)
        if abs(turn) <= 1e-7:
            raise ValueError("Rounded profile has a collinear corner")
        tangent = radius * math.tan(abs(turn) / 2.0)
        if tangent >= min(in_length, out_length) * 0.49:
            raise ValueError("Corner radius does not fit its adjacent profile edges")
        start = (point[0] - in_unit[0] * tangent,
                 point[1] - in_unit[1] * tangent)
        end = (point[0] + out_unit[0] * tangent,
               point[1] + out_unit[1] * tangent)
        turn_sign = 1.0 if turn > 0 else -1.0
        inward_in = (-in_unit[1] * turn_sign, in_unit[0] * turn_sign)
        center = (start[0] + inward_in[0] * radius,
                  start[1] + inward_in[1] * radius)
        start_angle = math.atan2(start[1] - center[1], start[0] - center[0])
        middle_angle = start_angle + turn / 2.0
        middle = (center[0] + radius * math.cos(middle_angle),
                  center[1] + radius * math.sin(middle_angle))
        corners.append((start, end, middle))

    geometry = []
    for index in range(count):
        start, end, middle = corners[index]
        geometry.append(Part.Arc(v2(start), v2(middle), v2(end)))
        next_start = corners[(index + 1) % count][0]
        geometry.append(Part.LineSegment(v2(end), v2(next_start)))
    return geometry


def plane_rotation(plane):
    if plane == "XY":
        return App.Rotation(vector(1, 0, 0), vector(0, 1, 0), vector(0, 0, 1), "ZXY")
    if plane == "XZ":
        return App.Rotation(vector(1, 0, 0), vector(0, 0, 1), vector(0, -1, 0), "ZXY")
    if plane == "YZ":
        return App.Rotation(vector(0, 1, 0), vector(0, 0, 1), vector(1, 0, 0), "ZXY")
    raise ValueError("Unknown sketch plane: " + plane)


def create_sketch(doc, internal_name, label, plane, origin):
    sketch = doc.addObject("Sketcher::SketchObject", internal_name)
    sketch.Label = label
    sketch.Placement = App.Placement(vector(*origin), plane_rotation(plane))
    return sketch


def add_profile(sketch, points, radius=0.0):
    geometry = rounded_profile(points, float(radius))
    for item in geometry:
        sketch.addGeometry(item, False)


def add_arc_profile(sketch, line_segments, arc_points):
    for start, end in line_segments:
        sketch.addGeometry(Part.LineSegment(v2(start), v2(end)), False)
    sketch.addGeometry(Part.Arc(v2(arc_points[0]), v2(arc_points[1]), v2(arc_points[2])), False)


def extrusion(doc, internal_name, label, sketch, direction, length):
    feature = doc.addObject("Part::Extrusion", internal_name)
    feature.Label = label
    feature.Base = sketch
    feature.DirMode = "Custom"
    feature.Dir = vector(*direction)
    feature.LengthFwd = float(length)
    feature.LengthRev = 0.0
    feature.Solid = True
    if hasattr(feature, "TaperAngle"):
        feature.TaperAngle = 0.0
    doc.recompute()
    require_nonempty_shape(feature, label)
    return feature


def shape_is_null(shape):
    value = getattr(shape, "isNull", None)
    return bool(value()) if callable(value) else False


def shape_is_valid(shape):
    value = getattr(shape, "isValid", None)
    return bool(value()) if callable(value) else False


def shape_is_closed(shape):
    value = getattr(shape, "isClosed", None)
    return bool(value()) if callable(value) else False


def require_nonempty_shape(obj, description):
    shape = getattr(obj, "Shape", None)
    if shape is None or shape_is_null(shape):
        raise RuntimeError(description + " produced a null shape")
    if not shape_is_valid(shape):
        raise RuntimeError(description + " produced an invalid shape")
    if len(shape.Solids) == 0:
        raise RuntimeError(description + " produced no solid")
    return shape


def require_solid_shape(shape, description, expected_count=None):
    if shape_is_null(shape) or not shape_is_valid(shape):
        raise RuntimeError(description + " is null or invalid")
    solids = list(shape.Solids)
    if not solids:
        raise RuntimeError(description + " contains no solids")
    if expected_count is not None and len(solids) != expected_count:
        raise RuntimeError(description + " has " + str(len(solids)) +
                           " solids; expected " + str(expected_count))
    for index, solid in enumerate(solids):
        if not solid.isValid():
            raise RuntimeError(description + " solid " + str(index) + " is invalid")
        if not solid.isClosed():
            raise RuntimeError(description + " solid " + str(index) + " is open")
    return solids


def all_edge_names(shape):
    return ["Edge" + str(index) for index in range(1, len(shape.Edges) + 1)]


def add_fillet(doc, internal_name, label, base, edge_names, radius):
    if not edge_names:
        raise RuntimeError(label + " found no edges to fillet")
    feature = doc.addObject("Part::Fillet", internal_name)
    feature.Label = label
    feature.Base = base
    if not hasattr(feature, "Edges"):
        raise RuntimeError("Part::Fillet has no Edges property in this FreeCAD build")
    edge_radius = float(radius)
    feature.Edges = [(int(name[4:]), edge_radius, edge_radius) for name in edge_names]
    doc.recompute()
    require_solid_shape(feature.Shape, label, 1)
    return feature


def create_box(doc, internal_name, label, x, y, z, length, width, height):
    box = doc.addObject("Part::Box", internal_name)
    box.Label = label
    box.Length = float(length)
    box.Width = float(width)
    box.Height = float(height)
    box.Placement.Base = vector(x, y, z)
    doc.recompute()
    require_solid_shape(box.Shape, label, 1)
    return box


def rounded_box(doc, internal_name, label, x, y, z, length, width, height, radius):
    base = create_box(doc, internal_name + "Raw", label + " raw box",
                      x, y, z, length, width, height)
    return add_fillet(doc, internal_name, label, base, all_edge_names(base.Shape), radius)


def fuse(doc, internal_name, label, shapes):
    if not shapes:
        raise ValueError(label + " needs at least one input shape")
    feature = doc.addObject("Part::MultiFuse", internal_name)
    feature.Label = label
    feature.Shapes = list(shapes)
    if hasattr(feature, "Refine"):
        feature.Refine = True
    doc.recompute()
    require_nonempty_shape(feature, label)
    return feature


def cut(doc, internal_name, label, base, tool):
    feature = doc.addObject("Part::Cut", internal_name)
    feature.Label = label
    feature.Base = base
    feature.Tool = tool
    if hasattr(feature, "Refine"):
        feature.Refine = True
    doc.recompute()
    require_nonempty_shape(feature, label)
    return feature


def common(doc, internal_name, label, shapes):
    feature = doc.addObject("Part::MultiCommon", internal_name)
    feature.Label = label
    feature.Shapes = list(shapes)
    if hasattr(feature, "Refine"):
        feature.Refine = True
    doc.recompute()
    require_nonempty_shape(feature, label)
    return feature


def plane_edges_at(shape, axis, values, tolerance=1e-6):
    names = []
    for index, edge in enumerate(shape.Edges, start=1):
        bounds = edge.BoundBox
        minimum = getattr(bounds, axis + "Min")
        maximum = getattr(bounds, axis + "Max")
        if maximum - minimum <= tolerance and any(abs(minimum - value) <= tolerance for value in values):
            names.append("Edge" + str(index))
    return names


def create_axis_cylinder(doc, internal_name, label, radius, height, base_point, axis):
    cylinder = doc.addObject("Part::Cylinder", internal_name)
    cylinder.Label = label
    cylinder.Radius = float(radius)
    cylinder.Height = float(height)
    if axis == "Y":
        rotation = App.Rotation(vector(1, 0, 0), -90.0)
    elif axis == "X":
        rotation = App.Rotation(vector(0, 1, 0), 90.0)
    else:
        raise ValueError("Cylinder axis must be X or Y")
    cylinder.Placement = App.Placement(vector(*base_point), rotation)
    doc.recompute()
    require_solid_shape(cylinder.Shape, label, 1)
    return cylinder


def make_group(doc, name, label, objects=()):
    group = doc.addObject("App::DocumentObjectGroup", name)
    group.Label = label
    for obj in objects:
        group.addObject(obj)
    return group


def add_to_group(group, obj):
    group.addObject(obj)


def add_window_tool(doc, name, label, plane, origin, points, radius, direction, length):
    sketch = create_sketch(doc, name + "Sketch", label + " profile", plane, origin)
    add_profile(sketch, points, radius)
    doc.recompute()
    return extrusion(doc, name + "Extrusion", label + " cutter", sketch, direction, length), sketch


def add_hex_color(obj, hex_value):
    color = tuple(int(hex_value[index:index + 2], 16) / 255.0 for index in (1, 3, 5))
    view_object = getattr(obj, "ViewObject", None)
    if view_object is not None:
        view_object.ShapeColor = color
        view_object.LineColor = tuple(max(0.0, component * 0.58) for component in color)


def hex_color_value(hex_value):
    return tuple(int(hex_value[index:index + 2], 16) / 255.0 for index in (1, 3, 5))


def dimensions_rows(spec):
    dims = spec["dimensions_mm"]
    roof = spec["roof"]
    chassis = spec["chassis"]
    seats = spec["seats"]
    rows = [
        ("target age", spec["target_age"], "design target"),
        ("wheel mode", spec["wheel_mode"], "design target"),
        ("body length", dims["body_length"], "mm"),
        ("body width", dims["body_width"], "mm"),
        ("target overall width", dims["overall_width"], "mm"),
        ("target overall height", dims["overall_height"], "mm"),
        ("wall thickness", dims["wall"], "mm"),
        ("pillar width", dims["pillar"], "mm"),
        ("body side-profile corner radius", spec["body_profile_corner_radius"], "mm"),
        ("body side edge radius", spec["body_side_edge_radius"], "mm"),
        ("roof x", roof["x"], "mm"),
        ("roof y", roof["y"], "mm"),
        ("roof z", roof["z"], "mm"),
        ("roof length", roof["length"], "mm"),
        ("roof width", roof["width"], "mm"),
        ("roof height", roof["height"], "mm"),
        ("roof end fillet", DETAILS["roof_end_fillet"], "mm"),
        ("wheel radius", dims["wheel_radius"], "mm"),
        ("wheel center x", ", ".join(str(v) for v in dims["wheel_centers_x"]), "mm"),
        ("wheel center z", dims["wheel_center_z"], "mm"),
        ("chassis", "%s x %s x %s" % (chassis["length"], chassis["width"], chassis["height"]), "mm"),
        ("seat row centers x", ", ".join(str(v) for v in seats["row_centers_x"]), "mm"),
        ("seat centers y", ", ".join(str(v) for v in seats["centers_y"]), "mm"),
        ("mesh linear deflection", DETAILS["mesh_linear_deflection"], "mm"),
        ("mesh angular deflection", DETAILS["mesh_angular_deflection"], "rad"),
    ]
    return rows


def add_documentation(doc, spec):
    sheet = doc.addObject("Spreadsheet::Sheet", "Dimensions")
    sheet.Label = "Design dimensions and build inputs"
    sheet.set("A1", "Parameter")
    sheet.set("B1", "Value")
    sheet.set("C1", "Unit / note")
    for row_index, row in enumerate(dimensions_rows(spec), start=2):
        sheet.set("A" + str(row_index), str(row[0]))
        sheet.set("B" + str(row_index), str(row[1]))
        sheet.set("C" + str(row_index), str(row[2]))

    notes = doc.addObject("App::DocumentObjectGroup", "DesignNotes")
    notes.Label = "Design notes"
    notes.addProperty("App::PropertyString", "Purpose", "Design")
    notes.Purpose = "Single-piece fixed-wheel toy concept based on design-spec.json."
    notes.addProperty("App::PropertyString", "AgeTarget", "Design")
    notes.AgeTarget = "Under 3 years is a design target only; this prototype is not approved for child use."
    notes.addProperty("App::PropertyString", "Manufacturing", "Design")
    notes.Manufacturing = "Two-color integrated regions share one connected solid. Printer upload and printing are not authorized."
    notes.addProperty("App::PropertyString", "GeometryNote", "Design")
    notes.GeometryNote = "The cocoa roof uses a YZ circular-arc crown within the dimensions in the input JSON."
    notes.addObject(sheet)
    return sheet, notes


def set_final_visibility(doc, visible_objects):
    missing = []
    for obj in doc.Objects:
        view_object = getattr(obj, "ViewObject", None)
        if view_object is None:
            continue
        try:
            view_object.Visibility = obj in visible_objects
        except Exception as exc:
            missing.append(obj.Name + ": " + str(exc))
    if missing:
        raise RuntimeError("Could not set visibility for final tree objects: " + "; ".join(missing))
    if not any(getattr(obj, "ViewObject", None) is not None for obj in doc.Objects):
        log("NOTICE: headless build has no ViewObject; saved shape data and color features remain available")


def write_binary_stl(shape, destination, linear_deflection, angular_deflection):
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=float(linear_deflection),
        AngularDeflection=float(angular_deflection),
        Relative=False,
    )
    if getattr(mesh, "CountFacets", 0) <= 0:
        raise RuntimeError("MeshPart produced no triangles for " + str(destination.name))
    mesh.write(str(destination))
    raw = destination.read_bytes()
    if len(raw) < 84:
        raise RuntimeError("STL output is shorter than a binary STL header: " + str(destination.name))
    triangle_count = struct.unpack("<I", raw[80:84])[0]
    if len(raw) != 84 + triangle_count * 50:
        raise RuntimeError("Mesh.write did not create a binary STL: " + str(destination.name))
    return triangle_count


def geometry_summary(total_shape, gold_shape, cocoa_shape, spec):
    bbox = total_shape.optimalBoundingBox()
    intersection = gold_shape.common(cocoa_shape)
    intersection_volume = float(intersection.Volume)
    total_volume = float(total_shape.Volume)
    gold_volume = float(gold_shape.Volume)
    cocoa_volume = float(cocoa_shape.Volume)
    volume_error = abs((gold_volume + cocoa_volume) - total_volume)
    tolerance = 0.05
    gold_solids = require_solid_shape(gold_shape, "Gold color region")
    cocoa_solids = require_solid_shape(cocoa_shape, "Cocoa color region")
    total_solids = require_solid_shape(total_shape, "Total", 1)
    return {
        "basis": "CAD B-rep analysis only; no physical measurement or child-use approval is implied.",
        "units": "mm and mm^3",
        "total": {
            "bounding_box_mm": {
                "min_x": float(bbox.XMin), "max_x": float(bbox.XMax),
                "min_y": float(bbox.YMin), "max_y": float(bbox.YMax),
                "min_z": float(bbox.ZMin), "max_z": float(bbox.ZMax),
                "length_x": float(bbox.XLength), "width_y": float(bbox.YLength),
                "height_z": float(bbox.ZLength),
            },
            "min_z_mm": float(bbox.ZMin),
            "volume_mm3": total_volume,
            "solid_count": len(total_solids),
            "valid": bool(total_shape.isValid()),
            "all_solids_closed": all(solid.isClosed() for solid in total_solids),
        },
        "color_regions": {
            "gold": {"volume_mm3": gold_volume, "solid_count": len(gold_solids),
                     "valid": bool(gold_shape.isValid()),
                     "all_solids_closed": all(solid.isClosed() for solid in gold_solids)},
            "cocoa": {"volume_mm3": cocoa_volume, "solid_count": len(cocoa_solids),
                      "valid": bool(cocoa_shape.isValid()),
                      "all_solids_closed": all(solid.isClosed() for solid in cocoa_solids)},
            "intersection_volume_mm3": intersection_volume,
            "disjoint": intersection_volume < 0.01,
            "volume_error_mm3": volume_error,
            "volume_error_relative": volume_error / max(total_volume, 1.0),
            "volume_error_tolerance_mm3": tolerance,
            "volume_sum_matches_total": volume_error <= tolerance,
        },
        "critical_dimensions_mm": {
            "body_length": spec["dimensions_mm"]["body_length"],
            "body_width": spec["dimensions_mm"]["body_width"],
            "target_overall_width": spec["dimensions_mm"]["overall_width"],
            "target_overall_height": spec["dimensions_mm"]["overall_height"],
            "body_profile_corner_radius": spec["body_profile_corner_radius"],
            "body_side_edge_radius": spec["body_side_edge_radius"],
            "wheel_radius": spec["dimensions_mm"]["wheel_radius"],
            "wheel_center_x": spec["dimensions_mm"]["wheel_centers_x"],
            "wheel_center_z": spec["dimensions_mm"]["wheel_center_z"],
            "roof_bounds": {key: spec["roof"][key] for key in ("x", "y", "z", "length", "width", "height")},
        },
    }


def require_report_pass(summary):
    if summary["total"]["solid_count"] != 1:
        raise RuntimeError("Final Total must contain exactly one solid")
    if not summary["total"]["valid"] or not summary["total"]["all_solids_closed"]:
        raise RuntimeError("Final Total must be valid and closed")
    colors = summary["color_regions"]
    if not colors["disjoint"]:
        raise RuntimeError("Gold and cocoa regions overlap by volume")
    if not colors["volume_sum_matches_total"]:
        raise RuntimeError("Color-region volume mismatch exceeds the recorded CAD integration tolerance: " + json.dumps(summary))

