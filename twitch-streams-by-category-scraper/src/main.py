import argparse
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from extractors.twitch_parser import scrape_category
from outputs.save_dataset import save_dataset

DEFAULT_SETTINGS: Dict[str, Any] = {
    "input_file": "data/inputs.sample.json",
    "output_format": "json",
    "output_dir": "data",
    "max_streams_per_category": 100,
    "http": {
        "timeout_seconds": 15,
        "headers": {
            "User-Agent": "Mozilla/5.0 (compatible; TwitchCategoryScraper/1.0; +https://bitbash.dev)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    },
}

def load_settings(path: Path) -> Dict[str, Any]:
    if not path.exists():
        logging.warning("Settings file not found at %s, using defaults.", path)
        return DEFAULT_SETTINGS.copy()

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as exc:
        logging.error("Failed to parse settings file %s: %s", path, exc)
        return DEFAULT_SETTINGS.copy()
    except OSError as exc:
        logging.error("Failed to read settings file %s: %s", path, exc)
        return DEFAULT_SETTINGS.copy()

    merged = DEFAULT_SETTINGS.copy()
    merged.update(data or {})
    # Merge nested http settings
    if "http" in data:
        merged_http = DEFAULT_SETTINGS["http"].copy()
        merged_http.update(data["http"] or {})
        merged["http"] = merged_http
    return merged

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scrape live Twitch streams by category."
    )
    parser.add_argument(
        "--settings",
        default="src/config/settings.example.json",
        help="Path to settings JSON file (relative to project root).",
    )
    parser.add_argument(
        "--input",
        help="Override input file containing categories (JSON).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "csv", "ndjson"],
        help="Override output format.",
    )
    parser.add_argument(
        "--max-streams",
        type=int,
        help="Override maximum number of streams to fetch per category.",
    )
    return parser.parse_args()

def load_categories(input_path: Path) -> List[str]:
    if not input_path.exists():
        logging.error("Input file not found at %s", input_path)
        return []

    try:
        with input_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as exc:
        logging.error("Failed to parse input file %s: %s", input_path, exc)
        return []
    except OSError as exc:
        logging.error("Failed to read input file %s: %s", input_path, exc)
        return []

    categories = payload.get("categories") or []
    if not isinstance(categories, list):
        logging.error("Invalid input format: 'categories' must be a list.")
        return []

    categories = [c for c in categories if isinstance(c, str) and c.strip()]
    if not categories:
        logging.error("No valid categories found in input file.")
    return categories

def main() -> None:
    base_dir = Path(__file__).resolve().parents[1]
    args = parse_args()

    settings_path = (base_dir / args.settings).resolve()
    settings = load_settings(settings_path)

    if args.input:
        settings["input_file"] = args.input
    if args.format:
        settings["output_format"] = args.format
    if args.max_streams is not None:
        settings["max_streams_per_category"] = args.max_streams

    input_path = (base_dir / settings.get("input_file", "data/inputs.sample.json")).resolve()
    output_dir = (base_dir / settings.get("output_dir", "data")).resolve()
    output_format = str(settings.get("output_format", "json")).lower()
    max_streams = int(settings.get("max_streams_per_category", 100))

    http_settings = settings.get("http", {}) or {}
    timeout_seconds = int(http_settings.get("timeout_seconds", 15))
    headers = http_settings.get("headers") or {}

    categories = load_categories(input_path)
    if not categories:
        logging.error("Aborting: no categories to scrape.")
        return

    all_records: List[Dict[str, Any]] = []

    for category in categories:
        try:
            logging.info("Scraping category '%s'...", category)
            records = scrape_category(
                category_name=category,
                max_streams=max_streams,
                timeout=timeout_seconds,
                headers=headers,
            )
            logging.info(
                "Scraped %d streams for category '%s'.", len(records), category
            )
            all_records.extend(records)
        except Exception as exc:
            logging.exception(
                "Unexpected error while scraping category '%s': %s", category, exc
            )

    if not all_records:
        logging.warning("No records scraped from any category. Nothing to save.")
        return

    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    base_filename = f"twitch_streams_{timestamp}"

    saved_path = save_dataset(
        records=all_records,
        output_dir=output_dir,
        base_filename=base_filename,
        output_format=output_format,
    )
    logging.info("Scraping completed. Dataset saved to %s", saved_path)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )
    main()