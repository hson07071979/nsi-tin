// In các dòng có chữ "Sơn" trong code đang chạy để kiểm tra. Không sửa file.
import fs from 'node:fs';
const s = fs.readFileSync(process.argv[2], 'utf8');
s.split('\n').forEach((l, i) => { if (/Sơn|zalo\.me/.test(l)) console.log(`${i + 1}: ${l.trim().slice(0, 400)}`); });
