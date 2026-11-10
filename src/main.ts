import './style.css';
import catalog, { catalogDownload } from './data';
import { categoriesOf, daysUntilRetirement, directoryUrl, escapeHtml as e, filterRecords, formatDate, groupRetirements, retirementYear, safeUrl, statusOf } from './catalog';
import type { CatalogFilters, RetirementLink, RetirementRecord, SortOrder, StatusFilter } from './types';

function element<T extends HTMLElement = HTMLElement>(selector: string): T {
  const node = document.querySelector<T>(selector);
  if (!node) throw new Error(`Required app element is missing: ${selector}`);
  return node;
}

function statusFilter(value: string | null): StatusFilter {
  return value === 'upcoming' || value === 'soon' || value === 'retired' || value === 'unknown' ? value : 'all';
}

function sortOrder(value: string): SortOrder {
  return value === 'newest' || value === 'title' ? value : 'date';
}

const icons = {
  grid: '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="3" y="15" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  moon: '<path d="M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10Z"/>',
  sun: '<circle cx="12" cy="12" r="4"/><path d="M12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5"/>',
  download: '<path d="M12 3v12m-5-5 5 5 5-5M4 17v4h16v-4"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  external: '<path d="M14 3h7v7m0-7L10 14"/><path d="M10 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-6"/>',
};
const icon = (name: keyof typeof icons) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
const labels = { upcoming: 'Upcoming', soon: 'Within 90 days', retired: 'Retired', unknown: 'Date to confirm' };
const services = [...new Set(catalog.records.flatMap(record => record.services))].sort();
const navigation = groupRetirements(catalog.records);
const categories = [...new Set(catalog.records.flatMap(categoriesOf))].sort();
const yearLabel = (year: string) => year === 'unknown' ? 'Unconfirmed year' : year;
let directoryHash = '#/';
let visible = 24;
let filters: CatalogFilters = { q: '', service: '', year: '', category: '', status: 'all', sort: 'newest' };
let activeRecord: RetirementRecord | undefined;
try {
  document.documentElement.dataset.theme = localStorage.getItem('retirements-theme')
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
} catch { /* The theme toggle still works when storage is disabled. */ }

