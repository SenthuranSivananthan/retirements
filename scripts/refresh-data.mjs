import { mkdir, rename, writeFile } from 'node:fs/promises';
import { endpoint, fetchRetirements } from './feed.mjs';

const records = await fetchRetirements();
const output = new URL('../data/retirements.json', import.meta.url);
await mkdir(new URL('../data/', import.meta.url), { recursive: true });
const temporary = new URL('../data/retirements.json.tmp', import.meta.url);
await writeFile(temporary, `${JSON.stringify({ source: endpoint, retrievedAt: new Date().toISOString(), records }, null, 2)}\n`);
await rename(temporary, output);
console.log(`Saved ${records.length} retirement announcements (${records.filter(record => record.retirementDate).length} with exact title dates).`);
