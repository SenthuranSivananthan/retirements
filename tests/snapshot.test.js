import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { parseCatalog, safeUrl } from '../site/src/catalog.ts';
import { titleDate } from '../scripts/feed.mjs';

test('the bundled catalog has stable unique IDs, valid provenance, and conservative dates', async () => {
  const catalog = parseCatalog(JSON.parse(await readFile(new URL('../data/retirements.json', import.meta.url), 'utf8')));
  assert.ok(catalog.records.length > 0);
  assert.equal(new Set(catalog.records.map(record => record.id)).size, catalog.records.length);
  assert.ok(Number.isFinite(Date.parse(catalog.retrievedAt)));
  for (const record of catalog.records) {
    assert.ok(record.id && record.title && record.questions.what.announcement, record.id);
    assert.ok(record.services.length > 0, record.id);
    assert.ok(Object.hasOwn(record, 'lastUpdatedOn'), record.id);
    if (!record.manuallyEnriched) {
      assert.equal(record.questions.deadline.date, titleDate(record.title), record.id);
      assert.ok(record.categories?.length > 0, record.id);
      assert.equal(new Set(record.categories).size, record.categories.length, record.id);
    }
    assert.equal(record.sourceUrl, `https://azure.microsoft.com/updates?id=${encodeURIComponent(record.id)}`);
    assert.deepEqual(Object.keys(record.questions), ['what', 'actions', 'impact', 'deadline', 'progress'], record.id);
    for (const key of ['details', 'actions', 'links', 'retirementDate', 'retirementMonth']) {
      assert.equal(Object.hasOwn(record, key), false, `${record.id}: ${key}`);
    }
    assert.deepEqual(Object.values(record.questions).map(answer => answer.question), [
      'What is changing?',
      'What do I need to do?',
      'Where, and how much, am I impacted?',
      'What is the deadline?',
      'How can I track progress?',
    ], record.id);
    for (const link of [...record.questions.actions.resources, record.questions.actions.support, record.questions.impact.advisor]) {
      assert.ok(safeUrl(link.url), record.id);
    }
  }
});
