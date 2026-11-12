import catalog from './data.js';
import { RETIREMENT_WINDOWS, announcedYears, categoriesOf, customerLeadTime, directoryUrl, escapeHtml as e, filterRecords, findDetailRecord, formatDate, groupRetirements, groupTimeline, inRetirementWindow, recordUrls, retirementCountdown, retirementWindow, retirementYear, servicesForCategory, statusOf } from './catalog.js';
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
const recordPaths = recordUrls(catalog.records);
const visibleRecords = catalog.records.filter(record => !record.hidden);
const categories = new Set(visibleRecords.flatMap(categoriesOf));
const years = new Set(groupRetirements(visibleRecords).map(group => group.year));
const labels = { upcoming: 'Upcoming', soon: 'Within 90 days', retired: 'Retired', unknown: 'Date to confirm' };
const yearLabel = (year) => year === 'unknown' ? 'Unconfirmed year' : year;
const directoryLink = (filters) => directoryUrl(filters, homeUrl.pathname);
const icon = (name) => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${name === 'clock' ? '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>' : '<path d="M5 12h14m-5-5 5 5-5 5"/>'}</svg>`;
function detailLink(record, context = {}) {
    const path = recordPaths.get(record.id);
    if (!path)
        throw new Error(`Missing retirement route: ${record.id}`);
    const url = new URL(path.slice(1), homeUrl);
    url.search = new URLSearchParams(Object.entries(context).filter(([, value]) => value)).toString();
    return `${url.pathname}${url.search}`;
}
function statusFilter(value) {
    return value === 'upcoming' || value === 'soon' || value === 'retired' || value === 'unknown' ? value : 'all';
}
function windowFilter(value) {
    return RETIREMENT_WINDOWS.includes(value) ? value : '';
}
function announcementYearFilter(value) {
    return announcedYears().includes(value) ? value : '';
}
function readFilters() {
    const params = new URLSearchParams(location.search);
    const service = params.get('service') || '';
    const year = params.get('year') || '';
    const requestedCategory = params.get('category') || '';
    const category = categories.has(requestedCategory) ? requestedCategory : '';
    return {
        q: params.get('q') || '', service: servicesForCategory(visibleRecords, category).includes(service) ? service : '',
        year: years.has(year) ? year : '', category,
        status: statusFilter(params.get('status')), sort: 'date-desc',
        window: windowFilter(params.get('window')),
        announcedYear: announcementYearFilter(params.get('announcedYear')),
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
    const record = findDetailRecord(catalog.records, recordPaths, match[1]);
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
        const hits = filterRecords(visibleRecords, { q, sort: 'newest' }).slice(0, 8);
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
    const navigationFilters = isDirectory ? filters : {};
    const matches = new Map(filterRecords(visibleRecords, navigationFilters).map(record => [record.id, record]));
    element('#year-navigation-count').textContent = String(matches.size);
    for (const yearGroup of document.querySelectorAll('#navigation .year-group')) {
        const year = yearGroup.dataset.yearGroup;
        const yearIds = new Set();
        const yearContext = { ...navigationFilters, year };
        yearGroup.querySelector(':scope > a[data-year]').href = `${directoryLink(yearContext)}#catalog`;
        for (const categoryGroup of yearGroup.querySelectorAll('.category-group')) {
            const category = categoryGroup.dataset.categoryGroup;
            const context = { ...yearContext, category };
            const categoryIds = new Set();
            categoryGroup.querySelector('.category-all').href = `${directoryLink(context)}#catalog`;
            for (const link of categoryGroup.querySelectorAll('.nav-record')) {
                const record = matches.get(link.dataset.record);
                link.hidden = !record || Boolean(navigationFilters.category && category !== navigationFilters.category);
                if (!link.hidden) {
                    categoryIds.add(record.id);
                    yearIds.add(record.id);
                    link.href = detailLink(record, context);
                }
            }
            categoryGroup.hidden = categoryIds.size === 0;
            categoryGroup.querySelector('summary .nav-count').textContent = String(categoryIds.size);
        }
        yearGroup.hidden = yearIds.size === 0;
        yearGroup.querySelector(':scope > summary .nav-count').textContent = String(yearIds.size);
    }
    element('#navigation-empty').hidden = matches.size > 0;
    const year = activeRecord ? retirementYear(activeRecord) : filters.year;
    const recordCategories = activeRecord ? categoriesOf(activeRecord).sort() : [];
    const category = activeRecord
        ? (recordCategories.includes(filters.category) ? filters.category : recordCategories[0]) : filters.category;
    for (const link of document.querySelectorAll('#navigation a[data-nav], #navigation a[data-year]')) {
        const active = link.dataset.record
            ? activeRecord?.id === link.dataset.record && link.dataset.year === year && link.dataset.category === category
            : link.dataset.year
                ? isDirectory && link.dataset.year === filters.year && link.dataset.category === filters.category
                : isDirectory && !filters.year && !filters.category && !filters.window && !filters.announcedYear && link.dataset.nav === filters.status;
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
function renderTimelineEntry(record) {
    const deadline = record.questions.deadline;
    const status = statusOf(deadline);
    const url = detailLink(record, filters);
    return `<li class="timeline-entry" data-record="${e(record.id)}">
      <div class="timeline-date"><span class="timeline-date-label">Retirement date</span>${deadline.date ? `<time datetime="${e(deadline.date)}">${e(formatDate(deadline.date))}</time>` : '<span>Date to confirm</span>'}<span class="timeline-date-label timeline-lead-time-label">Customer lead time</span><span class="timeline-lead-time">${e(customerLeadTime(record.announcedOn, deadline.date))}</span></div>
      <article class="timeline-content">
        <span class="badge ${status}" data-deadline="${e(deadline.date || '')}"><span></span>${labels[status]}</span>
        <h5><a href="${e(url)}">${e(record.title)}</a></h5><p>${e(record.summary)}</p>
        <a class="timeline-detail" href="${e(url)}" aria-label="View details: ${e(record.title)}">View details ${icon('arrow')}</a>
      </article>
    </li>`;
}
function renderResults() {
    const records = filterRecords(visibleRecords, filters);
    element('#result-count').textContent = `Showing ${Math.min(visible, records.length)} of ${records.length} retirements`;
    const groups = groupTimeline(records.slice(0, visible), filters);
    element('#results').innerHTML = records.length ? groups.map((category, categoryIndex) => `
      <section class="timeline-category" data-category="${e(category.name)}" aria-labelledby="timeline-category-${categoryIndex}">
        <div class="timeline-category-heading"><h3 id="timeline-category-${categoryIndex}">${e(category.name)}</h3><span>${category.count} ${category.count === 1 ? 'retirement' : 'retirements'}</span></div>
        ${category.services.map((service, serviceIndex) => `
        <section class="timeline-service" data-service="${e(service.name)}" aria-labelledby="timeline-service-${categoryIndex}-${serviceIndex}">
          <div class="timeline-service-heading"><h4 id="timeline-service-${categoryIndex}-${serviceIndex}">${e(service.name)}</h4><span>${service.records.length} ${service.records.length === 1 ? 'retirement' : 'retirements'}</span></div>
          <ol class="timeline-events">${service.records.map(renderTimelineEntry).join('')}</ol>
        </section>`).join('')}
      </section>`).join('') : `<div class="empty"><h3>No matching retirements</h3><p>Try a different keyword, service, retirement window, announcement year, or category.</p><a class="button" href="${e(homeUrl.pathname)}">Clear filters</a></div>`;
    element('#load-more').hidden = records.length <= visible;
    const group = element('#group-filter');
    group.hidden = !filters.year && !filters.announcedYear && !filters.category && filters.status === 'all';
    group.innerHTML = `${filters.year ? `<span>Retirement year: <strong>${e(yearLabel(filters.year))}</strong></span>` : ''}${filters.announcedYear ? `<span>Announced in: <strong>${e(filters.announcedYear)}</strong></span><a href="${e(directoryLink({ ...filters, announcedYear: '' }))}">Clear announcement year</a>` : ''}${filters.category ? `<span>Azure category: <strong>${e(filters.category)}</strong></span>` : ''}${filters.year || filters.category ? `<a href="${e(directoryLink({ ...filters, year: '', category: '' }))}">Clear year and category</a>` : ''}${filters.status !== 'all' ? `<span>Status: <strong>${e(labels[filters.status])}</strong></span><a href="${e(directoryLink({ ...filters, status: 'all' }))}">Clear status</a>` : ''}`;
    for (const card of document.querySelectorAll('[data-window]')) {
        if (card.dataset.window === filters.window)
            card.setAttribute('aria-current', 'true');
        else
            card.removeAttribute('aria-current');
    }
}
function updateServiceOptions() {
    const services = servicesForCategory(visibleRecords, filters.category);
    if (!services.includes(filters.service))
        filters.service = '';
    const control = element('#service');
    control.replaceChildren(new Option('All services', ''), ...services.map(service => new Option(service, service)));
    control.value = filters.service;
}
function updateAnnouncementYearOptions() {
    const control = element('#announced-year');
    control.replaceChildren(
        new Option('All announcement dates', ''),
        ...announcedYears().map(year => new Option(`Announced in ${year}`, year)),
    );
}
function restoreDirectoryFilters() {
    filters = readFilters();
    visible = 24;
    updateServiceOptions();
    updateAnnouncementYearOptions();
    for (const [id, key] of [['search', 'q'], ['category', 'category'], ['service', 'service'], ['window', 'window'], ['announced-year', 'announcedYear']]) {
        element(`#${id}`).value = key === 'window' ? filters.window || filters.year : filters[key];
    }
    renderResults();
    updateNav();
}
function bindDirectory() {
    for (const control of document.querySelectorAll('[data-enhancement]'))
        control.hidden = false;
    updateServiceOptions();
    updateAnnouncementYearOptions();
    for (const [id, key, event] of [['search', 'q', 'input'], ['category', 'category', 'change'], ['service', 'service', 'change'], ['window', 'window', 'change'], ['announced-year', 'announcedYear', 'change']]) {
        const control = element(`#${id}`);
        control.value = key === 'window' ? filters.window || filters.year : filters[key];
        control.addEventListener(event, () => {
            if (key === 'window') {
                filters.window = windowFilter(control.value);
                filters.year = years.has(control.value) ? control.value : '';
                filters.status = 'all';
            }
            else if (key === 'announcedYear')
                filters.announcedYear = announcementYearFilter(control.value);
            else
                filters[key] = control.value;
            if (key === 'category')
                updateServiceOptions();
            visible = 24;
            history.replaceState(null, '', directoryLink(filters));
            renderResults();
            updateNav();
        });
    }
    element('#load-more').addEventListener('click', () => {
        const nextRecord = filterRecords(visibleRecords, filters)[visible];
        visible += 24;
        renderResults();
        [...document.querySelectorAll('.timeline-entry')].find(entry => entry.dataset.record === nextRecord?.id)
            ?.querySelector('h5 a')?.focus();
    });
    element('#reset-filters').addEventListener('click', () => {
        history.replaceState(null, '', `${homeUrl.pathname}#catalog`);
        restoreDirectoryFilters();
    });
    window.addEventListener('popstate', restoreDirectoryFilters);
    renderResults();
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
        element('#upcoming-count').textContent = String(visibleRecords.filter(record => ['upcoming', 'soon'].includes(statusOf(record.questions.deadline))).length);
        element('#soon-count').textContent = String(visibleRecords.filter(record => statusOf(record.questions.deadline) === 'soon').length);
        const today = new Date().toISOString().slice(0, 10);
        const asOf = element('#outlook-date');
        asOf.dateTime = today;
        asOf.textContent = formatDate(today);
        for (const card of document.querySelectorAll('[data-window]')) {
            const window = card.dataset.window;
            const bounds = retirementWindow(window, today);
            card.querySelector('[data-window-count]').textContent = String(visibleRecords.filter(record => inRetirementWindow(record.questions.deadline, bounds)).length);
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
        updateNav();
        updateDates();
    };
    window.setInterval(refreshDay, 60000);
    document.addEventListener('visibilitychange', refreshDay);
    window.addEventListener('hashchange', redirectLegacyRoute);
}
