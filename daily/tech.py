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


def _vol_nodes(bars: list[dict], look: int = 120, bins: int = 40) -> list[dict]:
    """Vùng khối lượng lớn (volume-by-price) từ nến ngày: rải khối lượng mỗi phiên đều trên [thấp, cao],
    lấy các đỉnh cục bộ của phân bố ≥ 1,3 lần mức trung bình. Đây là nơi nhiều người đã mua/bán → hay thành hỗ trợ/kháng cự."""
    b = bars[-look:]
    lo, hi = min(x["l"] for x in b), max(x["h"] for x in b)
    if hi <= lo:
        return []
    step = (hi - lo) / bins
    hist = [0.0] * bins
    for x in b:
        i0 = min(bins - 1, int((x["l"] - lo) / step))
        i1 = min(bins - 1, int((x["h"] - lo) / step))
        share = (x["v"] or 0) / (i1 - i0 + 1)
        for i in range(i0, i1 + 1):
            hist[i] += share
    avg = sum(hist) / bins or 1
    out = []
    for i in range(bins):
        left = hist[i - 1] if i else 0
        right = hist[i + 1] if i < bins - 1 else 0
        if hist[i] >= 1.3 * avg and hist[i] >= left and hist[i] >= right:
            out.append({"gia": round(lo + (i + 0.5) * step, 2), "suc": round(hist[i] / avg, 2)})
    return out


def vung_ho_tro_khang_cu(bars: list[dict], close: float, mas: dict, tol: float = 0.015,
                         extra: list[dict] | None = None) -> tuple[list, list, dict | None]:
    """Hỗ trợ / kháng cự dạng VÙNG, chấm điểm độ mạnh (Sơn chốt 12/10: phân tích dựa vào hỗ trợ–kháng cự).

    Nguồn gom chung (một đỉnh cũ nằm dưới giá thì thành hỗ trợ — đổi vai):
      - đỉnh/đáy cục bộ ±3 phiên và ±8 phiên trong 250 phiên (±8 nặng gấp đôi; 60 phiên gần nhất nặng 1,5 lần)
      - vùng khối lượng lớn 120 phiên
      - MA50 / MA200 nằm trong vùng thì cộng điểm (hợp lưu)
    Điểm → độ mạnh 1–5. Mỗi phía trả tối đa 3 vùng gần giá nhất có độ mạnh ≥ 2."""
    b = bars[-250:]
    n = len(b)
    pts = []
    for w, wt in ((3, 1.0), (8, 2.0)):
        for i in range(w, n - w):
            seg = b[i - w:i + w + 1]
            rec = 1.5 if i >= n - 60 else 1.0
            if b[i]["l"] == min(x["l"] for x in seg):
                pts.append({"gia": b[i]["l"], "ngay": b[i]["d"], "loai": "đáy cũ", "w": wt * rec})
            if b[i]["h"] == max(x["h"] for x in seg):
                pts.append({"gia": b[i]["h"], "ngay": b[i]["d"], "loai": "đỉnh cũ", "w": wt * rec})
    for vn in _vol_nodes(bars):
        pts.append({"gia": vn["gia"], "ngay": "", "loai": "vùng khối lượng lớn", "w": 1.0 + vn["suc"]})
    # đáy/đỉnh 20 phiên (bắt cả đáy vừa tạo mấy phiên gần đây mà cửa sổ ±w chưa xác nhận)
    lo20 = min(b[-20:], key=lambda x: x["l"])
    hi20 = max(b[-20:], key=lambda x: x["h"])
    pts.append({"gia": lo20["l"], "ngay": lo20["d"], "loai": "đáy 20 phiên", "w": 1.5})
    pts.append({"gia": hi20["h"], "ngay": hi20["d"], "loai": "đỉnh 20 phiên", "w": 1.5})
    # chân các cây nến tăng mạnh có khối lượng (nơi tiền vào) — chỉ là MỘT nguồn của vùng hỗ trợ
    for x in extra or []:
        pts.append({"gia": x["chan"], "ngay": x["ngay"], "loai": "chân nến tăng mạnh", "w": 1.5})
    pts.sort(key=lambda x: x["gia"])
    zones: list[dict] = []
    for p in pts:
        z = zones[-1] if zones else None
        # vùng không được kéo dài quá 2×tol (tránh nối chuỗi thành một vùng khổng lồ)
        if z and p["gia"] <= z["den"] * (1 + tol) and p["gia"] <= z["tu"] * (1 + 2 * tol):
            z["den"] = max(z["den"], p["gia"])
            z["diem"] += p["w"]
            z["nguon"].add(p["loai"])
            if p["loai"] != "vùng khối lượng lớn":
                z["cham"] += 1
                z["ngay_gan_nhat"] = max(z["ngay_gan_nhat"], p["ngay"])
        else:
            zones.append({"tu": p["gia"], "den": p["gia"], "diem": p["w"], "nguon": {p["loai"]},
                          "cham": 0 if p["loai"] == "vùng khối lượng lớn" else 1, "ngay_gan_nhat": p["ngay"]})
    for z in zones:
        for k in ("ma50", "ma200"):
            m = mas.get(k)
            if m and z["tu"] * (1 - tol) <= m <= z["den"] * (1 + tol):
                z["diem"] += 1.5
                z["nguon"].add(k.upper())
        z["gia"] = round((z["tu"] + z["den"]) / 2, 2)
        z["tu"], z["den"] = round(z["tu"], 2), round(z["den"], 2)
        z["do_manh"] = 1 if z["diem"] < 2.5 else 2 if z["diem"] < 4 else 3 if z["diem"] < 6 else 4 if z["diem"] < 9 else 5
        z["nguon"] = sorted(z["nguon"])
        z["cach_pct"] = _pct(close, z["gia"])
        del z["diem"]
    # giữ vùng mạnh (≥2 sao); vùng yếu chỉ giữ nếu là vùng gần giá nhất (trong 5%) để không bỏ sót mốc sát chân
    def chon(ds, gan_truoc):
        ds = sorted(ds, key=gan_truoc)
        out = [z for z in ds if z["do_manh"] >= 2]
        if ds and ds[0] not in out and abs(ds[0]["cach_pct"] or 99) <= 5:
            out = [ds[0]] + out
        return out[:3]
    sup = chon([z for z in zones if z["den"] < close * 0.998], lambda z: -z["gia"])
    res = chon([z for z in zones if z["tu"] > close * 1.002], lambda z: z["gia"])
    # vùng đang chứa giá đóng cửa (giá đang "test" vùng này) — báo riêng, không bỏ sót
    trong = [z for z in zones if z["tu"] <= close * 1.002 and z["den"] >= close * 0.998]
    vung_dang_test = max(trong, key=lambda z: z["do_manh"]) if trong else None
    return sup, res, vung_dang_test


