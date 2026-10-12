"""Kiểm offline cho NSI Daily Market (không gọi mạng)."""
from datetime import date, timedelta

from daily import ai, forecast, prompts, tech


def _bars(n=260, start=100.0, step=0.1):
    d0 = date(2025, 1, 1)
    out, p = [], start
    for i in range(n):
        p = p + step if i % 7 else p - 3 * step
        out.append({"d": (d0 + timedelta(days=i)).isoformat(), "o": p, "h": p * 1.01, "l": p * 0.99, "c": p,
                    "v": 1000 + (5000 if i == n - 30 else 0)})
    return out


def test_analyse_shape():
    a = tech.analyse(_bars(), _bars())
    for k in ("ma10", "ma200", "ho_tro_gan", "khang_cu_gan", "day_60p", "rs_20p", "so_phien_duoi_ma10"):
        assert k in a
    assert a["ma200"] is not None


def test_analyse_short_history():
    assert tech.analyse(_bars(10)).get("thieu_lich_su")


def test_liquidity():
    days = [{"date": f"2026-10-{30 - i:02d}", "gt_khop": 10000 + i * 100, "gt_tong": 12000, "gt_thoa_thuan": 2000}
            for i in range(25)]
    lq = tech.liquidity(days)
    assert lq["khop_tb20"] and lq["ty_trong_thoa_thuan_pct"] == round(2000 / 12000 * 100, 1)


def test_forecast_cycle():
    rows = []
    forecast.add(rows, "2026-10-12", [{"doi_tuong": "vnindex", "loai": "giu", "moc": 1700, "han_phien": 2},
                                      {"doi_tuong": "SSI", "loai": "vuot", "moc": 20, "han_phien": 3},
                                      {"doi_tuong": "X", "loai": "sai_loai", "moc": 1}], "cach_1_luot")
    assert len(rows) == 2
    forecast.check(rows, "2026-10-12", {"VNINDEX": 1600})          # cùng ngày ghi → không chấm
    assert all(r["trang_thai"] == "mo" for r in rows)
    forecast.check(rows, "2026-10-13", {"VNINDEX": 1710, "SSI": 19})
    forecast.check(rows, "2026-10-13", {"VNINDEX": 1710, "SSI": 19})  # chạy lại trong ngày → không đếm 2 lần
    assert rows[0]["phien_da_qua"] == 1
    forecast.check(rows, "2026-10-14", {"VNINDEX": 1705, "SSI": 20.5})
    assert rows[0]["ket_qua"] == "ĐÚNG" and rows[1]["ket_qua"] == "ĐÚNG"


def test_forecast_thung_sai():
    rows = []
    forecast.add(rows, "2026-10-12", [{"doi_tuong": "VNINDEX", "loai": "giu", "moc": 1720, "han_phien": 5}], "x")
    forecast.check(rows, "2026-10-13", {"VNINDEX": 1700})
    assert rows[0]["ket_qua"] == "SAI"


def test_check_script_flags():
    sc = {"phan": [{"ten": "a", "loi_thoai": "mốc này chắc chắn sẽ giữ, anh chị cài SL ở 27"}], "tiktok": []}
    loi = ai.check_script(sc)
    assert any("ngắn" in x for x in loi) and any("cụm cấm" in x for x in loi) and any("TikTok" in x for x in loi)
    ok = {"phan": [{"ten": "a", "loi_thoai": "khối ngoại bán ra mạnh. " * 700}], "tiktok": [{}, {}, {}]}
    assert ai.check_script(ok) == []


def test_compact_has_no_key_collision():
    a = tech.analyse(_bars(), _bars())
    facts = {"ngay": "2026-10-12", "vnindex": {"dong_cua": 1, "ky_thuat": a},
             "ma": [{"ma": "SSI", "nhom": "Chứng khoán", **a}]}
    fc = prompts.compact(facts)
    row = fc["ma_theo_nhom"]["Chứng khoán"][0]
    assert row["ma"] == "SSI" and "duong_ma" in row
    assert prompts.prompt_mot_luot(fc, {}) and prompts.prompt_viet_lai(fc, {}, "bank yếu", None)


def test_lam_sach():
    sc = {"phan": [{"ten": "a", "loi_thoai": "gấp 1,3 lần TB20 (FACT). sổ dự báo hôm qua. cài SL ở 27"}],
          "tiktok": [{"loi_thoai": "trong dữ liệu FACT có 3 số"}]}
    out = ai.lam_sach(sc)
    t = out["phan"][0]["loi_thoai"]
    assert "TB20" not in t and "FACT" not in t and "cài SL" not in t and t.startswith("Gấp")
    assert "FACT" not in out["tiktok"][0]["loi_thoai"]


def test_ghi_khong_de_latest(tmp_path, monkeypatch):
    from daily import run_daily
    monkeypatch.setattr(run_daily, "OUT", tmp_path)
    run_daily._ghi("2026-10-12", {"ngay": "2026-10-12", "trang_thai_chay": "dat", "ban": [1]})
    run_daily._ghi("2026-10-13", {"ngay": "2026-10-13", "trang_thai_chay": "khong_phien"})
    import json
    assert json.loads((tmp_path / "latest.json").read_text())["ngay"] == "2026-10-12"
    assert len(json.loads((tmp_path / "index.json").read_text())) == 2


def test_khong_ai_va_uu_tien(monkeypatch):
    """Gemini chết hẳn → vẫn có bản phân tích số liệu (UT1), không có lời thoại."""
    import json as _j
    from pathlib import Path
    from daily import khong_ai
    a = tech.analyse(_bars(), _bars(), is_index=True)
    s = tech.analyse(_bars(), _bars())
    facts = {"ngay": "2026-10-12", "vnindex": {"dong_cua": a["dong_cua"], "diem": -5, "pct": -0.3, "ky_thuat": a},
             "breadth_hose": {"tang": 100, "giam": 200, "dung": 50, "tran": 1, "san": 2},
             "thanh_khoan_hose": {"gt_khop": 10000, "khop_so_tb20": 0.8}, "khoi_ngoai": {"phien": {"rong": -500}},
             "dong_gop_diem": {"am": [{"ma": "VIC", "diem": -3}], "duong": [], "nhom_vin": -3, "phan_con_lai": -2},
             "ma": [{"ma": "SSI", "nhom": "Chứng khoán", **s}], "the_gioi": {}, "nganh": []}
    pt = khong_ai.phan_tich(facts)
    assert pt["ky_thuat_chi_so"]["moc_chinh"] and pt["nganh"][0]["ma"][0]["ma"] == "SSI"
    _j.dumps(pt, ensure_ascii=False)

    def chet():
        raise ai.GeminiError("thiếu GEMINI_API_KEY")
    monkeypatch.setattr(ai, "new_client", chet)
    ket, meta = ai.chay_hai_ban({"ngay": "2026-10-12"}, {}, facts=facts)
    assert any(b["cach"] == "so_lieu_khong_ai" and b["phan_tich"] for b in ket)
    assert not any((b.get("script") or {}).get("phan") for b in ket)
