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
