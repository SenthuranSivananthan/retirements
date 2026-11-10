import './style.css';
import catalog, { catalogDownload } from './data.js';
import { escapeHtml as e, filterRecords, formatDate, safeUrl, statusOf } from './catalog.js';

const icons = {
  grid: '<rect x="3" y="3" width="6" height="6" rx="1"/><rect x="15" y="3" width="6" height="6" rx="1"/><rect x="3" y="15" width="6" height="6" rx="1"/><rect x="15" y="15" width="6" height="6" rx="1"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  arrow: '<path d="M5 12h14m-5-5 5 5-5 5"/>',
  search: '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 4 4"/>',
  moon: '<path d="M20 14A8 8 0 0 1 10 4a8 8 0 1 0 10 10Z"/>',
  menu: '<path d="M4 6h16M4 12h16M4 18h16"/>',
  external: '<path d="M14 3h7v7m0-7L10 14"/><path d="M10 3H4a1 1 0 0 0-1 1v16a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1v-6"/>',
};
const icon = name => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${icons[name]}</svg>`;
const labels = { upcoming: 'Upcoming', soon: 'Within 90 days', retired: 'Retired', unknown: 'Date to confirm' };
const services = [...new Set(catalog.records.flatMap(record => record.services))].sort();
let directoryHash = '#/';
let visible = 24;
let filters;
try {
  document.documentElement.dataset.theme = localStorage.getItem('retirements-theme')
    || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
} catch { /* The theme toggle still works when storage is disabled. */ }

document.querySelector('#app').innerHTML = `
  <a class="skip" href="#main">Skip to content</a>
  <header class="top">
    <button class="icon-button mobile-menu" aria-label="Toggle navigation" aria-expanded="false" aria-controls="navigation">${icon('menu')}</button>
    <a class="brand" href="#/" aria-label="Azure Retirements home"><span class="brand-mark">A<span>↗</span></span><span class="brand-separator"></span>Azure Retirements</a>
    <span class="brand-tag">Lifecycle guidance</span>
    <div class="top-actions"><a class="source-top" href="https://azure.microsoft.com/updates/" target="_blank" rel="noopener noreferrer">Azure Updates ${icon('external')}</a>
    <button id="theme" class="icon-button" aria-label="Toggle dark theme">${icon('moon')}</button></div>
  </header>
  <div class="layout">
    <aside class="sidebar" id="navigation">
      <p class="nav-label">WORKSPACE</p>
      <nav aria-label="Retirement navigation">
        <a href="#/" data-nav="all">${icon('grid')}All retirements<span>${catalog.records.length}</span></a>
        <a href="#/?status=upcoming" data-nav="upcoming">${icon('clock')}Upcoming</a>
        <a href="#/?status=soon" data-nav="soon">${icon('clock')}Next 90 days</a>
        <a href="#/?status=retired" data-nav="retired">${icon('grid')}Retired</a>
      </nav>
      <div class="sidebar-note"><span class="live-dot"></span> OFFICIAL SOURCES<p>Stay ahead of change.<br>Build with confidence.</p><small>Based on Microsoft Azure announcements.</small></div>
      <div class="sidebar-bottom"><a href="https://github.com/SenthuranSivananthan/retirements" target="_blank" rel="noopener noreferrer">View on GitHub ${icon('external')}</a><small>Community project · Not affiliated with Microsoft</small></div>
    </aside>
    <main id="main" tabindex="-1"></main>
  </div>`;

document.querySelector('#theme').addEventListener('click', () => {
  const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
  document.documentElement.dataset.theme = theme;
  try { localStorage.setItem('retirements-theme', theme); } catch { /* Theme still works without storage. */ }
  updateThemeLabel();
});
function updateThemeLabel() {
  document.querySelector('#theme').setAttribute('aria-label', `Switch to ${document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'} theme`);
}
updateThemeLabel();
document.querySelector('.mobile-menu').addEventListener('click', event => {
  const open = event.currentTarget.getAttribute('aria-expanded') !== 'true';
  event.currentTarget.setAttribute('aria-expanded', String(open));
  document.querySelector('.sidebar').classList.toggle('open', open);
});
document.addEventListener('click', event => {
  const link = event.target.closest('a[href="#main"], a[href="#catalog"]');
  if (!link) return;
  const target = document.querySelector(link.getAttribute('href'));
  if (target) {
    event.preventDefault();
    target.scrollIntoView();
    if (target.id === 'main') target.focus({ preventScroll: true });
  }
});

