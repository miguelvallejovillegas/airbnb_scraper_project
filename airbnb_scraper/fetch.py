"""Fetch raw listings from Airbnb's internal StaysSearch API (through pyairbnb's request layer)."""

import json
import time
from pathlib import Path

from pyairbnb import api, search

from .geocode import split_bbox


def _search_page(api_key, cursor, bbox, checkin, checkout, adults, currency, zoom=12):
    ne_lat, ne_lng, sw_lat, sw_lng = bbox
    return search.get(
        api_key=api_key, cursor=cursor, check_in=checkin, check_out=checkout,
        ne_lat=ne_lat, ne_long=ne_lng, sw_lat=sw_lat, sw_long=sw_lng, zoom_value=zoom,
        currency=currency, place_type="", price_min=0, price_max=0, amenities=[],
        free_cancellation=False, adults=adults, children=0, infants=0,
        min_bedrooms=0, min_beds=0, min_bathrooms=0, language="es", proxy_url="",
        hash="", timeout=60,
    )


def fetch_bbox(api_key, bbox, checkin, checkout, adults, currency):
    """Follow pagination for one bbox; return the raw StaySearchResult dicts."""
    items, cursor = [], ""
    while True:
        page = _search_page(api_key, cursor, bbox, checkin, checkout, adults, currency)
        results = page["data"]["presentation"]["staysSearch"]["results"]
        items += [r for r in results.get("searchResults", []) if r.get("__typename") == "StaySearchResult"]
        cursor = (results.get("paginationInfo") or {}).get("nextPageCursor")
        if not cursor:
            return items


def fetch_city(bbox, checkin, checkout, adults, currency, grid: int, raw_path: Path | None = None):
    """Search every tile of the city bbox, dedupe by listing id, optionally dump raw JSON."""
    api_key = api.get("")
    seen: dict = {}
    tiles = split_bbox(bbox, grid)
    for i, tile in enumerate(tiles, 1):
        try:
            results = fetch_bbox(api_key, tile, checkin, checkout, adults, currency)
        except Exception as e:  # best effort: Airbnb may block or change its API
            print(f"  tile {i}/{len(tiles)}: error {type(e).__name__}: {e}")
            continue
        new = sum(1 for r in results if r["demandStayListing"]["id"] not in seen)
        for r in results:
            seen.setdefault(r["demandStayListing"]["id"], r)
        print(f"  tile {i}/{len(tiles)}: {len(results)} resultados ({new} nuevos)")
        time.sleep(1)
    listings = list(seen.values())
    if raw_path:
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_text(json.dumps(listings, ensure_ascii=False))
    return listings
