# Domain Pitfalls: Web Scraping / Price Tracking

**Domain:** Competitor price monitoring for Russian e-commerce (askona.ru, ormatek.ru, sonum.ru)
**Researched:** 2026-03-14
**Project:** Lineaf Price Tracker

---

## Critical Pitfalls

Mistakes that cause rewrites, complete data loss, or months of stale data going unnoticed.

---

### Pitfall 1: Assuming Static HTML — All Three Target Sites Render via JavaScript

**What goes wrong:** You write Scrapy spiders using simple HTTP requests and CSS/XPath selectors. The spider runs, returns 200 OK, but the product list is empty or contains only a shell template. The actual product data is injected by JavaScript after the page loads.

**Why it happens:** Modern Russian e-commerce platforms (Askona uses a React-based frontend, Ormatek uses Vue-like rendering, Sonum uses a CMS with JS-rendered catalogs) load catalog data via async API calls after initial HTML delivery. A plain HTTP client sees the un-hydrated HTML skeleton.

**Consequences:** All scraped product counts show zero or a few static items. The pipeline appears to work (no exceptions) but silently captures nothing useful. This is the classic "soft failure" — wrong data that looks valid.

**Prevention:**
- Use `scrapy-playwright` for all three target sites from the start, not as a fallback.
- Before writing any spider, manually check: open browser DevTools → Network tab → reload the catalog page → look for XHR/fetch calls that return JSON product arrays. If you find them, target the API endpoint directly (faster, more reliable than DOM scraping).
- Test with `playwright` in headed mode first to confirm content loads before automating.

**Detection (warning signs):**
- Spider completes in under 2 seconds per page (no JS rendering time).
- Item count extracted is 0 or significantly lower than the visible count on the live site.
- Extracted price fields are `None` or empty strings despite products being visible in the browser.

**Phase mapping:** Scraper foundation phase — must be addressed before writing any production spider.

---

### Pitfall 2: Bot Detection Blocks and IP Bans Without a Recovery Plan

**What goes wrong:** The scraper runs fine for the first few weeks, then Askona or Ormatek's anti-bot system (potentially Cloudflare, or a custom WAF) starts returning 403s, CAPTCHAs, or JavaScript challenge pages. The job silently fails or logs errors that nobody monitors.

**Why it happens:** Repeated requests from the same IP on a fixed weekly schedule create a detectable pattern. Request rate, header fingerprints (missing `Accept-Language`, inconsistent `Referer`, headless browser leaks via `navigator.webdriver`), and user-agent strings all signal automation.

**Consequences:** Data collection stops. Since the failure is often a block returning a valid-looking page (a CAPTCHA page with HTTP 200), the scraper may not raise an exception — it just saves garbage HTML to the database.

**Prevention:**
- Use `playwright-stealth` (or `playwright-extra` with the stealth plugin) to patch headless browser fingerprint leaks from day one.
- Randomize request delays: not a fixed `DOWNLOAD_DELAY` but a range (e.g., 3–8 seconds, uniformly distributed).
- Rotate a realistic User-Agent pool (Chrome on Windows, matching `Accept` header sets).
- For the weekly run frequency of this project, a single residential or Russian datacenter IP is likely sufficient — but have a fallback IP or proxy ready.
- Implement a pre-run validation step: check if the catalog page returns the expected number of items; if not, halt and alert before writing bad data.

**Detection (warning signs):**
- HTTP 403, 429, or 503 in logs.
- Response body contains "checking your browser", "доступ ограничен", or CAPTCHA-related strings.
- Response body size is dramatically smaller than the baseline (~50KB catalog page returning 5KB is suspicious).

**Phase mapping:** Scraper foundation phase — build in stealth from day one. Do not add it as a retrofit.

---

### Pitfall 3: Selector Drift — Site Redesigns Break Scrapers Silently

**What goes wrong:** Three months after launch, Askona pushes a redesign. CSS class names change (e.g., `product-card__price` becomes `price-block__current`), or the catalog URL structure changes (e.g., `/catalog/matrasy/` becomes `/matrasy/`). The scraper continues running and saving `None` values to the database with no alert.

**Why it happens:** CSS class-based selectors are inherently fragile. E-commerce platforms redesign frequently — major Russian retailers do 2–4 frontend updates per year. There is no contract between a scraper and a target site.

**Consequences:** The price history database silently fills with nulls. By the time someone notices (looking at the dashboard and seeing gaps), weeks of history are lost and cannot be recovered.

