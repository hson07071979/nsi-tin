// Cách dùng: node ap-dung.mjs <file-worker.js>
// Cổng khách nsi-cong, trang /mo-tai-khoan (03/10):
//  1) Bỏ dòng "Nhắn Zalo cho anh Sơn để được duyệt nhanh:" phía trên nút Zalo sau khi gửi thành công.
//  2) Khi báo "Số điện thoại này đã đăng ký" → thêm 1 dòng link nhỏ tới Zalo anh Sơn ngay dưới thông báo lỗi.
import fs from 'node:fs';
const f = process.argv[2];
let s = fs.readFileSync(f, 'utf8');
const sua = [
  [`<p class="sub" style="text-align:center;margin:14px 0 8px">Nhắn Zalo cho anh Sơn để được duyệt nhanh:</p><a class="btn" href="https://zalo.me/0559562157" target="_blank" rel="noopener" style="display:block;`,
   `<a class="btn" href="https://zalo.me/0559562157" target="_blank" rel="noopener" style="margin-top:14px;display:block;`],
  [`else msg(j.error||'Chưa gửi được.')}\`);`,
   `else{msg(j.error||'Chưa gửi được.');const z=$('#zl');if(z)z.remove();if(/đã đăng ký/.test(j.error||''))$('#msg').insertAdjacentHTML('afterend','<a id="zl" class="link" href="https://zalo.me/0559562157" target="_blank" rel="noopener" style="display:block;text-align:center;font-size:14px;margin:6px 0 10px">Nhắn Zalo cho anh Sơn →</a>')}}\`);`],
];
sua.forEach(([tim, thay], i) => {
  const n = s.split(tim).length - 1;
  if (n !== 1) { console.error(`DỪNG: chỗ sửa ${i + 1} xuất hiện ${n} lần (cần đúng 1)`); process.exit(1); }
  s = s.replace(tim, () => thay);
  console.log(`Chỗ sửa ${i + 1}: OK`);
});
fs.writeFileSync(f, s);
