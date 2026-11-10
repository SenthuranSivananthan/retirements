import { parseFragment } from 'parse5';

export const endpoint = 'https://www.microsoft.com/releasecommunications/api/v2/azure';
const months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
const monthPattern = months.join('|');

export function readAnnouncement(html) {
  const links = [];
  function text(node) {
    if (['script', 'style', 'iframe'].includes(node.tagName)) return '';
    if (node.nodeName === '#text') return node.value.replace(/\s+/g, ' ');
    const content = (node.childNodes || []).map(text).join('');
    if (node.tagName === 'a') {
      const href = node.attrs.find(attr => attr.name === 'href')?.value;
      try {
        const url = new URL(href, 'https://azure.microsoft.com');
        if (url.protocol === 'https:') links.push({ title: content.trim(), url: url.href });
      } catch { /* Ignore malformed source links. */ }
    }
    return ['p', 'div', 'li', 'br', 'h1', 'h2', 'h3', 'h4', 'tr'].includes(node.tagName) ? `${content}\n` : content;
  }
  const details = text(parseFragment(html)).replace(/[ \t\u00a0]+/g, ' ').replace(/ *\n */g, '\n').replace(/\n{3,}/g, '\n\n').trim();
  return { details, links: [...new Map(links.map(link => [link.url, link])).values()] };
}

export function titleDate(title) {
  const dates = [];
  const add = (year, month, day) => {
    const iso = `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    const parsed = new Date(`${iso}T00:00:00Z`);
    if (Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === iso) dates.push(iso);
  };
  for (const match of title.matchAll(new RegExp(`\\b(${monthPattern})\\s+(\\d{1,2})(?:st|nd|rd|th)?[,]?\\s+(20\\d{2})\\b`, 'gi'))) {
    add(match[3], months.findIndex(month => month.toLowerCase() === match[1].toLowerCase()) + 1, match[2]);
  }
  for (const match of title.matchAll(new RegExp(`\\b(\\d{1,2})(?:st|nd|rd|th)?\\s+(${monthPattern})[,]?\\s+(20\\d{2})\\b`, 'gi'))) {
    add(match[3], months.findIndex(month => month.toLowerCase() === match[2].toLowerCase()) + 1, match[1]);
  }
  for (const match of title.matchAll(/\b(20\d{2})-(\d{2})-(\d{2})\b/g)) {
    const before = title.slice(0, match.index);
    const after = title.slice(match.index + match[0].length);
    const deadlineContext = /\b(?:on|by|after|from|retire[sd]?|retiring|ends?|ending|deadline(?:\s+is)?)\s*[:(]?\s*$/i.test(before);
    if (deadlineContext && !/^-(?:preview|ga)\b/i.test(after)) add(match[1], match[2], match[3]);
  }
  const unique = [...new Set(dates)];
  return unique.length === 1 ? unique[0] : null;
}

export function normalize(item) {
  if (!item.id || typeof item.title !== 'string' || typeof item.description !== 'string'
    || !Array.isArray(item.tags) || !item.tags.includes('Retirements')) {
    throw new Error('Invalid retirement announcement');
  }
  const { details, links } = readAnnouncement(item.description);
  const actionMatch = details.match(/(?:^|\n)(?:recommended actions?|required actions?|action required|what you need to do)[: ]*\n([\s\S]*?)(?=\n(?:help and support|more information|learn more)[: ]*(?:\n|$)|$)/i);
  const services = Array.isArray(item.products) ? item.products.filter(value => typeof value === 'string' && value.trim()) : [];
  if (!services.length) services.push('Azure platform');
  const availability = item.availabilities?.find(value => value.ring === 'Retirement');
  const retirementMonth = availability && Number.isInteger(availability.year) && months.includes(availability.month)
    ? `${availability.month} ${availability.year}` : null;
  const announcedOn = typeof item.created === 'string' && /^\d{4}-\d{2}-\d{2}T/.test(item.created) ? item.created.slice(0, 10) : null;
  return {
    id: String(item.id),
    title: item.title.trim(),
    services,
    service: services.join(' · '),
    retirementDate: titleDate(item.title),
    retirementMonth,
    announcedOn,
    summary: details.length > 240 ? `${details.slice(0, 237).replace(/\s+\S*$/, '')}…` : details,
    details,
    actions: actionMatch?.[1].trim() || null,
    links,
    sourceUrl: `https://azure.microsoft.com/updates?id=${encodeURIComponent(item.id)}`,
  };
}

export async function fetchRetirements(fetcher = fetch) {
  const records = new Map();
  let skip = 0;
  let expected;
  do {
    const params = new URLSearchParams({
      '$count': 'true', '$top': '100', '$skip': String(skip),
      '$filter': "tags/any(f:f eq 'Retirements')", '$orderby': 'id asc',
    });
    let response;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        response = await fetcher(`${endpoint}?${params}`, {
          headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(60000),
        });
        if (response.ok || (response.status !== 429 && response.status < 500)) break;
      } catch (error) {
        if (attempt === 2) throw error;
      }
      if (attempt < 2) await new Promise(resolve => setTimeout(resolve, 1000 * (attempt + 1)));
    }
    if (!response?.ok) throw new Error(`Azure feed request failed: ${response?.status}`);
    const data = await response.json();
    const count = data['@odata.count'];
    if (!Array.isArray(data.value) || !Number.isInteger(count) || count <= 0
      || (expected !== undefined && count !== expected)) {
      throw new Error('Azure feed schema or count changed; existing snapshot preserved');
    }
    expected = count;
    if (data.value.length === 0) throw new Error('Azure feed ended before all announcements were fetched');
    for (const item of data.value) {
      const record = normalize(item);
      records.set(record.id, record);
    }
    skip += data.value.length;
  } while (skip < expected);
  if (records.size !== expected) throw new Error('Azure feed contains duplicates or changed during pagination; retry refresh');
  return [...records.values()].sort((a, b) => a.id.localeCompare(b.id));
}
