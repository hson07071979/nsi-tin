"""Chỉ báo kỹ thuật tính sẵn bằng code (AI không tự tính số — chỉ đọc số đã tính).

Mỗi mã cho ra: vị trí so với MA10/20/50/200, khối lượng so TB20, đỉnh/đáy 20/60/250 phiên,
các mốc hỗ trợ/kháng cự gần nhất (đỉnh/đáy cục bộ, có đếm số lần chạm), chân các cây nến phát động gần đây,
sức mạnh tương đối so VN-Index, chuỗi phiên nằm dưới MA10.
"""
from __future__ import annotations

from statistics import mean


def _ma(c: list[float], n: int) -> float | None:
    return round(mean(c[-n:]), 2) if len(c) >= n else None


def _pct(a, b):
    return None if a is None or b in (None, 0) else round((a / b - 1) * 100, 2)


def pivots(bars: list[dict], w: int = 5, look: int = 250) -> tuple[list[dict], list[dict]]:
    """Đáy/đỉnh cục bộ: thấp/cao nhất trong cửa sổ ±w phiên."""
    b = bars[-look:]
    lows, highs = [], []
    for i in range(w, len(b) - w):
        seg = b[i - w:i + w + 1]
        if b[i]["l"] == min(x["l"] for x in seg):
            lows.append({"gia": b[i]["l"], "ngay": b[i]["d"]})
        if b[i]["h"] == max(x["h"] for x in seg):
            highs.append({"gia": b[i]["h"], "ngay": b[i]["d"]})
    return lows, highs


def _gom(levels: list[dict], tol: float = 0.015) -> list[dict]:
    """Gom các mốc sát nhau (±1,5%) thành vùng, đếm số lần chạm; giữ ngày gần nhất."""
    out: list[dict] = []
    for lv in sorted(levels, key=lambda x: x["gia"]):
        if out and abs(lv["gia"] / out[-1]["gia"] - 1) <= tol:
            g = out[-1]
            g["cham"] += 1
            g["tu"] = min(g["tu"], lv["gia"])
            g["den"] = max(g["den"], lv["gia"])
            g["gia"] = round((g["tu"] + g["den"]) / 2, 2)
            g["ngay_gan_nhat"] = max(g["ngay_gan_nhat"], lv["ngay"])
        else:
            out.append({"gia": lv["gia"], "tu": lv["gia"], "den": lv["gia"], "cham": 1, "ngay_gan_nhat": lv["ngay"]})
    return out


def launch_candles(bars: list[dict], min_pct: float, look: int = 120, vol_x: float = 1.3) -> list[dict]:
    """Cây nến phát động: tăng >= min_pct với khối lượng >= vol_x × TB20. Chân nến = giá thấp nhất phiên đó."""
    out = []
    n = len(bars)
    for i in range(max(21, n - look), n):
        prev = bars[i - 1]["c"]
        if not prev:
            continue
        pct = (bars[i]["c"] / prev - 1) * 100
        tb20 = mean(x["v"] for x in bars[i - 20:i]) or 0
        if pct >= min_pct and tb20 and bars[i]["v"] >= vol_x * tb20:
            out.append({"ngay": bars[i]["d"], "chan": bars[i]["l"], "pct": round(pct, 2),
                        "kl_x_tb20": round(bars[i]["v"] / tb20, 2)})
    return out[-3:]


