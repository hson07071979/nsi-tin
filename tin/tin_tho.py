"""Dự phòng khi Gemini hết lượt / lỗi: dựng bản tin sáng bằng code (12/10/2026).

Không tóm tắt, không nhận định — chỉ chọn và xếp tin thật đã cào được:
  - chấm điểm theo từ khóa vĩ mô/thị trường + nhóm nguồn + độ mới,
  - gộp các tin trùng nội dung (cùng sự kiện từ nhiều báo),
  - mỗi chủ đề = 1 sự kiện, có tiêu đề + tóm tắt gốc của báo + link nguồn.
Cùng khuôn với chủ đề AI nên trang /tin và NSI Daily Market đọc được ngay, không phải sửa trang.
Chỉ dùng cho tab WEB; tin Zalo không dựng bản thô.
"""
from __future__ import annotations

import re
import unicodedata

# từ khóa → (điểm, loại chủ đề). Viết không dấu, so trên tiêu đề + tóm tắt đã bỏ dấu.
TU_KHOA = [
    (r"ty gia|gia usd|usd tu do|dong usd|dxy|ngoai te|cho den", 5, "vi_mo_vn"),
    (r"lai suat|nhnn|ngan hang nha nuoc|lien ngan hang|tin phieu|omo|tai cap von", 5, "vi_mo_vn"),
    (r"fed|powell|cpi my|lam phat|trai phieu my|loi suat", 4, "the_gioi"),
    (r"gia vang|vang mieng|sjc", 4, "vi_mo_vn"),
    (r"gia dau|brent|opec|gia xang|xang dau", 4, "the_gioi"),
    (r"thue|thong tu|nghi dinh|nghi quyet|bo tai chinh|ubcknn|chinh sach", 4, "chinh_sach"),
    (r"chinh phu|quoc hoi|thu tuong", 2, "chinh_sach"),
    (r"gdp|cpi|xuat khau|nhap khau|fdi|dau tu cong|giai ngan von|tang truong", 4, "vi_mo_vn"),
    (r"khoi ngoai|nang hang|ftse|msci|etf", 4, "thi_truong"),
    (r"vn-index|vnindex|chung khoan|co phieu|thanh khoan", 2, "thi_truong"),
    (r"bat dong san|gia nha|chung cu|trai phieu doanh nghiep", 3, "vi_mo_vn"),
    (r"loi nhuan|ket qua kinh doanh|quy iii|quy 3|co tuc|phat hanh", 2, "doanh_nghiep"),
    (r"trung quoc|thue quan|thuong mai|chien tranh|xung dot", 3, "the_gioi"),
]


def _khong_dau(s: str) -> str:
    s = unicodedata.normalize("NFD", s or "").lower().replace("đ", "d")
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def _tu(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", _khong_dau(s)) if len(w) > 2}


def _diem(it: dict) -> tuple[int, str]:
    """Tiêu đề quyết định chính (×2, tối đa 2 nhóm từ khóa); tóm tắt chỉ cộng nhóm mạnh nhất — tránh tin tóm tắt dài
    nhắc đủ thứ được điểm cao."""
    tieu_de = _khong_dau(it.get("title", ""))
    tom_tat = _khong_dau(it.get("summary", ""))
    td = sorted(((d, lo) for pat, d, lo in TU_KHOA if re.search(pat, tieu_de)), reverse=True)[:2]
    tt = max(((d, lo) for pat, d, lo in TU_KHOA if re.search(pat, tom_tat)), default=(0, "khac"))
    diem = 2 * sum(d for d, _ in td) + tt[0]
    loai = td[0][1] if td else tt[1]
    if diem and it.get("group") == "quoc_te":
        diem += 1
    return diem, loai


def dung_tab(items: list[dict], max_topics: int = 10, ly_do: str = "") -> dict:
    """Trả tab WEB cùng khuôn run_tab, đánh dấu tin_tho=True."""
    tab: dict = {"kind": "web", "n_items": len(items), "topics": [], "tin_tho": True,
                 "loi": f"AI không chạy được ({ly_do[:160]}) — đang hiện bản tin thô xếp bằng code" if ly_do else None}
    if not items:
        tab["loi"] = "không có tin trong cửa sổ"
        return tab
    cham = []
    for it in items:
        d, lo = _diem(it)
        if d > 0:
            cham.append((d, it.get("published") or "", it, lo))
    cham.sort(key=lambda x: (x[0], x[1]), reverse=True)
    nhom: list[dict] = []          # mỗi nhóm = một sự kiện
    for d, _, it, lo in cham:
        w = _tu(it.get("title", ""))
        for g in nhom:
            if w and len(w & g["w"]) / max(1, min(len(w), len(g["w"]))) >= 0.6:
                g["ids"].append(it["id"])
                g["d"] += 1
                break
        else:
            nhom.append({"w": w, "ids": [it["id"]], "it": it, "d": d, "loai": lo})
    nhom.sort(key=lambda g: g["d"], reverse=True)
    for i, g in enumerate(nhom[:max_topics], 1):
        it = g["it"]
        tab["topics"].append({
            "id": f"t{i}", "hang": i, "tieu_de": it.get("title", "").strip(), "loai": g["loai"],
            "item_ids": g["ids"][:3], "mot_dong": (it.get("summary") or "").strip()[:400],
            "su_kien_hay_nhan_dinh": "chua_phan_loai", "quan_trong": max(1, min(5, round(g["d"] / 4))),
            "tin_tho": True,
        })
    by_id = {it["id"]: it for it in items}
    for t in tab["topics"]:
        t["nguon"] = [{"id": i, "title": by_id[i].get("title") or "", "summary": by_id[i].get("summary", ""),
                       "url": by_id[i].get("url"), "src_name": by_id[i].get("src_name"),
                       "published": by_id[i].get("published")} for i in t["item_ids"] if i in by_id]
    return tab
