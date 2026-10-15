"""Flatten raw StaySearchResult dicts into a tidy DataFrame."""

import base64
import re
from datetime import datetime, timezone

import pandas as pd

_NUM = re.compile(r"-?[\d.,]+")


def parse_money(text: str | None) -> float | None:
    """'326.800 $ COP' -> 326800.0, '1,234.50 USD' -> 1234.5, '524.982,80' -> 524982.8"""
    if not text:
        return None
    m = _NUM.search(text)
    if not m:
        return None
    s = m.group(0)
    if "." in s and "," in s:
        dec = s[max(s.rfind("."), s.rfind(","))]
    elif "." in s or "," in s:
        sep = "." if "." in s else ","
        dec = sep if len(s.rsplit(sep, 1)[1]) != 3 else None  # 'x.xxx' is a thousands group
    else:
        dec = None
    for sep in ".,":
        s = s.replace(sep, "." if sep == dec else "")
    return float(s)


def _listing_id(encoded: str) -> int:
    return int(base64.b64decode(encoded).decode().split(":")[-1])


def _rating(text: str | None):
    """'4,98 (42)' -> (4.98, 42); 'Nuevo' -> (None, 0)"""
    m = re.match(r"([\d.,]+)\s*\((\d+)\)", text or "")
    if not m:
        return None, 0
    return float(m.group(1).replace(",", ".")), int(m.group(2))


def _price_total(sdp: dict) -> float | None:
    line = (sdp or {}).get("primaryLine") or {}
    return parse_money(line.get("discountedPrice") or line.get("price"))


def to_dataframe(raw: list[dict], checkin: str, checkout: str, currency: str) -> pd.DataFrame:
    nights = (datetime.fromisoformat(checkout) - datetime.fromisoformat(checkin)).days
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for r in raw:
        d = r["demandStayListing"]
        coord = (d.get("location") or {}).get("coordinate") or {}
        rating, reviews = _rating(r.get("avgRatingLocalized"))
        badges = [b["loggingContext"]["badgeType"] for b in r.get("badges", []) if b.get("loggingContext")]
        total = _price_total(r.get("structuredDisplayPrice"))
        pics = r.get("contextualPictures") or []
        room_id = _listing_id(d["id"])
        rows.append({
            "room_id": room_id,
            "name": (d.get("description") or {}).get("name", {}).get("localizedStringWithTranslationPreference"),
            "title": r.get("title"),
            "details": " · ".join(m["body"] for m in (r.get("structuredContent") or {}).get("primaryLine", [])),
            "lat": coord.get("latitude"),
            "lng": coord.get("longitude"),
            "price_total": total,
            "price_per_night": total / nights if total else None,
            "currency": currency,
            "rating": rating,
            "review_count": reviews,
            "is_guest_favorite": any("GUEST_FAVORITE" in b for b in badges),
            "is_superhost": "SUPERHOST" in badges,
            "badges": "|".join(badges),
            "url": f"https://www.airbnb.com/rooms/{room_id}?check_in={checkin}&check_out={checkout}",
            "image_url": pics[0].get("picture") if pics else None,
            "checkin": checkin,
            "checkout": checkout,
            "nights": nights,
            "scraped_at": now,
        })
    return pd.DataFrame(rows)
