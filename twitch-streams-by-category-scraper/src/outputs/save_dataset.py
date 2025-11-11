import csv
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union

PathLike = Union[str, Path]

def ensure_output_dir(output_dir: Path) -> None:
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        logging.error("Failed to create output directory %s: %s", output_dir, exc)
        raise

def save_to_json(records: List[Dict[str, Any]], path: Path) -> None:
    try:
        with path.open("w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
    except OSError as exc:
        logging.error("Failed to write JSON file %s: %s", path, exc)
        raise

def save_to_ndjson(records: List[Dict[str, Any]], path: Path) -> None:
    try:
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        logging.error("Failed to write NDJSON file %s: %s", path, exc)
        raise

def save_to_csv(records: List[Dict[str, Any]], path: Path) -> None:
    if not records:
        logging.warning("No records provided, CSV file %s will be empty.", path)
        return

    fieldnames = sorted(records[0].keys())
    try:
        with path.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(record)
    except OSError as exc:
        logging.error("Failed to write CSV file %s: %s", path, exc)
        raise

def save_dataset(
    records: List[Dict[str, Any]],
    output_dir: PathLike,
    base_filename: str,
    output_format: str = "json",
) -> Path:
    if isinstance(output_dir, str):
        output_dir = Path(output_dir)

    ensure_output_dir(output_dir)

    fmt = (output_format or "json").lower()
    ext_map = {"json": ".json", "csv": ".csv", "ndjson": ".ndjson"}
    ext = ext_map.get(fmt, ".json")

    path = output_dir / f"{base_filename}{ext}"

    logging.info("Saving %d records as %s format to %s", len(records), fmt, path)

    if fmt == "csv":
        save_to_csv(records, path)
    elif fmt == "ndjson":
        save_to_ndjson(records, path)
    else:
        save_to_json(records, path)

    return path