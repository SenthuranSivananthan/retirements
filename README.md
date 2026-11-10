# Azure Retirements

A static, searchable directory of Microsoft Azure retirement announcements, designed for GitHub Pages. Its Azure-blue palette, Segoe typography, side navigation, and light/dark themes follow the visual direction of [Multi-Region Platform](https://github.com/SenthuranSivananthan/multi-region-platform).

## Run locally

Requires Node.js 22.12 or newer.

```sh
npm ci
npm run dev
```

```sh
npm test              # Node's built-in test runner; no Azure/network access needed
npm run build        # Static output in dist/
npm run preview      # Preview the production build
npm run refresh-data # Fetch all official retirement announcements
```

The checked-in catalog makes local builds reproducible without contacting Microsoft. There is no backend, Azure login, or browser-to-Microsoft API dependency.

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
- Every retirement detail page contains these sections, in order:
  1. **What is changing?** — official announcement text and financial considerations.
  2. **What do I need to do?** — migration resources and support options.
  3. **Where, and how much, am I impacted?** — inventory guidance and Azure Advisor.
  4. **What is the deadline?** — known dates, uncertainty, and consequences.
  5. **How can I track progress?** — a browser-local planning checklist.

Checklist progress is per announcement and saved only in the current browser's local storage. It is not a resource assessment or a shared migration tracker. Theme preferences also stay in the browser; the app has no analytics.

## Data provenance and limitations

The source is Microsoft's public [Azure Updates JSON feed](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)). The refresh fetches **every page** tagged `Retirements`, checks the reported count and unique IDs, and replaces `data/retirements.json` only after a complete fetch. Source IDs remain stable in detail URLs.

This is the complete tagged announcement collection returned by that feed, **not a guarantee that every Azure lifecycle obligation is represented**. Announcements may overlap. The public endpoint's schema may change; a refresh fails rather than silently publishing an incomplete directory.

The feed's structured retirement timing specifies a **month**, not an exact day. Exact dates are extracted conservatively from current announcement **titles** only when a single distinct, valid date appears. ISO dates require explicit deadline wording, so API version identifiers are not mistaken for retirement dates. Publication dates, IDs, URL slugs, and body dates are never used as deadlines. Month-only or ambiguous deadlines remain **Date to confirm** and are excluded from upcoming/retired counts. They remain searchable; detail pages preserve the source month when available. The **Within 90 days** status includes today and day 90 (UTC). **Upcoming** includes that group.

Announcement HTML is parsed into plain text; related HTTPS links are retained separately. The app escapes source text instead of rendering source HTML. Each page links to the official announcement. General planning advice is distinguished from source content, and tenant-specific impact, pricing, support, and phased deadlines must be verified with Microsoft.