"""Filter listings and compute a weighted score from price and rating."""

import tomllib
from pathlib import Path

import pandas as pd

DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "config.toml"


def load_config(path: Path = DEFAULT_CONFIG) -> dict:
    return tomllib.loads(Path(path).read_text())


def _minmax(s: pd.Series) -> pd.Series:
    rng = s.max() - s.min()
    return (s - s.min()) / rng if rng else pd.Series(0.5, index=s.index)


def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    out = df[df["price_per_night"].notna() & (df["review_count"] >= filters.get("min_reviews", 0))]
    out = out[out["rating"].fillna(0) >= filters.get("min_rating", 0)]
    if filters.get("max_price_per_night", 0):
        out = out[out["price_per_night"] <= filters["max_price_per_night"]]
    return out


def score(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Return a copy with price_score, rating_score, score and rank columns."""
    w = cfg["weights"]
    w_price, w_rating = w["price"] / (w["price"] + w["rating"]), w["rating"] / (w["price"] + w["rating"])
    m = cfg["score"]["prior_reviews"]
    q = cfg["score"]["price_clip_quantile"]

    out = df.copy()
    price = out["price_per_night"].clip(upper=out["price_per_night"].quantile(q))
    out["price_score"] = 1 - _minmax(price)

    n, r = out["review_count"], out["rating"].fillna(0)
    mean_rating = r[n > 0].mean()
    out["rating_bayes"] = (n / (n + m)) * r + (m / (n + m)) * mean_rating
    out["rating_score"] = _minmax(out["rating_bayes"])

    out["score"] = w_price * out["price_score"] + w_rating * out["rating_score"]
    out["rank"] = out["score"].rank(ascending=False, method="first").astype(int)
    return out.sort_values("rank")
