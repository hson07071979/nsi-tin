# slides/ — PPT video Nguyen Son Finance, dựng tự động (không gọi AI)

## Luồng mỗi ngày (Sơn chốt 13/10/2026)

| Giờ VN | Việc | Ai |
|---|---|---|
| 15:20 / 16:00 | `daily_market.yml`: số liệu + Gemini viết **1 bản** (phân tích + lời thoại) | đồng hồ ảo gọi |
| ngay sau đó | `python -m slides.brief` → `out/daily/brief/<ngày>.md`; `python -m slides.make` → PPT **nháp** lên KV | cùng workflow |
| tối | Sơn mở chat Claude: Claude đọc brief, kiểm số liệu/logic, **chỉ sửa câu sai** (không viết lại văn), ghi `out/daily/claude/<ngày>.json` rồi push | Claude |
| ngay khi push | `slides.yml` dựng lại PPT **chính thức** lên KV | GitHub Actions |
| bất kỳ | Trang quản trị `/daily` → nút **Tải PPT** | Sơn |

Bản Gemini (nháp) không bao giờ đè bản Claude cùng ngày trên KV.

## Chart

- Nến ngày 6 tháng, MA20/50/200, KL + TB20. **Không vẽ Bollinger** (Sơn chốt 13/10).
- Đường kẻ = mốc trong bảng phân tích: mốc theo dõi (trắng), hỗ trợ kế tiếp (xanh lá, từ trường `sl`), kháng cự kế tiếp (đỏ, từ `muc_tieu`).
- Hộp mờ = vùng hỗ trợ/kháng cự `daily/tech.py` tự tính (bỏ vùng dựng từ Bollinger). Mốc phân tích luôn nổi hơn.
- Trên slide không ghi "SL", "mục tiêu", "5 sao", "CAN", "đèn NSI".

## File kiểm tra của Claude: `out/daily/claude/<YYYY-MM-DD>.json`

```json
{
  "ngay": "2026-10-13",
  "ban_goc": "cach_1_luot",
  "kiem_tra": ["Breadth hai nguồn lệch: 89/198 và 95/200 — đã ghi rõ nguồn", "..."],
  "sua_phan_tich": [
    {"duong_dan": "regime.ten", "gia_tri": "Hồi kỹ thuật / dò đáy, chưa xác nhận"},
    {"duong_dan": "ky_thuat_chi_so.neu_thung", "gia_tri": "Thủng 1.701 thì về đáy cũ 1.687, sâu hơn là 1.651–1.665."},
    {"duong_dan": "nganh[2].ma[1].xac_nhan", "gia_tri": "Vượt dứt khoát MA200 (~64,7)"}
  ],
  "sua_loi_thoai": [
    {"tim": "câu sai nguyên văn trong lời thoại", "thay": "câu đã sửa"}
  ],
  "slide": {
    "cau_hoi": "câu hỏi trung tâm cho slide mở đầu (tùy chọn)",
    "regime": "nhãn regime hiển thị (tùy chọn)",
    "ma_dang_noi": ["FPT", "HDB", "KBC"],
    "ly_do": {"FPT": "vì sao đáng nói, 1 câu"},
    "tieu_de_ma": {"TCB": "giữ kênh trên, BB bóp chặt"}
  }
}
```

- `ban_goc`: `cach` hoặc `nhan` của bản Gemini dùng làm gốc (bỏ trống = bản đầu tiên có lời thoại).
- `duong_dan` tính từ gốc `phan_tich`, dạng `a.b[0].c`.
- `sua_loi_thoai` thay chuỗi nguyên văn; câu không tìm thấy sẽ được in cảnh báo trong log.

## Chạy tay

```bash
pip install -r requirements.txt && (cd slides && npm install)
python -m slides.brief 2026-10-13
python -m slides.make --ngay 2026-10-13 --khong-upload        # file ở .cache/slides/<ngày>/
```

## Cloudflare Workers KV (một lần, miễn phí, không cần thẻ)

1. Cloudflare → Storage & databases → Workers KV → Create namespace `nsi-slides`; chép Namespace ID.
2. My Profile → API Tokens → Create Custom Token: quyền Account · **Workers KV Storage · Edit**, chỉ tài khoản của anh.
3. GitHub nsi-tin → Settings → Secrets → Actions: `CF_ACCOUNT_ID`, `CF_KV_NAMESPACE_ID`, `CF_API_TOKEN`.
4. Worker nsi-quantri → Settings → Bindings → KV namespace: tên biến `SLIDES`, namespace `nsi-slides`.
Thiếu secret thì workflow vẫn chạy, PPT nằm trong mục Artifacts của lượt chạy.
