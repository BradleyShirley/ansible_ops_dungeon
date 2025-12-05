#!/usr/bin/env python3
"""
Terminal-based game engine entrypoint for Ansible Ops Dungeon.

This module contains:
- Core loop
- UI rendering
- Action dispatch
- Exit resolution

It is intentionally generic and contains no pack-specific content.
"""

import os
import sys
from typing import Dict, Any, Optional, List

# Ensure local modules can be imported when running as a script
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from models import (  # noqa: E402
    Pack,
    Room,
    GameState,
    Action,
)
import loader  # noqa: E402
import state as state_mod  # noqa: E402


def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def pause() -> None:
    input("\n[Enter] to continue...")


def choose_from_list(prompt: str, options: List[str]) -> Optional[int]:
    """
    Let the user choose an index in [0, len(options)-1].
    Returns index, or None to cancel.
    """
    if not options:
        return None

    while True:
        print(prompt)
        for i, label in enumerate(options, start=1):
            print(f"  {i}. {label}")
        print("  0. Cancel")

        choice = input("> ").strip()
        if not choice.isdigit():
            print("Please enter a number.")
            continue

        idx = int(choice)
        if idx == 0:
            return None
        if 1 <= idx <= len(options):
            return idx - 1
        print("Invalid selection.")


def render_room(pack: Pack, room: Room, game_state: GameState) -> None:
    """
    Render basic UI for the current room.
    """
    pack_state = game_state.packs.get(pack.pack_id)
    room_state = state_mod.get_room_state(pack_state, room.id)  # type: ignore[arg-type]

    clear_screen()
    print(f"=== Pack: {pack.pack_name} ({pack.pack_id}) v{pack.version} ===")
    print(f"Score (pack): {pack_state.score if pack_state else 0}")
    print(f"Score (player): {game_state.player.global_score}")
    print("=" * 70)
    print(f"[Room] {room.title}")
    print("-" * 70)
    print(room.description)
    print("-" * 70)
    print(f"Attempts: {room_state.attempts}  Hints used: {room_state.hints_used}")
    print("=" * 70)


def label_for_action(action) -> str:
    """
    Derive a human-readable label for an action from its params.
    Action is a models.Action object.
    """
    name = action.name
    params = action.params or {}
    for key in ("label", "prompt_label", "simulation_id", "artifact_id"):
        if key in params and params[key]:
            return f"{name}: {params[key]}"
    return name


def call_plugin(
    pack: Pack,
    handler_name: str,
    *args,
    **kwargs,
) -> Any:
    """
    Safely call a plugin handler, if available.
    """
    if not pack.logic_module:
        print(f"[WARN] Pack '{pack.pack_id}' has no logic module loaded.")
        return None
    func = getattr(pack.logic_module, handler_name, None)
    if not callable(func):
        print(f"[WARN] Handler '{handler_name}' not found in pack '{pack.pack_id}'.")
        return None
    try:
        return func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Plugin handler '{handler_name}' raised an exception: {exc}")
        return None


def handle_inspect_artifact(pack: Pack, room: Room, action_params: Dict[str, Any]) -> None:
    artifact_id = action_params.get("artifact_id")
    label_override = action_params.get("label")

    artifact = next((a for a in room.artifacts if a.id == artifact_id), None)
    if not artifact:
        print(f"[WARN] Artifact '{artifact_id}' not found in room '{room.id}'.")
        return

    label = label_override or artifact.label or artifact.id
    print(f"\n--- Artifact: {label} ({artifact.content_type}) ---")
    print(artifact.content)
    print("--- End of artifact ---")


