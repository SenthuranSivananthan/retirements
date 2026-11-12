---
description: Maintain, build, and verify the Azure Retirement Catalog website.
---

Change/rebuild the site here; use `retirement-enrichment.prompt.md` for catalog work.

## Architecture and sources of truth

- Python/Jinja static site with maintained browser JavaScript, CSS and templates. No TypeScript, JS build system, backend or new dependencies without an explicitly requested architecture change.
- Source: `data\retirements.json`, `site\templates`, `site\assets`, `scripts\catalog.py`, `site\build.py`. `docs` is generated publication output, never hand-edited; `site\_data` and `site\assets\data` are ignored generated artifacts.
- Pipeline stores: `data\pipeline\{raw,extracted,web_cache,canonical,manual}.sqlite`. Builds read automatic-plus-manual exported JSON, never the stores; no build-time refresh. Manual fields override supplied paths, not whole records; `manuallyEnriched` is deprecated.
- Inspect templates/helpers/tests/README; preserve patterns and make the smallest requested change.

## Product and interface requirements

- Match [Multi-region platform](https://azure.github.io/multi-region-platform/): Azure-blue palette, Segoe type, navigation/hero, responsive desktop/mobile and light/dark themes. Home title/heading: **Azure Retirement Catalog**.
- Use `style.css` relative typography tokens: .875rem body/controls/code/navigation/metadata/notices/footer, 1.6 line height; 1rem subheadings, 1.125rem section headings/counts, 1.375rem titles. Only timeline lead-time captions use .75rem `--text-caption`; dates/detail lead times stay body-sized. No extra small-print/mobile overrides: wrap/reflow, use spacing/weight/color, retain monospace code and browser text scaling.
- Keep `scripts\catalog.py`'s five-question schema/key grouping; display deadline, what, actions, impact, progress. Preserve citations/uncertainty. Align Python/browser validation: matching Azure Updates, applicable Learn or verified first-party Tech Community may support deadlines; guidance/tracking retain stricter rules.
- Enrichment supplies `html` for all five answers; render sanitized fragments with escaped plain fallback. Keep plain/rich facts aligned, semantic paragraphs/lists/headings/`br`, no visible literal `\n`/`\\n` or duplicated separately rendered dates/notices/support/Advisor/guidance.
- Use `sanitize_question_html`: only `p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, `br`; reject attributes/comments/unsupported/malformed markup. Escape text/catalog fields; never render raw announcement HTML.
- Progress shows rich/tracking guidance and optional source link; otherwise exactly "Tracking guidance is not available for this retirement." No legacy checklists/browser-saved progress claims.
- Keep official announcement and **References** from reviewed sources/action resources, with exclusions, redirects and safe destination deduplication. **Open Microsoft Learn guidance** is last in actions, after content and all support guidance/links.
- Timeline: category > service > retirement, unique counts, descending exact deadlines (unknown last), deterministic title ties. Sidebar: retirement year > category > retirement; directory counts/links reflect all active filters beside **By retirement year**. Details show the complete visible tree, highlight/expand current record and use unfiltered browse links; only the return link keeps incoming filters.
- Search/filters combine through query strings/history/return links. Labels: **Retirement window**; **Announcement year**, using `announcedOn`, current UTC year plus three previous, newest first, `Announced in <year>`.
- Outlook uses exact dates: cumulative 6/12/18-month windows include the entire current UTC month through target-month end; retired-this-year is January 1 through yesterday. Exclude unknown/month-only dates.
- Lead time = deadline minus announcement in calendar years/months/days: clamp month addition to valid month-end, retain negatives, omit zero units, missing exact dates => `Not calculable`. Show under timeline date, in detail facts and yellow countdown pill.
- Core pages, answers, sidebar and initial timeline work without JS; search/filter/countdown/theme are enhancements. Preserve escaping/safe URLs.
- Routes use exact deadline or `unknown-date`, then title slug. Python/JS generate matching safe length-limited slugs; append `--<record-id>` only for duplicate slugs across the full catalog, including hidden records. Preserve unambiguous legacy-ID/stale-date redirects, queries and anchors; builds never infer dates from titles/announcement timestamps.

## Build and verification

Use Python 3.10+ from the root; install missing dependencies with `python -m pip install -r requirements.txt`. For rendering/behavior changes:

```sh
python -m unittest discover -s tests -q
python site/build.py
python -m scripts.check_site
```

Build prepares metadata, renders home/404/all details, copies assets and validates. Stage details outside `docs`, then replace the complete detail tree to remove stale routes while preserving unrelated output. Commit generated changes with source.

Add focused regression tests: rich/plain/unsafe HTML for rendering changes, JS source behavior and generated static fallbacks for client changes, matching Python/browser results and expected pages/local links. Report only checks actually run.

For layout/type changes inspect home/detail/404, light/dark, desktop/mobile and enlarged text: computed token sizes, labels/menus, wrapping/overflow. Rebuild shared CSS output.

## Scope and completion

- No unrelated catalog edits, hand-edited output or schema/refresh/workflow-permission/publishing changes beyond the request. Shared-source rebuilds may update many pages.
- Commit/push/PR/merge only when requested. Report changed files/behavior, actual validation and remaining limitations.
