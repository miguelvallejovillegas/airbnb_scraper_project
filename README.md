# airbnb_scraper_project

Scraper that extracts every Airbnb listing available in a city for a date range, scores each one with a
weighted combination of **price per night** and **rating adjusted by number of reviews**, and writes a
ranked CSV. A companion notebook does an exploratory analysis of the data for Medellín.

Best-effort side project: it talks to Airbnb's internal `StaysSearch` API through
[`pyairbnb`](https://github.com/johnbalvin/pyairbnb), so it can break or get blocked whenever Airbnb changes something.

## How it works

```
city name ──► Nominatim (OSM) ──► bounding box ──► N x N tiles
                                                        │
                      pyairbnb (StaysSearch API, paginated) per tile
                                                        │
                   raw JSON ──► flat DataFrame ──► filters + score ──► CSV
```

- `airbnb_scraper/geocode.py` – city name → bounding box (no API key), and splits it into a grid.
  Airbnb caps a search at ~280 results, so more tiles = more listings.
- `airbnb_scraper/fetch.py` – paginates the search for each tile, dedupes by listing id, dumps raw JSON to `data/raw/`.
- `airbnb_scraper/transform.py` – flattens the raw results. Parses prices from the display strings
  (`"326.800 $ COP"`, `"$1,234.50"`) because `pyairbnb`'s own parser mangles locales that use `.` as thousands separator.
- `airbnb_scraper/score.py` – filters + weighted score (see below).
- `airbnb_scraper/__main__.py` – CLI.

## Usage

```bash
uv sync                      # scraper only
uv sync --group notebook     # + jupyter, matplotlib, seaborn

uv run python -m airbnb_scraper --city "Medellín" --checkin 2026-11-14 --checkout 2026-11-16 --grid 3
```

| flag | default | meaning |
|---|---|---|
| `--city` | `Medellín` | anything Nominatim can geocode |
| `--checkin` / `--checkout` | today + 30 days, 2 nights | ISO dates |
| `--adults` | `2` | |
| `--currency` | `COP` | any Airbnb currency code |
| `--grid` | `2` | split the city into N×N search tiles |
| `--config` | `config.toml` | weights and filters |
| `--out` | `data/{city}_{checkin}_{checkout}.csv` | |

The CSV keeps **every** listing found; `score` and `rank` are empty for listings that failed the filters.

## Score

Configured in `config.toml`:

```toml
[weights]
price = 0.5
rating = 0.5

[score]
prior_reviews = 10
price_clip_quantile = 0.95

[filters]
min_reviews = 3
min_rating = 0.0
max_price_per_night = 0   # 0 = no cap
```

- `price_score = 1 - minmax(price_per_night clipped at the p95)`
- `rating_bayes = n/(n+m) · rating + m/(n+m) · mean_rating`, with `n` = review count and `m = prior_reviews`,
  so a 5.0 with 2 reviews does not beat a 4.9 with 200.
- `rating_score = minmax(rating_bayes)`
- `score = w_price · price_score + w_rating · rating_score` (weights normalised to sum 1)

## CSV columns

`room_id, name, title, details, lat, lng, price_total, price_per_night, currency, rating, review_count,
is_guest_favorite, is_superhost, badges, url, image_url, checkin, checkout, nights, scraped_at,
price_score, rating_bayes, rating_score, score, rank`

`price_total` is the total Airbnb displays for the stay (discounts applied, taxes excluded).

## Notebook

`notebooks/eda_medellin.ipynb` – exploratory analysis of `data/medellin_2026-11-14_2026-11-16.csv`
(1,217 listings, 2 adults, Nov 14–16 2026): price distribution, type and zone, rating vs reviews,
correlations, badges, a map, the top 15 by score and how stable the ranking is when the weights change.

```bash
uv run jupyter notebook notebooks/eda_medellin.ipynb
# or re-execute headless
uv run jupyter nbconvert --execute --to notebook --inplace notebooks/eda_medellin.ipynb
```
