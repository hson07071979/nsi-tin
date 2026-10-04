"""AI debate, bản 3 (04-10-2026): mặc định chế độ GỌN — mỗi lô 1 lượt "hội đồng" (diễn giải + 3 phe + phản biện + trọng tài
trong cùng một câu trả lời) để vừa hạn mức Gemini miễn phí: ~9 lượt/ngày thay vì ~35. Đặt DEBATE_CHE_DO=day_du để quay lại bản 2.

Bản 2 (01-10-2026, theo góp ý anh Sơn: 'ngắn quá, không biết tin đó là cái gì, chỉ có 1 tin').

Mỗi tab:
  1. LỌC gom tối đa 15 chủ đề, XẾP HẠNG theo mức quan trọng, ghi lý do lọt top (1 lượt)
  2. ĐỌC BÀI (web) tải thân bài của các tin thuộc top chủ đề (không gọi AI)
  3. DIỄN GIẢI viết kỹ 'chuyện gì xảy ra' bằng lời dễ hiểu, số liệu chính, bối cảnh, thuật ngữ (lô 8 chủ đề/lượt)
  4. 3 PHE lạc quan / thận trọng / vĩ mô phân tích (3 × lô)
  5. PHẢN BIỆN chéo (3 × lô)
  6. TRỌNG TÀI chốt (lô)
15 chủ đề → 2 lô → ~17 lượt/tab, ~35 lượt/ngày (bản 2 — vượt hạn mức free từ 04/10/2026).
"""
from __future__ import annotations

import json
import os

from .fetch_web import fetch_bodies
from .gemini import Gemini, GeminiError

TOP_N = 15
LO = 8        # số chủ đề mỗi lượt gọi — tránh JSON dài bị cắt cụt
LO_GON = 5    # chế độ gọn: 5 chủ đề/lượt hội đồng (15 chủ đề → 3 lượt/tab)
CHE_DO = os.environ.get("DEBATE_CHE_DO", "gon")   # gon | day_du

NEN = """Bạn là thành viên hội đồng phân tích của Nguyễn Sơn Invest — hệ thống giao dịch cổ phiếu Việt Nam
theo CANSLIM/breakout (vũ trụ TOP thanh khoản HOSE/HNX, vào lệnh trong phiên bùng nổ, bộ thoát MA/van thời gian,
đèn thị trường Xanh/Vàng/Cam/Đỏ). Người đọc là anh Sơn: đang học sâu vĩ mô, cần hiểu TẬN GỐC chứ không cần câu khẩu hiệu.
Viết tiếng Việt, rõ ràng, có số liệu, câu đầy đủ chủ ngữ vị ngữ.

LUẬT BẮT BUỘC:
- Chỉ dùng thông tin trong dữ liệu được cung cấp + kiến thức kinh tế chung. KHÔNG bịa số liệu, KHÔNG bịa sự kiện.
  Con số nào không có trong dữ liệu thì không được viết như sự thật. Kiến thức nền thì nói rõ là kiến thức nền.
- Phân biệt SỰ KIỆN (đã xảy ra, có nguồn) và NHẬN ĐỊNH (ý kiến của ai đó, nhất là trong nhóm Zalo).
- Khung tư duy: Giá = Lợi nhuận × Định giá. Tin tác động qua 3 cửa: lợi nhuận DN / lãi suất chiết khấu /
  khẩu vị rủi ro–thanh khoản. BẤT NGỜ quan trọng hơn MỨC: mức cao đã nằm trong giá; cú sốc mới là tín hiệu.
- Vĩ mô → vi mô: đi theo chuỗi nhân quả từng mắt xích (ví dụ: tỷ giá căng → NHNN hút VND → LNH tăng →
  chi phí margin tăng → CTCK siết margin → cổ phiếu đầu cơ chịu bán). Nêu độ trễ nếu có.
- Vi mô → vi mô: tin một DN/ngành lan sang DN/ngành nào (đối thủ, chuỗi cung ứng, khách hàng, cùng nhóm vốn).
- Mọi cảnh báo vĩ mô là CỜ MỀM để soi tay, KHÔNG phải lệnh chặn mua; không đề xuất hạ cỡ lệnh thăm dò.
- Chỉ trả JSON đúng khuôn yêu cầu."""

