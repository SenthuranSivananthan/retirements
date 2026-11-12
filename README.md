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

Keep automatic research in the canonical database and user-provided content in `manual.sqlite`; export their composition to **`data/retirements.json`**, never edit generated copies. See [Protecting manual enrichments](#protecting-manual-enrichments).

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
    pipeline\               Versioned raw.sqlite, extracted.sqlite, web_cache.sqlite, canonical.sqlite, manual.sqlite
  scripts\
    catalog.py              Validation, dates, countdowns, grouping, and preparation
    feed.py                 Source parsing, normalization, pagination, and merging
    refresh_data.py         Refresh entry point and guarded atomic snapshot writer
    review_data.py          Review coverage, source-evidence checks, and guarded batch edits
    pipeline.py             Independent SQLite stages, conditional web cache, guarded JSON export
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

Catalog/download retain `schemaVersion: 2`, ID/title/services/categories, announcement/update dates, summary and source URL. The obsolete `manuallyEnriched` flag is removed; optional `manualEnrichment.fields` lists supplied override paths. Answers use exactly five `questions` keys:

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

Provide the retirement and manual content; resolve its unique existing ID and store supplied fields separately in **`data\pipeline\manual.sqlite`**. Manual values override only matching fields at export; automatic research remains available underneath. Objects merge recursively, arrays replace, explicit nulls remain null. Whole-record protection via `manuallyEnriched` is no longer used.

Each record also has a `hidden` boolean, initially `false`. Set it to `true` to exclude that retirement from search, navigation, filters, and visible counts; the direct detail page and public JSON download remain accessible, so this is not an access-control feature. Feed refresh preserves the flag for matching records. Older records without the field are treated as visible.


Manual batches use `catalogSha256` from `python -m scripts.pipeline status`:

```json
{"catalogSha256":"<reported composed hash>","overrides":[{"id":"<existing-id>","fields":{"questions":{"impact":{"guidance":"<user-provided content>"}}}}]}
```

Apply with `python -m scripts.pipeline manual --batch <manual-batch.json>`, then `export` and `python site/build.py`. Use the same `--db-dir`/`--output` options as the target pipeline. `fields: null` removes an override and restores automatic values. Identity/timestamps/visibility use their normal workflows, not content overrides. Custom content and citation fields are supported; HTML/resources/dates must pass existing validation. A plain answer change without matching HTML discards stale HTML and uses the plain fallback.

Automatic reviews use `status.automaticCatalogSha256`, never composed manual data. Export records supplied field paths as provenance; it does not claim user content was independently researched. Refresh reapplies overrides and retains their baseline for feed-absent records. Manual edits/research remain separate and neither silently overwrites the other.

`python -m scripts.pipeline migrate` removes legacy flags offline, preserving flagged content as manual overrides. The checked-in migration changed no retirement facts. JSON-only review refuses composed output. External JSON refreshes can still conflict with the canonical DB's export guard and need reconciliation; invalid data and concurrent edits fail without overwriting snapshots.

### Evidence-based content reviews

The [enrichment prompt](.github/prompts/retirement-enrichment.prompt.md#pipeline-entry-point) is the authoritative 12-stage design, with per-stage inputs/outputs and four modes: design/testing, full enrichment, date-only corrections and readability-only. SQLite stages are implemented for selected records; whole-feed discovery, parallel orchestration and hash-ID migration remain proposed.

Reviews organize automatic answers under five questions and add **`sourceReview`**: actual UTC day, `enriched` status, issues, sources and checks. This means reviewed/organized, not proof of every claim. Preserve uncertainty, original evidence and timestamps. Hidden content is untouched; automatic workers cannot write manual overrides.

Use the [evidence rules](.github/prompts/retirement-enrichment.prompt.md#authoritative-sources-and-evidence) and [review contract](.github/prompts/retirement-enrichment.prompt.md#apply-validate-and-report) for full field/URL requirements: read actual destinations, use real titles, verify Learn locale normalization, preserve selectors/original snapshots, account for every resource, and exclude references only after confirmed 404/410. `guidanceSource` selects Learn documentation cited for actions; `deadlineSource` must match cited applicable deadline evidence. References deduplicate reviewed sources/resources and use reviewed redirects; citation details remain in JSON.

The [seven ordered date rules](.github/prompts/retirement-enrichment.prompt.md#retirement-date-decision-rules) require matching event/scope/milestone and explicit first-party evidence. Exclude superseded dates only with documented extensions. A full conflict span of **1-6 days selects the earliest**, even over later Learn evidence; exactly seven days and longer chains do not qualify. Otherwise prefer an unambiguous current applicable Learn deadline; unresolved conflicts stay unconfirmed. Preserve month-only precision, alternatives, times/time zones and rationale; never claim Microsoft reconciled a conservative selection. Keep structured date/month, answers and citations consistent.

Inspect coverage and a resumable batch without network access or file changes:

```shell
python -m scripts.review_data --limit 20
```

The report includes a catalog SHA-256 guard, review counts/issues and candidate IDs. About one fifth rechecks oldest reviews; the rest advances unreviewed records. Database reviews use the automatic hash from pipeline status; manual overlays are not research.

Prepare a temporary JSON object with `catalogSha256` from the report and a `reviews` array. Each entry contains `id`, `summary`, `questions` (all five section keys, with changed answer fields only), and `sourceReview` (review date/status/issues, sources, resource checks, and nullable `deadlineSource`). Do not supply the two original-evidence fields; the command captures them automatically and preserves them on subsequent reviews. Apply and rebuild:

```shell
python -m scripts.review_data --apply <review-batch.json>
python -m unittest discover -s tests -q
python site/build.py
python -m scripts.check_site
```

The editor validates batches atomically, rejects stale/concurrent changes and preserves unrelated records/timestamps. It is not a crawler or proof of citation accuracy. JSON-only review is for catalogs without composed overrides; use pipeline review/manual/export when databases own the catalog. Keep checked-in `docs` synchronized.

### Incremental SQLite stages

Five Git-versioned SQLite stores under `data\pipeline` support incremental stages; their diffs are binary. JSON is the composed output:

```text
Public sources -> raw.sqlite -> extracted.sqlite --+
                     +-> web_cache.sqlite --------+-> canonical.sqlite --+
User-provided fields -----------------------------> manual.sqlite -------+-> JSON -> build
```

| Database | Stored data |
| --- | --- |
| `raw.sqlite` | Exact Azure Updates item-response bytes and the selected Lifecycle index, source IDs/URLs/hashes, and associations to retirement IDs. |
| `extracted.sqlite` | Per-source observations and original identities, announcement text/resources, provisional dates, source-body hashes and extractor version. |
| `web_cache.sqlite` | Downloaded public bodies, original references/destinations, content hashes, HTTP validators, portal skips and failures. |
| `canonical.sqlite` | Complete catalog baseline/order/metadata, unchanged curated five-question records, joined source/link provenance and reviewed input fingerprints. |
| `manual.sqlite` | User-provided partial overrides and baseline snapshots; export combines them with automatic records without modifying the research store. |

`seed` imports the complete catalog unchanged offline. Per-record stages preserve IDs, flags, custom fields, original evidence and feed timestamps; raw observations do not replace answers or adjudicate dates. The checked-in pilot has one tracked record; other rows are baseline copies, not newly enriched records.

Design/testing uses **one runtime-selected visible, editable record**, never a named prompt example; test writes use isolated copies unless local migration/promotion is approved. **Full enrichment covers all records without sampling**, including prior reviews, preserving hidden content/manual overrides. Batch/page limits affect throughput, not coverage; pending/blocked IDs mean incomplete work. The CLI is not a full-run orchestrator.

Run stages independently from the repository root. This PowerShell example uses placeholders for the selected retirement and its verified, applicable Lifecycle index; for testing, copy the existing catalog to `<test-directory>\retirements.json` first:

```powershell
$id = '<existing-retirement-id>'
$lifecycleUrl = '<verified-applicable-Lifecycle-index-url>'
$pipeline = @('--db-dir', '<test-directory>\databases', '--output', '<test-directory>\retirements.json')
python -m scripts.pipeline @pipeline seed
python -m scripts.pipeline @pipeline ingest --id $id --lifecycle-url $lifecycleUrl
python -m scripts.pipeline @pipeline extract --id $id
python -m scripts.pipeline @pipeline links --id $id
python -m scripts.pipeline @pipeline canonical --id $id
```

Inspect the observations, cached pages and automatic record. If it is unreviewed or needs answer changes, prepare the [review batch](#evidence-based-content-reviews) with `status.automaticCatalogSha256` as its `catalogSha256` and evidence-backed `sourceReview.status: enriched`. Apply it before approval, refresh any changed references, then reassemble:

```powershell
python -m scripts.pipeline @pipeline status
python -m scripts.pipeline @pipeline review --batch <review-batch.json>
python -m scripts.pipeline @pipeline links --id $id
python -m scripts.pipeline @pipeline canonical --id $id
```

Approval requires an enriched automatic record; fingerprints alone do not enrich it. After reviewing the current answers and exact inputs, approve using the latest assembly's `inputSha256`/`recordSha256`, not pre-review fingerprints:

```powershell
python -m scripts.pipeline @pipeline canonical --id $id --accept-review --input-sha256 <reviewed-input-hash> --record-sha256 <reviewed-record-hash>
python -m scripts.pipeline @pipeline export
python -m scripts.pipeline @pipeline status
```

These commands export isolated test JSON only; approved source-catalog export must immediately build. Manual batches use the composed hash and `manual --batch`, not the automatic review hash. Neither editing stage downloads/exports. Reconcile external JSON changes, never overwrite.

**Cache:** `links --id ...` still names the refresh command; its database is now `web_cache.sqlite`. ETag takes precedence over Last-Modified; 304 reuses bodies without writes. Identical 200 bodies retain review validity; absent validators require full download/hash comparison. Ingested source responses are reused. Real dynamic-HTML changes require renewed review; Content-Length/URL age and cached bytes prove neither freshness nor factual/MCP review.

**Guards:** extraction skips matching source hash/version; changed bodies invalidate approval, validator-only changes do not. Failures retain last-good bodies but block promotion. Missing/stale dependencies, approvals or concurrent JSON edits stop export. Offline no-ops preserve DB/JSON bytes; export uses the complete canonical catalog and can recreate missing JSON.

**Storage/safety:** public Microsoft HTTPS only, redirect/address checks, bounded size/time/retries, no credentials/tenant access/crawling; portals are classified without fetching. `.lock` serializes writers: inspect the owning PID before removing a crash-left lock. Close DELETE-journal SQLite connections before Git; ignore only lock/sidecars, never text-merge binary DB conflicts.

**Renaming old caches:** with connections closed, rename `links.sqlite` to `web_cache.sqlite`. If both exist, reconcile without overwriting either; the CLI refuses legacy names rather than creating an empty replacement. The tracked rename preserves cached bytes.

Full Lifecycle discovery, automatic matching/hash IDs, parallel orchestration, scheduling and publication remain unimplemented/gated. Legacy refresh reads the manual store but does not refresh the other databases.

### Parallel enrichment design (not implemented)

The [parallel enrichment contract](.github/prompts/retirement-enrichment.prompt.md#parallel-enrichment-design-not-implemented) separates concurrent research from serialized publication:

```text
Complete baseline -> coordinator queue -> bounded workers on disjoint record IDs
                            |                         |
                     shared fetch/cache        private guarded proposals
                            |                         |
                            +--> one integrator -> canonical.sqlite -> JSON -> build/audit
```

Workers get disjoint leased IDs, immutable inputs and private proposal paths. The coordinator owns deduplicated shared fetching, host/retry/page limits and all shared writes; proposals carry attempt tokens, original record/evidence hashes, citations and validation. Changed targets/evidence require renewed review; unrelated changes can be reconciled only after verifying the target/dependencies, retaining original guards. Durable outcomes allow safe restart without duplicate application or lost coverage.

All eligible records, prior reviews and protected outcomes remain accounted for; tests use one live example plus synthetic concurrency fixtures. See the linked contract for lease expiry, late results, stale guards and interrupted export recovery. Scheduler/leases/proposal reconciliation and concurrency tests remain implementation gates. **Do not run the current CLI concurrently against one `--db-dir` or merge worker database binaries.**

### Weekly Copilot cloud automation

**No cloud automation is created/enabled.** The last capability check reported it disabled/unavailable; the prompt grants neither tools nor schedules, and daily GitHub Actions refresh is unchanged.

When access is available, obtain separate approval for one personal automation, its activation/initial run and publication. Discover supported tools/triggers; grant only public-document retrieval, repository access and required execution. Set weekly day/time in UTC through structured schedule fields, not prompt text. Leave a reviewable diff unless publication is authorized.

Use the prompt's modes/budgets/coverage/resume rules. Before publication reconcile with main and rebuild; legacy refresh replaces automatic reviews but reapplies manual fields. Never overwrite/force-push over concurrent refreshes.

### Parallel discovery design (not implemented)

The [proposed common-baseline contract](.github/prompts/retirement-enrichment.prompt.md#proposed-parallel-discovery-and-common-baseline-contract) permits **only these two sources for retirement discovery and identity matching**:

| Source | Discovery entry point | Planned coverage |
| --- | --- | --- |
| Azure Updates | [Official JSON collection](https://www.microsoft.com/releasecommunications/api/v2/azure) filtered to `Retirements` | Every validated page, preserving official source IDs and timestamps. |
| Microsoft Lifecycle | [Lifecycle hub](https://learn.microsoft.com/lifecycle/) and [official navigation index](https://learn.microsoft.com/en-us/lifecycle/toc.json) | Dynamically discovered annual retirement/end-of-support indexes, including Additional Azure Changes; Azure-related entries only, with product/version/scope/milestone retained. Published years are not hard-coded. |

Other Learn docs and verified Microsoft/product-team Tech Community posts support enrichment only, not discovery/eligibility/matching; redirects do not expand that boundary. Lifecycle means `/lifecycle/`, not the whole Learn host.

The [matching contract](.github/prompts/retirement-enrichment.prompt.md#retirement-identity-and-matching) compares product/component, SKU/version, region/cloud, population and milestone. Titles/URLs/dates alone never prove identity; missing scope and partial overlap are not equivalence. Record confirmed/distinct/unresolved outcomes, preserve source identities, keep unresolved observations separate, and allow single-source retirements.

The [ID contract](.github/prompts/retirement-enrichment.prompt.md#hash-based-retirement-ids) uses `ret-` plus full SHA-256 of a frozen versioned canonical event identity. True digest collisions append persisted first-unused `-2`, `-3`, etc.; never recycle assignments or use suffixes to hide uncertain identity. Registry, serialization and alias/route compatibility need implementation/tests. Current IDs change only under separately approved migration, preserving old aliases and protected content.

First combined discovery preserves all existing records/content/metadata while staging provenance and `id-map.json`; curated duplicates are not auto-merged. `discoverySources` retains source URLs/identities/dates/coverage separately from reviewed citations. New records have five valid questions; provisional dates follow the ordered review rules, and Lifecycle-only entries never invent announcement timestamps.

Both sources must complete before guarded atomic integration; malformed/partial inputs preserve the current catalog. Dynamic years, Azure scope, non-retirement support phases, matching, IDs, provenance/schema/consumer round trips and preservation must pass the prompt's offline gates before a live combined run. The selected-record extractor is not a whole-feed Lifecycle adapter.

### Official source (current implementation)

The source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)). Refresh fetches every page tagged `Retirements`, checks the reported count and unique IDs, and replaces the snapshot only after a complete fetch. Source IDs remain unchanged in the catalog and disambiguate duplicate title slugs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap, and endpoint changes cause refresh to fail rather than silently publishing an incomplete directory.

The structured feed supplies a retirement **month**, not an exact day. For unreviewed records, exact dates are extracted conservatively from current announcement **titles** only when a single distinct, valid date appears. ISO dates require explicit deadline wording to distinguish deadlines from API versions. Automatic refresh does not infer deadlines from publication dates, IDs, URL slugs, or announcement descriptions. Reviewed deadlines may instead use explicit retirement-specific dates from the announcement's title or description, Microsoft Learn, or a verified first-party Tech Community article as described above. Month-only and unresolved deadlines remain **Date to confirm** and do not count as upcoming or retired. **Within 90 days** includes today and day 90 UTC; **Upcoming** includes that group.

Source HTML becomes escaped plain text plus separate HTTPS references. Automatic enrichment supplies safe HTML for all five answers; manual plain edits may use the escaped fallback. Allowed tags: `p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, `br`; reject attributes/active content and escape text. Preserve facts/limits, use concise semantic paragraphs/lists, convert newline escapes, and avoid duplicated dates/notices/support/tracking. Verify tenant impact, pricing, support and phased deadlines with Microsoft.

Site-wide typography uses four primary sizes: .875rem body text and controls (14px at the default browser size), 1rem subheadings (16px), 1.125rem section headings and summary counts (18px), and 1.375rem page titles (22px). Navigation, filters, cards, notices, metadata, and footers use the same body size and 1.6 line spacing on desktop and mobile. The only caption-size exception is the main timeline's customer lead-time label and duration at .75rem (12px); retirement dates and detail-page lead times retain the body size. Relative units respect browser font preferences. Headings retain their hierarchy, and semantic emphasis, code fonts, and notice colors remain distinct.
