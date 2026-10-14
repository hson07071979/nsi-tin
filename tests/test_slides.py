"""Kiểm offline bộ dựng slide (không gọi mạng, không chạy node)."""
import json
from datetime import date, timedelta
from pathlib import Path

from slides import charts, make

NGAY = "2026-10-13"


def _bars(n=260, start=100.0):
    d0, p, out = date(2025, 6, 1), start, []
    for i in range(n):
        p = p * (1.004 if i % 5 else 0.985)
        out.append({"d": (d0 + timedelta(days=i)).isoformat(), "o": p * 0.995, "h": p * 1.01, "l": p * 0.99, "c": p, "v": 1000 + i})
    return out


def _nen_dir(tmp_path: Path, day: dict) -> Path:
    syms = {"VNINDEX"} | {m["ma"] for b in day["ban"] for ng in (b.get("phan_tich") or {}).get("nganh") or [] for m in ng.get("ma") or []}
    for s in syms:
        (tmp_path / f"{s}.json").write_text(json.dumps(_bars(start=1700 if s == "VNINDEX" else 30)))
    return tmp_path


def test_helpers():
    assert make.gia(35.0) == "35,0" and make.gia(32.86) == "32,86" and make.gia(222.0) == "222,0"
    assert make.so_vn("1.701,14–1.725,4 điểm") == [1701.14, 1725.4]
    s = make.sach("Vùng hỗ trợ 5 sao 1.701 (CAN). Đèn hệ thống NSI không đọc được.")
    assert "sao" not in s and "CAN" not in s and "NSI" not in s
    assert make.ngan(["a", "b"], 50) == "a; b."
    assert make.tieu_de_ma("KBC", "Bật tăng 1,38%, vượt MA10", {}) == "KBC: bật tăng 1,38%"


def test_claude_patch():
    day = json.loads((make.OUT / f"{NGAY}.json").read_text(encoding="utf-8"))
    cl = {"sua_phan_tich": [{"duong_dan": "regime.ten", "gia_tri": "Hồi kỹ thuật"}],
          "sua_loi_thoai": [{"tim": "không có câu này", "thay": "x"}]}
    ban, nguon, ghi = make.chon_ban(day, cl)
    assert nguon == "claude" and ban["phan_tich"]["regime"]["ten"] == "Hồi kỹ thuật"
    assert any("không tìm thấy" in g for g in ghi)
    assert all(b["phan_tich"]["regime"]["ten"] != "Hồi kỹ thuật" for b in day["ban"])   # bản gốc không bị sửa tại chỗ


def test_build_content(tmp_path):
    day = json.loads((make.OUT / f"{NGAY}.json").read_text(encoding="utf-8"))
    ban, nguon, _ = make.chon_ban(day, None)
    (tmp_path / "nen").mkdir()
    C = make.build_content(day, ban, nguon, None, _nen_dir(tmp_path / "nen", day), tmp_path / "work")
    assert C["hook"]["question"] and len(C["signature"]) == 3
    assert C["vni"]["img"] and Path(C["vni"]["img"]).exists()
    assert C["sectors"] and all(C["stocks"][s]["img"] for sec in C["sectors"] for s in sec["syms"])
    assert all(len(g) <= 3 for g in C["others"])
    txt = json.dumps(C, ensure_ascii=False)
    assert "★" not in txt and "(CAN)" not in txt


def test_auto_zones_skip_bb():
    z = {"vung_dang_test": None, "ho_tro_gan": [{"tu": 9, "den": 9.2, "do_manh": 5}, {"tu": 8.8, "den": 8.8, "bb": True}],
         "khang_cu_gan": [{"tu": 11, "den": 11.3, "do_manh": 2}]}
    out = charts.auto_zones(z, 10)
    assert len(out) == 2 and out[0][3] == "Hỗ trợ mạnh"


def test_moc_khong_can_cu_bi_bo():
    f = {"vung_dang_test": "22.84–23.25 ★★", "ho_tro": ["21.88–22.19 ★★★ (3 lần chạm, đáy cũ, cách +5.3%)"],
         "khang_cu": [], "duong_ma": "MA10=21.9(+5.48%) MA20=21.55(+7.19%)"}
    assert make.can_cu(22.84, f) and make.can_cu(21.88, f) and make.can_cu(21.55, f)
    assert not make.can_cu(24.5, f)          # HDB 24,5 trong mẫu 13/10: không có nguồn
    assert not make.can_cu(5.3, f)           # không lấy nhầm số % làm mốc


def test_cham_khong_dem_trung_pivot():
    from daily import tech
    from datetime import date, timedelta
    d0, out = date(2025, 1, 1), []
    for i in range(260):                       # một đáy rất rõ ở ngày 200, đi ngang quanh 100
        lo = 90.0 if i == 200 else 99.0
        out.append({"d": (d0 + timedelta(days=i)).isoformat(), "o": 100, "h": 101, "l": lo, "c": 100, "v": 1000})
    sup, res, dang = tech.vung_ho_tro_khang_cu(out, 100.0, {}, tol=0.015)
    z = next(z for z in sup if z["tu"] <= 90.0 <= z["den"])
    assert z["cham"] == 1                       # trước đây ±3 và ±8 bắt cùng nến → 2 lần chạm


def test_khong_con_bb():
    from daily import tech
    a = tech.analyse(_bars())
    assert a["bollinger"] is None
    assert not any(z.get("bb") for z in (a.get("ho_tro_gan") or []) + (a.get("khang_cu_gan") or []))
