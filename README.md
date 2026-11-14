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
| `python site\build.py` | Prepare `data\retirements.json`, render every page into `docs`, copy public assets, and verify the result |
| `python site\build.py --serve` | Rebuild, verify, then serve at `http://localhost:8000/` |
| `python -m http.server 8000 --bind 127.0.0.1 --directory docs` | Preview the existing output without installing dependencies or rebuilding |
| `python -m unittest discover -s tests -v` | Run offline schema, date, source, refresh-protection, and renderer tests |
| `python -m scripts.check_site` | Verify an existing `docs` build against the canonical catalog |
| `python -m scripts.enrichment init` | Create the five JSON stage files without changing the website catalog |
| `python -m scripts.enrichment discover` | Crawl the complete Azure Updates retirement feed |
| `python -m scripts.enrichment download --workers 4` | Download automatic and manually supplied retirement source links |
| `python -m scripts.enrichment enrich --summarizer-command '["python","my_summarizer.py"]'` | Summarize acquired pages, depth-one references and manual context using your adapter |
| `python -m scripts.enrichment merge` | Reconcile sources and enrichment into `retirements_canonical.json`, then project the website catalog |
| `python -m scripts.enrichment status` | Inspect source, summary and failure counts without fetching content |
| `python -m scripts.enrichment reprocess --retirement-id <id>` | Force-refresh one existing record through projection without global discovery |
| `python -m scripts.convert_enrichment --help` | Show read-only SQLite-to-JSON conversion options |

These are PowerShell examples. On Linux, use `site/build.py` and `/` in filesystem
paths. JSON commands default to `data`; after conversion to another stage directory,
pass `--data-dir` consistently as described below. `my_summarizer.py` is a supplied
adapter, not a file bundled with this repository.

### JSON enrichment pipeline

The replacement pipeline is `python -m scripts.enrichment`. It uses readable JSON
instead of SQLite for its stage state. It does **not** migrate, delete or reuse the
existing databases automatically. `merge` writes to the selected stage directory
unless `--output` is supplied; merge first persists `retirements_canonical.json`,
then writes the website-facing `retirements.json`.
Existing hidden, feed-absent and manual-protected records are preserved.
If projection is interrupted, a pending marker permits retry only while the output
still matches its pre-write snapshot; a concurrent edit is preserved and blocks retry.

#### Process and starting point

1. **Acquire sources:** crawl Azure Updates and read the user-provided retirement
   list, then download their retirement pages.
2. **Enrich:** process those pages plus their directly linked references at depth 1,
   summarizing all five questions. Process additional user links/context separately
   as manual enrichment.
3. **Reconcile:** compose automatic and manual answers into
   `retirements_canonical.json`; validate and track each record's source/input revisions.
4. **Project and build:** generate website-schema `retirements.json` from the canonical
   view, then build and verify `docs`.

