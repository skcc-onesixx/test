from __future__ import annotations

import argparse
from pathlib import Path
import json
from typing import Any, Dict, List, Optional

from log_mapping.parser import parse_file

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Parse ACS/AGV logs into JSON (block granularity)."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        type=Path,
        help="Directory containing .log files to parse.",
    )
    parser.add_argument(
        "--output-dir",
        default=Path("out"),
        type=Path,
        help="Directory to write JSON outputs (per input file).",
    )
    parser.add_argument(
        "--granularity",
        default="block",
        choices=["block"],
        help="Output granularity. Only 'block' is supported.",
    )
    parser.add_argument(
        "--format",
        dest="output_format",
        default="array",
        choices=["array"],
        help="Output format for a file. Only 'array' is supported.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing JSON files in output directory.",
    )
    parser.add_argument(
        "--include-unmapped",
        action="store_true",
        help="Include 'unmapped' raw tokens for troubleshooting.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir: Path = args.input_dir
    output_dir: Path = args.output_dir
    granularity: str = args.granularity
    output_format: str = args.output_format
    overwrite: bool = bool(args.overwrite)
    include_unmapped: bool = bool(args.include_unmapped)

    if not input_dir.exists() or not input_dir.is_dir():
        raise SystemExit(f"Input directory not found or not a directory: {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    log_files: List[Path] = sorted([p for p in input_dir.iterdir() if p.is_file() and p.suffix == ".log"])
    if not log_files:
        print(f"[WARN] No .log files found in: {input_dir}")
        return

    # Load field map if present
    field_map_path = Path("log_mapping/field_map_v1.json")
    field_map: Optional[Dict[str, Any]] = None
    if field_map_path.exists():
        try:
            with field_map_path.open("r", encoding="utf-8") as fp:
                field_map = json.load(fp)
        except Exception as e:
            print(f"[WARN] Failed to load field map: {e}")
            field_map = None

    for log_path in log_files:
        out_path = output_dir / f"{log_path.name}.json"
        if out_path.exists() and not overwrite:
            print(f"[SKIP] Exists: {out_path}")
            continue

        print(f"[PARSE] {log_path} -> {out_path}")
        blocks = parse_file(log_path, field_map=field_map, include_unmapped=include_unmapped)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(blocks, f, ensure_ascii=False)
        print(f"[DONE] {out_path} ({len(blocks)} blocks)")


if __name__ == "__main__":
    main()
