"""Build the editable, single-body Sketcher/Pad bus candidate r00.

Run this file inside FreeCAD's Python environment. It refuses to overwrite
candidate-r00 and never sends a job to a printer.
"""
import json
import math
import os
import re
import shutil
import traceback

import FreeCAD as App
import Part
import Sketcher
import MeshPart


PARAMS = {
    "length": 40.0,
    "width": 20.0,
    "height": 22.0,
    "side_corner_radius": 3.0,
    "roof_front_x": 4.0,
    "edge_fillet_radius": 0.25,
    "window_centers_x": (11.5, 18.0, 24.5),
    "window_width": 5.4,
    "window_z_min": 14.2,
    "window_z_max": 18.2,
    "panel_corner_radius": 0.45,
    "window_depth": 0.45,
    "door_x_min": 29.0,
    "door_x_max": 34.0,
    "door_z_min": 8.0,
    "door_z_max": 14.0,
    "wheel_centers_x": (8.0, 32.0),
    "wheel_center_z": 4.0,
    "wheel_outer_diameter": 6.0,
    "wheel_inner_diameter": 3.4,
    "wheel_depth": 0.45,
    "front_window_bounds": (-6.0, 12.0, 6.0, 18.0),
    "rear_window_bounds": (-5.0, 11.0, 5.0, 17.0),
    "end_window_corner_radius": 0.5,
    "end_window_depth": 0.45,
}

PRINT_PROFILE = {
    "name": "NEKOMO simple bus r00 candidate",
    "inherits": "0.20mm Standard @BBL A1M",
    "type": "process",
    "from": "User",
    "instantiation": "true",
    "compatible_printers": ["Bambu Lab A1 mini 0.4 nozzle"],
    "layer_height": "0.2",
    "wall_loops": "3",
    "sparse_infill_density": "15%",
    "sparse_infill_pattern": "gyroid",
    "enable_support": "0",
    "enable_prime_tower": "0",
    "brim_type": "no_brim",
    "top_shell_layers": "5",
    "bottom_shell_layers": "4",
    "outer_wall_speed": "60",
    "inner_wall_speed": "120",
    "sparse_infill_speed": "150",
}


def point(x, z, y_sign=1.0):
    return App.Vector(float(x), float(z) * y_sign, 0.0)


def line(sketch, a, b, y_sign=1.0):
    sketch.addGeometry(Part.LineSegment(point(*a, y_sign), point(*b, y_sign)), False)


def arc(sketch, a, mid, b, y_sign=1.0):
    sketch.addGeometry(Part.Arc(point(*a, y_sign), point(*mid, y_sign), point(*b, y_sign)), False)


def rounded_rect(sketch, x0, z0, x1, z1, radius, y_sign=1.0):
    q = radius / math.sqrt(2.0)
    line(sketch, (x0 + radius, z0), (x1 - radius, z0), y_sign)
    arc(sketch, (x1 - radius, z0), (x1 - radius + q, z0 + radius - q),
        (x1, z0 + radius), y_sign)
    line(sketch, (x1, z0 + radius), (x1, z1 - radius), y_sign)
    arc(sketch, (x1, z1 - radius), (x1 - radius + q, z1 - radius + q),
        (x1 - radius, z1), y_sign)
    line(sketch, (x1 - radius, z1), (x0 + radius, z1), y_sign)
    arc(sketch, (x0 + radius, z1), (x0 + radius - q, z1 - radius + q),
        (x0, z1 - radius), y_sign)
    line(sketch, (x0, z1 - radius), (x0, z0 + radius), y_sign)
    arc(sketch, (x0, z0 + radius), (x0 + radius - q, z0 + radius - q),
        (x0 + radius, z0), y_sign)


def checked_shape(feature, label):
    shape = feature.Shape
    if shape.isNull() or not shape.isValid() or not shape.isClosed() or len(shape.Solids) != 1:
        raise RuntimeError("{} did not produce one valid, closed solid".format(label))
    return shape


def show_tip_only(body):
    tip = body.Tip
    for child in body.Group:
        child.Visibility = child == tip
    body.Visibility = True
    if tip is not None:
        tip.Visibility = True


def side_profile(body, p):
    s = body.newObject("Sketcher::SketchObject", "SideProfile")
    s.Label = "Rounded bus side profile (XZ)"
    s.Placement = App.Placement(
        App.Vector(0, p["width"] / 2.0, 0),
        App.Rotation(App.Vector(1, 0, 0), 90),
    )
    r, length, height = p["side_corner_radius"], p["length"], p["height"]
    roof_x = p["roof_front_x"]
    q = r / math.sqrt(2.0)
    roof_tangent = (roof_x - q, height - r + q)
    front_wall_top = roof_tangent[1] - roof_tangent[0]
    line(s, (r, 0), (length - r, 0))
    arc(s, (length - r, 0), (length - r + q, r - q), (length, r))
    line(s, (length, r), (length, height - r))
    arc(s, (length, height - r), (length - r + q, height - r + q),
        (length - r, height))
    line(s, (length - r, height), (roof_x, height))
    arc(s, (roof_x, height),
        (roof_x + r * math.cos(math.radians(112.5)), height - r + r * math.sin(math.radians(112.5))),
        roof_tangent)
    line(s, roof_tangent, (0, front_wall_top))
    line(s, (0, front_wall_top), (0, r))
    arc(s, (0, r), (r - q, r - q), (r, 0))
    s.addProperty("App::PropertyString", "ParameterSource", "Design")
    s.ParameterSource = "build_bus.py:PARAMS"
    return s, front_wall_top


