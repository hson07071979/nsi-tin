"""Dựng bộ slide PPTX cho video Nguyen Son Finance từ bản NSI Daily Market — không gọi AI.

Luồng (Sơn chốt 13/10/2026):
  15:20 daily_market.yml: số liệu + Gemini viết 1 bản (phân tích + lời thoại) → out/daily/<ngày>.json
        → bước này dựng ngay bản PPT NHÁP từ bản Gemini.
  Tối:  Claude kiểm số liệu/logic trong chat, chỉ sửa câu sai (không viết lại văn), ghi out/daily/claude/<ngày>.json
        → slides.yml tự chạy lại bước này → PPT CHÍNH THỨC.
  PPT lên Cloudflare Workers KV (slides/kv.py); trang quản trị /daily có nút "Tải PPT".

Chạy tay:  python -m slides.make --ngay 2026-10-13 [--nen-dir thư_mục_nến_json] [--khong-upload]
"""
from __future__ import annotations

import argparse
import copy
import json
import re
import subprocess
import sys
from pathlib import Path

from tin.common import ROOT

from . import charts

OUT = ROOT / "out" / "daily"
SL = Path(__file__).resolve().parent
UP, DOWN, SILVER, WATER = "26C281", "EF5466", "C5D0DE", "4FC3F7"

META = {
    "brand": "NGUYEN SON FINANCE",
    "youtube": "@NguyenSonFinance",
    "tiktok": "@NguyenSonFinance",
    "website": "nguyễnsơnfinance.com.vn",
    "contact": "Tư vấn Mr. Sơn · 0559562157",
    "ssi_id": "8B0327",
    "disclaimer": "Nội dung rà soát thị trường, không phải khuyến nghị mua bán",
}
REGIME_VI = {
    "risk-on/trend": "Xu hướng tăng, tiền vào rộng", "rotation/divergence": "Phân hóa, xoay vòng",
    "distribution": "Phân phối", "capitulation": "Bán tháo", "technical rebound": "Hồi kỹ thuật",
    "bottoming process": "Dò đáy",
}


# ------------------------------------------------------------------ chữ & số
def so(x, n: int = 1, dau: bool = False) -> str:
    if x is None:
        return "—"
    s = f"{abs(x):,.{n}f}".replace(",", "#").replace(".", ",").replace("#", ".")
    if x < 0:
        return "−" + s
    return ("+" if dau and x > 0 else "") + s


def pct(x) -> str:
    return so(x, 2, dau=True) + "%" if x is not None else "—"


def gia(x) -> str:
    """Giá cổ phiếu nghìn đồng: 32.95 → '32,95'; 35.0 → '35,0'; 222.0 → '222,0'."""
    if x is None:
        return "—"
    s = so(x, 2) if x < 100 else so(x, 1)
    while s.endswith("0") and len(s.split(",")[-1]) > 1:
        s = s[:-1]
    return s


def mau(s: str) -> str:
    s = str(s).strip()
    return UP if s.startswith("+") else DOWN if s.startswith(("−", "-")) else SILVER


_NOI_BO = [(re.compile(r"\s*\(\s*CAN\s*\)|\s*\(\s*QS\s*\)"), ""), (re.compile(r"★+"), ""),
           (re.compile(r"(hỗ trợ|kháng cự|vùng)\s*5 sao", re.I), r"\1 rất mạnh"),
           (re.compile(r"(hỗ trợ|kháng cự|vùng)\s*[34] sao", re.I), r"\1 mạnh"),
           (re.compile(r"đạt chuẩn rất mạnh tối đa trong hệ thống dữ liệu", re.I), "rất mạnh")]


def sach(s) -> str:
    """Bỏ từ nội bộ không nói với người xem: nhãn CAN/QS, sao, 'đèn NSI'."""
    s = str(s or "").strip()
    for rx, rep in _NOI_BO:
        s = rx.sub(rep, s)
    s = re.sub(r"[^.;]*đèn[^.;]*NSI[^.;]*[.;]?", "", s, flags=re.I)
    s = re.sub(r"[^.;]*hệ thống NSI[^.;]*[.;]?", "", s, flags=re.I)
    return re.sub(r"\s{2,}", " ", s).strip()


