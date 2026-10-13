"""Bản tóm tắt gọn (~5–10 nghìn token) để Claude đọc khi kiểm bản Gemini trong chat. Không gọi AI.

Ra: out/daily/brief/<ngày>.md  (workflow daily_market commit cùng out/daily)
Gồm: số liệu chính (FACT) · vùng hỗ trợ/kháng cự tự tính của các mã trong bảng · bản phân tích + lời thoại của Gemini.
Claude đối chiếu hai phần, rồi ghi out/daily/claude/<ngày>.json theo mẫu ở slides/README.md.
"""
from __future__ import annotations

import json
import sys

from tin.common import ROOT

from .make import OUT, so

W = ("dxy", "us10y", "usdvnd", "brent", "dow", "spx", "nasdaq", "es_fut", "vix", "shanghai", "nikkei", "hangseng")


def _ma(r: dict) -> str:
    return (f"{r['ma']} {r.get('dong')} ({so(r.get('pct'), 2, True)}%) KL×{r.get('kl_x_tb20')} · {r.get('duong_ma', '')} · "
            f"dưới MA10 {r.get('phien_duoi_ma10')} phiên · đáy20/60/250 {r.get('day_20_60_250p')} · đỉnh60/250 {r.get('dinh_60_250p')}\n"
            f"    test: {r.get('vung_dang_test') or '—'} | HT: {r.get('ho_tro')} | KC: {r.get('khang_cu')} | "
            f"P/B {r.get('pb')} P/E {r.get('pe')} · NN {r.get('nn_rong_ty')} tỷ · góp {r.get('diem_dong_gop')} điểm")


def tao(ngay: str | None = None) -> str:
    day = json.loads((OUT / f"{ngay or 'latest'}.json").read_text(encoding="utf-8"))
    fc = day.get("fc") or {}
    L = [f"# Brief cho Claude — phiên {day['ngay']}", "",
         "Vai: kiểm số liệu và logic của bản Gemini (chỉ sửa câu sai, KHÔNG viết lại văn), rồi ghi out/daily/claude/<ngày>.json.", ""]
    v = fc.get("vnindex") or {}
    kt = v.get("ky_thuat") or {}
    L += ["## FACT", f"- VN-Index {v.get('dong_cua')} ({so(v.get('diem'), 2, True)} điểm, {so(v.get('pct'), 2, True)}%), mở {v.get('mo')} cao {v.get('cao')} thấp {v.get('thap')}",
          f"- Kỹ thuật: {kt.get('duong_ma')} · test {kt.get('vung_dang_test')} · HT {kt.get('ho_tro')} · KC {kt.get('khang_cu')} · đáy20/60/250 {kt.get('day_20_60_250p')}",
          f"- Breadth: {json.dumps(fc.get('breadth_hose'), ensure_ascii=False)}",
          f"- Thanh khoản (tỷ): {json.dumps({k: x for k, x in (fc.get('thanh_khoan_hose_ty') or {}).items() if k != 'nam_phien_truoc'}, ensure_ascii=False)}"]
    kn = fc.get("khoi_ngoai_ty") or {}
    L += [f"- Khối ngoại: phiên {kn.get('phien')} · tháng {kn.get('luy_ke_thang')} · năm {kn.get('luy_ke_nam')} · mua {kn.get('mua_rong_nhieu')} · bán {kn.get('ban_rong_nhieu')}",
          f"- Tự doanh: {json.dumps(fc.get('tu_doanh_ty'), ensure_ascii=False)}"]
    dg = fc.get("dong_gop_diem") or {}
    L += [f"- Đóng góp: Vin {dg.get('nhom_vin')} ({dg.get('nhom_vin_chi_tiet')}) · còn lại {dg.get('phan_con_lai')} · dương {dg.get('duong')} · âm {dg.get('am')}",
          "- Ngành: " + " · ".join(f"{n['nganh']} {so(n['pct'], 2, True)}%" for n in (fc.get("nganh_hose") or []))]
    tg = fc.get("the_gioi_luc_chay") or {}
    L.append("- Thế giới: " + " · ".join(f"{k} {(tg.get(k) or {}).get('gia')} ({so((tg.get(k) or {}).get('pct_1p'), 2, True)}%, 20p cao {(tg.get(k) or {}).get('cao_20p')}, 3t cao {(tg.get(k) or {}).get('cao_3t')}, lúc {((tg.get(k) or {}).get('luc_vn') or '')[5:16]})"
                                          for k in W if tg.get(k)))
    L.append(f"- Thiếu dữ liệu: {fc.get('thieu_du_lieu')} · không có nguồn: {fc.get('khong_co_nguon')}")
    so_db = day.get("so_du_bao") or {}
    L += ["", "## Sổ dự báo đang mở"] + [f"- {r.get('doi_tuong')} {r.get('loai')} {r.get('moc')} ({r.get('loai_moc')}, hạn {r.get('han_phien')} phiên, đã qua {r.get('phien_da_qua')}): {r.get('noi_dung')}"
                                          for r in so_db.get("dang_mo") or []]
    ban = next((b for b in day.get("ban") or [] if (b.get("script") or {}).get("phan")), None) or (day.get("ban") or [{}])[0]
    pt = ban.get("phan_tich") or {}
    co_bang = {m["ma"] for ng in pt.get("nganh") or [] for m in ng.get("ma") or []}
    ma_fc = {r["ma"]: r for nh in (fc.get("ma_theo_nhom") or {}).values() for r in nh}
    L += ["", "## Mã có trong bảng phân tích — số liệu gốc"] + [_ma(ma_fc[m]) for m in sorted(co_bang) if m in ma_fc]
    L += ["", f"## Bản Gemini để kiểm ({ban.get('nhan')} · {ban.get('cach')} · {ban.get('model')})",
          f"Lỗi tự kiểm của bot: {ban.get('loi')}", "", "### phan_tich (JSON)", "```json",
          json.dumps(pt, ensure_ascii=False, separators=(",", ":")), "```", "", "### Lời thoại"]
    for p in (ban.get("script") or {}).get("phan") or []:
        L += [f"**{p.get('ten')}**", p.get("loi_thoai") or "", ""]
    return "\n".join(L)


def main(argv=None) -> int:
    ngay = (argv or sys.argv[1:] or [None])[0]
    md = tao(ngay)
    day = json.loads((OUT / f"{ngay or 'latest'}.json").read_text(encoding="utf-8"))["ngay"]
    f = ROOT / "out" / "daily" / "brief" / f"{day}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(md, encoding="utf-8")
    print(f"brief: {f} ({len(md)} ký tự)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
