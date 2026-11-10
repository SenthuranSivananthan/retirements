import test from 'node:test';
import assert from 'node:assert/strict';
import { fetchRetirements, normalize, readAnnouncement, titleDate } from '../scripts/feed.mjs';

const item = {
  id: 'stable-id-2025', title: 'Retirement: API keys end on 31 March 2027',
  description: '<p>Move to <a href="https://learn.microsoft.com/azure/">Entra ID</a>.</p>',
  products: ['Monitor'], tags: ['Retirements'], created: '2026-11-01T10:00:00Z',
  availabilities: [{ ring: 'Retirement', year: 2027, month: 'March' }],
};

test('exact dates come from current titles, never URL IDs or publication dates', () => {
  const record = normalize(item);
  assert.equal(record.retirementDate, '2027-03-31');
  assert.equal(record.retirementMonth, 'March 2027');
  assert.equal(record.announcedOn, '2026-11-01');
  assert.equal(record.sourceUrl, 'https://azure.microsoft.com/updates?id=stable-id-2025');
});

test('ambiguous, month-only, invalid and multiple deadlines remain unknown', () => {
  for (const title of ['Retires March 2027', 'Retires 31 February 2027', 'Retires 2027-99-99', 'Retires 1 May 2027 and 2 June 2027']) {
    assert.equal(titleDate(title), null, title);
  }
  assert.equal(titleDate('Retires November 10, 2026'), '2026-11-10');
  assert.equal(titleDate('Retires 10th November 2026'), '2026-11-10');
  assert.equal(titleDate('Retires 2028-02-29'), '2028-02-29');
});

test('announcement HTML is converted to text; entities and paragraph boundaries survive', () => {
  const result = readAnnouncement('<p>A &amp; B&nbsp;C</p><p>Next<br>line</p><script>evil()</script><a href="javascript:evil()">bad</a><a href="/updates/">Good</a>');
  assert.equal(result.details, 'A & B C\nNext\nline\nbadGood');
  assert.deepEqual(result.links, [{ title: 'Good', url: 'https://azure.microsoft.com/updates/' }]);
  assert.equal(normalize(item).details, 'Move to Entra ID.');
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
