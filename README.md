# Azure Retirements

A static website for Microsoft Azure retirement announcements. Its Azure-blue palette, Segoe typography, navigation, full-width hero, and light/dark themes follow [Multi-region platform](https://azure.github.io/multi-region-platform/).

Like the [reference project's build](https://github.com/SenthuranSivananthan/multi-region-platform/blob/main/guides/building.md), this project uses a **Python static-site generator** and commits the public website in **`docs`** for GitHub Pages. Python handles building, data refresh, validation, and tests. Browser enhancements use ordinary JavaScript modules; **Node.js, npm, TypeScript, Ruby, Bundler, and Jekyll are not required**.

Every retirement has a complete HTML page with all five planning questions. Content and sidebar navigation work without JavaScript; search, filters, live countdowns, and themes are progressive enhancements.

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

Edit curated content in **`data/retirements.json`**, not its generated copies. Set `manuallyEnriched: true` only when the record must be protected from refresh. See [Protecting manual enrichments](#protecting-manual-enrichments).

After changing source or data, rebuild and commit **both the source changes and the resulting `docs` changes**. A build does not refresh the source or change the canonical catalog. If a refresh fails, the previous snapshot stays intact; resolve the reported error before retrying.

## Project structure

```text
retirements
  .github\
    workflows\pages.yml     Python validation and scheduled/manual catalog refresh
    prompts\retirement-enrichment.prompt.md  Reusable evidence-review task; not a schedule
    prompts\site-build.prompt.md             Reusable site development and build instructions
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
      YYYY-MM-DD\<title-slug>\   Detail pages grouped by exact retirement deadline
      unknown-date\<title-slug>\ Detail pages without an exact retirement deadline
    assets\                 Published CSS, JavaScript, and catalog download
  data\
    retirements.json        Canonical, manually enrichable source catalog
  scripts\
    catalog.py              Validation, dates, countdowns, grouping, and preparation
    feed.py                 Source parsing, normalization, pagination, and merging
    refresh_data.py         Refresh entry point and guarded atomic snapshot writer
    review_data.py          Review coverage, source-evidence checks, and guarded batch edits
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

Each detail has a real static URL shaped like `/retirements/retirements/YYYY-MM-DD/<title-slug>/` on the project site. The first `retirements` is the repository's base path; the date folder is the exact retirement deadline, not the announcement date. Unknown or month-only deadlines use `unknown-date/<title-slug>/` without inventing a day. Slugs use normalized, lowercase title text, capped at 80 characters. When multiple records have the same title slug, each gets a `--<record-id>` suffix; the title portion may be shortened further for filesystem limits. IDs remain unchanged in the catalog. Every build recreates the entire generated `docs/retirements` tree from the catalog, removing stale pages, renamed folders, and orphaned files while preserving unrelated files elsewhere in `docs`.

Filters use ordinary query strings. Existing `#/retirements/<id>` and `#/?...` links redirect to their current static or query-string equivalents, retaining navigation context. On GitHub Pages, the custom 404 page also redirects old ID-based detail URLs and outdated date folders when the record can be identified unambiguously, preserving query strings and section anchors. These redirects require JavaScript; current detail pages and navigation remain usable without it. Python's basic local HTTP server does not serve the custom 404 page for missing paths.

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

- The home page's blue header banner contains the **Retirement outlook**, showing deadlines already passed this calendar year and cumulative **next 6, 12, and 18 calendar months**. Click a card to view its retirements, or use the **Retirement window** dropdown: rolling windows come first, followed by every known retirement year, newest first. Year options include month-only deadlines with a confirmed year. The separate **Announcement year** filter offers this calendar year and the previous three, matching `announcedOn`. Retirement-window and announcement-year filters can be combined and are preserved in shareable URLs and detail-page return links.
- Outlook counts and date ranges update on page load, at UTC date changes, and when returning to the tab. The cumulative 6/12/18-month windows start on the first day of the current UTC month and end on the last day of the month 6/12/18 months ahead, including both endpoints and dates already passed earlier this month. For example, in November 2026 the 6-month window is November 1, 2026 through May 31, 2027. These ranges roll forward when the current month changes. The retired view includes January 1 through yesterday of the current UTC year. Only exact source-backed deadlines count; unknown or month-only dates are excluded. “Retired” describes the deadline, not completion of a migration. Without JavaScript, the outlook reflects the last build.
- The directory is a vertical timeline grouped by **service category > individual service > retirements**. Categories and services are alphabetical; entries within each service are ordered by exact retirement deadline descending (furthest future first), with unknown or month-only dates last. Equal dates are ordered by title. Records with multiple categories or services appear in each applicable group, while result counts and pagination count unique retirements.
- Search titles and announcement text; combine **Category**, **Service**, **Retirement window**, and **Announcement year** filters. Each retirement shows customer lead time directly below its retirement date in the timeline, calculated from the exact retirement and announcement dates and displayed in calendar years, months, and days; missing exact dates are shown as not calculable. Detail pages repeat the value in a yellow pill in the countdown banner and in the retirement facts. Category includes every catalog category and an **All categories** option. Service choices narrow to the selected category; changing categories keeps a compatible service selection or resets it to **All services**. Selecting **All categories** restores the full service list. Selected category and service filters also restrict the timeline headings and persist in shared URLs, browser history, and detail-page return links. Status views remain available through sidebar shortcuts, with a visible status label and clear link instead of a Status dropdown. Load more results without changing the timeline's descending deadline order. The initial timeline is rendered in HTML and remains available without JavaScript.
- Expand the sidebar by **retirement year > Azure service category > retirement**. Years appear newest first, then **Unconfirmed year**. On the directory page, the tree follows all active filters, including category, service, retirement window, announcement year, status, and search; empty branches disappear. The **By retirement year** heading shows the unique filtered retirement count; year and category counts also reflect all matching retirements, independent of timeline pagination. Directory sidebar links retain the active filter context. Detail pages always show the complete visible catalog tree, highlight and expand the current retirement, and let you browse other retirements without inheriting directory filters. Their return-to-directory link still preserves the incoming filters. The complete tree remains available without JavaScript.
- Use **Reset filters** to clear search, category, service, retirement year/window, announcement year, and shortcut status filters, remove filter query parameters, restore all service options and sidebar branches, and return to the initial timeline results.
- On desktop, the sidebar starts directly beneath the top toolbar, beside the blue header banner, and stays pinned while the page scrolls.
- Share filtered URLs, download the complete JSON catalog, or use header search from any page (`Ctrl+K` or `Cmd+K`).
- On small screens, use the navigation button. Click the backdrop or press Escape to close the menu.
- Jump between the five detail sections using **In this article**. Theme preferences are saved only in the current browser; the app has no analytics.

Each detail shows whole days remaining until an exact retirement date using UTC calendar days. Deadlines today say **Retires today (0 days remaining)**; past dates say **Retired**. Unknown or month-only deadlines show **Retirement date to confirm** without inventing a countdown. Python renders the build-time value; JavaScript updates it on page load and when the UTC date changes.

Every retirement detail keeps these sections in order:

1. **What is the deadline?**
2. **What is changing?**
3. **What do I need to do?**
4. **Where, and how much, am I impacted?**
5. **How can I track progress?**

When available, **Open Microsoft Learn guidance** is the final element in **What do I need to do?**, after all migration content, support guidance, and support links. The shared detail template applies this order to every retirement page.

The progress section shows specific Microsoft Learn or verified first-party Tech Community guidance for identifying or tracking affected resources when available; otherwise it says tracking guidance is unavailable in the catalog. It does not assess a tenant or track migrations. Previously saved browser checklists are not displayed or deleted.

## Data provenance and limitations

### Question-organized JSON

The canonical catalog and download use `schemaVersion: 2`. Each record keeps its ID, title, services, Azure categories, announcement date (`announcedOn`), last-updated date (`lastUpdatedOn`), summary, source URL, and enrichment flag as metadata. Answers live under exactly five `questions` keys:

| Key | Organized content |
| --- | --- |
| `what` | Announcement text or source-backed change summary, and separate financial considerations |
| `actions` | Nullable official recommended action, planning guidance, announcement resources, and support |
| `impact` | Inventory guidance, impact checklist, tenant-access limitations, and Azure Advisor |
| `deadline` | Nullable exact `date`, source `month`, uncertainty, and consequences |
| `progress` | Optional `tracking` object with documented guidance and its cited Learn or verified first-party Tech Community `sourceUrl`; legacy checklist fields remain for compatibility but are not displayed |

Every section contains its complete `question` and `introduction`. The JSON key order remains unchanged; detail pages and their article navigation display `deadline` first. Templates read the headings and answers from prepared JSON, not a second UI-specific set. Preparation and browser loading reject missing or malformed sections. Source content is distinguished from general advice; tenant-specific impact and actual team progress are never inferred.

`announcedOn` is the UTC calendar date from Microsoft's per-announcement `created` timestamp, displayed as **Announced**; it records when the announcement was published. Missing values remain `null`, and dates are not inferred from announcement text. `lastUpdatedOn` is the UTC calendar date from Microsoft's per-announcement `modified` timestamp, displayed as **Last updated**. It is not the publication date, deadline, or retrieval time. Missing timestamps produce `null` and **Not provided by source**; malformed timestamps fail refresh. Catalog-level `retrievedAt` records when the complete feed was fetched.

`categories` comes from official `productCategories`, not guessed service names. Multi-category announcements appear under each applicable category but count once in directory totals. Missing categories, including on older protected records, use **Uncategorized** without modifying the record.

Navigation uses the exact deadline's year, otherwise the stated year of a valid source month, otherwise **Unconfirmed year**. It never uses the announcement year or invents an exact date from a month.

### Protecting manual enrichments

Every retirement has a boolean `manuallyEnriched`, initially `false`. To protect answers or custom information from refresh, set **`"manuallyEnriched": true`** and commit the JSON. Both automated and local refreshes preserve the entire protected record, including custom fields and its recorded `lastUpdatedOn`, even if the source removes that ID.

Each record also has a `hidden` boolean, initially `false`. Set it to `true` to exclude that retirement from search, navigation, filters, and visible counts; the direct detail page and public JSON download remain accessible, so this is not an access-control feature. Feed refresh preserves the flag for matching records. Older records without the field are treated as visible.


Unflagged records continue to refresh; new announcements use `false`. Set the flag back to `false` to resume source updates, replacing custom content on the next successful refresh. Keep all five sections and valid field types when enriching records.

Review metadata is independent of refresh protection: a reviewed record can have either flag value. A successful feed refresh replaces an unprotected record, including its review metadata and curated answers, or removes it if it is absent from the feed.

The refresh reads the existing snapshot after fetching, incorporating edits saved during the fetch. Invalid flags, duplicate IDs, malformed snapshots, and detected concurrent publishing edits fail instead of overwriting local data. Publishing uses a temporary file and atomic replacement. Changes made only to generated output are not durable.

### Evidence-based content reviews

The [enrichment prompt](.github/prompts/retirement-enrichment.prompt.md#pipeline-entry-point) defines the repeatable 12-stage pipeline, including files read/written at each stage: baseline and mode selection, discovery/merging, batch planning, source reading, evidence mapping, deadline reconciliation, five-question synthesis, readable HTML, factual review, guarded integration, full-output validation, and an authorized publication handoff. Design-only, full enrichment, date-only corrections, and readability-only passes have distinct mutation and research limits. A single integrator applies guarded batches. The current implementation adds the [incremental SQLite stages](#incremental-sqlite-stages) and a single Azure Front Door (classic) pilot; whole-feed discovery, hash-ID migration and automation remain outside that pilot.

Source reviews keep all answers under the existing five questions and add record-level **`sourceReview`** metadata. Integrate relevant announcement details into those answers and state verified facts directly instead of repeatedly saying that Microsoft Learn confirms them; retain attribution where needed to explain conflicts or uncertainty. Detail pages collect answer sources and announcement resources in **References** after the five questions, with duplicate destinations listed once. Evidence notes and per-question source mappings remain in the JSON. Reviewed redirects are used for reference links without changing the original resource URLs in the catalog. State uncertainty and conflicts in the answers and retain them in review metadata; the UTC content-review day is visible. The original announcement remains in the catalog as preserved evidence. The review day does not change `lastUpdatedOn` or catalog `retrievedAt`.

For reviewed resources, visit the public destination and use its actual page title instead of labels such as "Learn more", "here", or "instructions"; publisher branding may be omitted. Before removing a locale segment from a `learn.microsoft.com` URL, verify that the locale-free URL reaches the same intended public documentation. If it is inaccessible but the locale-based URL works, keep the locale-based URL. Apply a successful replacement consistently to the resource URL, its `resourceChecks.url` and `resolvedUrl`, and source/guidance/deadline/tracking URLs; preserve query parameters, fragments, and API-version selectors, and leave the original announcement snapshot unchanged. If normalization makes multiple resource URLs identical, retain one descriptive resource and one matching check while preserving distinct evidence details. Preserve URLs from other hosts. Do not invent titles from URL slugs or treat error/sign-in page titles as documentation titles. Keep a descriptive support label for sign-in-only resources and report unavailable destinations in `resourceChecks`. Unreviewed announcements may retain feed-provided labels until reviewed.

- `status` is `enriched` for every completed review of a visible record, including when some source questions remain unresolved. It means the five-question record was reviewed and organized, not that every fact was independently verified; explain uncertainty and conflicts in the answers and preserve supporting details in review metadata. Do not use `needs-review`. Hidden records are skipped and left unchanged.
- Visible manual-only records are included in the review queue. Their batches may add `sourceReview` metadata but must leave the existing summary, answers, and custom fields unchanged.
- `sources` records descriptive titles, resolved HTTPS URLs, supported question keys in `sections`, and factual evidence notes. The record's official Azure Updates announcement is authoritative for what it explicitly announces. Microsoft Learn product documentation is authoritative for product behavior, API details, and applicable retirement dates. Microsoft Tech Community blog posts authored by Microsoft or the responsible product team are authoritative for retirement-specific facts they directly cover. Community Q&A, training, generic directories, personal or third-party posts, and authenticated portals are not substitutes.
- Optional `guidanceSource` selects a relevant Microsoft Learn product-documentation URL already cited for `actions`. The actions button links to it as Microsoft Learn guidance; it is omitted when no suitable page has been reviewed. Subsequent batches retain the selection unless explicitly changed or set to null.
- Optional `excludedReferences` records confirmed nonexistent source or resource URLs with `url`, UTC `checkedOn`, and `httpStatus` (404 or 410). They are omitted from References while preserving the original evidence. Recheck exclusions during review; do not treat access restrictions or temporary failures as proof a page is gone.
- `resourceChecks` accounts for every distinct original announcement resource, with `read`, `partial`, `unavailable`, or `not-evidence`, nullable `resolvedUrl`, and a reason. Known support/community links can be classified without claiming they were read. Reading a page does not mean every statement in it was confirmed.
- `originalAnnouncement` and `originalDeadline` preserve the initial feed evidence. Professional summaries replace the displayed raw scrape, not the retained source text.
- Review the announcement's title and description and relevant Microsoft Learn documentation for explicit retirement dates for the same product, scope, and lifecycle milestone; verified first-party Tech Community posts can also provide dates. If conflicting explicit dates for that same scope and milestone span strictly less than 7 calendar days (1-6 days from earliest to latest), choose the earliest, even when another applicable Learn page gives a later date. Keep the alternative dates, stated times/time zones, and citations in the deadline explanation and review metadata, explaining this as a conservative selection rather than a source-reconciled date. For example, August 31, 2024 versus September 1, 2024 selects August 31, 2024, with the exact date and any month set consistently. The tolerance does not apply to month-only dates, different scopes or milestones, or a chain of nearby dates spanning 7 days or more.
- Otherwise, use an unambiguous, current Learn retirement date as authoritative when it differs from the announcement, and explain the discrepancy without claiming an extension unless explicitly documented. Unresolved conflicts between Learn dates and unclear scope or milestones remain unconfirmed; when no applicable Learn date exists, unresolved conflicts among non-Learn sources also remain unconfirmed. Exactly 7 days is outside the tolerance. Cite the chosen exact date in `sourceReview.sources` for `deadline` and set `deadlineSource` to the same Learn, verified Tech Community, or record-matching official Azure Updates URL; the latter accepts the original or locale-prefixed announcement URL. Historical deadlines and migration instructions are labeled as historical, not presented as still-available actions.

Inspect coverage and a resumable batch without network access or file changes:

```shell
python -m scripts.review_data --limit 20
```

The report includes a whole-catalog SHA-256 guard, reviewed/enriched/unreviewed counts, unresolved issues, and candidate IDs. Approximately one fifth of a batch rechecks the oldest reviews; the rest advances unreviewed records in catalog order. Existing manual enrichments without `sourceReview` are counted separately and excluded from automated edits.

Prepare a temporary JSON object with `catalogSha256` from the report and a `reviews` array. Each entry contains `id`, `summary`, `questions` (all five section keys, with changed answer fields only), and `sourceReview` (review date/status/issues, sources, resource checks, and nullable `deadlineSource`). Do not supply the two original-evidence fields; the command captures them automatically and preserves them on subsequent reviews. Apply and rebuild:

```shell
python -m scripts.review_data --apply <review-batch.json>
python -m unittest discover -s tests -q
python site/build.py
python -m scripts.check_site
```

The application command is a guarded editor, **not an autonomous web crawler or summarizer**. It validates every update before publishing any, rejects stale batches and concurrent edits, and preserves unrelated records, feed timestamps, and the existing `manuallyEnriched` flag. It cannot prove the semantic accuracy of a citation; actual page reading and human review remain necessary. Changes to checked-in `docs` must accompany catalog changes.

### Incremental SQLite stages

Four local databases under `data\pipeline` are versioned in Git. SQLite is self-contained and queryable with Python or SQLite tools, but its Git diffs are binary. The fifth stage exports the existing application JSON schema:

```text
Public sources -> raw.sqlite -> extracted.sqlite --+
                     |                            |
                     +-> links.sqlite ------------+-> canonical.sqlite -> retirements.json -> site build
                            cached evidence             reviewed answers
```

| Database | Stored data |
| --- | --- |
| `raw.sqlite` | Exact Azure Updates item-response bytes and the selected Lifecycle index, source IDs/URLs/hashes, and associations to retirement IDs. |
| `extracted.sqlite` | Per-source observations and original identities, announcement text/resources, provisional dates, source-body hashes and extractor version. |
| `links.sqlite` | Original link references, skipped portal reasons, cached public bodies, actual destinations, content hashes, HTTP validators and visible failure state. |
| `canonical.sqlite` | Complete catalog baseline/order/metadata, unchanged curated five-question records, joined source/link provenance and reviewed input fingerprints. |

`seed` imports the current complete catalog unchanged, without network access. The scoped stages process only the requested retirement, so the current pilot has one two-source observation set and one approved canonical target; the other 633 canonical records are baseline copies, not newly enriched records. Existing IDs, manual/hidden flags, custom fields, original evidence and feed timestamps are retained. The raw/extracted data does not silently replace reviewed answers or adjudicate dates.

Run stages independently from the repository root. This PowerShell example uses the same Front Door retirement:

```powershell
$id = 'azure-front-door-classic-will-be-retired-on-31-march-2027'
python -m scripts.pipeline seed
python -m scripts.pipeline ingest --id $id --lifecycle-url https://learn.microsoft.com/lifecycle/end-of-support/end-of-support-2027
python -m scripts.pipeline extract --id $id
python -m scripts.pipeline links --id $id
python -m scripts.pipeline canonical --id $id
```

Inspect the extracted observations, cached pages, canonical record and the reported `inputSha256`/`recordSha256`. After actually reviewing those exact inputs, approve them using both reported fingerprints:

```powershell
python -m scripts.pipeline canonical --id $id --accept-review --input-sha256 <reviewed-input-hash> --record-sha256 <reviewed-record-hash>
python -m scripts.pipeline export
python site\build.py
python -m scripts.pipeline status
```

For new answer edits, use the existing review-batch shape with the canonical catalog hash from `status`, but run `python -m scripts.pipeline review --batch <batch.json>`. This reuses the guarded review editor against the database, preserving original evidence. Refresh links if references changed, then reassemble, review/approve and export. Database review does not itself export, download evidence or invent answers. Existing JSON-only review commands remain supported outside this workflow; external JSON edits or daily feed refreshes after seeding can conflict with the database and must be reconciled, never overwritten automatically.

Link refresh uses conditional GET: ETag takes precedence, otherwise Last-Modified. It reuses raw-source responses already acquired by `ingest`, rather than downloading them again; use ingest to refresh those sources. A 304 reuses the cached body and makes no database write; identical 200 responses retain bodies without invalidating downstream stages. When a server supplies no usable validator, a full GET and content-hash comparison is unavoidable. Dynamic HTML can change even when visible article text appears unchanged; changed bodies conservatively require review. Response headers alone, Content-Length and URL age do not establish that content is unchanged. The cache stores public bytes, not proof that evidence has been read or verified through Microsoft Learn MCP.

Extraction skips unchanged source hashes and extractor versions. Changed body hashes invalidate canonical approval; metadata-only validator changes do not. Failed checks preserve last-known-good bodies but remain visible and block promotion. Missing stages, changed references, stale approvals and concurrent JSON edits stop export. Repeated unchanged runs leave database and JSON bytes unchanged. The full catalog is exported deterministically from the canonical database, not rebuilt from raw snippets; a missing JSON can be recreated from it.

Only approved public Microsoft HTTPS endpoints are downloaded, with public-address/redirect checks, bounded size/time/retries, and no credentials, tenant access or recursive crawling. Support and Advisor portals are classified without downloading. A directory `.lock` serializes writers; a crashed process can leave a lock that must be inspected before explicitly removing it. SQLite uses DELETE journaling and connections are closed before Git operations. The databases are tracked; lock/journal/WAL/SHM sidecars are ignored. Do not text-merge binary database conflicts or automatically discard either side.

The pilot does not implement full Lifecycle navigation discovery, arbitrary-source ingestion, automatic cross-source consolidation, hash-ID allocation, scheduling or publication. Those remain the separately gated design below. The legacy `scripts.refresh_data` command/workflow is unchanged and does not use these databases.

### Weekly Copilot cloud automation

The reusable task is [`.github/prompts/retirement-enrichment.prompt.md`](.github/prompts/retirement-enrichment.prompt.md). Its proposed full-run design discovers Azure-related retirements from Azure Updates and Microsoft Lifecycle independently, merges a common baseline once, then reviews every visible retirement across evidence-first batches of at most 80 distinct public documentation pages. Whole-feed multi-source discovery and its data pull remain deferred and require separate authorization; the SQLite pilot ingests only selected existing records, and the legacy refresh command remains Azure Updates-only. Resuming a run must not repeat discovery. Date-only and readability-only passes reuse reviewed evidence without a feed refresh or new source research. The prompt specifies per-question citations, bounded retries, preservation rules, validation, and source/merged coverage reporting. Azure Updates `created` timestamps populate `announcedOn`; Lifecycle-only records must not invent an announcement date.

**No cloud automation has been created or enabled.** The repository capability check reported cloud automations disabled and management unavailable to the current account. The prompt does not schedule work, grant tools, or bypass that restriction; the existing daily GitHub Actions feed refresh remains unchanged.

Once cloud automation access is available, review a single personal automation for this repository. Discover the service's supported tools/triggers and grant only public-document retrieval, repository reading/editing, and required execution capabilities. Choose the weekly day/time in UTC through the service's structured schedule fields; do not embed schedule/permissions in the task prompt. Creation, activation, and any initial run require separate approval. Publication behavior is also pending approval: the draft leaves a reviewable diff and does not authorize pushing, opening PRs, or merging.

Daily feed refresh replaces unprotected reviewed records with feed content; protected records remain unchanged and require separate checks of current documentation and announcements. Before any approved publication, reconcile with the latest main-branch feed snapshot and regenerate `docs`; never force-push over a concurrent refresh.

### Parallel discovery design (not implemented)

The [proposed common-baseline contract](.github/prompts/retirement-enrichment.prompt.md#proposed-parallel-discovery-and-common-baseline-contract) permits **only these two sources for retirement discovery and identity matching**:

| Source | Discovery entry point | Planned coverage |
| --- | --- | --- |
| Azure Updates | [Official JSON collection](https://www.microsoft.com/releasecommunications/api/v2/azure) filtered to `Retirements` | Every validated page, preserving official source IDs and timestamps. |
| Microsoft Lifecycle | [Lifecycle hub](https://learn.microsoft.com/lifecycle/) and [official navigation index](https://learn.microsoft.com/en-us/lifecycle/toc.json) | Dynamically discovered annual retirement/end-of-support indexes, including Additional Azure Changes; Azure-related entries only, with product/version/scope/milestone retained. Published years are not hard-coded. |

Other Microsoft Learn documentation and verified Microsoft/product-team Tech Community posts may support enrichment, including deadlines, migration, impact, and tracking. They cannot introduce a retirement, establish its discovery eligibility, or prove a cross-source match. Linked or redirected guides do not expand the two-source restriction; Microsoft Lifecycle means Lifecycle pages, not the whole Learn host.

The [identity-matching rules](.github/prompts/retirement-enrichment.prompt.md#retirement-identity-and-matching) compare product/component, SKU/version, region/cloud, affected population, and milestone using evidence from the two allowed sources. Different titles and URLs can describe one retirement; identical titles or dates can describe different events. Missing scope is not a wildcard, and partial overlap is not equivalence. Record each comparison as confirmed-match, distinct, or unresolved with its source evidence. Confirmed observations share a canonical retirement ID while retaining all original source IDs, titles, and URLs; unresolved matches stay separate. A retirement need not appear in both sources.

The [hash-ID design](.github/prompts/retirement-enrichment.prompt.md#hash-based-retirement-ids) assigns every canonical retirement `ret-` plus a full 64-character SHA-256 digest of a versioned, canonical identity seed, not its titles, URLs, or dates. For a true digest collision between different seeds, keep the existing ID and append the first unused numeric suffix to the new one: `ret-<hash>-2`, `ret-<hash>-3`, and so on. Persist frozen seeds, full allocated IDs, and reservations in a proposed catalog-level `identityRegistry`; reuse assignments and never recycle suffixes when records disappear. Keep original source identities and old catalog IDs as aliases. SHA-256 is collision-resistant, not mathematically collision-free; unresolved event identity is still a review blocker, not a reason to append a suffix or falsely merge. Exact serialization, suffix allocation, atomic registry updates, and alias/route compatibility require implementation and offline validation before use.

The first combined baseline must preserve all existing enriched answers, dates, review metadata, flags, and custom fields while adding new discoveries and non-destructive provenance. Existing IDs stay unchanged until an explicitly approved hash-ID migration; stage proposed mappings in run-local `id-map.json` first. Migration may change only approved identity/alias metadata, including on protected records, while retaining old IDs as working aliases. Otherwise protected records remain unchanged in full; existing curated duplicates are flagged for review rather than automatically consolidated. Assigned hash IDs remain stable when dates change or Azure Updates later discovers the event. A mainstream-to-extended-support transition is not a retirement, and an index's update date is not an item's announcement date.

Stage 6 follows the ordered [retirement-date decision rules](.github/prompts/retirement-enrichment.prompt.md#retirement-date-decision-rules): match the exact event, read explicit first-party evidence, account for documented extensions, select the earliest applicable date for conflicts spanning 1-6 days, otherwise prefer an unambiguous current Learn deadline, preserve unknown/month-only precision, and keep the result consistent and cited. Discovery dates are provisional; stages 9 and 11 verify the decision, including the exactly-seven-day boundary and unresolved conflicts.

Proposed catalog/record `discoverySources` metadata will retain per-source URLs, observations, dates, identities, and coverage separately from reviewed `sourceReview.sources`. All new records still use the existing five question objects. Both required sources must complete before a guarded, atomic baseline replacement; failures leave the canonical snapshot intact. Python/browser validators, provenance round trips, review handling, accurate source labels, and offline fixtures must be implemented before an approved whole-feed combined run. The selected-record SQLite extractor is not a full Lifecycle discovery adapter and does not change legacy refresh behavior or enable a schedule.

### Official source (current implementation)

The source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)). Refresh fetches every page tagged `Retirements`, checks the reported count and unique IDs, and replaces the snapshot only after a complete fetch. Source IDs remain unchanged in the catalog and disambiguate duplicate title slugs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap, and endpoint changes cause refresh to fail rather than silently publishing an incomplete directory.

The structured feed supplies a retirement **month**, not an exact day. For unreviewed records, exact dates are extracted conservatively from current announcement **titles** only when a single distinct, valid date appears. ISO dates require explicit deadline wording to distinguish deadlines from API versions. Automatic refresh does not infer deadlines from publication dates, IDs, URL slugs, or announcement descriptions. Reviewed deadlines may instead use explicit retirement-specific dates from the announcement's title or description, Microsoft Learn, or a verified first-party Tech Community article as described above. Month-only and unresolved deadlines remain **Date to confirm** and do not count as upcoming or retired. **Within 90 days** includes today and day 90 UTC; **Upcoming** includes that group.

Announcement HTML is parsed into plain text, with related HTTPS links retained separately. The app escapes source text instead of rendering source HTML. When answers are content-enriched, authors add an `html` fragment in each of the five question objects; legacy and protected manual-only records may omit it and use the plain-text fallback. The builder allows only semantic formatting tags (`p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, and `br`), rejects attributes and active content, and escapes text nodes. Lead with the main point, use short single-topic paragraphs, meaningful subheadings for complex answers, unordered lists for independent points, and ordered lists only for sequences. Preserve substantive facts and limitations without repeating separately rendered dates, notices, support, or tracking messages. Convert line breaks or literal newline escapes to paragraph boundaries or `<br>`. Each page links to the official announcement; verify tenant-specific impact, pricing, support, and phased deadlines with Microsoft.

Site-wide typography uses four primary sizes: .875rem body text and controls (14px at the default browser size), 1rem subheadings (16px), 1.125rem section headings and summary counts (18px), and 1.375rem page titles (22px). Navigation, filters, cards, notices, metadata, and footers use the same body size and 1.6 line spacing on desktop and mobile. The only caption-size exception is the main timeline's customer lead-time label and duration at .75rem (12px); retirement dates and detail-page lead times retain the body size. Relative units respect browser font preferences. Headings retain their hierarchy, and semantic emphasis, code fonts, and notice colors remain distinct.
