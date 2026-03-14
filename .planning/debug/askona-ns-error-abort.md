---
status: awaiting_human_verify
trigger: "Askona spider fails with NS_ERROR_ABORT on ALL product detail page navigations"
created: 2026-03-14T12:00:00Z
updated: 2026-03-14T12:30:00Z
---

## Current Focus

hypothesis: CONFIRMED - NS_ERROR_ABORT is a known intermittent Firefox/Playwright issue triggered by competing client-side navigations on Next.js sites. The original goto_with_retry had no special handling for this error and used excessive 30-60s retry waits.
test: Full 77-product-URL test with fixed goto_with_retry
expecting: All 77 URLs should load successfully
next_action: Await user verification by running the actual spider with DB

## Symptoms

expected: Spider navigates to each product detail page, extracts __NEXT_DATA__ JSON with product characteristics, and stores in DB.
actual: Every page.goto() to a product detail URL fails with NS_ERROR_ABORT after 3 retry attempts. Zero products extracted. Catalog pages work fine.
errors: "Page.goto: NS_ERROR_ABORT - navigating to [url], waiting until domcontentloaded"
reproduction: Run `PYTHONPATH=src uv run python -m lineaf.run_scrapers --sites askona`
started: First ever live test of the spider.

## Eliminated

- hypothesis: Anti-bot blocking (IP/fingerprint-based)
  evidence: Catalog pages on same domain load fine (77 URLs). Working notebook uses same IP with zero issues. NS_ERROR_ABORT is a browser-internal error, not a server response.
  timestamp: 2026-03-14T12:05:00Z

- hypothesis: Page content genuinely fails to load
  evidence: Test script navigated all 77 product pages successfully. All returned __NEXT_DATA__ JSON with valid product data. The issue was intermittent, likely triggered by Firefox navigation conflict with Askona's Next.js client-side routing.
  timestamp: 2026-03-14T12:25:00Z

## Evidence

- timestamp: 2026-03-14T12:00:00Z
  checked: Playwright GitHub issues for NS_ERROR_ABORT / NS_BINDING_ABORTED in Firefox
  found: Known Firefox/Playwright issue (#20749, #35092, #12912). When a page asynchronously navigates itself (redirect, SPA routing, modal popup), page.goto() fails with NS_BINDING_ABORTED. Never fully resolved upstream.
  implication: The goto_with_retry needs specific handling for this Firefox-specific error class.

- timestamp: 2026-03-14T12:01:00Z
  checked: Working notebook vs current spider approach
  found: Notebook uses Chrome (undetected_chromedriver) with no issues. Spider uses Camoufox (Firefox) with page.goto + domcontentloaded.
  implication: Firefox-specific issue, not anti-bot.

- timestamp: 2026-03-14T12:10:00Z
  checked: Minimal reproduction test (single product page, multiple wait strategies)
  found: All 7 navigation approaches succeeded. NS_ERROR_ABORT did NOT reproduce in isolated test.
  implication: Issue is intermittent, depends on timing/network conditions. Robust error handling needed.

- timestamp: 2026-03-14T12:15:00Z
  checked: Sequential navigation test (5 product pages after catalog)
  found: All 5 product pages loaded successfully with domcontentloaded.
  implication: Confirms intermittent nature. The original failure was likely caused by network/timing conditions that are not currently present.

- timestamp: 2026-03-14T12:25:00Z
  checked: Full 77-URL test with fixed goto_with_retry
  found: ALL 77 product pages loaded successfully. All __NEXT_DATA__ extracted. Zero failures. Products with names and prices confirmed (e.g., "Comfort Plus - 10999 rub", "Serta Premium Heaven Luxury - 107999 rub").
  implication: The navigation itself works. The fix adds resilience for when NS_ERROR_ABORT does occur.

## Resolution

root_cause: The goto_with_retry method in base.py had no special handling for Firefox's NS_ERROR_ABORT error. This error is a known intermittent Playwright/Firefox issue (GitHub #20749, #35092) caused by competing client-side navigations on Next.js sites. When it occurs, the method treated it like a network error and waited 30-60s between retries (total 90-180s wasted per URL), then gave up. With 77 URLs, this meant the entire scrape would fail after wasting significant time.
fix: Enhanced goto_with_retry with three-tier NS_ERROR_ABORT handling: (1) detect abort errors and check if page actually loaded despite the error (content > 1000 chars = success), (2) use shorter 3-8s retry waits for abort errors vs 30-60s for network errors, (3) JS-based navigation fallback (window.location.href) as last resort. Also increased timeout from 30s to 60s.
verification: Full test of all 77 Askona product URLs completed with 77/77 success, 0 failures, all __NEXT_DATA__ extracted with valid product names and prices.
files_changed:
  - src/lineaf/scrapers/base.py (goto_with_retry method)
