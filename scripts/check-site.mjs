import assert from 'node:assert/strict';
import { access, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parse, parseFragment } from 'parse5';
import { parseCatalog } from '../site/src/catalog.ts';

function elements(node) {
  return [node, ...(node.childNodes || []).flatMap(elements)];
}
const attribute = (node, name) => node.attrs?.find(attr => attr.name === name)?.value;
const text = node => node.nodeName === '#text' ? node.value : (node.childNodes || []).map(text).join('');
const catalog = parseCatalog(JSON.parse(await readFile(new URL('../data/retirements.json', import.meta.url), 'utf8')));
const destination = new URL('../site/_site/', import.meta.url);
const home = parse(await readFile(new URL('index.html', destination), 'utf8'));
const nodes = elements(home);
const base = attribute(nodes.find(node => node.tagName === 'body'), 'data-home');
assert.ok(base?.startsWith('/') && base.endsWith('/'), 'Missing site base path');
assert.equal(nodes.filter(node => node.tagName === 'article' && attribute(node, 'class') === 'card').length, Math.min(24, catalog.records.length));
const paths = new Set();
for (const node of nodes) {
  const href = attribute(node, 'href') || attribute(node, 'src');
  if (!href || href.startsWith('#') || /^https?:/.test(href)) continue;
  const url = new URL(href, `https://site.example${base}`);
  assert.ok(url.pathname.startsWith(base), `Link escapes the site base path: ${href}`);
  paths.add(url.pathname.slice(base.length));
}
for (const path of paths) {
  await access(new URL(path.endsWith('/') || path === '' ? `${path}index.html` : path, destination));
}
for (const record of catalog.records) {
  const html = await readFile(new URL(`retirements/${encodeURIComponent(record.id)}/index.html`, destination), 'utf8');
  const heading = elements(parseFragment(html.match(/<h1>[\s\S]*?<\/h1>/)?.[0] || '')).find(node => node.tagName === 'h1');
  assert.equal(heading && text(heading), record.title, `${record.id}: static title missing`);
  const article = html.slice(html.indexOf('<article class="detail-content">'), html.indexOf('</article>'));
  const sections = elements(parseFragment(article)).filter(node => node.tagName === 'section');
  assert.deepEqual(sections.map(node => attribute(node, 'id')), ['what', 'actions', 'impact', 'deadline', 'progress'], `${record.id}: question order`);
  for (const section of sections) {
    const id = attribute(section, 'id');
    const heading = elements(section).find(node => node.tagName === 'h2');
    assert.ok(text(heading).endsWith(record.questions[id].question), `${record.id}: ${id} heading`);
  }
  assert.ok(html.includes('data-countdown'), `${record.id}: static countdown missing`);
  assert.ok(html.includes(`${base}assets/js/main.js`), `${record.id}: script base path`);
}
assert.deepEqual(JSON.parse(await readFile(new URL('assets/data/retirements.json', destination), 'utf8')), catalog);
for (const privatePath of ['src', 'scripts', 'tests', 'data', 'Gemfile', 'package.json']) {
  await assert.rejects(access(new URL(privatePath, destination)), { code: 'ENOENT' }, `${privatePath} must not be published`);
}
for (const module of ['main.js', 'data.js', 'catalog.js']) {
  await access(new URL(join('assets', 'js', module).replaceAll('\\', '/'), destination));
}
console.log(`Verified ${catalog.records.length} Jekyll detail pages, five-question content, catalog download, and ${paths.size} local links/assets under ${base}.`);