element('#app').innerHTML = `
  <a class="skip" href="#main">Skip to content</a>
  <header class="top">
    <button class="icon-button mobile-menu" aria-label="Toggle navigation" aria-expanded="false" aria-controls="navigation">${icon('menu')}</button>
    <a class="brand" href="#/" aria-label="Azure Retirements home"><span class="brand-mark">${icon('clock')}</span><span class="brand-separator"></span><span class="brand-name">Azure Retirements</span><span class="brand-tag">Lifecycle guidance</span></a>
    <div class="header-search" role="search">
      ${icon('search')}<input id="global-search" type="search" placeholder="Search retirements" aria-label="Search all retirements" aria-controls="search-results" autocomplete="off"><kbd>Ctrl K</kbd>
      <div id="search-results" class="search-results" aria-label="Search results" hidden></div>
    </div>
    <div class="top-actions">
      <div class="downloads"><button id="downloads" class="button" aria-label="Downloads" aria-expanded="false" aria-controls="download-menu">${icon('download')}<span>Downloads</span></button>
        <div id="download-menu" class="download-menu" hidden><a href="${e(catalogDownload)}" download="retirements.json">${icon('download')}<span><strong>Retirement catalog (JSON)</strong><small>All ${catalog.records.length} announcements</small></span></a></div>
      </div>
      <button id="theme" class="icon-button" aria-label="Toggle dark theme"><span class="sun">${icon('sun')}</span><span class="moon">${icon('moon')}</span></button>
    </div>
  </header>
  <section class="hero" id="home-hero" aria-labelledby="hero-title">
    <div class="hero-in">
      <h1 id="hero-title">Plan your next Azure migration</h1>
      <p>Stay ahead of service retirements. Understand what is changing, find official guidance, and plan your path forward.</p>
      <div class="hero-cta"><a class="button" href="#catalog">Explore retirements ${icon('arrow')}</a><a class="button ghost" href="#/?status=soon">Review the next 90 days</a></div>
    </div>
    <div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="art-center">${icon('clock')}</div><span class="node node-one"></span><span class="node node-two"></span><span class="node node-three"></span></div>
  </section>
  <div class="nav-backdrop" hidden></div>
  <div class="layout">
    <aside class="sidebar" id="navigation">
      <p class="nav-label">Retirement guidance</p>
      <nav aria-label="Retirement navigation">
        <a href="#/" data-nav="all">${icon('grid')}All retirements<span class="nav-count">${catalog.records.length}</span></a>
        <p class="nav-section-label">By retirement year</p>
        ${navigation.map(group => `
          <details class="year-group" data-year-group="${e(group.year)}"${group.year === String(new Date().getUTCFullYear()) ? ' open' : ''}>
            <summary>${e(yearLabel(group.year))}<span class="nav-count">${group.records.length}</span></summary>
            <a href="${e(directoryUrl({ year: group.year }))}" data-year="${e(group.year)}" data-category="">All in ${e(yearLabel(group.year))}</a>
            ${group.categories.map(category => `
              <details class="category-group" data-category-group="${e(category.name)}">
                <summary>${e(category.name)}<span class="nav-count">${category.records.length}</span></summary>
                <a class="category-all" href="${e(directoryUrl({ year: group.year, category: category.name }))}" data-year="${e(group.year)}" data-category="${e(category.name)}">View all ${e(category.name)} retirements</a>
                ${category.records.map(record => `<a class="nav-record" href="#/retirements/${encodeURIComponent(record.id)}?${e(new URLSearchParams({ year: group.year, category: category.name }).toString())}" data-record="${e(record.id)}" data-year="${e(group.year)}" data-category="${e(category.name)}">${e(record.title)}</a>`).join('')}
              </details>`).join('')}
          </details>`).join('')}
        <details class="status-navigation"><summary>Browse by status</summary>
          <a href="#/?status=upcoming" data-nav="upcoming">Upcoming retirements</a>
          <a href="#/?status=soon" data-nav="soon">Within 90 days</a>
          <a href="#/?status=retired" data-nav="retired">Retired services</a>
          <a href="#/?status=unknown" data-nav="unknown">Dates to confirm</a>
        </details>
        <details><summary>Official resources</summary>
          <a href="https://azure.microsoft.com/updates/" target="_blank" rel="noopener noreferrer">Azure Updates ${icon('external')}</a>
          <a href="https://portal.azure.com/#view/Microsoft_Azure_Expert/AdvisorMenuBlade/~/serviceRetirement" target="_blank" rel="noopener noreferrer">Azure Advisor ${icon('external')}</a>
        </details>
      </nav>
      <div class="sidebar-note"><p>Plan with official guidance</p><small>Confirm dates, migration options, and workload impact with Microsoft.</small></div>
      <div class="sidebar-bottom"><a href="https://github.com/SenthuranSivananthan/retirements" target="_blank" rel="noopener noreferrer">View on GitHub ${icon('external')}</a><small>Community project · Not affiliated with Microsoft</small></div>
    </aside>
    <main id="main" tabindex="-1"></main>
  </div>`;

