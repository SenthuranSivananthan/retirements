# Azure Retirements

A static website for Microsoft Azure retirement announcements. Its Azure-blue palette, Segoe typography, navigation, full-width hero, and light/dark themes follow [Multi-region platform](https://azure.github.io/multi-region-platform/).

The application is a **Python/Jinja static site** with maintained CSS and browser JavaScript modules. The generated website is committed in **`docs`** for GitHub Pages. There is no TypeScript compilation, Node.js/npm build, backend or Jekyll dependency.

Every retirement has a complete HTML page with all five planning questions. Content and sidebar navigation work without JavaScript; search, filters, live countdowns, and themes are progressive enhancements.

## Current architecture

| Area | Implemented behavior |
| --- | --- |
| Website | `site\build.py` reads `data\retirements.json`, renders `docs`, and validates the output. Builds do not fetch announcements or run synthesis. |
| JSON enrichment | Opt-in `scripts.enrichment` commands acquire sources, synthesize five answers, reconcile `retirements_canonical.json`, and project website JSON. A real synthesis adapter is required. |
| Existing data | The SQLite and JSON workflows are separate. |
| Automation | `.github\workflows\pages.yml` validates changes and runs a daily/manual `scripts.refresh_data` feed refresh, **not** JSON synthesis or SQLite research stages. |

Use the [preview and development commands](#quick-preview) for site work and the
[JSON enrichment pipeline](#json-enrichment-pipeline) for the new data workflow.
Do not mix catalog writers.

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

The checked-in catalog supports offline builds and previews. There is no backend, Azure login, API key, or environment file to configure for building or previewing. Installing dependencies requires PyPI access; explicit discovery/download/enrichment commands can contact content sources and the configured synthesis adapter.

## Install development dependencies

All commands run from the repository root. Third-party dependencies are **Jinja2** for HTML templates, **html5lib** for parsing announcement HTML, and **markdown-it-py** for rendering structured enrichment answers; pip installs their transitive dependencies automatically.

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
| `python site\build.py` | Read `data\retirements.json`, prepare view metadata, render `docs`, and verify the result |
| `python site\build.py --serve` | Rebuild, verify, then serve at `http://localhost:8000/` |
| `python -m http.server 8000 --bind 127.0.0.1 --directory docs` | Preview the existing output without installing dependencies or rebuilding |
| `python -m unittest discover -s tests -v` | Run offline schema, date, source, refresh-protection, and renderer tests |
| `python -m scripts.check_site` | Verify an existing `docs` build against `data\retirements.json` |
| `python -m scripts.enrichment init` | Create the five JSON stage files without changing the website catalog |
| `python -m scripts.enrichment discover` | Crawl the complete Azure Updates retirement feed |
| `python -m scripts.enrichment download --workers 4` | Download automatic and manually supplied retirement source links |
| `python -m scripts.enrichment enrich --summarizer-command '["python","my_summarizer.py"]'` | Summarize acquired pages, depth-one references and manual context using your adapter |
| `python -m scripts.enrichment merge` | Reconcile sources and enrichment into `retirements_canonical.json`, then project the website catalog |
| `python -m scripts.enrichment status` | Inspect source, summary and failure counts without fetching content |
| `python -m scripts.enrichment reprocess --retirement-id <id> --summarizer-command '["python","my_summarizer.py"]'` | Force-refresh one existing record through projection without global discovery |

These are PowerShell examples. On Linux, use `site/build.py` and `/` in filesystem
paths. JSON commands default to `data`; pass `--data-dir` consistently when using
an isolated stage directory. `my_summarizer.py` is a supplied adapter, not a file
bundled with this repository.

## JSON enrichment pipeline

The JSON enrichment pipeline is `python -m scripts.enrichment`. It uses readable
JSON stage state and runs independently of the retained SQLite workflow. `merge`
writes to the selected stage directory unless `--output` is supplied; it first persists `retirements_canonical.json`,
then writes the website-facing `retirements.json`.
Existing hidden, feed-absent and manual-protected records are preserved.
If projection is interrupted, a pending marker permits retry only while the output
still matches its pre-write snapshot; a concurrent edit is preserved and blocks retry.

### Process and starting point

1. **Acquire sources:** crawl Azure Updates and read the user-provided retirement
   list, then download their retirement pages.
2. **Enrich:** process those pages plus their directly linked references at depth 1,
   summarizing all five questions. Process additional user links/context separately
   as manual enrichment.
3. **Reconcile:** compose automatic and manual answers into
   `retirements_canonical.json`; validate and track each record's source/input revisions.
4. **Project and build:** generate website-schema `retirements.json` from the canonical
   view, then build and verify `docs`.

Initialize the files below, add any manual sources/context, and run discovery through
merge. For **website-only changes**, run `python site\build.py`; no source acquisition
or synthesis is necessary.

| File in `data` | Contents |
| --- | --- |
| `retirement_source_automatic.json` | Azure Updates retirement URLs and download/refresh metadata |
| `retirement_source_manual.json` | User-supplied retirement URLs and download/refresh metadata |
| `retirement_enrichment_automatic.json` | Page and retirement summaries organized into five questions |
| `retirement_enrichment_manual.json` | Additional user links/context, explicit field overrides and their summaries |
| `retirements_canonical.json` | One composed retirement record per ID, with automatic/manual/source revisions and catalog metadata |
| `retirements.json` | Website projection of the validated canonical view, using the existing website schema |

Azure Updates is the only automatically crawled discovery feed. Manual retirement
links are the other discovery input; there is no independent Lifecycle discovery
or web search. Automatic enrichment processes each retirement page and its content
references at **depth 1 only**. Manual enrichment downloads only explicitly supplied
additional links. Navigation links and references on depth-1 pages are not crawled.
Azure announcements are acquired through their exact Azure Updates API item, not
a generic updates listing.

Initialize the five stage files without changing `retirements.json`:

```powershell
python -m scripts.enrichment init
```

In `retirement_source_manual.json`, add entries under `records`:

```json
{
  "schemaVersion": 1,
  "kind": "retirement_source_manual",
  "records": {
    "existing-or-new-retirement-id": {
      "title": "Retirement title",
      "urls": ["https://learn.microsoft.com/azure/example-retirement"]
    }
  },
  "pages": {}
}
```

Use an existing ID when explicitly associating another source with that retirement.
Different IDs cannot own the same source URL. The example URL is illustrative.
For additional context/links, edit `inputs` in `retirement_enrichment_manual.json`:

```json
{
  "existing-or-new-retirement-id": {
    "urls": ["https://learn.microsoft.com/azure/example-migration"],
    "context": "User-supplied context for this retirement.",
    "overrides": {
      "questions": {
        "actions": "The explicitly supplied replacement action summary."
      }
    }
  }
}
```

`inputs` is an object within that stage file, not its entire contents. A context-only
input is supported. `overrides` may replace `summary`, individual five-question
strings, and `deadline.date`/`deadline.month`. Missing fields keep automatic content;
other manual summaries are added with visible user-provided attribution. Conflicting
manual/automatic exact dates block export until an explicit deadline override is supplied.

Run stages independently from the repository root, proceeding only when the previous
command succeeds:

```powershell
$StageDir = "data"
python -m scripts.enrichment discover --data-dir $StageDir
python -m scripts.enrichment download --data-dir $StageDir --workers 4
python -m scripts.enrichment enrich --data-dir $StageDir --summarizer-command '["python","my_summarizer.py"]'
python -m scripts.enrichment merge --data-dir $StageDir
python -m scripts.enrichment status --data-dir $StageDir
```

`my_summarizer.py` is **your supplied adapter**, not a bundled model or fake summarizer.
For subsequent refreshes, the equivalent combined command is:

```powershell
python -m scripts.enrichment run --data-dir $StageDir --workers 4 --batch-size 10 --summarizer-command '["python","my_summarizer.py"]'
if ($LASTEXITCODE -ne 0) { throw "Enrichment failed; do not adopt or build a replacement catalog." }
```

`run` combines discovery, download, enrichment, canonical reconciliation and website
projection; it does not build the site.
To force a complete refresh for one existing retirement ID without rerunning global
discovery or touching other records, use:

```powershell
$RetirementId = "existing-retirement-id"
python -m scripts.enrichment reprocess --data-dir $StageDir --retirement-id $RetirementId --workers 4 --summarizer-command '["python","my_summarizer.py"]'
if ($LASTEXITCODE -ne 0) { throw "Record reprocessing failed; do not adopt or build a replacement catalog." }
```

`reprocess` requires that the ID already exists in the source stage files. It
unconditionally refreshes that record's retirement source pages, direct references
and any manual enrichment links, regenerates their summaries, then reconciles only
that ID into the canonical view and website projection. Other catalog records are
preserved unchanged. Hidden or manually protected records remain protected and are
reported rather than overwritten. This command does not create missing
retirement-source entries or refresh global discovery; run `discover` separately
when the feed's membership or metadata needs updating.
After a successful merge into the live `data` directory, build with
`python site\build.py`. For manual content changes, edit the stage inputs rather
than the merged catalog or generated `docs` pages.

For isolated evaluation use `--data-dir <scratch-directory>`; `--output <path>` selects
the merged catalog destination. No network is used by `init`, `merge`, or `status`.
No model API key is required by the pipeline itself; authentication/configuration for
an actual model belongs to the adapter and must not be stored in stage files.

### Retirement writing style

Apply this writing style to each of the five question answers in both automatic
and manual synthesis, not just the overview. Write for customers deciding whether
they are affected and what to do next. Use a calm, direct, factual tone, active
voice and short paragraphs. Address the reader as "you" for actions; name Microsoft
or the service for provider commitments,
rather than speaking as the provider. Lead with the change, applicable date and
practical consequence. Avoid marketing, apologies, alarmist language, vague
reassurance and repeated introductory text.

Keep the existing five questions and deadline-first navigation; organize useful
announcement and migration guidance within them rather than adding new sections:

- **Deadline:** Distinguish announcement, new-customer restrictions, deprecation,
  end of support and service shutdown. Label each applicable phase and population;
  never treat end of support as proof that workloads stop. Preserve date precision,
  conflicts and uncertainty rather than inventing a typical notice period.
- **What changes:** Explain affected features, versions, regions and customers,
  what remains available before the deadline, and what changes afterward. Mention
  maintenance, support or security-update commitments only when documented.
- **Actions:** Give ordered, practical steps to identify usage, choose a documented
  alternative by use case, migrate and validate. Include prerequisites, capability
  gaps and documented export/backup, cutover or cleanup steps where relevant;
  distinguish required work from optional recommendations.
- **Impact:** Explain the consequences of taking no action, separating workload
  continuity from loss of console/API access, integrations, deployment tooling,
  support or data access. Cover retention/deletion and cost implications only when
  supported, and state documented unaffected cases explicitly.
- **Progress:** Describe supported identification and completion checks, their scope
  and limitations, and team-owned evidence of migration. Include documented help or
  escalation routes when available. Do not imply this site inspects resources or
  stores checklist progress.

Apply these as content checks, not boilerplate that every source must satisfy.
Use only permitted retirement inputs; missing essential details remain explicitly
unavailable or unconfirmed, not inferred from another service's announcement.
Keep successfully processed source links in References, preserve manual content, and
apply this style only during an authorized synthesis.

### Synthesis and Microsoft Learn MCP adapters

The pipeline owns acquisition, depth limits, refresh state, checkpoints and merging.
Semantic synthesis is supplied by a local command (or the Python
`Enrichment(..., summarizer=callable)` interface). The command receives one JSON
object on stdin and returns one JSON object on stdout. It receives `instructions`,
plus either `kind: "page"` with `url`, `title`, and transient `content`, or
`kind: "retirement"` with the ID/title, page `documents` containing summaries,
`unavailableReferences`, `userContext`, and the automatic/manual `layer`.
The required response is:

```json
{
  "summary": "Concise retirement-specific overview.",
  "questions": {
    "what": "### What changes\n\nA concise description with **important scope**.\n\n- Affected configurations.\n- Documented exceptions.",
    "actions": "### Required actions\n\n1. Identify affected resources.\n2. Follow the documented migration and validation steps.",
    "impact": "Affected configurations and documented risks.",
    "deadline": "Dates, precision, conflicts and consequences.",
    "progress": "Documented verification methods and their limits, or an explicit unavailable answer."
  },
  "deadline": {"date": null, "month": null}
}
```

The overview is limited to 2,000 characters, each answer to 12,000. No missing
question or malformed date is accepted. Schema validation cannot establish factual
accuracy: the adapter must follow the [enrichment prompt](.github/prompts/retirement-enrichment.prompt.md)
and content review remains required. The CLI supplies built-in `instructions`;
it does not load the repository prompt automatically. Configure your adapter to
apply that prompt, including the five-question writing guidance. There is no
bundled model, summarizer script or heuristic synthesis fallback.

Question strings support a safe Markdown subset: paragraphs, subheadings, bullet
and numbered lists (including nested lists), bold/emphasis, inline code, fenced or
indented code blocks, and line breaks. Use ordered lists for sequential actions,
bullets for scope/alternatives, and code only when documented in the supplied
content. Keep the overview plain text; do not emit raw HTML, tables, images or inline
links. The existing References section owns source links.

Merge generates `questions.<key>.html` for **all five answers** and derives their
plain-text fields from the same parsed content, removing formatting markers without
dropping the facts. Heading levels normalize to `h3`; ordered lists start at 1.
Only the existing attribute-free HTML allowlist is emitted:
`p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, `br`.
Raw HTML is escaped, code stays literal, and unsupported Markdown remains visible
text rather than creating active markup. Manual summary additions and overrides use the same renderer. Preserve existing
curated content unless an authorized change explicitly replaces it.

The formatting-aware processor is `json-five-questions-v2`. The next explicitly
requested enrichment reprocesses summaries from older processor versions; it may
need to refetch content whose transient text was already discarded.

For Microsoft Learn, optionally pass
`--learn-mcp-command '["python","my_learn_mcp_bridge.py"]'` to `download`, `enrich`,
`run` or `reprocess`. This bridge must use your configured Microsoft Learn MCP
`microsoft_docs_fetch`, receiving `{"url":"https://learn.microsoft.com/..."}` and
returning `{"content":"complete Markdown","url":"the actual page URL","title":"optional title"}`.
The CLI cannot directly access tools in an agent's conversation, so it does not
pretend that an MCP bridge exists when none is configured. With the Python API,
`learn_fetch=callable` supplies the same contract. MCP full content is preferred;
an unavailable/failed bridge falls back to public HTTP and records the reason.
Search snippets are not full-page retrieval. MCP Markdown hashes are separate from
HTTP body hashes, and absent HTTP validators are never invented.

Agent tools and automation capabilities depend on the execution environment.
Discover and authenticate available tools there; a prompt does not install an MCP
server, grant access or create a schedule. An agent's available fetch tool is not
automatically available to a subprocess or an unattended GitHub Actions runner.
Keep adapter credentials outside tracked files and stage JSON.

### Refresh and recovery

Downloads use ETag first, then Last-Modified; unchanged content reuses summaries.
References are checked independently, and changed user context invalidates only
manual synthesis and the dependent merge. Without validators, content is fetched
and hashed on refresh. A processor-version change or missing summary refetches
discarded text for reprocessing even if normal conditional GET returns `304`.
Failures retain URL, status and reason in stage metadata for future retries; failed
references, search-result pages, sign-in pages and generic error pages are not
evidence and must not appear in answer citations or rendered References. Flag
excluded references internally for future review or retry. Essential source and
manual-link failures block dependent summaries/export. Optional reference failures
may allow synthesis to continue, but remain internal limitations rather than
customer-facing citations.

`--workers` controls bounded page acquisition (1-8, default 4), not parallel model
agents; retirement synthesis is serial. Responses are capped at 8 MiB. Acquired
text is staged temporarily in `$StageDir\.enrichment-work`, hash-verified on read
and removed after successful enrichment. Stage JSON retains summaries and refresh
metadata, not page-body archives.

One OS lease guards writers. Page/retirement revisions are saved atomically;
`--batch-size` (5-10, default 10) controls batch checkpoints in
`.enrichment-work\checkpoint.json`. These checkpoints describe stage outcomes,
not an external workflow runtime. After a failure, resolve the reported blocker
and rerun the affected stage against the **same directory**; saved valid summaries
are reused. `run` also refreshes discovery, while `reprocess` intentionally forces
the selected record's acquisition and synthesis.

For long-running full-catalog work, continue through routine batches and resume
from durable checkpoints if a turn ends. When an approved recurring session
wake-up is available, use it to resume the same session rather than creating a
replacement workflow. At **150 MB available memory**, pause at a safe checkpoint
without cancelling the task; resume when memory recovers. Report completed/total
and remaining counts with timestamps, distinguishing approval hashes from audited
coverage. Do not replace the live catalog or rebuild until the required reviews,
conflict decisions, audits and input-closure checks are complete.

Create `$StageDir\.enrichment-work\stop` to request a safe stop at a work boundary;
remove that signal before continuing. Do not remove an active lease or start
competing writers. Canonical/projection fingerprints reject out-of-band edits;
`pendingProjection` permits an interrupted merge to finish only if the destination
still matches its pre-write snapshot or already equals the canonical projection.
Concurrent edits are preserved and must be reconciled, not overwritten.

The [existing schedule](#automated-refresh) still runs `scripts.refresh_data`, not
JSON synthesis. That command refuses to overwrite a JSON-pipeline catalog.

## Project structure

```text
retirements
  .github\workflows\pages.yml   Validation and existing daily/manual feed refresh
  .github\prompts\              Enrichment and site-build instructions; not schedules
  site\                     Website source, separate from shared data and tooling
    build.py                Python/Jinja static-site generator and optional server
    config.json             Title, description, production URL, and project base URL
    templates\              Home, retirement, 404, shared layout, macros, and partials
    assets\css\style.css     Themes, layout, and responsive styles
    assets\js\              Maintained browser JavaScript; no compilation required
    assets\data\            Prepared catalog copy; ignored by Git
    _data\site.json          Prepared view metadata; ignored by Git
  docs\                     Generated public website; intentionally checked in
  data\
    retirements.json        Current website input and public download
    pipeline\               Retained five-store SQLite data
  scripts\
    enrichment.py           Opt-in JSON pipeline and single-record reprocessing
    enrichment_json.py      Guarded JSON writes, writer lease and transient text handling
    enrichment_http.py      Bounded page retrieval and content/reference extraction
    catalog.py              Validation, dates, countdowns, grouping, and preparation
    feed.py                 Azure Updates parsing, pagination, and normalization
    refresh_data.py         Existing feed refresh and manual-override composition
    pipeline.py             Retained SQLite stages and guarded export
    manual_data.py          Field-level manual composition
    review_data.py          Retained review reporting and guarded batch edits
    check_site.py           Generated page, question, link, and catalog checks
  tests\                    Python unittest suite and offline fixtures
  requirements.txt          Python dependencies
```

The [five JSON stages](#process-and-starting-point) are created by `init` in the
selected directory; they are not a preconfigured replacement catalog.

Edit templates for markup, `style.css` for appearance, and browser modules for
interaction (`main.js`, `catalog.js`, `data.js`). Never hand-edit `docs` or prepared
metadata. Rebuild when rendering or catalog changes require new output, and include
that output when publishing the change. Documentation-only edits do not need a
website rebuild. Keep credentials, virtual environments and temporary processing
files out of Git; retain adopted stage data and existing evidence deliberately.

## Publish on github.io

1. Build with `python site/build.py`, commit the resulting `docs` together with source changes, and merge into `main`.
2. In **Settings > Pages > Build and deployment**, choose **Deploy from a branch**, select **main**, choose **/docs**, and save. If migrating from the previous setup, change the source from **GitHub Actions**.
3. Open **https://senthuransivananthan.github.io/retirements/** after the native Pages build finishes.

The `docs/.nojekyll` file disables Jekyll processing. GitHub serves the already-generated HTML, CSS, JavaScript, and JSON; it does not install Python dependencies or rebuild templates.

`site/config.json` sets `url` to `https://senthuransivananthan.github.io` and `baseurl` to `/retirements`. Update them for another repository or custom domain, using an empty `baseurl` for a domain-root site. Normal pages use page-relative assets and navigation, supporting both root-level local preview and project-path publishing. The 404 page uses the configured production base path so it works for arbitrary missing URLs.

Detail URLs use `/retirements/retirements/YYYY-MM-DD/<title-slug>/` on the project
site: the first segment is the repository base path, the second is the detail
directory. The date is the exact deadline; month-only/unknown dates use
`unknown-date`. Duplicate title slugs receive an ID suffix. Each build replaces the
generated detail tree to remove stale routes while preserving unrelated output.

Filters use ordinary query strings. Existing `#/retirements/<id>` and `#/?...` links redirect to their current static or query-string equivalents, retaining navigation context. On GitHub Pages, the custom 404 page also redirects old ID-based detail URLs and outdated date folders when the record can be identified unambiguously, preserving query strings and section anchors. These redirects require JavaScript; current detail pages and navigation remain usable without it. Python's basic local HTTP server does not serve the custom 404 page for missing paths.

### Automated refresh

Pull requests and pushes to `main` install Python dependencies, run offline tests, check the committed publishing output, and rebuild from source. They do not fetch announcements or receive write permissions.

Daily at **06:23 UTC**, or through **Actions > Validate site and refresh GitHub Pages > Run workflow**, the main-branch refresh job:

1. Confirms Pages is configured for **main /docs**.
2. Fetches the complete Azure Updates retirement feed and composes retained manual overrides.
3. Runs tests, rebuilds, and validates the website.
4. Commits changes to `data/retirements.json` and `docs`, then pushes to `main`.
5. Explicitly requests a native Pages build, because pushes made using `GITHUB_TOKEN` do not trigger Pages builds automatically.

The refresh requires `contents: write` and `pages: write`; repository policy and branch protection must allow the bot's normal push. A rejected push or Pages request fails visibly; no force push or protection bypass is attempted. If you prefer local refreshes, disable the scheduled workflow and commit refreshed data and output yourself. Configure Pages before running the automated refresh. A failed fetch, validation, or build does not commit incomplete output.

This scheduled job still uses `scripts.refresh_data`, not the JSON enrichment
pipeline or its adapters. After adopting a JSON-pipeline catalog it intentionally
fails rather than replacing enriched answers. Disable the scheduled refresh or
configure a separately approved JSON workflow with real synthesis/MCP adapters.

## Explore and plan

- **Outlook:** retired-this-year and cumulative next 6/12/18-month views use exact
  deadlines. Rolling windows include the current UTC month through the last day of
  the target month; retired-this-year ends yesterday. Month-only/unknown deadlines
  do not count. "Retired" describes a deadline, not a completed migration.
- **Directory:** category > service > retirement, with alphabetical groups and
  descending exact deadlines (unknown last, title ties). Counts and pagination are
  unique even when an announcement belongs to several groups.
- **Search and filters:** combine category, service, retirement window, announcement
  year and sidebar status shortcuts. Announcement year uses the current UTC year
  and previous three; retirement years include confirmed month-only years. Shareable
  URLs, history and return links preserve filters; **Reset filters** clears them.
- **Sidebar:** retirement year > category > retirement. Directory branches/counts
  reflect all matches, not just loaded results. Detail pages show the complete
  visible tree with the current item expanded; only the return link keeps filters.
- **Details:** customer lead time uses exact announcement/deadline dates in calendar
  years, months and days; missing dates are not calculable. Use **In this article**
  to navigate the five answers, References for sources, and the JSON download for data.
- **Access:** desktop pinned sidebar, mobile navigation menu (Escape/backdrop to
  close), header search (`Ctrl+K`/`Cmd+K`) and light/dark themes. Only theme preferences
  are saved by the current UI; there is no tenant connection or analytics.

Countdowns use UTC calendar days: **Retires today (0 days remaining)**,
**Retired**, or **Retirement date to confirm** for unknown/month-only dates.
JavaScript updates countdowns/outlook on load and UTC date changes; without it,
static content reflects the build.

Every retirement detail keeps these sections in order:

1. **What is the deadline?**
2. **What is changing?**
3. **What do I need to do?**
4. **Where, and how much, am I impacted?**
5. **How can I track progress?**

When available, **Open Microsoft Learn guidance** is the final element in **What do I need to do?**, after all migration content, support guidance, and support links. The shared detail template applies this order to every retirement page.

The progress section renders answer HTML and an optional tracking-source link,
not an interactive checklist. Identification methods and their limits must be in
the rendered answer, not only auxiliary JSON fields. Missing methods are reported
explicitly. Team-owned/local planning is not progress saved by this site.

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

`announcedOn` is the UTC calendar date from Microsoft's per-announcement `created` timestamp, displayed as **Announced**; it records when the announcement was published. Missing values remain `null`, and dates are not inferred from announcement text. `lastUpdatedOn` is the UTC calendar date from Microsoft's per-announcement `modified` timestamp, displayed as **Last updated**. It is not the publication date, deadline, or retrieval time. Missing timestamps produce `null` and **Not provided by source**; malformed timestamps fail refresh. Catalog-level `retrievedAt` is the snapshot time, updated by a feed refresh or changed merged content; individual page download/check times remain in the stage metadata.

`categories` comes from official `productCategories`, not guessed service names. Multi-category announcements appear under each applicable category but count once in directory totals. Missing categories, including on older protected records, use **Uncategorized** without modifying the record.

Navigation uses the exact deadline's year, otherwise the stated year of a valid source month, otherwise **Unconfirmed year**. It never uses the announcement year or invents an exact date from a month.

### Protecting manual enrichments

For the JSON workflow, associate links/context with the existing retirement ID in
`retirement_enrichment_manual.json` → `inputs`. Explicit summary/question/deadline
overrides belong to that input's `overrides`; automatic summaries remain underneath.
See the [JSON workflow examples](#json-enrichment-pipeline).

Each record also has a `hidden` boolean, initially `false`. Set it to `true` to exclude that retirement from search, navigation, filters, and visible counts; the direct detail page and public JSON download remain accessible, so this is not an access-control feature. Feed refresh preserves the flag for matching records. Older records without the field are treated as visible.

#### Existing SQLite manual overrides

The following commands apply only while SQLite owns the catalog. Store supplied
fields separately in **`data\pipeline\manual.sqlite`**. Manual values override only
matching fields at export; objects merge recursively, arrays replace, and explicit
nulls remain null. Whole-record protection via `manuallyEnriched` is no longer used.

Manual batches use `catalogSha256` from `python -m scripts.pipeline status`:

```json
{"catalogSha256":"<reported composed hash>","overrides":[{"id":"<existing-id>","fields":{"questions":{"impact":{"guidance":"<user-provided content>"}}}}]}
```

Apply with `python -m scripts.pipeline manual --batch <manual-batch.json>`, then `export` and `python site/build.py`. Use the same `--db-dir`/`--output` options as the target pipeline. `fields: null` removes an override and restores automatic values. Identity/timestamps/visibility use their normal workflows, not content overrides. Custom content and citation fields are supported; HTML/resources/dates must pass existing validation. A plain answer change without matching HTML discards stale HTML and uses the plain fallback.

Automatic reviews use `status.automaticCatalogSha256`, never composed manual data. Export records supplied field paths as provenance; it does not claim user content was independently researched. Refresh reapplies overrides and retains their baseline for feed-absent records. Manual edits/research remain separate and neither silently overwrites the other.

`python -m scripts.pipeline migrate` removes legacy flags offline, preserving flagged content as manual overrides. The checked-in migration changed no retirement facts. JSON-only review refuses composed output. External JSON refreshes can still conflict with the canonical DB's export guard and need reconciliation; invalid data and concurrent edits fail without overwriting snapshots.

### Evidence-based content reviews

The [enrichment prompt](.github/prompts/retirement-enrichment.prompt.md) describes the
current three-step JSON workflow. The review commands in this subsection describe
the retained SQLite/guarded-review tools and existing `sourceReview` records, not an
additional required step for JSON enrichment.

Reviews organize automatic answers under five questions and add **`sourceReview`**: actual UTC day, `enriched` status, issues, sources and checks. This means reviewed/organized, not proof of every claim. Preserve uncertainty, original evidence and timestamps. Hidden content is untouched; automatic workers cannot write manual overrides.

For these existing review records, read actual destinations, use real titles, verify Learn locale normalization, preserve selectors/original snapshots, account for every resource, and exclude references only after confirmed 404/410. `guidanceSource` selects Learn documentation cited for actions; `deadlineSource` must match cited applicable deadline evidence. References deduplicate reviewed sources/resources and use reviewed redirects; citation details remain in JSON. The new workflow's [processing rules](.github/prompts/retirement-enrichment.prompt.md#step-2-process-and-summarize-enrichment) restrict content to its permitted source/reference inputs.

The [date and summary rules](.github/prompts/retirement-enrichment.prompt.md#five-question-summary-contract) require matching event/scope/milestone and explicit applicable evidence. Exclude superseded dates only with documented extensions. A full conflict span of **1-6 days selects the earliest**, even over later Learn evidence; exactly seven days and longer chains do not qualify. Otherwise prefer an unambiguous current applicable Learn deadline; unresolved conflicts stay unconfirmed. Preserve month-only precision, alternatives, times/time zones and rationale; never claim Microsoft reconciled a conservative selection. Keep structured date/month, answers and citations consistent.

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

### Retained SQLite tools

`scripts.pipeline` remains available for existing SQLite-owned catalogs; it is not
the new JSON workflow or a full-run research orchestrator. Inspect its actual CLI
before operating on a store:

```powershell
python -m scripts.pipeline --help
python -m scripts.pipeline canonical --help
python -m scripts.pipeline status
```

Its stages are `seed`, `ingest`, `extract`, `links`, `canonical`, `review`, `manual`,
`export` and `migrate`. The five stores hold raw source bytes (`raw.sqlite`),
observations (`extracted.sqlite`), cached pages (`web_cache.sqlite`), automatic
records/provenance (`canonical.sqlite`) and partial user overrides (`manual.sqlite`).
`ingest --id` requires an explicitly selected `--lifecycle-url`; this is not
permission to introduce Lifecycle discovery into the JSON workflow.

Review against `status.automaticCatalogSha256`, apply the evidence-backed batch
with `review --batch`, then reassemble using `canonical --id`. Approval requires an
enriched record and explicit attestation of the current `inputSha256` and
`recordSha256` using `--accept-review`, `--input-sha256` and `--record-sha256`.
Downloaded pages, fingerprints or approval-field counts alone do not prove
semantic completeness. Missing/stale dependencies and concurrent JSON edits block
export. Keep all existing evidence and external review journals for the final
audited handoff.

Do not run this CLI concurrently against one `--db-dir`, merge database binaries,
or remove a lock without checking its owner. The scheduled `scripts.refresh_data`
command reads manual overrides but does not refresh the research databases.

### Azure Updates feed and website output

The automatic discovery source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)); explicitly supplied links form the separate manual discovery input. Feed acquisition fetches every page tagged `Retirements`, checks the reported count and unique IDs, and publishes discovery state only after a complete fetch. Source IDs remain unchanged in the catalog and disambiguate duplicate title slugs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap, and endpoint changes cause refresh to fail rather than silently publishing an incomplete directory.

The structured feed supplies a retirement **month**, not an exact day. Before enrichment, feed normalization extracts exact dates conservatively from current announcement **titles** only when a single distinct, valid date appears; ISO dates require explicit deadline wording to distinguish deadlines from API versions. Enrichment may instead use explicit retirement-specific dates in the permitted announcement/reference content. Neither path infers deadlines from publication dates, IDs or URL slugs. Month-only and unresolved deadlines remain **Date to confirm** and do not count as upcoming or retired. **Within 90 days** includes today and day 90 UTC; **Upcoming** includes that group.

Source HTML becomes escaped plain text plus separate HTTPS references. JSON merge
renders the five Markdown answers through the safe HTML rules above; retained plain
answers may use the escaped fallback. Preserve facts and limits without duplicating
dates, support notices or tracking guidance. Verify impact, pricing, support and
phased deadlines against permitted source evidence, never assumed tenant access.

For detailed interface invariants, typography and rendering checks, see the
[site-build prompt](.github/prompts/site-build.prompt.md).