function badge(record) {
  const status = statusOf(record);
  return `<span class="badge ${status}"><span></span>${labels[status]}</span>`;
}
function sourceLink(record, text = 'Read official announcement') {
  const url = safeUrl(record.sourceUrl);
  return url ? `<a class="button primary" href="${e(url)}" target="_blank" rel="noopener noreferrer">${text} ${icon('external')}</a>` : '';
}
function footer() {
  return `<footer>Last refreshed ${e(formatDate(catalog.retrievedAt.slice(0, 10)))} · ${catalog.records.length} announcements
    <p>Announcement coverage is limited to the source catalog. Dates and guidance can change; confirm your plans with the official announcement.</p>
    <p>Theme and checklist preferences are stored only in this browser. No Azure account access, analytics, or tracking.</p></footer>`;
}

function renderDirectory() {
  document.title = 'Azure Retirements · Plan your next move';
  const params = new URLSearchParams(location.hash.split('?')[1] || '');
  filters = { q: params.get('q') || '', service: params.get('service') || '', status: params.get('status') || 'all', sort: params.get('sort') || 'newest' };
  if (!['all', 'upcoming', 'soon', 'retired', 'unknown'].includes(filters.status)) filters.status = 'all';
  if (!services.includes(filters.service)) filters.service = '';
  if (!['date', 'newest', 'title'].includes(filters.sort)) filters.sort = 'date';
  visible = 24;
  const upcoming = catalog.records.filter(record => ['upcoming', 'soon'].includes(statusOf(record))).length;
  const soon = catalog.records.filter(record => statusOf(record) === 'soon').length;
  document.querySelector('#main').innerHTML = `
    <div class="crumbs">Azure lifecycle <span>/</span> Retirement explorer</div>
    <section class="hero">
      <div class="eyebrow"><span class="live-dot"></span> CHANGE IS CONSTANT. BE READY.</div>
      <h1>Plan your next move<span>.</span></h1>
      <p>Azure evolves. Your platform should too.<br>Explore service retirements, understand the impact, and find your path forward.</p>
      <a class="hero-link" href="#catalog">Explore retirements ${icon('arrow')}</a>
      <div class="hero-art" aria-hidden="true"><div class="orbit orbit-one"></div><div class="orbit orbit-two"></div><div class="art-center">A</div><span class="node node-one"></span><span class="node node-two"></span><span class="node node-three"></span></div>
    </section>
    <section class="stats" aria-label="Catalog summary">
      <div><span class="stat-icon blue">${icon('grid')}</span><div><strong>${catalog.records.length}</strong><span>Retirement announcements</span></div></div>
      <div><span class="stat-icon teal">${icon('clock')}</span><div><strong>${upcoming}</strong><span>With known upcoming dates</span></div></div>
      <div><span class="stat-icon amber">${icon('clock')}</span><div><strong>${soon}</strong><span>Within the next 90 days</span></div></div>
    </section>
    <section id="catalog" aria-labelledby="catalog-title">
      <div class="section-heading"><div><span class="eyebrow">THE RETIREMENT EXPLORER</span><h2 id="catalog-title">Know what’s changing</h2><p>Your next migration starts with a little visibility.</p></div><a class="text-link" href="${e(catalogDownload)}" download="retirements.json">Download catalog ↓</a></div>
      <div class="filters">
        <label class="search-field"><span class="sr-only">Search retirements</span>${icon('search')}<input id="search" type="search" placeholder="Search services, features, or keywords…" value="${e(filters.q)}"></label>
        <label><span>Service</span><select id="service"><option value="">All services</option>${services.map(service => `<option value="${e(service)}"${filters.service === service ? ' selected' : ''}>${e(service)}</option>`).join('')}</select></label>
        <label><span>Status</span><select id="status">${[['all', 'All statuses'], ['upcoming', 'Upcoming'], ['soon', 'Next 90 days'], ['retired', 'Retired'], ['unknown', 'Date to confirm']].map(([value, label]) => `<option value="${value}"${filters.status === value ? ' selected' : ''}>${label}</option>`).join('')}</select></label>
      </div>
      <div class="results-bar"><p id="result-count" role="status" aria-live="polite"></p><label>Sort by <select id="sort"><option value="date">Retirement date</option><option value="newest">Latest announced</option><option value="title">Title A–Z</option></select></label></div>
      <div id="results" class="cards"></div>
      <div class="load-more"><button id="load-more" class="button">Show more retirements</button></div>
    </section>${footer()}`;
  document.querySelector('#sort').value = filters.sort;
  for (const [id, key, event] of [['search', 'q', 'input'], ['service', 'service', 'change'], ['status', 'status', 'change'], ['sort', 'sort', 'change']]) {
    document.getElementById(id).addEventListener(event, event => {
      filters[key] = event.target.value;
      visible = 24;
      const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
      directoryHash = `#/?${query}`;
      history.replaceState(null, '', directoryHash);
      renderResults();
      updateNav();
    });
  }
  document.querySelector('#load-more').addEventListener('click', () => {
    const firstNewCard = visible;
    visible += 24;
    renderResults();
    document.querySelectorAll('.card h3 a')[firstNewCard]?.focus();
  });
  renderResults();
}

