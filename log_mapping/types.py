from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict


class ACSState(TypedDict, total=False):
    # Explicit mappings (compact keys)
    mcs_connect: Optional[str]
    mcs_state: Optional[int]
    ucs_connect: Optional[str]
    ucs_state: Optional[int]
    control_state: Optional[str]
    TSCState: Optional[str]
    standby_mode: Optional[str]
    fire_on_bay_group: Optional[str]
    # Always keep raw tokens to ensure nothing is lost
    raw: List[str]
    # Named tokens for verification (pos, key if known, value)
    raw_named: List[Dict[str, Any]]


class VehicleRaw(TypedDict):
    core: List[str]
    cont1: List[str]
    cont2: List[str]


class NamedToken(TypedDict, total=False):
    pos: int
    key: str
    value: str


class VehicleRawNamed(TypedDict):
    core: List[NamedToken]
    cont1: List[NamedToken]
    cont2: List[NamedToken]


class Vehicle(TypedDict, total=False):
    vhl_idx: Optional[int]
    dt_receive: Optional[str]
    vhl_id: Optional[str]
    socket_state: Optional[int]
    CommState: Optional[int]
    comm_acs_hw: Optional[int]
    mode: Optional[int]
    X: Optional[float]
    Y: Optional[float]
    # Always keep raw tokens (all values preserved)
    raw: VehicleRaw
    # Named tokens for verification
    raw_named: VehicleRawNamed


class Command(TypedDict, total=False):
    # Future: fill mapped fields if/when command block structure is added
    pass


class Block(TypedDict):
    timestamp: str
    acs_state: ACSState
    vehicles: List[Vehicle]
    commands: List[Command]
    plc_count: int


__all__ = ["ACSState", "Vehicle", "VehicleRaw", "Command", "Block"]

