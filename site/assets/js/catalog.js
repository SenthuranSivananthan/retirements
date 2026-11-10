export function daysUntilRetirement(deadline, today = new Date().toISOString().slice(0, 10)) {
    return deadline.date === null ? null : Math.round((Date.parse(deadline.date) - Date.parse(today)) / 86400000);
}
export function statusOf(deadline, today) {
    const days = daysUntilRetirement(deadline, today);
    if (days === null)
        return 'unknown';
    if (days < 0)
        return 'retired';
    return days <= 90 ? 'soon' : 'upcoming';
}
export function retirementCountdown(deadline, today) {
    const days = daysUntilRetirement(deadline, today);
    return days === null ? 'Retirement date to confirm'
        : days < 0 ? 'Retired'
            : days === 0 ? 'Retires today (0 days remaining)'
                : `${days} ${days === 1 ? 'day' : 'days'} remaining`;
}
export const RETIREMENT_WINDOWS = ['retired-year', '6', '12', '18'];
export function retirementWindow(window, today = new Date().toISOString().slice(0, 10)) {
    if (!RETIREMENT_WINDOWS.includes(window))
        throw new Error(`Unknown retirement window: ${window}`);
    const current = new Date(`${today}T00:00:00Z`);
    const retired = window === 'retired-year';
    const start = retired ? `${today.slice(0, 4)}-01-01` : `${today.slice(0, 7)}-01`;
    let end = today;
    if (!retired) {
        const target = new Date(Date.UTC(current.getUTCFullYear(), current.getUTCMonth() + Number(window) + 1, 0));
        end = target.toISOString().slice(0, 10);
    }
    return {
        key: window, start, end, retired,
        label: retired ? 'Retired this calendar year' : `Next ${window} months`,
        range: retired ? `Before today, since ${formatDate(start)}` : `${formatDate(start)} – ${formatDate(end)}`,
    };
}
export function inRetirementWindow(deadline, bounds) {
    return deadline.date !== null && deadline.date >= bounds.start
        && (bounds.retired ? deadline.date < bounds.end : deadline.date <= bounds.end);
}
export function retirementYear(record) {
    const { date, month } = record.questions.deadline;
    if (date)
        return date.slice(0, 4);
    return month?.match(/^(?:January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})$/)?.[1] || 'unknown';
}
export function categoriesOf(record) {
    return record.categories?.length ? [...new Set(record.categories)] : ['Uncategorized'];
}
export function servicesOf(record) {
    return [...new Set(record.services.length ? record.services : [record.service])];
}
export function servicesForCategory(records, category = '') {
    return [...new Set(records
        .filter(record => !category || categoriesOf(record).includes(category))
        .flatMap(servicesOf))].sort((a, b) => a.localeCompare(b));
}
function compareTimelineDates(a, b) {
    return (b.questions.deadline.date || '').localeCompare(a.questions.deadline.date || '')
        || a.title.localeCompare(b.title) || a.id.localeCompare(b.id);
}
export function groupTimeline(records, filters = {}) {
    const groups = new Map();
    for (const record of records) {
        for (const category of categoriesOf(record)) {
            if (filters.category && category !== filters.category)
                continue;
            if (!groups.has(category))
                groups.set(category, new Map());
            const services = groups.get(category);
            for (const service of servicesOf(record)) {
                if (filters.service && service !== filters.service)
                    continue;
                if (!services.has(service))
                    services.set(service, []);
                services.get(service).push(record);
            }
        }
    }
    return [...groups].filter(([, services]) => services.size)
        .sort(([a], [b]) => a.localeCompare(b))
        .map(([name, services]) => ({
            name,
            count: new Set([...services.values()].flat().map(record => record.id)).size,
            services: [...services].sort(([a], [b]) => a.localeCompare(b))
                .map(([name, records]) => ({ name, records: [...records].sort(compareTimelineDates) })),
        }));
}
export function groupRetirements(records) {
    const years = new Map();
    for (const record of records) {
        const year = retirementYear(record);
        const group = years.get(year);
        if (group)
            group.push(record);
        else
            years.set(year, [record]);
    }
    return [...years].sort(([a], [b]) => a === 'unknown' ? 1 : b === 'unknown' ? -1 : b.localeCompare(a))
        .map(([year, yearRecords]) => {
        const sorted = [...yearRecords].sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id));
        const categories = new Map();
        for (const record of sorted) {
            for (const category of categoriesOf(record)) {
                const group = categories.get(category);
                if (group)
                    group.push(record);
                else
                    categories.set(category, [record]);
            }
        }
        return {
            year,
            records: sorted,
            categories: [...categories].sort(([a], [b]) => a.localeCompare(b)).map(([name, records]) => ({ name, records })),
        };
    });
}
export function directoryUrl(filters, base = '/') {
    const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
    return query.size ? `${base}?${query}` : base;
}
export function recordUrl(record) {
    return `/retirements/${record.questions.deadline.date || 'unknown-date'}/${encodeURIComponent(record.id)}/`;
}
export function filterRecords(records, filters, today = new Date().toISOString().slice(0, 10)) {
    const terms = (filters.q || '').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    const window = filters.window ? retirementWindow(filters.window, today) : null;
    return records.filter(record => {
        const status = statusOf(record.questions.deadline, today);
        const text = `${record.title} ${record.service} ${record.summary} ${record.questions.what.announcement}`.toLocaleLowerCase();
        return terms.every(term => text.includes(term))
            && (!filters.service || servicesOf(record).includes(filters.service))
            && (!filters.year || retirementYear(record) === filters.year)
            && (!filters.category || categoriesOf(record).includes(filters.category))
            && (!window || inRetirementWindow(record.questions.deadline, window))
            && (!filters.status || filters.status === 'all' || status === filters.status
                || (filters.status === 'upcoming' && status === 'soon'));
    }).sort((a, b) => {
        if (filters.sort === 'title')
            return a.title.localeCompare(b.title);
        if (filters.sort === 'newest')
            return (b.announcedOn || '').localeCompare(a.announcedOn || '') || a.title.localeCompare(b.title);
        if (filters.sort === 'date-desc')
            return compareTimelineDates(a, b);
        return (a.questions.deadline.date || '9999').localeCompare(b.questions.deadline.date || '9999') || a.title.localeCompare(b.title);
    });
}
export function formatDate(date) {
    return date ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
        .format(new Date(`${date}T00:00:00Z`)) : 'Date not specified';
}
export function escapeHtml(value = '') {
    const entities = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
    return String(value).replace(/[&<>"']/g, char => entities[char]);
}
export function safeUrl(value) {
    try {
        const url = new URL(value);
        return url.protocol === 'https:' ? url.href : null;
    }
    catch {
        return null;
    }
}
function isObject(value) {
    return typeof value === 'object' && value !== null;
}
function isNullableString(value) {
    return value === null || typeof value === 'string';
}
function isCatalogDate(value) {
    if (value === null)
        return true;
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value))
        return false;
    const parsed = new Date(`${value}T00:00:00Z`);
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}
function hasStrings(value, keys) {
    return isObject(value) && keys.every(key => typeof value[key] === 'string');
}
function isLink(value) {
    return hasStrings(value, ['title', 'url']);
}
function isChecklist(value) {
    return Array.isArray(value) && value.length > 0 && value.every((step) => typeof step === 'string');
}
function isQuestions(value) {
    if (!isObject(value) || Object.keys(value).length !== 5)
        return false;
    const { what, actions, impact, deadline, progress } = value;
    return hasStrings(what, ['question', 'introduction', 'announcement', 'financialConsiderations'])
        && hasStrings(actions, ['question', 'introduction', 'guidance', 'supportGuidance'])
        && isNullableString(actions.recommendedAction) && isLink(actions.support)
        && Array.isArray(actions.resources) && actions.resources.every(isLink)
        && hasStrings(impact, ['question', 'introduction', 'guidance', 'notice'])
        && isChecklist(impact.checklist) && isLink(impact.advisor)
        && hasStrings(deadline, ['question', 'introduction', 'dateGuidance', 'consequences'])
        && isCatalogDate(deadline.date) && isNullableString(deadline.month)
        && hasStrings(progress, ['question', 'introduction', 'guidance', 'storageNote'])
        && isChecklist(progress.checklist);
}
function isRetirementRecord(value) {
    return isObject(value)
        && typeof value.id === 'string' && typeof value.title === 'string'
        && typeof value.service === 'string' && typeof value.summary === 'string'
        && typeof value.sourceUrl === 'string' && isCatalogDate(value.announcedOn) && isCatalogDate(value.lastUpdatedOn)
        && typeof value.manuallyEnriched === 'boolean'
        && (value.categories === undefined || (Array.isArray(value.categories) && value.categories.length > 0
            && value.categories.every((category) => typeof category === 'string' && category.trim().length > 0)))
        && isQuestions(value.questions)
        && Array.isArray(value.services) && value.services.every((service) => typeof service === 'string');
}
export function parseCatalog(value) {
    if (!isObject(value) || value.schemaVersion !== 2 || typeof value.source !== 'string'
        || typeof value.retrievedAt !== 'string' || !Number.isFinite(Date.parse(value.retrievedAt))
        || !Array.isArray(value.records) || !value.records.every(isRetirementRecord)) {
        throw new Error('Invalid retirement catalog');
    }
    if (!value.records.length)
        throw new Error('Empty retirement catalog');
    return { schemaVersion: 2, source: value.source, retrievedAt: value.retrievedAt, records: value.records };
}
