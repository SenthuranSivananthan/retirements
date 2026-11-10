# Azure Retirements

A static website for Microsoft Azure retirement announcements. Its Azure-blue palette, Segoe typography, navigation, full-width hero, and light/dark themes follow [Multi-region platform](https://azure.github.io/multi-region-platform/).

Like the [reference project's build](https://github.com/SenthuranSivananthan/multi-region-platform/blob/main/guides/building.md), this project uses a **Python static-site generator** and commits the public website in **`docs`** for GitHub Pages. Python handles building, data refresh, validation, and tests. Browser enhancements use ordinary JavaScript modules; **Node.js, npm, TypeScript, Ruby, Bundler, and Jekyll are not required**.

Every retirement has a complete HTML page with all five planning questions. Content and sidebar navigation work without JavaScript; search, filters, live countdowns, themes, and saved checklists are progressive enhancements.

## Quick preview

Install **Python 3.10 or newer** and Git, then clone the repository. No third-party Python packages are needed just to serve the committed website.

**Windows PowerShell:**

```powershell
git clone https://github.com/SenthuranSivananthan/retirements.git
cd retirements
python -m http.server 8000 --bind 127.0.0.1 --directory docs
```

**Linux:**

```sh
git clone https://github.com/SenthuranSivananthan/retirements.git
cd retirements
python3 -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Open **http://localhost:8000/**. Stop with `Ctrl+C`. Serve over HTTP rather than opening HTML files directly, because browser modules fetch the catalog.

The checked-in catalog supports offline builds and previews. There is no backend, Azure login, API key, or environment file to configure. Installing dependencies requires PyPI access; only an explicit catalog refresh contacts Microsoft.

## Install development dependencies

All commands run from the repository root. The only third-party dependencies are **Jinja2** for HTML templates and **html5lib** for parsing announcement HTML; pip installs their transitive dependencies automatically.

### Windows

1. Install [Git for Windows](https://git-scm.com/downloads/win).
2. Install Python 3.10 or newer from [python.org](https://www.python.org/downloads/windows/), including pip and the option to add Python to `PATH`.
3. Open a new PowerShell window and confirm `git --version` and `python --version` work. If your installation exposes only the Python launcher, use `py -3` instead of `python` when creating the virtual environment.
4. From your checkout, create an isolated environment, install dependencies, and build:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe site\build.py --serve
```

These commands use the virtual environment's interpreter directly; activation and PowerShell execution-policy changes are unnecessary.

### Linux or WSL

On Ubuntu 22.04 or newer, or a current Debian release:

```sh
sudo apt-get update
sudo apt-get install -y git python3 python3-pip python3-venv
python3 --version
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python site/build.py --serve
```

On other distributions, install Git, Python 3.10 or newer, pip, and venv using the distribution's package manager. In WSL, keep the Python interpreter and virtual environment inside WSL rather than mixing Windows and Linux environments.

Both platforms serve the rebuilt site at **http://localhost:8000/**. The server does not watch files: rebuild after source or catalog changes. If `requirements.txt` changes, rerun the pip installation command.

### Commands

The examples below use `python` for an interpreter with the dependencies installed. On Windows, substitute `.\.venv\Scripts\python.exe`; on Linux, substitute `.venv/bin/python` when following the virtual-environment setup above.

| Command | Purpose |
| --- | --- |
| `python -m pip install -r requirements.txt` | Install all build and refresh dependencies |
| `python site/build.py` | Prepare the catalog, render every page into `docs`, copy public assets, and verify the result |
| `python site/build.py --serve` | Rebuild, verify, then serve at `http://localhost:8000/` |
| `python -m http.server 8000 --bind 127.0.0.1 --directory docs` | Preview the existing output without installing dependencies or rebuilding |
| `python -m unittest discover -s tests -v` | Run offline schema, date, source, refresh-protection, and renderer tests |
| `python -m scripts.check_site` | Verify an existing `docs` build against the canonical catalog |
| `python -m scripts.refresh_data` | Fetch the complete official feed while preserving manually enriched records |

### Refresh or enrich the catalog

Refreshing is optional for local development:

```sh
python -m scripts.refresh_data
python -m unittest discover -s tests -v
python site/build.py
```

Edit curated content in **`data/retirements.json`**, not its generated copies. Set `manuallyEnriched: true` when adding answers or custom information. See [Protecting manual enrichments](#protecting-manual-enrichments).

After changing source or data, rebuild and commit **both the source changes and the resulting `docs` changes**. A build does not refresh the source or change the canonical catalog. If a refresh fails, the previous snapshot stays intact; resolve the reported error before retrying.

## Project structure

```text
retirements
  .github\
    workflows\pages.yml     Python validation and scheduled/manual catalog refresh
  site\                     Website source, separate from shared data and tooling
    build.py                Python/Jinja static-site generator and optional server
    config.json             Title, description, production URL, and project base URL
    templates\              Home, retirement, 404, shared layout, macros, and partials
    assets\
      css\style.css         Themes, layout, and responsive styles
      js\                   Maintained browser JavaScript; no compilation required
      data\                 Prepared catalog copy; ignored by Git
    _data\site.json          Prepared view metadata; ignored by Git
  docs\                     Generated public website; intentionally checked in
    .nojekyll               Tells GitHub Pages to serve generated files directly
    index.html
    404.html
    retirements\
      YYYY-MM-DD\<id>\      Detail pages grouped by exact retirement deadline
      unknown-date\<id>\    Detail pages without an exact retirement deadline
    assets\                 Published CSS, JavaScript, and catalog download
  data\
    retirements.json        Canonical, manually enrichable source catalog
  scripts\
    catalog.py              Validation, dates, countdowns, grouping, and preparation
    feed.py                 Source parsing, normalization, pagination, and merging
    refresh_data.py         Refresh entry point and guarded atomic snapshot writer
    check_site.py           Generated page, question, link, and catalog checks
  tests\                    Python unittest suite and offline fixtures
  requirements.txt          Python dependencies
  .gitignore                Dependencies, caches, intermediate files, and local files
  .gitattributes            Marks docs as generated for GitHub review
```

For markup changes, edit `site/templates`; for appearance, edit `site/assets/css/style.css`. Interactive behavior lives in `site/assets/js/main.js`, with browser catalog helpers in `catalog.js` and loading/error reporting in `data.js`. These JavaScript files are maintained source, not generated bundles.

Git ignores `.venv`, Python caches, intermediate metadata, the prepared catalog copy, and temporary refresh files. Recreate them with pip installation and the Python build. Keep the website source, `requirements.txt`, canonical JSON, and generated **`docs`** checked in. `docs` is the deliberate exception to ignoring generated files: it is the GitHub Pages publishing source. Text files use LF line endings for consistent output on Windows and Linux.

## Publish on github.io

1. Build with `python site/build.py`, commit the resulting `docs` together with source changes, and merge into `main`.
2. In **Settings > Pages > Build and deployment**, choose **Deploy from a branch**, select **main**, choose **/docs**, and save. If migrating from the previous setup, change the source from **GitHub Actions**.
3. Open **https://senthuransivananthan.github.io/retirements/** after the native Pages build finishes.

The `docs/.nojekyll` file disables Jekyll processing. GitHub serves the already-generated HTML, CSS, JavaScript, and JSON; it does not install Python dependencies or rebuild templates.

`site/config.json` sets `url` to `https://senthuransivananthan.github.io` and `baseurl` to `/retirements`. Update them for another repository or custom domain, using an empty `baseurl` for a domain-root site. Normal pages use page-relative assets and navigation, supporting both root-level local preview and project-path publishing. The 404 page uses the configured production base path so it works for arbitrary missing URLs.

Each detail has a real static URL shaped like `/retirements/retirements/YYYY-MM-DD/<id>/` on the project site. The first `retirements` is the repository's base path; the date folder is the exact retirement deadline, not the announcement date. Records sharing a deadline keep separate ID folders. Unknown or month-only deadlines use `unknown-date/<id>/` without inventing a day. Rebuilding removes stale generated pages and empty date folders when a deadline changes, while preserving unrelated files.

Filters use ordinary query strings. Existing `#/retirements/<id>` and `#/?...` links redirect to their current static or query-string equivalents, retaining navigation context. On GitHub Pages, the custom 404 page also redirects old flat detail URLs and outdated date folders to the current detail page, preserving query strings and section anchors. These redirects require JavaScript; current detail pages and navigation remain usable without it. Python's basic local HTTP server does not serve the custom 404 page for missing paths.

### Automated refresh

Pull requests and pushes to `main` install Python dependencies, run offline tests, check the committed publishing output, and rebuild from source. They do not fetch announcements or receive write permissions.

Daily at **06:23 UTC**, or through **Actions > Validate site and refresh GitHub Pages > Run workflow**, the main-branch refresh job:

1. Confirms Pages is configured for **main /docs**.
2. Fetches the complete feed, preserving checked-in manual enrichments.
3. Runs tests, rebuilds, and validates the website.
4. Commits changes to `data/retirements.json` and `docs`, then pushes to `main`.
5. Explicitly requests a native Pages build, because pushes made using `GITHUB_TOKEN` do not trigger Pages builds automatically.

The refresh requires `contents: write` and `pages: write`; repository policy and branch protection must allow the bot's normal push. A rejected push or Pages request fails visibly; no force push or protection bypass is attempted. If you prefer local refreshes, disable the scheduled workflow and commit refreshed data and output yourself. Configure Pages before running the automated refresh. A failed fetch, validation, or build does not commit incomplete output.

## Explore and plan

- The home page's blue header banner contains the **Retirement outlook**, showing deadlines already passed this calendar year and cumulative **next 6, 12, and 18 calendar months**. Click a card to view its retirements, or use the **Date window** dropdown: rolling windows come first, followed by every known retirement year, newest first. Year options include month-only deadlines with a confirmed year. Selecting a date window replaces the previous year/window and clears any status shortcut filter. The selection is preserved in shareable URLs and detail-page return links.
- Outlook counts and date ranges update on page load, at UTC date changes, and when returning to the tab. The cumulative 6/12/18-month windows start on the first day of the current UTC month and end on the last day of the month 6/12/18 months ahead, including both endpoints and dates already passed earlier this month. For example, in November 2026 the 6-month window is November 1, 2026 through May 31, 2027. These ranges roll forward when the current month changes. The retired view includes January 1 through yesterday of the current UTC year. Only exact source-backed deadlines count; unknown or month-only dates are excluded. “Retired” describes the deadline, not completion of your migration checklist. Without JavaScript, the outlook reflects the last build.
- Search titles and announcement text; combine service, date-window, and Azure-category filters. Status views remain available through sidebar shortcuts, with a visible status label and clear link instead of a Status dropdown. Sort by announcement date, retirement date, or title, and load more results.
- Expand the sidebar by **retirement year > Azure service category > retirement**. Years appear newest first, then **Unconfirmed year**. Each year and category also links to its filtered directory.
- On desktop, the sidebar starts directly beneath the top toolbar, beside the blue header banner, and stays pinned while the page scrolls.
- Share filtered URLs, download the complete JSON catalog, or use header search from any page (`Ctrl+K` or `Cmd+K`).
- On small screens, use the navigation button. Click the backdrop or press Escape to close the menu.
- Jump between the five detail sections using **In this article**. Checklists and theme preferences are saved only in the current browser; the app has no analytics.

Each detail shows whole days remaining until an exact retirement date using UTC calendar days. Deadlines today say **Retires today (0 days remaining)**; past dates say **Retired**. Unknown or month-only deadlines show **Retirement date to confirm** without inventing a countdown. Python renders the build-time value; JavaScript updates it on page load and when the UTC date changes.

Every retirement detail keeps these sections in order:

1. **What is changing?**
2. **What do I need to do?**
3. **Where, and how much, am I impacted?**
4. **What is the deadline?**
5. **How can I track progress?**

Checklist progress is per announcement and browser-local. It is not a tenant assessment or a shared migration tracker.

## Data provenance and limitations

### Question-organized JSON

The canonical catalog and download use `schemaVersion: 2`. Each record keeps its ID, title, services, Azure categories, announcement date (`announcedOn`), last-updated date (`lastUpdatedOn`), summary, source URL, and enrichment flag as metadata. Answers live under exactly five `questions` keys:

| Key | Organized content |
| --- | --- |
| `what` | Official announcement text and separate financial considerations |
| `actions` | Nullable official recommended action, planning guidance, announcement resources, and support |
| `impact` | Inventory guidance, impact checklist, tenant-access limitations, and Azure Advisor |
| `deadline` | Nullable exact `date`, source `month`, uncertainty, and consequences |
| `progress` | Planning guidance, checklist steps, and browser-storage limitations |

Every section contains its complete `question` and `introduction`. Templates read the headings and answers from prepared JSON, not a second UI-specific set. Preparation and browser loading reject missing or malformed sections. Source content is distinguished from general advice; tenant-specific impact and actual team progress are never inferred.

`lastUpdatedOn` is the UTC calendar date from Microsoft's per-announcement `modified` timestamp, displayed as **Last updated**. It is not the publication date, deadline, or retrieval time. Missing timestamps produce `null` and **Not provided by source**; malformed timestamps fail refresh. Catalog-level `retrievedAt` records when the complete feed was fetched.

`categories` comes from official `productCategories`, not guessed service names. Multi-category announcements appear under each applicable category but count once in directory totals. Missing categories, including on older protected records, use **Uncategorized** without modifying the record.

Navigation uses the exact deadline's year, otherwise the stated year of a valid source month, otherwise **Unconfirmed year**. It never uses the announcement year or invents an exact date from a month.

### Protecting manual enrichments

Every retirement has a boolean `manuallyEnriched`, initially `false`. When editing answers or adding custom information, set **`"manuallyEnriched": true`** and commit the JSON. Both automated and local refreshes preserve the entire protected record, including custom fields and its recorded `lastUpdatedOn`, even if the source removes that ID.

Unflagged records continue to refresh; new announcements use `false`. Set the flag back to `false` to resume source updates, replacing custom content on the next successful refresh. Keep all five sections and valid field types when enriching records.

The refresh reads the existing snapshot after fetching, incorporating edits saved during the fetch. Invalid flags, duplicate IDs, malformed snapshots, and detected concurrent publishing edits fail instead of overwriting local data. Publishing uses a temporary file and atomic replacement. Changes made only to generated output are not durable.

### Official source

The source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)). Refresh fetches every page tagged `Retirements`, checks the reported count and unique IDs, and replaces the snapshot only after a complete fetch. Source IDs remain stable in detail URLs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap, and endpoint changes cause refresh to fail rather than silently publishing an incomplete directory.

The structured feed supplies a retirement **month**, not an exact day. Exact dates are extracted conservatively from current announcement **titles** only when a single distinct, valid date appears. ISO dates require explicit deadline wording to distinguish deadlines from API versions. Publication dates, IDs, URL slugs, and body dates are never used as deadlines. Month-only or ambiguous deadlines remain **Date to confirm** and do not count as upcoming or retired. **Within 90 days** includes today and day 90 UTC; **Upcoming** includes that group.

Announcement HTML is parsed into plain text, with related HTTPS links retained separately. The app escapes source text instead of rendering source HTML. Each page links to the official announcement; verify tenant-specific impact, pricing, support, and phased deadlines with Microsoft.
