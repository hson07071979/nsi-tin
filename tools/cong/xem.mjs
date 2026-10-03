// In các đoạn code liên quan để chẩn đoán. Không sửa file.
import fs from 'node:fs';
const s = fs.readFileSync(process.argv[2], 'utf8');
s.split('\n').forEach((l, i) => { if (/mo-tai-khoan|409|tồn tại|đã (được )?đăng ký|đã có tài khoản|đã dùng|trùng|const ZALO/i.test(l)) console.log(`${i + 1}: ${l.slice(0, 500)}`); });
