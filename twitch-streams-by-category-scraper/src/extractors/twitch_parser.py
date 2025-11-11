import json
import logging
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup

from .utils_format import normalize_tags, safe_int, slugify_category_name

def fetch_category_html(
    category_slug: str,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
) -> str:
    url = f"https://www.twitch.tv/directory/category/{category_slug}"
    base_headers = {
        "User-Agent": "Mozilla/5.0 (compatible; TwitchCategoryScraper/1.0; +https://bitbash.dev)",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if headers:
        base_headers.update(headers)

    logging.debug("Fetching Twitch category page: %s", url)
    try:
        response = requests.get(url, headers=base_headers, timeout=timeout)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("HTTP error while fetching %s: %s", url, exc)
        raise

    return response.text

def extract_next_data(html: str) -> Optional[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")

    if not script or not script.string:
        logging.warning("Could not locate __NEXT_DATA__ script in Twitch HTML.")
        return None

    try:
        data = json.loads(script.string)
    except json.JSONDecodeError as exc:
        logging.error("Failed to decode __NEXT_DATA__ JSON: %s", exc)
        return None

    return data

def _gather_stream_nodes(node: Any, results: List[Dict[str, Any]]) -> None:
    if isinstance(node, dict):
        keys = node.keys()
        has_viewers = any(k in keys for k in ("viewCount", "viewersCount", "viewerCount"))
        has_title = "title" in keys
        has_broadcaster = any(
            k in keys for k in ("broadcasterLogin", "login", "channelLogin")
        )

        if has_viewers and has_title and has_broadcaster:
            results.append(node)

        for value in node.values():
            _gather_stream_nodes(value, results)

    elif isinstance(node, list):
        for item in node:
            _gather_stream_nodes(item, results)

def parse_streams_from_data(
    data: Optional[Dict[str, Any]],
    max_streams: int,
) -> List[Dict[str, Any]]:
    if not data:
        return []

    candidates: List[Dict[str, Any]] = []
    _gather_stream_nodes(data, candidates)

    if not candidates:
        logging.warning("No stream nodes found in Twitch page data.")
        return []

    unique_nodes: List[Dict[str, Any]] = []
    seen_keys = set()

    for node in candidates:
        login = node.get("broadcasterLogin") or node.get("login") or node.get(
            "channelLogin"
        )
        title = node.get("title")
        key = (login, title)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        unique_nodes.append(node)

    streams: List[Dict[str, Any]] = []

    for node in unique_nodes[:max_streams]:
        login = node.get("broadcasterLogin") or node.get("login") or node.get(
            "channelLogin"
        )
        url = f"https://www.twitch.tv/{login}" if login else None

        game = node.get("game")
        game_name: Optional[str] = None
        if isinstance(game, dict):
            game_name = game.get("displayName") or game.get("name")
        elif isinstance(game, str):
            game_name = game
        elif game is not None:
            game_name = str(game)

        badges = node.get("broadcasterBadges") or []
        broadcaster_type = (node.get("broadcasterType") or "").upper()
        partner_status = "Partnered" if broadcaster_type == "PARTNER" else "Non-Partner"

        if badges:
            badge_text = " ".join(
                " ".join(
                    str(part or "")
                    for part in (
                        badge.get("setID"),
                        badge.get("title"),
                        badge.get("description"),
                    )
                )
                for badge in badges
                if isinstance(badge, dict)
            )
            if re.search(r"partner", badge_text, re.IGNORECASE):
                partner_status = "Partnered"

        tags = normalize_tags(node.get("tags"))

        viewers = (
            node.get("viewCount")
            or node.get("viewersCount")
            or node.get("viewerCount")
            or 0
        )

        stream_record: Dict[str, Any] = {
            "url": url,
            "gameName": game_name,
            "partnerStatus": partner_status,
            "tags": tags,
            "title": node.get("title"),
            "viewCount": safe_int(viewers, default=0),
        }
        streams.append(stream_record)

    return streams

def scrape_category(
    category_name: str,
    max_streams: int = 100,
    timeout: int = 15,
    headers: Optional[Dict[str, str]] = None,
) -> List[Dict[str, Any]]:
    category_slug = slugify_category_name(category_name)
    logging.info(
        "Scraping Twitch category '%s' (slug: '%s')", category_name, category_slug
    )

    html = fetch_category_html(
        category_slug=category_slug,
        timeout=timeout,
        headers=headers,
    )
    next_data = extract_next_data(html)
    streams = parse_streams_from_data(next_data, max_streams=max_streams)

    if not streams:
        logging.warning(
            "No streams parsed for category '%s' (slug '%s').",
            category_name,
            category_slug,
        )

    for stream in streams:
        if not stream.get("gameName"):
            stream["gameName"] = category_name

    return streams