def so_vn(txt: str) -> list[float]:
    """'1.701,14–1.725,4 điểm' → [1701.14, 1725.4]."""
    out = []
    for m in re.findall(r"\d[\d.]*(?:,\d+)?", txt or ""):
        try:
            out.append(float(m.replace(".", "").replace(",", ".")))
        except ValueError:
            pass
    return out


def ngan(s, n: int = 150) -> str:
    """Rút gọn để vừa slide: ưu tiên cắt ở hết câu; danh sách thì nối bằng '; '."""
    if isinstance(s, (list, tuple)):
        s = "; ".join(str(x).strip().rstrip(".") for x in s if x) + "."
    s = sach(s)
    if len(s) <= n:
        return s
    cut = s[:n]
    k = max(cut.rfind(". "), cut.rfind("; "))
    if k >= n * 0.55:
        return cut[:k + 1] if cut[k] == "." else cut[:k].rstrip() + "."
    return cut[: n - 1].rsplit(" ", 1)[0] + "…"


# ------------------------------------------------------------------ chọn bản + áp sửa của Claude
def _set(obj, duong_dan: str, gia_tri):
    parts = re.findall(r"[^.\[\]]+|\[\d+\]", duong_dan)
    cur = obj
    for i, p in enumerate(parts):
        last = i == len(parts) - 1
        key = int(p[1:-1]) if p.startswith("[") else p
        if last:
            cur[key] = gia_tri
        else:
            cur = cur[key]


def chon_ban(day: dict, claude: dict | None) -> tuple[dict, str, list[str]]:
    bans = [b for b in day.get("ban") or [] if b.get("phan_tich")]
    if not bans:
        raise SystemExit("không có bản phân tích nào")
    goc = None
    if claude and claude.get("ban_goc"):
        goc = next((b for b in bans if claude["ban_goc"] in (b.get("cach"), b.get("nhan"))), None)
    goc = goc or next((b for b in bans if (b.get("script") or {}).get("phan")), bans[0])
    b = copy.deepcopy(goc)
    ghi = []
    if claude:
        for s in claude.get("sua_phan_tich") or []:
            try:
                _set(b["phan_tich"], s["duong_dan"], s["gia_tri"])
            except (KeyError, IndexError, TypeError) as e:
                ghi.append(f"không áp được sửa {s.get('duong_dan')}: {e}")
        for s in claude.get("sua_loi_thoai") or []:
            hit = False
            for p in (b.get("script") or {}).get("phan") or []:
                if s["tim"] in (p.get("loi_thoai") or ""):
                    p["loi_thoai"] = p["loi_thoai"].replace(s["tim"], s["thay"])
                    hit = True
            if not hit:
                ghi.append(f"không tìm thấy câu cần sửa: {s['tim'][:60]}")
    return b, ("claude" if claude else "gemini"), ghi


# ------------------------------------------------------------------ nến
def nen(sym: str, nen_dir: Path | None) -> list[dict]:
    if nen_dir:
        f = nen_dir / f"{sym}.json"
        if f.exists():
            j = json.loads(f.read_text(encoding="utf-8"))
            if isinstance(j, dict) and "t" in j:   # dạng dchart thô
                import datetime as dt  # noqa: PLC0415
                return [{"d": dt.datetime.fromtimestamp(t, dt.UTC).date().isoformat(), "o": o, "h": h, "l": lo, "c": c, "v": v}
                        for t, o, h, lo, c, v in zip(j["t"], j["o"], j["h"], j["l"], j["c"], j["v"])]
            return j
    from daily import sources, store  # noqa: PLC0415
    bars = [] if sym == "VNINDEX" else store.load(sym)
    if len(bars) < 200:
        bars = sources.dchart(sym, days=320) or bars
    return bars


def tu_tinh(bars: list[dict], is_index: bool) -> dict | None:
    from daily import tech  # noqa: PLC0415
    try:
        a = tech.analyse(bars, is_index=is_index)
    except Exception:  # noqa: BLE001
        return None
    return a if not a.get("thieu_lich_su") else None