element('#theme').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('retirements-theme', theme); } catch { /* Theme still works without storage. */ }
  updateThemeLabel();
});
function updateThemeLabel() {
  element('#theme').setAttribute('aria-label', `Switch to ${document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'} theme`);
}
updateThemeLabel();
function setNavigation(open: boolean) {
  element('.mobile-menu').setAttribute('aria-expanded', String(open));
  element('.sidebar').classList.toggle('open', open);
  element('.nav-backdrop').hidden = !open;
  document.body.classList.toggle('nav-open', open);
}
element('.mobile-menu').addEventListener('click', () => {
  setNavigation(element('.mobile-menu').getAttribute('aria-expanded') !== 'true');
});
element('.nav-backdrop').addEventListener('click', () => setNavigation(false));
element('#navigation').addEventListener('click', event => {
  if (event.target instanceof Element && event.target.closest('a')) setNavigation(false);
});
function closeDownloads() {
  element('#download-menu').hidden = true;
  element('#downloads').setAttribute('aria-expanded', 'false');
}
element('#downloads').addEventListener('click', () => {
  const menu = element('#download-menu');
  menu.hidden = !menu.hidden;
  element('#downloads').setAttribute('aria-expanded', String(!menu.hidden));
});
const globalSearch = element<HTMLInputElement>('#global-search');
const searchResults = element('#search-results');
function closeSearch() {
  searchResults.hidden = true;
}
function searchCatalog() {
  const q = globalSearch.value.trim();
  if (q.length < 2) { closeSearch(); return; }
  const hits = filterRecords(catalog.records, { q, sort: 'newest' }).slice(0, 8);
  searchResults.innerHTML = hits.length
    ? hits.map(record => `<a href="#/retirements/${encodeURIComponent(record.id)}"><strong>${e(record.title)}</strong><small>${e(record.service)}</small></a>`).join('')
    : '<p>No matching retirements.</p>';
  searchResults.hidden = false;
}
globalSearch.addEventListener('input', searchCatalog);
globalSearch.addEventListener('focus', searchCatalog);
element('.header-search').addEventListener('focusout', event => {
  if (!(event.relatedTarget instanceof Node) || !element('.header-search').contains(event.relatedTarget)) closeSearch();
});
element('.header-search').addEventListener('keydown', event => {
  const links = [...searchResults.querySelectorAll<HTMLAnchorElement>('a')];
  if (searchResults.hidden || !links.length) return;
  const current = links.findIndex(link => link === document.activeElement);
  if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
    event.preventDefault();
    const next = event.key === 'ArrowDown' ? current + 1 : (current < 0 ? links.length - 1 : current - 1);
    links[(next + links.length) % links.length]?.focus();
  } else if (event.key === 'Enter' && event.target === globalSearch) {
    event.preventDefault();
    links[0]?.click();
  }
});
document.addEventListener('keydown', event => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    globalSearch.focus();
    globalSearch.select();
  }
  if (event.key === 'Escape') {
    if (!searchResults.hidden) globalSearch.focus();
    else if (!element('#download-menu').hidden) element('#downloads').focus();
    else if (element('.sidebar').classList.contains('open')) element('.mobile-menu').focus();
    closeSearch();
    closeDownloads();
    setNavigation(false);
  }
});
document.addEventListener('click', event => {
  if (!(event.target instanceof Element)) return;
  if (!event.target.closest('.header-search') || event.target.closest('#search-results a')) closeSearch();
  if (!event.target.closest('.downloads') || event.target.closest('#download-menu a')) closeDownloads();
  const link = event.target.closest('a[href="#main"], a[href="#catalog"], a[data-section]');
  if (!link) return;
  const href = link.getAttribute('href');
  const target = href ? document.querySelector<HTMLElement>(href) : null;
  if (target) {
    event.preventDefault();
    target.scrollIntoView();
    if (target.id !== 'catalog') {
      target.tabIndex = -1;
      target.focus({ preventScroll: true });
    }
  }
});

function badge(record: RetirementRecord) {
  const status = statusOf(record.questions.deadline);
  return `<span class="badge ${status}"><span></span>${labels[status]}</span>`;
}
function sourceLink(record: RetirementRecord, text = 'Read official announcement') {
  const url = safeUrl(record.sourceUrl);
  return url ? `<a class="button primary" href="${e(url)}" target="_blank" rel="noopener noreferrer">${text} ${icon('external')}</a>` : '';
}
function externalLink(link: RetirementLink) {
  const url = safeUrl(link.url);
  return url ? `<a href="${e(url)}" target="_blank" rel="noopener noreferrer">${e(link.title || link.url)} ${icon('external')}</a>` : '';
}
function footer() {
  return `<footer>Last refreshed ${e(formatDate(catalog.retrievedAt.slice(0, 10)))} · ${catalog.records.length} announcements
    <p>Announcement coverage is limited to the source catalog. Dates and guidance can change; confirm your plans with the official announcement.</p>
    <p>Theme and checklist preferences are stored only in this browser. No Azure account access, analytics, or tracking.</p></footer>`;
}

