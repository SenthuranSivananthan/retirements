import { mkdir, readFile, rename, rm, writeFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';
import { endpoint, fetchRetirements, mergeRetirements } from './feed.mjs';

async function readSnapshot(output) {
  try {
    return await readFile(output, 'utf8');
  } catch (error) {
    if (error.code === 'ENOENT') return null;
    throw error;
  }
}

export async function refreshCatalog({ fetcher, output = new URL('../data/retirements.json', import.meta.url) } = {}) {
  const fetched = await fetchRetirements(fetcher);
  const original = await readSnapshot(output);
  const previous = original === null ? null : JSON.parse(original);
  if (original !== null && previous?.schemaVersion !== 2) {
    throw new Error('Unsupported catalog schema; existing snapshot preserved');
  }
  const records = mergeRetirements(fetched, previous === null ? [] : previous.records);
  const catalog = { schemaVersion: 2, source: endpoint, retrievedAt: new Date().toISOString(), records };
  await mkdir(new URL('.', output), { recursive: true });
  const temporary = new URL(`${output.href}.${process.pid}.tmp`);
  try {
    await writeFile(temporary, `${JSON.stringify(catalog, null, 2)}\n`);
    if (await readSnapshot(output) !== original) {
      throw new Error('Catalog changed during refresh; existing snapshot preserved. Retry the refresh.');
    }
    await rename(temporary, output);
  } finally {
    await rm(temporary, { force: true });
  }
  return catalog;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const { records } = await refreshCatalog();
  console.log(`Saved ${records.length} retirement announcements (${records.filter(record => record.manuallyEnriched).length} manually enriched records preserved).`);
}
