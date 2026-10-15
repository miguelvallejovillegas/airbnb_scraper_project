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

### Findings (Medellín, Nov 14–16 2026, 2 adults, 1,217 listings)

1. **Rating does not discriminate; review count does.** Mean rating is 4.82, median 4.87. 59% of listings with
   5 or fewer reviews have a perfect 5.0; among listings with more than 50 reviews that share drops to 1%.
   A 5.0 is almost always a sign of a new listing, not of superior quality. That is why the score uses a
   Bayesian average instead of the raw rating.
2. **Reputation is not priced in.** Correlation of price with rating, Guest Favorite and Superhost is below 0.1
   in every case. Median price with and without Superhost differs by less than 10k COP, and Superhosts do not
   even rate higher on average (4.819 vs 4.824). Guest Favorite is the only badge with a real signal
   (4.92 vs 4.72 average rating).
3. **New listings are more expensive, not cheaper.** The 375 listings without reviews (31% of the total) have a
   median of 276k COP vs 218k for listings with history. Median price falls monotonically with review count,
   from 226k (1–5 reviews) to 198k (300+). Cheap listings get booked and build history; expensive new ones wait.
4. **The expensive stuff is outside the city.** The highest median prices are rural: Vereda El Noral (915k),
   San Félix, Guarne, Copacabana and Santa Elena (306k). Laureles-Estadio, Envigado and Itagüí are among the
   cheapest (165–170k). These are fincas and cabins for groups. Nominatim's bounding box for "Medellín" pulls in
   neighbouring municipalities, which is what makes the dataset interesting.
5. **Listing type explains more than any other variable.** Median per night: Habitación 161k, Apartamento 192k,
   Loft 204k vs Cabaña 362k, Casa 403k, Vivienda 420k. Roughly 2x between the urban block and the whole-house
   or rural block.
6. **The 50/50 score favours private rooms.** 10 of the top 15 are rooms, all between 58k and 170k COP per
   night, with a median of 54 reviews. Because ratings are so compressed, price ends up deciding. To get whole
   apartments, raise the rating weight or filter by type.
7. **The ranking is moderately stable.** Moving to 70% price keeps 8 of the default top 10; moving to 70%
   rating keeps 6. There is a core of listings that are good on both dimensions.
8. **Fun fact.** The most-reviewed listing has 4,028 reviews (a suite in El Poblado with coworking and gym,
   254k per night, 4.81). The runner-up, with 931, is a coliving room at 108k.

**Gap:** the scraper does not capture guest capacity or area, only the bed/bath text. Adding capacity would
allow price per person, which would likely close much of the gap between fincas and rooms.