function renderDirectory() {
  activeRecord = undefined;
  document.title = 'Azure Retirements · Plan your next move';
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  filters = {
    q: params.get('q') || '', service: params.get('service') || '',
    year: params.get('year') || '', category: params.get('category') || '',
    status: statusFilter(params.get('status')), sort: sortOrder(params.get('sort') || 'newest'),
  };
  if (!services.includes(filters.service)) filters.service = '';
  if (!navigation.some(group => group.year === filters.year)) filters.year = '';
  if (!categories.includes(filters.category)) filters.category = '';
  visible = 24;
  const upcoming = catalog.records.filter(record => ['upcoming', 'soon'].includes(statusOf(record.questions.deadline))).length;
  const soon = catalog.records.filter(record => statusOf(record.questions.deadline) === 'soon').length;
  element('#main').innerHTML = `
    <div class="crumbs">Azure lifecycle <span>/</span> Retirement explorer</div>
    <section class="stats" aria-label="Catalog summary">
      <div><span class="stat-icon blue">${icon('grid')}</span><div><strong>${catalog.records.length}</strong><span>Retirement announcements</span></div></div>
      <div><span class="stat-icon teal">${icon('clock')}</span><div><strong>${upcoming}</strong><span>With known upcoming dates</span></div></div>
      <div><span class="stat-icon amber">${icon('clock')}</span><div><strong>${soon}</strong><span>Within the next 90 days</span></div></div>
    </section>
    <section id="catalog" aria-labelledby="catalog-title">
      <div class="section-heading"><div><span class="eyebrow">THE RETIREMENT EXPLORER</span><h2 id="catalog-title">Know what’s changing</h2><p>Your next migration starts with a little visibility.</p></div><a class="text-link" href="${e(catalogDownload)}" download="retirements.json">Download catalog ↓</a></div>
      ${filters.year || filters.category ? `<div class="group-filter" aria-label="Current navigation filters">${filters.year ? `<span>Retirement year: <strong>${e(yearLabel(filters.year))}</strong></span>` : ''}${filters.category ? `<span>Azure category: <strong>${e(filters.category)}</strong></span>` : ''}<a href="${e(directoryUrl({ ...filters, year: '', category: '' }))}">Clear year and category</a></div>` : ''}
      <div class="filters">
        <label class="search-field"><span class="sr-only">Search retirements</span>${icon('search')}<input id="search" type="search" placeholder="Search services, features, or keywords…" value="${e(filters.q)}"></label>
        <label><span>Service</span><select id="service"><option value="">All services</option>${services.map(service => `<option value="${e(service)}"${filters.service === service ? ' selected' : ''}>${e(service)}</option>`).join('')}</select></label>
        <label><span>Status</span><select id="status">${[['all', 'All statuses'], ['upcoming', 'Upcoming'], ['soon', 'Next 90 days'], ['retired', 'Retired'], ['unknown', 'Date to confirm']].map(([value, label]) => `<option value="${value}"${filters.status === value ? ' selected' : ''}>${label}</option>`).join('')}</select></label>
      </div>
      <div class="results-bar"><p id="result-count" role="status" aria-live="polite"></p><label>Sort by <select id="sort"><option value="date">Retirement date</option><option value="newest">Latest announced</option><option value="title">Title A–Z</option></select></label></div>
      <div id="results" class="cards"></div>
      <div class="load-more"><button id="load-more" class="button">Show more retirements</button></div>
    </section>${footer()}`;
  element<HTMLSelectElement>('#sort').value = filters.sort;
  for (const [id, key, event] of [['search', 'q', 'input'], ['service', 'service', 'change'], ['status', 'status', 'change'], ['sort', 'sort', 'change']] as const) {
    const control = element<HTMLInputElement | HTMLSelectElement>(`#${id}`);
    control.addEventListener(event, () => {
      if (key === 'status') filters.status = statusFilter(control.value);
      else if (key === 'sort') filters.sort = sortOrder(control.value);
      else filters[key] = control.value;
      visible = 24;
      directoryHash = directoryUrl(filters);
      history.replaceState(null, '', directoryHash);
      const clearGroup = document.querySelector<HTMLAnchorElement>('.group-filter a');
      if (clearGroup) clearGroup.href = directoryUrl({ ...filters, year: '', category: '' });
      renderResults();
      updateNav();
    });
  }
  element('#load-more').addEventListener('click', () => {
    const firstNewCard = visible;
    visible += 24;
    renderResults();
    document.querySelectorAll<HTMLAnchorElement>('.card h3 a')[firstNewCard]?.focus();
  });
  renderResults();
}

