# Ansible Ops Dungeon 🐍🧭

A modular, terminal-based Ansible training game engine. The engine contains zero scenario content — gameplay is provided by external, hot-loadable packs so you can build dungeons of Ansible troubleshooting rooms without changing the engine.

---

## Quick links

- Repository: https://github.com/BradleyShirley/ansible_ops_dungeon
- Language: Python (engine)

---

## Features ✨

- Pack-based architecture: all content is external and dynamically loaded from `packs/`.
- Plugin hooks: packs may provide Python handlers (validate_*, simulate_*, check_*, score_*, handle_*).
- 3-level hint system (low → mid → full answer) and configurable scoring.
- Full game state persistence (saves/game_state.json): per-room attempts, hints used, solved/failed state, scores.
- No external Python dependencies — runs with Python 3.8+ in a terminal.

---

## Quickstart 🚀

Requirements:

- Python 3.8+
- Terminal (Linux, macOS, WSL, or Windows Terminal)

Run the engine from the project root:

```bash
python3 engine/engine.py
```

The engine will:
- Discover packs under `packs/`
- Load and validate `pack.json`, `rooms.json`, and optional `logic.py`
- Restore or initialize game state
- Place the player in the pack's `entry_room`

---

## Project layout

ansible_ops_dungeon/

- engine/
  - engine.py      # Main loop, UI, action dispatcher
  - loader.py      # Pack validation, JSON parsing, plugin loading
  - models.py      # Pack, Room, Artifact, Action, Hint, Exit models
  - state.py       # Load/save game_state.json

- packs/
  - core_ops_v1/
    - pack.json     # Pack metadata + scoring config
    - rooms.json    # Room definitions, actions, artifacts, hints
    - logic.py      # Optional pack plugin functions (validators, simulators, scoring)

- saves/
  - game_state.json # Persistent player progress (auto-created)

---

## Pack anatomy (authoring)

Each pack must live in `packs/<pack_id>/` and include at minimum:

- pack.json (required): metadata and configuration (pack_id, pack_name, entry_room, rooms, optional logic_module, scoring rules, tags)
- rooms.json (required): array of room objects (id, title, description, artifacts, actions, exits, success/failure conditions, exactly 3 hints)
- logic.py (optional): Python plugin functions referenced by the JSON (validate_*, simulate_*, check_*, score_*, handle_*)

Example pack.json:

```json
{
  "pack_id": "core_ops_v1",
  "pack_name": "Core Ops Dungeon",
  "entry_room": "room_start",
  "rooms": ["room_start", "room_fix", "room_done"],
  "logic_module": "logic"
}
```

Example plugin function (in logic.py):

```python
def validate_idempotency_fix(player_input, room_state, player_state):
    if "force: no" in player_input or "remove force" in player_input:
        return { "ok": True, "is_success": True, "message": "Correct!", "score_delta": 10 }
    return { "ok": False, "message": "Not quite. Think about idempotency." }
```

---

## Creating your own packs 🧩

1. Create a directory: `mkdir packs/my_new_pack`
2. Add `pack.json`, `rooms.json`, and (optionally) `logic.py`.
3. Validate:
   - `pack_id` matches the folder name
   - `entry_room` exists and is listed in `rooms`
   - every room has exactly three hints
   - any plugin functions referenced in JSON exist in `logic.py`

Your pack will be discovered automatically when you run the engine if it validates successfully.

---

## Game state

The engine persists progress to `saves/game_state.json` containing current pack & room, per-room attempts and hints used, solved/failed lists, and scores. Remove this file to reset progress.

---

## Roadmap 🛠️

- More built-in training packs (facts, templates, networking, handlers)
- Pack version compatibility checks
- CI validator for pack authors
- Colored terminal UI
- Exportable score reports and optional replay logs
- In-game pack browser / downloader

---

## License

MIT (update as desired)

---

## Author

Designed to support modular, extensible Ansible-learning scenarios. If you want help writing new packs or plugin logic, open an issue or ask here.

(Edited by GitHub Copilot — README cleaned and restructured)