# ------------------------------------------------------------------ nội dung
def notes_map(script: dict) -> dict[str, str]:
    m = {}
    for p in script.get("phan") or []:
        ten = (p.get("ten") or "").lower()
        key = ("hook" if "hook" in ten else "forecast" if "dự báo" in ten else "world" if "thế giới" in ten
               else "vn" if "việt nam" in ten else "distort" if "index" in ten else "tech" if "kỹ thuật" in ten
               else "scan" if "ngành" in ten else "picks" if "đáng nói" in ten else "regime" if "regime" in ten
               else "bye" if "chào" in ten else ten)
        m[key] = (m.get(key, "") + " " + (p.get("loi_thoai") or "")).strip()
    return m


def cau(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.?!])\s+(?=[A-ZĐÀ-Ỹ])", text or "") if s.strip()]


def cau_ve_ma(sym: str, pool: list[str], all_syms: set[str]) -> str:
    out, cur = [], None
    for s in pool:
        found = [t for t in all_syms if re.search(rf"\b{t}\b", s)]
        if len(found) == 1:
            cur = found[0]
        elif len(found) > 1:
            cur = sym if sym in found and s.startswith(("Với", "Mã")) else None
        elif re.match(r"^(Sang|Chuyển|Nhìn chung|Với nhóm|Nhóm|Các nhóm|Cuối cùng|Ngược lại|Các mã)", s):
            cur = None
        if cur == sym:
            out.append(s)
    return " ".join(out)


def tieu_de_ma(sym: str, cau_truc: str, ep: dict) -> str:
    if ep.get(sym):
        return f"{sym}: {ep[sym]}"
    t = re.sub(r"\([^)]*\)", "", sach(cau_truc))
    t = re.split(r"[;:]|[.,]\s", t)[0].strip()
    if len(t) > 42:
        t = t[:42].rsplit(" ", 1)[0]
    return f"{sym}: {t[:1].lower() + t[1:]}" if t else sym


TEN_NGAN = {"dxy": "DXY", "brent": "Dầu Brent", "wti": "Dầu WTI", "us10y": "US10Y", "usdvnd": "USD/VND", "gold": "Vàng"}


def _tieu_de_tg(key: str, w: dict, item: dict) -> str:
    ten = TEN_NGAN.get(key, w.get("ten") or key)
    g = w.get("gia") or 0
    nums = [x for x in so_vn(item.get("nguong") or "") if g and 0.7 < x / g < 1.3]   # bỏ số như "20 phiên"
    if nums:
        x = min(nums, key=lambda q: abs(q / g - 1))
        return f"{ten}: ngưỡng cần theo dõi {so(x, 2 if x < 1000 else 0)}"
    return ten


