// Node.js script: извлекает CATEGORIES из strips.html -> categories_db.json
// Запуск: node dashboard/extract_cats_node.mjs
import { readFileSync, writeFileSync, mkdirSync } from 'fs';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const STRIPS = join(__dirname, 'templates', 'strips.html');
const OUT_DIR = join(__dirname, 'data');
const OUT_JSON = join(OUT_DIR, 'categories_db.json');

const html = readFileSync(STRIPS, 'utf-8');

// Находим блок между маркерами
const startMark = '// [[CATEGORIES_START]]';
const endMark   = '// [[CATEGORIES_END]]';
const s = html.indexOf(startMark);
const e = html.indexOf(endMark);
if (s === -1 || e === -1) throw new Error('Markers not found');

const block = html.slice(s + startMark.length, e).trim();
// block = "const CATEGORIES = { ... };"

// Безопасно исполняем через Function (не eval глобального контекста)
const fn = new Function(`${block}; return CATEGORIES;`);
const CATEGORIES = fn();

// Проверяем
const catKeys = Object.keys(CATEGORIES);
console.log(`Categories found: ${catKeys.length}`);
catKeys.forEach(k => {
  const items = CATEGORIES[k].items || [];
  console.log(`  [${k}] ${CATEGORIES[k].title} - ${items.length} items`);
});

// Пишем JSON
mkdirSync(OUT_DIR, { recursive: true });
writeFileSync(OUT_JSON, JSON.stringify(CATEGORIES, null, 2), 'utf-8');
const total = catKeys.reduce((s, k) => s + (CATEGORIES[k].items?.length || 0), 0);
console.log(`\nSaved to: ${OUT_JSON}`);
console.log(`Total items: ${total}`);