def handle_run_playbook(pack: Pack, room: Room, pack_state, room_state, player_state, action_params: Dict[str, Any]) -> None:
    simulation_id = action_params.get("simulation_id", "simulation")
    handler_spec = action_params.get("handler")
    print(f"\n[Simulation] Running: {simulation_id}")

    if isinstance(handler_spec, dict) and handler_spec.get("type") == "plugin":
        handler_name = handler_spec.get("handler")
        if handler_name:
            result = call_plugin(
                pack,
                handler_name,
                action_params,
                room_state.__dict__,
                player_state.__dict__,
            )
            if isinstance(result, dict):
                output = result.get("output") or result.get("message")
                if output:
                    print(output)
                rs_updates = result.get("update_room_state") or {}
                ps_updates = result.get("update_player_state") or {}
                score_delta = int(result.get("score_delta", 0))

                from state import apply_state_update  # local import to avoid cycle

                apply_state_update(room_state.__dict__, rs_updates)
                apply_state_update(player_state.custom, ps_updates)
                if score_delta:
                    pack_state.score = max(0, pack_state.score + score_delta)
                    player_state.global_score = max(0, player_state.global_score + score_delta)
            else:
                print("[INFO] Simulation completed.")
        else:
            print("[WARN] No handler name provided for simulation.")
    else:
        print("[INFO] Simulation completed (no plugin handler).")


