import logging
import re
import unicodedata
from typing import Any, Iterable, List

def slugify_category_name(name: str) -> str:
    value = unicodedata.normalize("NFKD", name)
    value = value.encode("ascii", "ignore").decode("ascii")
    value = value.lower()
    value = re.sub(r"[^\w\s-]", "", value)
    value = re.sub(r"[\s_]+", "-", value).strip("-")
    return value

def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        logging.debug("Failed to convert %r to int. Using default %d.", value, default)
        return default

def normalize_tags(raw_tags: Any) -> List[str]:
    if raw_tags is None:
        return []

    tags: List[str] = []

    if isinstance(raw_tags, dict):
        raw_tags = raw_tags.values()

    if isinstance(raw_tags, str):
        for part in raw_tags.split(","):
            tag = part.strip()
            if tag:
                tags.append(tag)
    elif isinstance(raw_tags, Iterable):
        for tag in raw_tags:
            if isinstance(tag, dict):
                candidate = (
                    tag.get("tagName")
                    or tag.get("localizedName")
                    or tag.get("label")
                    or ""
                )
            else:
                candidate = str(tag or "")
            candidate = candidate.strip()
            if candidate:
                tags.append(candidate)
    else:
        candidate = str(raw_tags or "").strip()
        if candidate:
            tags.append(candidate)

    seen = set()
    unique_tags: List[str] = []
    for t in tags:
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        unique_tags.append(t)

    return unique_tags