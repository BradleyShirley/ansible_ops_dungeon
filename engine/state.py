#!/usr/bin/env python3
"""
Game state load/save and helper functions.
"""

import json
from pathlib import Path
from typing import Dict

from models import GameState, PackState, RoomState, Pack


BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR.parent / "game_state.json"


def load_state(packs: Dict[str, Pack]) -> GameState:
    """
    Load game state from disk. If none exists, create a default state.

    The state is reconciled with available packs so that missing packs
    do not break the engine.
    """
    if STATE_FILE.exists():
        try:
            with STATE_FILE.open("r", encoding="utf-8") as f:
                data = json.load(f)
            state = GameState.from_dict(data)
        except Exception:  # noqa: BLE001
            # Corrupt state; start fresh
            state = GameState()
    else:
        state = GameState()

    # Ensure pack states exist for available packs
    for pack_id in packs.keys():
        if pack_id not in state.packs:
            state.packs[pack_id] = PackState()

    # Drop states for packs that no longer exist
    for pack_id in list(state.packs.keys()):
        if pack_id not in packs:
            del state.packs[pack_id]

    # Ensure current pack/room are valid
    if state.current_pack_id not in packs:
        # Default to first available pack
        state.current_pack_id = next(iter(packs.keys()), None)
        state.current_room_id = None

    # If we have a current pack but no room id, set to entry_room
    if state.current_pack_id and state.current_room_id is None:
        pack = packs[state.current_pack_id]
        state.current_room_id = pack.entry_room

    return state


def save_state(state: GameState) -> None:
    """
    Persist state to disk as JSON.
    """
    data = state.to_dict()
    with STATE_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)


def get_room_state(pack_state: PackState, room_id: str) -> RoomState:
    """
    Get or create per-room state skeleton.
    """
    if room_id not in pack_state.room_state:
        pack_state.room_state[room_id] = RoomState()
    return pack_state.room_state[room_id]


def apply_state_update(target: Dict, updates: Dict) -> None:
    """
    Shallow-merge updates into target dictionary.
    """
    for key, value in updates.items():
        target[key] = value

