import test from 'node:test';
import assert from 'node:assert/strict';
import { escapeHtml, filterRecords, formatDate, safeUrl, statusOf } from '../src/catalog.js';

const records = [
  { id: 'a', title: 'Retire compute', service: 'Compute', services: ['Compute'], summary: 'Migrate VMs', details: 'Use new sizes', retirementDate: '2026-11-10', announcedOn: '2026-09-01' },
  { id: 'b', title: 'Retire network', service: 'Network · Compute', services: ['Network', 'Compute'], summary: 'Upgrade', details: '', retirementDate: '2027-02-08', announcedOn: '2026-10-01' },
  { id: 'c', title: 'Older storage', service: 'Storage', services: ['Storage'], summary: '', details: '', retirementDate: '2026-11-09', announcedOn: '2026-08-01' },
  { id: 'd', title: 'Unknown date', service: 'Storage', services: ['Storage'], summary: '', details: '', retirementDate: null, announcedOn: null },
];
const today = '2026-11-10';

test('deadline today and day 90 are urgent; day 91 is upcoming; unknown dates are not invented', () => {
  assert.equal(statusOf(records[0], today), 'soon');
  assert.equal(statusOf(records[1], today), 'soon');
  assert.equal(statusOf({ retirementDate: '2027-02-09' }, today), 'upcoming');
  assert.equal(statusOf(records[2], today), 'retired');
  assert.equal(statusOf(records[3], today), 'unknown');
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