PHE = {
    "lac_quan": ("Phe LẠC QUAN", "Tìm cơ hội thật: tin nào cải thiện lợi nhuận, hạ lãi suất chiết khấu hay kéo dòng tiền vào. "
                  "Chỉ ra ngành/mã hưởng lợi. Không cổ vũ mù quáng: nếu tin xấu thật thì nói là xấu."),
    "than_trong": ("Phe THẬN TRỌNG", "Tìm rủi ro, kịch bản xấu, điểm yếu trong lập luận lạc quan, tin chưa xác minh, "
                    "tin đồn trong nhóm Zalo, mâu thuẫn giữa các nguồn. Không bi quan mù quáng: tin tốt thật thì nói là tốt."),
    "vi_mo": ("CHIẾN LƯỢC GIA VĨ MÔ", "Đặt tin vào bối cảnh chu kỳ: lãi suất, tỷ giá, thanh khoản hệ thống, Fed/DXY, "
               "hàng hoá. Vẽ chuỗi truyền dẫn vĩ mô → ngành → DN và vi mô → vi mô. Đối chiếu với ảnh chụp số liệu và cờ vĩ mô mềm."),
}


def _items_block(items: list[dict], kind: str, limit_chars: int, body_chars: int = 0) -> str:
    lines = []
    for it in items:
        if kind == "web":
            t = f"[{it['id']}] ({it['src_name']}, {it.get('published') or 'không rõ giờ'}) {it['title']}"
            if it.get("summary"):
                t += f" — {it['summary'][:300]}"
            if body_chars and it.get("body"):
                t += f"\nNỘI DUNG BÀI: {it['body'][:body_chars]}"
        else:
            t = f"[{it['id']}] (nhóm {it['src_name']}, {it['published']}, {it['author']}): {it['text'][:900]}"
        lines.append(t)
    return "\n".join(lines)[:limit_chars]


def _chunks(xs, n=LO):
    return [xs[i:i + n] for i in range(0, len(xs), n)]


def triage(g: Gemini, items: list[dict], kind: str, max_topics: int = TOP_N) -> dict:
    ten = "tin trên web (báo, nguồn chính thức, quốc tế, web các nguồn)" if kind == "web" else \
          "tin nhắn 5 nhóm Zalo đầu tư (Money Noobs, FinSuccess, Lavender, Balance, Ánh Kem) — phần lớn là nhận định/ý kiến"
    prompt = f"""Dưới đây là {len(items)} {ten} trong cửa sổ từ sáng hôm qua tới 7h sáng nay.
Gom thành các CHỦ ĐỀ và XẾP HẠNG theo mức quan trọng với nhà đầu tư cổ phiếu Việt Nam HÔM NAY. Trả tối đa {max_topics}
chủ đề — càng nhiều chủ đề THẬT SỰ đáng đọc càng tốt, nhưng không nhồi tin rác cho đủ số.
Bỏ: quảng cáo, chào mời mở tài khoản, chuyện phiếm, tin không liên quan chứng khoán/kinh tế.
Tin trùng nội dung (nhiều báo đăng lại) gộp chung một chủ đề và ghi đủ item_ids.
Thứ tự ưu tiên: chính sách tiền tệ/lãi suất/tỷ giá VN > dòng tiền & thị trường chung > Fed/quốc tế ảnh hưởng VN >
ngành > doanh nghiệp lớn (VN30, nhóm TOP thanh khoản) > doanh nghiệp nhỏ.
Trích SỐ LIỆU nếu dữ liệu nêu rõ (không có thì null, không suy đoán).

Trả JSON:
{{"chu_de":[{{"id":"t1","hang":1,"tieu_de":"<tiêu đề rõ nghĩa, ≤ 14 chữ>","loai":"vi_mo_vn|quoc_te|chinh_sach|nganh|doanh_nghiep|thi_truong|tin_don",
"item_ids":["..."],"mot_dong":"<1 câu nói thẳng chuyện gì>","ly_do_top":"<vì sao xếp hạng này>",
"su_kien_hay_nhan_dinh":"su_kien|nhan_dinh|ca_hai","quan_trong":1-5,"ma_lien_quan":["VCB"],"nganh":["Ngân hàng"]}}],
"so_lieu":{{"lnh_qua_dem":null,"lnh_1_tuan":null,"omo_bom_rong_ty":null,"tin_phieu_ty":null,"ty_gia_trung_tam":null,
"khoi_ngoai_rong_ty":null,"ghi_chu":"<nguồn của từng số>"}},
"so_tin_bo_qua":0}}

DỮ LIỆU:
{_items_block(items, kind, 120000)}"""
    return g.json(NEN, prompt, temperature=0.2, max_out=16384)