function renderResults() {
  const records = filterRecords(catalog.records, filters);
  element('#result-count').textContent = `Showing ${Math.min(visible, records.length)} of ${records.length} retirements`;
  element('#results').innerHTML = records.length ? records.slice(0, visible).map(record => `
    <article class="card">
      <div class="card-top"><span class="service-name">${e(record.service)}</span>${badge(record)}</div>
      <h3><a href="#/retirements/${encodeURIComponent(record.id)}">${e(record.title)}</a></h3>
      <p>${e(record.summary)}</p>
      <div class="card-bottom"><span>${icon('clock')}${record.questions.deadline.date ? `<time datetime="${e(record.questions.deadline.date)}">${e(formatDate(record.questions.deadline.date))}</time>` : 'Date not specified'}</span><a href="#/retirements/${encodeURIComponent(record.id)}" aria-label="View details: ${e(record.title)}">View details ${icon('arrow')}</a></div>
    </article>`).join('') : `<div class="empty"><h3>No matching retirements</h3><p>Try a different keyword, service, status, year, or category.</p><button class="button" id="clear-filters">Clear filters</button></div>`;
  element('#load-more').hidden = records.length <= visible;
  document.querySelector('#clear-filters')?.addEventListener('click', () => { location.hash = '#/'; });
}

const detailSections = ['what', 'actions', 'impact', 'deadline', 'progress'] as const;

