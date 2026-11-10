export function statusOf(record, today = new Date().toISOString().slice(0, 10)) {
  if (!record.retirementDate) return 'unknown';
  if (record.retirementDate < today) return 'retired';
  const days = Math.round((Date.parse(record.retirementDate) - Date.parse(today)) / 86400000);
  return days <= 90 ? 'soon' : 'upcoming';
}

export function filterRecords(records, filters, today) {
  const terms = (filters.q || '').toLocaleLowerCase().trim().split(/\s+/).filter(Boolean);
  return records.filter(record => {
    const status = statusOf(record, today);
    const text = `${record.title} ${record.service} ${record.summary} ${record.details}`.toLocaleLowerCase();
    return terms.every(term => text.includes(term))
      && (!filters.service || record.services.includes(filters.service))
      && (!filters.status || filters.status === 'all' || status === filters.status
        || (filters.status === 'upcoming' && status === 'soon'));
  }).sort((a, b) => {
    if (filters.sort === 'title') return a.title.localeCompare(b.title);
    if (filters.sort === 'newest') return (b.announcedOn || '').localeCompare(a.announcedOn || '') || a.title.localeCompare(b.title);
    return (a.retirementDate || '9999').localeCompare(b.retirementDate || '9999') || a.title.localeCompare(b.title);
  });
}

export function formatDate(date) {
  return date ? new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone: 'UTC' })
    .format(new Date(`${date}T00:00:00Z`)) : 'Date not specified';
}

export function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
}

export function safeUrl(value) {
  try {
    const url = new URL(value);
    return url.protocol === 'https:' ? url.href : null;
  } catch {
    return null;
  }
}
