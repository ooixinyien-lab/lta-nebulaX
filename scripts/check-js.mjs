// Optional syntax test. Run from the repository root: node scripts/check-js.mjs
import { readdirSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
const root = resolve(dirname(fileURLToPath(import.meta.url)), '../frontend/src');
function walk(dir) { return readdirSync(dir, {withFileTypes:true}).flatMap(x=>x.isDirectory()?walk(join(dir,x.name)):[join(dir,x.name)]); }
const files=walk(root).filter(x=>x.endsWith('.js'));
for(const file of files) execFileSync(process.execPath,['--check',file],{stdio:'inherit'});
console.log(`${files.length} frontend modules passed JavaScript syntax checks.`);
