import { parseCatalog } from './catalog.js';
async function loadCatalog() {
    try {
        const response = await fetch(new URL('../data/retirements.json', import.meta.url));
        if (!response.ok)
            throw new Error(`Catalog request failed: ${response.status}`);
        const catalog = await response.json();
        return parseCatalog(catalog);
    }
    catch (error) {
        const message = document.createElement('div');
        message.className = 'notice';
        message.setAttribute('role', 'alert');
        const heading = document.createElement('h1');
        heading.textContent = 'Interactive catalog features could not be loaded.';
        const hint = document.createElement('p');
        hint.textContent = 'The static retirement pages remain available. Reload to retry search and saved progress, or visit Microsoft Azure Updates for official announcements.';
        const link = document.createElement('a');
        link.href = 'https://azure.microsoft.com/updates/';
        link.textContent = 'Open Azure Updates';
        message.append(heading, hint, link);
        document.querySelector('#main')?.prepend(message);
        throw error;
    }
}
export default await loadCatalog();
