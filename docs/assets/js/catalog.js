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
export function customerLeadTime(announcedOn, retirementDate) {
    if (announcedOn === null || retirementDate === null)
        return 'Not calculable';
    let start = new Date(`${announcedOn}T00:00:00Z`);
    let end = new Date(`${retirementDate}T00:00:00Z`);
    const negative = end < start;
    if (negative)
        [start, end] = [end, start];
    let months = (end.getUTCFullYear() - start.getUTCFullYear()) * 12
        + end.getUTCMonth() - start.getUTCMonth();
    const addMonths = (value, count) => {
        const month = value.getUTCMonth() + count;
        const year = value.getUTCFullYear();
        const lastDay = new Date(Date.UTC(year, month + 1, 0)).getUTCDate();
        return new Date(Date.UTC(year, month, Math.min(value.getUTCDate(), lastDay)));
    };
    let anchor = addMonths(start, months);
    if (anchor > end) {
        months--;
        anchor = addMonths(start, months);
    }
    const days = Math.round((end - anchor) / 86400000);
    const years = Math.floor(months / 12);
    months %= 12;
    const parts = [[years, 'year'], [months, 'month'], [days, 'day']]
        .filter(([value]) => value)
        .map(([value, unit]) => `${value} ${unit}${value === 1 ? '' : 's'}`);
    const duration = parts.join(', ') || '0 days';
    return negative ? `-${duration}` : duration;
}
export const RETIREMENT_WINDOWS = ['retired-year', '6', '12', '18'];
export function announcedYears(today = new Date().toISOString().slice(0, 10)) {
    const currentYear = Number(today.slice(0, 4));
    return Array.from({ length: 4 }, (_, offset) => String(currentYear - offset));
}
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
const TITLE_SLUG_MAX_LENGTH = 80;
const DETAIL_SLUG_MAX_LENGTH = 130;
export function titleSlug(title) {
    let slug = title.normalize('NFKD').replace(/\p{M}/gu, '').toLowerCase()
        .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, TITLE_SLUG_MAX_LENGTH).replace(/-+$/, '') || 'retirement';
    if (/^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])$/.test(slug))
        slug = `retirement-${slug}`;
    return slug;
}
function identifierSlug(identifier) {
    return [...new TextEncoder().encode(identifier)].map(byte =>
        (byte >= 97 && byte <= 122) || (byte >= 48 && byte <= 57) || byte === 45
            ? String.fromCharCode(byte) : `_${byte.toString(16).padStart(2, '0')}`).join('');
}
export function recordUrl(record, duplicateSlug = false) {
    const deadline = record.questions.deadline.date;
    if (!isCatalogDate(deadline))
        throw new Error(`Invalid retirement date for ${record.id}: ${deadline}`);
    let slug = titleSlug(record.title);
    if (duplicateSlug) {
        const suffix = identifierSlug(record.id);
        const available = DETAIL_SLUG_MAX_LENGTH - suffix.length - 2;
        if (available < 1)
            throw new Error(`Record ID is too long to disambiguate title slug: ${record.id}`);
        slug = `${slug.slice(0, available).replace(/-+$/, '')}--${suffix}`;
    }
    return `/retirements/${deadline || 'unknown-date'}/${slug}/`;
}
export function recordUrls(records) {
    const slugs = records.map(record => titleSlug(record.title));
    const counts = new Map();
    for (const slug of slugs)
        counts.set(slug, (counts.get(slug) || 0) + 1);
    const urls = new Map();
    const seen = new Set();
    records.forEach((record, index) => {
        if (urls.has(record.id))
            throw new Error(`Duplicate record ID: ${record.id}`);
        const url = recordUrl(record, counts.get(slugs[index]) > 1);
        if (seen.has(url.toLowerCase()))
            throw new Error(`Duplicate retirement route: ${url}`);
        seen.add(url.toLowerCase());
        urls.set(record.id, url);
    });
    return urls;
}
export function findDetailRecord(records, urls, encodedSegment) {
    let segment;
    try {
        segment = decodeURIComponent(encodedSegment);
    }
    catch (error) {
        if (error instanceof URIError)
            return null;
        throw error;
    }
    const separator = segment.indexOf('--');
    const suffix = separator < 0 ? null : segment.slice(separator + 2);
    const matches = records.filter(record => {
        const url = urls.get(record.id);
        if (!url)
            throw new Error(`Missing retirement route: ${record.id}`);
        const slug = url.slice(0, -1).split('/').pop();
        return record.id === segment || slug === segment
            || (suffix !== null && identifierSlug(record.id) === suffix);
    });
    return matches.length === 1 ? matches[0] : null;
}
export function filterRecords(records, filters, today = new Date().toISOString().slice(0, 10)) {
    const terms = (filters.q || '').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
    const window = filters.window ? retirementWindow(filters.window, today) : null;
    const announcedYear = announcedYears(today).includes(filters.announcedYear) ? filters.announcedYear : '';
    return records.filter(record => {
        const status = statusOf(record.questions.deadline, today);
        const text = `${record.title} ${record.service} ${record.summary} ${record.questions.what.announcement}`.toLocaleLowerCase();
        return terms.every(term => text.includes(term))
            && (!filters.service || servicesOf(record).includes(filters.service))
            && (!announcedYear || record.announcedOn?.slice(0, 4) === announcedYear)
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
function isLearnDocumentation(value) {
    if (!safeUrl(value))
        return false;
    const url = new URL(value);
    return url.hostname === 'learn.microsoft.com' && !url.username
        && !/^\/(?:[a-z]{2}-[a-z]{2}\/)?(?:answers|users|training)(?:\/|$)/i.test(url.pathname);
}
function isMicrosoftTechCommunityArticle(value) {
    if (!safeUrl(value))
        return false;
    const url = new URL(value);
    return url.hostname === 'techcommunity.microsoft.com' && !url.username
        && /^\/(?:blog\/[^/]+\/[^/]+\/\d+|t5\/[^/]+\/[^/]+\/ba-p\/\d+)\/?$/i.test(url.pathname);
}
function isAuthoritativeRetirementUrl(value) {
    return isLearnDocumentation(value) || isMicrosoftTechCommunityArticle(value);
}
function isAzureUpdatesAnnouncement(value, record) {
    const matches = candidate => {
        if (typeof candidate !== 'string' || /[\x00-\x20\x7f]/.test(candidate)
            || !/^https:\/\/azure\.microsoft\.com(?::443)?\/(?:[a-z]{2}-[a-z]{2}\/)?updates\/?(?:[?#]|$)/i.test(candidate)
            || !safeUrl(candidate))
            return false;
        const ids = new URL(candidate).searchParams.getAll('id');
        return ids.length === 1 && ids[0] === record.id;
    };
    return matches(value) && matches(record.sourceUrl);
}
function isSourceReview(record) {
    const tracking = record.questions.progress.tracking;
    if (record.sourceReview === undefined)
        return tracking === undefined || tracking === null;
    const review = record.sourceReview;
    const sections = ['what', 'actions', 'impact', 'deadline', 'progress'];
    if (!isObject(review)
        || !['enriched', 'needs-review'].includes(review.status)
        || review.reviewedOn === null || !isCatalogDate(review.reviewedOn)
        || typeof review.originalAnnouncement !== 'string' || !review.originalAnnouncement.trim()
        || !Array.isArray(review.issues) || !review.issues.every(issue => typeof issue === 'string' && issue.trim())
        || (review.status === 'needs-review' && !review.issues.length)
        || !isObject(review.originalDeadline) || !isCatalogDate(review.originalDeadline.date)
        || !isNullableString(review.originalDeadline.month)
        || !Array.isArray(review.sources) || !review.sources.length
        || !review.sources.every(source => hasStrings(source, ['title', 'url', 'note'])
            && source.title.trim() && source.note.trim() && safeUrl(source.url)
            && isChecklist(source.sections) && source.sections.every(section => sections.includes(section))))
        return false;
    if (!sections.every(section => review.sources.some(source => source.sections.includes(section)))
        || (review.status === 'enriched' && !review.sources.some(source =>
            isAuthoritativeRetirementUrl(source.url) || isAzureUpdatesAnnouncement(source.url, record))))
        return false;
    if (tracking !== undefined && tracking !== null
        && (!hasStrings(tracking, ['guidance', 'sourceUrl']) || Object.keys(tracking).length !== 2
            || !tracking.guidance.trim() || !isAuthoritativeRetirementUrl(tracking.sourceUrl)
            || !review.sources.some(source => source.url === tracking.sourceUrl && source.sections.includes('progress'))))
        return false;
    if (review.guidanceSource !== undefined && review.guidanceSource !== null
        && (!isLearnDocumentation(review.guidanceSource)
            || !review.sources.some(source => source.url === review.guidanceSource && source.sections.includes('actions'))))
        return false;
    if (review.deadlineSource !== null
        && (!(isAuthoritativeRetirementUrl(review.deadlineSource) || isAzureUpdatesAnnouncement(review.deadlineSource, record))
        || !review.sources.some(source => source.url === review.deadlineSource && source.sections.includes('deadline'))))
        return false;
    if (record.questions.deadline.date !== null && record.questions.deadline.date !== review.originalDeadline.date
        && review.deadlineSource === null)
        return false;
    const resources = new Set(record.questions.actions.resources.map(resource => resource.url));
    if (!Array.isArray(review.resourceChecks) || review.resourceChecks.length !== resources.size)
        return false;
    const checked = new Set();
    if (!review.resourceChecks.every(check => {
        if (!hasStrings(check, ['url', 'detail']) || !check.detail.trim()
            || !['read', 'partial', 'unavailable', 'not-evidence'].includes(check.status)
            || (check.resolvedUrl !== null && !safeUrl(check.resolvedUrl))
            || (check.status === 'read' && check.resolvedUrl === null)
            || !resources.has(check.url) || checked.has(check.url))
            return false;
        checked.add(check.url);
        return true;
    }))
        return false;
    const exclusions = review.excludedReferences ?? [];
    if (!Array.isArray(exclusions))
        return false;
    const eligible = new Set([...resources, ...review.sources.map(source => source.url),
        ...review.resourceChecks.map(check => check.resolvedUrl).filter(url => url !== null)]);
    const excluded = new Set();
    return exclusions.every(item => {
        if (!isObject(item) || Object.keys(item).length !== 3 || typeof item.url !== 'string'
            || !eligible.has(item.url) || excluded.has(item.url) || typeof item.checkedOn !== 'string'
            || !isCatalogDate(item.checkedOn) || ![404, 410].includes(item.httpStatus))
            return false;
        excluded.add(item.url);
        return true;
    });
}
function isRetirementRecord(value) {
    return isObject(value)
        && typeof value.id === 'string' && typeof value.title === 'string'
        && typeof value.service === 'string' && typeof value.summary === 'string'
        && typeof value.sourceUrl === 'string' && isCatalogDate(value.announcedOn) && isCatalogDate(value.lastUpdatedOn)
        && typeof value.manuallyEnriched === 'boolean'
        && (value.hidden === undefined || typeof value.hidden === 'boolean')
        && (value.categories === undefined || (Array.isArray(value.categories) && value.categories.length > 0
            && value.categories.every((category) => typeof category === 'string' && category.trim().length > 0)))
        && isQuestions(value.questions)
        && isSourceReview(value)
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
