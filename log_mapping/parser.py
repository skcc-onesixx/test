from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}")


def _split_tabs(line: str) -> List[str]:
    # Preserve empty fields caused by consecutive tabs
    parts = line.rstrip("\n").split("\t")
    # Trim spaces around tokens but keep empties
    return [p.strip() for p in parts]


def _is_timestamp_line(line: str) -> bool:
    return bool(TIMESTAMP_RE.match(line))


def _to_int(s: str, default: int = 0) -> int:
    try:
        return int(s)
    except Exception:
        return default


def _to_number_if_possible(s: str) -> Any:
    """Convert to int or float if plausible, otherwise return original string."""
    if s is None:
        return None
    if s == "":
        return ""
    # int
    try:
        if s.isdigit() or (s.startswith("-") and s[1:].isdigit()):
            return int(s)
    except Exception:
        pass
    # float
    try:
        # Avoid converting datetime strings — naive check
        if "." in s and " " not in s and s.replace(".", "", 1).replace("-", "", 1).isdigit():
            return float(s)
    except Exception:
        pass
    return s


def _map_tokens_by_index(tokens: List[str], index_map: Dict[str, int], cast_rules: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """
    Map tokens to field names using an index map like {"field": 0, ...}.
    Optionally cast using cast_rules: {"field": "int"|"float"|"str"}.
    """
    result: Dict[str, Any] = {}
    for name, idx in index_map.items():
        value = tokens[idx] if 0 <= idx < len(tokens) else ""
        if cast_rules:
            kind = cast_rules.get(name)
        else:
            kind = None
        if kind == "int":
            try:
                result[name] = int(value) if value != "" else None
            except Exception:
                result[name] = None
        elif kind == "float":
            try:
                result[name] = float(value) if value != "" else None
            except Exception:
                result[name] = None
        elif kind == "str":
            result[name] = value
        else:
            # best-effort numeric cast
            result[name] = _to_number_if_possible(value)
    return result


def _make_raw_named(tokens: List[str], idx_to_name: Optional[Dict[int, str]] = None) -> List[Dict[str, Any]]:
    """
    Produce a diagnostics-friendly list of {pos, key?, value} for tokens.
    If idx_to_name is provided, 'key' is included when known.
    """
    out: List[Dict[str, Any]] = []
    for pos, tok in enumerate(tokens):
        entry: Dict[str, Any] = {"pos": pos, "value": tok}
        if idx_to_name and pos in idx_to_name:
            entry["key"] = idx_to_name[pos]
        out.append(entry)
    return out


def parse_file(
    file_path: Path,
    field_map: Optional[Dict[str, Any]] = None,
    include_unmapped: bool = False,
) -> List[Dict[str, Any]]:
    """
    Parse a single .log file into a list of JSON-serializable blocks.
    Each block corresponds to a timestamp group:
      - timestamp line
      - RCS/ACS line
      - vhl <cnt>
      - 'cnt' vehicle groups (3 lines per vehicle observed)
      - command <cnt>
      - plc cnt <n>
    """
    blocks: List[Dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    i = 0
    total = len(lines)
    while i < total:
        line = lines[i]
        if not line.strip():
            i += 1
            continue

        if not _is_timestamp_line(line):
            # Skip until we find a timestamp line
            i += 1
            continue

        timestamp = line.strip()
        i += 1

        # Expect RCS line
        if i >= total:
            break
        rcs_line = lines[i]
        rcs_tokens = _split_tabs(rcs_line)
        i += 1

        # Map ACS state
        acs_state: Dict[str, Any] = {}
        if rcs_tokens and rcs_tokens[0] == "RCS":
            acs_tokens = rcs_tokens[1:]
            acs_map = (field_map or {}).get("acs_state") if field_map else None
            if isinstance(acs_map, dict) and acs_map:
                acs_state = _map_tokens_by_index(acs_tokens, acs_map, cast_rules={
                    "mcs_connect": "str",
                    "mcs_state": "int",
                    "ucs_connect": "str",
                    "ucs_state": "int",
                    "control_state": None,
                    "TSCState": None,
                    "standby_mode": None,
                    "fire_on_bay_group": "str",
                })
            # Always preserve raw tokens
            acs_state["raw"] = acs_tokens
            # Add named raw tokens for verification
            if isinstance(acs_map, dict) and acs_map:
                # build reverse map: index -> name
                rev = {idx: name for name, idx in acs_map.items() if isinstance(idx, int)}
            else:
                rev = {}
            acs_state["raw_named"] = _make_raw_named(acs_tokens, rev)
        else:
            # Unexpected
            acs_state = {"raw": rcs_tokens}

        # Expect vhl line
        if i >= total:
            break
        vhl_line = lines[i]
        vhl_tokens = _split_tabs(vhl_line)
        i += 1

        vehicles: List[Dict[str, Any]] = []
        vhl_cnt = 0
        if vhl_tokens and vhl_tokens[0] == "vhl":
            if len(vhl_tokens) > 1:
                vhl_cnt = _to_int(vhl_tokens[1], 0)
        else:
            # If structure is off, try to recover by scanning ahead
            vhl_cnt = 0

        for _ in range(vhl_cnt):
            if i >= total:
                break
            core = lines[i]
            i += 1
            core_tokens = _split_tabs(core)

            # Two continuation lines are typically present
            cont1_tokens: List[str] = []
            if i < total:
                cont1_tokens = _split_tabs(lines[i])
                i += 1
            cont2_tokens: List[str] = []
            if i < total:
                cont2_tokens = _split_tabs(lines[i])
                i += 1

            vehicle_obj: Dict[str, Any] = {}
            vmap = (field_map or {}).get("vehicle_core") if field_map else None
            if isinstance(vmap, dict) and vmap:
                vehicle_obj.update(
                    _map_tokens_by_index(
                        core_tokens,
                        vmap,
                        cast_rules={
                            "vhl_idx": "int",
                            "dt_receive": "str",
                            "vhl_id": "str",
                        },
                    )
                )
            else:
                # Fallback minimal extraction
                vhl_idx: Optional[int] = None
                dt_receive: Optional[str] = None
                vhl_id: Optional[str] = None
                if len(core_tokens) > 0:
                    try:
                        vhl_idx = int(core_tokens[0])
                    except Exception:
                        vhl_idx = None
                if len(core_tokens) > 1:
                    dt_receive = core_tokens[1] or None
                if len(core_tokens) > 2:
                    vhl_id = core_tokens[2] or None
                vehicle_obj.update(
                    {
                        "vhl_idx": vhl_idx,
                        "dt_receive": dt_receive,
                        "vhl_id": vhl_id,
                    }
                )

            # Always preserve raw tokens so nothing is dropped
            vehicle_obj["raw"] = {
                "core": core_tokens,
                "cont1": cont1_tokens,
                "cont2": cont2_tokens,
            }
            # Named tokens for verification using available maps
            vmap = (field_map or {}).get("vehicle_core") if field_map else None
            vrev = {idx: name for name, idx in vmap.items()} if isinstance(vmap, dict) else {}
            cont1_map = (field_map or {}).get("vehicle_cont1") if field_map else None
            cont1_rev = {idx: name for name, idx in cont1_map.items()} if isinstance(cont1_map, dict) else {}
            cont2_map = (field_map or {}).get("vehicle_cont2") if field_map else None
            cont2_rev = {idx: name for name, idx in cont2_map.items()} if isinstance(cont2_map, dict) else {}
            vehicle_obj["raw_named"] = {
                "core": _make_raw_named(core_tokens, vrev),
                "cont1": _make_raw_named(cont1_tokens, cont1_rev),
                "cont2": _make_raw_named(cont2_tokens, cont2_rev),
            }
            # Also include named tokens inside raw for convenience
            vehicle_obj["raw"]["core_named"] = _make_raw_named(core_tokens, vrev)
            vehicle_obj["raw"]["cont1_named"] = _make_raw_named(cont1_tokens, cont1_rev)
            vehicle_obj["raw"]["cont2_named"] = _make_raw_named(cont2_tokens, cont2_rev)

            # Heuristic parsing of list groups from continuation tokens.
            # Many list sections encode counts like 'N;' followed by N tokens.
            # We parse sequential counts and map to known group names in order.
            cont_stream: List[str] = []
            if cont1_tokens:
                cont_stream.extend(cont1_tokens)
            if cont2_tokens:
                cont_stream.extend(cont2_tokens)

            def is_count_tok(tok: str) -> bool:
                return tok.endswith(";") and tok[:-1].strip().lstrip("-").isdigit()

            groups_order = [
                "list_sch",
                "list_pp",
                "list_po_idx",
                "list_oppo_path_seq_idx",
                "list_da_block_idx",
                "list_da_block_idx_manual",
            ]
            group_idx = 0
            j = 0
            parsed_groups: Dict[str, Any] = {}
            while j < len(cont_stream) and group_idx < len(groups_order):
                tok = cont_stream[j]
                if is_count_tok(tok):
                    cnt = _to_int(tok[:-1], 0)
                    j += 1
                    items: List[Any] = []
                    for _k in range(cnt):
                        if j >= len(cont_stream):
                            break
                        items.append(_to_number_if_possible(cont_stream[j]))
                        j += 1
                    gname = groups_order[group_idx]
                    # If group already exists (multiple counts), suffix with index
                    if gname in parsed_groups:
                        idx_suffix = 2
                        while f"{gname}_{idx_suffix}" in parsed_groups:
                            idx_suffix += 1
                        gname = f"{gname}_{idx_suffix}"
                    parsed_groups[gname] = {
                        "count": cnt,
                        "items": items,
                    }
                    group_idx += 1
                else:
                    # Non-count token; advance
                    j += 1

            if parsed_groups:
                vehicle_obj.update(parsed_groups)

            # Append assembled vehicle
            vehicles.append(vehicle_obj)

        # Expect command line
        commands: List[Dict[str, Any]] = []
        cmd_count = 0
        if i < total:
            cmd_line = lines[i]
            cmd_tokens = _split_tabs(cmd_line)
            if cmd_tokens and cmd_tokens[0] == "command":
                if len(cmd_tokens) > 1:
                    cmd_count = _to_int(cmd_tokens[1], 0)
                i += 1

        # Expect plc cnt line
        plc_count = 0
        if i < total:
            plc_line = lines[i]
            plc_tokens = _split_tabs(plc_line)
            if plc_tokens and plc_tokens[0].startswith("plc cnt"):
                if len(plc_tokens) > 1:
                    plc_count = _to_int(plc_tokens[1], 0)
                i += 1

        blocks.append(
            {
                "timestamp": timestamp,
                "acs_state": acs_state,
                "vehicles": vehicles,
                "commands": commands if cmd_count > 0 else [],
                "plc_count": plc_count,
            }
        )

    return blocks

