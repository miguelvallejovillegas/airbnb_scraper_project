"""CLI: python -m airbnb_scraper --city "Medellín" --checkin 2026-11-14 --checkout 2026-11-16"""

import argparse
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

from .fetch import fetch_city
from .geocode import city_to_bbox
from .score import apply_filters, load_config, score
from .transform import to_dataframe

ROOT = Path(__file__).resolve().parent.parent


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def main():
    default_in = date.today() + timedelta(days=30)
    p = argparse.ArgumentParser(description="Scrape Airbnb listings for a city and rank them into a CSV.")
    p.add_argument("--city", default="Medellín")
    p.add_argument("--checkin", default=default_in.isoformat())
    p.add_argument("--checkout", default=(default_in + timedelta(days=2)).isoformat())
    p.add_argument("--adults", type=int, default=2)
    p.add_argument("--currency", default="COP")
    p.add_argument("--grid", type=int, default=2, help="split the city bbox into N x N tiles (more tiles = more listings)")
    p.add_argument("--config", type=Path, default=ROOT / "config.toml")
    p.add_argument("--out", type=Path)
    args = p.parse_args()

    slug = f"{slugify(args.city)}_{args.checkin}_{args.checkout}"
    out = args.out or ROOT / "data" / f"{slug}.csv"

    print(f"Geocodificando {args.city}...")
    bbox = city_to_bbox(args.city)
    print(f"Buscando en Airbnb ({args.checkin} -> {args.checkout}, {args.adults} adultos, {args.currency})")
    raw = fetch_city(bbox, args.checkin, args.checkout, args.adults, args.currency, args.grid,
                     raw_path=ROOT / "data" / "raw" / f"{slug}.json")
    df = to_dataframe(raw, args.checkin, args.checkout, args.currency)
    print(f"{len(df)} listings únicos")

    cfg = load_config(args.config)
    ranked = score(apply_filters(df, cfg["filters"]), cfg)
    # keep every listing in the CSV; score/rank are empty for those that failed the filters
    score_cols = ["room_id", "price_score", "rating_bayes", "rating_score", "score", "rank"]
    full = df.merge(ranked[score_cols], on="room_id", how="left").sort_values("rank", na_position="last")
    out.parent.mkdir(parents=True, exist_ok=True)
    full.to_csv(out, index=False)
    print(f"{len(ranked)} listings pasan los filtros y reciben score -> {out}\n")
    cols = ["rank", "name", "price_per_night", "rating", "review_count", "score", "url"]
    print(ranked[cols].head(10).to_string(index=False))


if __name__ == "__main__":
    main()
