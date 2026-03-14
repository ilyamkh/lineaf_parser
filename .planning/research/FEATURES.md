# Feature Landscape

**Domain:** Competitor price monitoring / price tracking (internal tool, mattress retail)
**Project:** Lineaf Price Tracker
**Researched:** 2026-03-14
**Scope:** Monitoring 160x200 mattress prices on askona.ru, ormatek.ru, sonum.ru

---

## Context: What This Tool Is

An internal dashboard for Lineaf brand team. Not a SaaS product sold to external customers.
This constrains which commercial-product features are relevant: no need for multi-tenant user
management, billing, MAP enforcement, or marketplace integrations. The audience is a small
internal team making weekly pricing decisions.

---

## Table Stakes

Features users expect. Missing = tool feels broken or untrustworthy.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Current price per product | Core value of any price tracker | Low | Both "price before discount" and "price after discount" — Russian retailers heavily use promotional pricing |
| Price history per product | Without it, you can't see trends or seasonality | Medium | Requires storing every scrape run, not just the latest |
| Competitor comparison view | See Lineaf's position relative to Askona/Ormatek/Sonum simultaneously | Medium | Table or chart grouping same-tier mattresses across brands |
| New / removed product detection | Assortment shifts matter as much as price shifts | Medium | Flag when a SKU appears or disappears from a competitor's catalog |
| Scheduled automatic collection | Manual scraping defeats the purpose; weekly cadence required | Medium | Cron-based job; must run reliably unattended |
| Product attributes alongside prices | Firmness, height, filler, cover material determine comparability | Low | Already specified in project requirements — without these, price comparison is apples-to-oranges |
| Historical data persistence | Users must be able to look back weeks/months | Medium | PostgreSQL with timestamp-keyed rows per scrape run |
| Basic filtering / sorting | Filter by competitor, sort by price, filter by firmness | Low | Without this, a 50-row table is unusable |
| Last-updated timestamp | Users must know how fresh the data is | Low | Show when each site was last successfully scraped |
| Error visibility | Know when a scrape failed vs. when data is genuinely unchanged | Low | Distinguish "no data" from "price unchanged" |

---

## Differentiators

Features that go beyond minimum and create genuine analysis value. Not expected day one,
but worth planning for.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Price delta highlighting | Color-code or flag products where price changed since last run | Low | Easy win: red/green for up/down; drives immediate attention to what matters |
| Price index (relative position) | Show Lineaf's price as % of each competitor's price for comparable tier | Medium | Requires mapping Lineaf products to competitor equivalents; powerful for positioning decisions |
| Discount depth tracking | Track discount % separately from absolute price — Russian retailers run aggressive promos | Low | Store (original_price - sale_price) / original_price as a derived column |
| Trend charts per product | Line chart showing price over time for a specific model | Medium | Plotly/Chart.js in frontend; very useful for seasonal pattern spotting |
| Side-by-side attribute comparison | For two selected models (one per brand), show all attributes in a table | Medium | Helps answer "is their cheaper product actually comparable?" |
| Export to Excel/CSV | Team already works in Excel; export is a bridge between the tool and existing workflows | Low | Simple endpoint returning CSV; reduces friction for management reporting |
| Assortment overview | Count of SKUs per competitor per scrape run — detect when a brand expands or shrinks lineup | Low | Aggregate query on top of existing data |
| Search / text filter | Find a specific model name quickly | Low | Client-side filter on the dashboard table |

---

## Anti-Features

Things to deliberately NOT build in v1. These are present in commercial products but are
wrong for this context.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Telegram / email alerts | Explicitly out of scope per PROJECT.md; adds infrastructure complexity | Keep it in backlog; pull-model dashboard is sufficient for weekly review |
| Dynamic pricing automation | Lineaf needs to make human decisions, not automated repricing | Surface data clearly; let humans decide |
| Product matching / AI deduplication | Askona/Ormatek/Sonum sell their own branded products — there are no cross-site "same SKU" matches to make | Track per-brand catalog independently; no matching needed |
| MAP / MSRP violation tracking | Lineaf is monitoring competitors, not enforcing its own MAP | Irrelevant to use case |
| Multi-currency support | All three sites sell in RUB | Unnecessary complexity |
| Multi-user roles / permissions | Small internal team, no access control needed in v1 | Single shared login or no auth for internal network deploy |
| Marketplace integrations (Wildberries, Ozon) | Out of scope; sites are direct brand stores | Add in future milestone if needed |
| Scraping other mattress sizes | Only 160x200 per PROJECT.md | Parameterize the query so adding sizes later is easy |
| Mobile app | Web dashboard is sufficient; team works on desktop | Responsive layout is nice-to-have, not required |
| Reprice recommendations / AI insights | Adds ML complexity; team wants data not advice | Present clean data; team applies judgment |

