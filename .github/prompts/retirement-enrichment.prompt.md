---
description: Design or run the mode-scoped, evidence-backed retirement enrichment pipeline.
---

Maintain `SenthuranSivananthan/retirements` using README and the five-question/`sourceReview` contract in `scripts\catalog.py`. Apply the selected mode and the shared rules below; do not execute every stage unconditionally.

## Pipeline entry point

**Current phase: design/testing.** Choose one existing retirement at run time; never name a preferred product/title/ID here. Full enrichment always covers all records without sampling. Design/testing authorizes no whole-feed pull, ID migration, automation or publication. This is an agent-run process, not a crawler or schedule.

**Implemented:** selected-record SQLite stages, a separate manual-content store, composed JSON export; legacy refresh fetches Azure Updates only and reapplies stored manual fields. **Proposed:** whole-feed parallel discovery/enrichment, matching, hash IDs/registry and consumer migrations. Implement/test these before a combined run. Retrieval, migration and publication need explicit approval; a one-record test never substitutes for full coverage.

| Mode | Stages and permitted changes |
| --- | --- |
| Design/testing | Revise prompt/README from existing research; design-only work executes nothing. Requested tests use one visible, editable record under the isolation rules below. |
| Full enrichment | After implementation/data-pull approval, run stages 1-12: discover once, preserve the first combined baseline, review every visible record including prior reviews, using bounded parallel workers and serial integration. Account for protected records; never sample. |
| Date-only corrections | No discovery/new evidence. Audit stored evidence, including exact dates; stages 5-10 change only deadlines, `deadlineSource` and dependent explanations. Preserve unrelated answers, order, original evidence, timestamps, review day/status, flags and resources. No refresh/rewrite. |
| Readability-only | No discovery/research/date adjudication. Reformat reviewed automatic answers in stages 7-10; preserve facts, dates, citations/review metadata and all manual overrides. Report unreviewed records. |

### Shared preservation and run control

- Hidden content remains unchanged. User-supplied fields live in `manual.sqlite`; research edits the automatic baseline only and cannot overwrite manual data. Export reapplies supplied fields, not whole-record protection. The deprecated `manuallyEnriched` flag is absent from records.
- First combined discovery preserves every existing record and all content/metadata. Protected/absent-from-source records remain identical JSON values; put new observations in artifacts. Only approved ID migration may change identity/aliases; never auto-consolidate curated duplicates.
- Automatic review status is not refresh protection. Legacy refresh replaces automatic feed content but reapplies manual fields; future full replacement needs an explicit execution choice. Preserve manual snapshots for retirements absent from fresh feeds.
- Record the complete post-discovery target set, including prior reviews. Account for each ID: changed/audited-no-change, protected, pending or blocked/failed. No record cap; **80 distinct public documentation pages maximum per review batch**. Queue limits affect dispatch only. Filter completed IDs/widen repeated same-day selections; neither zero unreviewed records nor review dates prove coverage. Any pending/blocked/failed target prevents full completion.
- Resume from current catalog/run state, reconcile concurrent changes and reuse discovery; never refresh away completed work. Use disjoint worker IDs, immutable inputs and serial guarded integration; no concurrent canonical edits or blind file replacement.
- Content modes edit canonical data, generated copies and artifacts only. Code, dependencies, templates/CSS, workflows or prompt changes require authorization. Generated output is never the source.

## Incremental local databases and stage execution

Commit **five SQLite files in `data\pipeline`**; export JSON afterward. Accept binary diffs; use standard-library SQLite, versioned schemas, transactions, DELETE journaling and closed connections before Git. Ignore sidecars/locks; no secrets/authenticated responses/local logs, automatic vacuum or unchanged-value churn. Close/rename legacy `links.sqlite` to `web_cache.sqlite`; reconcile both without overwrite if necessary. The CLI refuses legacy names rather than silently creating an empty cache.

