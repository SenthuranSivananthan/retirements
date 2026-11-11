---
description: Maintain, build, and verify the Azure Retirement Catalog website.
---

Use this prompt to change or rebuild the website. For evidence-based catalog enrichment, use `retirement-enrichment.prompt.md` instead.

## Architecture and sources of truth

- This is a static website generated with Python and Jinja2. Browser enhancements are maintained JavaScript modules; CSS and templates are source files. Do not introduce TypeScript, a JavaScript build system, a backend, or new dependencies unless the user explicitly requests an architecture change.
- `data/retirements.json` is the canonical catalog. `site/templates`, `site/assets`, `scripts/catalog.py`, and `site/build.py` are the site source. `docs` is generated publishing output and must not be edited by hand.
- Keep the prepared files under `site/_data` and `site/assets/data` generated; they are ignored local build artifacts.
- A catalog refresh is separate from a site build. Do not fetch or change retirement data unless the user asks; consult `retirement-enrichment.prompt.md` for catalog review and refresh rules.
- Inspect existing templates, helpers, tests, and README before changing behavior. Make the smallest change that satisfies the request and preserve current patterns.

## Product and interface requirements

- Keep the Azure-blue palette, Segoe typography, navigation, hero, and light/dark theme consistent with [Multi-region platform](https://azure.github.io/multi-region-platform/). Preserve responsive desktop and mobile layouts.
- The home page browser title and main heading are **Azure Retirement Catalog**.
- Every record uses the five-question catalog schema validated in `scripts/catalog.py`. Detail pages display the deadline question first, followed by what changes, required actions, impact, and progress. Keep the question content grouped under those schema keys and preserve source citations and uncertainty.
- The home page is a retirement timeline grouped by service category, then service, then retirement. Preserve unique result counts, deadline-descending order, and deterministic title ordering for equal or unknown dates.
- The sidebar groups records by retirement year, Azure category, and retirement. It shows the unique count for the active filters beside **By retirement year**, and updates year/category counts and links with active filters.
- Keep search and filters combinable and shareable through query strings, browser history, and detail-page return links. The date filter is labeled **Retirement window**. The **Announcement year** filter uses `announcedOn` and offers the current UTC calendar year plus the previous three, newest first, labeled `Announced in <year>`.
- The outlook uses exact retirement dates only. Cumulative 6/12/18-month windows include the full current UTC month through the last day of the target month. The retired-this-year window is January 1 through yesterday. Unknown and month-only dates are excluded from exact-date windows.
- Customer lead time is retirement date minus announcement date, displayed as calendar years, months, and days. Clamp dates to the last valid day when adding calendar months; preserve negative durations, omit zero units, and show `Not calculable` when either exact date is missing. Show it below the retirement date in the main timeline, in the detail facts, and in a yellow pill in the detail countdown banner.
- Keep core pages, five answers, sidebar navigation, and the initial timeline available without JavaScript. Treat search, filtering, countdown updates, and theme controls as progressive enhancements. Escape catalog content and preserve safe URL handling.
- Detail URLs use the exact deadline as `retirements/YYYY-MM-DD/<id>/`; unknown or month-only dates use `retirements/unknown-date/<id>/`. Do not infer an exact date from an announcement date or title.

## Build and verification

Run commands from the repository root with Python 3.10 or newer. Install dependencies only if needed:

```sh
python -m pip install -r requirements.txt
python -m unittest discover -s tests -q
python site/build.py
python -m scripts.check_site
```

`site/build.py` prepares metadata from the canonical catalog, renders the home page, 404 page, and every detail page, copies public assets, and validates the result. It stages detail pages outside `docs`, then recreates the complete `docs/retirements` tree to prevent stale or orphaned routes; unrelated files elsewhere in `docs` must be preserved. Commit generated `docs` changes with their source changes.

Add focused tests for new behavior in the existing suite. Test client-side behavior at its JavaScript source and static fallbacks through generated markup; keep corresponding server-rendered and browser behavior consistent. Run the tests, build, and `scripts.check_site` after changes that affect rendering or behavior. Ensure the build completes with the expected detail pages and local links. Do not claim validation that did not run.

## Scope and completion

- Do not rewrite or reformat unrelated catalog records or generated pages. Do not change the five-question schema, data-refresh policy, workflow permissions, or publishing configuration unless required by the user’s request.
- Do not commit, push, create or update a pull request, or merge unless explicitly requested.
- Report the files and user-visible behavior changed, plus the actual test/build/check results and any remaining limitation.