function renderResults() {
  const records = filterRecords(catalog.records, filters);
  document.querySelector('#result-count').textContent = `Showing ${Math.min(visible, records.length)} of ${records.length} retirements`;
  document.querySelector('#results').innerHTML = records.length ? records.slice(0, visible).map(record => `
    <article class="card">
      <div class="card-top"><span class="service-name">${e(record.service)}</span>${badge(record)}</div>
      <h3><a href="#/retirements/${encodeURIComponent(record.id)}">${e(record.title)}</a></h3>
      <p>${e(record.summary)}</p>
      <div class="card-bottom"><span>${icon('clock')}${record.retirementDate ? `<time datetime="${e(record.retirementDate)}">${e(formatDate(record.retirementDate))}</time>` : 'Date not specified'}</span><a href="#/retirements/${encodeURIComponent(record.id)}" aria-label="View details: ${e(record.title)}">View details ${icon('arrow')}</a></div>
    </article>`).join('') : `<div class="empty"><h3>No matching retirements</h3><p>Try a different keyword, service, or status.</p><button class="button" id="clear-filters">Clear filters</button></div>`;
  document.querySelector('#load-more').hidden = records.length <= visible;
  document.querySelector('#clear-filters')?.addEventListener('click', () => { location.hash = '#/'; });
}

const checklist = [
  'Identify affected resources, subscriptions, and owners',
  'Review the official migration guidance and estimate cost changes',
  'Test the replacement and agree a migration plan',
  'Complete migration and validate production workloads',
];