| Store / output | Contents and stage contract |
| --- | --- |
| `raw.sqlite` | Exact Azure Updates JSON/Lifecycle HTML, keys, URLs, hashes and target associations. Commit selected source bytes atomically only after both succeed; interpretation stays separate. |
| `extracted.sqlite` | Original per-source identities/titles/URLs, announcement/resources, provisional dates, body hash and extractor version. Offline extraction skips matching inputs; multi-product cells never transfer neighboring scope. |
| `web_cache.sqlite` | Original references, public bodies/destinations/hashes/media types, HTTP validators and failure/skip reasons. Strip fragments only for body keys; preserve queries/version selectors. Cached bytes do not prove review, authorship, applicability or completeness. |
| `canonical.sqlite` | Complete ordered catalog/metadata, five-question records and provenance/fingerprints. Seed unchanged offline; process approved targets only, preserving curated/protected/unrelated data. Changed inputs require explicit review, never automatic answer replacement. |
| `manual.sqlite` | User-supplied per-ID partial fields plus an automatic baseline snapshot for absent records. Separate from research, source cache and review approvals; dictionaries merge, lists replace, explicit nulls remain null. |
| `data\retirements.json` | Deterministic automatic-plus-manual catalog, with manual fields taking precedence. Preserve schema/routes, validate approvals/dependencies/concurrency, atomically write then build. Semantic no-ops preserve bytes. |

`python -m scripts.pipeline` stages: `seed`, `ingest --id ... --lifecycle-url ...`, `extract --id ...`, `links --id ...`, `canonical --id ...`, `review --batch ...`, `manual --batch ...`, `migrate`, `export`, `status`. Missing/stale inputs fail without hidden refetch. Unreviewed records require guarded `review --batch` with `sourceReview.status: enriched`, any needed link refresh and reassembly before approval. `canonical --accept-review` requires that status plus the latest exact `--input-sha256`/`--record-sha256`; fingerprints do not create review metadata. One process lock owns writes/export; independent atomic stores use fingerprint gates, not a distributed transaction. `migrate` removes legacy flags offline and preserves flagged content as manual overrides.

Refresh with ETag/`If-None-Match`, otherwise Last-Modified/`If-Modified-Since`. Reuse ingested source responses; only ingest refreshes them. A 304 reuses the body without row writes; identical 200 bodies do not invalidate review/extraction. Without validators, full GET/hash comparison is unavoidable; Content-Length/URL age proves nothing. Report real dynamic-HTML changes even if visible text seems unchanged. Errors retain last-good bodies but remain visible and block promotion, never stale-success fallbacks. No periodic whole-cache downloads.

Every download/redirect must use approved public Microsoft HTTPS endpoints: no private addresses, sign-in/tenant access, credentials, downloaded-code execution or recursive crawling. Classify support/Advisor portals without fetching. Bound size, redirects, timeouts and retries; HTTP caching remains separate from Learn MCP and evidence reading.

Design/testing records its one selected ID/evidence URLs in `<run>\state.json`. Test writes use isolated DB/JSON copies; source data/output changes need separate promotion approval. Seed the full baseline as preservation controls, not newly enriched rows. Reuse cached inputs offline. Approved live tests verify the exact announcement and linked Lifecycle row, cache only that record's references and report actual hits/changes. Prove offline byte-idempotence; test changed validators/content, failures, stale inputs and approval/export guards. One example limits live record scope, not regression coverage, and is never full enrichment.

## Pipeline stages and files

`<run>` holds session-local reports; `<work>` means `<run>\workers\<worker>\<assignment>`. Persistent inputs use five stores (isolated in tests). Generated output: `site\_data\site.json`, `site\assets\data\retirements.json`, `docs`. Builds never refresh; tests use selected-item ingest.

