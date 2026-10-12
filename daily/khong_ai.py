"""Phương án dự phòng khi Gemini hết lượt / lỗi: bản PHÂN TÍCH SỐ LIỆU dựng hoàn toàn bằng code.

Ưu tiên của anh Sơn (12/10/2026): (1) phân tích số liệu trước, (2) viết script sau nếu còn lượt.
Bản này luôn có, kể cả khi không gọi được AI. Câu chữ theo khuôn, không văn hoa, nhưng đủ 9 tầng ở mức số liệu:
signature, mốc chính VN-Index (giữ/thủng), thanh khoản, dòng tiền, index distortion, regime tạm tính theo quy tắc,
từng mã trong rổ có mốc theo dõi + mốc kế tiếp + định giá.
"""
from __future__ import annotations


def _f(x, n=1):
    if x is None:
        return "—"
    s = f"{x:,.{n}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return s


def _moc_chinh(kt: dict, close: float) -> dict:
    """Ưu tiên vùng giá đang test (≥3 sao), rồi vùng hỗ trợ gần nhất ≥3 sao, rồi chân nến tăng mạnh gần, rồi đáy 20 phiên."""
    z = kt.get("vung_dang_test")
    if z and z.get("do_manh", 0) >= 3:
        return {"gia": z["tu"], "nguon": f"vùng {z['tu']}–{z['den']} {'★' * z['do_manh']} ({', '.join(z['nguon'])}) — giá đang test",
                "da_gay": False}
    for z in kt.get("ho_tro_gan") or []:
        if z.get("do_manh", 0) >= 3:
            return {"gia": z["gia"], "nguon": f"vùng hỗ trợ {z['tu']}–{z['den']} {'★' * z['do_manh']} ({', '.join(z['nguon'])})",
                    "da_gay": False}
    for x in reversed(kt.get("nen_phat_dong") or []):
        if abs(close / x["chan"] - 1) <= 0.03:
            return {"gia": x["chan"], "nguon": f"chân cây nến phát động ngày {x['ngay']} (+{x['pct']}%)",
                    "da_gay": x["da_gay"]}
    for z in kt.get("ho_tro_gan") or []:
        if z["cham"] >= 2:
            return {"gia": z["gia"], "nguon": f"vùng đáy chạm {z['cham']} lần, gần nhất {z['ngay_gan_nhat']}", "da_gay": False}
    d = kt.get("day_20p") or {}
    return {"gia": d.get("gia"), "nguon": f"đáy 20 phiên ngày {d.get('ngay')}", "da_gay": False}


def _ke_tiep(kt: dict, duoi: float) -> float | None:
    for z in kt.get("ho_tro_gan") or []:
        if z["gia"] < duoi * 0.995:
            return z["gia"]
    d = (kt.get("day_60p") or {}).get("gia")
    return d if d and d < duoi else None


def _cau_truc(a: dict) -> str:
    tren = [n for n in (10, 20, 50, 200) if (a.get(f"so_ma{n}_pct") or -1) > 0]
    if len(tren) == 4:
        return "trên cả MA10/20/50/200 (nền cao)"
    if not tren:
        return f"dưới cả 4 đường MA, {a.get('so_phien_duoi_ma10')} phiên dưới MA10 (nhóm đáy/downtrend)"
    return "trên " + "/".join(f"MA{n}" for n in tren) + ", dưới các MA còn lại"


def _ma_row(r: dict) -> dict:
    close = r.get("dong_cua")
    if not close or r.get("thieu_lich_su"):
        return {"ma": r["ma"], "cau_truc": "chưa đủ lịch sử giá"}
    # các mốc dưới giá: hỗ trợ cục bộ, đáy 20/60/250 phiên, chân nến phát động chưa gãy → lấy mốc cao nhất làm mốc theo dõi
    cands = [z["gia"] for z in r.get("ho_tro_gan") or []]
    cands += [(r.get(k) or {}).get("gia") for k in ("day_20p", "day_60p", "day_250p")]
    cands += [x["chan"] for x in r.get("nen_phat_dong") or [] if not x["da_gay"]]
    duoi = sorted({c for c in cands if c and c < close * 0.995}, reverse=True)
    sup = duoi[0] if duoi else None
    ke = next((c for c in duoi[1:] if c < sup * 0.99), None) if sup else None
    cach = round((close / sup - 1) * 100, 1) if sup else None
    gay = [x for x in r.get("nen_phat_dong") or [] if x["da_gay"]]
    ct = _cau_truc(r) + (f"; đã gãy chân nến phát động {gay[-1]['ngay']}" if gay else "")
    sl = round(max(sup, close * 0.93), 2) if sup else round(close * 0.93, 2)       # SL theo mốc, không quá 7%
    tren = sorted(z["gia"] for z in r.get("khang_cu_gan") or [] if z["gia"] > close * 1.005)
    muc_tieu = tren[0] if tren else None
    return {
        "ma": r["ma"], "cau_truc": ct, "moc_theo_doi": sup, "sl": sl, "muc_tieu": muc_tieu,
        "thung_thi": f"về vùng {_f(ke, 2)}" if ke else "chưa có hỗ trợ gần hơn trong dữ liệu",
        "xac_nhan": f"lấy lại MA20 ({_f(r.get('ma20'), 2)})" if (r.get("so_ma20_pct") or 0) < 0 else
                    f"giữ trên MA20 ({_f(r.get('ma20'), 2)}) với khối lượng ≥ trung bình",
        "diem_dung_cach_pct": cach, "rong_hon_chuan_7": bool(cach and cach > 7),
        "dinh_gia": f"P/B {_f(r.get('pb'), 2)}, P/E {_f(r.get('pe'), 1)}" if r.get("pb") else "chưa có dữ liệu định giá",
        "nhan": "OBSERVATION",
        "_pct": r.get("pct_phien"), "_kl": r.get("kl_x_tb20"),
    }