**Prevention:**
- Prefer structural selectors over class-based ones where possible (e.g., `[itemprop="price"]`, `[data-price]`, JSON-LD structured data in `<script type="application/ld+json">`). These are more stable because they are tied to SEO/schema markup that sites maintain across redesigns.
- Alternatively, target the underlying API endpoint (discovered via DevTools) rather than the rendered DOM. API contracts change less frequently than CSS class names.
- Add a post-extraction validation step: after each scrape run, assert that every extracted item has a non-null, numeric price within a plausible range (e.g., 5,000–300,000 RUB for mattresses). Log and halt if the assertion fails.
- Store the raw HTML/JSON response alongside extracted data during early operation, so you can re-parse historical responses when selectors change.

**Detection (warning signs):**
- Sudden drop in extracted item count (was 45 items, now 0 or 3).
- Price fields returning `None` or empty strings for all items in a run.
- Any run where `null_count / total_count > 0.1` should trigger an alert.

**Phase mapping:** Data pipeline phase and monitoring/observability phase.

---

### Pitfall 4: Silent Cron Job Failures — Stale Data Looks Current

**What goes wrong:** The weekly APScheduler/cron job fails — due to a scraper exception, a network timeout, a server restart on the VM, or a Playwright crash from a memory leak. Nobody is notified. The dashboard continues showing data that is 3 weeks old, presenting it as if it were current. The team makes pricing decisions on stale data.

**Why it happens:** Scheduled jobs don't generate events when they don't run. Traditional monitoring watches for errors; a job that silently doesn't start generates nothing to watch.

**Consequences:** Loss of trust in the tool. Incorrect pricing decisions. The team reverts to manual data collection — defeating the project's purpose.

**Prevention:**
- Implement a "last successful run" timestamp stored in the database. The dashboard must display this prominently (e.g., "Data last updated: 12 days ago" in red if > 8 days).
- Use a dead-man's switch pattern: the scraper POSTs to a healthcheck URL (healthchecks.io or a simple internal endpoint) on successful completion. If no ping arrives within 9 days, send an alert (email or Telegram).
- Log start time, end time, items_scraped, and items_failed for every run to a `scrape_runs` table.
- Wrap the entire scrape job in a try/except that catches all exceptions and writes a FAILED status to `scrape_runs` before re-raising.

**Detection (warning signs):**
- Dashboard shows data older than 8 days.
- No entry in `scrape_runs` table for the expected run window.
- No healthcheck ping received.

**Phase mapping:** Scheduler and deployment phase — build observability into the job before first production run.

---

## Moderate Pitfalls

### Pitfall 5: Fake / Inflated "Original Prices" in Russian Retail

**What goes wrong:** Russian mattress retailers, including Askona and Ormatek, routinely use artificial "strikethrough" pricing: the "original price" (цена до скидки) is inflated and may never have been the real selling price. Scraping both `price_before` and `price_after` and treating the difference as a "real discount" produces misleading analytics.

**Why it happens:** This is a common and legal dark pattern in Russian e-commerce. A "50% off" sale badge may persist for months. The "original" price field exists in the DOM but has no reliable meaning.

**Consequences:** Discount percentage calculations in the dashboard are misleading. The team may incorrectly believe a competitor is running an aggressive temporary promotion when it is a permanent pricing structure.

**Prevention:**
- Store both prices faithfully as scraped — do not compute "true discount" as a KPI.
- In the dashboard, show the `price_after` (effective price) as the primary metric for competitive analysis.
- Track the `price_after` time series, not the discount percentage, to detect genuine price movements.
- Add a note in the dashboard UI warning that "original prices" are not independently verified.

**Detection (warning signs):**
- `price_before` never changes across multiple weekly runs while `price_after` fluctuates.
- Discount percentages above 40% that are stable for more than 4 weeks.

**Phase mapping:** Data modeling phase — define price schema correctly before any data is stored.

---

### Pitfall 6: Product Identity and Name Normalization Across Competitors

**What goes wrong:** Askona sells "Матрас AScona SKY NIGHT 160x200", Ormatek sells "Матрас Ormatek Dream Pro 160×200", and Sonum sells "Соном Комфорт Плюс 160x200". The scraper stores them as three unrelated items. Comparing prices across competitors is impossible without a cross-site product taxonomy.

**Why it happens:** Competitors have their own brand names, SKUs, and product line naming conventions. There is no shared identifier. Mattresses are especially difficult because the same comfort/material tier has different names at each brand.

**Consequences:** The dashboard cannot show "how does our hardness tier X compare to competitors' hardness tier Y at the same price point" — reducing its analytical value to raw price lists rather than strategic insights.