def _topics_block(topics: list[dict], items_by_id: dict, kind: str, body_chars: int = 1500) -> str:
    out = []
    for t in topics:
        src = [items_by_id[i] for i in t.get("item_ids", []) if i in items_by_id][:4]
        ev = _items_block(src, kind, 9000, body_chars)
        extra = ""
        if t.get("chuyen_gi"):
            extra = f"\nDiễn giải: {t['chuyen_gi']}"
        out.append(f"### {t['id']}. {t['tieu_de']} (loại {t.get('loai')}, hạng {t.get('hang')})\n"
                   f"Một dòng: {t.get('mot_dong')}{extra}\nBằng chứng:\n{ev}")
    return "\n\n".join(out)


def explain(g: Gemini, topics: list[dict], by_id: dict, kind: str) -> dict:
    zalo_note = ("Đây là tin NHÓM ZALO: phân biệt rõ ai nói, nói gì, có dẫn nguồn không. Ý kiến cá nhân phải ghi là ý kiến."
                 if kind == "zalo" else "")
    prompt = f"""Nhiệm vụ: DIỄN GIẢI từng chủ đề cho anh Sơn đọc hiểu trọn vẹn mà không cần mở bài báo. {zalo_note}
- "chuyen_gi": 5–8 câu. Ai làm gì, khi nào, con số cụ thể bao nhiêu, so với trước thế nào, vì sao xảy ra.
  Viết như một nhà phân tích kể lại cho đồng nghiệp — không liệt kê cụt lủn, không lặp tiêu đề.
- "so_lieu_chinh": các con số quan trọng nhất có trong bài (dạng "Khối ngoại bán ròng: 1.010 tỷ đồng").
- "boi_canh": 2–3 câu: chuyện này nằm trong diễn biến nào (các tuần/tháng trước ra sao). Kiến thức nền thì ghi "(nền)".
- "vi_sao_quan_trong": 2–3 câu: tại sao nhà đầu tư cổ phiếu VN nên quan tâm.
- "thuat_ngu": giải thích thuật ngữ khó xuất hiện trong chủ đề (OMO, tín phiếu, LNH, DXY, nâng hạng, ...), tối đa 3.

CÁC CHỦ ĐỀ:
{_topics_block(topics, by_id, kind, 3000)}

Trả JSON: {{"dien_giai":[{{"id":"t1","chuyen_gi":"...","so_lieu_chinh":["..."],"boi_canh":"...",
"vi_sao_quan_trong":"...","thuat_ngu":[{{"tu":"...","nghia":"..."}}]}}]}}"""
    return g.json(NEN, prompt, temperature=0.3, max_out=24576)


KHUON_PHE = """{"phan_tich":[{"id":"t1","nhan_dinh":"tot|xau|trung_tinh","do_manh":1-3,
"lap_luan":"<4-6 câu, có số liệu>","chuoi_truyen_dan":["<mắt xích 1 → mắt xích 2 → ...>"],
"anh_huong":[{"ten":"<ngành hoặc mã>","chieu":"+|-","ly_do":"<ngắn>"}],
"rui_ro":"<rủi ro chính>","do_tin_cay":0-100}]}"""