function renderDetail(id: string) {
  const record = catalog.records.find(record => record.id === id);
  activeRecord = record;
  if (!record) {
    document.title = 'Retirement not found · Azure Retirements';
    element('#main').innerHTML = `<section class="not-found"><span class="eyebrow">404 · RETIREMENT NOT FOUND</span><h1>This page has moved on.</h1><p>The link may be incorrect or the announcement may no longer be in the catalog.</p><a class="button primary" href="#/">Explore retirements ${icon('arrow')}</a></section>`;
    return;
  }
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  const year = params.get('year');
  const category = params.get('category');
  if (year === retirementYear(record) && category && categoriesOf(record).includes(category)) {
    filters = { q: '', service: '', status: 'all', sort: 'newest', year, category };
    directoryHash = directoryUrl({ year, category });
  }
  const { what, actions, impact, deadline, progress } = record.questions;
  const days = daysUntilRetirement(deadline);
  const countdown = days === null ? 'Retirement date to confirm'
    : days < 0 ? 'Retired'
      : days === 0 ? 'Retires today (0 days remaining)'
        : `${days} ${days === 1 ? 'day' : 'days'} remaining`;
  const checklist = progress.checklist;
  document.title = `${record.title} · Azure Retirements`;
  element('#main').innerHTML = `
    <div class="crumbs"><a href="${e(directoryHash)}">Retirement explorer</a><span>/</span>${e(record.service)}</div>
    <a class="back-link" href="${e(directoryHash)}">← All retirements</a>
    <div class="detail-heading"><div class="card-top"><span class="service-name">${e(record.service)}</span>${badge(record)}</div><h1>${e(record.title)}</h1><p>${e(record.summary)}</p>
      <div class="retirement-countdown ${statusOf(deadline)}"><strong>${e(countdown)}</strong>${deadline.date ? `<span>Retirement date: <time datetime="${e(deadline.date)}">${e(formatDate(deadline.date))}</time></span>` : ''}</div>
    </div>
    <div class="detail-layout">
      <article class="detail-content">
        <section id="what"><h2><span class="section-number">1</span>${e(what.question)}</h2>
          <p class="section-intro">${e(what.introduction)}</p>
          ${what.announcement.split(/\n+/).filter(Boolean).map(paragraph => `<p>${e(paragraph)}</p>`).join('')}
          <div class="notice">${e(what.financialConsiderations)}</div>
        </section>
        <section id="actions"><h2><span class="section-number">2</span>${e(actions.question)}</h2>
          <p class="section-intro">${e(actions.introduction)}</p>
          ${actions.recommendedAction ? `<h3>Microsoft’s recommended action</h3>${actions.recommendedAction.split(/\n+/).filter(Boolean).map(paragraph => `<p>${e(paragraph)}</p>`).join('')}` : ''}
          <p>${e(actions.guidance)}</p>
          ${sourceLink(record, 'Open Microsoft migration guidance')}
          ${actions.resources.some(link => safeUrl(link.url)) ? `<h3>Resources from the announcement</h3><ul class="resource-links">${actions.resources.filter(link => safeUrl(link.url)).map(link => `<li>${externalLink(link)}</li>`).join('')}</ul>` : ''}
          <p>${e(actions.supportGuidance)} ${externalLink(actions.support)}</p>
        </section>
        <section id="impact"><h2><span class="section-number">3</span>${e(impact.question)}</h2>
          <p class="section-intro">${e(impact.introduction)}</p>
          <p>${e(impact.guidance)}</p>
          <ul>${impact.checklist.map(step => `<li>${e(step)}</li>`).join('')}</ul>
          <div class="notice">${e(impact.notice)} ${externalLink(impact.advisor)}</div>
        </section>
        <section id="deadline"><h2><span class="section-number">4</span>${e(deadline.question)}</h2>
          <p class="section-intro">${e(deadline.introduction)}</p>
          <p class="deadline-date">${e(formatDate(deadline.date))}</p>
          <p>${e(deadline.dateGuidance)}</p>
          <p>${e(deadline.consequences)}</p>
          ${sourceLink(record, 'Verify dates and consequences')}
        </section>
        <section id="progress"><h2><span class="section-number">5</span>${e(progress.question)}</h2>
          <p class="section-intro">${e(progress.introduction)}</p>
          <p>${e(progress.guidance)}</p>
          <div class="progress-summary" id="progress-summary" role="status" aria-live="polite"></div>
          <div class="checklist">${checklist.map((text, index) => `<label><input type="checkbox" data-step="${index}"><span>${e(text)}</span></label>`).join('')}</div>
          <p class="storage-note" id="storage-note">${e(progress.storageNote)}</p>
        </section>
      </article>
      <aside class="detail-rail" aria-label="Retirement facts"><div class="fact-card"><span class="eyebrow">RETIREMENT AT A GLANCE</span><dl><dt>Retirement date</dt><dd>${deadline.date ? `<time datetime="${e(deadline.date)}">${e(formatDate(deadline.date))}</time>` : 'Not specified as an exact date'}</dd><dt>Service</dt><dd>${e(record.service)}</dd><dt>Announced</dt><dd>${e(formatDate(record.announcedOn))}</dd><dt>Last updated</dt><dd>${record.lastUpdatedOn ? `<time datetime="${e(record.lastUpdatedOn)}">${e(formatDate(record.lastUpdatedOn))}</time>` : 'Not provided by source'}</dd><dt>Source</dt><dd>Microsoft Azure Updates</dd></dl>${sourceLink(record)}</div><div class="notice">Dates may be revised. Always verify the latest information with Microsoft.</div></aside>
    </div>${footer()}`;
  element('.detail-rail').insertAdjacentHTML('afterbegin', `<nav class="article-nav" aria-label="In this article"><h2>In this article</h2>${detailSections.map(id => `<a href="#${id}" data-section>${e(record.questions[id].question)}</a>`).join('')}</nav>`);
  const key = `retirements-progress:${record.id}`;
  let saved: unknown[] = [];
  try {
    const value: unknown = JSON.parse(localStorage.getItem(key) || '[]');
    if (Array.isArray(value)) saved = value;
  } catch { /* Invalid or unavailable storage starts with an empty checklist. */ }
  const checkboxes = [...document.querySelectorAll<HTMLInputElement>('[data-step]')];
  const updateProgress = () => {
    const done = checkboxes.filter(input => input.checked).length;
    element('#progress-summary').textContent = `${done} of ${checklist.length} planning steps complete · ${checklist.length - done} remaining`;
  };
  for (const input of checkboxes) {
    input.checked = saved[Number(input.dataset.step)] === true;
    input.addEventListener('change', () => {
      updateProgress();
      try { localStorage.setItem(key, JSON.stringify(checkboxes.map(input => input.checked))); }
      catch { element('#storage-note').textContent = 'Browser storage is unavailable. Progress will not be saved when you leave this page.'; }
    });
  }
  updateProgress();
}

