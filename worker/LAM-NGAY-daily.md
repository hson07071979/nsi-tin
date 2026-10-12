# LÀM NGAY — nối NSI Daily Market vào đồng hồ ảo + trang quản trị (12/10/2026)

Code bot đã nằm trong repo `nsi-tin` (thư mục `daily/`, workflow `daily_market.yml`) và đã chạy thật được.
Còn 3 việc ở Cloudflare. Không việc nào động tới bot giao dịch hay trang khách.

## 1. Đồng hồ ảo `nsi-dong-ho` gọi bot lúc 15:20 và gác lúc 16:00

Token `nsi-dong-ho-ao` **đã có** quyền Actions trên nsi-tin (vì đang gọi `sang.yml`) → không cần sửa token.

Sửa `worker.js` của nsi-dong-ho, 2 chỗ:

```js
// (a) trong function lich(h, m), ngay dưới các dòng của TIN (07:00 / 07:45 / 08:15)
  if (t === 15 * 60 + 20) out.push([TIN, 'daily_market.yml', 'chay']);
  if (t === 16 * 60)      out.push([TIN, 'daily_market.yml', 'gac']);

// (b) trong function goi(...), ngay TRÊN dòng  if (wf === 'daily.yml')
  if (wf === 'daily_market.yml') body.inputs = { che_do: nhan || 'chay' };
```

Cron của Worker giữ nguyên (`*/5 0-14 * * MON-FRI` đã phủ 15:20 và 16:00 giờ VN). Cuối tuần Worker tự lọc bỏ.
Deploy xong, mở `https://nsi-dong-ho.hson07071979.workers.dev/` → phải thấy dòng `15:20 nsi-tin/daily_market.yml`
và `16:00 nsi-tin/daily_market.yml`.

## 2. Trang `/daily` ở nsi-quantri

1. Copy `worker/daily_page.js` vào `src/` của Worker (deploy bằng dashboard một file: bỏ chữ `export` ở hàm
   `handleDaily` và dán cả file vào cuối `index.js`).
2. Đầu `index.js`: `import { handleDaily } from './daily_page.js';`
3. Trong `serveSite()`, ngay dưới dòng `/tin` đã có:
   ```js
   if (ADMIN && (url.pathname === '/daily' || url.pathname.startsWith('/daily/'))) return handleDaily(req, env)
   ```
4. Header trang quản trị, cạnh `<a href="/tin">Bản tin sáng</a>`: thêm `<a href="/daily">Daily Market</a>`.
5. Biến Worker: `TIN_REPO`, `TIN_TOKEN` đã có (đọc nsi-tin) → dùng lại. Thêm **một** Secret mới cho nút "Viết lại":
   - GitHub → Settings → Developer settings → Fine-grained tokens → Generate: chỉ repo `nsi-tin`,
     quyền **Actions: Read and write** (không cần quyền nào khác).
   - Cloudflare → nsi-quantri → Settings → Variables and Secrets → thêm `DAILY_DISPATCH_TOKEN` (loại Secret).
   Chưa có secret này thì trang vẫn đọc được bản tự động; chỉ nút "Viết lại" báo thiếu.
6. Kiểm: nsi-quantri (đã đăng nhập admin) `/daily` ra bản phiên 12/10; trang khách (nsi-cong) `/daily` → 404.

## 3. (Tùy chọn) link từ /daily mở thẳng Chi tiết mã

Bấm mã trên `/daily` mở `/index.html?ma=SSI#bieudo`. Trang web hiện chưa đọc `?ma=` nên sẽ mở Chi tiết mã của mã
mặc định. Muốn mở đúng mã: thêm đoạn trong `worker/site_deeplink_p21.patch` vào CUỐI `site/p21.js` của nsi-bot
(trước p7.js trong thứ tự dựng trang). Đây là thay đổi giao diện, không động tới luật giao dịch — nhưng là PROD
nên anh tự quyết.

## Lịch chạy hằng ngày

| Giờ VN | Ai gọi | Việc |
|---|---|---|
| 07:00 | đồng hồ ảo | nsi-tin bản tin sáng (đã có) → nsi-daily đọc lại phần vĩ mô + tin web lúc chiều |
| 15:20 | đồng hồ ảo | daily_market `chay`: chờ VNDirect công bố đủ (tối đa 25'), dựng FACT, Gemini 2 cách |
| 16:00 | đồng hồ ảo | daily_market `gac`: chưa có bản thì chạy lại |
| 16:40 | cron GitHub (dự phòng) | `gac` |
| bất kỳ | trang /daily | `viet_lai` theo view anh gõ |

Ngày lễ: bot thấy VNDirect không có phiên → ghi "Không có phiên", không gọi Gemini.
