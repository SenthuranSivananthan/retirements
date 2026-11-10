import test from 'node:test';
import assert from 'node:assert/strict';
import { parseCatalog } from '../src/catalog.ts';
import { normalize } from '../scripts/feed.mjs';

function catalog() {
  return {
    schemaVersion: 2,
    source: 'https://www.microsoft.com/releasecommunications/api/v2/azure',
    retrievedAt: '2026-11-10T00:00:00Z',
    records: [normalize({
      id: 'a', title: 'Retire compute', products: ['Compute'], tags: ['Retirements'],
      description: '<p>Use new sizes.</p><a href="https://learn.microsoft.com/azure/">Migration guidance</a>',
    })],
  };
}

test('catalog parsing preserves records and nullable source fields', () => {
  const value = catalog();
  assert.deepEqual(parseCatalog(value), value);
});

test('catalog parsing rejects malformed metadata and empty catalogs', () => {
  for (const value of [null, [], {}, { ...catalog(), schemaVersion: 1 }, { ...catalog(), retrievedAt: 'invalid' }, { ...catalog(), source: null }]) {
    assert.throws(() => parseCatalog(value), /Invalid retirement catalog/);
  }
  assert.throws(() => parseCatalog({ ...catalog(), records: [] }), /Empty retirement catalog/);
});

test('catalog parsing rejects malformed record fields before rendering', () => {
  for (const change of [
    { id: 1 }, { title: null }, { services: [42] }, { services: null },
    { announcedOn: undefined }, { announcedOn: '2026-13-01' },
    { lastUpdatedOn: undefined }, { lastUpdatedOn: 'invalid' }, { lastUpdatedOn: '2026-02-30' },
    { manuallyEnriched: undefined }, { manuallyEnriched: 'true' },
    { summary: null }, { sourceUrl: null }, { questions: null }, { questions: [] },
  ]) {
    const value = catalog();
    Object.assign(value.records[0], change);
    assert.throws(() => parseCatalog(value), /Invalid retirement catalog/);
  }
});

test('category metadata is validated when present and optional for older protected records', () => {
  for (const categories of [null, [], [''], [' '], [42], 'Compute']) {
    const value = catalog();
    value.records[0].categories = categories;
    assert.throws(() => parseCatalog(value), /Invalid retirement catalog/);
  }
  const value = catalog();
  value.records[0].manuallyEnriched = true;
  delete value.records[0].categories;
  assert.deepEqual(parseCatalog(value).records[0], value.records[0]);
});

test('catalog parsing requires all five question sections and their answers', () => {
  for (const section of ['what', 'actions', 'impact', 'deadline', 'progress']) {
    for (const invalid of ['missing', 'question', 'introduction']) {
      const value = catalog();
      const questions = value.records[0].questions;
      if (invalid === 'missing') delete questions[section];
      else questions[section][invalid] = null;
      assert.throws(() => parseCatalog(value), /Invalid retirement catalog/, `${section}: ${invalid}`);
    }
  }
  const extra = catalog();
  extra.records[0].questions.extra = { question: 'Unexpected question' };
  assert.throws(() => parseCatalog(extra), /Invalid retirement catalog/);
});

test('catalog parsing rejects malformed answer details, dates, resources, and checklist steps', () => {
  const cases = [
    ['what', 'announcement', null],
    ['what', 'financialConsiderations', false],
    ['actions', 'recommendedAction', []],
    ['actions', 'resources', null],
    ['actions', 'resources', [null]],
    ['actions', 'resources', [{ title: 'Guide', url: 42 }]],
    ['actions', 'support', {}],
    ['actions', 'supportGuidance', null],
    ['impact', 'guidance', null],
    ['impact', 'notice', null],
    ['impact', 'advisor', null],
    ['impact', 'checklist', [42]],
    ['deadline', 'date', false],
    ['deadline', 'date', 'invalid'],
    ['deadline', 'date', '2026-02-30'],
    ['deadline', 'month', 2027],
    ['deadline', 'consequences', null],
    ['progress', 'checklist', []],
    ['progress', 'checklist', [false]],
    ['progress', 'storageNote', null],
  ];
  for (const [section, field, invalid] of cases) {
    const value = catalog();
    value.records[0].questions[section][field] = invalid;
    assert.throws(() => parseCatalog(value), /Invalid retirement catalog/, `${section}.${field}`);
  }
});