def round1(g: Gemini, phe: str, ctx: str, topics_txt: str) -> dict:
    ten, vai = PHE[phe]
    prompt = f"""Vai của bạn: {ten}. {vai}

BỐI CẢNH (số liệu định lượng sáng nay + cờ vĩ mô mềm + hệ thống):
{ctx}

CÁC CHỦ ĐỀ:
{topics_txt}

Phân tích TỪNG chủ đề. Trả JSON: {KHUON_PHE}"""
    return g.json(NEN, prompt, temperature=0.5, max_out=16384)


def round2(g: Gemini, phe: str, ctx: str, topics_txt: str, r1: dict) -> dict:
    ten, vai = PHE[phe]
    others = {k: v for k, v in r1.items() if k != phe}
    prompt = f"""Vai của bạn: {ten}. {vai}
Đây là VÒNG PHẢN BIỆN. Đọc phân tích của hai phe còn lại, chỉ ra chỗ họ sai/thiếu, và tự sửa nhận định của mình
nếu bị thuyết phục (được đổi ý — đổi ý có lý do là điểm cộng).

BỐI CẢNH:
{ctx}

CÁC CHỦ ĐỀ:
{topics_txt}

NHẬN ĐỊNH VÒNG 1 CỦA BẠN:
{json.dumps(r1.get(phe, {}), ensure_ascii=False)[:15000]}

NHẬN ĐỊNH VÒNG 1 CỦA HAI PHE KIA:
{json.dumps(others, ensure_ascii=False)[:30000]}

Trả JSON: {{"phan_bien":[{{"id":"t1","phan_bac":"<phản bác cụ thể, nêu phe nào, 2-3 câu>","nhan_dinh_cuoi":"tot|xau|trung_tinh",
"doi_y":true|false,"ly_do_doi_y":"<nếu có>"}}]}}"""
    return g.json(NEN, prompt, temperature=0.4, max_out=12288)


def judge(g: Gemini, ctx: str, topics_txt: str, r1: dict, r2: dict) -> dict:
    prompt = f"""Bạn là TRỌNG TÀI của hội đồng. Đọc toàn bộ tranh luận và chốt cho từng chủ đề. Cân lập luận, không đếm phiếu.
Tin chỉ có trong nhóm Zalo mà không có nguồn xác nhận thì phải ghi xac_minh="tin_don" và hạ độ tin cậy.
"vi_mo_to_vi_mo" và "vi_mo_vi_mo": viết thành đoạn 2–4 câu giải thích CƠ CHẾ, không chỉ mũi tên.
"can_trong" phải là việc làm cụ thể (ví dụ: "không mua đuổi nhóm CK trong 3 phiên; soi tỷ lệ margin/VCSH trước khi vào"),
không viết chung chung kiểu "cần theo dõi thêm".
"kiem_chung_sau" = dấu hiệu quan sát được ở T+1/T+5 cho biết nhận định đúng hay sai (để chấm điểm sau).
"nganh_ma": ưu tiên MÃ cổ phiếu cụ thể (3 chữ cái) khi có cơ sở, vì mã mới chấm điểm được bằng giá thật.

BỐI CẢNH:
{ctx}

CÁC CHỦ ĐỀ:
{topics_txt}

VÒNG 1: {json.dumps(r1, ensure_ascii=False)[:40000]}
PHẢN BIỆN: {json.dumps(r2, ensure_ascii=False)[:25000]}

Trả JSON:
{{"ket_luan":[{{"id":"t1","danh_gia":"tot|xau|trung_tinh","muc_do":"thap|vua|cao",
"vi_mo_to_vi_mo":"<đoạn 2-4 câu, hoặc 'không áp dụng'>",
"vi_mo_vi_mo":"<đoạn 2-4 câu, hoặc 'không áp dụng'>",
"nganh_ma":[{{"ten":"<mã hoặc ngành>","chieu":"+|-","ly_do":"<ngắn>"}}],
"rui_ro":["<rủi ro 1>","<rủi ro 2>"],
"can_trong":"<nên cẩn trọng như nào — cụ thể>",
"hanh_dong":"khong_hanh_dong|theo_doi|than_trong|han_che_rui_ro|co_hoi",
"xac_minh":"da_xac_minh|mot_nguon|tin_don","dong_thuan":"<phe nào thuyết phục hơn, vì sao — 2 câu>",
"lien_he_he_thong":"<liên hệ đèn thị trường / cờ vĩ mô / mã đang cầm — chỉ là gợi ý soi tay>",
"kiem_chung_sau":"<dấu hiệu T+1/T+5>","do_tin_cay":0-100}}],
"tong_ket":"<1-2 câu cho lô này>"}}"""
    return g.json(NEN, prompt, temperature=0.2, max_out=24576)