def add_side_details(body, p, side):
    y = side * p["width"] / 2.0
    y_sign = -float(side)  # local sketch Y maps to global +Z with outward normal
    rotation = App.Rotation(App.Vector(1, 0, 0), -90 if side > 0 else 90)
    s = body.newObject("Sketcher::SketchObject", "SideDetails{}".format("R" if side > 0 else "L"))
    s.Label = "Windows, door, and fixed tire reliefs {}".format("right" if side > 0 else "left")
    s.Placement = App.Placement(App.Vector(0, y, 0), rotation)
    half = p["window_width"] / 2.0
    for center in p["window_centers_x"]:
        rounded_rect(s, center - half, p["window_z_min"], center + half,
                     p["window_z_max"], p["panel_corner_radius"], y_sign)
    rounded_rect(s, p["door_x_min"], p["door_z_min"], p["door_x_max"],
                 p["door_z_max"], p["panel_corner_radius"], y_sign)
    for center in p["wheel_centers_x"]:
        cy = y_sign * p["wheel_center_z"]
        normal = App.Vector(0, 0, 1)
        s.addGeometry(Part.Circle(App.Vector(center, cy, 0), normal,
                                  p["wheel_outer_diameter"] / 2.0), False)
        s.addGeometry(Part.Circle(App.Vector(center, cy, 0), normal,
                                  p["wheel_inner_diameter"] / 2.0), False)
    return s


def add_end_window(body, p, rear):
    s = body.newObject("Sketcher::SketchObject", "RearWindow" if rear else "FrontWindow")
    if rear:
        s.Label = "Shallow rear window"
        s.Placement = App.Placement(
            App.Vector(p["length"], 0, 0),
            App.Rotation(App.Vector(0, 1, 0), App.Vector(0, 0, 1),
                         App.Vector(1, 0, 0), "ZXY"),
        )
        bounds = p["rear_window_bounds"]
    else:
        s.Label = "Shallow front window"
        s.Placement = App.Placement(
            App.Vector(0, 0, 0),
            App.Rotation(App.Vector(0, -1, 0), App.Vector(0, 0, 1),
                         App.Vector(-1, 0, 0), "ZXY"),
        )
        bounds = p["front_window_bounds"]
    rounded_rect(s, bounds[0], bounds[1], bounds[2], bounds[3],
                 p["end_window_corner_radius"])
    return s


def pocket(body, sketch, name, label, depth):
    feature = body.newObject("PartDesign::Pocket", name)
    feature.Label = label
    feature.Profile = sketch
    feature.Length = depth
    App.ActiveDocument.recompute()
    checked_shape(feature, label)
    sketch.Visibility = False
    show_tip_only(body)
    return feature


