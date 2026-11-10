import type { CatalogFilters, DeadlineQuestion, RetirementCatalog, RetirementQuestions, RetirementRecord, RetirementStatus } from './types.js';

export function daysUntilRetirement(deadline: Pick<DeadlineQuestion, 'date'>, today = new Date().toISOString().slice(0, 10)): number | null {
  return deadline.date === null ? null : Math.round((Date.parse(deadline.date) - Date.parse(today)) / 86400000);
}

export function statusOf(deadline: Pick<DeadlineQuestion, 'date'>, today?: string): RetirementStatus {
  const days = daysUntilRetirement(deadline, today);
  if (days === null) return 'unknown';
  if (days < 0) return 'retired';
  return days <= 90 ? 'soon' : 'upcoming';
}

export function retirementCountdown(deadline: Pick<DeadlineQuestion, 'date'>, today?: string): string {
  const days = daysUntilRetirement(deadline, today);
  return days === null ? 'Retirement date to confirm'
    : days < 0 ? 'Retired'
      : days === 0 ? 'Retires today (0 days remaining)'
        : `${days} ${days === 1 ? 'day' : 'days'} remaining`;
}

export function retirementYear(record: Pick<RetirementRecord, 'questions'>): string {
  const { date, month } = record.questions.deadline;
  if (date) return date.slice(0, 4);
  return month?.match(/^(?:January|February|March|April|May|June|July|August|September|October|November|December) (\d{4})$/)?.[1] || 'unknown';
}

export function categoriesOf(record: Pick<RetirementRecord, 'categories'>): string[] {
  return record.categories?.length ? [...new Set(record.categories)] : ['Uncategorized'];
}

export function groupRetirements(records: readonly RetirementRecord[]) {
  const years = new Map<string, RetirementRecord[]>();
  for (const record of records) {
    const year = retirementYear(record);
    const group = years.get(year);
    if (group) group.push(record);
    else years.set(year, [record]);
  }
  return [...years].sort(([a], [b]) => a === 'unknown' ? 1 : b === 'unknown' ? -1 : b.localeCompare(a))
    .map(([year, yearRecords]) => {
      const sorted = [...yearRecords].sort((a, b) => a.title.localeCompare(b.title) || a.id.localeCompare(b.id));
      const categories = new Map<string, RetirementRecord[]>();
      for (const record of sorted) {
        for (const category of categoriesOf(record)) {
          const group = categories.get(category);
          if (group) group.push(record);
          else categories.set(category, [record]);
        }
      }
      return {
        year,
        records: sorted,
        categories: [...categories].sort(([a], [b]) => a.localeCompare(b)).map(([name, records]) => ({ name, records })),
      };
    });
}

export function directoryUrl(filters: Partial<CatalogFilters>, base = '/'): string {
  const query = new URLSearchParams(Object.entries(filters).filter(([, value]) => value));
  return query.size ? `${base}?${query}` : base;
}

export function filterRecords<T extends Pick<RetirementRecord, 'title' | 'service' | 'services' | 'categories' | 'summary' | 'questions' | 'announcedOn'>>(
  records: readonly T[], filters: Partial<CatalogFilters>, today?: string,
): T[] {
  const terms = (filters.q || '').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return records.filter(record => {
    const status = statusOf(record.questions.deadline, today);
    const text = `${record.title} ${record.service} ${record.summary} ${record.questions.what.announcement}`.toLocaleLowerCase();
    return terms.every(term => text.includes(term))
      && (!filters.service || record.services.includes(filters.service))
      && (!filters.year || retirementYear(record) === filters.year)
      && (!filters.category || categoriesOf(record).includes(filters.category))
      && (!filters.status || filters.status === 'all' || status === filters.status
        || (filters.status === 'upcoming' && status === 'soon'));
  }).sort((a, b) => {
    if (filters.sort === 'title') return a.title.localeCompare(b.title);
    if (filters.sort === 'newest') return (b.announcedOn || '').localeCompare(a.announcedOn || '') || a.title.localeCompare(b.title);
    return (a.questions.deadline.date || '9999').localeCompare(b.questions.deadline.date || '9999') || a.title.localeCompare(b.title);
  });
}

export function formatDate(date: string | null) {
  return date ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${date}T00:00:00Z`)) : 'Date not specified';
}

export function escapeHtml(value: unknown = '') {
  const entities: Record<string, string> = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
  return String(value).replace(/[&<>"']/g, char => entities[char]);
}

export function safeUrl(value: string) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isNullableString(value: unknown): value is string | null {
  return value === null || typeof value === 'string';
}

function isCatalogDate(value: unknown): value is string | null {
  if (value === null) return true;
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
  const parsed = new Date(`${value}T00:00:00Z`);
  return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
}

function hasStrings<K extends string>(value: unknown, keys: readonly K[]): value is Record<K, string> & Record<string, unknown> {
  return isObject(value) && keys.every(key => typeof value[key] === 'string');
}

function isLink(value: unknown): boolean {
  return hasStrings(value, ['title', 'url']);
}

function isChecklist(value: unknown): boolean {
  return Array.isArray(value) && value.length > 0 && value.every((step: unknown) => typeof step === 'string');
}

function isQuestions(value: unknown): value is RetirementQuestions {
  if (!isObject(value) || Object.keys(value).length !== 5) return false;
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

function isRetirementRecord(value: unknown): value is RetirementRecord {
  return isObject(value)
    && typeof value.id === 'string' && typeof value.title === 'string'
    && typeof value.service === 'string' && typeof value.summary === 'string'
    && typeof value.sourceUrl === 'string' && isCatalogDate(value.announcedOn) && isCatalogDate(value.lastUpdatedOn)
    && typeof value.manuallyEnriched === 'boolean'
    && (value.categories === undefined || (Array.isArray(value.categories) && value.categories.length > 0
      && value.categories.every((category: unknown) => typeof category === 'string' && category.trim().length > 0)))
    && isQuestions(value.questions)
    && Array.isArray(value.services) && value.services.every((service: unknown) => typeof service === 'string');
}

export function parseCatalog(value: unknown): RetirementCatalog {
  if (!isObject(value) || value.schemaVersion !== 2 || typeof value.source !== 'string'
    || typeof value.retrievedAt !== 'string' || !Number.isFinite(Date.parse(value.retrievedAt))
    || !Array.isArray(value.records) || !value.records.every(isRetirementRecord)) {
    throw new Error('Invalid retirement catalog');
  }
  if (!value.records.length) throw new Error('Empty retirement catalog');
  return { schemaVersion: 2, source: value.source, retrievedAt: value.retrievedAt, records: value.records };
}
