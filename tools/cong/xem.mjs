// In các đoạn code liên quan (CSP, hàm page, registerPage) để chẩn đoán. Không sửa file.
import fs from 'node:fs';
const s = fs.readFileSync(process.argv[2], 'utf8');
const lines = s.split('\n');
lines.forEach((l, i) => { if (/content-security-policy|sha256|nonce|SEC_HEADERS|script-src|function page\(|crypto\.subtle|digest/i.test(l)) console.log(`${i + 1}: ${l.slice(0, 400)}`); });
const a = s.indexOf('function page('); if (a >= 0) console.log('--- page() ---\n' + s.slice(a, a + 2500));
const b = s.indexOf('function registerPage'); if (b >= 0) console.log('--- registerPage ---\n' + s.slice(b, b + 2600));
