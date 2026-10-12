"""Sổ dự báo tự ghi, tự chấm (data/daily/so_du_bao.json).

Mỗi dòng do AI đề xuất ở cuối bản phân tích, nhưng CHẤM bằng code với giá đóng cửa thật — không để AI tự chấm mình.

Loại dòng:
  giu   : "<đối tượng> giữ trên <mốc>"   → ĐÚNG nếu hết hạn mà chưa phiên nào đóng cửa dưới mốc; SAI ngay khi thủng
  thung : "<đối tượng> thủng <mốc>"      → ĐÚNG ngay khi đóng cửa dưới mốc; SAI nếu hết hạn chưa thủng
  vuot  : "<đối tượng> vượt <mốc>"       → ĐÚNG ngay khi đóng cửa trên mốc; SAI nếu hết hạn chưa vượt
  duoi  : "<đối tượng> không vượt <mốc>" → SAI ngay khi đóng cửa trên mốc; ĐÚNG nếu hết hạn vẫn dưới
Hạn tính bằng số phiên (mặc định 5, tối đa 20).
"""
from __future__ import annotations

import hashlib

from tin.common import ROOT, read_json, write_json

SO = ROOT / "data" / "daily" / "so_du_bao.json"
LOAI = {"giu", "thung", "vuot", "duoi"}


def load() -> list[dict]:
    return read_json(SO, [])


def save(rows: list[dict]) -> None:
    write_json(SO, rows[-600:])


def check(rows: list[dict], today: str, closes: dict[str, float]) -> list[dict]:
    """Chấm các dòng đang mở bằng giá đóng cửa phiên `today`. Trả các dòng vừa đổi trạng thái."""
    changed = []
    for r in rows:
        if r.get("trang_thai") != "mo" or r.get("ngay_ghi", "") >= today or r.get("ngay_cham_cuoi") == today:
            continue
        c = closes.get(r["doi_tuong"])
        if c is None:
            continue
        r["ngay_cham_cuoi"] = today          # chạy lại trong ngày (gác / viết lại) không đếm phiên hai lần
        r["phien_da_qua"] = r.get("phien_da_qua", 0) + 1
        moc, loai = r["moc"], r["loai"]
        ket = None
        if loai == "giu" and c < moc:
            ket = "SAI"
        elif loai == "thung" and c < moc:
            ket = "ĐÚNG"
        elif loai == "vuot" and c > moc:
            ket = "ĐÚNG"
        elif loai == "duoi" and c > moc:
            ket = "SAI"
        if ket is None and r["phien_da_qua"] >= r["han_phien"]:
            ket = "ĐÚNG" if loai in ("giu", "duoi") else "SAI"
        if ket:
            r.update({"trang_thai": "dong", "ket_qua": ket, "ngay_dong": today, "gia_luc_dong": c})
            changed.append(r)
    return changed


def add(rows: list[dict], today: str, proposals: list, ban: str) -> list[dict]:
    """Ghi dòng mới từ đề xuất của AI (đã kiểm khuôn). Trùng nội dung trong ngày thì bỏ."""
    added = []
    have = {r["id"] for r in rows}
    for p in proposals or []:
        try:
            doi = str(p["doi_tuong"]).upper().strip()
            loai = str(p["loai"]).strip().lower()
            moc = float(p["moc"])
            han = max(1, min(20, int(p.get("han_phien") or 5)))
        except (KeyError, TypeError, ValueError):
            continue
        if loai not in LOAI or not doi or moc <= 0:
            continue
        rid = hashlib.sha1(f"{today}|{doi}|{loai}|{moc}".encode()).hexdigest()[:10]
        if rid in have:
            continue
        row = {"id": rid, "ngay_ghi": today, "ban": ban, "doi_tuong": doi, "loai": loai, "moc": moc, "han_phien": han,
               "loai_moc": "CAN" if str(p.get("loai_moc", "")).upper().startswith("C") else "QS",
               "noi_dung": str(p.get("noi_dung", ""))[:240], "trang_thai": "mo", "phien_da_qua": 0}
        rows.append(row)
        have.add(rid)
        added.append(row)
    return added


def summary(rows: list[dict], today: str) -> dict:
    """Phần đưa vào prompt: dòng vừa chốt hôm nay + dòng còn mở + tỷ lệ đúng tích lũy."""
    dong = [r for r in rows if r.get("trang_thai") == "dong"]
    dung = sum(1 for r in dong if r.get("ket_qua") == "ĐÚNG")
    return {
        "vua_cham_hom_nay": [r for r in dong if r.get("ngay_dong") == today],
        "dang_mo": [r for r in rows if r.get("trang_thai") == "mo"][-15:],
        "tich_luy": {"so_dong_da_cham": len(dong), "dung": dung,
                     "ty_le_dung_pct": round(dung / len(dong) * 100, 1) if len(dong) >= 10 else None,
                     "ghi_chu": "chỉ hiện tỷ lệ khi đã chấm từ 10 dòng trở lên"},
    }