def phan_tich(facts: dict) -> dict:
    vn = facts["vnindex"]
    kt = vn.get("ky_thuat") or {}
    b = facts.get("breadth_hose") or {}
    lq = facts.get("thanh_khoan_hose") or {}
    ng = facts.get("khoi_ngoai") or {}
    td = facts.get("tu_doanh") or {}
    dg = facts.get("dong_gop_diem") or {}
    close = vn["dong_cua"]
    moc = _moc_chinh(kt, close)
    ke = _ke_tiep(kt, moc["gia"]) if moc.get("gia") else None
    ratio = lq.get("khop_so_tb20")
    co_tien = "có tiền" if ratio and ratio >= 1.1 else "thiếu tiền" if ratio and ratio < 0.9 else "trung tính"
    tren = [n for n in (20, 50, 200) if (kt.get(f"so_ma{n}_pct") or -1) > 0]
    if not tren and (b.get("giam") or 0) > 1.5 * (b.get("tang") or 1) and (ratio or 0) >= 1.2:
        regime = "Capitulation"
    elif not tren and co_tien == "thiếu tiền":
        regime = "Rotation/Divergence" if (b.get("tang") or 0) >= (b.get("giam") or 0) else "Distribution"
    elif len(tren) == 3:
        regime = "Risk-on/Trend" if co_tien != "thiếu tiền" else "Rotation/Divergence"
    else:
        regime = "Technical rebound" if (vn.get("diem") or 0) > 0 else "Distribution"
    nn = (ng.get("phien") or {}).get("rong")
    nganh: dict[str, list] = {}
    for r in facts.get("ma", []):
        nganh.setdefault(r["nhom"], []).append(_ma_row(r))
    nganh_out = []
    for nhom, rows in nganh.items():
        tang = sum(1 for x in rows if (x.get("_pct") or 0) > 0)
        giam = sum(1 for x in rows if (x.get("_pct") or 0) < 0)
        for x in rows:
            x.pop("_pct", None)
            x.pop("_kl", None)
        nganh_out.append({"nhom": nhom, "nhan_dinh": f"{tang} mã tăng / {giam} mã giảm trong rổ.", "ma": rows})
    sec = facts.get("nganh") or []
    return {
        "_ban_so_lieu": True,
        "signature": {
            "index_noi_gi": f"VN-Index {_f(vn.get('diem'), 2)} điểm ({_f(vn.get('pct'), 2)}%) về {_f(close, 2)}; nhóm Vin "
                            f"{_f(dg.get('nhom_vin'), 1)} điểm, phần còn lại {_f(dg.get('phan_con_lai'), 1)} điểm.",
            "co_phieu_noi_gi": f"HOSE {b.get('tang')} tăng / {b.get('giam')} giảm / {b.get('dung')} đứng, trần {b.get('tran')} · sàn {b.get('san')}.",
            "dong_tien_noi_gi": f"Khớp {_f(lq.get('gt_khop'), 0)} tỷ = {_f(ratio, 2)} lần TB20 ({co_tien}); khối ngoại {_f(nn, 0)} tỷ.",
        },
        "ky_thuat_chi_so": {
            "moc_chinh": moc.get("gia"), "loai_moc": "QS", "nguon_goc": moc.get("nguon"),
            "vi_sao_thi_truong_nhan_ra": "mốc cấu trúc lấy tự động từ nến phát động / vùng đáy nhiều lần chạm",
            "neu_giu": f"giữ trên {_f(moc.get('gia'), 2)} thì còn đi ngang, phân hóa",
            "neu_thung": f"thủng {_f(moc.get('gia'), 2)} thì hỗ trợ kế tiếp {_f(ke, 2)}" if ke else "chưa có hỗ trợ gần hơn",
            "xac_nhan": f"lấy lại MA10 ({_f(kt.get('ma10'), 2)}) với khớp lệnh ≥ trung bình 20 phiên",
            "vo_hieu": f"đóng cửa dưới {_f(ke or moc.get('gia'), 2)}",
            "ho_tro_ke_tiep": ke,
            **({"ghi_chu": "HÔM NAY ĐÃ ĐÓNG CỬA DƯỚI MỐC NÀY (gãy chân nến phát động)"} if moc.get("da_gay") else {}),
        },
        "regime": {"ten": regime + " (tạm tính bằng quy tắc, chưa qua AI)", "co_tien": co_tien,
                   "ung_ho": [f"VN-Index {'trên' if tren else 'dưới'} MA20/50/200: trên {tren or 'không đường nào'}",
                              f"khớp lệnh {_f(ratio, 2)} lần TB20"],
                   "phan_bac": ["quy tắc đơn giản, cần người đọc xác nhận"],
                   "so_voi_den_nsi": str((facts.get("den_nsi") or {}).get("den_thi_truong") or "không đọc được đèn NSI")},
        "thanh_khoan": f"Tổng {_f(lq.get('gt_tong'), 0)} tỷ − thỏa thuận {_f(lq.get('gt_thoa_thuan'), 0)} tỷ "
                       f"({_f(lq.get('ty_trong_thoa_thuan_pct'), 1)}%) = khớp {_f(lq.get('gt_khop'), 0)} tỷ; phiên trước "
                       f"{_f(lq.get('khop_phien_truoc'), 0)}, TB5 {_f(lq.get('khop_tb5'), 0)}, TB20 {_f(lq.get('khop_tb20'), 0)}.",
        "dong_tien": f"Khối ngoại {_f(nn, 0)} tỷ, lũy kế tháng {_f(ng.get('luy_ke_thang'), 0)} tỷ, từ đầu năm "
                     f"{_f(ng.get('luy_ke_nam'), 0)} tỷ. Tự doanh phiên {(td.get('phien') or {}).get('date')}: "
                     f"{_f((td.get('phien') or {}).get('rong'), 0)} tỷ.",
        "index_distortion": "Đóng góp âm lớn nhất: " + ", ".join(f"{x['ma']} {_f(x['diem'], 2)}" for x in dg.get("am", [])[:5])
                            + ". Dương: " + ", ".join(f"{x['ma']} {_f(x['diem'], 2)}" for x in dg.get("duong", [])[:5]) + ".",
        "xoay_vong": "Ngành mạnh nhất: " + ", ".join(f"{x['nganh']} {_f(x['pct'], 2)}%" for x in sec[:3])
                     + ". Yếu nhất: " + ", ".join(f"{x['nganh']} {_f(x['pct'], 2)}%" for x in sec[-3:]) + ".",
        "the_gioi": [{"bien": v.get("ten"), "muc": f"{v.get('gia')} lúc {v.get('luc_vn', '')[11:16]}",
                      "kenh_truyen_dan": f"1 phiên {_f(v.get('pct_1p'), 2)}%, 20 phiên {_f(v.get('pct_20p'), 2)}%",
                      "he_qua_neu_vuot": f"cao 20 phiên {v.get('cao_20p')} / thấp {v.get('thap_20p')}", "nhan": "FACT"}
                     for k, v in (facts.get("the_gioi") or {}).items()
                     if not v.get("thieu") and k in ("brent", "dxy", "us10y", "usdvnd", "spx", "es_fut", "shanghai", "hangseng")],
        "nganh": nganh_out,
        "luan_diem_chinh": [],
        "phien_toi": {"xac_nhan": [f"VN-Index lấy lại MA10 {_f(kt.get('ma10'), 2)}"],
                      "vo_hieu": [f"VN-Index thủng {_f(ke or moc.get('gia'), 2)}"], "cung_co": [], "lam_yeu": []},
        "du_bao_moi": ([{"doi_tuong": "VNINDEX", "loai": "vuot" if moc.get("da_gay") else "giu", "moc": moc["gia"],
                         "han_phien": 5, "loai_moc": "QS",
                         "noi_dung": f"VN-Index {'lấy lại' if moc.get('da_gay') else 'giữ trên'} {_f(moc['gia'], 2)} trong 5 phiên"}]
                       if moc.get("gia") else []),
    }
