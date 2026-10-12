"""Gọi Gemini cho NSI Daily Market.

Hai cách chạy để so (anh Sơn chọn 12/10/2026), cùng một bộ FACT:
  cach_2_buoc : lượt 1 phân tích 9 tầng → lượt 2 viết lời thoại từ bản phân tích
  cach_1_luot : một lượt vừa phân tích vừa viết
Trang hiện "Bản 1 / Bản 2" xáo ngẫu nhiên; cách chạy chỉ lộ khi bấm "Xem cách chạy".
"""
from __future__ import annotations

import json
import os
import random
import re
import time

import requests

from tin.gemini import API, Gemini, GeminiError, parse_json_loose, rank_models

from . import prompts

_PRO = re.compile(r"^gemini-(\d+(?:\.\d+)?)-pro(?:-preview(?:-[\w-]+)?)?(?:-\d{2,})?$")


def pick_models(key: str) -> list[str]:
    """Ưu tiên bản pro mới nhất (viết hay hơn) rồi tới flash. Pro hết hạn mức free → tự rơi về flash."""
    env = os.environ.get("DAILY_MODELS")
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    have: list[str] = []
    try:
        r = requests.get(f"{API}/models", params={"key": key, "pageSize": 1000}, timeout=20)
        have = [m["name"].split("/")[-1] for m in r.json().get("models", [])
                if "generateContent" in m.get("supportedGenerationMethods", [])]
    except Exception:  # noqa: BLE001
        pass
    pros = []
    for n in have:
        m = _PRO.match(n)
        if m and not any(b in n for b in ("image", "tts", "audio", "live", "exp")):
            pros.append(((-float(m.group(1)), "preview" in n, len(n)), n))
    chosen = [n for _, n in sorted(pros)[:1]] + rank_models(have)[:6]   # flash + flash-lite: mỗi model một hạn mức riêng
    return chosen or ["gemini-2.5-flash"]


