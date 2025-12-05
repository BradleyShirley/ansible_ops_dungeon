


##############################################
## WORK IN PROGress ##
##############################################



# Ansible Ops Dungeon

A modular, terminal-based Ansible training game engine.

The engine itself contains **zero scenario content** — all gameplay is defined
in external, hot-loadable **packs**, allowing you to build entire dungeons filled
with Ansible troubleshooting rooms without ever modifying the engine.

---

## Features

- **Pack-based architecture**  
  All content is external. The engine loads everything dynamically.

- **Dynamic discovery**  
  The engine scans `packs/` at runtime and loads all valid packs.

- **No hardcoded gameplay**  
  All rooms, artifacts, hints, actions, scoring, and logic reside in the pack files.

- **Plugin architecture**  
  Packs can define Python handlers for:
  - validation (`validate_*`)
  - simulations (`simulate_*`)
  - scoring overrides (`score_*`)
  - success conditions (`check_*`)
  - custom actions (`handle_*`)

- **3-level structured hint system**

- **Scoring engine**
  - Base per-room points  
  - Hint penalty  
  - Attempt penalty  
  - Failure penalty  
  - Optional pack-defined scoring overrides

- **Full game state tracking**
  - Attempts + hints per room  
  - Solved and failed rooms  
  - Per-room custom plugin state  
  - Pack score + global score  
  - Player profile persistence  

---

## Project Structure

ansible_ops_dungeon/
│
├── engine/
│   ├── engine.py      # Main loop, UI, action dispatcher
│   ├── loader.py      # Pack validation, JSON parsing, plugin loading
│   ├── models.py      # Pack, Room, Artifact, Action, Hint, Exit models
│   └── state.py       # Load/save game_state.json
│
├── packs/
│   └── core_ops_v1/
│       ├── pack.json   # Pack metadata + scoring config
│       ├── rooms.json  # Room definitions, actions, artifacts, hints
│       └── logic.py    # Plugin functions (validators, simulators, scoring)
│
├── saves/
│   └── game_state.json # Persistent player progress (auto-created)
│
└── README.md

## Requirements

- Python **3.8+**
- No external Python packages
- Terminal environment (Linux, macOS, WSL, or Windows Terminal)

Check Python version:

```bash
python3 --version
Running the Game
From the project root:

bash
Copy code
python3 engine/engine.py
The engine will:

Discover packs under packs/

Load and validate pack.json, rooms.json, and logic.py

Restore or initialize the game state

Drop the player into the pack’s entry_room

Content Pack Anatomy
Every pack must live under:

pgsql
Copy code
packs/<pack_id>/
  pack.json
  rooms.json
  logic.py
pack.json (required)
Defines:

pack_id, pack_name, version

entry_room

list of room IDs

scoring rules

metadata (difficulty, tags, engine version)

reference to optional logic_module

Example fields:

js
Copy code
{
  "pack_id": "core_ops_v1",
  "pack_name": "Core Ops Dungeon",
  "entry_room": "room_start",
  "rooms": ["room_start", "room_fix", "room_done"],
  "logic_module": "logic"
}
rooms.json (required)
A list of full room definitions.

Each room contains:

id, title, description

metadata

artifacts (files/tasks/data the player can inspect)

actions (inspect_artifact, propose_fix, run_playbook, etc.)

exactly 3 hints (low → mid → full-answer)

success/failure conditions

exits to other rooms

Rooms define zero Python code — all logic is JSON and plugins.

logic.py (optional, required if referenced)
Implements plugin functions:

validate_* — for validating freeform player fixes

simulate_* — for producing simulated playbook output

check_* — for determining if a room is solved

score_* — optional scoring overrides

handle_* — custom actions

Example:

python
Copy code
def validate_idempotency_fix(player_input, room_state, player_state):
    if "force: no" in player_input or "remove force" in player_input:
        return { "ok": True, "is_success": True, "message": "Correct!", "score_delta": 10 }
    return { "ok": False, "message": "Not quite. Think about idempotency." }
Included Example Pack
core_ops_v1 demonstrates:

A flawed Ansible copy task

A simulated playbook run

A freeform text validator

A success condition handler

A scoring config

A multi-room dungeon flow

This pack should be used as reference when authoring new content.

Creating Your Own Packs
Create a directory:

bash
Copy code
mkdir packs/my_new_pack
Add:

pgsql
Copy code
pack.json
rooms.json
logic.py
Ensure:

pack_id matches the folder name

entry_room exists

all rooms exist in rooms.json

each room contains EXACTLY 3 hints

plugin functions referenced in JSON exist in logic.py

Launch the game:

bash
Copy code
python3 engine/engine.py
Your pack will load automatically if valid.

Game State File
The engine persists progress to:

bash
Copy code
saves/game_state.json
It contains:

current pack & room

per-room attempts, hints, and custom state

solved/failed room lists

pack score & global score

You can delete the file to start over.

Roadmap
More built-in training packs (facts, templates, networking, handlers)

Pack version compatibility checks

CI validator for pack authors

Colored terminal UI

Exportable score reports

Optional game replay logs

In-game pack browser / downloader

License
MIT (or any license you choose — update as needed)

Author
This engine was designed to support modular, extensible
Ansible-learning scenarios that evolve independently from the engine.

If you need help writing new packs, plugin logic, or adding new engine features,
just ask!
