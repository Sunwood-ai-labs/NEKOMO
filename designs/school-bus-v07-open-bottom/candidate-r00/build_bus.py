"""Build the open-bottom, two-color school bus in FreeCAD's Python console."""
import json
import math
import os
import re
import traceback

import FreeCAD as App
import MeshPart
import Part


PARAMS = {
    "length_mm": 40.0,
    "body_width_mm": 18.0,
    "overall_width_mm": 20.0,
    "height_mm": 22.0,
    "body_bottom_z_mm": 1.5,
    "wall_mm": 1.6,
    "cavity_width_mm": 14.8,
    "cavity_roof_z_mm": 20.4,
    "outer_profile_xz_mm": (
        (2.0, 1.5), (38.0, 1.5), (40.0, 3.5), (40.0, 20.0),
        (38.0, 22.0), (2.0, 22.0), (0.0, 20.0), (0.0, 3.5),
    ),
    "cavity_profile_xz_mm": (
        (1.6, -1.0), (38.4, -1.0), (38.4, 19.3373),
        (37.3373, 20.4), (2.6627, 20.4), (1.6, 19.3373),
    ),
    "color_split_z_mm": 10.0,
    "window_centers_x_mm": (12.0, 19.5, 27.0),
    "window_width_mm": 5.4,
    "window_z_min_mm": 14.0,
    "window_z_max_mm": 18.4,
    "front_window_z_min_mm": 14.0,
    "front_window_z_max_mm": 18.4,
    "front_pillar_width_mm": 1.6,
    "front_window_edge_margin_mm": 2.2,
    "wheel_centers_x_mm": (8.0, 32.0),
    "wheel_center_z_mm": 4.0,
    "wheel_diameter_mm": 8.0,
    "wheel_root_embed_mm": 1.0,
    "wheel_cone_overlap_mm": 0.05,
    "wheel_outer_face_radius_mm": 3.0,
    "wheel_hub_groove_outer_radius_mm": 2.6,
    "wheel_hub_groove_inner_radius_mm": 2.0,
    "wheel_hub_groove_depth_mm": 0.3,
    "layer_height_mm": 0.2,
}

PRINT_PROFILE = {
    "name": "NEKOMO school bus v07 two color draft",
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
    "enable_prime_tower": "1",
    "brim_type": "no_brim",
    "top_shell_layers": "5",
    "bottom_shell_layers": "4",
    "outer_wall_speed": "60",
    "inner_wall_speed": "120",
    "sparse_infill_speed": "150",
}


def vector(x, y, z):
    return App.Vector(float(x), float(y), float(z))


def prism_from_xz(points, y_min, y_max):
    wire_points = [vector(x, y_min, z) for x, z in points]
    wire_points.append(wire_points[0])
    face = Part.Face(Part.makePolygon(wire_points))
    return face.extrude(vector(0, y_max - y_min, 0))


def checked_solid(shape, label):
    if shape.isNull() or not shape.isValid() or not shape.isClosed() or len(shape.Solids) != 1:
        raise RuntimeError("{} must be one valid closed solid".format(label))
    return shape


def add_feature(doc, name, label, shape, role):
    obj = doc.addObject("Part::Feature", name)
    obj.Label = label
    obj.Shape = shape
    obj.addProperty("App::PropertyString", "DesignRole", "Design")
    obj.DesignRole = role
    view = getattr(obj, "ViewObject", None)
    if view is not None:
        view.Visibility = False
    return obj


def cut_side_windows(shape, p):
    for center in p["window_centers_x_mm"]:
        cutter = Part.makeBox(
            p["window_width_mm"], p["body_width_mm"] + 4.0,
            p["window_z_max_mm"] - p["window_z_min_mm"],
            vector(center - p["window_width_mm"] / 2.0,
                   -p["body_width_mm"] / 2.0 - 2.0, p["window_z_min_mm"]),
        )
        shape = shape.cut(cutter)
    return shape


