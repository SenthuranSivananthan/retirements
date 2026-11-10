# Azure Retirements

A static, searchable TypeScript web app for Microsoft Azure retirement announcements, built with Vite and designed for GitHub Pages. Its Azure-blue palette, Segoe typography, full-width hero, and light/dark themes follow the visual direction of [Multi-region platform](https://azure.github.io/multi-region-platform/).

## Run locally

### Prerequisites

Install **Node.js 22.12 or newer** with npm, and Git if cloning the repository. CI uses Node.js 22. Run all commands below from the repository root.

The checked-in catalog makes local development and builds possible without contacting Microsoft. There is no backend, Azure login, API key, or environment file to configure. Installing dependencies requires access to the npm registry; refreshing the catalog separately requires access to Microsoft's public feed.

### Start the development server

```sh
git clone https://github.com/SenthuranSivananthan/retirements.git
cd retirements
npm ci
npm run dev
```

If you already have a checkout, start with `npm ci` in its root. Open the URL printed by Vite, normally **http://localhost:5173**. Vite reloads the app as you edit its source. Stop the server with `Ctrl+C`.

On Windows PowerShell, if execution policy blocks `npm.ps1`, use `npm.cmd` in place of `npm` in these commands.

### Check changes and preview the production build

```sh
npm test
npm run build
npm run preview
```

Open the preview URL printed by Vite, normally **http://localhost:4173**. `npm run build` performs strict TypeScript checking before generating `dist`; `npm run dev` does not replace that check. Rebuild after source or catalog changes before previewing again.

Use the development or preview server rather than opening `index.html` directly: the app loads its catalog over HTTP. The preview server is for local verification; GitHub Pages serves the generated static site in production.

### Refresh or enrich the catalog

Refreshing data is optional for local development:

```sh
npm run refresh-data
npm test
npm run build
```

The refresh fetches all official retirement announcements and updates `data/retirements.json`, preserving records marked `manuallyEnriched: true`. To curate an announcement, edit its five question sections, set that flag, and commit the JSON changes as described in [Protecting manual enrichments](#protecting-manual-enrichments). Do not edit the generated catalog in `dist`.

If a refresh fails, the previous snapshot stays intact. Resolve the reported source, network, or local-data error before retrying; a refresh is not required just to run the app with its checked-in data.

### Command reference

| Command | Purpose |
| --- | --- |
| `npm ci` | Install the exact dependency versions in the lockfile |
| `npm run dev` | Start Vite's development server |
| `npm test` | Run Node's test runner through `tsx`, without Azure or network access |
| `npm run typecheck` | Check TypeScript without emitting files |
| `npm run build` | Type-check and create the static site in `dist` |
| `npm run preview` | Serve the existing production build locally |
| `npm run refresh-data` | Refresh the source catalog while preserving manual enrichments |

## Project structure

```text
retirements
  .github\
    workflows\
      pages.yml             Validation, source refresh, and Pages deployment
  data\
    retirements.json        Checked-in, question-organized catalog
  scripts\
    feed.mjs                Source parsing, normalization, pagination, protected merging
    refresh-data.mjs        Refresh entry point and guarded atomic snapshot writer
  src\
    main.ts                 App shell, navigation, filters, details, and local progress
    catalog.ts              Validation, grouping, filtering, dates, and countdowns
    data.ts                 Catalog loading and downloadable asset URL
    types.ts                Shared catalog, question, and filter types
    style.css               Themes, layout, and responsive styles
  tests\
    catalog.test.js         Search, statuses, dates, countdowns, and safe rendering helpers
    feed.test.js            Source parsing, normalization, and complete pagination
    navigation.test.js      Retirement-year/category grouping, filters, and URLs
    refresh.test.js         Manual-enrichment preservation and snapshot publishing
    schema.test.js          Runtime catalog validation
    snapshot.test.js        Checked-in catalog integrity and provenance
  index.html                Browser entry point loading src\main.ts
  package.json              npm commands and development dependencies
  package-lock.json         Locked dependency versions
  tsconfig.json             Strict, no-emit TypeScript configuration
  vite.config.ts            Vite configuration with relative asset paths
  dist\                     Generated production output; ignored by Git
  node_modules\             Installed dependencies; ignored by Git
```

Browser code is TypeScript; the refresh scripts remain Node.js ES modules. Tests are JavaScript ES modules and use `tsx` to exercise TypeScript directly. The browser validates catalog JSON before rendering it. Vite publishes the JSON as a separate asset, and the same catalog powers both the UI and the download.

For UI changes, start in `src\main.ts` and `src\style.css`. Keep reusable catalog behavior in `src\catalog.ts` and its data contracts in `src\types.ts`. For source ingestion or refresh changes, use `scripts` and the feed/refresh tests. Change curated content in `data\retirements.json`, not in generated output.

## Publish on github.io

1. In this repository's **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source.
2. Merge these changes into `main`. The **Validate and deploy GitHub Pages** workflow tests, refreshes the catalog, builds, and deploys the site.
3. Open **https://senthuransivananthan.github.io/retirements/**.

Pull requests run tests and build only, without deployment privileges. A daily scheduled run and **Run workflow** also refresh and deploy from `main`. A failed refresh fails deployment, leaving the previous live site intact. Scheduled runs do not commit data changes; the deployed artifact includes the freshly fetched catalog. To update the checked-in snapshot, run `npm run refresh-data` locally and commit the result.

Assets use relative paths. Detail URLs use hash routing (for example, `#/retirements/575106`), so sharing or reloading a retirement page works under the project subdirectory without server rewrites.

## Explore and plan

- Search titles and announcement text; combine service and status filters.
- Sort by announcement date, retirement date, or title; load more to browse the complete catalog.
- Share filtered URLs or download the complete JSON catalog.
- Use the header search from any page (`Ctrl+K` or `Cmd+K`), and open the Downloads menu for the JSON catalog.
- Expand the sidebar by **retirement year → Azure service category → retirement**. Years appear newest first, followed by **Unconfirmed year**. Each year and category also links to its filtered directory; status shortcuts and official resources remain available. On small screens, use the navigation button; click the backdrop or press Escape to close it.
- Year/category filters combine with search, service, status, and sorting, remain in shareable URLs, and can be cleared independently. Detail links from the tree retain their year/category context for returning to the directory.
- Jump between detail sections using the **In this article** navigation.
- Each detail page prominently shows the whole days remaining until its exact retirement date, calculated using UTC calendar days. Deadlines today say **Retires today (0 days remaining)**; past dates say **Retired**. Records without an exact date show **Retirement date to confirm**, without inventing a countdown from a month-only deadline.
- Every retirement detail page contains these sections, in order:
  1. **What is changing?** — official announcement text and financial considerations.
  2. **What do I need to do?** — migration resources and support options.
  3. **Where, and how much, am I impacted?** — inventory guidance and Azure Advisor.
  4. **What is the deadline?** — known dates, uncertainty, and consequences.
  5. **How can I track progress?** — a browser-local planning checklist.

Checklist progress is per announcement and saved only in the current browser's local storage. It is not a resource assessment or a shared migration tracker. Theme preferences also stay in the browser; the app has no analytics.

## Data provenance and limitations

### Question-organized JSON

`data/retirements.json` and the catalog download use `schemaVersion: 2`. Each record keeps its ID, title, services, Azure service categories (`categories`), announcement date (`announcedOn`), last updated date (`lastUpdatedOn`), summary, and source URL as metadata. Its answers live under exactly five `questions` keys, in this order:

| Key | Question | Organized content |
| --- | --- | --- |
| `what` | What is changing? | Official announcement text and separate financial considerations |
| `actions` | What do I need to do? | Official recommended action (nullable), planning guidance, announcement resources, and support |
| `impact` | Where, and how much, am I impacted? | Service-specific inventory guidance, impact checklist, tenant-access limitations, and Azure Advisor |
| `deadline` | What is the deadline? | Nullable exact `date`, source `month`, date uncertainty, and consequences |
| `progress` | How can I track progress? | Planning guidance, checklist steps, and browser-storage limitations |

Every section includes its full `question` text and an `introduction`. The detail page and article navigation read these answers and headings from JSON rather than keeping a separate set in the UI. Refreshing the source regenerates the same structure for every announcement. The loader rejects catalogs missing a section or containing malformed answers.

Version 2 replaces the old flat `details`, `actions`, `links`, `retirementDate`, and `retirementMonth` fields with `questions.what.announcement`, `questions.actions.recommendedAction`, `questions.actions.resources`, `questions.deadline.date`, and `questions.deadline.month`. Source announcement content remains distinct from general planning guidance; tenant-specific impact and actual team progress are not inferred or written into the catalog.

`lastUpdatedOn` is the UTC calendar date (`YYYY-MM-DD`) from Microsoft's per-announcement `modified` timestamp, displayed as **Last updated** in the retirement facts. It is not the publication date, retirement deadline, or catalog retrieval time. If the source omits the timestamp, the field is `null` and the UI says **Not provided by source**; a malformed timestamp fails the refresh. The catalog-level `retrievedAt` separately records when the complete feed was fetched.

`categories` comes from Microsoft's official `productCategories`, not guessed from service names. Multi-category announcements appear under each applicable category but count only once in their year and directory results. Missing source categories use **Uncategorized**; older manually enriched records may omit this metadata and use the same fallback without being modified.

Navigation uses the year of `questions.deadline.date`, or the stated year of a valid source `questions.deadline.month` when no exact date is available. It never uses the announcement year. If neither supplies a retirement year, the record appears under **Unconfirmed year**. Grouping a month-only deadline by year does not invent an exact date or change its **Date to confirm** status.

### Protecting manual enrichments

Every retirement includes a boolean `manuallyEnriched`, initially `false`. When editing a record's answers or adding custom information, set `"manuallyEnriched": true` on that record and commit the JSON changes. Both scheduled automation and `npm run refresh-data` preserve that entire record, including custom fields and its recorded `lastUpdatedOn`. A protected record is retained even if its ID disappears from the source feed.

Unflagged records continue to refresh, and new announcements are added with `manuallyEnriched: false`. Set the flag back to `false` to resume source updates for a record; its custom content will then be replaced on the next successful refresh. Keep the five-question structure and valid field types when enriching records.

The refresh reads the existing snapshot after fetching the feed, so edits saved during the fetch are included in the merge. Invalid flags, duplicate IDs, malformed snapshots, and detected file changes during publishing fail the refresh instead of replacing existing data. The GitHub Actions workflow uses the checked-in JSON as its enrichment baseline; changes made only to a deployed artifact are not durable.

### Official source

The source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)). The refresh fetches **every page** tagged `Retirements`, checks the reported count and unique IDs, and replaces `data/retirements.json` only after a complete fetch. Source IDs remain stable in detail URLs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap. The public endpoint's schema may change; a refresh fails rather than silently publishing an incomplete directory.

The feed's structured retirement timing specifies a **month**, not an exact day. Automatically normalized exact dates are extracted conservatively from current announcement **titles** only when a single distinct, valid date appears. ISO dates require explicit deadline wording, so API version identifiers are not mistaken for retirement dates. Publication dates, IDs, URL slugs, and body dates are never used as deadlines. Month-only or ambiguous deadlines remain **Date to confirm** and are excluded from upcoming/retired counts. They remain searchable; detail pages preserve the source month when available. The **Within 90 days** status includes today and day 90 (UTC). **Upcoming** includes that group.

Announcement HTML is parsed into plain text; related HTTPS links are retained separately. The app escapes source text instead of rendering source HTML. Each page links to the official announcement. General planning advice is distinguished from source content, and tenant-specific impact, pricing, support, and phased deadlines must be verified with Microsoft.