def build_content(day: dict, ban: dict, nguon: str, claude: dict | None, nen_dir: Path | None, work: Path) -> dict:
    fc, pt, sc = day["fc"], ban["phan_tich"], ban.get("script") or {}
    ngay = day["ngay"]
    d = ngay.split("-")
    ngay_vn = f"{d[2]}/{d[1]}/{d[0]}"
    sl = (claude or {}).get("slide") or {}
    N = notes_map(sc)
    vn, br = fc["vnindex"], fc.get("breadth_hose") or {}
    tk, kn = fc.get("thanh_khoan_hose_ty") or {}, fc.get("khoi_ngoai_ty") or {}
    dg, td = fc.get("dong_gop_diem") or {}, fc.get("tu_doanh_ty") or {}
    ma_fc = {r["ma"]: r for nh in (fc.get("ma_theo_nhom") or {}).values() for r in nh}
    charts_dir = work / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)
    C: dict = {"meta": dict(META, date=ngay_vn, date_long=f"Phiên {ngay_vn}", nguon=nguon), "notes": N}

    # 1. hook + 2. signature
    C["hook"] = {"question": sl.get("cau_hoi") or sach(sc.get("tieu_de_youtube") or ""),
                 "cards": [[so(vn["dong_cua"], 2), f"VN-Index · {so(vn['diem'], 2, True)} điểm ({pct(vn['pct'])})", mau(so(vn["diem"], 2, True))],
                           [f"{br.get('tang', '—')} / {br.get('giam', '—')}", "Mã tăng / mã giảm trên HOSE",
                            UP if (br.get("tang") or 0) >= (br.get("giam") or 0) else DOWN],
                           [so(dg.get("phan_con_lai"), 2, True), "Điểm của phần còn lại khi bỏ nhóm Vin", mau(so(dg.get("phan_con_lai"), 2, True))]]}
    sg = pt.get("signature") or {}
    C["signature"] = [ngan(sg.get("index_noi_gi"), 160), ngan(sg.get("co_phieu_noi_gi"), 160), ngan(sg.get("dong_tien_noi_gi"), 160)]

    # 3. đối chiếu dự báo
    rows = []
    for r in pt.get("doi_chieu_du_bao") or []:
        kq = (r.get("ket_qua") or "").lower()
        rows.append([ngan(r.get("noi_dung"), 110), ngan(r.get("nhan_xet"), 120), r.get("ket_qua") or "—",
                     UP if "đúng" in kq else DOWN if "sai" in kq else WATER])
    C["forecast"] = rows[:4]

    # 4–6. thế giới
    tg = fc.get("the_gioi_luc_chay") or {}
    from daily import sources  # noqa: PLC0415
    cfg = json.loads((ROOT / "config" / "daily.json").read_text(encoding="utf-8"))
    sym_of = {x["key"]: x["sym"] for x in cfg.get("the_gioi", [])}
    world = []
    for item in (pt.get("the_gioi") or [])[:4]:
        ten = (item.get("bien") or "").lower()
        key = ("dxy" if "dxy" in ten else "brent" if "brent" in ten else "wti" if "wti" in ten
               else "us10y" if ("10" in ten or "lợi suất" in ten) else "usdvnd" if "usd/vnd" in ten
               else "gold" if "vàng" in ten else None)
        w = tg.get(key) or {}
        if not key or not w.get("gia"):
            continue
        img = None
        y = None if nen_dir else sources.yahoo(sym_of.get(key, ""), "1y")
        if y and y.get("series"):
            lv = [(w["cao_3t"], "res", "Đỉnh 3 tháng")] if w.get("cao_3t") else []
            if w.get("cao_20p") and w.get("cao_3t") and abs(w["cao_20p"] / w["cao_3t"] - 1) > 0.004:
                lv.append((w["cao_20p"], "ref", "Đỉnh 20 phiên"))
            f = charts_dir / f"world_{key}.png"
            if charts.draw_line(w.get("ten") or key.upper(), y["series"], f, levels=lv, unit=w.get("don_vi", "")):
                img = str(f)
        luc = (w.get("luc_vn") or "")[11:16]
        chips = [["Trong ngày", pct(w.get("pct_1p"))], ["5 phiên", pct(w.get("pct_5p"))], ["Đỉnh 3 tháng", so(w.get("cao_3t"), 2)]]
        if key == "us10y":
            chips = [[f"Dow · {so((tg.get('dow') or {}).get('gia'), 0)}", pct((tg.get("dow") or {}).get("pct_1p"))],
                     [f"Nasdaq · {so((tg.get('nasdaq') or {}).get('gia'), 0)}", pct((tg.get("nasdaq") or {}).get("pct_1p"))],
                     ["HĐTL S&P 500", pct((tg.get("es_fut") or {}).get("pct_1p"))]]
        world.append({"key": key, "tag": f"THẾ GIỚI · {(w.get('ten') or key).upper()}",
                      "title": _tieu_de_tg(key, w, item),
                      "img": img, "big": so(w["gia"], 2 if w["gia"] < 1000 else 0), "unit": f"{w.get('don_vi', '')} · lúc {luc}",
                      "chips": chips, "chan": ngan(item.get("kenh_truyen_dan"), 130), "cross": ngan(item.get("he_qua_neu_vuot"), 140)})
    C["world"] = world

    # 7. độ rộng, 8. thanh khoản, 9. dòng tiền
    tang, giam = br.get("tang") or 0, br.get("giam") or 0
    ti = (giam / tang) if tang else None
    C["breadth"] = {"tang": tang, "dung": br.get("dung") or 0, "giam": giam, "tran": br.get("tran"), "san": br.get("san"),
                    "note": ngan(pt.get("suc_khoe_vn"), 190),
                    "head": (f"Mã giảm gấp ~{so(ti, 1)} lần mã tăng. " if ti and ti >= 1.3 else
                             f"Mã tăng gấp ~{so(tang / giam, 1)} lần mã giảm. " if giam and tang / giam >= 1.3 else "Độ rộng cân bằng. ")}
    C["liquidity"] = {"vals": [tk.get("khop_phien_truoc"), tk.get("gt_khop"), tk.get("khop_tb5"), tk.get("khop_tb20")],
                      "tong": tk.get("gt_tong"), "khop": tk.get("gt_khop"), "tt": tk.get("gt_thoa_thuan"),
                      "tt_pct": tk.get("ty_trong_thoa_thuan_pct"), "x": tk.get("khop_so_tb20"),
                      "note": ngan((cau(pt.get("thanh_khoan") or "")[-1:] or [""])[0], 120)}
    ph = kn.get("phien") or {}
    ban_r = sorted(kn.get("ban_rong_nhieu") or [], key=lambda r: r["rong"])[:5]
    mua_r = sorted(kn.get("mua_rong_nhieu") or [], key=lambda r: -r["rong"])[:3][::-1]
    tdp = td.get("phien") or {}
    C["foreign"] = {"phien": ph.get("rong"), "thang": kn.get("luy_ke_thang"), "nam": kn.get("luy_ke_nam"),
                    "labels": [r["ma"] for r in ban_r + mua_r], "vals": [r["rong"] for r in ban_r + mua_r],
                    "td1": (f"Phiên {tdp.get('date', '')[8:10]}/{tdp.get('date', '')[5:7]}: {'mua' if (tdp.get('rong') or 0) >= 0 else 'bán'} ròng {so(abs(tdp.get('rong') or 0), 1)} tỷ"
                            if tdp else "Chưa có số"),
                    "td_hom_nay": bool(td.get("la_phien_hom_nay")),
                    "doc": ngan((cau(pt.get("dong_tien") or "")[-1:] or [""])[0], 120)}

    # 10–11. index distortion
    top = sorted((dg.get("duong") or [])[:3] + (dg.get("am") or [])[:5], key=lambda r: -r["diem"])
    vin_ct = dg.get("nhom_vin_chi_tiet") or {}
    big = max(vin_ct.items(), key=lambda kv: abs(kv[1])) if vin_ct else ("", 0)
    C["distort"] = {"vin": dg.get("nhom_vin"), "con_lai": dg.get("phan_con_lai"), "index": vn.get("diem"),
                    "labels": [r["ma"] for r in top], "vals": [r["diem"] for r in top],
                    "big_ma": big[0], "big_diem": big[1], "note": ngan(pt.get("index_distortion"), 200)}

    # 12–13. kỹ thuật VN-Index
    kt = pt.get("ky_thuat_chi_so") or {}
    vb = nen("VNINDEX", nen_dir)
    rng = so_vn(kt.get("moc_chinh"))
    a = tu_tinh(vb, True) if vb else None
    zones = charts.auto_zones(a, vn["dong_cua"]) if a else []
    if len(rng) >= 2:
        zones = [z for z in zones if not (z[0] <= rng[1] and z[1] >= rng[0])]
        zones.append((min(rng[:2]), max(rng[:2]), "sup" if vn["dong_cua"] >= min(rng[:2]) else "res", "Mốc chính"))
    elif len(rng) == 1:
        zones.append((rng[0], rng[0], "sup", "Mốc chính"))
    vimg = None
    if vb and charts.draw("VNINDEX", vb, charts_dir / "VNINDEX.png", zones=zones, idx=True, size=(7.8, 3.83), ngay=ngay_vn):
        vimg = str(charts_dir / "VNINDEX.png")
    C["vni"] = {"img": vimg, "title": ngan(f"Mốc chính: {kt.get('moc_chinh') or ''}", 60),
                "caption": ngan(f"{kt.get('nguon_goc') or ''} {kt.get('vi_sao_thi_truong_nhan_ra') or ''}", 230)}
    C["scenario"] = {"title": ngan(f"Hai nhánh quanh {kt.get('moc_chinh') or 'mốc chính'}", 60),
                     "giu": ngan(kt.get("neu_giu"), 190), "thung": ngan(kt.get("neu_thung"), 190),
                     "xac_nhan": ngan(kt.get("xac_nhan"), 170), "vo_hieu": ngan(kt.get("vo_hieu"), 170)}

    # 14+. ngành + mã
    scan = cau(N.get("scan", ""))
    pick_pool = cau(N.get("picks", ""))
    syms_all: set[str] = set()
    for ng in pt.get("nganh") or []:
        for m in ng.get("ma") or []:
            syms_all.add(m["ma"])
    stocks, sectors = {}, []
    for ng in pt.get("nganh") or []:
        rows = []
        for m in ng.get("ma") or []:
            s = m["ma"]
            f = ma_fc.get(s, {})
            st = {"sym": s, "price": gia(f.get("dong")), "chg": pct(f.get("pct")), "struct": ngan(m.get("cau_truc"), 120),
                  "watch": gia(m.get("moc_theo_doi")), "broke": ngan(m.get("thung_thi"), 110),
                  "sup": gia(m.get("sl")), "res": gia(m.get("muc_tieu")), "conf": ngan(m.get("xac_nhan"), 100),
                  "val": sach(m.get("dinh_gia") or "chưa có dữ liệu định giá"),
                  "head": tieu_de_ma(s, m.get("cau_truc") or "", sl.get("tieu_de_ma") or {}),
                  "notes": cau_ve_ma(s, scan, syms_all), "pick_notes": cau_ve_ma(s, pick_pool, syms_all), "img": None, "mini": None}
            if f.get("nn_rong_ty") is not None and abs(f["nn_rong_ty"]) >= 30:
                st["extra"] = f"Khối ngoại {'mua' if f['nn_rong_ty'] > 0 else 'bán'} ròng {so(abs(f['nn_rong_ty']), 1)} tỷ"
            bars = nen(s, nen_dir)
            if bars:
                lv = []
                if m.get("moc_theo_doi"):
                    lv.append((m["moc_theo_doi"], "watch", "Mốc theo dõi"))
                if m.get("sl"):
                    lv.append((m["sl"], "sup", "Hỗ trợ kế tiếp"))
                if m.get("muc_tieu"):
                    lv.append((m["muc_tieu"], "res", "Kháng cự kế tiếp"))
                az = charts.auto_zones(tu_tinh(bars, False), bars[-1]["c"], n_each=1)
                if charts.draw(s, bars, charts_dir / f"{s}.png", levels=lv, zones=az, ngay=ngay_vn):
                    st["img"] = str(charts_dir / f"{s}.png")
                if charts.draw(s, bars, charts_dir / f"{s}_mini.png", levels=lv, size=(3.3, 3.2), compact=True):
                    st["mini"] = str(charts_dir / f"{s}_mini.png")
            stocks[s] = st
            rows.append(s)
        nhom = ng.get("nhom") or ""
        sec = {"tag": f"QUÉT NGÀNH · {nhom.upper()}", "title": ngan(f"{nhom}", 50), "lead": ngan(ng.get("nhan_dinh"), 160),
               "syms": rows, "notes": " ".join(x for x in scan if nhom.split()[0].lower() in x.lower())[:1500]}
        if "chứng khoán" in nhom.lower():
            ck = [ma_fc.get(s, {}) for s in rows]
            tren10 = [r["ma"] for r in ck if re.search(r"MA10=[\d.]+\(\+", r.get("duong_ma") or "")]
            tren20 = [r["ma"] for r in ck if re.search(r"MA20=[\d.]+\(\+", r.get("duong_ma") or "")]
            no = [r["ma"] for r in ck if (r.get("kl_x_tb20") or 0) >= 1.3]
            sec["checklist"] = [("Lấy lại MA10", "Có: " + ", ".join(tren10) if tren10 else "Chưa"),
                                ("Lấy lại MA20", "Có: " + ", ".join(tren20) if tren20 else "Chưa"),
                                ("Nổ khối lượng", "Có: " + ", ".join(no) if no else "Chưa")]
        sectors.append(sec)
    C["stocks"], C["sectors"] = stocks, sectors

    # nhóm không có bảng → thẻ ngắn
    covered = {(ng.get("nhom") or "").lower() for ng in pt.get("nganh") or []}
    groups = []
    for nhom, ds in (fc.get("ma_theo_nhom") or {}).items():
        if "nổi bật" in nhom or nhom.lower() in covered:
            continue
        ds = sorted(ds, key=lambda r: -(r.get("gt_khop_ty") or 0))[:3]
        if not ds:
            continue
        items = []
        for r in ds:
            note = ""
            if (r.get("kl_x_tb20") or 0) >= 1.3:
                note = f"KL {so(r['kl_x_tb20'], 1)}× TB20"
            elif r.get("nn_rong_ty") is not None and abs(r["nn_rong_ty"]) >= 20:
                note = f"NN {'mua' if r['nn_rong_ty'] > 0 else 'bán'} {so(abs(r['nn_rong_ty']), 0)} tỷ"
            items.append([r["ma"], gia(r.get("dong")), pct(r.get("pct")), note])
        avg = sum(r.get("pct") or 0 for r in ds) / len(ds)
        groups.append([nhom, f"Trung bình 3 mã thanh khoản lớn: {pct(avg)}", items])
    C["others"] = [groups[i:i + 3] for i in range(0, min(len(groups), 6), 3)]

    # xoay vòng, mã đáng nói, regime, phiên tới
    C["rotation"] = {"text": ngan(pt.get("xoay_vong"), 330), "points": [ngan(x, 140) for x in (pt.get("luan_diem_chinh") or [])[:4]]}
    picks = sl.get("ma_dang_noi") or []
    if not picks:
        seen = []
        for t in re.findall(r"\b[A-Z]{3}\b", N.get("picks", "")):
            if t in stocks and t not in seen:
                seen.append(t)
        picks = seen[:3]
    C["picks"] = [p for p in picks if p in stocks][:3]
    def ly_do(p):
        if (sl.get("ly_do") or {}).get(p):
            return sl["ly_do"][p]
        ds = [x for x in cau(stocks[p]["pick_notes"]) if len(x) > 40 and not x.startswith("Mã thứ")]
        return ds[0] if ds else stocks[p]["struct"]
    C["whys"] = {p: ngan(ly_do(p), 150) for p in C["picks"]}
    rg = pt.get("regime") or {}
    ten = rg.get("ten") or ""
    C["regime"] = {"ten": sl.get("regime") or REGIME_VI.get(ten.lower().strip(), ten), "co_tien": rg.get("co_tien") or "",
                   "x": tk.get("khop_so_tb20"), "ung_ho": [ngan(x, 120) for x in (rg.get("ung_ho") or [])[:3]],
                   "phan_bac": [ngan(x, 120) for x in (rg.get("phan_bac") or [])[:3]], "breadth": f"Độ rộng {tang} tăng / {giam} giảm"}
    pt_ = pt.get("phien_toi") or {}
    C["next"] = {k: ngan(pt_.get(k), 160) for k in ("cung_co", "lam_yeu", "xac_nhan", "vo_hieu")}
    return C


