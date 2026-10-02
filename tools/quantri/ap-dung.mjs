// Cách dùng: node ap-dung.mjs <file-worker.js>
// Áp 5 chỗ sửa + dán DAN-CUOI-FILE.txt vào cuối. Mỗi chữ cần tìm phải xuất hiện đúng 1 lần, nếu không thì dừng, không ghi gì.
import fs from 'node:fs';
const f = process.argv[2];
if (!f) { console.error('Thiếu tên file'); process.exit(1); }
let s = fs.readFileSync(f, 'utf8');
const once = (needle) => {
  const n = s.split(needle).length - 1;
  if (n !== 1) { console.error(`DỪNG: "${needle}" xuất hiện ${n} lần (cần đúng 1)`); process.exit(1); }
};
if (s.includes('const TIN_MOD')) { console.error('DỪNG: file đã được sửa rồi (có TIN_MOD)'); process.exit(1); }
const steps = [
  ['const origin = (env.ORIGIN ||', () => s.replace('const origin = (env.ORIGIN ||', 'const origin = ADMIN ? RAW_GOC : (env.ORIGIN ||')],
  ['url.pathname + url.search', () => s.replace('url.pathname + url.search', '(ADMIN ? duongRaw(url.pathname) : url.pathname + url.search)')],
  ['const h = new Headers(up.headers)', () => s.replace(/(const h = new Headers\(up\.headers\)[^\n]*\n)/, `$1if (ADMIN) suaRaw(h, url.pathname);\n`)],
  ['async function serveSite', () => s.replace(/(async function serveSite[^\n]*\n[^\n]*const url = new URL\(req\.url\)[^\n]*\n)/, `$1if (ADMIN && url.pathname === '/tin') return TIN_MOD.handleTin(req, env);\n`)],
  ['>Xem web</a>', () => s.replace('>Xem web</a>', '>Xem web</a> <a href="/tin">Bản tin sáng</a>')],
];
steps.forEach(([needle, apply], i) => {
  once(needle);
  const before = s; s = apply();
  if (s === before) { console.error(`DỪNG: bước ${i + 1} không khớp mẫu quanh "${needle}"`); process.exit(1); }
  console.log(`Bước ${i + 1}: OK`);
});
s = s.replace(/\s*$/, '\n') + fs.readFileSync(new URL('./DAN-CUOI-FILE.txt', import.meta.url), 'utf8');
fs.writeFileSync(f, s);
console.log('Bước 6: đã dán DAN-CUOI-FILE.txt vào cuối. Xong — chạy: node --check ' + f);
