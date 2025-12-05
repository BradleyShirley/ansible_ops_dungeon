#!/usr/bin/env python3
"""
Pack discovery, JSON loading, validation, and plugin import.
"""

import importlib.util
import json
import os
import traceback
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

from models import Pack, Room


BASE_DIR = Path(__file__).resolve().parent
PACKS_DIR = BASE_DIR.parent / "packs"


class PackLoadError(Exception):
    pass


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _find_plugin_handlers_in_room(room_data: Dict[str, Any]) -> List[str]:
    handlers: List[str] = []

    # success_condition
    sc = room_data.get("success_condition")
    if isinstance(sc, dict) and sc.get("type") == "plugin":
        handler_name = sc.get("handler")
        if handler_name:
            handlers.append(handler_name)

    # actions: validators + handlers
    for action in room_data.get("actions", []):
        params = action.get("params", {})
        validator = params.get("validator")
        if isinstance(validator, dict) and validator.get("type") == "plugin":
            h = validator.get("handler")
            if h:
                handlers.append(h)
        handler = params.get("handler")
        if isinstance(handler, dict) and handler.get("type") == "plugin":
            h = handler.get("handler")
            if h:
                handlers.append(h)

    # exits: spec mentions "custom (plugin)" but does not define handler schema.
    # We do not infer handlers from exits here because there is no handler field
    # defined in the contract for exits.

    return handlers


def _collect_plugin_handlers(pack_json: Dict[str, Any], rooms_json: Dict[str, Any]) -> List[str]:
    required_handlers: List[str] = []

    # scoring custom handler
    scoring = pack_json.get("scoring", {})
    custom_score_handler = scoring.get("custom_rules_handler")
    if custom_score_handler:
        required_handlers.append(custom_score_handler)

    for room_data in rooms_json.get("rooms", []):
        required_handlers.extend(_find_plugin_handlers_in_room(room_data))

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for h in required_handlers:
        if h not in seen:
            seen.add(h)
            unique.append(h)
    return unique


def _import_logic_module(pack_id: str, logic_module_name: str) -> Any:
    """
    Import packs/<pack_id>/<logic_module_name>.py as a unique module.
    """
    logic_path = PACKS_DIR / pack_id / f"{logic_module_name}.py"
    if not logic_path.exists():
        raise PackLoadError(f"logic module '{logic_module_name}.py' missing for pack '{pack_id}'")

    module_name = f"packs_{pack_id}_{logic_module_name}"
    spec = importlib.util.spec_from_file_location(module_name, str(logic_path))
    if spec is None or spec.loader is None:
        raise PackLoadError(f"Unable to create spec for logic module '{logic_module_name}' in pack '{pack_id}'")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)  # type: ignore
    except Exception as exc:  # noqa: BLE001
        raise PackLoadError(f"Error importing logic module for pack '{pack_id}': {exc}") from exc
    return module


def _validate_pack_structure(
    pack_id: str,
    pack_json: Dict[str, Any],
    rooms_json: Dict[str, Any],
    logic_module: Optional[Any],
    required_handlers: List[str],
) -> None:
    """
    Enforce pack validation rules defined in the spec.
    Raises PackLoadError on validation failure.
    """
    if pack_json.get("pack_id") != pack_id:
        raise PackLoadError(f"pack_id mismatch for folder '{pack_id}'")

    entry_room = pack_json.get("entry_room")
    if not entry_room:
        raise PackLoadError(f"entry_room missing in pack '{pack_id}'")

    rooms_list = rooms_json.get("rooms")
    if not isinstance(rooms_list, list):
        raise PackLoadError(f"rooms.json must contain a 'rooms' list for pack '{pack_id}'")

    rooms_by_id = {}
    for room_dict in rooms_list:
        if "id" not in room_dict:
            raise PackLoadError(f"Room without 'id' in pack '{pack_id}'")
        room_id = room_dict["id"]
        if room_id in rooms_by_id:
            raise PackLoadError(f"Duplicate room id '{room_id}' in pack '{pack_id}'")
        rooms_by_id[room_id] = room_dict

    if entry_room not in rooms_by_id:
        raise PackLoadError(f"entry_room '{entry_room}' not found in rooms for pack '{pack_id}'")

    declared_rooms = pack_json.get("rooms", [])
    for rid in declared_rooms:
        if rid not in rooms_by_id:
            raise PackLoadError(f"pack.json 'rooms' references missing room '{rid}' in pack '{pack_id}'")

    # If any plugin handlers are referenced, logic_module must exist and define them
    if required_handlers:
        if logic_module is None:
            raise PackLoadError(f"logic.py required but missing for pack '{pack_id}'")
        for handler_name in required_handlers:
            if not hasattr(logic_module, handler_name):
                raise PackLoadError(
                    f"Handler '{handler_name}' referenced in pack '{pack_id}' but not found in logic module"
                )


def discover_packs() -> Dict[str, Pack]:
    """
    Discover, load, and validate packs under packs/.

    Returns a dict of pack_id -> Pack for all valid packs.
    Invalid packs are skipped but do not crash the engine.
    """
    packs: Dict[str, Pack] = {}

    if not PACKS_DIR.exists():
        # No packs directory yet: engine must still run
        return packs

    for item in sorted(PACKS_DIR.iterdir()):
        if not item.is_dir():
            continue
        pack_id = item.name
        try:
            pack_json_path = item / "pack.json"
            rooms_json_path = item / "rooms.json"

            if not pack_json_path.exists() or not rooms_json_path.exists():
                raise PackLoadError("pack.json or rooms.json missing")

            pack_json = _load_json(pack_json_path)
            rooms_json = _load_json(rooms_json_path)

            required_handlers = _collect_plugin_handlers(pack_json, rooms_json)

            logic_module = None
            logic_module_name = pack_json.get("logic_module")
            if logic_module_name:
                logic_module = _import_logic_module(pack_id, logic_module_name)

            _validate_pack_structure(
                pack_id=pack_id,
                pack_json=pack_json,
                rooms_json=rooms_json,
                logic_module=logic_module,
                required_handlers=required_handlers,
            )

            pack = Pack.from_dict(pack_json, rooms_json, logic_module=logic_module)
            packs[pack.pack_id] = pack

        except (PackLoadError, OSError, json.JSONDecodeError) as exc:
            # Invalid packs must not be listed or loaded; log to stderr-like output
            print(f"[WARN] Failed to load pack '{pack_id}': {exc}")
            traceback.print_exc()

    return packs

