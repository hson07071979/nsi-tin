// Cách dùng: node ap-dung.mjs <file-worker.js>
// Cổng khách nsi-cong, trang /mo-tai-khoan: ô #msg nằm TRONG form nên ẩn cả form thì ẩn luôn thông báo chờ duyệt + nút Zalo.
// Sửa: chỉ ẩn các phần tử khác của form, giữ #msg và nút "Nhắn Zalo cho anh Sơn" (zalo.me/0559562157).
import fs from 'node:fs';
const f = process.argv[2];
let s = fs.readFileSync(f, 'utf8');
const TIM = `if(ok){$('#f').style.display='none';msg(j.message,true);$('#msg').insertAdjacentHTML(`;
const THAY = `if(ok){[...$('#f').children].forEach(c=>{if(c.id!=='msg')c.style.display='none'});msg(j.message,true);$('#msg').insertAdjacentHTML(`;
if (s.includes(THAY)) { console.error('DỪNG: file đã được sửa rồi'); process.exit(1); }
const n = s.split(TIM).length - 1;
if (n !== 1) { console.error(`DỪNG: chỗ cần sửa xuất hiện ${n} lần (cần đúng 1)`); process.exit(1); }
s = s.replace(TIM, THAY);
fs.writeFileSync(f, s);
console.log('Đã sửa: sau khi gửi chỉ ẩn ô nhập, giữ thông báo chờ duyệt + nút Zalo.');
