import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchRetirements, normalize, readAnnouncement, titleDate } from '../scripts/feed.mjs';

const item = {
  id: 'stable-id-2025', title: 'Retirement: API keys end on 31 March 2027',
  description: '<p>Move to <a href="https://learn.microsoft.com/azure/">Entra ID</a>.</p>',
  products: ['Monitor'], tags: ['Retirements'], created: '2026-11-01T10:00:00Z',
  modified: '2026-11-05T08:30:45.1234567Z',
  availabilities: [{ ring: 'Retirement', year: 2027, month: 'March' }],
};

test('exact dates come from current titles, never URL IDs or publication dates', () => {
  const record = normalize(item);
  assert.equal(record.questions.deadline.date, '2027-03-31');
  assert.equal(record.questions.deadline.month, 'March 2027');
  assert.equal(record.announcedOn, '2026-11-01');
  assert.equal(record.lastUpdatedOn, '2026-11-05');
  assert.equal(record.sourceUrl, 'https://azure.microsoft.com/updates?id=stable-id-2025');
});

test('last updated dates come from the source modified timestamp, not publication or refresh dates', () => {
  assert.equal(normalize({ ...item, modified: undefined }).lastUpdatedOn, null);
  assert.equal(normalize({ ...item, modified: null }).lastUpdatedOn, null);
  assert.equal(normalize({ ...item, modified: '2026-11-05T23:30:00-02:00' }).lastUpdatedOn, '2026-11-06');
  for (const modified of ['', 'invalid', '2026-11-05', '2026-02-30T00:00:00Z', 42]) {
    assert.throws(() => normalize({ ...item, modified }), /Invalid announcement modified timestamp/);
  }
});

test('ambiguous, month-only, invalid and multiple deadlines remain unknown', () => {
  for (const title of ['Retires March 2027', 'Retires 31 February 2027', 'Retires 2027-99-99', 'Retires 1 May 2027 and 2 June 2027']) {
    assert.equal(titleDate(title), null, title);
  }
  assert.equal(titleDate('Retires November 10, 2026'), '2026-11-10');
  assert.equal(titleDate('Retires 10th November 2026'), '2026-11-10');
  assert.equal(titleDate('Retires 2028-02-29'), '2028-02-29');
});

test('ISO-shaped API versions never become deadlines or hide explicit retirement dates', () => {
  for (const title of [
    'Retirement: Azure Container Apps preview API versions 2023-04-01-preview',
    'Azure Digital Twins Control-Plane Preview API Retirement (2020-03-31)',
    'Pod Security Policy is being deprecated with AKS 1.25 and 2023-06-01 API version',
    'We’re ending support for the 2017-03-01-GA API.',
  ]) assert.equal(titleDate(title), null, title);
  assert.equal(titleDate('Retirement: Azure Maps Data Registry APIs V 2023-06-01 will be retired on September 30th, 2025.'), '2025-09-30');
  assert.equal(titleDate('Migrate to Azure Resource Manager control plane API version 2021-11-01 by 30 September 2026'), '2026-09-30');
  assert.equal(titleDate('API version 2023-04-01-preview retires on 2027-03-31'), '2027-03-31');
});

test('announcement HTML is converted to text; entities and paragraph boundaries survive', () => {
  const result = readAnnouncement('<p>A &amp; B&nbsp;C</p><p>Next<br>line</p><script>evil()</script><a href="javascript:evil()">bad</a><a href="/updates/">Good</a>');
  assert.equal(result.details, 'A & B C\nNext\nline\nbadGood');
  assert.deepEqual(result.links, [{ title: 'Good', url: 'https://azure.microsoft.com/updates/' }]);
  assert.equal(normalize(item).questions.what.announcement, 'Move to Entra ID.');
  assert.equal(readAnnouncement('<p>A long\nline with <strong>formatted\ntext</strong>.</p>').details, 'A long line with formatted text.');
});

test('explicit action sections are retained as source guidance without inventing steps', () => {
  const description = '<p>What changes.</p><h3>Recommended action</h3><p>Migrate to the new API.</p><h3>Help and support</h3><p>Contact us.</p>';
  assert.equal(normalize({ ...item, description }).questions.actions.recommendedAction, 'Migrate to the new API.');
  assert.equal(normalize(item).questions.actions.recommendedAction, null);
});

test('normalized records organize source content and planning guidance under all five questions', () => {
  const record = normalize(item);
  assert.deepEqual(Object.keys(record.questions), ['what', 'actions', 'impact', 'deadline', 'progress']);
  assert.deepEqual(Object.values(record.questions).map(answer => answer.question), [
    'What is changing?',
    'What do I need to do?',
    'Where, and how much, am I impacted?',
    'What is the deadline?',
    'How can I track progress?',
  ]);
  assert.deepEqual(record.questions.actions.resources, [{ title: 'Entra ID', url: 'https://learn.microsoft.com/azure/' }]);
  assert.ok(record.questions.impact.guidance.includes('Monitor'));
  assert.ok(record.questions.impact.notice.includes('cannot determine whether your resources are affected'));
  assert.equal(record.questions.progress.checklist.length, 4);
  for (const key of ['details', 'actions', 'links', 'retirementDate', 'retirementMonth']) {
    assert.equal(Object.hasOwn(record, key), false, key);
  }
});

test('question answers retain unknown dates and month-only deadline guidance', () => {
  const record = normalize({ ...item, title: 'Retirement: API keys' });
  assert.equal(record.questions.deadline.date, null);
  assert.equal(record.questions.deadline.month, 'March 2027');
  assert.match(record.questions.deadline.dateGuidance, /unambiguous exact date could not be extracted/);
  assert.match(record.questions.deadline.dateGuidance, /March 2027/);
});

test('fetch follows count and explicit offsets even without nextLink', async () => {
  const offsets = [];
  const result = await fetchRetirements(async url => {
    const skip = Number(new URL(url).searchParams.get('$skip'));
    offsets.push(skip);
    return { ok: true, json: async () => ({ '@odata.count': 3, value: skip === 0 ? [item, { ...item, id: 'two' }] : [{ ...item, id: 'three' }] }) };
  });
  assert.deepEqual(offsets, [0, 2]);
  assert.equal(result.length, 3);
});

test('an incomplete, duplicate, malformed, or changing feed cannot replace the snapshot', async () => {
  await assert.rejects(fetchRetirements(async () => ({ ok: true, json: async () => ({ '@odata.count': 1, value: [] }) })), /ended/);
  await assert.rejects(fetchRetirements(async () => ({ ok: true, json: async () => ({ '@odata.count': 2, value: [item, item] }) })), /duplicates/);
  await assert.rejects(fetchRetirements(async () => ({ ok: true, json: async () => ({ value: [item] }) })), /schema/);
  let page = 0;
  await assert.rejects(fetchRetirements(async () => ({ ok: true, json: async () => ({ '@odata.count': ++page === 1 ? 2 : 3, value: [item] }) })), /count changed/);
});

test('missing source products use an explicit platform fallback', () => {
  assert.deepEqual(normalize({ ...item, products: [] }).services, ['Azure platform']);
  assert.throws(() => normalize({ ...item, tags: [] }), /Invalid/);
});

test('official service categories are trimmed and deduplicated without inferring categories from products', () => {
  assert.deepEqual(normalize({ ...item, productCategories: ['Analytics', ' Internet of Things ', 'Analytics', '', null] }).categories, ['Analytics', 'Internet of Things']);
  for (const productCategories of [undefined, null, [], ['', ' ', null]]) {
    assert.deepEqual(normalize({ ...item, productCategories }).categories, ['Uncategorized']);
  }
});
