import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';
import { endpoint, mergeRetirements, normalize } from '../scripts/feed.mjs';
import { refreshCatalog } from '../scripts/refresh-data.mjs';
import { parseCatalog } from '../site/src/catalog.ts';

const item = {
  id: 'a', title: 'Retirement: API keys end on 31 March 2027',
  description: '<p>New official guidance.</p>', products: ['Monitor'], tags: ['Retirements'],
  created: '2026-11-01T10:00:00Z', modified: '2026-11-05T08:30:00Z',
};
const fetcher = async () => ({ ok: true, json: async () => ({ '@odata.count': 1, value: [item] }) });

async function fixture(t, records) {
  const directory = await mkdtemp(join(tmpdir(), 'retirements-refresh-'));
  t.after(() => rm(directory, { recursive: true, force: true }));
  const output = pathToFileURL(join(directory, 'retirements.json'));
  if (records) {
    await writeFile(output, JSON.stringify({
      schemaVersion: 2, source: endpoint, retrievedAt: '2026-11-01T00:00:00Z', records,
    }));
  }
  return { directory, output };
}

test('refresh merges preserve complete enriched records, refresh others, and add new records', () => {
  const enriched = normalize(item);
  enriched.manuallyEnriched = true;
  enriched.questions.actions.guidance = 'Custom migration instructions.';
  enriched.customNotes = { owner: 'Platform team', steps: ['Verify regional rollout'] };
  enriched.lastUpdatedOn = '2026-11-02';
  const retained = { ...enriched, id: 'removed-from-source' };
  const previous = [enriched, retained, { ...normalize(item), id: 'b', title: 'Old title' }];
  const fresh = [normalize(item), normalize({ ...item, id: 'b' }), normalize({ ...item, id: 'c' })];
  const merged = mergeRetirements(fresh, previous);
  assert.deepEqual(merged.map(record => record.id), ['a', 'b', 'c', 'removed-from-source']);
  assert.deepEqual(merged[0], enriched);
  assert.deepEqual(merged[1], fresh[1]);
  assert.deepEqual(merged[2], fresh[2]);
  assert.deepEqual(merged[3], retained);
  assert.equal(merged[0].lastUpdatedOn, '2026-11-02');
  assert.equal(previous[2].title, 'Old title');
});

test('unflagged records absent from a complete source refresh are removed', () => {
  assert.deepEqual(mergeRetirements([normalize(item)], [normalize({ ...item, id: 'old' })]), [normalize(item)]);
});

test('invalid enrichment flags and duplicate IDs fail instead of risking custom content', () => {
  for (const manuallyEnriched of [undefined, null, 'true', 'false', 1]) {
    assert.throws(() => mergeRetirements([normalize(item)], [{ ...normalize(item), manuallyEnriched }]), /enrichment flag/);
  }
  assert.throws(() => mergeRetirements([normalize(item)], [normalize(item), normalize(item)]), /duplicate ID/);
  assert.throws(() => mergeRetirements([normalize(item)], null), /Invalid catalog records/);
  assert.equal(normalize({ ...item, manuallyEnriched: true }).manuallyEnriched, false);
});

test('the automation writer persists all questions, source update dates, and preserved enrichments', async t => {
  const enriched = normalize(item);
  enriched.manuallyEnriched = true;
  enriched.questions.impact.guidance = 'Custom impact assessment.';
  const { output, directory } = await fixture(t, [enriched]);
  const result = await refreshCatalog({ fetcher, output });
  const saved = parseCatalog(JSON.parse(await readFile(output, 'utf8')));
  assert.deepEqual(saved, result);
  assert.deepEqual(saved.records[0], enriched);
  assert.equal(saved.records[0].lastUpdatedOn, '2026-11-05');
  assert.equal(Object.keys(saved.records[0].questions).length, 5);
  assert.deepEqual(await readdir(directory), ['retirements.json']);
});

test('enrichments saved while the feed is being fetched are read before merging', async t => {
  const { output } = await fixture(t, [normalize(item)]);
  const result = await refreshCatalog({
    output,
    fetcher: async () => {
      const current = JSON.parse(await readFile(output, 'utf8'));
      current.records[0].manuallyEnriched = true;
      current.records[0].questions.actions.guidance = 'Edited during refresh.';
      await writeFile(output, JSON.stringify(current));
      return fetcher();
    },
  });
  assert.equal(result.records[0].manuallyEnriched, true);
  assert.equal(result.records[0].questions.actions.guidance, 'Edited during refresh.');
});

test('failed or incomplete source refreshes leave the existing file unchanged', async t => {
  const { output } = await fixture(t, [normalize(item)]);
  const original = await readFile(output, 'utf8');
  await assert.rejects(refreshCatalog({
    output, fetcher: async () => ({ ok: true, json: async () => ({ '@odata.count': 1, value: [] }) }),
  }), /ended/);
  assert.equal(await readFile(output, 'utf8'), original);
});

test('invalid local protection metadata leaves the existing file unchanged', async t => {
  const { output } = await fixture(t, [{ ...normalize(item), manuallyEnriched: 'true' }]);
  const original = await readFile(output, 'utf8');
  await assert.rejects(refreshCatalog({ output, fetcher }), /enrichment flag/);
  assert.equal(await readFile(output, 'utf8'), original);
  await writeFile(output, 'null');
  await assert.rejects(refreshCatalog({ output, fetcher }), /Unsupported catalog schema/);
  assert.equal(await readFile(output, 'utf8'), 'null');
});

test('a first refresh creates a catalog with protection disabled on new source records', async t => {
  const { output } = await fixture(t);
  const result = await refreshCatalog({ output, fetcher });
  assert.equal(result.records[0].manuallyEnriched, false);
  assert.equal(result.records[0].lastUpdatedOn, '2026-11-05');
  assert.deepEqual(parseCatalog(JSON.parse(await readFile(output, 'utf8'))), result);
});