def cut_front_windows(shape, p):
    edge_margin = p["front_window_edge_margin_mm"]
    pane_width = (p["body_width_mm"] - 2.0 * edge_margin -
                  p["front_pillar_width_mm"]) / 2.0
    y_ranges = (
        (-p["body_width_mm"] / 2.0 + edge_margin,
         -p["front_pillar_width_mm"] / 2.0),
        (p["front_pillar_width_mm"] / 2.0,
         p["body_width_mm"] / 2.0 - edge_margin),
    )
    for y0, y1 in y_ranges:
        if y1 - y0 <= 0 or y1 - y0 > pane_width + 1e-6:
            raise ValueError("front window dimensions do not fit the body width")
        cutter = Part.makeBox(
            3.0, y1 - y0,
            p["front_window_z_max_mm"] - p["front_window_z_min_mm"],
            vector(-1, y0, p["front_window_z_min_mm"]),
        )
        shape = shape.cut(cutter)
    return shape


def add_fixed_wheels(shape, p):
    radius = p["wheel_diameter_mm"] / 2.0
    root_depth = p["wheel_root_embed_mm"]
    cone_overlap = p["wheel_cone_overlap_mm"]
    outer_radius = p["wheel_outer_face_radius_mm"]
    overlap_volume = 0.0
    for center_x in p["wheel_centers_x_mm"]:
        for side in (-1, 1):
            body_face_y = side * p["body_width_mm"] / 2.0
            if side > 0:
                root_y = body_face_y - root_depth
                root = Part.makeCylinder(radius, root_depth,
                                         vector(center_x, root_y, p["wheel_center_z_mm"]),
                                         vector(0, 1, 0))
                taper = Part.makeCone(radius + cone_overlap, outer_radius,
                                      1.0 + cone_overlap,
                                      vector(center_x, body_face_y - cone_overlap,
                                             p["wheel_center_z_mm"]), vector(0, 1, 0))
            else:
                root = Part.makeCylinder(radius, root_depth,
                                         vector(center_x, body_face_y,
                                                p["wheel_center_z_mm"]), vector(0, 1, 0))
                taper = Part.makeCone(outer_radius, radius + cone_overlap,
                                      1.0 + cone_overlap,
                                      vector(center_x, body_face_y - 1.0,
                                             p["wheel_center_z_mm"]), vector(0, 1, 0))
            wheel = root.fuse(taper).removeSplitter()
            overlap_volume += wheel.common(shape).Volume
            shape = shape.fuse(wheel)
    return shape.removeSplitter(), overlap_volume


def cut_hub_grooves(shape, p):
    outer = p["wheel_hub_groove_outer_radius_mm"]
    inner = p["wheel_hub_groove_inner_radius_mm"]
    depth = p["wheel_hub_groove_depth_mm"]
    for center_x in p["wheel_centers_x_mm"]:
        for side in (-1, 1):
            face_y = side * (p["body_width_mm"] / 2.0 +
                             1.0)
            y0 = face_y - depth if side > 0 else face_y - 0.1
            cutter_length = depth + 0.1
            outer_cyl = Part.makeCylinder(outer, cutter_length,
                                          vector(center_x, y0, p["wheel_center_z_mm"]),
                                          vector(0, 1, 0))
            inner_cyl = Part.makeCylinder(inner, cutter_length + 0.2,
                                          vector(center_x, y0 - 0.1, p["wheel_center_z_mm"]),
                                          vector(0, 1, 0))
            shape = shape.cut(outer_cyl.cut(inner_cyl))
    return shape.removeSplitter()


def print_orientation(shape, height):
    oriented = shape.copy()
    oriented.rotate(vector(0, 0, 0), vector(1, 0, 0), 180)
    oriented.translate(vector(0, 0, height))
    return oriented


