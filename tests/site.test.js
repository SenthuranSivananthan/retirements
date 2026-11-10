import test from 'node:test';
import assert from 'node:assert/strict';
import { access, mkdtemp, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { normalize } from '../scripts/feed.mjs';
import { prepareSite } from '../scripts/prepare-site.mjs';
import { directoryUrl, retirementCountdown } from '../site/src/catalog.ts';

async function fixture(t) {
  const root = await mkdtemp(join(tmpdir(), 'retirements-site-'));
  t.after(() => rm(root, { recursive: true, force: true }));
  const source = { description: '<p>Source guidance.</p>', products: ['Monitor'], tags: ['Retirements'] };
  const records = [
    normalize({ ...source, id: 'future', title: 'Retires on 12 November 2026', productCategories: ['Compute', 'Storage'] }),
    normalize({ ...source, id: 'retired', title: 'Retired on 9 November 2026', productCategories: ['Compute'] }),
    normalize({ ...source, id: 'unknown', title: 'Unconfirmed retirement' }),
  ];
  records[2].manuallyEnriched = true;
  records[2].customNotes = 'Keep my curated answers.';
  delete records[2].categories;
  await mkdir(join(root, 'data'));
  const catalog = { schemaVersion: 2, source: 'https://www.microsoft.com/releasecommunications/api/v2/azure', retrievedAt: '2026-11-10T00:00:00Z', records };
  const save = () => writeFile(join(root, 'data', 'retirements.json'), `${JSON.stringify(catalog, null, 2)}\n`);
  await save();
  return { root, catalog, save };
}

test('Jekyll preparation generates one document per retirement without modifying the canonical catalog', async t => {
  const { root, catalog } = await fixture(t);
  const before = await readFile(join(root, 'data', 'retirements.json'), 'utf8');
  const site = await prepareSite({ root, today: '2026-11-10' });
  assert.equal(site.count, 3);
  assert.equal(site.byId.future.countdown, '2 days remaining');
  assert.equal(site.byId.retired.countdown, 'Retired');
  assert.equal(site.byId.unknown.countdown, 'Retirement date to confirm');
  assert.deepEqual(site.byId.unknown.record, catalog.records[2]);
  assert.deepEqual(site.byId.unknown.categories, ['Uncategorized']);
  assert.deepEqual(site.byId.future.sections.map(section => section.id), ['what', 'actions', 'impact', 'deadline', 'progress']);
  assert.equal(await readFile(join(root, 'data', 'retirements.json'), 'utf8'), before);
  assert.equal(await readFile(join(root, 'site', 'assets', 'data', 'retirements.json'), 'utf8'), before);
  for (const obsolete of ['assets', '_generated', '_site']) {
    await assert.rejects(access(join(root, obsolete)), { code: 'ENOENT' });
  }
  assert.deepEqual(await readdir(join(root, 'data')), ['retirements.json']);
  const collection = join(root, 'site', '_generated', '_retirements');
  assert.equal((await readdir(collection)).length, 3);
  const document = await readFile(join(collection, 'record-0000.html'), 'utf8');
  const frontMatter = JSON.parse(document.split('---')[1]);
  assert.equal(frontMatter.layout, 'retirement');
  assert.equal(frontMatter.record_id, 'future');
  assert.equal(frontMatter.permalink, '/retirements/future/');
});

test('preparation safely encodes document URLs and removes only stale generated files', async t => {
  const { root, catalog, save } = await fixture(t);
  catalog.records[0].id = '../custom ?&';
  await save();
  const site = await prepareSite({ root, today: '2026-11-10' });
  assert.equal(site.byId['../custom ?&'].url, '/retirements/..%2Fcustom%20%3F%26/');
  const collection = join(root, 'site', '_generated', '_retirements');
  await writeFile(join(collection, 'notes.txt'), 'Do not delete.');
  catalog.records.pop();
  await save();
  await prepareSite({ root, today: '2026-11-10' });
  assert.deepEqual((await readdir(collection)).sort(), ['notes.txt', 'record-0000.html', 'record-0001.html']);
  assert.equal(await readFile(join(collection, 'notes.txt'), 'utf8'), 'Do not delete.');
});

test('duplicate IDs fail before replacing prepared metadata', async t => {
  const { root, catalog, save } = await fixture(t);
  await prepareSite({ root });
  const before = await readFile(join(root, 'site', '_data', 'site.json'), 'utf8');
  catalog.records[1].id = catalog.records[0].id;
  await save();
  await assert.rejects(prepareSite({ root }), /duplicate retirement ID/);
  assert.equal(await readFile(join(root, 'site', '_data', 'site.json'), 'utf8'), before);
});

test('static directory URLs retain project base paths and countdown labels cover boundary cases', () => {
  assert.equal(directoryUrl({}, '/retirements/'), '/retirements/');
  assert.equal(directoryUrl({ year: '2027', category: 'AI + machine learning' }, '/retirements/'), '/retirements/?year=2027&category=AI+%2B+machine+learning');
  assert.equal(retirementCountdown({ date: '2026-11-10' }, '2026-11-10'), 'Retires today (0 days remaining)');
  assert.equal(retirementCountdown({ date: '2026-11-11' }, '2026-11-10'), '1 day remaining');
  assert.equal(retirementCountdown({ date: null }, '2026-11-10'), 'Retirement date to confirm');
});