function updateNav() {
  const detail = location.hash.startsWith('#/retirements/');
  const year = activeRecord ? retirementYear(activeRecord) : filters.year;
  const recordCategories = activeRecord ? categoriesOf(activeRecord).sort() : [];
  const category = activeRecord
    ? (recordCategories.includes(filters.category) ? filters.category : recordCategories[0])
    : filters.category;
  for (const link of document.querySelectorAll<HTMLAnchorElement>('#navigation a[data-nav], #navigation a[data-year]')) {
    let active = false;
    if (link.dataset.record) {
      active = activeRecord?.id === link.dataset.record && link.dataset.year === year && link.dataset.category === category;
    } else if (link.dataset.year) {
      active = !detail && link.dataset.year === filters.year && link.dataset.category === filters.category;
    } else {
      active = !detail && !filters.year && !filters.category && link.dataset.nav === filters.status;
    }
    if (active) {
      link.setAttribute('aria-current', 'page');
      let group = link.closest('details');
      while (group) {
        group.open = true;
        group = group.parentElement?.closest('details') || null;
      }
    } else link.removeAttribute('aria-current');
  }
}
function render() {
  setNavigation(false);
  closeSearch();
  closeDownloads();
  const route = location.hash.split('?')[0];
  element('#home-hero').hidden = route.startsWith('#/retirements/');
  if (route.startsWith('#/retirements/')) {
    let id;
    try { id = decodeURIComponent(route.slice('#/retirements/'.length)); } catch { id = ''; }
    renderDetail(id);
  } else {
    directoryHash = location.hash.startsWith('#/') ? location.hash : '#/';
    renderDirectory();
  }
  updateNav();
  updateArticleNav();
}
function updateArticleNav() {
  const links = [...document.querySelectorAll<HTMLAnchorElement>('.article-nav a')];
  let active = links[0];
  for (const link of links) {
    const section = document.getElementById(link.hash.slice(1));
    if (section && section.getBoundingClientRect().top <= 130) active = link;
  }
  for (const link of links) {
    if (link === active) link.setAttribute('aria-current', 'location');
    else link.removeAttribute('aria-current');
  }
}
window.addEventListener('scroll', updateArticleNav, { passive: true });
window.addEventListener('hashchange', () => {
  render();
  window.scrollTo(0, 0);
  element('#main').focus({ preventScroll: true });
});
render();