For **existing, freshly downloaded SQLite data**, finish the current enrichment and
close its writers first, then follow [Convert existing SQLite data](#convert-existing-sqlite-data)
and [Build from the converted catalog](#build-from-the-converted-catalog).
Conversion preserves that data's freshness and does not run discovery or redownload it.
Do not initialize empty stages as a substitute for converting the completed work.

For a **new JSON workflow without SQLite input**, initialize the files below, add any
manual sources/context, and run discovery through merge. For **website-only changes**,
run `python site\build.py`; no discovery, conversion or synthesis is necessary.

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
$StageDir = "data" # Use "data\converted" instead when continuing converted stages.
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
If `$StageDir` is `data`, build with `python site\build.py` after a successful merge.
For `data\converted`, first follow the catalog adoption/build step below, and repeat
that step after later successful merges. For manual content changes, edit the stage
inputs rather than the merged catalog or generated `docs` pages.

For isolated evaluation use `--data-dir <scratch-directory>`; `--output <path>` selects
the merged catalog destination. No network is used by `init`, `merge`, or `status`.
No model API key is required by the pipeline itself; authentication/configuration for
an actual model belongs to the adapter and must not be stored in stage files.

#### Synthesis and Microsoft Learn MCP adapters

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
and content review remains required. There is deliberately no heuristic fallback
that claims to have performed semantic synthesis.

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
text rather than creating active markup. Manual summary additions and overrides use
the same renderer. Conversion preserves existing HTML and imported manual field
patches rather than reformatting curated content.

The formatting-aware processor is `json-five-questions-v2`. The next explicitly
requested enrichment reprocesses summaries from older processor versions; it may
need to refetch content whose transient text was already discarded. Conversion or
offline merge of unchanged imported records does not trigger those downloads.

For Microsoft Learn, optionally pass
`--learn-mcp-command '["python","my_learn_mcp_bridge.py"]'` to `download`, `enrich`,
or `run`. This bridge must use your configured Microsoft Learn MCP
`microsoft_docs_fetch`, receiving `{"url":"https://learn.microsoft.com/..."}` and
returning `{"content":"complete Markdown","url":"the actual page URL","title":"optional title"}`.
The CLI cannot directly access tools in an agent's conversation, so it does not
pretend that an MCP bridge exists when none is configured. With the Python API,
`learn_fetch=callable` supplies the same contract. MCP full content is preferred;
an unavailable/failed bridge falls back to public HTTP and records the reason.
Search snippets are not full-page retrieval. MCP Markdown hashes are separate from
HTTP body hashes, and absent HTTP validators are never invented.

Downloads use ETag first, then Last-Modified; unchanged content reuses summaries.
References are checked independently, and changed user context invalidates only
manual synthesis and the dependent merge. Without validators, content is fetched
and hashed on refresh. A processor-version change or missing summary refetches
discarded text for reprocessing even if normal conditional GET returns `304`.
Failures retain last-good metadata but remain explicitly failed; essential source
and manual-link failures block dependent summaries/export, while unavailable
automatic references are supplied to synthesis as limitations.

Only active workers retain bodies (at most eight, default four, each response capped
at 8 MiB). Global outcomes and lookahead do not hold page bodies. Full text is staged
temporarily in `.enrichment-work` under the selected stage directory because all source links are downloaded
before synthesis; it is hash-verified on read and removed after successful enrichment.
The five JSON stages keep summaries, references, hashes and refresh metadata, not
base64 archives. One OS lease guards JSON writers, each page/retirement is saved
atomically, and batches of 5-10 targets checkpoint remaining work. Create
`$StageDir\.enrichment-work\stop` to request a safe stop; remove that explicit stop signal
before resuming the same stages. Repeated commands validate/reuse completed input
revisions rather than regenerate their summaries. Concurrent manual edits cause a
guard failure rather than being overwritten.

The new path is opt-in. The existing scheduled workflow still calls the SQLite
refresh command below; that command refuses to overwrite a catalog already exported
by the new JSON pipeline. Switching scheduled synthesis requires separately configuring
the adapters and workflow rather than silently publishing feed-only replacements.

#### Convert existing SQLite data

The read-only converter publishes a **new directory** containing five JSON stages
plus the website projection (six JSON files total):

```powershell
$DbDir = "data\pipeline"
$SourceCatalog = "data\retirements.json"
$StageDir = "data\converted" # Must not already exist.
python -m scripts.convert_enrichment --db-dir $DbDir --catalog $SourceCatalog --output-dir $StageDir --dry-run
```

Use the **completed enrichment's** database directory and matching catalog if it
ran in another worktree; the paths above are defaults, not instructions to convert
an older snapshot instead. Inspect the dry-run report, resolve blockers, then run:

```powershell
python -m scripts.convert_enrichment --db-dir $DbDir --catalog $SourceCatalog --output-dir $StageDir
if ($LASTEXITCODE -ne 0) { throw "Conversion failed; leave the live catalog unchanged." }
python -m scripts.enrichment merge --data-dir $StageDir
if ($LASTEXITCODE -ne 0) { throw "Merge failed; leave the live catalog unchanged." }
python -m scripts.enrichment status --data-dir $StageDir
```

This merge is offline and retains unchanged imported answers. Do not run
`discover`, `download`, `enrich` or `run` merely to complete the conversion.
Inspect `retirements_canonical.json` as the reconciled review view; the converter
also writes the website projection from that view.

Drain the SQLite writer first. All five stores must exist, pass read-only checks,
and stay unchanged throughout conversion; `.lock`, hot journals and WAL files block
conversion rather than being removed. The optional `--catalog` checks that the current
website catalog agrees with the database composition. If it differs, reconcile that
content first. Omitting it converts the stores, not external JSON edits.

Schema-version-1 stores with extra populated workflow tables report them under
`unmappedAuxiliaryTables`; publication is blocked by default. Inspect the dry-run
report before using `--allow-unmapped`, which explicitly leaves those auxiliary
tables (for example, unfinished research journals) only in the retained databases.
It does not claim that pending workflow work was migrated.

The converter never modifies or deletes the SQLite files and never overwrites an
existing destination. Source-file hashes are reported and verified before publication.
`--dry-run` validates in temporary staging without publishing a destination. Review
the converted directory before choosing whether to point the website at its
`retirements.json`; the live catalog is not switched automatically.

Canonical records, IDs, hidden/absent records, curated answers and unknown record
fields are preserved. Manual database fields remain separate under
`retirement_enrichment_manual.json` → `recordOverrides`, then are composed using the
same field-level rules. These raw field patches are for preserving existing manual
data, unlike `inputs` which holds new links/context to synthesize. Untouched imported
records can be merged offline without rewriting their answers. A small compatible
`enrichmentPipeline: "json-v1"` catalog marker prevents accidental SQLite refresh.

Imported page metadata retains URLs, ETags, Last-Modified, raw hashes and failures,
but **no downloaded bodies or base64 page archives are copied**. Canonical answer
snapshots are retained for lossless conversion, so existing long answers are not
silently shortened. On subsequent enrichment they can be replaced by properly
synthesized summaries. Conversion is a format change, **not an indication that the
data is old**: recorded download times, source update times, validators, approvals
and provenance are carried forward. Imported pages are labelled `imported` with
`origin: "sqlite-import"` on retirement summaries. They can be merged offline
without downloading again; conversion itself performs no new fetch or review.
If acquisition inputs later change, process those changes before merging.

Non-Azure discoveries already present stay in the converted website catalog and are listed
in `retainedOutsideDiscovery`. They are **not** silently relabelled as user-provided
source links. Add any intended future sources explicitly to the manual source JSON.

#### Build from the converted catalog

After conversion and offline merge succeed, review `$StageDir\retirements.json`.
Keep all catalog writers stopped and reconcile any local catalog edits before
replacing the website input. The following **explicit adoption step** backs up the
current website catalog outside the checkout, then replaces it with the converted
catalog. It does not modify or delete the source databases:

```powershell
$Backup = Join-Path $env:TEMP ("retirements-before-adoption-" + (Get-Date -Format "yyyyMMdd-HHmmssfff") + ".json")
Copy-Item -LiteralPath "data\retirements.json" -Destination $Backup -ErrorAction Stop
Copy-Item -LiteralPath "$StageDir\retirements.json" -Destination "data\retirements.json" -ErrorAction Stop
python site\build.py
if ($LASTEXITCODE -ne 0) { throw "Site build or validation failed; do not publish docs." }
```

`site\build.py` prepares the data, renders all pages, copies the merged download and
runs `scripts.check_site`. To preview the completed build:

```powershell
python -m http.server 8000 --bind 127.0.0.1 --directory docs
```

Open **http://localhost:8000/**. Building does not commit, push or deploy. For code
changes, also run `python -m unittest discover -s tests -q`. Do not run
`scripts.refresh_data` on the converted catalog; use the JSON stages above for
future refreshes and keep `$StageDir` pointed at the same stage files.

### Existing SQLite refresh and enrichment

The following commands describe the retained SQLite pipeline. Refreshing is optional for local development:

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
    retirements.json        Website-schema projection generated from the canonical view
    retirement_source_automatic.json     Azure Updates sources (default JSON stage location)
    retirement_source_manual.json        Explicitly supplied retirement sources
    retirement_enrichment_automatic.json Five-question automatic summaries and refresh metadata
    retirement_enrichment_manual.json    Manual links/context, summaries and field overrides
    retirements_canonical.json           Composed records, source/input revisions, catalog metadata
    converted\              Optional converted five-file stage directory; use --data-dir consistently
    pipeline\               Existing raw.sqlite, extracted.sqlite, web_cache.sqlite, canonical.sqlite, manual.sqlite
  scripts\
    enrichment.py           JSON discovery, acquisition, synthesis, merge and status commands
    enrichment_json.py      Guarded JSON writes, writer lease and transient text handling
    enrichment_http.py      Bounded page retrieval and content/reference extraction
    convert_enrichment.py   Read-only SQLite-to-JSON conversion into a new directory
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

This scheduled job still uses `scripts.refresh_data`, not the JSON enrichment
pipeline or its adapters. After adopting a JSON-pipeline catalog it intentionally
fails rather than replacing enriched answers. Disable the scheduled refresh or
configure a separately approved JSON workflow with real synthesis/MCP adapters;
conversion does not switch the schedule automatically.

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

`announcedOn` is the UTC calendar date from Microsoft's per-announcement `created` timestamp, displayed as **Announced**; it records when the announcement was published. Missing values remain `null`, and dates are not inferred from announcement text. `lastUpdatedOn` is the UTC calendar date from Microsoft's per-announcement `modified` timestamp, displayed as **Last updated**. It is not the publication date, deadline, or retrieval time. Missing timestamps produce `null` and **Not provided by source**; malformed timestamps fail refresh. Catalog-level `retrievedAt` is the snapshot time, updated by a feed refresh or changed merged content; individual page download/check times remain in the stage metadata. Conversion preserves the recorded timestamps.

`categories` comes from official `productCategories`, not guessed service names. Multi-category announcements appear under each applicable category but count once in directory totals. Missing categories, including on older protected records, use **Uncategorized** without modifying the record.

Navigation uses the exact deadline's year, otherwise the stated year of a valid source month, otherwise **Unconfirmed year**. It never uses the announcement year or invents an exact date from a month.

### Protecting manual enrichments

For the JSON workflow, associate links/context with the existing retirement ID in
`retirement_enrichment_manual.json` → `inputs`. Explicit summary/question/deadline
overrides belong to that input's `overrides`. Converted partial website-field patches
remain separately in `recordOverrides`; automatic summaries remain underneath.
See the [JSON workflow examples](#json-enrichment-pipeline). Do not write new manual
data to SQLite after switching to JSON stages.

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
additional required step for JSON enrichment or conversion.

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

Design/testing uses **one runtime-selected visible, editable record**, never a named prompt example; test writes use isolated copies unless local migration/promotion is approved. An explicit request to refresh feeds and enrich everything selects **full enrichment**, not a test or the previous subset. Full enrichment refreshes both complete discovery feeds, freezes the complete target manifest, orchestrates every eligible record (including prior reviews) at maximum available runtime parallelism within host/page limits, then serially integrates database results and exports composed JSON. It must finish with `python -m unittest discover -s tests -q`, `python site\build.py` and `python -m scripts.check_site` to update the site; no separate rebuild request is needed. Hidden content/manual overrides remain protected. Batch/page limits affect throughput, not coverage; pending/blocked IDs mean incomplete work, with regular coverage reports and resumable accepted results. The selected-record CLI is not a full-run orchestrator; the implementation gates below still apply.

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

**Guards:** extraction skips matching source hash/version; changed bodies invalidate approval, validator-only changes do not. Required-source failures retain last-good bodies but block promotion. Authenticated portals and uncited resources explicitly checked as `not-evidence` or `unavailable` remain in the catalog with skip reasons, without fetching or claiming freshness; required citations cannot use this exemption. Missing/stale dependencies, approvals or concurrent JSON edits stop export. Offline no-ops preserve DB/JSON bytes; export uses the complete composed catalog and can recreate missing JSON.

**Storage/safety:** public Microsoft HTTPS only, redirect/address checks, bounded size/time/retries, no credentials/tenant access/crawling; portals are classified without fetching. `.lock` serializes writers: inspect the owning PID before removing a crash-left lock. Close DELETE-journal SQLite connections before Git; ignore only lock/sidecars, never text-merge binary DB conflicts.

**Renaming old caches:** with connections closed, rename `links.sqlite` to `web_cache.sqlite`. If both exist, reconcile without overwriting either; the CLI refuses legacy names rather than creating an empty replacement. The tracked rename preserves cached bytes.

Full Lifecycle discovery, automatic matching/hash IDs, parallel orchestration, scheduling and publication remain unimplemented/gated. Legacy refresh reads the manual store but does not refresh the other databases.

### Parallel enrichment design (not implemented)

This earlier SQLite orchestration proposal separates concurrent research from
serialized publication; it is not the new JSON CLI's bounded download pool:

```text
Complete baseline -> coordinator queue -> bounded workers on disjoint record IDs
                            |                         |
                     shared fetch/cache        private guarded proposals
                            |                         |
                            +--> one integrator -> canonical.sqlite -> JSON -> build/audit
```

Workers get disjoint leased IDs, immutable inputs and private proposal paths. The coordinator owns deduplicated shared fetching, host/retry/page limits and all shared writes; proposals carry attempt tokens, original record/evidence hashes, citations and validation. Changed targets/evidence require renewed review; unrelated changes can be reconciled only after verifying the target/dependencies, retaining original guards. Durable outcomes allow safe restart without duplicate application or lost coverage.

All eligible records, prior reviews and protected outcomes remain accounted for; tests use one live example plus synthetic concurrency fixtures. Lease expiry, late results, stale guards, interrupted export recovery, scheduler/proposal reconciliation and concurrency tests remain implementation gates for this SQLite proposal. **Do not run the SQLite CLI concurrently against one `--db-dir` or merge worker database binaries.**

### Weekly Copilot cloud automation

**No cloud automation is created/enabled.** The last capability check reported it disabled/unavailable; the prompt grants neither tools nor schedules, and daily GitHub Actions refresh is unchanged.

When access is available, obtain separate approval for one personal automation, its activation/initial run and publication. Discover supported tools/triggers; grant only public-document retrieval, repository access and required execution. Set weekly day/time in UTC through structured schedule fields, not prompt text. Leave a reviewable diff unless publication is authorized.

Follow the current prompt's input, depth, refresh, coverage and recovery rules.
Before publication reconcile with main and rebuild. The SQLite refresh command is
not a JSON-stage refresh. Never overwrite/force-push over concurrent refreshes.

### Retirement discovery scope

The JSON workflow has exactly two discovery inputs:

| Stage | Discovery input | Coverage |
| --- | --- | --- |
| `retirement_source_automatic` | [Azure Updates JSON collection](https://www.microsoft.com/releasecommunications/api/v2/azure) filtered to `Retirements` | Every validated feed page, preserving official IDs and timestamps. |
| `retirement_source_manual` | Retirement links explicitly supplied by the user | Every supplied record/link, preserving its ID and source association. |

There is no independent Microsoft Lifecycle crawl, search-driven discovery, combined
feed requirement or automatic hash-ID migration in the new process. Lifecycle,
Learn and other pages may be processed when explicitly supplied or reached through
permitted depth-one references; references do not automatically create retirements.

Conversion preserves existing non-Azure records without inventing user input.
Existing IDs and manual content remain intact; similar titles or dates alone never
authorize combining events. See [the workflow](#json-enrichment-pipeline) for commands.

### Azure Updates feed and website output

The automatic discovery source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)); explicitly supplied links form the separate manual discovery input. Feed acquisition fetches every page tagged `Retirements`, checks the reported count and unique IDs, and publishes discovery state only after a complete fetch. Source IDs remain unchanged in the catalog and disambiguate duplicate title slugs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap, and endpoint changes cause refresh to fail rather than silently publishing an incomplete directory.

The structured feed supplies a retirement **month**, not an exact day. Before enrichment, feed normalization extracts exact dates conservatively from current announcement **titles** only when a single distinct, valid date appears; ISO dates require explicit deadline wording to distinguish deadlines from API versions. Enrichment may instead use explicit retirement-specific dates in the permitted announcement/reference content. Neither path infers deadlines from publication dates, IDs or URL slugs. Month-only and unresolved deadlines remain **Date to confirm** and do not count as upcoming or retired. **Within 90 days** includes today and day 90 UTC; **Upcoming** includes that group.

Source HTML becomes escaped plain text plus separate HTTPS references. Automatic enrichment supplies safe HTML for all five answers; manual plain edits may use the escaped fallback. Allowed tags: `p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, `br`; reject attributes/active content and escape text. Preserve facts/limits, use concise semantic paragraphs/lists, convert newline escapes, and avoid duplicated dates/notices/support/tracking. Verify tenant impact, pricing, support and phased deadlines with Microsoft.

Site-wide typography uses four primary sizes: .875rem body text and controls (14px at the default browser size), 1rem subheadings (16px), 1.125rem section headings and summary counts (18px), and 1.375rem page titles (22px). Navigation, filters, cards, notices, metadata, and footers use the same body size and 1.6 line spacing on desktop and mobile. The only caption-size exception is the main timeline's customer lead-time label and duration at .75rem (12px); retirement dates and detail-page lead times retain the body size. Relative units respect browser font preferences. Headings retain their hierarchy, and semantic emphasis, code fonts, and notice colors remain distinct.
