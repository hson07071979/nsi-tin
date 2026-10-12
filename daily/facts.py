"""Dựng bộ FACT của phiên — mô hình dữ liệu chung cho phân tích, script và trang /daily.

Nối 3 nguồn theo cùng khóa (ngày, mã, ngành, biến vĩ mô):
  1. Phiên VN (VNDirect)                      → chỉ số, breadth, thanh khoản thực, khối ngoại, tự doanh, đóng góp điểm,
                                                 ngành, rổ mã + mã nổi bật (kỹ thuật tính sẵn, định giá)
  2. Liên thị trường lúc chạy (Yahoo)        → dầu, DXY, lợi suất, Mỹ, châu Á, hàng hóa
  3. Bản tin sáng nsi-tin (out/latest.json)  → số vĩ mô 7h, cờ vĩ mô mềm, tin WEB đã xác minh (KHÔNG lấy Zalo)
  + Đèn thị trường NSI (nếu đọc được)

Mọi số ở đây là FACT tính từ dữ liệu. AI chỉ diễn giải, không được tự tính số mới.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

from tin import nsi_context
from tin.common import ROOT, read_json

from . import sources, store, tech


def _round(x, n=2):
    return None if x is None else round(x, n)


def basket(cfg: dict) -> list[tuple[str, str]]:
    out, seen = [], set()
    for g in cfg["ro"]:
        for m in g["ma"]:
            if m not in seen:
                out.append((m, g["nhom"]))
                seen.add(m)
    return out


def contributions(prices: dict, ratios: dict, idx_prev_close: float, idx_change: float) -> dict:
    """Đóng góp điểm ước tính theo vốn hóa (VN-Index tính theo vốn hóa), chuẩn hóa về đúng số điểm thật."""
    raw, base = {}, 0.0
    for m, p in prices.items():
        if p["san"] != "HOSE":
            continue
        sh = (ratios.get(m) or {}).get("cp_luu_hanh")
        ref, cl = p.get("tham_chieu"), p.get("close_raw")
        if not sh or not ref or cl is None:
            continue
        base += ref * sh
        raw[m] = (cl - ref) * sh
    if not base or not raw:
        return {}
    pts = {m: v / base * idx_prev_close for m, v in raw.items()}
    tot = sum(pts.values())
    scale = idx_change / tot if tot and abs(tot) > 0.05 and idx_change is not None else 1.0
    if not 0.5 <= abs(scale) <= 2.0:      # lệch quá xa → không chuẩn hóa, ghi chú
        scale = 1.0
    pts = {m: v * scale for m, v in pts.items()}
    return pts


def sector_table(prices: dict, ratios: dict, sector: dict, fstocks: dict) -> list[dict]:
    agg: dict[str, dict] = {}
    for m, p in prices.items():
        sec = sector.get(m)
        ref, cl = p.get("tham_chieu"), p.get("close_raw")
        if not sec or not ref or cl is None:
            continue
        sh = (ratios.get(m) or {}).get("cp_luu_hanh") or 0
        a = agg.setdefault(sec, {"nganh": sec, "w0": 0.0, "w1": 0.0, "gt": 0.0, "tang": 0, "giam": 0, "nn": 0.0})
        a["w0"] += ref * sh
        a["w1"] += cl * sh
        a["gt"] += p.get("gt_khop") or 0
        a["tang"] += cl > ref
        a["giam"] += cl < ref
        a["nn"] += fstocks.get(m, 0.0)
    out = []
    for a in agg.values():
        if a["gt"] < 20 or not a["w0"]:
            continue
        out.append({"nganh": a["nganh"], "pct": round((a["w1"] / a["w0"] - 1) * 100, 2), "gt_khop": round(a["gt"]),
                     "tang": a["tang"], "giam": a["giam"], "nn_rong": round(a["nn"], 1)})
    return sorted(out, key=lambda x: -x["pct"])


def collect(today: date, cfg: dict, log: list[str]) -> dict:
    t = today.isoformat()
    idx_days = sources.vnindex_days(sources.days_ago(today, 50))
    if not idx_days:
        return {"loi_nguon": True, "ngay": t}
    if idx_days[0]["date"] != t:
        return {"khong_phien": True, "ngay": t, "phien_gan_nhat": idx_days[0]["date"] if idx_days else None}
    s0 = idx_days[0]
    prev_session = idx_days[1]["date"] if len(idx_days) > 1 else None
    prev_close = idx_days[1]["close"] if len(idx_days) > 1 else None
    thieu: list[str] = []

    # ---- giá từng mã + định giá + số cổ phiếu
    prices = sources.stock_prices_on(t)
    if not prices:
        thieu.append("giá từng mã (VNDirect stock_prices)")
    hose = sorted(m for m, p in prices.items() if p["san"] == "HOSE")
    bk = basket(cfg)
    ratios = sources.ratios(sorted(set(hose) | {m for m, _ in bk}))
    if not ratios:
        thieu.append("định giá / số cổ phiếu (VNDirect ratios)")

    # ---- khối ngoại
    fi = sources.foreign_index(f"{today.year}-01-01")
    f_today = next((x for x in fi if x["date"] == t), None)
    fstocks = sources.foreign_stocks(t) if f_today else {}
    ngoai = {}
    if f_today:
        ms = sources.month_start(today)
        ngoai = {
            "phien": f_today,
            "luy_ke_thang": round(sum(x["rong"] or 0 for x in fi if x["date"] >= ms), 1),
            "so_phien_thang": sum(1 for x in fi if x["date"] >= ms),
            "luy_ke_nam": round(sum(x["rong"] or 0 for x in fi), 1),
            "nam_phien_truoc": [{"ngay": x["date"], "rong": x["rong"]} for x in fi[1:6]],
            "mua_rong_nhieu": sorted(({"ma": m, "rong": v} for m, v in fstocks.items() if v > 0), key=lambda x: -x["rong"])[:6],
            "ban_rong_nhieu": sorted(({"ma": m, "rong": v} for m, v in fstocks.items() if v < 0), key=lambda x: x["rong"])[:6],
        }
    else:
        thieu.append("khối ngoại phiên hôm nay (VNDirect chưa công bố lúc chạy)")

    # ---- tự doanh (thường công bố muộn — có thì dùng, không có thì ghi phiên gần nhất)
    pi = sources.prop_index(25)
    tu_doanh = {}
    if pi:
        p0 = pi[0]
        ps = sources.prop_stocks(p0["date"])
        tu_doanh = {
            "phien": p0, "la_phien_hom_nay": p0["date"] == t,
            "luy_ke_5_phien": round(sum(x["rong"] or 0 for x in pi[:5]), 1),
            "mua_rong_nhieu": sorted(({"ma": m, "rong": v} for m, v in ps.items() if v > 0), key=lambda x: -x["rong"])[:5],
            "ban_rong_nhieu": sorted(({"ma": m, "rong": v} for m, v in ps.items() if v < 0), key=lambda x: x["rong"])[:5],
        }
        if p0["date"] != t:
            thieu.append(f"tự doanh phiên hôm nay (mới có tới phiên {p0['date']})")
    else:
        thieu.append("tự doanh")

    # ---- đóng góp điểm + ngành
    pts = contributions(prices, ratios, prev_close, s0.get("change")) if prev_close else {}
    vin = cfg.get("nhom_vin", [])
    dong_gop = {}
    if pts:
        top = sorted(pts.items(), key=lambda kv: kv[1])
        vin_sum = sum(pts.get(m, 0) for m in vin)
        dong_gop = {
            "duong": [{"ma": m, "diem": round(v, 2)} for m, v in reversed(top[-6:]) if v > 0],
            "am": [{"ma": m, "diem": round(v, 2)} for m, v in top[:6] if v < 0],
            "nhom_vin": round(vin_sum, 2),
            "nhom_vin_chi_tiet": {m: round(pts.get(m, 0), 2) for m in vin if m in pts},
            "phan_con_lai": round((s0.get("change") or 0) - vin_sum, 2),
            "ghi_chu": "ước tính theo vốn hóa đầy đủ, đã chuẩn hóa về số điểm thật; lệch nhẹ so với số HOSE công bố",
        }
    else:
        thieu.append("đóng góp điểm (thiếu số cổ phiếu lưu hành)")
    sector = read_json(ROOT / "config" / "daily_sector.json", {})
    nganh = sector_table(prices, ratios, sector, fstocks) if prices else []

    # ---- VN-Index: nến + kỹ thuật
    ibars = store.index_bars(t, idx_days, keep=cfg.get("lich_su_phien", 300))
    idx_tech = tech.analyse(ibars, is_index=True)

    # ---- breadth HOSE: lấy số HOSE công bố, đối chiếu đếm tay
    dem = {"tang": 0, "giam": 0, "dung": 0}
    for m in hose:
        p = prices[m]
        if p.get("close_raw") is None or not p.get("tham_chieu") or not p.get("kl"):
            continue
        k = "tang" if p["close_raw"] > p["tham_chieu"] else "giam" if p["close_raw"] < p["tham_chieu"] else "dung"
        dem[k] += 1

    # ---- rổ mã + mã nổi bật
    ly_do: list[str] = []
    noi_bat = _notable(prices, fstocks, pts, {m for m, _ in bk}, cfg.get("ma_noi_bat_toi_da", 10))
    syms = bk + [(m, sector.get(m, "Khác") + " (nổi bật hôm nay)") for m in noi_bat]
    link = cfg.get("link_chi_tiet_ma", "/index.html?ma={ma}#bieudo")
    pi_ma = sources.prop_stocks(t) if tu_doanh.get("la_phien_hom_nay") else {}
    ma_rows = []
    keep = cfg.get("lich_su_phien", 300)
    with ThreadPoolExecutor(6) as ex:
        all_bars = list(ex.map(lambda mn: store.update(mn[0], t, prev_session, prices.get(mn[0]), keep=keep, ly_do=ly_do),
                               syms))
    for (m, nhom), bars in zip(syms, all_bars):
        p = prices.get(m)
        if not bars:
            continue
        a = tech.analyse(bars, ibars)
        r = ratios.get(m) or {}
        row = {"ma": m, "nhom": nhom, "san": (p or {}).get("san"), "link": link.format(ma=m),
               "gt_khop": (p or {}).get("gt_khop"), "tran_san": _tran_san(p),
               "pe": _round(r.get("pe"), 1), "pb": _round(r.get("pb"), 2),
               "cao_52t": r.get("cao_52t"), "thap_52t": r.get("thap_52t"),
               "nn_rong": fstocks.get(m), "tu_doanh_rong": pi_ma.get(m), "diem_dong_gop": _round(pts.get(m), 2),
               **a}
        if row.get("cao_52t") and row["cao_52t"] > 1000:      # VNDirect trả 52 tuần theo đồng
            row["cao_52t"] = round(row["cao_52t"] / 1000, 2)
            row["thap_52t"] = round((row["thap_52t"] or 0) / 1000, 2)
        ma_rows.append(row)
    if ly_do:
        log.extend(ly_do)

    # ---- liên thị trường + nsi-tin + đèn NSI
    the_gioi = sources.world(cfg["the_gioi"])
    tin_sang = _nsi_tin(t)
    nsi = nsi_context.load()

    return {
        "ngay": t, "luc_lay": s0.get("time"),
        "vnindex": {
            "dong_cua": s0["close"], "diem": _round(s0.get("change"), 2), "pct": _round(s0.get("pct"), 2),
            "mo": s0.get("open"), "cao": s0.get("high"), "thap": s0.get("low"), "phien_truoc": prev_close,
            "kl_trieu_cp": _round((s0.get("kl") or 0) / 1e6, 1),
            "ky_thuat": idx_tech,
        },
        "breadth_hose": {"tang": s0.get("tang"), "giam": s0.get("giam"), "dung": s0.get("dung"),
                         "tran": s0.get("tran"), "san": s0.get("san"), "dem_doi_chieu": dem},
        "thanh_khoan_hose": tech.liquidity(idx_days),
        "khoi_ngoai": ngoai, "tu_doanh": tu_doanh, "dong_gop_diem": dong_gop,
        "nganh": nganh, "ma": ma_rows,
        "the_gioi": the_gioi, "khong_co_nguon": cfg.get("khong_co_nguon_mien_phi", []),
        "ban_tin_sang": tin_sang, "den_nsi": nsi,
        "thieu_du_lieu": thieu,
    }


def _tran_san(p):
    if not p or p.get("close_raw") is None:
        return None
    if p.get("tran") and p["close_raw"] >= p["tran"]:
        return "TRẦN"
    if p.get("san_gia") and p["close_raw"] <= p["san_gia"]:
        return "SÀN"
    return None


def _notable(prices: dict, fstocks: dict, pts: dict, exclude: set, k: int) -> list[str]:
    cand: dict[str, float] = {}
    for m, p in prices.items():
        if m in exclude or len(m) != 3 or (p.get("gt_khop") or 0) < 20:
            continue
        pct = p.get("pct") or 0
        sc = 0.0
        if abs(pct) >= 3:
            sc += abs(pct) * (p["gt_khop"] ** 0.5)
        if _tran_san(p):
            sc += 50 + p["gt_khop"] ** 0.5
        if abs(fstocks.get(m, 0)) >= 30:
            sc += abs(fstocks[m])
        if abs(pts.get(m, 0)) >= 0.5:
            sc += 30 * abs(pts[m])
        if sc:
            cand[m] = sc
    return [m for m, _ in sorted(cand.items(), key=lambda kv: -kv[1])[:k]]


def _nsi_tin(today: str) -> dict:
    """Bản tin sáng cùng ngày (cùng repo). Chỉ lấy vĩ mô + tin WEB; tin Zalo không bao giờ đi vào nsi-daily."""
    j = read_json(ROOT / "out" / f"{today}.json", None)
    if not j:
        return {"co": False, "ghi_chu": "chưa có bản tin sáng hôm nay"}
    vm = j.get("vi_mo") or {}
    pb = vm.get("playbook") or {}
    topics = []
    for tp in ((j.get("web") or {}).get("topics") or [])[:10]:
        topics.append({k: tp.get(k) for k in ("tieu_de", "mot_dong", "vi_sao_quan_trong", "vi_mo_to_vi_mo", "nganh",
                                               "ma_lien_quan", "danh_gia", "muc_do", "su_kien_hay_nhan_dinh", "xac_minh")
                       if tp.get(k) not in (None, "", [])})
    return {
        "co": True, "chup_luc": j.get("bat_dau_luc"),
        "so_lieu_7h": {k: v for k, v in (vm.get("so_lieu") or {}).items()
                       if k in ("lnh_on", "lnh_on_chg5_bp", "lnh_on_chg20_bp", "usdvnd", "usdvnd_chg20_pct", "dxy",
                                "dxy_chg20_pct", "us10y", "us10y_chg20_bp", "brent", "brent_chg20_pct", "vix")},
        "co_vi_mo_bat": [{"id": f.get("id"), "muc": f.get("muc_ten"), "y_nghia": f.get("doc")}
                         for f in (pb.get("flags") or []) if f.get("trang_thai") == "bat"],
        "co_thieu_du_lieu": [f.get("id") for f in (pb.get("flags") or []) if f.get("trang_thai") == "thieu_du_lieu"],
        "tin_web": topics,
    }


def prev_trading_day(today: date) -> date:
    d = today - timedelta(days=1)
    while d.weekday() >= 5:
        d -= timedelta(days=1)
    return d