def analyse(bars: list[dict], index_bars: list[dict] | None = None, is_index: bool = False) -> dict:
    if len(bars) < 21:
        return {"thieu_lich_su": True, "so_phien": len(bars)}
    c = [x["c"] for x in bars]
    last = bars[-1]
    close = last["c"]
    prev = bars[-2]["c"]
    v20 = mean(x["v"] for x in bars[-21:-1]) or 0
    d: dict = {
        "ngay": last["d"], "dong_cua": close, "pct_phien": _pct(close, prev),
        "kl_x_tb20": round(last["v"] / v20, 2) if v20 else None,
        "pct_5p": _pct(close, c[-6]) if len(c) > 5 else None,
        "pct_20p": _pct(close, c[-21]) if len(c) > 20 else None,
        "pct_60p": _pct(close, c[-61]) if len(c) > 60 else None,
    }
    for n in (10, 20, 50, 200):
        m = _ma(c, n)
        d[f"ma{n}"] = m
        d[f"so_ma{n}_pct"] = _pct(close, m)
    # MA đang dốc lên hay xuống (so 5 phiên trước)
    for n in (20, 50):
        if len(c) >= n + 5:
            d[f"ma{n}_doc"] = "lên" if mean(c[-n:]) > mean(c[-n - 5:-5]) else "xuống"
    # chuỗi phiên đóng cửa dưới MA10
    streak = 0
    for i in range(len(c) - 1, 9, -1):
        if c[i] < mean(c[i - 9:i + 1]):
            streak += 1
        else:
            break
    d["so_phien_duoi_ma10"] = streak
    for n, k in ((20, "20p"), (60, "60p"), (250, "250p")):
        seg = bars[-n:]
        lo = min(seg, key=lambda x: x["l"])
        hi = max(seg, key=lambda x: x["h"])
        d[f"day_{k}"] = {"gia": lo["l"], "ngay": lo["d"], "cach_pct": _pct(close, lo["l"])}
        d[f"dinh_{k}"] = {"gia": hi["h"], "ngay": hi["d"], "cach_pct": _pct(close, hi["h"])}
    lows, highs = pivots(bars)
    sup = [z for z in _gom(lows) if z["den"] < close]
    res = [z for z in _gom(highs) if z["tu"] > close]
    d["ho_tro_gan"] = [dict(z, cach_pct=_pct(close, z["gia"])) for z in sorted(sup, key=lambda z: -z["gia"])[:3]]
    d["khang_cu_gan"] = [dict(z, cach_pct=_pct(close, z["gia"])) for z in sorted(res, key=lambda z: z["gia"])[:3]]
    lc = launch_candles(bars, 1.5 if is_index else 4.0, vol_x=1.1 if is_index else 1.3)
    for x in lc:
        x["da_gay"] = close < x["chan"]
    d["nen_phat_dong"] = lc
    # khoảng trống giá chưa lấp trong 60 phiên (gap xuống/lên)
    gaps = []
    for i in range(max(1, len(bars) - 60), len(bars)):
        a, b = bars[i - 1], bars[i]
        if b["l"] > a["h"]:
            vung = (a["h"], b["l"])
            if min(x["l"] for x in bars[i:]) > a["h"]:
                gaps.append({"ngay": b["d"], "loai": "gap lên chưa lấp", "tu": vung[0], "den": vung[1]})
        elif b["h"] < a["l"]:
            if max(x["h"] for x in bars[i:]) < a["l"]:
                gaps.append({"ngay": b["d"], "loai": "gap xuống chưa lấp", "tu": b["h"], "den": a["l"]})
    d["gap"] = gaps[-2:]
    if index_bars and not is_index and len(index_bars) > 21:
        ic = {x["d"]: x["c"] for x in index_bars}
        def rs(n):
            if len(bars) <= n:
                return None
            d0 = bars[-1 - n]["d"]
            if d0 not in ic or last["d"] not in ic:
                return None
            return round(_pct(close, bars[-1 - n]["c"]) - _pct(ic[last["d"]], ic[d0]), 2)
        d["rs_5p"] = rs(5)
        d["rs_20p"] = rs(20)
    return d


def liquidity(days: list[dict]) -> dict:
    """Thanh khoản thực (khớp lệnh) so phiên trước / TB5 / TB20. days: mới nhất trước."""
    k = [x["gt_khop"] for x in days if x.get("gt_khop")]
    if not k:
        return {}
    today = days[0]
    tb5 = round(mean(k[1:6]), 0) if len(k) > 5 else None
    tb20 = round(mean(k[1:21]), 0) if len(k) > 20 else None
    tong = today.get("gt_tong") or 0
    tt = today.get("gt_thoa_thuan") or 0
    return {
        "gt_tong": tong, "gt_thoa_thuan": tt, "gt_khop": today.get("gt_khop"),
        "ty_trong_thoa_thuan_pct": round(tt / tong * 100, 1) if tong else None,
        "khop_phien_truoc": k[1] if len(k) > 1 else None,
        "khop_tb5": tb5, "khop_tb20": tb20,
        "khop_so_tb20": round(today["gt_khop"] / tb20, 2) if tb20 and today.get("gt_khop") else None,
        "nam_phien_truoc": [{"ngay": x["date"], "khop": x["gt_khop"], "thoa_thuan": x["gt_thoa_thuan"]}
                                  for x in days[1:6]],
    }