def hoi_dong(g: Gemini, ctx: str, topics: list[dict], by_id: dict, kind: str) -> dict:
    """Chế độ gọn: MỘT lượt làm trọn diễn giải + 3 phe + phản biện + trọng tài cho cả lô."""
    zalo_note = ("Đây là tin NHÓM ZALO: phân biệt rõ ai nói, nói gì, có dẫn nguồn không. Ý kiến cá nhân phải ghi là ý kiến."
                 if kind == "zalo" else "")
    vai = "\n".join(f"- {k} = {ten}: {mo_ta}" for k, (ten, mo_ta) in PHE.items())
    prompt = f"""Bạn điều phối hội đồng phân tích. Với TỪNG chủ đề, làm đủ 4 bước TRONG MỘT câu trả lời. {zalo_note}
B1 DIỄN GIẢI cho anh Sơn đọc hiểu mà không cần mở bài báo:
  "chuyen_gi" 4–6 câu (ai làm gì, khi nào, số liệu cụ thể, so với trước, vì sao); "so_lieu_chinh" các con số quan trọng;
  "boi_canh" 2 câu (kiến thức nền thì ghi "(nền)"); "vi_sao_quan_trong" 2 câu; "thuat_ngu" tối đa 3 thuật ngữ khó.
B2 BA PHE phân tích ĐỘC LẬP, mỗi phe giữ đúng vai, không phe nào được nhại phe khác:
{vai}
  Mỗi phe: nhan_dinh, do_manh 1-3, lap_luan 2–4 câu có số liệu, chuoi_truyen_dan, anh_huong, rui_ro, do_tin_cay 0-100.
B3 PHẢN BIỆN: mỗi phe chỉ ra chỗ sai/thiếu cụ thể của phe khác (nêu tên phe), được đổi ý nếu bị thuyết phục.
B4 TRỌNG TÀI chốt — cân lập luận, không đếm phiếu. Tin chỉ có trong nhóm Zalo mà không có nguồn xác nhận thì
  xac_minh="tin_don" và hạ độ tin cậy. "vi_mo_to_vi_mo"/"vi_mo_vi_mo" là đoạn 2–3 câu giải thích CƠ CHẾ.
  "can_trong" là việc làm cụ thể, không viết chung chung. "kiem_chung_sau" = dấu hiệu T+1/T+5 để chấm đúng/sai.
  "nganh_ma" ưu tiên MÃ cổ phiếu 3 chữ cái khi có cơ sở.

BỐI CẢNH (số liệu định lượng sáng nay + cờ vĩ mô mềm + hệ thống):
{ctx}

CÁC CHỦ ĐỀ:
{_topics_block(topics, by_id, kind, 2500)}

Trả JSON:
{{"chu_de":[{{"id":"t1","chuyen_gi":"...","so_lieu_chinh":["..."],"boi_canh":"...","vi_sao_quan_trong":"...",
"thuat_ngu":[{{"tu":"...","nghia":"..."}}],
"phe":{{"lac_quan":{{"nhan_dinh":"tot|xau|trung_tinh","do_manh":1,"lap_luan":"...","chuoi_truyen_dan":["a → b → c"],
"anh_huong":[{{"ten":"<ngành hoặc mã>","chieu":"+|-","ly_do":"<ngắn>"}}],"rui_ro":"...","do_tin_cay":60}},
"than_trong":{{...cùng khuôn...}},"vi_mo":{{...cùng khuôn...}}}},
"phan_bien":{{"lac_quan":{{"phan_bac":"<2 câu, nêu phe nào>","nhan_dinh_cuoi":"tot|xau|trung_tinh","doi_y":false,"ly_do_doi_y":""}},
"than_trong":{{...}},"vi_mo":{{...}}}},
"danh_gia":"tot|xau|trung_tinh","muc_do":"thap|vua|cao","vi_mo_to_vi_mo":"...","vi_mo_vi_mo":"...",
"nganh_ma":[{{"ten":"...","chieu":"+|-","ly_do":"..."}}],"rui_ro":["..."],"can_trong":"...",
"hanh_dong":"khong_hanh_dong|theo_doi|than_trong|han_che_rui_ro|co_hoi","xac_minh":"da_xac_minh|mot_nguon|tin_don",
"dong_thuan":"<phe nào thuyết phục hơn, vì sao — 2 câu>","lien_he_he_thong":"<gợi ý soi tay>",
"kiem_chung_sau":"...","do_tin_cay":0}}],
"tong_ket":"<1-2 câu cho lô này>"}}"""
    return g.json(NEN, prompt, temperature=0.35, max_out=32768)


