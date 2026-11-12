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
- Use the four primary typography tokens in `site/assets/css/style.css`: .875rem body and controls (14px by default), 1rem subheadings (16px), 1.125rem section headings and summary counts (18px), and 1.375rem page titles (22px). Keep relative units to respect browser font preferences. Navigation, labels, metadata, cards, notices, code, and footers share the body size and 1.6 line spacing. The only caption-size exception is the main timeline's customer lead-time label and duration, using `--text-caption` at .75rem (12px); keep retirement dates and detail-page lead times at body size. Do not introduce other small-print or mobile font-size overrides. Use weight, spacing, and color for supporting hierarchy, keep code monospace, and let controls and labels wrap or reflow rather than shrinking text.
- The home page browser title and main heading are **Azure Retirement Catalog**.
- Every record uses the five-question catalog schema validated in `scripts/catalog.py`. Detail pages display the deadline question first, followed by what changes, required actions, impact, and progress. Keep the question content grouped under those schema keys and preserve source citations and uncertainty.
- Keep Python and browser review validation aligned: deadline evidence may cite the record's matching Azure Updates announcement, Microsoft Learn, or a verified first-party Tech Community article, while Learn guidance and progress tracking retain their stricter source rules.
- Each of `questions.what`, `questions.actions`, `questions.impact`, `questions.deadline`, and `questions.progress` may contain an `html` fragment alongside its plain-text fields; enrichment supplies it for all five. Render each fragment as structured HTML, not escaped markup text, and retain the existing escaped plain-text fallback when it is absent. Preserve paragraphs, lists, headings, and `<br>` line breaks rather than displaying literal `\n` or `\\n` as text. Keep the rich content consistent with the plain-text claims and preserve separately displayed dates, notices, support and Advisor links, and guidance links without duplicating them.
- Validate and render question fragments through `sanitize_question_html` in `scripts/catalog.py`. Allow only `p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, and `br`; reject attributes, comments, unsupported tags, and malformed markup. Escape text nodes and other catalog text, and never render raw announcement HTML.
- For progress, display the tracking guidance or its rich-content replacement and link to the tracking source when available. Otherwise display "Tracking guidance is not available for this retirement." Do not display legacy progress checklists.
- Keep the official announcement link and the **References** list. Build the list from reviewed sources and action resources, honor exclusions and reviewed redirects, and deduplicate safe destinations.
- When a Learn guidance source is available, render **Open Microsoft Learn guidance** as the final element of the actions section, after all rich/plain answer content, support guidance, and support links. Keep this order in the shared template for every detail page.
- The home page is a retirement timeline grouped by service category, then service, then retirement. Preserve unique result counts, deadline-descending order, and deterministic title ordering for equal or unknown dates.
- The sidebar groups records by retirement year, Azure category, and retirement. On the directory page, show the unique count for active filters beside **By retirement year** and update year/category counts and links with those filters. On detail pages, show the complete visible catalog tree regardless of incoming query filters, highlight and expand the current retirement, and use unfiltered year/category navigation contexts so users can browse other retirements. Preserve incoming filters only for the return-to-directory link.
- Keep search and filters combinable and shareable through query strings, browser history, and detail-page return links. The date filter is labeled **Retirement window**. The **Announcement year** filter uses `announcedOn` and offers the current UTC calendar year plus the previous three, newest first, labeled `Announced in <year>`.
- The outlook uses exact retirement dates only. Cumulative 6/12/18-month windows include the full current UTC month through the last day of the target month. The retired-this-year window is January 1 through yesterday. Unknown and month-only dates are excluded from exact-date windows.
- Customer lead time is retirement date minus announcement date, displayed as calendar years, months, and days. Clamp dates to the last valid day when adding calendar months; preserve negative durations, omit zero units, and show `Not calculable` when either exact date is missing. Show it below the retirement date in the main timeline, in the detail facts, and in a yellow pill in the detail countdown banner.
- Keep core pages, five answers, sidebar navigation, and the initial timeline available without JavaScript. Treat search, filtering, countdown updates, and theme controls as progressive enhancements. Escape catalog content and preserve safe URL handling.
- Detail URLs use `retirements/YYYY-MM-DD/<title-slug>/`, or `retirements/unknown-date/<title-slug>/` for unknown or month-only dates. Derive matching safe, length-limited slugs from titles in Python and JavaScript; append `--<record-id>` only for duplicate title slugs across the full catalog, including hidden records. Preserve unambiguous redirects from legacy ID URLs and outdated date folders, including query strings and anchors. Use the catalog's structured deadline instead of inferring a date from the announcement date or title during the site build.

## Build and verification

Run commands from the repository root with Python 3.10 or newer. If dependencies are missing, install them with `python -m pip install -r requirements.txt`. For changes affecting rendering or behavior, run:

```sh
python -m unittest discover -s tests -q
python site/build.py
python -m scripts.check_site
```

`site/build.py` prepares metadata from the canonical catalog, renders the home page, 404 page, and every detail page, copies public assets, and validates the result. It stages detail pages outside `docs`, then recreates the complete `docs/retirements` tree to prevent stale or orphaned routes; unrelated files elsewhere in `docs` must be preserved. Commit generated `docs` changes with their source changes.

Add focused tests for new behavior in the existing suite. Cover rich HTML and plain-text fallbacks, including rejection of unsafe markup, when changing question rendering. Test client-side behavior at its JavaScript source and static fallbacks through generated markup; keep corresponding server-rendered and browser behavior consistent. Ensure the build completes with the expected detail pages and local links. Do not claim validation that did not run.

For typography or layout changes, inspect the home, detail, and 404 pages in light and dark themes at desktop and mobile widths. Check computed sizes against the shared scale, readable labels and menus, wrapping, and horizontal overflow, including enlarged browser text. Rebuild to synchronize the generated stylesheet with its source.

## Scope and completion

- Do not make unrelated catalog changes or edit generated pages by hand; rebuilding may update many pages when shared site sources change. Do not change the five-question schema, data-refresh policy, workflow permissions, or publishing configuration unless required by the user’s request.
- Do not commit, push, create or update a pull request, or merge unless explicitly requested.
- Report the files and user-visible behavior changed, plus the actual test/build/check results and any remaining limitation.
