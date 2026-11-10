# Azure Retirements

A static Jekyll site for Microsoft Azure retirement announcements, with TypeScript enhancements for search, filters, live countdowns, themes, and saved checklists. Its Azure-blue palette, Segoe typography, full-width hero, and light/dark themes follow the visual direction of [Multi-region platform](https://azure.github.io/multi-region-platform/).

Jekyll renders the directory, shared navigation, and a complete HTML page for every retirement. Retirement content and navigation remain available without JavaScript; interactive features require it.

## Run locally

### Prerequisites

Use **Ruby 3.3**, **Node.js 22 or newer** (including npm), **Git**, and **Bundler 2.5.23**. CI uses Ruby 3.3 and Node.js 22; the Bundler version matches `Gemfile.lock`.

The checked-in catalog makes local development and builds possible without contacting Microsoft. There is no backend, Azure login, API key, or environment file to configure. Initial installation requires access to npm and RubyGems; refreshing the catalog separately requires access to Microsoft's public feed.

#### Windows

1. Install [Git for Windows](https://git-scm.com/downloads/win), keeping the option that makes Git available from the command line.
2. Install Node.js 22 or a newer LTS version from the [official Node.js downloads](https://nodejs.org/en/download). Include npm and add Node.js to `PATH`.
3. Install **Ruby+Devkit 3.3**, not the Ruby-only package, from [RubyInstaller](https://rubyinstaller.org/downloads/). Enable the option to add Ruby executables to `PATH`.
4. Run `ridk install` at the end of the installer, or from PowerShell afterward, and select **MSYS2 and MINGW development toolchain**. This installs the compiler and tools needed by native Ruby gems.
5. Open a new PowerShell window so the updated `PATH` takes effect, then continue with the dependency installation below.

The Gemfile includes `tzinfo` and `tzinfo-data` for Windows; Bundler installs them to support the site's UTC timezone. For additional platform troubleshooting, see [Jekyll on Windows](https://jekyllrb.com/docs/installation/windows/). If using WSL instead, install Git, Node.js, and Ruby inside WSL and run all project commands there rather than mixing Windows and Linux runtimes.

#### macOS

Install the Apple command-line tools with `xcode-select --install`, then install [Homebrew](https://brew.sh/) if needed. Install the project runtimes:

```sh
brew install git node@22 ruby@3.3
export PATH="$(brew --prefix ruby@3.3)/bin:$(brew --prefix node@22)/bin:$PATH"
export PATH="$(ruby -r rubygems -e 'puts Gem.bindir'):$PATH"
```

Persist the equivalent `PATH` setup in your shell profile. Use the Homebrew Ruby rather than macOS's system Ruby; the second export also makes installed gem executables such as `bundle` available.

#### Linux (Ubuntu / Debian, including Ubuntu on WSL)

The commands below assume Bash and a fresh user setup. If you already manage Ruby or Node.js with a version manager, use it to select Ruby 3.3 and Node.js 22 instead of installing another manager.

Install Git, download tools, and the native build prerequisites:

```sh
sudo apt-get update
sudo apt-get install -y git curl ca-certificates build-essential autoconf bison \
  libssl-dev libyaml-dev zlib1g-dev libffi-dev libreadline-dev libgdbm-dev \
  libgmp-dev pkg-config python3
```

Install [rbenv and ruby-build](https://github.com/rbenv/rbenv#installation), then build and select the latest stable Ruby 3.3 patch release. This also installs the matching Ruby headers needed by native gems:

```sh
git clone https://github.com/rbenv/rbenv.git "$HOME/.rbenv"
git clone https://github.com/rbenv/ruby-build.git "$HOME/.rbenv/plugins/ruby-build"
export PATH="$HOME/.rbenv/bin:$PATH"
eval "$(rbenv init - bash)"

ruby_version="$(rbenv install --list-all | grep -E '^3\.3\.[0-9]+$' | sort -V | tail -n 1)"
rbenv install "$ruby_version"
rbenv global "$ruby_version"
```

Load rbenv automatically in future Bash terminals:

```sh
printf '%s\n' 'export PATH="$HOME/.rbenv/bin:$PATH"' \
  'eval "$(rbenv init - bash)"' >> "$HOME/.bashrc"
```

Install [nvm](https://github.com/nvm-sh/nvm#git-install) and Node.js 22, which includes npm:

```sh
git clone --branch v0.41.0 --depth 1 https://github.com/nvm-sh/nvm.git "$HOME/.nvm"
export NVM_DIR="$HOME/.nvm"
. "$NVM_DIR/nvm.sh"
nvm install 22
nvm alias default 22
```

Load nvm automatically in future Bash terminals:

```sh
printf '%s\n' 'export NVM_DIR="$HOME/.nvm"' \
  '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"' >> "$HOME/.bashrc"
```

Open a new Bash terminal, verify the versions below, and continue with **Install project dependencies**. Do not assume the distribution's default Ruby or Node.js package matches these versions. Use your user-managed Ruby for gem installation rather than `sudo gem install`. On other Linux distributions, install the equivalent compiler, OpenSSL, YAML, zlib, and Ruby build prerequisites using your package manager before following the version-manager steps.

#### Verify the system tools

In the terminal you will use for development, confirm that all commands are available and report the expected versions:

```sh
git --version
node --version
npm --version
ruby --version
gem --version
```

On Windows PowerShell, if execution policy blocks `npm.ps1`, use `npm.cmd` in place of `npm` in these commands and the steps below.

### Install project dependencies

Clone the repository, or change into the root of your existing checkout:

```sh
git clone https://github.com/SenthuranSivananthan/retirements.git
cd retirements
```

Run the following from the repository root:

```sh
gem install bundler --version 2.5.23
bundle --version
npm ci --include=dev
bundle config set --local path vendor
bundle install
```

`npm ci --include=dev` installs the locked Node dependencies, including the build and test tools: TypeScript, `tsx`, and `parse5`. `bundle install` installs the locked Jekyll dependencies, including its local web server and platform-specific gems. You do not need to install TypeScript or Jekyll globally.

The local Bundler configuration installs Ruby gems under `vendor` instead of requiring a system-wide gem installation. Both `vendor` and `.bundle` are ignored by Git. Keep `package-lock.json` and `Gemfile.lock` checked in; do not delete them to resolve installation errors.

Verify the project dependencies:

```sh
bundle check
bundle exec jekyll --version
npm run typecheck
```

After pulling changes to either dependency manifest or lockfile, rerun `npm ci --include=dev` and `bundle install` before starting or building the site.

### Start the development server

From the repository root:

```sh
npm run dev
```

Open **http://localhost:4000**. The development command prepares the catalog and compiled scripts, then serves the Jekyll source in `site` with live reload and an empty base URL. Stop the server with `Ctrl+C`.

Jekyll watches layouts, includes, and CSS inside `site`. After changing TypeScript or the catalog, run `npm run prepare-site` in another terminal to regenerate the scripts, navigation metadata, and retirement documents; Jekyll then rebuilds those changes. Restart the server after changing `site\_config.yml`.

### Check changes and preview the production build

```sh
npm test
npm run build
npm run preview
```

Open **http://localhost:4000/retirements/** with the checked-in production configuration. `npm run build` compiles and checks TypeScript once during preparation, generates static assets and retirement documents, builds Jekyll from `site`, and checks the generated site in `site\_site`. Type errors or unused TypeScript code stop preparation before new browser modules are emitted. Rebuild after source or catalog changes before previewing again.

Use Jekyll's development or preview server rather than opening `site\index.html` directly: source pages contain Liquid templates and front matter, and interactive features fetch their catalog over HTTP. GitHub Pages serves the generated HTML, CSS, JavaScript, and JSON in production.

### Refresh or enrich the catalog

Refreshing data is optional for local development:

```sh
npm run refresh-data
npm test
npm run build
```

The refresh fetches all official retirement announcements and updates `data/retirements.json`, preserving records marked `manuallyEnriched: true`. To curate an announcement, edit its five question sections, set that flag, and commit the JSON changes as described in [Protecting manual enrichments](#protecting-manual-enrichments). Do not edit generated documents, metadata, compiled scripts, or the copied catalog under `site\_generated`, `site\_data`, `site\assets\js`, `site\assets\data`, or `site\_site`.

If a refresh fails, the previous snapshot stays intact. Resolve the reported source, network, or local-data error before retrying; a refresh is not required just to run the app with its checked-in data.

### Command reference

| Command | Purpose |
| --- | --- |
| `gem install bundler --version 2.5.23` | Install the Bundler version recorded in `Gemfile.lock` |
| `npm ci --include=dev` | Install all locked Node dependencies, including build and test tools |
| `bundle config set --local path vendor` | Keep this checkout's installed Ruby gems in the ignored `vendor` folder |
| `bundle install` | Install Jekyll and its Ruby dependencies |
| `bundle check` | Confirm all required Ruby gems are installed |
| `npm run dev` | Prepare assets and start Jekyll with live reload at the site root |
| `npm run prepare-site` | Compile TypeScript and generate Jekyll documents, navigation metadata, and the download |
| `npm test` | Run Node's test runner through `tsx`, without Azure or network access |
| `npm run typecheck` | Check TypeScript without emitting files |
| `npm run build` | Type-check, prepare assets, build Jekyll, and check `site\_site` |
| `npm run check-site` | Verify an existing Jekyll build, including detail pages and local asset links |
| `npm run preview` | Serve the existing production build locally |
| `npm run refresh-data` | Refresh the source catalog while preserving manual enrichments |

## Project structure

```text
retirements
  .github\
    workflows\
      pages.yml             Validation, source refresh, and Pages deployment
  site\                     All website source and generated assets
    _includes\              Shared header, sidebar, cards, links, and footer
    _layouts\               Default, directory, and retirement Liquid layouts
    _generated\             Generated retirement collection; ignored by Git
    _data\site.json         Generated Jekyll view metadata; ignored by Git
    assets\
      css\style.css         Themes, layout, and responsive styles
      js\                   Compiled TypeScript modules; ignored by Git
      data\                 Downloadable catalog copy; ignored by Git
    src\
      main.ts               Progressive search, filters, themes, countdowns, and progress
      catalog.ts            Validation, grouping, filtering, dates, and countdowns
      data.ts               Catalog loading and visible failure reporting
      types.ts              Shared catalog, question, and filter types
    _config.yml             Jekyll collections, deployment URL, and exclusions
    index.html              Directory front matter using the home layout
    404.html                Static not-found page
    tsconfig.json           Strict, no-emit TypeScript configuration
    tsconfig.build.json     Browser module compilation into site\assets\js
    _site\                  Jekyll production output; ignored by Git
  data\
    retirements.json        Canonical catalog shared by ingestion, tests, and the site
  scripts\
    feed.mjs                Source parsing, normalization, pagination, protected merging
    refresh-data.mjs        Refresh entry point and guarded atomic snapshot writer
    prepare-site.mjs        Validated Jekyll documents and view metadata
    check-site.mjs          Generated HTML, page coverage, and local link checks
  tests\
    catalog.test.js         Search, statuses, dates, countdowns, and safe rendering helpers
    feed.test.js            Source parsing, normalization, and complete pagination
    navigation.test.js      Retirement-year/category grouping, filters, and URLs
    refresh.test.js         Manual-enrichment preservation and snapshot publishing
    schema.test.js          Runtime catalog validation
    snapshot.test.js        Checked-in catalog integrity and provenance
    site.test.js            Static document generation and source preservation
  Gemfile                   Jekyll dependency declaration
  Gemfile.lock              Locked Ruby dependency versions
  package.json              npm commands and development dependencies
  package-lock.json         Locked dependency versions
  node_modules\             Installed dependencies; ignored by Git
```

Jekyll owns page rendering; JavaScript enhances the static pages rather than replacing them with a client-side router. TypeScript checks native ES module imports and compiles browser modules without a bundler. Node.js scripts prepare the static collection and metadata using the same validation, grouping, and date helpers as the browser. Tests use `tsx` to exercise those helpers directly. The same canonical JSON powers static pages, interactive filtering, and downloads.

The `site` folder separates all website files from the shared catalog, ingestion scripts, tests, and root-level dependency tooling. npm commands run from the repository root and select the correct Jekyll source, configuration, and destination automatically. The source folder does not add `/site` to public URLs.

Git ignores installed dependencies, generated site files, build caches, and temporary catalog writes. Recreate dependencies with `npm ci` and `bundle install`, and site assets with `npm run prepare-site` or the complete `npm run build`. Keep the dependency manifests and lockfiles, website source, and canonical `data\retirements.json` checked in: the catalog contains the durable baseline for manual enrichments and offline builds.

For markup changes, edit `site\_layouts` and `site\_includes`; for visual changes, edit `site\assets\css\style.css`. Interactive behavior lives in `site\src\main.ts`, reusable catalog behavior in `site\src\catalog.ts`, and data contracts in `site\src\types.ts`. For source ingestion or refresh changes, use `scripts` and the feed/refresh tests. Change curated content in `data\retirements.json`, not in generated output.

## Publish on github.io

1. In this repository's **Settings → Pages → Build and deployment**, select **GitHub Actions** as the source.
2. Merge changes into `main`. The **Validate and deploy GitHub Pages** workflow installs Node.js and Ruby dependencies, refreshes the catalog, tests, builds Jekyll, and deploys `site\_site`.
3. Open **https://senthuransivananthan.github.io/retirements/**.

Pull requests run tests and build only, without deployment privileges. A daily scheduled run and **Run workflow** also refresh and deploy from `main`. A failed refresh fails deployment, leaving the previous live site intact. Scheduled runs do not commit data changes; the deployed artifact includes the freshly fetched catalog. To update the checked-in snapshot, run `npm run refresh-data` locally and commit the result.

Keep **GitHub Actions** as the publishing source rather than **Deploy from a branch**: the workflow must compile TypeScript and prepare the retirement collection before Jekyll runs. The site uses standard Liquid layouts and collections, without custom Jekyll plugins.

`site\_config.yml` sets `url` to `https://senthuransivananthan.github.io` and `baseurl` to `/retirements`. Update both when publishing to a different repository or custom domain; use an empty `baseurl` for a domain-root site. Liquid's `relative_url` filter and the browser's site-root metadata keep assets and links inside that base path.

Each detail has a real static URL, for example `/retirements/retirements/575106/` on the project site (the first `retirements` is the repository base path). Directory filters use ordinary query strings. Existing `#/retirements/<id>` and `#/?...` links are redirected by JavaScript to their new static or query-string URLs, including navigation context.

## Explore and plan

- Search titles and announcement text; combine service and status filters.
- Sort by announcement date, retirement date, or title; load more to browse the complete catalog.
- Share filtered URLs or download the complete JSON catalog.
- Use the header search from any page (`Ctrl+K` or `Cmd+K`), and open the Downloads menu for the JSON catalog.
- Expand the sidebar by **retirement year → Azure service category → retirement**. Years appear newest first, followed by **Unconfirmed year**. Each year and category also links to its filtered directory; status shortcuts and official resources remain available. On small screens, use the navigation button; click the backdrop or press Escape to close it.
- Year/category filters combine with search, service, status, and sorting, remain in shareable URLs, and can be cleared independently. Detail links from the tree retain their year/category context for returning to the directory.
- Jump between detail sections using the **In this article** navigation.
- Each detail page prominently shows the whole days remaining until its exact retirement date, calculated using UTC calendar days. Deadlines today say **Retires today (0 days remaining)**; past dates say **Retired**. Records without an exact date show **Retirement date to confirm**, without inventing a countdown from a month-only deadline. Jekyll renders a build-time value; JavaScript refreshes it when the page loads and when the UTC date changes.
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

Every section includes its full `question` text and an `introduction`. Jekyll's detail layout and article navigation read these answers and headings from prepared JSON rather than keeping a separate set in the UI. Refreshing the source regenerates the same structure for every announcement. Both site preparation and browser loading reject catalogs missing a section or containing malformed answers.

Source announcement content remains distinct from general planning guidance; tenant-specific impact and actual team progress are not inferred or written into the catalog.

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