def tong_hop(g: Gemini, ctx: str, web: dict, zalo: dict) -> dict:
    def brief(tab):
        return [{"hang": t.get("hang"), "tieu_de": t.get("tieu_de"), "chuyen_gi": (t.get("chuyen_gi") or "")[:400],
                 **{k: t.get(k) for k in ("danh_gia", "muc_do", "hanh_dong", "xac_minh", "can_trong")}}
                for t in tab.get("topics", [])]
    prompt = f"""Tổng hợp buổi sáng cho anh Sơn (đọc lúc 8h, trước phiên). Đối chiếu tab WEB và tab ZALO: tin Zalo nào đã có
báo/nguồn chính thức xác nhận, tin nào chỉ là đồn, hai bên có mâu thuẫn không.
"ba_dieu_can_biet": mỗi điều 2 câu (chuyện gì + nghĩa là gì với thị trường), không viết cụt.
Thêm MỘT bài luyện vĩ mô dựa trên tin hôm nay (tình huống + câu hỏi + đáp án có chuỗi nhân quả), để anh luyện phản xạ
kiểu "lãi suất cao bình thường thì không làm gì, LNH tăng sốc thì hạn chế rủi ro ra sao".

BỐI CẢNH: {ctx}
TAB WEB: {json.dumps(brief(web), ensure_ascii=False)[:20000]}
TAB ZALO: {json.dumps(brief(zalo), ensure_ascii=False)[:20000]}

Trả JSON: {{"trang_thai":"tot|xau|trung_tinh","tieu_de":"<1 dòng>","ba_dieu_can_biet":["...","...","..."],
"doi_chieu_web_zalo":["<điểm đối chiếu>"],"viec_hom_nay":["<việc cụ thể trước/trong phiên>"],
"canh_bao":"<nếu có, không thì rỗng>",
"bai_luyen_vi_mo":{{"tinh_huong":"...","cau_hoi":"...","dap_an":"...","chuoi_nhan_qua":["..."],"luat_lien_quan":"<id cờ trong sổ luật nếu có>"}}}}"""
    return g.json(NEN, prompt, temperature=0.3, max_out=8192)


def _pick(lst, key, tid):
    return next((x for x in (lst or []) if x.get(key) == tid), None)


def _nguon(by_id: dict, t: dict) -> list[dict]:
    return [{"id": i, "title": by_id[i].get("title") or "", "text": by_id[i].get("text", "")[:900],
             "author": by_id[i].get("author"), "summary": by_id[i].get("summary", ""),
             "url": by_id[i].get("url"), "src_name": by_id[i]["src_name"],
             "published": by_id[i].get("published")}
            for i in t.get("item_ids", []) if i in by_id]


