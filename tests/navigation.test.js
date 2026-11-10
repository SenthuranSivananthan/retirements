import test from 'node:test';
import assert from 'node:assert/strict';
import { categoriesOf, directoryUrl, filterRecords, groupRetirements, retirementYear, statusOf } from '../src/catalog.ts';
import { normalize } from '../scripts/feed.mjs';

function records() {
  const source = { description: '<p>Plan your migration.</p>', products: ['Monitor'], tags: ['Retirements'], created: '2026-01-01T00:00:00Z' };
  const values = [
    { id: 'a', title: 'Zulu retires on 1 January 2027', productCategories: ['Compute', 'Storage'] },
    { id: 'b', title: 'Alpha retirement', productCategories: ['Storage', 'Networking'], availabilities: [{ ring: 'Retirement', month: 'September', year: 2027 }] },
    { id: 'c', title: 'Legacy retirement' },
    { id: 'd', title: 'Earlier retires on 1 December 2025', productCategories: ['Compute'] },
    { id: 'e', title: 'Newest retires on 1 February 2028', productCategories: ['Compute'] },
  ].map(item => normalize({ ...source, ...item }));
  delete values[2].categories;
  return values;
}

test('navigation uses retirement years, including month-only timing, never publication years', () => {
  const [exact, monthOnly, unknown] = records();
  exact.questions.deadline.month = 'December 2028';
  assert.equal(retirementYear(exact), '2027');
  assert.equal(retirementYear(monthOnly), '2027');
  assert.equal(monthOnly.questions.deadline.date, null);
  assert.equal(statusOf(monthOnly.questions.deadline), 'unknown');
  assert.equal(retirementYear(unknown), 'unknown');
  unknown.questions.deadline.month = 'Unconfirmed 2029';
  assert.equal(retirementYear(unknown), 'unknown');
});

test('the navigation groups years descending, categories alphabetically, and unconfirmed years last', () => {
  const source = records();
  const before = structuredClone(source);
  const groups = groupRetirements(source);
  assert.deepEqual(groups.map(group => group.year), ['2028', '2027', '2025', 'unknown']);
  const year = groups.find(group => group.year === '2027');
  assert.deepEqual(year.records.map(record => record.id), ['b', 'a']);
  assert.deepEqual(year.categories.map(category => category.name), ['Compute', 'Networking', 'Storage']);
  assert.deepEqual(year.categories.find(category => category.name === 'Storage').records.map(record => record.id), ['b', 'a']);
  assert.equal(groups.at(-1).categories[0].name, 'Uncategorized');
  assert.deepEqual(source, before);
  assert.deepEqual(groupRetirements([]), []);
});

test('multiple categories do not duplicate records within a category or inflate year counts', () => {
  const source = records();
  source[0].categories.push('Storage');
  assert.deepEqual(categoriesOf(source[0]), ['Compute', 'Storage']);
  assert.deepEqual(categoriesOf(source[2]), ['Uncategorized']);
  const year = groupRetirements(source).find(group => group.year === '2027');
  assert.equal(year.records.length, 2);
  assert.equal(year.categories.find(category => category.name === 'Storage').records.length, 2);
});

test('year and category filters combine with search, service, status and sorting', () => {
  const source = records();
  const select = filters => filterRecords(source, filters, '2026-01-01').map(record => record.id);
  assert.deepEqual(select({ year: '2027', category: 'Storage', sort: 'title' }), ['b', 'a']);
  assert.deepEqual(select({ year: '2027', category: 'Storage', sort: 'deadline' }), ['a', 'b']);
  assert.deepEqual(select({ year: '2027', category: 'Storage', service: 'Monitor', q: 'Alpha', status: 'unknown' }), ['b']);
  assert.deepEqual(select({ year: '2027', category: 'Storage', status: 'upcoming' }), ['a']);
  assert.deepEqual(select({ year: '2027', service: 'Missing service' }), []);
  assert.deepEqual(select({ year: '2026' }), []);
  assert.deepEqual(select({ year: 'unknown', category: 'Uncategorized' }), ['c']);
  assert.deepEqual(source.map(record => record.id), ['a', 'b', 'c', 'd', 'e']);
});

test('directory URLs preserve and safely encode year, category and existing filters', () => {
  const filters = { year: 'unknown', category: 'AI & machine learning / Data + analytics', q: 'A&B', service: '', status: 'unknown', sort: 'title' };
  const url = directoryUrl(filters);
  const params = new URLSearchParams(url.split('?')[1]);
  assert.equal(params.get('year'), filters.year);
  assert.equal(params.get('category'), filters.category);
  assert.equal(params.get('q'), filters.q);
  assert.equal(params.get('status'), filters.status);
  assert.equal(params.get('sort'), filters.sort);
  assert.equal(params.has('service'), false);
  assert.equal(directoryUrl({}), '#/');
});
