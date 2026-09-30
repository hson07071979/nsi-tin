"""Chấm điểm 'was_i_right' cho các bản tin cũ — vòng luyện độ hiểu vĩ mô.

Mỗi bản tin 8h sáng ngày D chốt 'tốt/xấu' cho chủ đề và '+/-' cho mã. Sau 5 phiên, đối chiếu giá thật:
- Mã: lợi suất vượt VN-Index từ đóng cửa D-1 → đóng cửa phiên T+0 (chính ngày D) và T+4 (5 phiên).
- Chủ đề vĩ mô / thị trường (không có mã): chiều VN-Index T+4.
Trung tính không chấm. Kết quả: tỷ lệ đúng của TRỌNG TÀI và của TỪNG PHE → biết phe nào đáng tin hơn,
loại tin nào (web / zalo / tin đồn) hay sai. Đây là số liệu để chỉnh prompt và sổ luật, không phải để tự đổi luật giao dịch.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime, timedelta

from .common import ROOT, VN, http_get, now_vn, read_json, write_json

SYM = re.compile(r"^[A-Z][A-Z0-9]{2}$")
_cache: dict[str, list[tuple[str, float]]] = {}


def closes(sym: str, end: datetime) -> list[tuple[str, float]]:
    if sym in _cache:
        return _cache[sym]
    t = int(end.timestamp())
    r = http_get("https://dchart-api.vndirect.com.vn/dchart/history",
                 params={"resolution": "D", "symbol": sym, "from": t - 200 * 86400, "to": t}, tries=2)
    out = []
    if r is not None:
        try:
            j = r.json()
            out = [(datetime.fromtimestamp(a, VN).date().isoformat(), float(c)) for a, c in zip(j["t"], j["c"])]
        except (KeyError, TypeError, ValueError):
            out = []
    _cache[sym] = out
    return out


def fwd(series: list[tuple[str, float]], day: str, n: int) -> float | None:
    """Lợi suất từ đóng cửa phiên cuối TRƯỚC `day` tới đóng cửa phiên thứ n tính từ `day` (n=0 là chính day)."""
    before = [i for i, (d, _) in enumerate(series) if d < day]
    if not before:
        return None
    i0 = before[-1]
    j = i0 + 1 + n
    if j >= len(series):
        return None
    return series[j][1] / series[i0][1] - 1


def _sign(x: str | None) -> int:
    return {"tot": 1, "+": 1, "co_hoi": 1, "xau": -1, "-": -1}.get((x or "").strip(), 0)


def score_day(rep: dict, end: datetime) -> list[dict]:
    day = rep["ngay"]
    vni = closes("VNINDEX", end)
    rows = []
    for tab in ("web", "zalo"):
        for t in rep.get(tab, {}).get("topics", []) or []:
            base = {"ngay": day, "tab": tab, "chu_de": t.get("tieu_de"), "xac_minh": t.get("xac_minh"),
                    "loai": t.get("loai")}
            phe = {p: _sign((v or {}).get("nhan_dinh")) for p, v in (t.get("phe") or {}).items()}
            syms = [(x.get("ten", "").strip().upper(), _sign(x.get("chieu"))) for x in t.get("nganh_ma") or []]
            syms = [(s, c) for s, c in syms if SYM.match(s) and c]
            if syms:
                for s, c in syms:
                    ser = closes(s, end)
                    r5, b5 = fwd(ser, day, 4), fwd(vni, day, 4)
                    r0, b0 = fwd(ser, day, 0), fwd(vni, day, 0)
                    if r5 is None or b5 is None:
                        continue
                    ex5 = r5 - b5
                    rows.append({**base, "doi_tuong": s, "du_bao": c, "vuot_t0": None if r0 is None or b0 is None else round((r0 - b0) * 100, 2),
                                 "vuot_t4": round(ex5 * 100, 2), "dung": (ex5 > 0) == (c > 0),
                                 "phe": {p: (None if v == 0 else (ex5 > 0) == (v > 0)) for p, v in phe.items()}})
            else:
                c = _sign(t.get("danh_gia"))
                if c == 0 or t.get("loai") not in ("vi_mo_vn", "quoc_te", "chinh_sach", "thi_truong"):
                    continue
                b5 = fwd(vni, day, 4)
                if b5 is None:
                    continue
                rows.append({**base, "doi_tuong": "VNINDEX", "du_bao": c, "vuot_t4": round(b5 * 100, 2),
                             "dung": (b5 > 0) == (c > 0),
                             "phe": {p: (None if v == 0 else (b5 > 0) == (v > 0)) for p, v in phe.items()}})
    return rows


def summarize(rows: list[dict]) -> dict:
    def rate(xs):
        xs = [x for x in xs if x is not None]
        return {"n": len(xs), "ty_le_dung": round(sum(xs) / len(xs) * 100, 1) if xs else None}
    by = defaultdict(list)
    for r in rows:
        by["trong_tai"].append(r["dung"])
        by[f"tab_{r['tab']}"].append(r["dung"])
        by[f"xac_minh_{r.get('xac_minh')}"].append(r["dung"])
        for p, v in (r.get("phe") or {}).items():
            by[f"phe_{p}"].append(v)
    return {k: rate(v) for k, v in sorted(by.items())}


def main() -> int:
    end = now_vn()
    out_dir = ROOT / "out"
    allrows = []
    for f in sorted(out_dir.glob("20??-??-??.json")):
        rep = read_json(f, {})
        if not rep.get("ngay"):
            continue
        # cần đủ 5 phiên sau ngày tin (≈ 7 ngày lịch) mới chấm
        if datetime.fromisoformat(rep["ngay"]).date() > (end - timedelta(days=7)).date():
            continue
        allrows += score_day(rep, end)
    res = {"cap_nhat": end.isoformat(timespec="minutes"), "tong_ket": summarize(allrows),
           "chi_tiet": allrows[-300:],
           "ghi_chu": "Chấm trên giá thật; trung tính không chấm; mẫu < 30 thì chưa kết luận được gì."}
    write_json(out_dir / "cham_diem.json", res)
    print(res["tong_ket"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
