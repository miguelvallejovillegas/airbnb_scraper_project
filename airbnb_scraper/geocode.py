"""City name -> bounding box (via OpenStreetMap Nominatim, no API key)."""

import requests

NOMINATIM = "https://nominatim.openstreetmap.org/search"


def city_to_bbox(city: str) -> tuple[float, float, float, float]:
    """Return (ne_lat, ne_lng, sw_lat, sw_lng) for a city name."""
    r = requests.get(
        NOMINATIM,
        params={"q": city, "format": "json", "limit": 1},
        headers={"User-Agent": "airbnb-scraper-side-project"},
        timeout=30,
    )
    r.raise_for_status()
    hits = r.json()
    if not hits:
        raise ValueError(f"Nominatim no encontró la ciudad: {city!r}")
    south, north, west, east = (float(x) for x in hits[0]["boundingbox"])
    return north, east, south, west


def split_bbox(bbox, n: int):
    """Split a bbox into an n x n grid of smaller bboxes (same tuple order)."""
    ne_lat, ne_lng, sw_lat, sw_lng = bbox
    dlat = (ne_lat - sw_lat) / n
    dlng = (ne_lng - sw_lng) / n
    return [
        (sw_lat + (i + 1) * dlat, sw_lng + (j + 1) * dlng, sw_lat + i * dlat, sw_lng + j * dlng)
        for i in range(n)
        for j in range(n)
    ]
