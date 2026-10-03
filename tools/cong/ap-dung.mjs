// Cách dùng: node ap-dung.mjs <file-worker.js>
// Cổng khách nsi-cong: sau khi gửi yêu cầu mở tài khoản, hiện thêm nút "Nhắn Zalo cho anh Sơn" (zalo.me/0559562157).
import fs from 'node:fs';
const f = process.argv[2];
let s = fs.readFileSync(f, 'utf8');
const TIM = 'msg(j.message,true)}';
const THAY = `msg(j.message,true);$('#msg').insertAdjacentHTML('afterend','<p class="sub" style="text-align:center;margin:14px 0 8px">Nhắn Zalo cho anh Sơn để được duyệt nhanh:</p><a class="btn" href="https://zalo.me/0559562157" target="_blank" rel="noopener" style="display:block;text-align:center;text-decoration:none">Nhắn Zalo cho anh Sơn →</a>')}`;
if (s.includes('Nhắn Zalo cho anh Sơn')) { console.error('DỪNG: file đã có nút Nhắn Zalo cho anh Sơn'); process.exit(1); }
const n = s.split(TIM).length - 1;
if (n !== 1) { console.error(`DỪNG: "${TIM}" xuất hiện ${n} lần (cần đúng 1)`); process.exit(1); }
const i = s.indexOf(TIM);
console.log('--- Ngữ cảnh quanh chỗ sửa ---\n' + s.slice(Math.max(0, i - 700), i + 200));
s = s.replace(TIM, THAY);
fs.writeFileSync(f, s);
console.log('Đã thêm nút Zalo sau thông báo chờ duyệt.');
