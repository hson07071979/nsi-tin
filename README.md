# nsi-tin — Bản tin sáng 7h → 8h (Nguyễn Sơn Invest)

Repo **PRIVATE**. Chứa tin nhóm Zalo kín — không bao giờ để public.

```
6h40  laptop: bộ nghe Zalo (nick phụ) bù lịch sử 5 nhóm + đẩy zalo/inbox/*.jsonl lên repo
7h00  đồng hồ ảo nsi-dong-ho → workflow sang.yml (che_do=chay)
        1. cào tab WEB: CafeF, VnExpress, Vietstock, VnEconomy, TNCK, NHNN (LNH), Fed, MarketWatch, Investing, fisc.vn
        2. đọc tab ZALO: Money Noobs, FinSuccess, Lavender, Balance, Ánh Kem
        3. ảnh chụp vĩ mô (LNH, USD/VND, DXY, US10Y, Brent, vàng, VIX, VN-Index) + sổ luật vĩ mô MỀM
        4. AI debate (Gemini) mỗi tab: lọc + xếp hạng top 15 → đọc trọn bài báo → diễn giải kỹ → 3 phe (lạc quan / thận trọng / vĩ mô) → phản biện chéo → trọng tài
        5. tổng hợp sáng: 3 điều cần biết, đối chiếu web↔Zalo, việc hôm nay, 1 bài luyện vĩ mô
        6. chấm điểm bản tin cũ (T+5 vs VN-Index) → phe nào hay đúng, tin đồn đúng bao nhiêu
      → out/latest.json   (xong khoảng 7h05–7h20)
7h45  gác: hôm nay chưa có bản đạt thì chạy lại
8h15  gác lần cuối (hạn chót 8h30)
      anh Sơn đọc ở nsi-quantri /tin — 2 tab Tin web | Tin Zalo
```

## Nguyên tắc (không được phá)

- **Sổ luật vĩ mô là cờ MỀM.** Không cờ nào chặn lệnh của bộ máy 9 lớp, không cờ nào hạ cỡ lệnh thăm dò.
  Mức cao nhất một cờ được gợi ý: *không pyramid / không top-up mới, soi tay kỹ hơn*.
- **Mức cao không phải tín hiệu, cú sốc mới là tín hiệu.** "Lãi suất cao bình thường" → `LS_CAO_ON_DINH` → không hành động.
  "LNH tăng sốc" → `LNH_SOC_NGAN` → thận trọng. Tỷ giá căng + LNH sốc cùng lúc → cặp nguy hiểm.
- Muốn nâng một cờ thành luật: chạy `research/macro_research.py` trên deal thật. Phải qua đủ 5 lớp
  (mẫu ≥ 20, bootstrap, theo năm, bỏ deal biên, walk-forward lồng) và **hỏi anh Sơn trước khi đụng PROD**.
- Nguồn hỏng không được làm sập cả buổi sáng: mỗi nguồn lỗi riêng, AI lỗi giữa chừng vẫn ghi danh sách tin.
- Thiếu dữ liệu ≠ cờ tắt. Trang hiện "thiếu dữ liệu".

## File

| Đường dẫn | Việc |
|---|---|
| `tin/run_sang.py` | điều phối (`--gac`, `--dry`) |
| `tin/fetch_web.py` · `tin/fetch_zalo.py` | cào web / đọc Zalo |
| `tin/macro.py` · `tin/playbook.py` | ảnh chụp vĩ mô, sổ nhật ký điểm-thời-gian `data/macro_daily.csv`, chấm cờ mềm |
| `tin/gemini.py` · `tin/debate.py` | client Gemini (tự chọn model flash, giãn nhịp 8 lượt/phút, thử lại 429) · hội đồng 3 phe + trọng tài |
| `tin/cham_diem.py` | was_i_right: chấm nhận định cũ bằng giá thật |
| `config/sources.json` | thêm/bớt nguồn web |
| `config/zalo_groups.json` | 5 nhóm Zalo (điền threadId sau khi chạy `--liet-ke`) |
| `config/macro_playbook.json` | sổ luật vĩ mô mềm |
| `zalo-listener/` | chạy trên laptop Windows (Node 18+, zca-js) |
| `worker/tin_page.js` | trang /tin cho Worker nsi-quantri |
| `worker/dong_ho_tin.js` | thêm vào Worker nsi-dong-ho |
| `research/macro_research.py` | kiểm cờ vĩ mô trên deal thật |
| `tests/` | `python -m pytest -q tests` (13 test, không gọi mạng) |

## Chi phí và lưu ý Gemini free tier

- ~35 lượt gọi/ngày (15 chủ đề × 2 tab, chia lô 8) — vẫn xa hạn mức free. Không tốn tiền.
- **Free tier: Google có thể dùng nội dung gửi lên để cải thiện model.** Tức là tin nhắn 5 nhóm Zalo sẽ đi qua Google.
  Muốn tránh: bật billing cho project Gemini (bản trả phí không dùng dữ liệu để train; ~17 lượt/ngày tốn rất ít).
- Free tier không dành cho mục đích thương mại — ở đây chỉ anh Sơn đọc ở trang quản trị, không bán cho khách.

---

# nsi-daily — NSI Daily Market (thêm 12/10/2026)

Bản nháp phân tích + lời thoại YouTube ~20' + 3 clip TikTok sau mỗi phiên. Chỉ hiện ở trang quản trị `/daily`.

```
15:20  đồng hồ ảo → daily_market.yml che_do=chay
         1. chờ VNDirect công bố đủ phiên (tối đa 20'; ngày nghỉ thì không chờ)
         2. FACT: VN-Index + breadth + khớp/thỏa thuận + khối ngoại + tự doanh (VNDirect), đóng góp điểm, ngành,
            ~95 mã rổ + ≤10 mã nổi bật (kỹ thuật tính bằng code), liên thị trường (Yahoo), vĩ mô 7h + tin WEB của nsi-tin
         3. chấm sổ dự báo bằng giá thật (data/daily/so_du_bao.json)
         4. Gemini 2 cách (2 bước / 1 lượt) → "Bản 1 / Bản 2" xáo ngẫu nhiên
       → out/daily/<ngày>.json + latest.json (xong ~5–15')
16:00  gác: chưa có bản thì chạy lại · 16:40 cron GitHub dự phòng
bất kỳ: trang /daily → che_do=viet_lai (THESIS CHECK view của anh + viết lại lời thoại)
```

- Kho nến: cào lịch sử một lần, sau đó mỗi ngày chỉ nối nến phiên; tự dựng lại khi thiếu phiên hoặc có quyền (giá tham chiếu lệch).
  Lưu bằng actions/cache, không commit.
- Tin Zalo **không bao giờ** đi vào nsi-daily.
- Chọn xong cách chạy thì sửa `config/daily.json` → `cach_chay` còn một cách cho đỡ hạn mức Gemini.
- Rổ mã: `config/daily.json` → `ro`. Ngành ICB: `config/daily_sector.json` (chép từ nsi-bot).
- Kiểm offline: `python -m pytest -q tests/test_daily.py`. Chạy thử không gọi AI: `python -m daily.run_daily --dry`.
- Nối Cloudflare (đồng hồ ảo 15:20, trang /daily): xem `worker/LAM-NGAY-daily.md`.