| Stage | Work / gate | Reads | Writes |
| --- | --- | --- | --- |
| 1. Establish baseline | Confirm mode/capabilities/approval, diff/hash, IDs/visibility/manual ownership/coverage; seed automatic data unchanged. Never seed from composed manual output. | Catalog, schema, README/prompt, DBs/state. | `canonical.sqlite`; `<run>\state.json` baseline/targets/approvals. |
| 2. Discover/merge | New full runs only. Both sources must complete; validate discovery/matching/IDs/schema/preservation/aliases/concurrency, atomically integrate, then build. No combined command yet. | Both sources, catalog, registry, flags/aliases/state. | `<run>\azure-updates.raw.json`, `lifecycle.raw.json`, `discovery-manifest.json`, `id-map.json`, `common-baseline.json`; gated catalog/registry/output. |
| 3. Plan batches | Coordinator leases disjoint IDs across all targets. `python -m scripts.review_data --limit 20` aids dispatch, not coverage. Include prior reviews/protected outcomes and page budgets; tests dispatch one example. | Catalog/run state. | `<run>\queue.json`, `completed-ids.json`, state/leases/input packages. |
| 4. Read evidence | Coordinator deduplicates fetches/writes; workers read immutable evidence in parallel and request extra references. Track destinations, access limits and pages. | Assigned records/URLs, snapshots, Learn MCP/verified posts. | Coordinator: `raw.sqlite`, `extracted.sqlite`, `web_cache.sqlite`; workers: `<work>\evidence.json`. |
| 5. Map claims | Map event/question/scope, migration/cost/impact limits, identification and conflicts; enrichment cannot prove identity. | Records/manifest/evidence. | Mappings/checks/guidance/tracking in `<work>\evidence.json`. |
| 6. Reconcile deadlines | Apply seven date rules, including exact dates. | Original/current deadlines and evidence. | Decisions/alternatives/precision/time zones/rationale in `<work>\evidence.json`. |
| 7. Draft answers | Write five service-specific, mode-limited answers with explicit uncertainty. | Existing answers/evidence/date decisions. | `<work>\drafts.json`, including review metadata. |
| 8. Format HTML | Align plain/rich facts; preserve substance and rendered tracking limits. | Drafts/originals/display rules. | Updated `<work>\drafts.json`; no CSS/template edits. |
| 9. Review batch | Check own evidence/originals, identity/dates/identifiers/numeric limits/warnings/qualifiers; return guarded proposals or audited no-change. | Assigned snapshots/drafts/evidence/hashes. | `<work>\proposal.json`; reconciled coordinator `<run>\batch.json`. |
| 10. Integrate/build | One writer validates/applies automatic proposals, approves fingerprints, overlays manual fields, exports and builds. Complete changed IDs only on success; user content is not researched approval. | Proposals, automatic baseline, `manual.sqlite`, current DBs/output. | `canonical.sqlite`, composed JSON/generated output, completion/state/queue. |
| 11. Audit | Check preservation, source/match/ID/date contracts, provenance round trips, content/routes/navigation/links/downloads/counts. | Baseline/artifacts/catalog/tests/output. | `<run>\audit.json`; build changes generated output only. |
| 12. Report/publish | Report source/merged/review coverage, remaining/protected IDs, changed dates/sources, unresolved scope/evidence and failures/validation. | Audit/state/queue/diff. | `<run>\state.json` summary; publish only with explicit approval. |

## Parallel enrichment design (not implemented)

Parallelize research/drafting, not shared database ownership. Record bounded worker/per-host limits before dispatch; concurrency never reduces coverage or authorizes execution.

| Work | Ownership |
| --- | --- |
| Baseline/discovery, 1-2 | Coordinator snapshots/validates/merges; two feed adapters may acquire independently before dispatch. |
| Acquisition/extraction, 4 | Fetches may overlap; coordinator alone writes shared raw/extracted/cache stores and versions inputs. |
| Evidence/drafts, 4-9 | Disjoint IDs/immutable snapshots; workers write only private `<work>` artifacts/disposable DB copies. |
| Integration/export/build/audit, 10-12 | Coordinator alone validates/applies serially and writes shared canonical/JSON/output/approvals/completion. |

- **Assignments:** track targets, lease/attempt tokens, automatic catalog/preimage hashes, dependency fingerprints, page budgets/outcomes. One lease per ID; no expanded assignments, hidden edits or manual-store writes. Reassign expired work with new tokens; reject late results and resume accepted work without rediscovery.
- **Acquisition:** one in-flight fetch per cache key, original references retained. Share host throttles/retries and the 80-page review-batch budget across workers. New references go through the coordinator for versioned results. Changed/failed inputs invalidate dependent proposals; unrelated work continues. Cache reuse never claims evidence reading/MCP retrieval.
- **Snapshots:** coordinator captures closed, consistent copies, never live files mid-write. Workers use immutable/private inputs, not shared locking CLI connections. Never share a writable `--db-dir`, remove locks, merge binaries or replace shared DBs with worker copies.
- **Proposals:** return tokens/IDs, baseline/preimage/dependency hashes, five-question changed fields, citations/checks, actual pages, issues and validation. Audited no-change needs identical guards/evidence. Workers cannot approve shared inputs, export or build.
- **Reconciliation:** under the writer lock reject unassigned/duplicate/stale work, changed target/dependencies, failed checks, invalid answers or protection violations. If only another ID changed the catalog hash, verify this target's original record/dependency hashes before constructing a new current-guard batch; retain original guards and rationale. Never mechanically replace stale guards or accept changed targets without renewed review. Keep approval/export gates.
- **Recovery:** integrate accepted results in catalog order within each batch; journal acceptance/export/build outcomes. After interrupted writes, compare actual record/input/output fingerprints before replay/completion. Requeue stale/expired jobs; retain failures. Complete only after all eligible IDs are integrated/audited-no-change, protected IDs accounted for and export/build/audit succeeds.

