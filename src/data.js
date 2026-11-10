export const catalogDownload = new URL('../data/retirements.json', import.meta.url).href;

async function loadCatalog() {
  try {
    const response = await fetch(catalogDownload);
    if (!response.ok) throw new Error(`Catalog request failed: ${response.status}`);
    const catalog = await response.json();
    if (!Array.isArray(catalog.records) || !catalog.records.length) throw new Error('Empty retirement catalog');
    return catalog;
  } catch (error) {
    const message = document.createElement('main');
    const heading = document.createElement('h1');
    heading.textContent = 'The retirement catalog could not be loaded.';
    const hint = document.createElement('p');
    hint.textContent = 'Check your connection and reload this page, or visit Microsoft Azure Updates for official announcements.';
    const link = document.createElement('a');
    link.href = 'https://azure.microsoft.com/updates/';
    link.textContent = 'Open Azure Updates';
    message.append(heading, hint, link);
    document.querySelector('#app').replaceChildren(message);
    throw error;
  }
}

export default await loadCatalog();
