"""Bản tin sáng: 7h00 đồng hồ ảo gọi → cào web + đọc Zalo → ảnh chụp vĩ mô + cờ mềm → AI debate → out/latest.json.

python -m tin.run_sang            chạy thật
python -m tin.run_sang --gac      chế độ GÁC (7h45/8h15): hôm nay đã có bản đạt thì thoát ngay
python -m tin.run_sang --dry      không gọi AI (thử cào + giao diện)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import timedelta

from . import macro, nsi_context, playbook
from .common import ROOT, iso, now_vn, parse_iso, read_json, write_json
from .fetch_web import fetch_web
from .fetch_zalo import load_zalo

HAN_CHOT = (8, 30)  # 8h30: trễ nhất
PB_VER = 1


def _ctx_text(feat: dict, pb: dict, nsi: dict, lnh_note: str) -> str:
    keys = ["lnh_on", "lnh_on_chg5_bp", "lnh_on_chg20_bp", "usdvnd", "usdvnd_chg20_pct", "dxy", "dxy_chg20_pct",
            "us10y", "us10y_chg20_bp", "brent", "brent_chg20_pct", "gold_chg20_pct", "vix", "spx_chg5_pct",
            "vnindex", "vnindex_chg5_pct", "vnindex_chg20_pct"]
    so = ", ".join(f"{k}={feat.get(k)}" for k in keys if feat.get(k) is not None)
    bat = [f"{f['id']} ({f['muc_ten']}): {f['doc']}" for f in pb["flags"] if f["trang_thai"] == "bat"]
    thieu = [f["id"] for f in pb["flags"] if f["trang_thai"] == "thieu_du_lieu"]
    s = f"Số liệu: {so}. {lnh_note}\nCờ vĩ mô mềm đang BẬT: {bat or 'không'}. Thiếu dữ liệu: {thieu or 'không'}."
    if nsi:
        s += f"\nHệ thống NSI: đèn thị trường={nsi.get('den_thi_truong')}, đang cầm={nsi.get('dang_cam')}, watchlist={nsi.get('watchlist')}."
    return s


def _window(state: dict, end):
    last = parse_iso(state.get("last_end"))
    if last and last < end:
        start = max(last, end - timedelta(hours=80))
    else:
        start = end - timedelta(hours=24)
    return start, end


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gac", action="store_true")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--max-topics", type=int, default=15)
    a = ap.parse_args(argv)

    t0 = time.time()
    end = now_vn()
    today = end.date().isoformat()
    out_dir, data_dir = ROOT / "out", ROOT / "data"
    cur = read_json(out_dir / f"{today}.json", None)
    if a.gac and cur and cur.get("trang_thai_chay") == "dat":
        print(f"GÁC: {today} đã có bản đạt lúc {cur.get('xong_luc')} — thoát.")
        return 0

    state = read_json(data_dir / "state.json", {})
    # chạy lại trong cùng ngày thì giữ nguyên cửa sổ của lần đầu (để không mất tin)
    if cur and cur.get("cua_so"):
        start = parse_iso(cur["cua_so"]["tu"])
    else:
        start, _ = _window(state, end)
    cfg = read_json(ROOT / "config" / "sources.json", {})
    zcfg = read_json(ROOT / "config" / "zalo_groups.json", {"groups": []})
    pbk = read_json(ROOT / "config" / "macro_playbook.json", {})
    seen = set(read_json(data_dir / "seen.json", []))
    lim = cfg.get("gioi_han", {})
    print(f"Cửa sổ tin: {iso(start)} → {iso(end)}")

    print("1) Cào web")
    web_items, lnh_sbv, src_log = fetch_web(cfg, start, end, seen)
    web_items = sorted(web_items, key=lambda x: -x["score"])[: lim.get("web_toi_da_vao_ai", 140)]
    print("2) Đọc Zalo")
    zalo_items, zalo_status = load_zalo(ROOT, zcfg, start, end)
    zalo_items = sorted(zalo_items, key=lambda x: -x["score"])[: lim.get("zalo_toi_da_vao_ai", 220)]
    zalo_items.sort(key=lambda x: x["published"])
    print(f"   web {len(web_items)} · zalo {len(zalo_items)} (listener sống: {zalo_status['listener_song']})")

    print("3) Vĩ mô")
    snap = macro.snapshot(end)
    jpath = data_dir / "macro_daily.csv"
    journal = macro.load_journal(jpath)
    lnh_note = ""
    lnh_today = None
    if lnh_sbv:
        lnh_today = {"lnh_on": lnh_sbv.get("qua_dem"), "lnh_1w": lnh_sbv.get("1_tuan"), "lnh_nguon": "sbv"}
        lnh_note = f"LNH qua đêm theo NHNN (ngày áp dụng {lnh_sbv.get('ngay')})."
    row = {"date": today, **(lnh_today or {}), **{k: snap.get(k) for k in macro.COLS if k in snap}}
    macro.append_journal(jpath, row)
    series = macro.lnh_series(macro.load_journal(jpath), data_dir / "lnh_hist.csv")
    feat = macro.to_features(snap, macro.lnh_features(series, today))
    pb = playbook.evaluate(pbk, feat)
    nsi = nsi_context.load()
    ctx = _ctx_text(feat, pb, nsi, lnh_note)

    result = {
        "ngay": today, "bat_dau_luc": iso(end), "cua_so": {"tu": iso(start), "den": iso(end)},
        "nguon_web": src_log, "zalo_status": zalo_status, "vi_mo": {"so_lieu": feat, "playbook": pb},
        "nsi": nsi, "web": {"items": web_items}, "zalo": {"items": zalo_items},
        "ai": None, "trang_thai_chay": "dang_chay", "pb_ver": PB_VER,
    }

    if a.dry:
        result["trang_thai_chay"] = "dry"
    else:
        from .debate import run_tab, tong_hop  # noqa: PLC0415
        from .gemini import Gemini, GeminiError  # noqa: PLC0415
        try:
            g = Gemini()
            print("4) Debate tab WEB")
            web_tab = run_tab(g, web_items, "web", ctx, a.max_topics)
            # NHNN chặn IP nước ngoài → lấy LNH từ số liệu báo mà AI trích được
            sl = web_tab.get("so_lieu") or {}
            if not lnh_today and isinstance(sl.get("lnh_qua_dem"), (int, float)) and 0 < sl["lnh_qua_dem"] < 30:
                row.update({"lnh_on": sl["lnh_qua_dem"], "lnh_1w": sl.get("lnh_1_tuan"), "lnh_nguon": "bao"})
                macro.append_journal(jpath, row)
                series = macro.lnh_series(macro.load_journal(jpath), data_dir / "lnh_hist.csv")
                feat = macro.to_features(snap, macro.lnh_features(series, today))
                pb = playbook.evaluate(pbk, feat)
                result["vi_mo"] = {"so_lieu": feat, "playbook": pb,
                                   "ghi_chu": "LNH lấy từ tin báo (AI trích), không phải bảng NHNN."}
                ctx = _ctx_text(feat, pb, nsi, "LNH qua đêm lấy từ tin báo.")
            print("5) Debate tab ZALO")
            zalo_tab = run_tab(g, zalo_items, "zalo", ctx, a.max_topics)
            print("6) Tổng hợp sáng")
            if not web_tab.get("topics") and not zalo_tab.get("topics"):
                th = {"loi": "bỏ qua tổng hợp vì cả hai tab không có chủ đề (tránh AI viết khi không có tin)"}
            else:
                try:
                    th = tong_hop(g, ctx, web_tab, zalo_tab)
                except GeminiError as e:
                    th = {"loi": str(e)[:300]}
            result["web"].update(web_tab)
            result["zalo"].update(zalo_tab)
            result["tong_hop"] = th
            result["ai"] = {"models": g.models[:2], "so_luot": g.calls, "token_vao": g.tokens_in, "token_ra": g.tokens_out}
            if not web_tab.get("topics") and not zalo_tab.get("topics"):
                result["trang_thai_chay"] = "loi_ai"
            else:
                ok = not web_tab.get("loi") or web_tab.get("topics")
                result["trang_thai_chay"] = "dat" if ok and "loi" not in th else "mot_phan"
        except GeminiError as e:
            result["ai"] = {"loi": str(e)[:300]}
            result["trang_thai_chay"] = "loi_ai"
        # Dự phòng 12/10/2026: AI hỏng / hết lượt → vẫn có bản tin sáng dạng THÔ (tin thật, xếp bằng code, không nhận định).
        # Không cập nhật state nên lần gác 7h45 / 8h15 / 14h05 vẫn chạy lại bản AI đầy đủ.
        if not a.dry and (result["trang_thai_chay"] == "loi_ai" or not result["web"].get("topics")):
            from . import tin_tho  # noqa: PLC0415
            ly_do = (result.get("ai") or {}).get("loi") or result["web"].get("loi") or "AI không trả chủ đề"
            tho = tin_tho.dung_tab(web_items, a.max_topics, str(ly_do))
            if tho["topics"]:
                result["web"].update(tho)
                if result["trang_thai_chay"] == "loi_ai":
                    result["trang_thai_chay"] = "chi_tin_tho"
                print(f"  [dự phòng] bản tin thô: {len(tho['topics'])} chủ đề")

    done = now_vn()
    result["xong_luc"] = iso(done)
    result["chay_giay"] = round(time.time() - t0)
    result["dung_han"] = (done.hour, done.minute) <= HAN_CHOT
    write_json(out_dir / f"{today}.json", result)
    write_json(out_dir / "latest.json", result)
    idx = [x for x in read_json(out_dir / "index.json", []) if x.get("ngay") != today]
    idx.append({"ngay": today, "trang_thai_chay": result["trang_thai_chay"],
                "tong": (result.get("tong_hop") or {}).get("trang_thai"), "xong_luc": result["xong_luc"]})
    write_json(out_dir / "index.json", sorted(idx, key=lambda x: x["ngay"], reverse=True)[:400])
    if result["trang_thai_chay"] in ("dat", "mot_phan"):
        state["last_end"] = iso(end)
        write_json(data_dir / "state.json", state)
        seen |= {it["id"][1:] for it in web_items}
        write_json(data_dir / "seen.json", sorted(seen)[-5000:])
    print(json.dumps({k: result[k] for k in ("trang_thai_chay", "xong_luc", "chay_giay", "dung_han")}, ensure_ascii=False))
    return 0 if result["trang_thai_chay"] in ("dat", "mot_phan", "dry", "chi_tin_tho") else 2


if __name__ == "__main__":
    sys.exit(main())
