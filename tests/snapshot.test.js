import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { safeUrl } from '../src/catalog.js';
import { titleDate } from '../scripts/feed.mjs';

test('the bundled catalog has stable unique IDs, valid provenance, and conservative dates', async () => {
  const catalog = JSON.parse(await readFile(new URL('../data/retirements.json', import.meta.url), 'utf8'));
  assert.ok(catalog.records.length > 0);
  assert.equal(new Set(catalog.records.map(record => record.id)).size, catalog.records.length);
  assert.ok(Number.isFinite(Date.parse(catalog.retrievedAt)));
  for (const record of catalog.records) {
    assert.ok(record.id && record.title && record.details, record.id);
    assert.ok(record.services.length > 0, record.id);
    assert.equal(record.retirementDate, titleDate(record.title), record.id);
    assert.equal(record.sourceUrl, `https://azure.microsoft.com/updates?id=${encodeURIComponent(record.id)}`);
    for (const link of record.links) assert.ok(safeUrl(link.url), record.id);
  }
});