Tests use one live example (one lease), synthetic fixtures for multi-record concurrency. Acceptance requires out-of-order/exclusive/late/duplicate work, URL deduplication, host/page limits, stale and unrelated-record reconciliation, crashes before/after export, protected-row preservation, serial-equivalent output and full coverage. Scheduler, lease journal and proposal import/reconciliation are not implemented.

## Manual enrichment

Resolve the user's retirement to one existing ID; ambiguous identity is a blocker. Store only explicitly supplied content, never inferred research, using `manual --batch <batch.json>`:

```json
{"catalogSha256":"<status catalogSha256>","overrides":[{"id":"<existing-id>","fields":{"summary":"<user content>","questions":{"impact":{"guidance":"<user content>"}}}}]}
```

Manual fields override matching automatic fields only; retain other research. Nested objects merge, arrays replace, explicit nulls stay null; `fields: null` removes that record's overrides and restores automatic values. Identity/source timestamps/visibility/question headings cannot be overridden. Custom content and explicitly supplied `sourceReview` citation fields are supported but must pass existing validation; never present user claims as independently verified Microsoft facts.

Keep automatic JSON in `canonical.sqlite` and supplied fields/baseline snapshots in `manual.sqlite`; missing manual storage for composed output blocks writes, never silently discards content. Export adds `manualEnrichment.fields` provenance, not a protection flag. Plain answer edits without replacement HTML drop stale HTML for escaped fallback; supplied HTML must be safe/aligned. Resource/deadline edits retain consistent citations/checks. Manual content is not researched approval.

Use `status.automaticCatalogSha256` for automatic review batches and `status.catalogSha256` for manual batches. Both are guarded/atomic; neither stage exports until `export` runs. Repeated inputs are no-ops. Keep manually referenced records via their stored baseline if absent from new feeds. Do not initialize a new automatic store from already composed output.

## Source discovery URLs

**Only Azure Updates and Microsoft Lifecycle may discover retirements, establish Azure eligibility, or confirm cross-source identity.** Lifecycle means `/lifecycle/` pages on `learn.microsoft.com`, optionally locale-prefixed, not the entire Learn host. Linked/redirected guides do not expand this boundary.