def bollinger(c: list[float], n: int = 20, k: float = 2.0) -> dict | None:
    """Dải Bollinger (20, 2) quanh MA20. Có vùng hỗ trợ/kháng cự cấu trúc thì BB là bổ trợ; KHÔNG nhận diện được vùng
    thì dải BB được dùng làm hỗ trợ/kháng cự động (Sơn chốt 12/10). Cần ≥20 phiên; 'bóp chặt' cần ≥140 phiên."""
    if len(c) < n:
        return None
    def band(seg):
        m = mean(seg)
        sd = (sum((x - m) ** 2 for x in seg) / len(seg)) ** 0.5
        return m, m + k * sd, m - k * sd
    m, up, lo = band(c[-n:])
    bw = (up - lo) / m if m else None
    hist_bw = []
    for i in (range(len(c) - 120, len(c)) if len(c) >= n + 120 else ()):
        mm, uu, ll = band(c[i - n + 1:i + 1])
        if mm:
            hist_bw.append((uu - ll) / mm)
    rank = sum(1 for x in hist_bw if x <= bw) / len(hist_bw) if hist_bw and bw is not None else None
    return {"tren": round(up, 2), "giua": round(m, 2), "duoi": round(lo, 2),
            "pct_b": round((c[-1] - lo) / (up - lo), 2) if up > lo else None,
            "do_rong_pct": round(bw * 100, 2) if bw is not None else None,
            "bop_chat": bool(rank is not None and rank <= 0.1)}


def bb_lam_ho_tro_khang_cu(sup: list, res: list, bb: dict | None, close: float, gan_pct: float = 7.0,
                           dang: dict | None = None):
    """Không có vùng hỗ trợ (hoặc kháng cự) ≥2 sao trong phạm vi gan_pct% → vẽ dải Bollinger làm mốc động cho phía đó.
    Dải dưới/giữa nằm dưới giá → hỗ trợ; dải giữa/trên nằm trên giá → kháng cự. Trả (sup, res, dùng_bb)."""
    dung = {"ho_tro": False, "khang_cu": False}
    if not bb or not close:
        return sup, res, dung
    ten = {"duoi": "dải Bollinger dưới", "giua": "dải Bollinger giữa (MA20)", "tren": "dải Bollinger trên"}

    def z(k):
        g = bb[k]
        return {"gia": g, "tu": g, "den": g, "cham": 0, "ngay_gan_nhat": None, "nguon": [ten[k]],
                "do_manh": 2, "cach_pct": _pct(g, close), "bb": True}

    def ro(ds):
        return any(x.get("do_manh", 0) >= 2 and abs(x.get("cach_pct") or 99) <= gan_pct for x in ds)

    co_vung_test = bool(dang and dang.get("do_manh", 0) >= 2)   # giá đang test vùng rõ → phía hỗ trợ đã có mốc
    if not ro(sup) and not co_vung_test:
        them = [z(k) for k in ("giua", "duoi") if bb[k] < close * 0.998]
        if them:
            sup = sorted(them + list(sup), key=lambda x: -x["gia"])[:3]
            dung["ho_tro"] = True
    if not ro(res):
        them = [z(k) for k in ("giua", "tren") if bb[k] > close * 1.002]
        if them:
            res = sorted(them + list(res), key=lambda x: x["gia"])[:3]
            dung["khang_cu"] = True
    return sup, res, dung


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
    lc = launch_candles(bars, 1.5 if is_index else 4.0, vol_x=1.1 if is_index else 1.3)
    for x in lc:
        x["da_gay"] = close < x["chan"]
    d["nen_phat_dong"] = lc
    sup, res, dang = vung_ho_tro_khang_cu(bars, close, {"ma50": d.get("ma50"), "ma200": d.get("ma200")},
                                          tol=0.008 if is_index else 0.015, extra=lc)
    bb = bollinger(c)
    sup, res, d["sr_tu_bb"] = bb_lam_ho_tro_khang_cu(sup, res, bb, close, dang=dang)
    d["ho_tro_gan"], d["khang_cu_gan"], d["vung_dang_test"] = sup, res, dang
    d["bollinger"] = bb
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
