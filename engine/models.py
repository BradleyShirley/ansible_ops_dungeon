#!/usr/bin/env python3
"""
Core data models for the Ansible Ops Dungeon engine.

These classes are thin wrappers around JSON structures. They are designed
to be easy to construct from JSON dictionaries and to remain
JSON-serializable.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class Artifact:
    id: str
    type: str
    label: str
    content_type: str
    content: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Artifact":
        return Artifact(
            id=data["id"],
            type=data.get("type", ""),
            label=data.get("label", ""),
            content_type=data.get("content_type", "text/plain"),
            content=data.get("content", ""),
        )


@dataclass
class Action:
    name: str
    params: Dict[str, Any]

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Action":
        return Action(
            name=data["name"],
            params=data.get("params", {}),
        )


@dataclass
class Hint:
    level: int
    id: str
    text: str

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Hint":
        return Hint(
            level=int(data["level"]),
            id=data["id"],
            text=data.get("text", ""),
        )


@dataclass
class Exit:
    id: str
    target_room: str
    condition: str = "always"  # "on_success", "on_failure", "always", "custom"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Exit":
        return Exit(
            id=data["id"],
            target_room=data["target_room"],
            condition=data.get("condition", "always"),
        )


@dataclass
class FailureOnFailure:
    type: str  # "exit", "reset_room", "none"
    target_room: Optional[str] = None
    message: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FailureOnFailure":
        return FailureOnFailure(
            type=data.get("type", "none"),
            target_room=data.get("target_room"),
            message=data.get("message"),
        )


@dataclass
class FailureCondition:
    max_attempts: int = 0
    max_hints: int = 0
    on_failure: FailureOnFailure = field(default_factory=FailureOnFailure)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "FailureCondition":
        return FailureCondition(
            max_attempts=int(data.get("max_attempts", 0)),
            max_hints=int(data.get("max_hints", 0)),
            on_failure=FailureOnFailure.from_dict(data.get("on_failure", {})),
        )

@dataclass
class Room:
    id: str
    title: str
    description: str
    metadata: Dict[str, Any]
    artifacts: List[Artifact]
    actions: List[Action]
    hints: List[Hint]
    success_condition: Optional[Dict[str, Any]] = None
    failure_condition: Optional[FailureCondition] = None
    exits: List[Exit] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "Room":
        hints_data = data.get("hints", [])
        hints = [Hint.from_dict(h) for h in hints_data]
        hints_sorted = sorted(hints, key=lambda h: h.level)

        # Handle failure_condition being absent OR null OR a dict
        failure_condition = None
        fc_raw = data.get("failure_condition", None)
        if isinstance(fc_raw, dict):
            failure_condition = FailureCondition.from_dict(fc_raw)

        return Room(
            id=data["id"],
            title=data.get("title", ""),
            description=data.get("description", ""),
            metadata=data.get("metadata", {}),
            artifacts=[Artifact.from_dict(a) for a in data.get("artifacts", [])],
            actions=[Action.from_dict(a) for a in data.get("actions", [])],
            hints=hints_sorted,
            success_condition=data.get("success_condition"),
            failure_condition=failure_condition,
            exits=[Exit.from_dict(e) for e in data.get("exits", [])],
        )



@dataclass
class PackScoring:
    base_per_room: int = 0
    hint_penalty: int = 0
    attempt_penalty: int = 0
    failure_penalty: int = 0
    custom_rules_handler: Optional[str] = None

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PackScoring":
        return PackScoring(
            base_per_room=int(data.get("base_per_room", 0)),
            hint_penalty=int(data.get("hint_penalty", 0)),
            attempt_penalty=int(data.get("attempt_penalty", 0)),
            failure_penalty=int(data.get("failure_penalty", 0)),
            custom_rules_handler=data.get("custom_rules_handler"),
        )


@dataclass
class PackMetadata:
    difficulty: str = "unknown"
    tags: List[str] = field(default_factory=list)
    description: str = ""
    recommended_order: str = "graph"
    min_engine_version: str = "1.0.0"

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PackMetadata":
        return PackMetadata(
            difficulty=data.get("difficulty", "unknown"),
            tags=list(data.get("tags", [])),
            description=data.get("description", ""),
            recommended_order=data.get("recommended_order", "graph"),
            min_engine_version=data.get("min_engine_version", "1.0.0"),
        )


@dataclass
class Pack:
    pack_id: str
    pack_name: str
    version: str
    entry_room: str
    rooms: Dict[str, Room]
    scoring: PackScoring
    metadata: PackMetadata
    logic_module_name: Optional[str] = None
    logic_module: Any = None  # populated by loader

    @staticmethod
    def from_dict(
        pack_json: Dict[str, Any],
        rooms_json: Dict[str, Any],
        logic_module: Any = None,
    ) -> "Pack":
        rooms_list = rooms_json.get("rooms", [])
        rooms: Dict[str, Room] = {}
        for r in rooms_list:
            room = Room.from_dict(r)
            rooms[room.id] = room

        scoring = PackScoring.from_dict(pack_json.get("scoring", {}))
        metadata = PackMetadata.from_dict(pack_json.get("metadata", {}))

        return Pack(
            pack_id=pack_json["pack_id"],
            pack_name=pack_json.get("pack_name", pack_json["pack_id"]),
            version=pack_json.get("version", "1.0.0"),
            entry_room=pack_json["entry_room"],
            rooms=rooms,
            scoring=scoring,
            metadata=metadata,
            logic_module_name=pack_json.get("logic_module"),
            logic_module=logic_module,
        )


# --- State models ------------------------------------------------------------


@dataclass
class RoomState:
    attempts: int = 0
    hints_used: int = 0
    last_fix: str = ""
    solved: bool = False
    failed: bool = False
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempts": self.attempts,
            "hints_used": self.hints_used,
            "last_fix": self.last_fix,
            "solved": self.solved,
            "failed": self.failed,
            "custom": self.custom,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "RoomState":
        return RoomState(
            attempts=int(data.get("attempts", 0)),
            hints_used=int(data.get("hints_used", 0)),
            last_fix=data.get("last_fix", ""),
            solved=bool(data.get("solved", False)),
            failed=bool(data.get("failed", False)),
            custom=dict(data.get("custom", {})),
        )


@dataclass
class PackState:
    visited_rooms: List[str] = field(default_factory=list)
    solved_rooms: List[str] = field(default_factory=list)
    failed_rooms: List[str] = field(default_factory=list)
    room_state: Dict[str, RoomState] = field(default_factory=dict)
    score: int = 0
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "visited_rooms": self.visited_rooms,
            "solved_rooms": self.solved_rooms,
            "failed_rooms": self.failed_rooms,
            "room_state": {
                rid: rs.to_dict() for rid, rs in self.room_state.items()
            },
            "score": self.score,
            "custom": self.custom,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PackState":
        room_state = {
            rid: RoomState.from_dict(rs)
            for rid, rs in data.get("room_state", {}).items()
        }
        return PackState(
            visited_rooms=list(data.get("visited_rooms", [])),
            solved_rooms=list(data.get("solved_rooms", [])),
            failed_rooms=list(data.get("failed_rooms", [])),
            room_state=room_state,
            score=int(data.get("score", 0)),
            custom=dict(data.get("custom", {})),
        )


@dataclass
class PlayerState:
    name: str = "Player"
    global_score: int = 0
    custom: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "global_score": self.global_score,
            "custom": self.custom,
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "PlayerState":
        return PlayerState(
            name=data.get("name", "Player"),
            global_score=int(data.get("global_score", 0)),
            custom=dict(data.get("custom", {})),
        )


@dataclass
class GameState:
    current_pack_id: Optional[str] = None
    current_room_id: Optional[str] = None
    packs: Dict[str, PackState] = field(default_factory=dict)
    player: PlayerState = field(default_factory=PlayerState)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_pack_id": self.current_pack_id,
            "current_room_id": self.current_room_id,
            "packs": {
                pid: ps.to_dict() for pid, ps in self.packs.items()
            },
            "player": self.player.to_dict(),
        }

    @staticmethod
    def from_dict(data: Dict[str, Any]) -> "GameState":
        packs = {
            pid: PackState.from_dict(ps)
            for pid, ps in data.get("packs", {}).items()
        }
        return GameState(
            current_pack_id=data.get("current_pack_id"),
            current_room_id=data.get("current_room_id"),
            packs=packs,
            player=PlayerState.from_dict(data.get("player", {})),
        )

