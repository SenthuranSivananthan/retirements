import catalog from './data.js';
import { RETIREMENT_WINDOWS, categoriesOf, directoryUrl, escapeHtml as e, filterRecords, formatDate, groupRetirements, inRetirementWindow, recordUrl, retirementCountdown, retirementWindow, retirementYear, statusOf } from './catalog.js';
function element(selector) {
    const node = document.querySelector(selector);
    if (!node)
        throw new Error(`Required site element is missing: ${selector}`);
    return node;
}
const home = document.body.dataset.home;
if (!home)
    throw new Error('The site base URL is missing');
const homeUrl = new URL(home, location.href);
const isDirectory = document.body.dataset.page === 'home';
const activeRecord = catalog.records.find(record => record.id === document.body.dataset.record);
const services = new Set(catalog.records.flatMap(record => record.services));
const categories = new Set(catalog.records.flatMap(categoriesOf));
const years = new Set(groupRetirements(catalog.records).map(group => group.year));
const labels = { upcoming: 'Upcoming', soon: 'Within 90 days', retired: 'Retired', unknown: 'Date to confirm' };
const yearLabel = (year) => year === 'unknown' ? 'Unconfirmed year' : year;
const directoryLink = (filters) => directoryUrl(filters, homeUrl.pathname);
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${name === 'clock' ? '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>' : '<path d="M5 12h14m-5-5 5 5-5 5"/>'}</svg>`;
function detailLink(record, context = {}) {
    const url = new URL(recordUrl(record).slice(1), homeUrl);
    url.search = new URLSearchParams(Object.entries(context).filter(([, value]) => value)).toString();
    return `${url.pathname}${url.search}`;
}
function statusFilter(value) {
    return value === 'upcoming' || value === 'soon' || value === 'retired' || value === 'unknown' ? value : 'all';
}
function sortOrder(value) {
    return value === 'date' || value === 'title' ? value : 'newest';
}
function windowFilter(value) {
    return RETIREMENT_WINDOWS.includes(value) ? value : '';
}
function readFilters() {
    const params = new URLSearchParams(location.search);
    const service = params.get('service') || '';
    const year = params.get('year') || '';
    const category = params.get('category') || '';
    return {
        q: params.get('q') || '', service: services.has(service) ? service : '',
        year: years.has(year) ? year : '', category: categories.has(category) ? category : '',
        status: statusFilter(params.get('status')), sort: sortOrder(params.get('sort')),
        window: windowFilter(params.get('window')),
    };
}
let filters = readFilters();
let visible = 24;
function redirectLegacyRoute() {
    if (!location.hash.startsWith('#/'))
        return false;
    const [route, query = ''] = location.hash.slice(1).split('?');
    if (route.startsWith('/retirements/')) {
        let id;
        try {
            id = decodeURIComponent(route.slice('/retirements/'.length));
        }
        catch {
            location.replace(new URL('404.html', homeUrl));
            return true;
        }
        const record = catalog.records.find(record => record.id === id);
        const target = record
            ? new URL(detailLink(record), location.origin) : new URL('404.html', homeUrl);
        target.search = query;
        location.replace(target);
    }
    else {
        const target = new URL(homeUrl);
        target.search = query;
        location.replace(target);
    }
    return true;
}
function redirectMovedDetail() {
    if (document.body.dataset.page !== 'not-found' || !location.pathname.startsWith(homeUrl.pathname))
        return false;
    const path = location.pathname.slice(homeUrl.pathname.length);
    const match = /^retirements\/(?:(?:\d{4}-\d{2}-\d{2}|unknown-date)\/)?([^/]+)\/?$/.exec(path);
    if (!match)
        return false;
    let id;
    try {
        id = decodeURIComponent(match[1]);
    }
    catch {
        return false;
    }
    const record = catalog.records.find(record => record.id === id);
    if (!record)
        return false;
    const target = new URL(detailLink(record), location.origin);
    target.search = location.search;
    target.hash = location.hash;
    if (target.href === location.href)
        return false;
    location.replace(target);
    return true;
}
function setNavigation(open) {
    element('.mobile-menu').setAttribute('aria-expanded', String(open));
    element('.sidebar').classList.toggle('open', open);
    element('.nav-backdrop').hidden = !open;
    document.body.classList.toggle('nav-open', open);
}
function closeDownloads() {
    element('#download-menu').hidden = true;
    element('#downloads').setAttribute('aria-expanded', 'false');
}
function closeSearch() {
    element('#search-results').hidden = true;
}
function updateThemeLabel() {
    element('#theme').setAttribute('aria-label', `Switch to ${document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark'} theme`);
}
function bindShell() {
    try {
        document.documentElement.dataset.theme = localStorage.getItem('retirements-theme')
            || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
    }
    catch { /* The theme toggle still works when storage is disabled. */ }
    updateThemeLabel();
    element('#theme').addEventListener('click', () => {
        const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
        document.documentElement.dataset.theme = theme;
        try {
            localStorage.setItem('retirements-theme', theme);
        }
        catch { /* The theme still changes without storage. */ }
        updateThemeLabel();
    });
    element('.mobile-menu').addEventListener('click', () => setNavigation(element('.mobile-menu').getAttribute('aria-expanded') !== 'true'));
    element('.nav-backdrop').addEventListener('click', () => setNavigation(false));
    element('#navigation').addEventListener('click', event => {
        if (event.target instanceof Element && event.target.closest('a'))
            setNavigation(false);
    });
    element('#downloads').addEventListener('click', () => {
        const menu = element('#download-menu');
        menu.hidden = !menu.hidden;
        element('#downloads').setAttribute('aria-expanded', String(!menu.hidden));
    });
    const search = element('#global-search');
    const results = element('#search-results');
    const searchCatalog = () => {
        const q = search.value.trim();
        if (q.length < 2) {
            closeSearch();
            return;
        }
        const hits = filterRecords(catalog.records, { q, sort: 'newest' }).slice(0, 8);
        results.innerHTML = hits.length
            ? hits.map(record => `<a href="${e(detailLink(record))}"><strong>${e(record.title)}</strong><small>${e(record.service)}</small></a>`).join('')
            : '<p>No matching retirements.</p>';
        results.hidden = false;
    };
    search.addEventListener('input', searchCatalog);
    search.addEventListener('focus', searchCatalog);
    element('.header-search').addEventListener('focusout', event => {
        if (!(event.relatedTarget instanceof Node) || !element('.header-search').contains(event.relatedTarget))
            closeSearch();
    });
    element('.header-search').addEventListener('keydown', event => {
        const links = [...results.querySelectorAll('a')];
        if (results.hidden || !links.length)
            return;
        const current = links.findIndex(link => link === document.activeElement);
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
            event.preventDefault();
            const next = event.key === 'ArrowDown' ? current + 1 : (current < 0 ? links.length - 1 : current - 1);
            links[(next + links.length) % links.length]?.focus();
        }
        else if (event.key === 'Enter' && event.target === search) {
            event.preventDefault();
            links[0]?.click();
        }
    });
    document.addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
            event.preventDefault();
            search.focus();
            search.select();
        }
        if (event.key === 'Escape') {
            if (!results.hidden)
                search.focus();
            else if (!element('#download-menu').hidden)
                element('#downloads').focus();
            else if (element('.sidebar').classList.contains('open'))
                element('.mobile-menu').focus();
            closeSearch();
            closeDownloads();
            setNavigation(false);
        }
    });
    document.addEventListener('click', event => {
        if (!(event.target instanceof Element))
            return;
        if (!event.target.closest('.header-search') || event.target.closest('#search-results a'))
            closeSearch();
        if (!event.target.closest('.downloads') || event.target.closest('#download-menu a'))
            closeDownloads();
    });
}
function updateNav() {
    const year = activeRecord ? retirementYear(activeRecord) : filters.year;
    const recordCategories = activeRecord ? categoriesOf(activeRecord).sort() : [];
    const category = activeRecord
        ? (recordCategories.includes(filters.category) ? filters.category : recordCategories[0]) : filters.category;
    for (const link of document.querySelectorAll('#navigation a[data-nav], #navigation a[data-year]')) {
        const active = link.dataset.record
            ? activeRecord?.id === link.dataset.record && link.dataset.year === year && link.dataset.category === category
            : link.dataset.year
                ? isDirectory && link.dataset.year === filters.year && link.dataset.category === filters.category
                : isDirectory && !filters.year && !filters.category && !filters.window && link.dataset.nav === filters.status;
        if (active) {
            link.setAttribute('aria-current', 'page');
            let group = link.closest('details');
            while (group) {
                group.open = true;
                group = group.parentElement?.closest('details') || null;
            }
        }
        else
            link.removeAttribute('aria-current');
    }
}
function renderResults() {
    const records = filterRecords(catalog.records, filters);
    element('#result-count').textContent = `Showing ${Math.min(visible, records.length)} of ${records.length} retirements`;
    element('#results').innerHTML = records.length ? records.slice(0, visible).map(record => {
        const deadline = record.questions.deadline;
        const status = statusOf(deadline);
        const url = detailLink(record, filters);
        return `<article class="card">
      <div class="card-top"><span class="service-name">${e(record.service)}</span><span class="badge ${status}" data-deadline="${e(deadline.date || '')}"><span></span>${labels[status]}</span></div>
      <h3><a href="${e(url)}">${e(record.title)}</a></h3><p>${e(record.summary)}</p>
      <div class="card-bottom"><span>${icon('clock')}${deadline.date ? `<time datetime="${e(deadline.date)}">${e(formatDate(deadline.date))}</time>` : 'Date not specified'}</span><a href="${e(url)}" aria-label="View details: ${e(record.title)}">View details ${icon('arrow')}</a></div>
    </article>`;
    }).join('') : `<div class="empty"><h3>No matching retirements</h3><p>Try a different keyword, service, date window, or category.</p><a class="button" href="${e(homeUrl.pathname)}">Clear filters</a></div>`;
    element('#load-more').hidden = records.length <= visible;
    const group = element('#group-filter');
    group.hidden = !filters.year && !filters.category && filters.status === 'all';
    group.innerHTML = `${filters.year ? `<span>Retirement year: <strong>${e(yearLabel(filters.year))}</strong></span>` : ''}${filters.category ? `<span>Azure category: <strong>${e(filters.category)}</strong></span>` : ''}${filters.year || filters.category ? `<a href="${e(directoryLink({ ...filters, year: '', category: '' }))}">Clear year and category</a>` : ''}${filters.status !== 'all' ? `<span>Status: <strong>${e(labels[filters.status])}</strong></span><a href="${e(directoryLink({ ...filters, status: 'all' }))}">Clear status</a>` : ''}`;
    for (const card of document.querySelectorAll('[data-window]')) {
        if (card.dataset.window === filters.window)
            card.setAttribute('aria-current', 'true');
        else
            card.removeAttribute('aria-current');
    }
}
function bindDirectory() {
    for (const control of document.querySelectorAll('[data-enhancement]'))
        control.hidden = false;
    for (const [id, key, event] of [['search', 'q', 'input'], ['service', 'service', 'change'], ['sort', 'sort', 'change'], ['window', 'window', 'change']]) {
        const control = element(`#${id}`);
        control.value = key === 'window' ? filters.window || filters.year : filters[key];
        control.addEventListener(event, () => {
            if (key === 'sort')
                filters.sort = sortOrder(control.value);
            else if (key === 'window') {
                filters.window = windowFilter(control.value);
                filters.year = years.has(control.value) ? control.value : '';
                filters.status = 'all';
            }
            else
                filters[key] = control.value;
            visible = 24;
            history.replaceState(null, '', directoryLink(filters));
            renderResults();
            updateNav();
        });
    }
    element('#load-more').addEventListener('click', () => {
        const firstNewCard = visible;
        visible += 24;
        renderResults();
        document.querySelectorAll('.card h3 a')[firstNewCard]?.focus();
    });
    window.addEventListener('popstate', () => {
        filters = readFilters();
        visible = 24;
        for (const [id, key] of [['search', 'q'], ['service', 'service'], ['sort', 'sort'], ['window', 'window']]) {
            element(`#${id}`).value = key === 'window' ? filters.window || filters.year : filters[key];
        }
        renderResults();
        updateNav();
    });
    renderResults();
}
function bindProgress(record) {
    const key = `retirements-progress:${record.id}`;
    let saved = [];
    try {
        const value = JSON.parse(localStorage.getItem(key) || '[]');
        if (Array.isArray(value))
            saved = value;
    }
    catch { /* Invalid or unavailable storage starts with an empty checklist. */ }
    const checkboxes = [...document.querySelectorAll('[data-step]')];
    const update = () => {
        const done = checkboxes.filter(input => input.checked).length;
        element('#progress-summary').textContent = `${done} of ${checkboxes.length} planning steps complete · ${checkboxes.length - done} remaining`;
    };
    for (const input of checkboxes) {
        input.disabled = false;
        input.checked = saved[Number(input.dataset.step)] === true;
        input.addEventListener('change', () => {
            update();
            try {
                localStorage.setItem(key, JSON.stringify(checkboxes.map(input => input.checked)));
            }
            catch {
                element('#storage-note').textContent = 'Browser storage is unavailable. Progress will not be saved when you leave this page.';
            }
        });
    }
    update();
}
function updateArticleNav() {
    const links = [...document.querySelectorAll('.article-nav a')];
    let active = links[0];
    for (const link of links) {
        if ((document.getElementById(link.hash.slice(1))?.getBoundingClientRect().top ?? Infinity) <= 130)
            active = link;
    }
    for (const link of links) {
        if (link === active)
            link.setAttribute('aria-current', 'location');
        else
            link.removeAttribute('aria-current');
    }
}
function updateDates() {
    for (const badge of document.querySelectorAll('.badge[data-deadline]')) {
        const status = statusOf({ date: badge.dataset.deadline || null });
        badge.className = `badge ${status}`;
        badge.innerHTML = `<span></span>${labels[status]}`;
    }
    if (activeRecord) {
        const countdown = element('[data-countdown]');
        countdown.className = `retirement-countdown ${statusOf(activeRecord.questions.deadline)}`;
        element('[data-countdown] strong').textContent = retirementCountdown(activeRecord.questions.deadline);
    }
    if (isDirectory) {
        element('#upcoming-count').textContent = String(catalog.records.filter(record => ['upcoming', 'soon'].includes(statusOf(record.questions.deadline))).length);
        element('#soon-count').textContent = String(catalog.records.filter(record => statusOf(record.questions.deadline) === 'soon').length);
        const today = new Date().toISOString().slice(0, 10);
        const asOf = element('#outlook-date');
        asOf.dateTime = today;
        asOf.textContent = formatDate(today);
        for (const card of document.querySelectorAll('[data-window]')) {
            const window = card.dataset.window;
            const bounds = retirementWindow(window, today);
            card.querySelector('[data-window-count]').textContent = String(catalog.records.filter(record => inRetirementWindow(record.questions.deadline, bounds)).length);
            card.querySelector('[data-window-range]').textContent = bounds.range;
        }
    }
}
if (!redirectLegacyRoute() && !redirectMovedDetail()) {
    bindShell();
    if (isDirectory)
        bindDirectory();
    if (activeRecord) {
        for (const link of document.querySelectorAll('[data-back]'))
            link.href = directoryLink(filters);
        bindProgress(activeRecord);
        window.addEventListener('scroll', updateArticleNav, { passive: true });
        updateArticleNav();
    }
    updateNav();
    updateDates();
    let day = new Date().toISOString().slice(0, 10);
    const refreshDay = () => {
        const current = new Date().toISOString().slice(0, 10);
        if (day === current)
            return;
        day = current;
        if (isDirectory)
            renderResults();
        updateDates();
    };
    window.setInterval(refreshDay, 60000);
    document.addEventListener('visibilitychange', refreshDay);
    window.addEventListener('hashchange', redirectLegacyRoute);
}
