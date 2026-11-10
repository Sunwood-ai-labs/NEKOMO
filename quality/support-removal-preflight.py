"""File-only guard for support-removal risk in Bambu Studio sliced 3MFs.

The guard checks slicer metadata and positive-extrusion G-code feature/tool
assignments. It cannot verify a physical spool, AMS mapping, or support removal.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import xml.etree.ElementTree as ET


SUPPORT_POLICY_CODE = "NEKOMO-TR-001"
INPUT_EVIDENCE_CODE = "NEKOMO-TR-002"
REQUIRED_3MF_ENTRIES = (
    "Metadata/project_settings.config",
    "Metadata/slice_info.config",
    "Metadata/plate_1.gcode",
)
SUPPORT_FEATURE = re.compile(r"^Support(?:\b|\s)", re.IGNORECASE)
WORD = re.compile(r"(?<![A-Za-z])([A-Za-z])\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+))")
TOOL = re.compile(r"^T\s*(\d+)\s*$", re.IGNORECASE)
MOTION = re.compile(r"^G0*([0-3])(?:\s|[A-Za-z]|$)", re.IGNORECASE)
M620_SELECT = re.compile(r"^M620\s+S(\d+)(A?)(?:\s|$)", re.IGNORECASE)
M621_COMMIT = re.compile(r"^M621\s+S(\d+)(A?)(?:\s|$)", re.IGNORECASE)
LAYER_START = re.compile(r"^;\s*layer num/total_layer_count:\s*\d+/\d+", re.IGNORECASE)


@dataclass(frozen=True)
class Filament:
    filament_id: str
    material_type: str
    material_ids: tuple[str, ...]
    used_for_object: bool | None
    used_for_support: bool | None
    marked_as_support: bool


@dataclass(frozen=True)
class GcodeAudit:
    support_moves: int
    interface_moves: int
    object_moves: int
    support_tools: Counter[int | None]
    interface_tools: Counter[int | None]
    object_tools: Counter[int | None]
    raw_interface_tools: Counter[int]
    t1000_interface_moves: int
    undecidable_e_moves: int
    undecidable_material_moves: int
    unknown_feature_moves: int
    toolchange_anomalies: tuple[str, ...]


@dataclass(frozen=True)
class Issue:
    code: str
    message: str


def parse_bool(value: Any) -> bool | None:
    if value is None:
        return None
    normalized = str(value).strip().lower()
    if normalized in {"1", "true", "yes"}:
        return True
    if normalized in {"0", "false", "no"}:
        return False
    return None


def array_item(value: Any, index: int) -> str | None:
    """Read a slicer array in JSON or its semicolon-delimited G-code form."""
    if isinstance(value, list):
        return str(value[index]) if index < len(value) else None
    if isinstance(value, str):
        values = value.split(";")
        return values[index].strip() if index < len(values) else None
    return None


def support_marker(
    material_ids: tuple[str, ...],
    material_type: str,
    settings: dict[str, Any],
    filament_id: str,
) -> bool:
    normalized_ids = {value.strip().upper() for value in material_ids if value.strip()}
    normalized_type = material_type.casefold().replace("-", " ").replace("_", " ")
    named_support = any(
        value.startswith(("GFS02", "GFSS02")) for value in normalized_ids
    ) or any(
        marker in normalized_type
        for marker in ("support", "breakaway", "support interface", "pla-s")
    )
    try:
        settings_index = int(filament_id) - 1
    except ValueError:
        settings_index = -1
    flag = array_item(settings.get("filament_is_support"), settings_index)
    return named_support or parse_bool(flag) is True


def load_3mf(path: Path) -> tuple[dict[str, Any], dict[str, Any], bytes, str]:
    if not path.is_file():
        raise ValueError(f"Input is not a file: {path}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        missing = [name for name in REQUIRED_3MF_ENTRIES if name not in archive.namelist()]
        if missing:
            raise ValueError("Missing sliced 3MF entries: " + ", ".join(missing))
        settings = json.loads(archive.read(REQUIRED_3MF_ENTRIES[0]).decode("utf-8-sig"))
        slice_root = ET.fromstring(archive.read(REQUIRED_3MF_ENTRIES[1]))
        gcode = archive.read(REQUIRED_3MF_ENTRIES[2])

    if not isinstance(settings, dict):
        raise ValueError("project_settings.config is not a JSON object")
    metadata = {
        element.attrib.get("key"): element.attrib.get("value")
        for element in slice_root.findall(".//metadata")
        if element.attrib.get("key")
    }
    filaments: dict[str, Filament] = {}
    for element in slice_root.findall(".//filament"):
        attrs = element.attrib
        filament_id = attrs.get("id", "")
        if not filament_id:
            continue
        settings_index = int(filament_id) - 1 if filament_id.isdigit() else -1
        material_ids = tuple(
            value
            for value in (
                attrs.get("tray_info_idx", ""),
                attrs.get("filament_id", ""),
                array_item(settings.get("filament_ids"), settings_index) or "",
            )
            if value.strip()
        )
        material_type = attrs.get("type", "")
        configured_type = array_item(settings.get("filament_type"), settings_index)
        if configured_type and configured_type.casefold() not in material_type.casefold():
            material_type = f"{material_type} {configured_type}".strip()
        if filament_id in filaments:
            raise ValueError(f"Duplicate slice_info filament id {filament_id}")
        filaments[filament_id] = Filament(
            filament_id=filament_id,
            material_type=material_type,
            material_ids=material_ids,
            used_for_object=parse_bool(attrs.get("used_for_object")),
            used_for_support=parse_bool(attrs.get("used_for_support")),
            marked_as_support=support_marker(
                material_ids, material_type, settings, filament_id
            ),
        )
    if not filaments:
        raise ValueError("slice_info.config has no filament records")
    return settings, {"metadata": metadata, "filaments": filaments}, gcode, digest


def audit_gcode(gcode_bytes: bytes) -> GcodeAudit:
    """Track material through completed Bambu M620/M621 tool changes."""
    text = gcode_bytes.decode("utf-8", "replace")
    if "; HEADER_BLOCK_END" in text:
        text = text.split("; HEADER_BLOCK_END", 1)[1]

    feature = "Unknown"
    active_tool: int | None = None
    active_raw_tool: int | None = None
    pending_tool: int | None = None
    pending_tool_seen: int | None = None
    pending_selection_valid = False
    relative_e: bool | None = None
    absolute_e = 0.0
    in_layer_gcode = False
    in_flush = False
    support_tools: Counter[int | None] = Counter()
    interface_tools: Counter[int | None] = Counter()
    object_tools: Counter[int | None] = Counter()
    raw_interface_tools: Counter[int] = Counter()
    support_moves = 0
    interface_moves = 0
    object_moves = 0
    t1000_interface_moves = 0
    undecidable_e = 0
    undecidable_material = 0
    unknown_feature = 0
    anomalies: list[str] = []

    def anomaly(message: str) -> None:
        if message not in anomalies:
            anomalies.append(message)

    for raw_line in text.splitlines():
        if LAYER_START.match(raw_line):
            in_layer_gcode = True
        if raw_line.startswith("; FEATURE:"):
            feature = raw_line.split(":", 1)[1].strip()
        flush_current = in_flush
        if "; FLUSH_START" in raw_line:
            in_flush = True
            flush_current = True
        if "; FLUSH_END" in raw_line:
            # The line carrying FLUSH_END still contains the final purge move.
            flush_current = True
            in_flush = False

        command = raw_line.split(";", 1)[0].strip()
        if not command:
            continue

        selection = M620_SELECT.fullmatch(command)
        if selection:
            selected_tool = int(selection.group(1))
            if pending_tool is not None:
                anomaly("M620 selection began before the previous M621 commit.")
            pending_tool = selected_tool
            pending_tool_seen = None
            pending_selection_valid = bool(selection.group(2)) or selected_tool == 255
            if not pending_selection_valid:
                anomaly(f"M620 S{selected_tool}A selection is missing its AMS A marker.")
            continue

        commit = M621_COMMIT.fullmatch(command)
        if commit:
            committed_tool = int(commit.group(1))
            matching_ams_mode = bool(commit.group(2)) or committed_tool == 255
            if (
                pending_tool == committed_tool
                and pending_tool_seen == committed_tool
                and pending_selection_valid
                and matching_ams_mode
            ):
                # Slot 255 is the A1M unload sequence, not a material/tool id.
                active_tool = None if committed_tool == 255 else committed_tool
            else:
                active_tool = None
                anomaly(
                    f"M621 S{committed_tool}A did not match a completed M620/T{committed_tool} selection."
                )
            pending_tool = None
            pending_tool_seen = None
            pending_selection_valid = False
            continue

        tool_match = TOOL.fullmatch(command)
        if tool_match:
            active_raw_tool = int(tool_match.group(1))
            if active_raw_tool == 1000:
                # Bambu's A1M start G-code uses T1000 for the nozzle-load line.
                # It has no material id; retain only a completed M620/M621 selection.
                continue
            logical_tool = active_raw_tool
            if pending_tool is None:
                active_tool = None
                anomaly(f"T{logical_tool} appeared without a pending M620 S<n>A selection.")
            elif logical_tool != pending_tool:
                active_tool = None
                pending_tool_seen = None
                anomaly(f"M620 selected S{pending_tool}A but G-code selected T{logical_tool}.")
            else:
                pending_tool_seen = logical_tool
            continue
        upper = command.upper()
        if upper == "M82":
            relative_e = False
            continue
        if upper == "M83":
            relative_e = True
            continue

        words = {letter.upper(): float(value) for letter, value in WORD.findall(command)}
        if re.match(r"^G0*92(?:\s|[A-Za-z]|$)", command, re.IGNORECASE):
            if "E" in words:
                absolute_e = words["E"]
            continue
        if not MOTION.match(command) or "E" not in words or not in_layer_gcode:
            continue
        if relative_e is None:
            undecidable_e += 1
            continue

        if relative_e:
            extrusion_delta = words["E"]
        else:
            extrusion_delta = words["E"] - absolute_e
            absolute_e = words["E"]
        if extrusion_delta <= 1e-6:
            continue

        feature_key = feature.casefold()
        if flush_current or feature_key in {"prime tower", "wipe tower", "custom", "skirt"} or feature_key.endswith(" tower"):
            continue
        if feature_key == "unknown":
            unknown_feature += 1
            undecidable_material += 1
            continue

        material_tool = active_tool if pending_tool is None else None
        if material_tool is None:
            undecidable_material += 1
        if SUPPORT_FEATURE.match(feature):
            support_moves += 1
            support_tools[material_tool] += 1
            if feature_key.startswith("support interface"):
                interface_moves += 1
                interface_tools[material_tool] += 1
                if active_raw_tool is not None:
                    raw_interface_tools[active_raw_tool] += 1
                if active_raw_tool == 1000 and material_tool is not None:
                    t1000_interface_moves += 1
        else:
            object_moves += 1
            object_tools[material_tool] += 1

    return GcodeAudit(
        support_moves=support_moves,
        interface_moves=interface_moves,
        object_moves=object_moves,
        support_tools=support_tools,
        interface_tools=interface_tools,
        object_tools=object_tools,
        raw_interface_tools=raw_interface_tools,
        t1000_interface_moves=t1000_interface_moves,
        undecidable_e_moves=undecidable_e,
        undecidable_material_moves=undecidable_material,
        unknown_feature_moves=unknown_feature,
        toolchange_anomalies=tuple(anomalies),
    )


def support_used_flag(metadata: dict[str, str]) -> bool | None:
    return parse_bool(metadata.get("support_used"))


def interface_selector(settings: dict[str, Any]) -> int | None:
    raw = settings.get("support_interface_filament")
    if isinstance(raw, list):
        raw = raw[0] if raw else None
    if raw is None:
        return None
    try:
        return int(str(raw).strip())
    except ValueError:
        return None


def tool_id_for_filament(filament_id: str) -> int | None:
    """Bambu sliced 3MF tool T0 corresponds to slice_info filament id 1."""
    try:
        index = int(filament_id) - 1
    except ValueError:
        return None
    return index if index >= 0 else None


def format_tools(tools: Counter[int | None]) -> dict[str, int]:
    return {"unresolved" if tool is None else str(tool): count for tool, count in sorted(
        tools.items(), key=lambda item: (item[0] is None, -1 if item[0] is None else item[0])
    )}


def preflight(path: Path) -> dict[str, Any]:
    settings, slice_info, gcode, digest = load_3mf(path)
    metadata: dict[str, str] = slice_info["metadata"]
    filaments: dict[str, Filament] = slice_info["filaments"]
    audit = audit_gcode(gcode)
    metadata_support_used = support_used_flag(metadata)
    issues: list[Issue] = []
    dedicated_tools = {
        tool_id_for_filament(filament.filament_id)
        for filament in filaments.values()
        if filament.marked_as_support
    }
    dedicated_tools.discard(None)

    if audit.support_moves > 0 and audit.undecidable_e_moves:
        issues.append(
            Issue(
                INPUT_EVIDENCE_CODE,
                "Support or object extrusion has E moves with unknown M82/M83 state.",
            )
        )
    if (audit.support_moves > 0 or dedicated_tools) and audit.undecidable_material_moves:
        issues.append(
            Issue(
                INPUT_EVIDENCE_CODE,
                f"Cannot attribute {audit.undecidable_material_moves} positive feature extrusion moves to a completed M620/M621 material selection or a known feature.",
            )
        )
    if (audit.support_moves > 0 or dedicated_tools) and audit.toolchange_anomalies:
        issues.append(
            Issue(
                INPUT_EVIDENCE_CODE,
                "G-code has an unresolved toolchange: " + " ".join(audit.toolchange_anomalies),
            )
        )

    dedicated_object_use = {
        tool: audit.object_tools.get(tool, 0)
        for tool in dedicated_tools
        if audit.object_tools.get(tool, 0) > 0
    }
    if dedicated_object_use:
        issues.append(
            Issue(
                SUPPORT_POLICY_CODE,
                "Dedicated support material has positive Object-feature extrusion on logical tool(s) "
                f"{format_tools(Counter(dedicated_object_use))}; Prime tower and FLUSH sections are excluded.",
            )
        )
    if metadata_support_used is True and audit.support_moves == 0:
        issues.append(
            Issue(
                INPUT_EVIDENCE_CODE,
                "slice_info marks support as used, but G-code has no detectable positive support extrusion.",
            )
        )
    if metadata_support_used is False and audit.support_moves > 0:
        issues.append(
            Issue(
                INPUT_EVIDENCE_CODE,
                "slice_info marks support as unused, but G-code contains positive support extrusion.",
            )
        )
    if metadata_support_used is None:
        issues.append(
            Issue(INPUT_EVIDENCE_CODE, "slice_info support_used metadata is missing or invalid.")
        )

    if audit.support_moves == 0 and metadata_support_used is False:
        # A genuine support-free slice is eligible without a support filament.
        pass
    elif audit.support_moves > 0:
        selector = interface_selector(settings)
        selected = filaments.get(str(selector)) if selector is not None and selector > 0 else None
        if audit.interface_moves == 0:
            issues.append(
                Issue(
                    SUPPORT_POLICY_CODE,
                    "Support is present, but the sliced G-code has no positive Support interface extrusion to verify.",
                )
            )
        if selector is None or selector <= 0:
            issues.append(
                Issue(
                    SUPPORT_POLICY_CODE,
                    "support_interface_filament is unset or auto (0). Loaded spools do not change the sliced interface assignment.",
                )
            )
        elif selected is None:
            issues.append(
                Issue(
                    SUPPORT_POLICY_CODE,
                    f"support_interface_filament={selector} has no matching slice_info filament record.",
                )
            )
        else:
            if not selected.marked_as_support:
                issues.append(
                    Issue(
                        SUPPORT_POLICY_CODE,
                        f"Selected interface filament {selector} is not identified as dedicated support material (expected GFS02 or a matching support marker).",
                    )
                )
            if selected.used_for_support is not True or selected.used_for_object is not False:
                issues.append(
                    Issue(
                        SUPPORT_POLICY_CODE,
                        f"Selected interface filament {selector} is not marked used_for_support=true and used_for_object=false in slice_info.",
                    )
                )
            expected_tool = tool_id_for_filament(selected.filament_id)
            if not audit.interface_tools:
                issues.append(
                    Issue(SUPPORT_POLICY_CODE, "No active tool could be tied to positive interface extrusion.")
                )
            elif any(tool != expected_tool for tool in audit.interface_tools):
                issues.append(
                    Issue(
                        SUPPORT_POLICY_CODE,
                        "Positive Support interface extrusion uses tools "
                        f"{format_tools(audit.interface_tools)}; selected filament {selector} expects logical tool T{expected_tool}.",
                    )
                )
            selected_tool_object_moves = audit.object_tools.get(expected_tool, 0)
            if expected_tool is not None and selected_tool_object_moves > 0 and not dedicated_object_use:
                issues.append(
                    Issue(
                        SUPPORT_POLICY_CODE,
                        f"Selected support interface material also has {selected_tool_object_moves} positive Object-feature extrusion moves on logical tool T{expected_tool}.",
                    )
                )
    else:
        issues.append(
            Issue(
                INPUT_EVIDENCE_CODE,
                "The slice has neither verified support extrusion nor an explicit support_used=false marker.",
            )
        )

    status = "PASS_FILE_ONLY" if not issues else "BLOCK"
    return {
        "status": status,
        "input": path.name,
        "sha256": digest,
        "slice_support_used": metadata_support_used,
        "positive_support_extrusion_moves": audit.support_moves,
        "positive_support_interface_extrusion_moves": audit.interface_moves,
        "positive_object_feature_extrusion_moves": audit.object_moves,
        "support_interface_tools_by_logical_material": format_tools(audit.interface_tools),
        "support_interface_raw_gcode_tools": format_tools(audit.raw_interface_tools),
        "t1000_interface_moves_resolved_from_completed_material_selection": audit.t1000_interface_moves,
        "object_feature_tools_by_logical_material": format_tools(audit.object_tools),
        "unresolved_material_feature_moves": audit.undecidable_material_moves,
        "unknown_feature_extrusion_moves": audit.unknown_feature_moves,
        "toolchange_anomalies": list(audit.toolchange_anomalies),
        "support_interface_filament_selector": settings.get("support_interface_filament"),
        "issues": [issue.__dict__ for issue in issues],
        "scope": [
            "Reads only the supplied sliced 3MF metadata and embedded G-code.",
            "Does not verify the physical spool, current AMS mapping, or physical support removal.",
            "PASS_FILE_ONLY is a file preflight result, not approval to repeat the whole model print.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check support-interface assignment in a sliced Bambu Studio 3MF."
    )
    parser.add_argument("sliced_3mf", type=Path, help="Sliced 3MF with embedded G-code")
    args = parser.parse_args(argv)
    try:
        report = preflight(args.sliced_3mf)
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, ET.ParseError, json.JSONDecodeError) as exc:
        report = {
            "status": "BLOCK",
            "input": args.sliced_3mf.name,
            "issues": [{"code": INPUT_EVIDENCE_CODE, "message": str(exc)}],
            "scope": ["No physical spool, AMS, or removal claim is made."],
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "PASS_FILE_ONLY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