def handle_propose_fix(
    pack: Pack,
    room: Room,
    pack_state,
    room_state,
    player_state,
    action_params: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns the validator result dict (if any) to be used by success evaluation.
    """
    prompt_label = action_params.get("prompt_label", "Enter your proposed fix:")
    validator_spec = action_params.get("validator")

    print(f"\n{prompt_label}")
    player_input = input("> ")

    room_state.attempts += 1
    room_state.last_fix = player_input

    if isinstance(validator_spec, dict) and validator_spec.get("type") == "plugin":
        handler_name = validator_spec.get("handler")
        if handler_name:
            result = call_plugin(
                pack,
                handler_name,
                player_input,
                room_state.__dict__,
                player_state.__dict__,
            )
            if not isinstance(result, dict):
                print("[WARN] Validator did not return a dict.")
                return {}
            message = result.get("message")
            if message:
                print(message)

            from state import apply_state_update  # local import

            rs_updates = result.get("update_room_state") or {}
            ps_updates = result.get("update_player_state") or {}
            apply_state_update(room_state.__dict__, rs_updates)
            apply_state_update(player_state.custom, ps_updates)

            score_delta = int(result.get("score_delta", 0))
            if score_delta:
                pack_state.score = max(0, pack_state.score + score_delta)
                player_state.global_score = max(0, player_state.global_score + score_delta)

            return result

    # No validator or invalid spec: accept input but no extra logic
    print("[INFO] Proposed fix recorded.")
    return {}


def handle_request_hint(room: Room, room_state, failure_condition) -> None:
    max_hints = 3
    if failure_condition and failure_condition.max_hints:
        max_hints = failure_condition.max_hints

    if room_state.hints_used >= max_hints:
        print("[INFO] No more hints available in this room.")
        return

    room_state.hints_used += 1
    hint_level = room_state.hints_used

    hint = next((h for h in room.hints if h.level == hint_level), None)
    if hint:
        print(f"\n[Hint {hint.level}] {hint.text}")
    else:
        print("[WARN] Hint data missing for this level.")


def evaluate_failure(
    pack: Pack,
    room: Room,
    pack_state,
    room_state,
    player_state,
) -> Optional[str]:
    """
    Check failure conditions and apply penalties/transitions if triggered.

    Returns new_room_id if a transition occurs, or None otherwise.
    """
    if room_state.failed:
        return None

    fc = room.failure_condition
    if not fc:
        return None

    trigger = False
    if fc.max_attempts and room_state.attempts >= fc.max_attempts:
        trigger = True
    if fc.max_hints and room_state.hints_used >= fc.max_hints:
        trigger = True

    if not trigger:
        return None

    room_state.failed = True
    if room.id not in pack_state.failed_rooms:
        pack_state.failed_rooms.append(room.id)

    # Apply failure penalty
    failure_penalty = pack.scoring.failure_penalty
    if failure_penalty:
        pack_state.score = max(0, pack_state.score - failure_penalty)
        player_state.global_score = max(0, player_state.global_score - failure_penalty)
        print(f"\n[Failure] Penalty applied: -{failure_penalty} points.")

    on_failure = fc.on_failure
    if on_failure.type == "exit":
        if on_failure.message:
            print(on_failure.message)
        return on_failure.target_room
    elif on_failure.type == "reset_room":
        room_state.attempts = 0
        room_state.hints_used = 0
        room_state.failed = False
        print("[INFO] Room has been reset after failure.")
        return room.id
    elif on_failure.type == "none":
        print("[INFO] Failure condition reached; remaining in the same room.")
        return room.id

    return None


def evaluate_success(
    pack: Pack,
    room: Room,
    pack_state,
    room_state,
    player_state,
    last_validator_result: Dict[str, Any],
) -> Optional[str]:
    """
    Evaluate success condition and return new_room_id if a transition occurs.

    This function also handles scoring on success.
    """
    if room_state.solved:
        # Already solved; do not re-score or re-transition
        return None

    is_success = False

    # validator may directly signal success
    if last_validator_result.get("ok") and last_validator_result.get("is_success"):
        is_success = True

    # success_condition plugin can override/additional check
    sc = room.success_condition
    if isinstance(sc, dict) and sc.get("type") == "plugin":
        handler_name = sc.get("handler")
        if handler_name:
            result = call_plugin(
                pack,
                handler_name,
                room_state.__dict__,
                player_state.__dict__,
            )
            if isinstance(result, bool) and result:
                is_success = True

    if not is_success:
        return None

    # Mark room as solved
    room_state.solved = True
    if room.id not in pack_state.solved_rooms:
        pack_state.solved_rooms.append(room.id)

    # Base scoring
    base_score = pack.scoring.base_per_room
    base_score -= pack.scoring.attempt_penalty * room_state.attempts
    base_score -= pack.scoring.hint_penalty * room_state.hints_used
    base_score = max(0, base_score)

    # Allow custom scoring override
    custom_handler = pack.scoring.custom_rules_handler
    if custom_handler:
        result = call_plugin(
            pack,
            custom_handler,
            room_state.__dict__,
            player_state.__dict__,
            base_score,
        )
        if isinstance(result, int):
            base_score = max(0, result)

    if base_score:
        pack_state.score = max(0, pack_state.score + base_score)
        player_state.global_score = max(0, player_state.global_score + base_score)

    print(f"\n[Success] Room solved! Score gained: {base_score}")

    # Determine exits for success path
    candidate_exits = [
        ex for ex in room.exits if ex.condition in ("on_success", "always")
    ]

    if not candidate_exits:
        print("[INFO] No exits from this room. Pack may be complete.")
        return None

    if len(candidate_exits) == 1:
        ex = candidate_exits[0]
        print(f"[Transition] Moving to room: {ex.target_room}")
        return ex.target_room

    # Multiple exits: let player choose
    options = [f"{ex.id} -> {ex.target_room} ({ex.condition})" for ex in candidate_exits]
    idx = choose_from_list("Choose an exit:", options)
    if idx is None:
        return None
    ex = candidate_exits[idx]
    return ex.target_room


def handle_custom_action(
    pack: Pack,
    room: Room,
    pack_state,
    room_state,
    player_state,
    action_params: Dict[str, Any],
) -> None:
    handler_spec = action_params.get("handler")
    if not isinstance(handler_spec, dict) or handler_spec.get("type") != "plugin":
        print("[WARN] custom action missing plugin handler definition.")
        return
    handler_name = handler_spec.get("handler")
    if not handler_name:
        print("[WARN] custom action handler name missing.")
        return
    result = call_plugin(
        pack,
        handler_name,
        action_params,
        room_state.__dict__,
        player_state.__dict__,
    )
    if isinstance(result, dict):
        output = result.get("message")
        if output:
            print(output)
        from state import apply_state_update  # local import

        rs_updates = result.get("update_room_state") or {}
        ps_updates = result.get("update_player_state") or {}
        apply_state_update(room_state.__dict__, rs_updates)
        apply_state_update(player_state.custom, ps_updates)


def dispatch_action(
    pack: Pack,
    room: Room,
    game_state: GameState,
    action: Action,
) -> Dict[str, Any]:
    """
    Dispatch a room action.

    Returns the last validator result dict (may be empty) but does not
    itself cause room transitions.
    """
    pack_state = game_state.packs[pack.pack_id]
    room_state = state_mod.get_room_state(pack_state, room.id)
    player_state = game_state.player

    name = action.name
    params = action.params or {}

    last_validator_result: Dict[str, Any] = {}

    if name == "inspect_artifact":
        handle_inspect_artifact(pack, room, params)
    elif name == "run_playbook":
        handle_run_playbook(pack, room, pack_state, room_state, player_state, params)
    elif name == "propose_fix":
        last_validator_result = handle_propose_fix(
            pack, room, pack_state, room_state, player_state, params
        )
    elif name == "request_hint":
        handle_request_hint(room, room_state, room.failure_condition)
    elif name == "move_to_exit":
        # Manual exit selection independent of success/failure
        if not room.exits:
            print("[INFO] No exits available from this room.")
        else:
            options = [f"{ex.id} -> {ex.target_room} ({ex.condition})" for ex in room.exits]
            idx = choose_from_list("Choose an exit:", options)
            if idx is not None:
                target = room.exits[idx].target_room
                print(f"[Transition] Moving to room: {target}")
                game_state.current_room_id = target
    elif name == "custom":
        handle_custom_action(
            pack, room, pack_state, room_state, player_state, params
        )
    else:
        print(f"[WARN] Unknown action '{name}'.")

    return last_validator_result


def main() -> None:
    packs: Dict[str, Pack] = loader.discover_packs()
    if not packs:
        print("No valid packs found under 'packs/'.")
        print("The engine is running, but there is no content to play yet.")
        return

    game_state = state_mod.load_state(packs)

    while True:
        if game_state.current_pack_id not in packs:
            # Let user select a pack
            clear_screen()
            print("Select a pack to play:")
            pack_ids = list(packs.keys())
            options = [f"{packs[pid].pack_name} ({pid})" for pid in pack_ids]
            idx = choose_from_list("Available packs:", options)
            if idx is None:
                print("No pack selected. Exiting.")
                break
            chosen_id = pack_ids[idx]
            game_state.current_pack_id = chosen_id
            game_state.current_room_id = packs[chosen_id].entry_room

        pack = packs[game_state.current_pack_id]
        pack_state = game_state.packs[pack.pack_id]

        if game_state.current_room_id not in pack.rooms:
            # Fallback to entry room if current room disappeared
            game_state.current_room_id = pack.entry_room

        room = pack.rooms[game_state.current_room_id]
        if room.id not in pack_state.visited_rooms:
            pack_state.visited_rooms.append(room.id)

        render_room(pack, room, game_state)

        # Build actions list + a generic quit option
        actions = room.actions
        action_labels = [label_for_action(a) for a in actions]
        action_labels.append("Quit")

        idx = choose_from_list("Choose an action:", action_labels)
        if idx is None:
            # Cancel selection; re-render
            continue

        if idx == len(actions):
            # Quit
            print("Exiting game. Saving state...")
            state_mod.save_state(game_state)
            break

        chosen_action = actions[idx]
        last_validator_result = dispatch_action(pack, room, game_state, chosen_action)

        # After the action, evaluate failure and success
        pack_state = game_state.packs[pack.pack_id]
        room_state = state_mod.get_room_state(pack_state, room.id)
        player_state = game_state.player

        # Failure first
        new_room_id = evaluate_failure(
            pack,
            room,
            pack_state,
            room_state,
            player_state,
        )

        # If not failed, check success
        if new_room_id is None:
            new_room_id = evaluate_success(
                pack,
                room,
                pack_state,
                room_state,
                player_state,
                last_validator_result,
            )

        # Update current room if there is a transition
        if new_room_id:
            if new_room_id in pack.rooms:
                game_state.current_room_id = new_room_id
            else:
                print(f"[WARN] Target room '{new_room_id}' does not exist in pack '{pack.pack_id}'.")

        # Save after each loop iteration
        state_mod.save_state(game_state)
        pause()


if __name__ == "__main__":
    main()