| Source / URL | Allowed use |
| --- | --- |
| Azure Updates [JSON collection](https://www.microsoft.com/releasecommunications/api/v2/azure) / [retirement filter](https://www.microsoft.com/releasecommunications/api/v2/azure?$count=true&$filter=tags/any(f:f%20eq%20%27Retirements%27)) | Discovery: `$filter=tags/any(f:f eq 'Retirements')`, `$count=true`, `$top=100`, `$skip` pagination, `$orderby=id asc`, URL-encoded. Fetch every page; validate stable positive count and unique source IDs. |
| Azure Updates item: `https://azure.microsoft.com/updates?id=<encoded-source-id>` | Matching announcement title/full description and retained evidence. A generic listing returned by an item URL is not article content. |
| Lifecycle [hub](https://learn.microsoft.com/lifecycle/) / [official navigation](https://learn.microsoft.com/en-us/lifecycle/toc.json) | Independent discovery of all published annual `lifecycle/end-of-support/end-of-support-YYYY` indexes; no hard-coded year window. Extract individual Azure-related entries and use linked Lifecycle product pages for identity. |
| Other [Microsoft Learn Azure docs](https://learn.microsoft.com/azure/) and [Tech Community](https://techcommunity.microsoft.com/) | Enrichment only for already-identified events, including deadlines, migration, impact, and tracking. Never create records or confirm eligibility/matches from these sources. |

Annual URL pattern: `https://learn.microsoft.com/lifecycle/end-of-support/end-of-support-YYYY`; discover years from navigation, not a fixed range. Advisor/support portals are planning references, not feeds; no tenant access.

## Proposed parallel discovery and common-baseline contract

- Adapters independently produce raw observations/coverage. Validate navigation, all selected Lifecycle indexes, tables, row dates/precision and links. Missing/malformed/unexpectedly empty inputs block replacement; a valid future index without Azure rows is allowed if accounted for. Retain partial diagnostics.
- Only the two sources establish Azure scope: Additional Azure Changes or explicit product identification. Neither inherit neighboring scope nor include all Microsoft products; the literal word Azure is unnecessary with explicit linkage. Report scope-unconfirmed candidates.
- Split multi-anchor cells; retain product/feature, version, cloud/region, population, milestone, section, URL and raw date/precision. Retirement/end-of-support/end-of-servicing qualify, not mainstream-to-extended-support transitions. Keep creation/migration/access-loss/shutdown/support phases separate.
- New records have five valid question objects with unresolved unsupported answers; never invent review metadata/day or an Azure announcement for Lifecycle-only entries.
- Proposed catalog `discoverySources`: source keys, collection/index URLs, retrieval time/counts, Lifecycle years/pages. Per-record: original IDs/titles, exact entry/reference URLs, scope/milestone/raw dates. Separate ingestion from reviewed citations; preserve legacy `source`, actual primary `sourceUrl` and accurate labels.
- Azure `created`/`modified` supply `announcedOn`/`lastUpdatedOn`; absent values stay null. Lifecycle index years/page updates are not item timestamps. Neither these nor `retrievedAt` imply review dates/deadlines.
- Stage raw inputs/coverage/exclusions/matches/conflicts/ID map/proposed snapshot. After acquisition, re-read/reconcile/validate the whole catalog; byte/hash-guard atomic replacement. Stale/concurrent changes stop integration; preserve first-baseline content, never mechanically replace guards.
- Report actual coverage/unresolved candidates, not fixed totals, invented announcements or a guarantee of every Azure obligation.

## Retirement identity and matching

1. **Only the two allowed sources** establish product/component, SKU/version/generation, cloud/region, population and milestone. Confirm material dimensions or non-applicability; missing scope is unknown, not wildcard. Partial overlap/multi-event announcements are not equivalence.
2. Different titles/URLs may match through verified item identity or explicit cross-references with compatible details. Normalize superficial text only. Similar titles, shared guides, equal/nearby dates and seven-day tolerance never prove identity.
3. Manifest outcome: `confirmed-match`, `distinct` or `unresolved`, with original source/item IDs/titles/URLs, proposed ID, per-field comparison, exact allowed evidence/rationale. Different events are distinct; absent/conflicting/ambiguous proof stays unresolved. Answers/supplemental citations suggest candidates only; recheck contradictions against allowed sources.
4. Single-source events qualify. Confirmed observations reuse an assigned ID/all aliases; retain raw date differences for stage 6. Flag curated duplicates, never auto-delete/consolidate or force unresolved matches.

## Hash-based retirement IDs

Every canonical retirement uses the full digest below, optionally suffixed `-2`, `-3`, ... for a true collision; never truncate it.

```text
baseId = "ret-" + SHA256(UTF8("azure-retirement:v1\n" + canonicalJson(identity))).hexdigest()
id = persistedAssignment(identity) or firstAvailable(baseId, baseId + "-2", baseId + "-3", ...)
```

- Match first; freeze a versioned product/component, SKU/version, cloud/region, population, milestone and evidence-backed stable discriminator. Exclude titles, URLs, dates/timestamps/index years, answers, review status and row positions. Insufficient identity blocks allocation; keep observations separate.
- Serialization: fixed versioned schema, sorted keys, compact UTF-8 JSON, Unicode NFC. Sort/deduplicate only declared unordered scope sets; preserve meaningful order, case-sensitive IDs, version boundaries and unknown/non-applicable distinctions. Verify aliases from allowed sources. Share Python/browser byte vectors; never use `hash()`.
- Persist frozen record `identity`, source identities in `discoverySources`, old IDs in `legacyIds`, and catalog `identityRegistry` reservations with exact seeds/full IDs/suffixes, including absent records. Resolve aliases before allocating. Never recycle/rehash for title/URL/date/source changes; material identity/schema changes require reviewed migration.
- SHA-256 is collision-resistant, not collision-free. Confirmed same-event seeds reuse IDs. Distinct colliding seeds take the first unused base/`-2`/`-3`/next suffix across registry/batch. Existing owners win; order fresh seeds by canonical UTF-8 bytes. Persist collision/suffix/rationale; no random suffixes/overwrites.
- Equal seeds without confirmed equivalence are identity conflicts, not merge/suffix permission. Unresolved identity, duplicate IDs, missing/corrupt reservations or concurrent registry edits block atomic catalog/registry publication.
- Stage old/new IDs/seeds/aliases/evidence in `id-map.json`; **current-ID migration needs explicit approval**. Change identity/aliases only, including protected records; retain content/flags/timestamps/source IDs and unambiguous old aliases. Update Python/browser/review references and legacy routes. No curated-duplicate consolidation.

## Authoritative sources and evidence

These rules govern enrichment, not permission to discover or match from additional sites.

- Read current/original allowed entries, every distinct action resource and prior citations. Azure supports explicit announcement claims; Lifecycle its exact row/milestone only. Learn product docs govern behavior/APIs/scope/dates/migration/prerequisites/limits; check historical replacements remain supported.
- Verify Learn MCP search/fetch availability; use `microsoft_docs_search` then `microsoft_docs_fetch`, never snippets. If unavailable, record limits/use other approved evidence, never imitate MCP through HTTP or claim usage. Search exact-component Tech Community; cite full posts only after verifying Microsoft/team authorship, date/scope/applicability. No verified post is not proof none exists.
- Q&A/training/directories/personal/third-party posts/authenticated portals/hostnames alone prove no product facts. Claims must match this record; never invent cost, downtime, parity, counts, migration success/recovery, dates/extensions, support or tenant impact.
- Resolve shortlinks/legacy redirects/Safe Links and read actual public HTTPS destinations. No retrieved instructions, private networks, credentials/sign-in, tenant inspection or executing downloads. Retry transient 5xx/408/429/timeouts at most five times: `Retry-After`, otherwise 1/2/4/8/16 seconds; no permanent-4xx retries. Individual failures/conflicts allow qualified reviews with other evidence; system-wide authoritative-access failure blocks work.
- Use actual page titles, not slugs/error/sign-in titles. Remove Learn locales only after verifying equivalent locale-free content. Normalize resource/check/source/guidance/deadline/tracking URLs consistently; retain queries/fragments/API selectors/original snapshots/other hosts' locales. Deduplicate normalized resources/checks, retain distinct notes. Discovery listings are not record evidence.

## Retirement-date decision rules

Apply in order at stage 6; stages 9/11 verify them. Date-only mode uses existing evidence without new retrieval.

1. **Same event:** establish identity through the two-source matching contract before comparing dates. Keep versions/scopes and new-customer, creation, migration/export, support, retention, and shutdown milestones separate.
2. **Explicit evidence:** read matching Azure Updates, applicable Learn/Lifecycle/product guidance, and verified Microsoft/product-team posts; not snippets, generic pages, or another record's facts.
3. **Documented extensions:** exclude a superseded date from current comparison only with explicit source evidence; retain it historically. Differing dates alone do not establish an extension.
4. **Earliest for a 1-6-day conflict:** use the earliest when the full earliest-to-latest span is strictly less than seven calendar days, even if Learn gives a later date. August 31 versus September 1 selects August 31. Exactly seven days, chains spanning seven or more days, month-only evidence, and different scopes/phases do not qualify. Preserve alternatives, times/time zones, and citations; describe conservative selection, not source reconciliation.
5. **Otherwise current Learn precedence:** prefer an unambiguous applicable current Learn date, including an exact Lifecycle entry, over a different announcement date. Unresolved conflicting Learn dates or unclear scope/milestone remain unconfirmed; without applicable Learn evidence, unresolved non-Learn conflicts also stay unconfirmed unless a source explicitly resolves them.
6. **Preserve precision:** month-only evidence keeps `date: null`; retain `month` only if applicable and unambiguous, otherwise null. Never infer deadlines from publication/modification/retrieval timestamps, index years, API versions, IDs/slugs, or manufacture a day from a month.
7. **Consistent and cited:** selected dates use `YYYY-MM-DD` in `questions.deadline.date`, with matching month, plain/HTML explanations, and directly dependent text. Map the exact supporting URL to `deadline` in `sourceReview.sources` and select it as `deadlineSource`; otherwise null. Retain raw alternatives/rationale and original evidence; obey mode/protection limits.

Discovery dates are provisional. Today's Azure Updates parser uses a single distinct valid **title** date only, with deadline context required for ISO dates; it does not adjudicate descriptions or conflicts. Lifecycle must retain explicit row precision. Reviewed decisions occur here, not by using dates to deduplicate; first-baseline discovery preserves curated deadlines.

## Writing and display

### Five-question contract

Preserve headings/key order `what`, `actions`, `impact`, `deadline`, `progress`; display deadline first. Keep ingestion/provenance outside answers. Automatic enrichment supplies HTML for all five; manual plain edits may use the escaped fallback as described above.

| Question | Required content |
| --- | --- |
| `deadline` - What is the deadline? | Exact/month/unknown precision, cited selection/conflicts, separate phases, consequences; derive countdowns, lead times, grouping, and outlook from structured dates. |
| `what` - What is changing? | Affected service/feature, versions, regions, customer scopes/exceptions, what stops/changes, and source-backed financial considerations separate from workload estimates. Preserve original evidence, not a displayed raw scrape. |
| `actions` - What do I need to do? | Nullable official recommended action; currently supported alternatives by use case, prerequisites, ordered export/conversion/migration/testing/cutover/validation/cleanup, limits, and support. Distinguish required/optional and historical/current advice; no unsupported continuity, reversibility, recovery, parity, preservation, or cost guarantees. |
| `impact` - Where, and how much, am I impacted? | Supported affected configurations/inventory methods, dependencies and operational/data/cost risks, concise bullets, and no-tenant-access limits. Advisor/portal references do not prove affected resources or complete coverage. |
| `progress` - How can I track progress? | Specific supported inventory/verification/tracking methods, prerequisites, and coverage limits, in rendered `progress.html`, not only legacy fields. `tracking` needs a documented method from Learn/verified Microsoft Tech Community, cited for `progress`; otherwise null and exact answer: "Tracking guidance is not available for this retirement." Label any other HTML planning as team-owned/local; keep plain guidance/`storageNote` accurate. No browser-saved checklist claims. |

### Rendering rules

- Calm, direct, professional English; facts first, active voice, no promotion/filler or repetitive "Learn confirms" attribution. Attribute uncertainty, source conflicts, historical advice, and local planning clearly. Summary and introductions are one sentence each without losing substantive detail.
- Read prior plain/HTML answers; preserve exact names, code identifiers, versions, boundaries, qualifiers, warnings, financial/support/operational limits, and supported tracking details. Never import another record's facts or shrink content to force a uniform shape.
- Non-HTML fields are plain text: no Markdown, headings, bullet/number glyphs, raw URLs, manual line breaks, or literal newline escapes. Use spelled-out dates in prose and ISO structured dates.
- HTML allowlist: `p`, `h3`, `ul`, `ol`, `li`, `strong`, `em`, `code`, `pre`, `br`; no attributes/comments/active content. Escape text nodes. Lead with the main point; short single-topic paragraphs, meaningful subheadings, unordered independent points, ordered real sequences, sparing emphasis/code. Convert real/literal `\n`/`\\n` to semantic boundaries or intentional `<br>`.
- Align plain/HTML facts; avoid repeating separately rendered dates, notices, support, tracking status, or buttons. Impact bullets have no embedded glyph/number prefixes. Unavailable tracking may have clearly local-planning HTML, not a repeated unavailable message. Legacy progress checklists are not rendered; never claim site/browser progress storage.
- Inherit shared semantic typography: .875rem body/code/notices (14px default), 1.6 line height, 16/18/22px heading scale. The 12px exception is only timeline lead-time captions. No inline/custom sizing or CSS edits. The optional **Open Microsoft Learn guidance** button ends actions; all migration/support prose stays above it, without duplicating the button.

## Apply, validate, and report

- Prepare `<run>\batch.json` with the current `catalogSha256` and nonempty `reviews`. Each entry contains exactly `id`, `summary`, `questions` (all five keys, changed answer fields only, empty objects for unaffected answers), and `sourceReview`; no heading changes. Do not supply `originalAnnouncement`/`originalDeadline`: the apply tool captures/preserves them.
- New completed visible reviews use actual UTC `reviewedOn` and `status: enriched`, including uncertainty-qualified reviews; this means reviewed/organized, not independent verification of every fact. Do not introduce `needs-review`. Record unresolved limits in `issues`; preserve existing day/status in date-only/readability-only modes. Map sources to all five questions with descriptive titles, exact HTTPS URLs, sections, and accurate notes; each answer needs support or clearly attributed uncertainty.
- `deadlineSource` follows the date rules: applicable Learn (including Lifecycle), verified first-party Tech Community, or record-matching Azure Updates cited for `deadline`. Azure announcement variants must identify the actual source item, not assume a future hash ID equals the Azure ID. `guidanceSource` is nullable Learn product guidance cited for `actions`; absent a suitable page, omit the button. `progress.tracking` contains supported `guidance`/`sourceUrl`, cited for `progress`, or null; no invented tracking methods.
- `resourceChecks` covers every distinct final action resource: original `url`, nullable actual `resolvedUrl`, `status` (`read`, `partial`, `unavailable`, `not-evidence`), and reason. A `read` claim needs an actual destination, not merely a redirect/200 response. Known support/community links may be classified without claiming reading; use descriptive support labels for sign-in-only pages. Preserve original external URLs except verified Learn normalization; add useful verified Microsoft posts as resources.
- Optional `excludedReferences` uses `url`, actual UTC `checkedOn`, and confirmed `httpStatus` 404/410 after redirects; remove exclusions when sources return. Never infer nonexistence from 403, authentication, rate limiting, timeouts, or transient failures.
- Automatic database reviews use `status.automaticCatalogSha256` as the batch's `catalogSha256`, then `review --batch`, refresh changed references, assemble/approve exact fingerprints, `export` and `python site/build.py`. Manual batches use the composed hash and the manual stage. Stop on failure; never replace stale guards mechanically. JSON-only review refuses composed manual output; external edits after seeding require reconciliation. Complete only after export/build; remove only the named applied batch.
- Audit factual fidelity against each record's prior plain/HTML fields and own evidence, including removed duplicate notices. Schema/HTML checks do not prove accuracy. Use conservative prose-preserving formatting if uncertain. For an executed content run, run `python -m unittest discover -s tests -q`, `python site/build.py`, and `python -m scripts.check_site`.
- Inspect all five rendered answers, citations/review notes, complex-answer readability, detail sidebar exposing the full visible catalog, actions-button placement, date/title-slug routes, duplicate-title/legacy/stale routes, and local links. Downloads/prepared copies must match canonical JSON; counts derive from actual records. Diff against the baseline for mode-specific preservation; keep `docs` synchronized. Do not falsify `retrievedAt`, `lastUpdatedOn`, or review dates.
- Leave a reviewable diff and honest stage-12 coverage report. Design/testing reports its one example and test outcomes, never full-catalog enrichment. Full enrichment reconciles completed/preserved IDs against the complete target set; report partial completion on any remaining eligible records, unresolved discovery/matching, blocked evidence access, or failed required gates. Commit/push/PR/merge/main-branch writes only when explicitly authorized. Reconcile concurrent main-branch refreshes without overwriting/force-pushing. No automation, schedule, or permission changes are authorized by this prompt.

## Implementation acceptance gates

Before any approved live combined run, implement and validate the proposed adapters/preservation mode, parallel worker/queue/reconciliation contract, metadata shapes/schema compatibility, Python/browser parsing without silently dropped top-level fields, source labels, review handling, routes, and downloadable provenance/registry round trips.

Offline cases must cover:

- **Discovery/matching:** dynamic years, malformed/partial sources, valid empty future Azure scope, multi-anchor rows, Azure scope without name-only assumptions, non-retirement support phases, single-source events, different titles/URLs for one event, identical titles with different versions/phases, partial/shared-reference scope, ambiguous many-to-one matches, and rejected third-source discovery/match proof.
- **IDs/preservation:** exact serialization and unordered-set ordering; distinct scope/version/milestone keys; same confirmed event across both sources; unchanged IDs after title/URL/date changes; simulated `-2`/`-3`/next-unused collisions; deterministic fresh-batch ordering and persisted assignment reuse across resumes/absence; no reservation reuse; incomplete equal seeds without a confirmed match; ambiguous aliases; protected/hidden/absent records and curated content; approved alias/ID migration; full/suffixed route IDs; source failure and concurrent allocation/publishing.
- **Dates/content:** 1-6-day conflicts, exactly seven days, chains spanning seven or more days, documented extensions, conflicting Learn dates, different scopes/milestones, month-only precision, API-version dates, all five question/HTML objects, accurate rendered tracking/local planning, citations, and mode-restricted diffs.