---

## Feature Dependencies

```
Scheduled scraper run
  └── Raw price + attribute data stored in DB
        ├── Current price view (requires: latest run per product)
        ├── New/removed product detection (requires: diff between runs)
        ├── Price history (requires: multiple runs stored)
        │     └── Trend charts (requires: price history)
        ├── Discount depth tracking (requires: both original + sale price stored)
        │     └── Price index / relative position (requires: Lineaf reference data)
        ├── Basic filtering/sorting (requires: current price view)
        │     └── Search / text filter (same)
        └── Export CSV (requires: current price view or history)
```

Key dependency: **everything downstream depends on the scraper running reliably and storing
complete, timestamped records.** The scraper is the foundation; the dashboard is secondary.

---

## MVP Recommendation

Prioritize in this order:

1. **Scraper for all three sites** — correct field extraction (model, price_original, price_sale, firmness, height, filler, cover, weight_per_sleeping_place) with run timestamp
2. **Price history persistence** — append-only records; never overwrite
3. **New / removed product detection** — compare current run's SKU set to previous run
4. **Current prices dashboard** — table view with filtering and last-updated timestamp
5. **Price delta highlighting** — color-code changes since last run (high value, low effort)
6. **Trend charts** — line chart per product over time

Defer to post-MVP:
- Export to CSV (useful but not urgent; team can query DB directly at first)
- Discount depth as a separate column (can be computed from stored fields anytime)
- Price index / relative positioning (requires Lineaf product catalog mapping, which is external work)
- Side-by-side attribute comparison (nice-to-have; table view partially covers this)

---

## Domain-Specific Notes for Russian Mattress Retail

**Promotional pricing is pervasive.** Askona, Ormatek, and Sonum frequently show large
"before discount" prices alongside sale prices. Tracking only sale_price misses important
context about promotional strategy. Both fields are required. (MEDIUM confidence — based on
known Russian retail patterns and the existing Excel sample in the project which includes both
price columns.)

**Product names are not standardized across brands.** Askona's "Dreamline Luxe" is not
comparable to Ormatek's "Grand Comfort" by name. Comparability must be inferred from
attributes (firmness, height, filler) — which is why attribute tracking is table stakes, not
optional. (HIGH confidence — confirmed by mattress industry research showing brands
deliberately obfuscate cross-brand comparison.)

**Anti-bot risk is low for three known, fixed URLs.** Scraping one catalog page per
competitor per week is far below thresholds that trigger enterprise anti-bot systems.
Respectful rate limiting (2–5 second delays between requests) and a realistic user-agent are
sufficient. No need for proxy rotation or CAPTCHA services at this scale. (MEDIUM confidence —
no specific data found on askona.ru/ormatek.ru bot protection; this is a reasonable inference
from scale and frequency.)

---

## Sources

- [Prisync competitor price tracking features](https://prisync.com/competitor-price-tracking/)
- [Price2Spy feature comparison page](https://www.price2spy.com/feature-comparison.html)
- [Top 8 Price Monitoring Tools for Brands & Retailers — Price2Spy Blog](https://www.price2spy.com/blog/top-price-monitoring-tools/)
- [Competera competitive data monitoring](https://competera.ai/competitive-data-price-monitoring)
- [Best Price Monitoring Software 2026 — Pricelysis](https://pricelysis.com/blog/best-price-monitoring-software-2026)
- [Price monitoring software assortment tracking — Altosight](https://altosight.com/features/)
- [How to Build Pricing Dashboards — Monetizely](https://www.getmonetizely.com/articles/how-to-build-pricing-dashboards-kpis-and-metrics-that-actually-matter)
- [Mattress name comparison and cross-brand confusion — GoodBed](https://www.goodbed.com/guides/mattress-name-comparison/)