**Prevention:**
- The v1 scope (160x200 only) is correct — don't expand size scope, as it multiplies this problem.
- Define a canonical taxonomy based on scraped attributes: `firmness` (жёсткость), `height` (высота), `price_tier` (price range bucket).
- Do NOT attempt automated cross-brand product identity matching in v1 — it requires NLP and is out of scope. Instead, design the database schema with a `tags` or `attributes` JSON column that enables manual grouping later.
- Scrape structured attribute fields (жёсткость, высота, наполнитель) consistently — these are the cross-site comparison anchors.

**Phase mapping:** Data modeling phase — schema must support attribute-based comparison from day one.

---

### Pitfall 7: Playwright Memory Leaks in Long-Running or Repeated Scrape Jobs

**What goes wrong:** Each weekly scrape run launches a Playwright browser context, scrapes ~50 pages across three sites, and exits. On a VM with limited RAM (e.g., 2GB), Playwright browser processes accumulate, RAM spikes occur on timeout errors, and eventually the job crashes with "JavaScript heap out of memory."

**Why it happens:** Known, reported bugs in `scrapy-playwright` (GitHub issues #240, #325, #19) cause memory to not be fully released, especially on `TimeoutError`. Headless Chromium itself is heavy (~200–400MB per context).

**Consequences:** Scrape jobs crash partway through, leaving incomplete data for that week's run.

**Prevention:**
- Explicitly close browser contexts in a `finally` block after each spider completes.
- Use `PLAYWRIGHT_MAX_CONTEXTS` setting to limit concurrency.
- Set `PLAYWRIGHT_BROWSER_TYPE = "firefox"` as an alternative — Firefox tends to have lower memory footprint than Chromium for scraping.
- For a weekly job with ~150 total pages across three sites, consider running spiders sequentially (one site at a time) with process restarts between them, rather than concurrent contexts.
- Monitor VM RAM usage during test runs before deploying to production.

**Phase mapping:** Infrastructure/deployment phase.

---

### Pitfall 8: Scraping Pagination Incompletely — Assuming One Page Equals Full Catalog

**What goes wrong:** The scraper fetches the first page of the catalog (e.g., 20 items) and treats it as the complete product list. The remaining pages (or lazy-load triggers) are never scraped. The database contains a partial catalog that looks complete.

**Why it happens:** Pagination is often dynamically triggered (infinite scroll, "Load more" button, or URL parameter `?page=2`). If the spider doesn't explicitly handle pagination, it stops at page 1.

**Consequences:** ~20–30% of products are never tracked. Price changes on products on pages 2+ are invisible.

**Prevention:**
- For each target site, manually count the total number of 160x200 mattresses visible on the site and verify the scraper captures the same count.
- Implement pagination explicitly: detect total item count from the first page response, calculate expected page count, and assert that scraped count matches expected count ± 2 items.
- For infinite scroll: use Playwright to scroll to page bottom and wait for new items to load, repeating until no new items appear.

**Phase mapping:** Scraper implementation phase for each target site.

---

## Minor Pitfalls

### Pitfall 9: Price Field Parsing — Russian Locale Formatting

**What goes wrong:** Russian sites format prices as "12 990 ₽" (with a non-breaking space as thousands separator) or "12&nbsp;990". A naive `float(text)` call raises a `ValueError`. A regex that strips regular spaces but not `\xa0` (non-breaking space) silently extracts "12" instead of "12990".

**Prevention:**
- Always strip with `.replace('\xa0', '').replace(' ', '').replace('\u202f', '')` before parsing price strings.
- Assert that parsed prices are > 1000 and < 500000 for mattresses as a sanity check.
- Write a dedicated `parse_price(text: str) -> Optional[int]` utility function used by all spiders.

**Phase mapping:** Scraper implementation phase — write the utility function before any spider extracts prices.

---

### Pitfall 10: Scraping During Maintenance Windows or A/B Tests

**What goes wrong:** The weekly scraper runs at a fixed time (e.g., Monday 03:00). If a target site happens to be in a maintenance window, running an A/B test with a different layout, or serving a regional variant, the scraper captures anomalous data that gets stored as valid.

**Prevention:**
- Randomize the run time within a window (e.g., any time between Monday 02:00 and Monday 10:00).
- Implement a "sanity check" after each run: if fewer than 10 items were scraped from a site that normally returns 30+, mark the run as PARTIAL and do not overwrite the previous week's prices with nulls.
- Never `DELETE` previous records — always `INSERT` new ones with a timestamp. This way a failed run produces no data rather than overwriting good data.

**Phase mapping:** Data pipeline phase.

---

### Pitfall 11: Legal Risk — Terms of Service and Russian Law

**What goes wrong:** The project scrapes publicly available pricing data from competitors. This is generally low-risk in Russia for publicly accessible, non-personal data. However, if scraping causes measurable load on target servers, or if the scraper bypasses an explicit technical restriction (robots.txt disallow, login wall), legal exposure increases.

**Russian legal context:**
- Federal Law No. 149-FZ (on information and IT protection) — scraping that disrupts a site's operation can constitute unauthorized access.
- Federal Law No. 135-FZ (on competition protection) — using scraped data to manipulate prices could theoretically be framed as unfair competition, but this is extreme edge-case for internal analytics use.
- Scraping publicly available prices for internal business analysis has no established enforcement precedent in Russia as of 2025.

**Prevention:**
- Respect `robots.txt` — check each site's `robots.txt` before first run and document findings.
- Keep request rates low (weekly, with 3–8s delays between requests). Never hammer a site.
- Do not store personal data — prices and product specs are not personal data under 152-FZ.
- Keep the tool strictly internal (not a public product). Internal competitive intelligence is standard business practice.
- Do not publish or redistribute scraped data.

**Phase mapping:** Project inception — check robots.txt files during initial site analysis.

---

## Phase-Specific Warning Matrix

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Spider foundation | JS rendering assumption | Use Playwright from day one; detect API endpoints first |
| Spider foundation | Bot detection on first run | Add stealth, random delays, realistic headers before first test |
| Data modeling | Price field ambiguity | Define `price_regular` vs `price_sale` clearly; never compute "real discount" |
| Data modeling | Product identity across sites | Use attribute fields (firmness, height) as comparison anchors, not product names |
| Pipeline | Silent null values | Validate non-null prices post-extraction; halt and alert on failures |
| Pipeline | Price string parsing (RU locale) | Write `parse_price()` utility with `\xa0` handling before any spider |
| Pagination | Incomplete catalog | Count-based assertion: scraped count must match expected count |
| Deployment | Silent cron failures | "Last run" timestamp on dashboard + dead-man's switch healthcheck |
| Deployment | Playwright memory on VM | Sequential spider runs, explicit context cleanup, RAM monitoring |
| Ongoing | Selector drift after redesign | Monitor item count per run; alert on >10% drop |
| Ongoing | Stale data presented as current | Prominent "data age" indicator on dashboard |

---

## Sources

- [Stop Getting Blocked: 10 Common Web-Scraping Mistakes & Easy Fixes](https://www.firecrawl.dev/blog/web-scraping-mistakes-and-fixes) — MEDIUM confidence (WebSearch)
- [The Ultimate Guide to Web Scraping Antibot Systems 2025](https://webautomation.io/blog/ultimate-guide-to-web-scraping-antibot-and-blocking-systems-and-how-to-bypass-them/) — MEDIUM confidence (WebSearch)
- [How to Fix Inaccurate Web Scraping Data: 2026 Best Practices](https://brightdata.com/blog/web-data/fix-inaccurate-web-scraping-data) — MEDIUM confidence (WebSearch)
- [Scrapy memory leak debugging — official docs](https://docs.scrapy.org/en/latest/topics/leaks.html) — HIGH confidence (official)
- [scrapy-playwright RAM spikes on TimeoutError — GitHub issue #325](https://github.com/scrapy-plugins/scrapy-playwright/issues/325) — HIGH confidence (official repo)
- [scrapy-playwright heap out of memory — GitHub issue #19](https://github.com/scrapy-plugins/scrapy-playwright/issues/19) — HIGH confidence (official repo)
- [Парсинг сайтов. Россия и мир — vc.ru legal analysis](https://vc.ru/legal/64328-parsing-saitov-rossiya-i-mir-kak-s-tochki-zreniya-zakona-vyglyadit-odin-iz-samyh-poleznyh-instrumentov) — MEDIUM confidence (WebSearch, Russian legal source)
- [How a silent cron job failure made me build my own monitoring tool](https://dev.to/cronbeats/how-a-silent-cron-job-failure-made-me-build-my-own-monitoring-tool-5gh1) — LOW confidence (WebSearch, illustrative)
- [Data Quality Checklist for Web Scraping: 15-Point Framework](https://tendem.ai/blog/data-quality-checklist-web-scraping) — MEDIUM confidence (WebSearch)
- [9 Web Scraping Challenges and How to Solve Them — Octoparse](https://www.octoparse.com/blog/9-web-scraping-challenges) — MEDIUM confidence (WebSearch)
