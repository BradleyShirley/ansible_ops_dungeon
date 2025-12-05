"""
Plugin logic for core_ops_v1 pack.

All handlers here are referenced from pack.json / rooms.json.
"""

def simulate_idempotency_run(params, room_state, player_state):
    """
    Simulation handler: pretend to run the playbook and report behavior.
    """
    output = (
        "PLAY [web] *******************************************************************\n"
        "TASK [Deploy web config] ******************************************************\n"
        "changed: [web1]\n\n"
        "PLAY RECAP ********************************************************************\n"
        "web1 : ok=1 changed=1 unreachable=0 failed=0\n\n"
        "Note: This task reports 'changed' on every run due to its configuration."
    )

    # mark that simulation has been run at least once
    updates = {
        "custom": {
            **room_state.get("custom", {}),
            "simulation_runs": room_state.get("custom", {}).get("simulation_runs", 0) + 1
        }
    }

    return {
        "message": output,
        "output": output,
        "update_room_state": updates,
        "update_player_state": {},
        "score_delta": 0
    }


def validate_idempotency_fix(player_input, room_state, player_state):
    """
    Validator: check the user's freeform answer for a reasonable fix.
    We keep it simple: look for references to changing/removing 'force: yes'.
    """
    text = (player_input or "").lower()

    # crude heuristic: must mention 'force' and some negation like 'no'/'false' or 'remove'
    mentions_force = "force" in text
    mentions_disable = any(word in text for word in ["no", "false", "remove", "omit", "delete"])

    ok = True
    is_success = False
    message = ""

    if mentions_force and mentions_disable:
        is_success = True
        message = "That sounds like a solid fix. Adjusting or removing 'force' restores idempotency."
        room_state.setdefault("custom", {})
        room_state["custom"]["idempotency_fix_good"] = True
    else:
        message = (
            "Not quite. Think about which option in the task might be causing the file "
            "to be overwritten on every run."
        )
        room_state.setdefault("custom", {})
        room_state["custom"]["idempotency_fix_good"] = False

    # include a tiny score nudge for trying
    score_delta = 5 if not is_success else 0

    return {
        "ok": ok,
        "is_success": is_success,
        "message": message,
        "update_room_state": {
            "custom": room_state.get("custom", {})
        },
        "update_player_state": {},
        "score_delta": score_delta
    }


def check_idempotency_success(room_state, player_state):
    """
    Success condition: confirm that the fix was evaluated as good.
    """
    custom = room_state.get("custom", {})
    return bool(custom.get("idempotency_fix_good", False))


def score_core_ops(room_state, player_state, base_score):
    """
    Scoring override for this pack.

    Simple rule: if the player solved it with zero hints, add a small bonus.
    """
    hints_used = room_state.get("hints_used", 0)
    bonus = 20 if hints_used == 0 else 0
    return max(0, base_score + bonus)

