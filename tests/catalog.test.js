import test from 'node:test';
import assert from 'node:assert/strict';
import { daysUntilRetirement, escapeHtml, filterRecords, formatDate, safeUrl, statusOf } from '../src/catalog.ts';

const records = [
  { id: 'a', title: 'Retire compute', service: 'Compute', services: ['Compute'], summary: 'Migrate VMs', questions: { what: { announcement: 'Use new sizes' }, deadline: { date: '2026-11-10' } }, announcedOn: '2026-09-01' },
  { id: 'b', title: 'Retire network', service: 'Network · Compute', services: ['Network', 'Compute'], summary: 'Upgrade', questions: { what: { announcement: '' }, deadline: { date: '2027-02-08' } }, announcedOn: '2026-10-01' },
  { id: 'c', title: 'Older storage', service: 'Storage', services: ['Storage'], summary: '', questions: { what: { announcement: '' }, deadline: { date: '2026-11-09' } }, announcedOn: '2026-08-01' },
  { id: 'd', title: 'Unknown date', service: 'Storage', services: ['Storage'], summary: '', questions: { what: { announcement: '' }, deadline: { date: null } }, announcedOn: null },
];
const today = '2026-11-10';

test('retirement countdowns use whole UTC calendar days and preserve unknown deadlines', () => {
  assert.equal(daysUntilRetirement({ date: '2026-11-10' }, today), 0);
  assert.equal(daysUntilRetirement({ date: '2026-11-11' }, today), 1);
  assert.equal(daysUntilRetirement({ date: '2027-02-08' }, today), 90);
  assert.equal(daysUntilRetirement({ date: '2026-11-09' }, today), -1);
  assert.equal(daysUntilRetirement({ date: null, month: 'November 2026' }, today), null);
  assert.equal(daysUntilRetirement({ date: '2028-03-01' }, '2028-02-28'), 2);
  assert.equal(daysUntilRetirement({ date: '2027-03-15' }, '2027-03-13'), 2);
  assert.equal(daysUntilRetirement({ date: '2026-11-02' }, '2026-10-31'), 2);
  assert.equal(daysUntilRetirement({ date: today }), daysUntilRetirement({ date: today }, new Date().toISOString().slice(0, 10)));
});

test('deadline today and day 90 are urgent; day 91 is upcoming; unknown dates are not invented', () => {
  assert.equal(statusOf(records[0].questions.deadline, today), 'soon');
  assert.equal(statusOf(records[1].questions.deadline, today), 'soon');
  assert.equal(statusOf({ date: '2027-02-09' }, today), 'upcoming');
  assert.equal(statusOf(records[2].questions.deadline, today), 'retired');
  assert.equal(statusOf(records[3].questions.deadline, today), 'unknown');
});

test('search combines case-insensitive terms with multi-product service and status filters', () => {
  assert.deepEqual(filterRecords(records, { q: 'NEW compute', service: 'Compute', status: 'upcoming' }, today).map(record => record.id), ['a']);
  assert.equal(filterRecords(records, { service: 'Compute' }, today).length, 2);
  assert.equal(filterRecords(records, { q: 'nothing' }, today).length, 0);
  assert.equal(filterRecords(records, { status: 'unknown' }, today)[0].id, 'd');
});

test('date sorting places missing dates last; sorting does not mutate the source', () => {
  assert.deepEqual(filterRecords(records, { sort: 'date' }, today).map(record => record.id), ['c', 'a', 'b', 'd']);
  assert.equal(filterRecords(records, { sort: 'newest' }, today)[0].id, 'b');
  assert.equal(filterRecords(records, { sort: 'title' }, today)[0].id, 'c');
  assert.equal(records[0].id, 'a');
});

test('format dates in UTC and label unknown values explicitly', () => {
  assert.equal(formatDate('2026-11-10'), '10 Nov 2026');
  assert.equal(formatDate(null), 'Date not specified');
});

test('source strings are escaped and executable URLs are rejected', () => {
  assert.equal(escapeHtml('<img src=x onerror="evil()"> & \''), '&lt;img src=x onerror=&quot;evil()&quot;&gt; &amp; &#39;');
  assert.equal(safeUrl('javascript:alert(1)'), null);
  assert.equal(safeUrl('data:text/html,test'), null);
  assert.equal(safeUrl('http://example.com'), null);
  assert.equal(safeUrl('https://learn.microsoft.com/azure/'), 'https://learn.microsoft.com/azure/');
});
