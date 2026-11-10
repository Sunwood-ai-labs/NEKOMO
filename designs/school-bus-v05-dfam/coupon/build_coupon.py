"""Build a one-solid, mono-color support-removal coupon from a source FCStd.

Run inside FreeCAD's Python environment, for example by executing this file
with the headless FreeCAD integration. A different source/variant can be
supplied as a JSON file with the same fields as coupon-spec.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass

import FreeCAD as App
import Mesh
import MeshPart
import Part


HERE = os.path.dirname(os.path.abspath(__file__))


@dataclass(frozen=True)
class CouponSpec:
    source_file: str
    source_object: str
    coupon_name: str
    x_bounds: tuple[float, float]
    middle_window_x: tuple[float, float]
    endcap_nominal_depth: float
    endcap_yz: tuple[float, float, float, float]
    base_cut_z: float | None
    mesh_linear_deflection: float
    mesh_angular_deflection: float
    envelope_margin: float

    @classmethod
    def load(cls, path: str) -> "CouponSpec":
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        source = raw["source_file"]
        if not os.path.isabs(source):
            source = os.path.normpath(os.path.join(os.path.dirname(path), source))
        spec = cls(
            source_file=source,
            source_object=raw["source_object"],
            coupon_name=raw["coupon_name"],
            x_bounds=tuple(raw["x_bounds"]),
            middle_window_x=tuple(raw["middle_window_x"]),
            endcap_nominal_depth=float(raw["endcap_nominal_depth"]),
            endcap_yz=tuple(raw["endcap_yz"]),
            base_cut_z=float(raw["base_cut_z"]) if raw.get("base_cut_z") is not None else None,
            mesh_linear_deflection=float(raw["mesh_linear_deflection"]),
            mesh_angular_deflection=float(raw["mesh_angular_deflection"]),
            envelope_margin=float(raw["envelope_margin"]),
        )
        if not (spec.x_bounds[0] < spec.middle_window_x[0] < spec.middle_window_x[1] < spec.x_bounds[1]):
            raise ValueError("X coupon bounds must enclose the real middle-window interval")
        return spec


def mesh_bounds(shape: Part.Shape, spec: CouponSpec) -> dict[str, float]:
    mesh = MeshPart.meshFromShape(
        Shape=shape,
        LinearDeflection=spec.mesh_linear_deflection,
        AngularDeflection=spec.mesh_angular_deflection,
        Relative=False,
    )
    bb = mesh.BoundBox
    return {
        "x_min": bb.XMin, "x_max": bb.XMax,
        "y_min": bb.YMin, "y_max": bb.YMax,
        "z_min": bb.ZMin, "z_max": bb.ZMax,
    }


def dimensions(bounds: dict[str, float]) -> list[float]:
    return [
        bounds["x_max"] - bounds["x_min"],
        bounds["y_max"] - bounds["y_min"],
        bounds["z_max"] - bounds["z_min"],
    ]


def build_coupon(source_shape: Part.Shape, envelope: dict[str, float], spec: CouponSpec) -> tuple[Part.Shape, list[dict[str, float]]]:
    """Clip in global X and close only the two newly exposed ends."""
    x0, x1 = spec.x_bounds
    margin = spec.envelope_margin
    clip = Part.makeBox(
        x1 - x0,
        envelope["y_max"] - envelope["y_min"] + 2 * margin,
        envelope["z_max"] - envelope["z_min"] + 2 * margin,
        App.Vector(x0, envelope["y_min"] - margin, envelope["z_min"] - margin),
    )
    clipped = source_shape.copy().common(clip).removeSplitter()
    if clipped.isNull() or not clipped.isValid():
        raise RuntimeError("X-slab clipping returned a null or invalid shape")

    y0, y1, z0, z1 = spec.endcap_yz
    if not (envelope["y_min"] <= y0 < y1 <= envelope["y_max"] and envelope["z_min"] <= z0 < z1 <= envelope["z_max"]):
        raise ValueError("Endcap profile falls outside the tessellated source envelope")
    left_end = min(x0 + spec.endcap_nominal_depth, spec.middle_window_x[0])
    right_start = max(x1 - spec.endcap_nominal_depth, spec.middle_window_x[1])
    cap_bounds = [
        {"x_min": x0, "x_max": left_end, "y_min": y0, "y_max": y1, "z_min": z0, "z_max": z1},
        {"x_min": right_start, "x_max": x1, "y_min": y0, "y_max": y1, "z_min": z0, "z_max": z1},
    ]
    caps = [
        Part.makeBox(c["x_max"] - c["x_min"], y1 - y0, z1 - z0, App.Vector(c["x_min"], y0, z0))
        for c in cap_bounds
    ]
    coupon = clipped.multiFuse(caps).removeSplitter()
    if spec.base_cut_z is not None:
        if not envelope["z_min"] < spec.base_cut_z < envelope["z_max"]:
            raise ValueError("Base cut must fall inside the tessellated source Z envelope")
        flat_clip = Part.makeBox(
            x1 - x0,
            envelope["y_max"] - envelope["y_min"] + 2 * margin,
            envelope["z_max"] - spec.base_cut_z + margin,
            App.Vector(x0, envelope["y_min"] - margin, spec.base_cut_z),
        )
        coupon = coupon.common(flat_clip).removeSplitter()
    if coupon.isNull() or not coupon.isValid() or not coupon.isClosed() or len(coupon.Solids) != 1:
        raise RuntimeError(
            "Coupon must be one valid closed solid; got valid=%s closed=%s solids=%d"
            % (coupon.isValid(), coupon.isClosed(), len(coupon.Solids))
        )
    return coupon, cap_bounds


def main(spec_path: str) -> None:
    spec = CouponSpec.load(spec_path)
    with open(spec.source_file, "rb") as f:
        source_hash = hashlib.sha256(f.read()).hexdigest()

    source_doc = App.openDocument(spec.source_file)
    source_obj = source_doc.getObject(spec.source_object)
    if source_obj is None or source_obj.Shape.isNull():
        raise RuntimeError("Source object %r is missing or has no computed shape" % spec.source_object)
    source_shape = source_obj.Shape.copy()
    source_report = {
        "valid": source_shape.isValid(),
        "closed": source_shape.isClosed(),
        "solid_count": len(source_shape.Solids),
    }
    if not source_report["valid"] or not source_report["closed"] or source_report["solid_count"] != 1:
        raise RuntimeError("Source PhysicalBus is not one valid closed solid: %r" % source_report)
    source_envelope = mesh_bounds(source_shape, spec)
    App.closeDocument(source_doc.Name)

    coupon_shape, cap_bounds = build_coupon(source_shape, source_envelope, spec)
    out_doc = App.newDocument("NekomoDfamCoupon")
    feature = out_doc.addObject("Part::Feature", "SupportRemovalCoupon")
    feature.Label = spec.coupon_name
    feature.Shape = coupon_shape.copy()
    out_doc.recompute()

    fcstd_path = os.path.join(HERE, spec.coupon_name + ".FCStd")
    stl_path = os.path.join(HERE, spec.coupon_name + ".stl")
    step_path = os.path.join(HERE, spec.coupon_name + ".step")
    out_doc.saveAs(fcstd_path)
    # Export from the stored, standalone Part::Feature; no App::Link is used.
    coupon_mesh = MeshPart.meshFromShape(
        Shape=feature.Shape,
        LinearDeflection=spec.mesh_linear_deflection,
        AngularDeflection=spec.mesh_angular_deflection,
        Relative=False,
    )
    coupon_mesh.write(stl_path)
    Part.export([feature], step_path)

    # Reopen the native file before writing the evidence report.
    out_name = out_doc.Name
    App.closeDocument(out_name)
    reopened = App.openDocument(fcstd_path)
    stored = reopened.getObject("SupportRemovalCoupon")
    if stored is None:
        raise RuntimeError("Reopened FCStd does not contain SupportRemovalCoupon")
    reopened_shape = stored.Shape
    reopened_bounds = mesh_bounds(reopened_shape, spec)
    step_shape = Part.read(step_path)
    if step_shape.isNull() or not step_shape.isValid() or not step_shape.isClosed() or len(step_shape.Solids) != 1:
        raise RuntimeError("STEP readback failed the one-valid-closed-solid check")
    step_bounds = mesh_bounds(step_shape, spec)
    stl_mesh = Mesh.Mesh(stl_path)
    stl_bb = stl_mesh.BoundBox
    stl_bounds = {
        "x_min": stl_bb.XMin, "x_max": stl_bb.XMax,
        "y_min": stl_bb.YMin, "y_max": stl_bb.YMax,
        "z_min": stl_bb.ZMin, "z_max": stl_bb.ZMax,
    }
    stl_facets = len(stl_mesh.Facets)
    if stl_facets <= 0:
        raise RuntimeError("STL readback contains no facets")
    for axis in ("x_min", "x_max", "y_min", "y_max", "z_min", "z_max"):
        if abs(stl_bounds[axis] - reopened_bounds[axis]) > 0.01:
            raise RuntimeError("STL bounds differ from reopened FCStd by more than 0.01 mm at %s" % axis)
    report = {
        "source_file": os.path.relpath(spec.source_file, HERE).replace("\\", "/"),
        "source_sha256": source_hash,
        "source_object": spec.source_object,
        "source_shape": source_report,
        "source_actual_mesh_bounds_mm": source_envelope,
        "source_actual_dimensions_mm": dimensions(source_envelope),
        "coupon_spec": {
            "x_bounds_mm": list(spec.x_bounds),
            "middle_window_x_mm": list(spec.middle_window_x),
            "endcap_nominal_depth_mm": spec.endcap_nominal_depth,
            "coupon_only_flat_base_cut_z_mm": spec.base_cut_z,
            "endcap_actual_bounds_mm": cap_bounds,
            "endcap_profile_yz_mm": list(spec.endcap_yz),
            "mesh_deflection_mm_rad": [spec.mesh_linear_deflection, spec.mesh_angular_deflection],
        },
        "reopened_fcstd_shape": {
            "valid": reopened_shape.isValid(),
            "closed": reopened_shape.isClosed(),
            "solid_count": len(reopened_shape.Solids),
            "volume_mm3": reopened_shape.Volume,
        },
        "coupon_actual_mesh_bounds_mm": reopened_bounds,
        "coupon_actual_dimensions_mm": dimensions(reopened_bounds),
        "step_readback": {
            "valid": step_shape.isValid(),
            "closed": step_shape.isClosed(),
            "solid_count": len(step_shape.Solids),
            "actual_mesh_bounds_mm": step_bounds,
        },
        "stl_readback": {
            "facets": stl_facets,
            "actual_mesh_bounds_mm": stl_bounds,
        },
        "files": {
            "fcstd": os.path.basename(fcstd_path),
            "stl": os.path.basename(stl_path),
            "step": os.path.basename(step_path),
        },
        "limitations": [
            "Endcaps are coupon-only constraints and can change support branch layout.",
            "The flat-base cut is coupon-only and removes the partial rear-wheel arc below Z=3.744 mm.",
            "This geometry review does not prove physical support removal; the coupon has not been printed.",
            "No full-model color bonding, child safety, or print-use claim is made.",
        ],
    }
    if not report["reopened_fcstd_shape"]["valid"] or not report["reopened_fcstd_shape"]["closed"] or report["reopened_fcstd_shape"]["solid_count"] != 1:
        raise RuntimeError("Reopened FCStd failed the one-valid-closed-solid check")
    with open(os.path.join(HERE, "coupon-geometry.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))


spec_argument = next((arg for arg in sys.argv[1:] if arg.lower().endswith(".json")), None)
main(spec_argument or os.path.join(HERE, "coupon-spec.json"))