def run_tab(g: Gemini, items: list[dict], kind: str, ctx: str, max_topics: int = TOP_N) -> dict:
    """Chạy trọn một tab. Lỗi giữa chừng thì trả phần đã có + ghi lỗi (không bao giờ ném ra ngoài)."""
    tab: dict = {"kind": kind, "n_items": len(items), "topics": [], "loi": None}
    if not items:
        tab["loi"] = "không có tin trong cửa sổ"
        return tab
    by_id = {it["id"]: it for it in items}
    try:
        tri = triage(g, items, kind, max_topics)
        topics = [t for t in tri.get("chu_de", []) if t.get("item_ids")]
        topics.sort(key=lambda t: (int(t.get("hang") or 99), -int(t.get("quan_trong") or 0)))
        topics = topics[:max_topics]
        for i, t in enumerate(topics, 1):
            t["hang"] = i
            t["id"] = f"t{i}"   # id ổn định theo hạng
        tab["so_lieu"] = tri.get("so_lieu") or {}
        tab["topics"] = [dict(t) for t in topics]
        tab["so_tin_bo_qua"] = tri.get("so_tin_bo_qua")
        if not topics:
            tab["loi"] = "AI không tìm thấy chủ đề đáng kể"
            return tab
        if kind == "web":
            ids = [i for t in topics for i in t["item_ids"][:3]]
            tab["so_bai_doc_duoc"] = fetch_bodies(items, ids, max_n=45)

        if CHE_DO != "day_du":
            # chế độ gọn: 1 lượt/lô
            for lo in _chunks(tab["topics"], LO_GON):
                try:
                    h = hoi_dong(g, ctx, lo, by_id, kind)
                except GeminiError as e:
                    tab["loi_hoi_dong"] = str(e)[:200]
                    if "429" in str(e):
                        break   # hết hạn mức: các lô sau cũng sẽ hỏng, dừng cho đỡ tốn thời gian
                    continue
                tab.setdefault("tong_ket_lo", []).append(h.get("tong_ket"))
                for t in lo:
                    k = dict(_pick(h.get("chu_de"), "id", t["id"]) or {})
                    phe = k.pop("phe", None) or {}
                    pb = k.pop("phan_bien", None) or {}
                    t.update({kk: vv for kk, vv in k.items() if kk != "id"})
                    t["phe"] = {p: phe.get(p) for p in PHE}
                    t["phan_bien"] = {p: pb.get(p) for p in PHE if isinstance(pb.get(p), dict)}
        else:
            # 3. diễn giải
            for lo in _chunks(tab["topics"]):
                try:
                    ex = explain(g, lo, by_id, kind)
                    for t in lo:
                        d = _pick(ex.get("dien_giai"), "id", t["id"])
                        if d:
                            t.update({k: v for k, v in d.items() if k != "id"})
                except GeminiError as e:
                    tab["loi_dien_giai"] = str(e)[:200]

            # 4–6. tranh luận theo lô
            for lo in _chunks(tab["topics"]):
                ttxt = _topics_block(lo, by_id, kind)
                r1 = {p: round1(g, p, ctx, ttxt) for p in PHE}
                r2 = {}
                for p in PHE:
                    try:
                        r2[p] = round2(g, p, ctx, ttxt, r1)
                    except GeminiError as e:
                        r2[p] = {"loi": str(e)[:200]}
                j = judge(g, ctx, ttxt, r1, r2)
                tab.setdefault("tong_ket_lo", []).append(j.get("tong_ket"))
                for t in lo:
                    k = _pick(j.get("ket_luan"), "id", t["id"]) or {}
                    t.update({kk: vv for kk, vv in k.items() if kk != "id"})
                    t["phe"] = {p: _pick(r1[p].get("phan_tich"), "id", t["id"]) for p in PHE}
                    t["phan_bien"] = {p: _pick(r2[p].get("phan_bien"), "id", t["id"]) for p in PHE if isinstance(r2.get(p), dict)}
        for t in tab["topics"]:
            t["nguon"] = _nguon(by_id, t)
        xs = [t.get("danh_gia") for t in tab["topics"] if t.get("danh_gia")]
        tab["dem"] = {k: xs.count(k) for k in ("tot", "xau", "trung_tinh")}
    except GeminiError as e:
        tab["loi"] = f"AI lỗi: {str(e)[:300]}"
        for t in tab["topics"]:
            t.setdefault("nguon", _nguon(by_id, t))
    return tab