def write_json(path, value):
    with open(path, "w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def write_mesh(shape, path):
    mesh = MeshPart.meshFromShape(Shape=shape, LinearDeflection=0.08,
                                  AngularDeflection=0.35, Relative=False)
    mesh.write(path)


def build():
    design_dir = os.path.dirname(os.path.abspath(__file__))
    revision = os.environ.get("NEKOMO_BUS_REVISION", "r00")
    if not re.fullmatch(r"r\d{2}", revision):
        raise ValueError("NEKOMO_BUS_REVISION must match rNN, such as r00 or r01")

    final_dir = os.path.join(design_dir, "candidate-{}".format(revision))
    staging_dir = os.path.join(design_dir, ".candidate-{}-staging".format(revision))
    failed_dir = os.path.join(design_dir, "candidate-{}-failed".format(revision))
    if any(os.path.exists(path) for path in (final_dir, staging_dir, failed_dir)):
        raise RuntimeError("revision output or prior failure exists; refusing to overwrite")

    os.makedirs(staging_dir)
    for name in ("cad", "exports", "evidence"):
        os.makedirs(os.path.join(staging_dir, name))

    doc = None
    try:
        p = PARAMS
        doc = App.newDocument("NEKOMO_SchoolBus_{}".format(revision))
        whole_width = p["body_width_mm"]
        outer = prism_from_xz(p["outer_profile_xz_mm"],
                              -whole_width / 2.0, whole_width / 2.0)
        history = [add_feature(doc, "OuterEnvelope", "Rounded bus hull envelope", outer,
                               "outer bus envelope")]

        cavity = prism_from_xz(p["cavity_profile_xz_mm"],
                               -p["cavity_width_mm"] / 2.0,
                               p["cavity_width_mm"] / 2.0)
        shell = outer.cut(cavity).removeSplitter()
        history.append(add_feature(doc, "OpenCavity", "Open underside and hollow cabin", shell,
                                   "open-bottom cavity cut"))

        side_windowed = cut_side_windows(shell, p).removeSplitter()
        history.append(add_feature(doc, "SideWindows", "Three through windows per side",
                                   side_windowed, "through side windows"))
        front_windowed = cut_front_windows(side_windowed, p).removeSplitter()
        history.append(add_feature(doc, "FrontWindows", "Split through windshield",
                                   front_windowed, "through front windows"))
        wheeled, wheel_overlap_volume = add_fixed_wheels(front_windowed, p)
        history.append(add_feature(doc, "FixedWheels", "Four integrated red tires", wheeled,
                                   "fixed tire cylinders"))
        whole = checked_solid(cut_hub_grooves(wheeled, p), "assembled bus")
        whole_obj = add_feature(doc, "BusWhole", "Complete bus, assembled coordinates", whole,
                                "single assembled solid")
        metadata = doc.addObject("App::FeaturePython", "DesignParameters")
        metadata.Label = "Bus design parameters"
        metadata.addProperty("App::PropertyString", "DesignRevision", "Design")
        metadata.DesignRevision = revision
        metadata.addProperty("App::PropertyString", "ParametersJSON", "Design")
        metadata.ParametersJSON = json.dumps(PARAMS, ensure_ascii=False)
        history.append(whole_obj)

        split = p["color_split_z_mm"]
        red_box = Part.makeBox(p["length_mm"] + 10, p["overall_width_mm"] + 10,
                               split + 5, vector(-5, -p["overall_width_mm"] / 2.0 - 5, -5))
        white_box = Part.makeBox(p["length_mm"] + 10, p["overall_width_mm"] + 10,
                                 p["height_mm"] - split + 5,
                                 vector(-5, -p["overall_width_mm"] / 2.0 - 5, split))
        red = checked_solid(whole.common(red_box).removeSplitter(), "red lower body")
        white = checked_solid(whole.common(white_box).removeSplitter(), "white upper body")
        red_obj = add_feature(doc, "BusRedLower", "Red lower body and tires", red,
                              "red lower color region")
        white_obj = add_feature(doc, "BusWhiteUpper", "White roof and upper body", white,
                                "white upper color region")
        red_view = getattr(red_obj, "ViewObject", None)
        white_view = getattr(white_obj, "ViewObject", None)
        whole_view = getattr(whole_obj, "ViewObject", None)
        if red_view is not None:
            red_view.ShapeColor = (0.78, 0.055, 0.035)
            red_view.Visibility = True
        if white_view is not None:
            white_view.ShapeColor = (0.92, 0.92, 0.88)
            white_view.Visibility = True
        if whole_view is not None:
            whole_view.Visibility = False
        doc.recompute()

        access_probe = Part.makeBox(4.0, 4.0, p["cavity_roof_z_mm"] + 1.0,
                                    vector(p["length_mm"] / 2.0 - 2.0, -2.0, -1.0))
        roof_probe = Part.makeBox(4.0, 4.0, 0.2,
                                  vector(p["length_mm"] / 2.0 - 2.0, -2.0,
                                         p["cavity_roof_z_mm"] + 0.1))
        floorless_volume = whole.common(access_probe).Volume
        roof_witness_volume = whole.common(roof_probe).Volume
        if floorless_volume > 1e-5 or roof_witness_volume <= 0:
            raise RuntimeError("open-bottom access or intact-roof proof failed")

        window_probes_clear = []
        for center in p["window_centers_x_mm"]:
            for y in (-8.0, 8.0):
                probe = Part.makeBox(0.2, 0.2, 0.2, vector(center - 0.1, y - 0.1, 16.0))
                window_probes_clear.append(whole.common(probe).Volume <= 1e-5)
        if not all(window_probes_clear):
            raise RuntimeError("a side window probe is blocked")

        union = red.fuse(white).removeSplitter()
        checked_solid(union, "red and white color union")
        volume_error = abs(union.Volume - whole.Volume)
        if volume_error > max(1e-4, whole.Volume * 1e-8):
            raise RuntimeError("color regions do not reconstruct the complete bus")

        assembled_box = whole.BoundBox
        oriented_whole = print_orientation(whole, p["height_mm"])
        oriented_red = print_orientation(red, p["height_mm"])
        oriented_white = print_orientation(white, p["height_mm"])
        print_box = oriented_whole.BoundBox
        print_boundary_z = p["height_mm"] - split
        report = {
            "revision": revision,
            "design_parameters": PARAMS,
            "geometry": {
                "valid_closed_one_solid": True,
                "assembled_bounds_mm": {"length": assembled_box.XLength,
                                         "width": assembled_box.YLength,
                                         "height": assembled_box.ZLength,
                                         "xmin": assembled_box.XMin,
                                         "ymin": assembled_box.YMin,
                                         "zmin": assembled_box.ZMin},
                "print_oriented_bounds_mm": {"length": print_box.XLength,
                                              "width": print_box.YLength,
                                              "height": print_box.ZLength,
                                              "zmin": print_box.ZMin},
                "volume_mm3": whole.Volume,
                "open_bottom_center_access_probe_volume_mm3": floorless_volume,
                "roof_witness_volume_mm3": roof_witness_volume,
                "wheel_body_positive_overlap_volume_mm3": wheel_overlap_volume,
                "wheel_root_embed_mm": p["wheel_root_embed_mm"],
                "wheel_taper_radial_drop_mm": p["wheel_diameter_mm"] / 2.0 -
                                               p["wheel_outer_face_radius_mm"],
                "side_window_probe_clear": window_probes_clear,
                "color_regions_each_one_solid": True,
                "color_union_volume_error_mm3": volume_error,
                "enclosed_floor": False,
            },
            "color_change": {
                "assembled_boundary_z_mm": split,
                "print_boundary_z_mm": print_boundary_z,
                "layer_height_mm": p["layer_height_mm"],
                "boundary_layer_count": print_boundary_z / p["layer_height_mm"],
                "expected_color_change_count": 1,
                "white": "upper roof/body; through windows are in this region",
                "red": "lower body and fixed wheels with 45-degree tapered faces and hub grooves",
                "status": "geometry split verified; slicer and 3MF assembly unverified",
            },
            "print_time_target": {
                "minutes": 60,
                "status": "unverified until sliced with the target printer profile",
            },
            "profile_status": "Bambu process-profile draft; verify preset compatibility in the slicer",
            "printer_dispatch": False,
        }

        cad_dir = os.path.join(staging_dir, "cad")
        export_dir = os.path.join(staging_dir, "exports")
        evidence_dir = os.path.join(staging_dir, "evidence")
        doc.recompute()
        doc.saveAs(os.path.join(cad_dir, "school-bus-{}.FCStd".format(revision)))
        Part.export([red_obj, white_obj],
                    os.path.join(export_dir, "school-bus-{}-assembled.step".format(revision)))
        write_mesh(whole, os.path.join(export_dir, "school-bus-{}-assembled.stl".format(revision)))
        write_mesh(oriented_whole,
                   os.path.join(export_dir, "school-bus-{}-print-oriented.stl".format(revision)))
        write_mesh(oriented_white,
                   os.path.join(export_dir, "school-bus-{}-white-print-oriented.stl".format(revision)))
        write_mesh(oriented_red,
                   os.path.join(export_dir, "school-bus-{}-red-print-oriented.stl".format(revision)))
        write_json(os.path.join(export_dir, "profile.json"), PRINT_PROFILE)
        write_json(os.path.join(evidence_dir, "geometry.json"), report)
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
                "revision": revision,
                "error": str(error),
                "traceback": traceback.format_exc(),
            })
            if not os.path.exists(failed_dir):
                os.rename(staging_dir, failed_dir)
        raise


build()
