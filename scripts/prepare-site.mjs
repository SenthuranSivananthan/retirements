import { copyFile, mkdir, readFile, readdir, rm, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { categoriesOf, filterRecords, formatDate, groupRetirements, parseCatalog, retirementCountdown, retirementYear, safeUrl, statusOf } from '../site/src/catalog.ts';

const labels = { upcoming: 'Upcoming', soon: 'Within 90 days', retired: 'Retired', unknown: 'Date to confirm' };
const projectRoot = fileURLToPath(new URL('../', import.meta.url));

export async function prepareSite({ root = projectRoot, today = new Date().toISOString().slice(0, 10) } = {}) {
  const source = join(root, 'data', 'retirements.json');
  const catalog = parseCatalog(JSON.parse(await readFile(source, 'utf8')));
  const ids = new Set();
  for (const record of catalog.records) {
    if (!record.id || ids.has(record.id)) throw new Error('Empty or duplicate retirement ID; site generation stopped');
    ids.add(record.id);
  }
  const link = value => ({ ...value, url: safeUrl(value.url) });
  const byId = Object.fromEntries(catalog.records.map(record => {
    const status = statusOf(record.questions.deadline, today);
    return [record.id, {
      record, status, label: labels[status], countdown: retirementCountdown(record.questions.deadline, today),
      sections: ['what', 'actions', 'impact', 'deadline', 'progress'].map(id => ({ id, question: record.questions[id].question })),
      year: retirementYear(record), categories: categoriesOf(record).sort(),
      url: `/retirements/${encodeURIComponent(record.id)}/`,
      deadline: formatDate(record.questions.deadline.date),
      announced: formatDate(record.announcedOn),
      updated: record.lastUpdatedOn ? formatDate(record.lastUpdatedOn) : 'Not provided by source',
      sourceUrl: safeUrl(record.sourceUrl),
      resources: record.questions.actions.resources.map(link).filter(value => value.url),
      support: link(record.questions.actions.support),
      advisor: link(record.questions.impact.advisor),
    }];
  }));
  const reference = record => ({ id: record.id, title: record.title, url: byId[record.id].url });
  const navigation = groupRetirements(catalog.records).map(group => ({
    year: group.year, label: group.year === 'unknown' ? 'Unconfirmed year' : group.year,
    count: group.records.length,
    categories: group.categories.map(category => ({
      name: category.name, count: category.records.length, records: category.records.map(reference),
    })),
  }));
  const site = {
    byId, navigation, buildDate: today,
    services: [...new Set(catalog.records.flatMap(record => record.services))].sort(),
    initialIds: filterRecords(catalog.records, { sort: 'newest' }, today).slice(0, 24).map(record => record.id),
    count: catalog.records.length, refreshed: formatDate(catalog.retrievedAt.slice(0, 10)),
    upcoming: catalog.records.filter(record => ['upcoming', 'soon'].includes(byId[record.id].status)).length,
    soon: catalog.records.filter(record => byId[record.id].status === 'soon').length,
  };
  const siteRoot = join(root, 'site');
  const collection = join(siteRoot, '_generated', '_retirements');
  const download = join(siteRoot, 'assets', 'data', 'retirements.json');
  const metadata = join(siteRoot, '_data', 'site.json');
  await mkdir(collection, { recursive: true });
  await mkdir(dirname(download), { recursive: true });
  await mkdir(dirname(metadata), { recursive: true });
  await copyFile(source, download);
  const files = new Set();
  for (const [index, record] of catalog.records.entries()) {
    const name = `record-${String(index).padStart(4, '0')}.html`;
    files.add(name);
    const frontMatter = {
      layout: 'retirement', title: record.title, record_id: record.id, permalink: byId[record.id].url,
    };
    await writeFile(join(collection, name), `---\n${JSON.stringify(frontMatter, null, 2)}\n---\n`);
  }
  for (const name of await readdir(collection)) {
    if (/^record-\d+\.html$/.test(name) && !files.has(name)) await rm(join(collection, name));
  }
  await writeFile(metadata, `${JSON.stringify(site)}\n`);
  return site;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const site = await prepareSite();
  console.log(`Prepared ${site.count} static retirement pages for Jekyll.`);
}