def try_side_edge_fillet(body, pad, p):
    refs = []
    for index, edge in enumerate(pad.Shape.Edges, 1):
        box = edge.BoundBox
        if abs(box.YLength - p["width"]) < 1e-5 and box.ZMin > 1e-5:
            refs.append("Edge{}".format(index))
    if not refs:
        return pad, {"status": "not_attempted", "reason": "no eligible side edges"}
    feature = body.newObject("PartDesign::Fillet", "SideEdgeFillet")
    feature.Label = "Small radius on exposed side edges"
    feature.Base = (pad, refs)
    feature.Radius = p["edge_fillet_radius"]
    App.ActiveDocument.recompute()
    try:
        checked_shape(feature, "edge fillet")
        show_tip_only(body)
        return feature, {"status": "valid_feature", "radius_mm": p["edge_fillet_radius"], "requested_edge_count": len(refs), "note": "Kernel can skip tangent-continuous edges; requested count is not the applied edge count."}
    except Exception as error:
        App.ActiveDocument.removeObject(feature.Name)
        body.Tip = pad
        App.ActiveDocument.recompute()
        return pad, {"status": "omitted", "reason": str(error), "edge_count": len(refs)}


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def build():
    design_dir = os.path.dirname(os.path.abspath(__file__))
    revision = os.environ.get("NEKOMO_BUS_REVISION", "r00")
    if not re.fullmatch(r"r\d{2}", revision):
        raise ValueError("NEKOMO_BUS_REVISION must match rNN, for example r00 or r01")
    final_dir = os.path.join(design_dir, "candidate-{}".format(revision))
    staging_dir = os.path.join(design_dir, ".candidate-{}-staging".format(revision))
    failure_dir = os.path.join(design_dir, "candidate-{}-failed".format(revision))
    if any(os.path.exists(path) for path in (final_dir, staging_dir, failure_dir)):
        raise RuntimeError("revision {} already has output or failure evidence; refusing to overwrite".format(revision))
    os.makedirs(staging_dir)
    for folder in ("cad", "exports", "evidence"):
        os.makedirs(os.path.join(staging_dir, folder))
    doc = None
    try:
        doc = App.newDocument("NEKOMO_SimpleBus_{}".format(revision))
        body = doc.addObject("PartDesign::Body", "BusBody")
        body.Label = "Simple bus, one solid"
        profile, front_wall_top = side_profile(body, PARAMS)
        pad = body.newObject("PartDesign::Pad", "BodyPad")
        pad.Label = "Pad side profile to full width"
        pad.Profile = profile
        pad.Length = PARAMS["width"]
        doc.recompute()
        checked_shape(pad, "body Pad")
        profile.Visibility = False
        show_tip_only(body)
        tip, fillet_review = try_side_edge_fillet(body, pad, PARAMS)
        for side in (1, -1):
            side_sketch = add_side_details(body, PARAMS, side)
            tip = pocket(body, side_sketch, "SidePocket{}".format("R" if side > 0 else "L"),
                         "Shallow side details {}".format("right" if side > 0 else "left"),
                         PARAMS["window_depth"])
        front_sketch = add_end_window(body, PARAMS, False)
        tip = pocket(body, front_sketch, "FrontWindowPocket", "Shallow front window",
                     PARAMS["end_window_depth"])
        rear_sketch = add_end_window(body, PARAMS, True)
        tip = pocket(body, rear_sketch, "RearWindowPocket", "Shallow rear window",
                     PARAMS["end_window_depth"])
        doc.recompute()
        shape = checked_shape(body, "final body")
        box = shape.BoundBox
        shell_count = len(shape.Solids[0].Shells)
        report = {
            "candidate": revision,
            "design_parameters": PARAMS,
            "geometry": {
                "valid": shape.isValid(),
                "closed": shape.isClosed(),
                "closed_one_solid": len(shape.Solids) == 1,
                "bounds_mm": {"x": box.XLength, "y": box.YLength, "z": box.ZLength,
                              "xmin": box.XMin, "ymin": box.YMin, "zmin": box.ZMin},
                "volume_mm3": shape.Volume,
                "shell_count": shell_count,
                "enclosed_void_shell_count": max(0, shell_count - 1),
                "no_enclosed_cavity_by_shell_count": shell_count == 1,
                "through_windows": False,
                "front_wall_top_z_mm": front_wall_top,
            },
            "edge_fillet": fillet_review,
            "pocket_depths_mm": {
                "side_windows_door_and_tires": PARAMS["window_depth"],
                "front_and_rear_windows": PARAMS["end_window_depth"],
            },
            "print_profile": PRINT_PROFILE,
            "time_target_minutes": {"print": 45, "cooling_and_handling": 15, "total": 60,
                                    "status": "unverified; boat sample conditions are unknown"},
            "slicing_notes": {
                "time_estimate": "unverified until sliced",
                "filament_selection": "load red PLA Basic explicitly in Bambu Studio",
                "cad_solid_vs_infill": "one CAD solid; slicer infill remains a separate process setting",
            },
            "printer_dispatch": False,
        }
        cad_path = os.path.join(staging_dir, "cad", "school-bus-{}.FCStd".format(revision))
        step_path = os.path.join(staging_dir, "exports", "school-bus-{}.step".format(revision))
        stl_path = os.path.join(staging_dir, "exports", "school-bus-{}.stl".format(revision))
        doc.recompute()
        doc.saveAs(cad_path)
        Part.export([body], step_path)
        mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.08,
                                      AngularDeflection=0.35, Relative=False)
        mesh.write(stl_path)
        write_json(os.path.join(staging_dir, "exports", "print-profile.json"), PRINT_PROFILE)
        write_json(os.path.join(staging_dir, "evidence", "geometry-report.json"), report)
        os.rename(staging_dir, final_dir)
        print("Created {}".format(final_dir))
        return doc
    except Exception as error:
        if doc is not None:
            App.closeDocument(doc.Name)
        if os.path.isdir(staging_dir):
            evidence_dir = os.path.join(staging_dir, "evidence")
            os.makedirs(evidence_dir, exist_ok=True)
            write_json(os.path.join(evidence_dir, "failed.json"), {
                "candidate": revision,
                "error": str(error),
                "traceback": traceback.format_exc(),
            })
            if not os.path.exists(failure_dir):
                os.rename(staging_dir, failure_dir)
        raise


build()