function renderDetail(id) {
  const record = catalog.records.find(record => record.id === id);
  if (!record) {
    document.title = 'Retirement not found · Azure Retirements';
    document.querySelector('#main').innerHTML = `<section class="not-found"><span class="eyebrow">404 · RETIREMENT NOT FOUND</span><h1>This page has moved on.</h1><p>The link may be incorrect or the announcement may no longer be in the catalog.</p><a class="button primary" href="#/">Explore retirements ${icon('arrow')}</a></section>`;
    return;
  }
  document.title = `${record.title} · Azure Retirements`;
  document.querySelector('#main').innerHTML = `
    <div class="crumbs"><a href="${e(directoryHash)}">Retirement explorer</a><span>/</span>${e(record.service)}</div>
    <a class="back-link" href="${e(directoryHash)}">← All retirements</a>
    <div class="detail-heading"><div class="card-top"><span class="service-name">${e(record.service)}</span>${badge(record)}</div><h1>${e(record.title)}</h1><p>${e(record.summary)}</p></div>
    <div class="detail-layout">
      <article class="detail-content">
        <section id="what"><h2><span class="section-number">1</span>What is changing?</h2>
          <p class="section-intro">The change and what it means, including technical and financial considerations.</p>
          ${(record.details || record.summary).split(/\n+/).filter(Boolean).map(paragraph => `<p>${e(paragraph)}</p>`).join('')}
          <div class="notice">The text above is from Microsoft’s announcement. Pricing and financial impact are workload-specific; review replacement-service pricing and your agreements before migrating.</div>
        </section>
        <section id="actions"><h2><span class="section-number">2</span>What do I need to do?</h2>
          <p class="section-intro">Required actions, options, and available support.</p>
          ${record.actions ? `<h3>Microsoft’s recommended action</h3>${record.actions.split(/\n+/).filter(Boolean).map(paragraph => `<p>${e(paragraph)}</p>`).join('')}` : ''}
          <p>Use the official announcement for service-specific migration instructions and replacement options. Inventory dependencies, test the recommended replacement, and plan a validated rollout.</p>
          ${sourceLink(record, 'Open Microsoft migration guidance')}
          ${record.links?.some(link => safeUrl(link.url)) ? `<h3>Resources from the announcement</h3><ul class="resource-links">${record.links.filter(link => safeUrl(link.url)).map(link => `<li><a href="${e(safeUrl(link.url))}" target="_blank" rel="noopener noreferrer">${e(link.title || link.url)} ${icon('external')}</a></li>`).join('')}</ul>` : ''}
          <p>For help with your specific environment, contact your Microsoft account team or <a href="https://azure.microsoft.com/support/create-ticket/" target="_blank" rel="noopener noreferrer">Azure support</a>.</p>
        </section>
        <section id="impact"><h2><span class="section-number">3</span>Where, and how much, am I impacted?</h2>
          <p class="section-intro">Your affected environments, resources, and users.</p>
          <p>This announcement concerns <strong>${e(record.service)}</strong>. Compare the versions, regions, configurations, and exceptions in the announcement with your inventory.</p>
          <ul><li>Check every subscription and environment, including development, test, and production.</li><li>Identify dependent applications, users, and resource owners.</li><li>Estimate migration effort, downtime risk, and replacement-service costs.</li></ul>
          <div class="notice"><strong>No tenant access.</strong> This directory cannot determine whether your resources are affected. Use <a href="https://portal.azure.com/#view/Microsoft_Azure_Expert/AdvisorMenuBlade/~/serviceRetirement" target="_blank" rel="noopener noreferrer">Azure Advisor service retirements</a> alongside your inventory and the official guidance. Advisor coverage may vary by service.</div>
        </section>
        <section id="deadline"><h2><span class="section-number">4</span>What is the deadline?</h2>
          <p class="section-intro">Key dates and the consequences of not acting.</p>
          <p class="deadline-date">${e(formatDate(record.retirementDate))}</p>
          <p>${record.retirementDate ? 'This date is extracted from the announcement title. Check the full announcement for phased deadlines, extensions, and exceptions.' : `An unambiguous exact date could not be extracted from the announcement title.${record.retirementMonth ? ` The source lists ${e(record.retirementMonth)} as the retirement month.` : ''} Review the official announcement for all applicable dates.`}</p>
          <p>After the applicable deadline, support or service availability may change. The exact consequences are service-specific; verify them in the announcement and plan to finish your migration ahead of time.</p>
          ${sourceLink(record, 'Verify dates and consequences')}
        </section>
        <section id="progress"><h2><span class="section-number">5</span>How can I track progress?</h2>
          <p class="section-intro">What work remains, and what needs attention.</p>
          <p>Use this planning checklist as a starting point. Record resource-level owners, target dates, blockers, and evidence in your team’s tracking system.</p>
          <div class="progress-summary" id="progress-summary" role="status" aria-live="polite"></div>
          <div class="checklist">${checklist.map((text, index) => `<label><input type="checkbox" data-step="${index}"><span>${e(text)}</span></label>`).join('')}</div>
          <p class="storage-note" id="storage-note">Checklist progress is saved only in this browser, not in Azure or a shared team system. Clearing browser data removes it.</p>
        </section>
      </article>
      <aside class="detail-rail" aria-label="Retirement facts"><div class="fact-card"><span class="eyebrow">RETIREMENT AT A GLANCE</span><dl><dt>Retirement date</dt><dd>${record.retirementDate ? `<time datetime="${e(record.retirementDate)}">${e(formatDate(record.retirementDate))}</time>` : 'Not specified as an exact date'}</dd><dt>Service</dt><dd>${e(record.service)}</dd><dt>Announced</dt><dd>${e(formatDate(record.announcedOn))}</dd><dt>Source</dt><dd>Microsoft Azure Updates</dd></dl>${sourceLink(record)}</div><div class="notice">Dates may be revised. Always verify the latest information with Microsoft.</div></aside>
    </div>${footer()}`;
  const key = `retirements-progress:${record.id}`;
  let saved = [];
  try {
    const value = JSON.parse(localStorage.getItem(key) || '[]');
    if (Array.isArray(value)) saved = value;
  } catch { /* Invalid or unavailable storage starts with an empty checklist. */ }
  const checkboxes = [...document.querySelectorAll('[data-step]')];
  const updateProgress = () => {
    const done = checkboxes.filter(input => input.checked).length;
    document.querySelector('#progress-summary').textContent = `${done} of ${checklist.length} planning steps complete · ${checklist.length - done} remaining`;
  };
  for (const input of checkboxes) {
    input.checked = saved[Number(input.dataset.step)] === true;
    input.addEventListener('change', () => {
      updateProgress();
      try { localStorage.setItem(key, JSON.stringify(checkboxes.map(input => input.checked))); }
      catch { document.querySelector('#storage-note').textContent = 'Browser storage is unavailable. Progress will not be saved when you leave this page.'; }
    });
  }
  updateProgress();
}

function updateNav() {
  for (const link of document.querySelectorAll('[data-nav]')) {
    const active = !location.hash.startsWith('#/retirements/') && link.dataset.nav === (filters?.status === 'all' ? 'all' : filters?.status);
    if (active) link.setAttribute('aria-current', 'page');
    else link.removeAttribute('aria-current');
  }
}
function render() {
  document.querySelector('.sidebar').classList.remove('open');
  document.querySelector('.mobile-menu').setAttribute('aria-expanded', 'false');
  const route = location.hash.split('?')[0];
  if (route.startsWith('#/retirements/')) {
    let id;
    try { id = decodeURIComponent(route.slice('#/retirements/'.length)); } catch { id = ''; }
    renderDetail(id);
  } else {
    directoryHash = location.hash.startsWith('#/') ? location.hash : '#/';
    renderDirectory();
  }
  updateNav();
}
window.addEventListener('hashchange', () => {
  render();
  window.scrollTo(0, 0);
  document.querySelector('#main').focus({ preventScroll: true });
});
render();