def run(ngay: str | None, nen_dir: Path | None, upload: bool, out_dir: Path) -> Path:
    f = OUT / f"{ngay or 'latest'}.json"
    day = json.loads(f.read_text(encoding="utf-8"))
    ngay = day["ngay"]
    if day.get("trang_thai_chay") == "khong_phien":
        raise SystemExit(f"{ngay}: không có phiên")
    cf = OUT / "claude" / f"{ngay}.json"
    claude = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else None
    ban, nguon, ghi = chon_ban(day, claude)
    work = out_dir / ngay
    work.mkdir(parents=True, exist_ok=True)
    C = build_content(day, ban, nguon, claude, nen_dir, work)
    C["ghi_chu_dung"] = ghi
    cj = work / "content.json"
    cj.write_text(json.dumps(C, ensure_ascii=False, indent=1), encoding="utf-8")
    pptx = work / f"NSF_RaSoat_{ngay}.pptx"
    subprocess.run(["node", str(SL / "build.js"), str(cj), str(pptx)], check=True, cwd=SL)
    for g in ghi:
        print("CẢNH BÁO:", g)
    print(json.dumps({"ngay": ngay, "nguon": nguon, "pptx": str(pptx), "kb": pptx.stat().st_size // 1024}, ensure_ascii=False))
    if upload:
        from . import kv  # noqa: PLC0415
        kv.put(ngay, pptx, nguon)
    return pptx


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ngay", default=None)
    ap.add_argument("--nen-dir", default=None, help="thư mục nến <MÃ>.json (chạy thử offline)")
    ap.add_argument("--khong-upload", action="store_true")
    ap.add_argument("--out", default=str(ROOT / ".cache" / "slides"))
    a = ap.parse_args(argv)
    run(a.ngay, Path(a.nen_dir) if a.nen_dir else None, not a.khong_upload, Path(a.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