class GeminiDaily(Gemini):
    """Như Gemini của nsi-tin, thêm 3 thứ cho việc viết script dài:
    - nghĩ kỹ hơn (DAILY_THINKING, mặc định medium);
    - model nào hỏng cứng (hết hạn mức ngày, 4xx) thì gạch khỏi danh sách cho cả lần chạy → không đốt thời gian thử lại;
    - ghi nhật ký từng lượt (model, giây, lỗi) để trang /daily và log Actions thấy được.
    """

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.chet: set[str] = set()
        self.nhat_ky: list[str] = []
        self.han: float | None = None          # mốc giờ (time.time()) phải dừng gọi AI
        self.bi_429 = 0                        # số lần bị báo hết hạn mức trong lần chạy (model tốt nhất)

    def _stream(self, model: str, body: dict):
        """Gọi dạng stream (SSE) để kết nối không bị cắt khi lời thoại dài (bản thường bị ngắt ở ~270 giây).
        Trả (mã HTTP, chữ, usage, finishReason, đối tượng lỗi có .status_code/.text)."""
        url = f"{API}/models/{model}:streamGenerateContent"
        with requests.post(url, params={"key": self.key, "alt": "sse"}, json=body, stream=True,
                           timeout=(20, 300)) as r:
            if r.status_code != 200:
                class _E:
                    status_code = r.status_code
                    text = r.text
                return r.status_code, "", {}, None, _E()
            r.encoding = "utf-8"               # SSE không ghi charset → requests mặc định latin-1 → hỏng dấu
            parts, usage, fin = [], {}, None
            t_end = time.time() + 600
            for line in r.iter_lines(decode_unicode=True):
                if time.time() > t_end:
                    raise requests.ReadTimeout("quá 10 phút cho một lượt")
                if not line or not line.startswith("data:"):
                    continue
                try:
                    j = json.loads(line[5:].strip())
                except ValueError:
                    continue
                if j.get("usageMetadata"):
                    usage = j["usageMetadata"]
                for c in j.get("candidates") or []:
                    fin = c.get("finishReason") or fin
                    for p in (c.get("content") or {}).get("parts") or []:
                        if p.get("text") and not p.get("thought"):
                            parts.append(p["text"])
            return 200, "".join(parts), usage, fin, None

    def _thinking(self, model: str) -> dict:  # type: ignore[override]
        lv = getattr(self, "muc_nghi", None) or os.environ.get("DAILY_THINKING", "medium")
        if re.match(r"gemini-[3-9]", model):
            return {"thinkingLevel": lv}
        if model.startswith("gemini-2.5"):
            return {"thinkingBudget": {"low": 1024, "medium": 4096, "high": 8192}.get(lv, 4096)}
        return {}

    def json(self, system: str, prompt: str, *, temperature: float = 0.4, max_out: int = 8192,  # noqa: C901
             models: list[str] | None = None) -> dict:
        errs: dict[str, str] = {}
        for model in [m for m in (models or self.models) if m not in self.chet]:
            gen = {"temperature": temperature, "maxOutputTokens": 65536, "responseMimeType": "application/json"}
            th = self._thinking(model)
            if th and model not in self.no_thinking_cfg:
                gen["thinkingConfig"] = th
            body = {"systemInstruction": {"parts": [{"text": system}]},
                    "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
            for attempt in range(3):
                if self.han and time.time() > self.han:
                    raise GeminiError("hết quỹ thời gian của lần chạy")
                self._wait()
                t0 = time.time()
                try:
                    st, text, u, fin, raw = self._stream(model, body)
                except requests.RequestException as e:
                    errs[model] = f"mạng: {str(e)[:120]}"
                    self._log(model, t0, errs[model])
                    time.sleep(5 * (attempt + 1))
                    continue
                if st == 200:
                    self.tokens_in += u.get("promptTokenCount", 0)
                    self.tokens_out += u.get("candidatesTokenCount", 0)
                    if not text:
                        errs[model] = f"trả rỗng ({fin})"
                        self._log(model, t0, errs[model])
                        break
                    out = parse_json_loose(text)
                    if out is not None:
                        self.calls += 1
                        out["_model"] = model
                        self._log(model, t0, f"ok, ra {u.get('candidatesTokenCount', 0)} token")
                        return out
                    errs[model] = f"JSON hỏng (finishReason={fin}, {len(text)} ký tự)"
                    self._log(model, t0, errs[model])
                    gen["temperature"] = 0.2
                    continue
                r = raw
                msg = r.text[:200].replace("\n", " ")
                errs[model] = f"HTTP {r.status_code}: {msg}"
                self._log(model, t0, errs[model])
                if r.status_code == 400 and "thinking" in r.text.lower() and "thinkingConfig" in gen:
                    self.no_thinking_cfg.add(model)
                    gen.pop("thinkingConfig", None)
                    continue
                if r.status_code == 429:
                    if model != "gemini-2.5-flash" and "-pro" not in model:
                        self.bi_429 += 1
                    if "PerDay" in r.text or "per day" in r.text.lower() or "limit: 0" in r.text:
                        self.chet.add(model)          # hết hạn mức ngày / không có hạn mức free → bỏ hẳn
                        break
                    m = re.search(r'"retryDelay":\s*"(\d+)s"', r.text)
                    time.sleep(min(int(m.group(1)) + 2 if m else 20 * (attempt + 1), 75))
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(8 * (attempt + 1))
                    continue
                self.chet.add(model)                  # 400/403/404: model không dùng được với key này
                break
        raise GeminiError(" | ".join(f"{k}: {v}" for k, v in errs.items()) or "không gọi được Gemini")

    def _log(self, model: str, t0: float, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {model} {round(time.time() - t0)}s — {msg}"
        self.nhat_ky.append(line)
        print("  [gemini]", line, flush=True)


def tang_model(g: GeminiDaily) -> tuple[list[str], list[str]]:
    """(13/10) Sơn chốt: LỜI THOẠI phải do model tốt nhất viết. Model "tốt" = bản pro (nếu có hạn mức) + 2 bản flash
    (không lite) có số phiên bản cao nhất. Trả (tot, du_phong)."""
    flash = [m for m in g.models if "-pro" not in m and "lite" not in m]
    pro = [m for m in g.models if "-pro" in m]
    tot = pro + flash[:2]
    return tot, [m for m in g.models if m not in tot]


def thu_tu_phan_tich(g: GeminiDaily) -> list[str]:
    """Bước phân tích dùng model tốt thứ 2 trước, để lượt của model tốt nhất dành cho lời thoại."""
    tot, du = tang_model(g)
    flash_tot = [m for m in tot if "-pro" not in m]
    if len(flash_tot) >= 2:
        return [flash_tot[1], flash_tot[0]] + du
    return tot + du


def con_model_tot(g: GeminiDaily) -> bool:
    return any(m not in g.chet for m in tang_model(g)[0] if "-pro" not in m)


def new_client() -> GeminiDaily:
    key = os.environ.get("GEMINI_API_KEY", "")
    if not key:
        raise GeminiError("thiếu GEMINI_API_KEY")
    return GeminiDaily(key=key, rpm=int(os.environ.get("GEMINI_RPM", 8)), models=pick_models(key))


# ------------------------------------------------------------------ kiểm khuôn
def _so_chu(script: dict) -> int:
    return sum(len(str(p.get("loi_thoai", "")).split()) for p in (script or {}).get("phan", []) or [])


THAY_CO_DINH = [
    (re.compile(r"\bTB ?20\b"), "trung bình 20 phiên"), (re.compile(r"\bTB ?5\b"), "trung bình 5 phiên"),
    (re.compile(r"\s*\(?\b(FACT|OBSERVATION|INTERPRETATION|HYPOTHESIS|CONFIRMATION)\b\)?:?", re.I), ""),
    (re.compile(r"(trong|theo|từ) (bộ )?dữ liệu FACT", re.I), r"\1 dữ liệu"), (re.compile(r"\bFACT\b"), "dữ liệu"),
    (re.compile(r"sổ dự báo", re.I), "những mốc em đã nói"),
    (re.compile(r"chắc chắn sẽ", re.I), "nhiều khả năng sẽ"),
    # độ mạnh vùng: bảng điểm nội bộ → lời nói
    (re.compile(r"\s*\(?★+\)?"), ""),
    (re.compile(r"\b5 sao\b"), "rất mạnh"), (re.compile(r"\b4 sao\b"), "mạnh"),
    (re.compile(r"\b3 sao\b"), "khá mạnh"), (re.compile(r"\b[12] sao\b"), "vừa"),
    # số chỉ số hàng nghìn đọc tròn: 1.701,14 → 1.701
    (re.compile(r"\b(\d{1,2}\.\d{3}),\d{1,2}\b"), r"\1"),
    (re.compile(r"[ \t]{2,}"), " "),
]


def lam_sach(script: dict) -> dict:
    """Làm sạch chắc chắn bằng code (không tốn lượt AI): bỏ nhãn nội bộ, đổi viết tắt sang lời nói."""
    if not isinstance(script, dict):
        return script

    def sach(t):
        t = str(t or "")
        for rx, rep in THAY_CO_DINH:
            t = rx.sub(rep, t)
        # viết hoa lại chữ đầu câu sau khi thay
        return re.sub(r"(^|[.!?]\s+)(\w)", lambda m: m.group(1) + m.group(2).upper(), t.strip())

    for p in script.get("phan") or []:
        p["loi_thoai"] = sach(p.get("loi_thoai"))
    for t in script.get("tiktok") or []:
        if isinstance(t, dict):
            t["loi_thoai"] = sach(t.get("loi_thoai"))
    return script


def check_script(script: dict) -> list[str]:
    loi = []
    if not isinstance(script, dict) or not script.get("phan"):
        return ["thiếu lời thoại"]
    n = _so_chu(script)
    if n < 2400:
        loi.append(f"lời thoại ngắn ({n} chữ, cần ~3.000 cho 20 phút)")
    tk = script.get("tiktok") or []
    if len(tk) < 3:
        loi.append(f"chỉ có {len(tk)} clip TikTok")
    # "khối ngoại mua vào/bán ra" là mô tả hợp lệ nên không cấm; cấm lời khuyên hành động và độ chắc tuyệt đối
    cam = re.compile(r"(?<!\w)(giải ngân|margin|nên mua|nên bán|mua ngay|bán ngay|all[- ]in|canh mua|canh bán)(?!\w)",
                     re.I)
    for p in script["phan"]:
        m = cam.search(str(p.get("loi_thoai", "")))
        if m:
            loi.append(f"phần '{p.get('ten')}' có cụm cấm: '{m.group(0)}'")
    return loi


def check_phan_tich(pt: dict) -> list[str]:
    need = ["signature", "ky_thuat_chi_so", "regime", "nganh", "luan_diem_chinh", "phien_toi"]
    return [f"phân tích thiếu '{k}'" for k in need if not (pt or {}).get(k)]


MUC_TIEU_CHU = [("hook", 80), ("đối chiếu", 80), ("thế giới", 300), ("thị trường việt nam", 450), ("index", 220),
                ("bản đồ", 300), ("quét ngành", 1100), ("mã đáng nói", 400), ("regime", 150)]


def _muc_tieu(ten: str) -> int | None:
    t = (ten or "").lower()
    return next((n for k, n in MUC_TIEU_CHU if k in t), None)


def _sua_script(g: GeminiDaily, script: dict, loi: list[str], fc: dict) -> dict:
    """Sửa có chọn lọc: chỉ viết lại các PHẦN hụt chữ hoặc dính cụm cấm, rồi ghép vào bản cũ.
    Ra ít chữ hơn viết lại cả bài → nhanh, ít hỏng JSON, đỡ tốn hạn mức. Sắp hết quỹ thời gian thì bỏ qua."""
    if g.han and time.time() > g.han - 6 * 60:
        return script
    cam = re.compile(r"(?<!\w)(giải ngân|margin|nên mua|nên bán|mua ngay|bán ngay|all[- ]in|canh mua|canh bán)(?!\w)",
                     re.I)
    can_sua = []
    for p in script.get("phan") or []:
        n = len(str(p.get("loi_thoai", "")).split())
        mt = _muc_tieu(p.get("ten", ""))
        ly = []
        if mt and n < 0.7 * mt:
            ly.append(f"mới {n} chữ, cần khoảng {mt} chữ")
        if cam.search(str(p.get("loi_thoai", ""))):
            ly.append("có câu hô hào mua/bán hoặc nói tỷ trọng/margin")
        if ly:
            can_sua.append({"ten": p.get("ten"), "ly_do": "; ".join(ly), "loi_thoai_cu": p.get("loi_thoai")})
    if not can_sua:
        return script
    g.muc_nghi = "medium"
    khuon = {"phan": [{"ten": "giữ đúng tên phần", "loi_thoai": "lời thoại mới đầy đủ", "chen_hinh": ""}]}
    p = (f"Các PHẦN lời thoại dưới đây chưa đạt. Viết lại ĐÚNG các phần này (giữ tên phần), đủ độ dài yêu cầu, cùng giọng, "
         f"không lặp ý các phần khác. Quét ngành thì đi qua mọi nhóm trong rổ, nhóm có chuyện thì nhiều mã hơn. "
         f"Thay câu hô hào bằng mức tham chiếu có điều kiện (mốc theo dõi / SL / mục tiêu). Số liệu chỉ lấy từ FACT.\n"
         f"PHẦN CẦN SỬA: {prompts._j(can_sua)}\nFACT: {prompts._j(fc)}\n{prompts.MAU_GIONG}\n"
         f"Trả JSON đúng khuôn: {prompts._j(khuon)}")
    try:
        out = g.json(prompts.LUAT, p, temperature=0.7, models=tang_model(g)[0])
    except GeminiError:
        return script
    moi = {str(x.get("ten", "")).strip().lower(): x for x in out.get("phan") or [] if x.get("loi_thoai")}
    sc = dict(script)
    sc["phan"] = []
    for ph in script.get("phan") or []:
        x = moi.get(str(ph.get("ten", "")).strip().lower())
        cu = str(ph.get("loi_thoai", ""))
        if x and (len(str(x["loi_thoai"]).split()) >= len(cu.split()) * 0.9
                  or (cam.search(cu) and not cam.search(str(x["loi_thoai"])) and len(str(x["loi_thoai"]).split()) >= len(cu.split()) * 0.75)):
            ph = {**ph, "loi_thoai": x["loi_thoai"], **({"chen_hinh": x["chen_hinh"]} if x.get("chen_hinh") else {})}
        sc["phan"].append(ph)
    return sc


# ------------------------------------------------------------------ hai cách chạy
def cach_2_buoc(g: GeminiDaily, fc: dict, so: dict) -> dict:
    res: dict = {"cach": "cach_2_buoc", "loi": []}
    g.muc_nghi = None                       # phân tích: nghĩ theo DAILY_THINKING (medium)
    try:
        pt = g.json(prompts.LUAT, prompts.prompt_phan_tich(fc, so), temperature=0.4)
    except GeminiError as e:
        res["loi"].append(f"bước phân tích: {str(e)[:300]}")
        return res
    res["phan_tich"] = pt
    res["loi"] += check_phan_tich(pt)
    g.muc_nghi = "low"                      # viết lời thoại từ bản phân tích đã chốt: không cần nghĩ lâu
    try:
        sc = g.json(prompts.LUAT, prompts.prompt_script_tu_phan_tich(fc, so, pt), temperature=0.75)
    except GeminiError as e:
        res["loi"].append(f"bước viết lời thoại: {str(e)[:300]}")
        return res
    sc = lam_sach(sc)
    loi = check_script(sc)
    if loi:
        sc = lam_sach(_sua_script(g, sc, loi, fc))
        loi = check_script(sc)
    res["script"] = sc
    res["loi"] += loi
    res["model"] = pt.get("_model")
    return res


def cach_1_luot(g: GeminiDaily, fc: dict, so: dict) -> dict:
    res: dict = {"cach": "cach_1_luot", "loi": []}
    g.muc_nghi = None
    try:
        out = g.json(prompts.LUAT, prompts.prompt_mot_luot(fc, so), temperature=0.65, models=tang_model(g)[0])
    except GeminiError as e:
        res["loi"].append(str(e)[:300])
        return res
    res["phan_tich"] = out.get("phan_tich") or {}
    sc = out.get("script") or {}
    res["loi"] += check_phan_tich(res["phan_tich"])
    sc = lam_sach(sc)
    loi = check_script(sc)
    if loi:
        sc = lam_sach(_sua_script(g, sc, loi, fc))
        loi = check_script(sc)
    res["script"] = sc
    res["loi"] += loi
    res["model"] = out.get("_model")
    return res


CACH = {"cach_2_buoc": cach_2_buoc, "cach_1_luot": cach_1_luot}


def con_luot(g: GeminiDaily, phut_du_tru: float = 5) -> bool:
    """Còn model sống và còn thời gian thì mới gọi tiếp."""
    if not [m for m in g.models if m not in g.chet]:
        return False
    return not (g.han and time.time() > g.han - phut_du_tru * 60)


def chay_hai_ban(fc: dict, so: dict, phut_toi_da: float = 30, cach: list[str] | None = None,
                 facts: dict | None = None) -> tuple[list[dict], dict]:
    """Chạy theo THỨ TỰ ƯU TIÊN (anh Sơn chốt 12/10/2026):
      UT1  phân tích số liệu  — AI (bước 1 của cách 2 bước); AI hỏng hết thì dựng bằng code (khong_ai), luôn có bản này
      UT2  viết lời thoại từ bản phân tích — chỉ khi còn lượt
      UT3  cách 1 lượt (để so) — chỉ khi còn lượt và còn thời gian
    """
    from . import khong_ai  # noqa: PLC0415
    ds = [c for c in (cach or list(CACH)) if c in CACH] or list(CACH)
    ket: list[dict] = []
    try:
        g = new_client()
    except GeminiError as e:
        g = None
        loi_khoi_tao = str(e)[:200]
    if g:
        g.han = time.time() + phut_toi_da * 60

    # ---- UT1 + UT2
    if "cach_2_buoc" in ds or (g is None) or not con_luot(g):
        b = {"cach": "cach_2_buoc", "loi": []}
        pt = None
        if g and con_luot(g):
            g.muc_nghi = None
            try:
                pt = g.json(prompts.LUAT, prompts.prompt_phan_tich(fc, so), temperature=0.4, models=thu_tu_phan_tich(g))
                b["loi"] += check_phan_tich(pt)
                b["model"] = pt.get("_model")
                b["model_phan_tich"] = pt.get("_model")
            except GeminiError as e:
                b["loi"].append(f"AI phân tích hỏng: {str(e)[:200]}")
        if not pt:
            if facts:
                pt = khong_ai.phan_tich(facts)
                b["cach"] = "so_lieu_khong_ai"
                b["loi"].append("Gemini hết lượt/lỗi — bản phân tích số liệu dựng bằng code, chưa có lời thoại AI"
                                + (f" ({loi_khoi_tao})" if g is None else ""))
        b["phan_tich"] = pt or {}
        if pt and g and con_luot(g):
            g.muc_nghi = "medium"              # 13/10: lời thoại cần câu chữ tốt → nghĩ vừa, model tốt nhất
            tot, du = tang_model(g)
            try:
                try:
                    sc = g.json(prompts.LUAT, prompts.prompt_script_tu_phan_tich(fc, so, pt), temperature=0.75, models=tot)
                except GeminiError:
                    if not con_luot(g, 8):
                        raise
                    sc = g.json(prompts.LUAT, prompts.prompt_script_tu_phan_tich(fc, so, pt), temperature=0.75, models=du)
                    b["loi"].append(f"Lời thoại viết bằng model dự phòng {sc.get('_model')} vì các model tốt "
                                    f"({', '.join(m for m in tot if '-pro' not in m)}) đã hết lượt hôm nay — câu chữ sẽ kém hơn")
                b["model"] = sc.get("_model")
                b["model_loi_thoai"] = sc.get("_model")
                sc = lam_sach(sc)
                loi = check_script(sc)
                if loi and con_luot(g, 8):
                    sc = lam_sach(_sua_script(g, sc, loi, fc))
                    loi = check_script(sc)
                b["script"] = sc
                b["loi"] += loi
            except GeminiError as e:
                b["loi"].append(f"bỏ qua lời thoại (hết lượt/lỗi): {str(e)[:200]}")
        elif pt:
            b["loi"].append("bỏ qua lời thoại: không còn lượt Gemini hoặc hết quỹ thời gian")
        ket.append(b)

    # ---- UT3
    # bản thứ hai chỉ chạy khi chắc còn lượt: không model flash nào bị báo hết hạn mức trong lần chạy này
    co_ban_script = any((b.get("script") or {}).get("phan") for b in ket)
    if "cach_1_luot" in ds and g and con_luot(g, 10) and con_model_tot(g) and (g.bi_429 == 0 or not co_ban_script):
        ket.append(cach_1_luot(g, fc, so))
    elif "cach_1_luot" in ds and co_ban_script:
        pass                                   # đã có 1 bản đủ lời thoại → im lặng bỏ bản so sánh cho đỡ lượt
    elif "cach_1_luot" in ds:
        ket.append({"cach": "cach_1_luot", "loi": ["bỏ qua: hết lượt Gemini hoặc hết quỹ thời gian (đã ưu tiên bản phân tích)"]})

    if facts and not any(b.get("phan_tich") for b in ket):      # UT1 phải luôn có
        ket.append({"cach": "so_lieu_khong_ai", "phan_tich": khong_ai.phan_tich(facts),
                    "loi": ["AI không ra được bản phân tích — bản số liệu dựng bằng code"]})
    if len(ket) > 1:
        random.shuffle(ket)
    for i, b in enumerate(ket, 1):
        b["nhan"] = f"Bản {i}" if b.get("cach") != "so_lieu_khong_ai" else f"Bản {i} · số liệu (không AI)"
    ai = {"models": g.models if g else [], "so_luot": g.calls if g else 0,
          "token_vao": g.tokens_in if g else 0, "token_ra": g.tokens_out if g else 0,
          "nhat_ky": (g.nhat_ky[-30:] if g else [f"không khởi tạo được Gemini: {loi_khoi_tao}"])}
    return ket, ai


def viet_lai(fc: dict, so: dict, view: str, pt_cu: dict | None) -> tuple[dict, dict]:
    g = new_client()
    g.han = time.time() + 25 * 60
    res: dict = {"loi": []}
    g.muc_nghi = "medium"
    tot, du = tang_model(g)
    try:
        try:
            out = g.json(prompts.LUAT, prompts.prompt_viet_lai(fc, so, view, pt_cu), temperature=0.65, models=tot)
        except GeminiError:
            out = g.json(prompts.LUAT, prompts.prompt_viet_lai(fc, so, view, pt_cu), temperature=0.65, models=du)
            res["loi"].append(f"Viết lại bằng model dự phòng {out.get('_model')} vì các model tốt đã hết lượt hôm nay "
                              f"— câu chữ sẽ kém hơn; nên viết lại sau 14:00 hôm sau")
    except GeminiError as e:
        res["loi"].append(str(e)[:300])
        return res, {"so_luot": g.calls, "nhat_ky": g.nhat_ky[-30:]}
    sc = out.get("script") or {}
    sc = lam_sach(sc)
    loi = check_script(sc)
    if loi:
        sc = lam_sach(_sua_script(g, sc, loi, fc))
        loi = check_script(sc)
    res.update({"thesis_check": out.get("thesis_check") or [], "view_sau_phan_bien": out.get("view_sau_phan_bien"),
                "script": sc, "du_bao_moi": out.get("du_bao_moi") or [], "model": out.get("_model")})
    res["loi"] += loi
    return res, {"models": g.models, "so_luot": g.calls, "token_vao": g.tokens_in, "token_ra": g.tokens_out,
                 "nhat_ky": g.nhat_ky[-30:]}
