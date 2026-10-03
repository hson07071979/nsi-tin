// Cách dùng: node ap-dung.mjs <file-worker.js>
// Cổng khách nsi-cong (03/10): khách không gọi "anh Sơn" → đổi mọi chữ "anh Sơn"/"Anh Sơn" thành "Nguyễn Sơn".
import fs from 'node:fs';
const f = process.argv[2];
let s = fs.readFileSync(f, 'utf8');
const RE = /\b[Aa]nh Sơn\b/gu;
const lines = s.split('\n');
let dem = 0;
lines.forEach((l, i) => { if (RE.test(l)) { RE.lastIndex = 0; dem += (l.match(RE) || []).length; console.log(`${i + 1}: ${l.trim().slice(0, 300)}`); } RE.lastIndex = 0; });
if (!dem) { console.error('DỪNG: không còn chữ "anh Sơn" nào'); process.exit(1); }
s = s.replace(RE, 'Nguyễn Sơn');
fs.writeFileSync(f, s);
console.log(`Đã đổi ${dem} chỗ "anh Sơn" → "Nguyễn Sơn".`);
