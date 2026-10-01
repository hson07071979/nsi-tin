// Trang /tin cho Worker QUẢN TRỊ (nsi-quantri). Đọc JSON từ repo PRIVATE nsi-tin qua GitHub API và vẽ HTML phía server.
// Cần 2 biến môi trường của Worker:
//   TIN_REPO  = "hson07071979/nsi-tin"
//   TIN_TOKEN = token fine-grained CHỈ ĐỌC (Contents: Read-only) cho đúng repo nsi-tin   (đặt dạng Secret)
// Gắn vào src/index.js ở nhánh MODE=admin, SAU bước kiểm đăng nhập admin:
//   import { handleTin } from "./tin_page.js";
//   if (url.pathname === "/tin" || url.pathname.startsWith("/tin/")) return handleTin(request, env);

const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const safeUrl = (u) => (/^https?:\/\//i.test(String(u || "")) ? esc(u) : "#");
const DG = { tot: ["Tốt", "g"], xau: ["Xấu", "r"], trung_tinh: ["Trung tính", "n"] };
const HD = { khong_hanh_dong: "Không hành động", theo_doi: "Theo dõi", than_trong: "Thận trọng", han_che_rui_ro: "Hạn chế rủi ro", co_hoi: "Cơ hội" };
const XM = { da_xac_minh: ["Đã xác minh", "g"], mot_nguon: ["Một nguồn", "n"], tin_don: ["Tin đồn", "r"] };
const TT = { dat: ["Đạt", "g"], mot_phan: ["Một phần", "y"], loi_ai: ["AI lỗi", "r"], dry: ["Chạy thử", "n"], dang_chay: ["Đang chạy", "y"] };
const PHE = { lac_quan: "Phe lạc quan", than_trong: "Phe thận trọng", vi_mo: "Chiến lược gia vĩ mô" };
const GRP = { bao_vn: "Báo tài chính VN", chinh_thuc: "Nguồn chính thức", quoc_te: "Quốc tế", nguon_5: "Web 5 nguồn" };

async function gh(env, path) {
  const r = await fetch(`https://api.github.com/repos/${env.TIN_REPO}/contents/${path}`, {
    headers: { Authorization: `Bearer ${env.TIN_TOKEN}`, Accept: "application/vnd.github.raw", "User-Agent": "nsi-quantri" },
  });
  if (r.status === 404) return null;
  if (!r.ok) throw new Error(`GitHub ${r.status}`);
  return r.json();
}

const pill = (txt, cls) => `<span class="pill ${cls}">${esc(txt)}</span>`;
const vnNow = () => new Date(Date.now() + 7 * 3600e3);
const fmtD = (iso) => (iso ? iso.slice(8, 10) + "/" + iso.slice(5, 7) + "/" + iso.slice(0, 4) : "");
const hm = (iso) => (iso ? iso.slice(11, 16) : "—");

const loaiTen = { vi_mo_vn: "Vĩ mô VN", quoc_te: "Quốc tế", chinh_sach: "Chính sách", nganh: "Ngành", doanh_nghiep: "Doanh nghiệp", thi_truong: "Thị trường", tin_don: "Tin đồn" };
const para = (label, txt, cls = "") => (txt && txt !== "không áp dụng" ? `<div class="blk ${cls}"><h5>${label}</h5><p>${esc(txt)}</p></div>` : "");

function nguonHtml(t, kind) {
  const ns = t.nguon || [];
  if (!ns.length) return "";
  const one = (n) => kind === "zalo"
    ? `<li class="quote"><span class="muted">${hm(n.published)} · ${esc(n.src_name)} · <b>${esc(n.author || "?")}</b></span><br>${esc(n.text || n.title).replace(/\n/g, "<br>")}</li>`
    : `<li><a href="${safeUrl(n.url)}" target="_blank" rel="noopener">${esc(n.title)}</a> <span class="muted">· ${esc(n.src_name)} · ${hm(n.published)}</span>${n.summary ? `<br><span class="sum">${esc(n.summary)}</span>` : ""}</li>`;
  const head = ns.slice(0, 2).map(one).join("");
  const rest = ns.slice(2).map(one).join("");
  return `<div class="blk src-blk"><h5>${kind === "zalo" ? "Nhóm nói gì (trích nguyên văn)" : "Tin gốc"} · ${ns.length} nguồn</h5><ul class="src">${head}</ul>
    ${rest ? `<details><summary>Xem thêm ${ns.length - 2} nguồn</summary><ul class="src">${rest}</ul></details>` : ""}</div>`;
}

function topicCard(t, kind) {
  const [dg, dc] = DG[t.danh_gia] || ["Chưa chốt", "n"];
  const [xm, xc] = XM[t.xac_minh] || ["—", "n"];
  const hd = t.hanh_dong ? pill(HD[t.hanh_dong] || t.hanh_dong, t.hanh_dong === "co_hoi" ? "g" : ["than_trong", "han_che_rui_ro"].includes(t.hanh_dong) ? "y" : "n") : "";
  const ma = (t.nganh_ma || []).map((x) => `<span class="ma ${x.chieu === "-" ? "r" : "g"}">${x.chieu === "-" ? "▼" : "▲"} ${esc(x.ten)}<small>${x.ly_do ? " — " + esc(x.ly_do) : ""}</small></span>`).join("");
  const sl = (t.so_lieu_chinh || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const rr = (t.rui_ro || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const tn = (t.thuat_ngu || []).map((x) => `<dt>${esc(x.tu)}</dt><dd>${esc(x.nghia)}</dd>`).join("");
  const phe = Object.entries(t.phe || {}).map(([k, v]) => {
    if (!v) return "";
    const [d, c] = DG[v.nhan_dinh] || ["?", "n"];
    const pb = (t.phan_bien || {})[k];
    return `<div class="phe"><b>${PHE[k] || k}</b> ${pill(d, c)} <span class="muted">tin cậy ${esc(v.do_tin_cay ?? "?")}/100</span>
      <p>${esc(v.lap_luan)}</p>${(v.chuoi_truyen_dan || []).map((c) => `<p class="chuoi">${esc(c)}</p>`).join("")}
      ${pb ? `<p class="pb"><i>Phản biện:</i> ${esc(pb.phan_bac)}${pb.doi_y ? ` <b>→ đổi ý: ${esc(pb.ly_do_doi_y)}</b>` : ""}</p>` : ""}</div>`;
  }).join("");
  return `<article class="card topic ${dc}" id="${kind}-${esc(t.id)}">
  <header><h3><span class="rank">#${esc(t.hang ?? "")}</span> ${esc(t.tieu_de)}</h3>
    <div class="badges">${pill(dg, dc)} ${t.muc_do ? pill("mức " + t.muc_do, "n") : ""} ${hd} ${pill(xm, xc)} ${t.loai ? `<span class="muted">${esc(loaiTen[t.loai] || t.loai)}</span>` : ""}</div></header>
  ${para("Chuyện gì xảy ra", t.chuyen_gi || t.mot_dong, "main")}
  ${sl ? `<div class="blk"><h5>Số liệu chính</h5><ul class="sl">${sl}</ul></div>` : ""}
  <div class="two">${para("Bối cảnh", t.boi_canh)}${para("Vì sao quan trọng", t.vi_sao_quan_trong)}</div>
  <div class="two">${para("Vĩ mô → vi mô", t.vi_mo_to_vi_mo)}${para("Vi mô → vi mô (lan sang DN/ngành khác)", t.vi_mo_vi_mo)}</div>
  ${ma ? `<div class="blk"><h5>Mã / ngành bị ảnh hưởng</h5><div class="mas">${ma}</div></div>` : ""}
  ${rr ? `<div class="blk"><h5>Rủi ro</h5><ul>${rr}</ul></div>` : ""}
  ${t.can_trong ? `<div class="blk ct"><h5>Nên cẩn trọng thế nào</h5><p>${esc(t.can_trong)}</p></div>` : ""}
  ${t.lien_he_he_thong ? `<p class="muted"><b>Với hệ thống NSI:</b> ${esc(t.lien_he_he_thong)}</p>` : ""}
  ${tn ? `<details><summary>Thuật ngữ trong tin</summary><dl class="tn">${tn}</dl></details>` : ""}
  ${nguonHtml(t, kind)}
  ${phe ? `<details><summary>Tranh luận 3 phe & trọng tài</summary>${phe}
    ${t.dong_thuan ? `<p><b>Trọng tài chốt:</b> ${esc(t.dong_thuan)}</p>` : ""}${t.kiem_chung_sau ? `<p class="muted">Sau 5 phiên sẽ chấm bằng: ${esc(t.kiem_chung_sau)}</p>` : ""}</details>` : ""}
  ${t.ly_do_top ? `<p class="muted why">Vì sao xếp hạng #${esc(t.hang)}: ${esc(t.ly_do_top)}</p>` : ""}
</article>`;
}

function tabHtml(tab, kind) {
  if (!tab) return `<p class="muted">Không có dữ liệu.</p>`;
  const topics = (tab.topics || []).slice().sort((a, b) => (a.hang ?? 99) - (b.hang ?? 99));
  const items = tab.items || [];
  const dem = tab.dem || {};
  const err = tab.loi ? `<div class="warn">${esc(tab.loi)}</div>` : "";
  const stat = `<p class="muted">${topics.length} chủ đề quan trọng nhất, lọc từ ${items.length} tin${tab.so_bai_doc_duoc != null ? ` · AI đọc trọn ${tab.so_bai_doc_duoc} bài` : ""}
    ${topics.length ? ` · <span class="c-g">${dem.tot || 0} tốt</span> · <span class="c-r">${dem.xau || 0} xấu</span> · ${dem.trung_tinh || 0} trung tính` : ""}</p>`;
  const toc = topics.length ? `<ol class="toc">${topics.map((t) => {
    const [d, c] = DG[t.danh_gia] || ["—", "n"];
    return `<li><a href="#${kind}-${esc(t.id)}"><span class="rank">#${esc(t.hang)}</span> ${pill(d, c)} <b>${esc(t.tieu_de)}</b></a><div class="muted">${esc(t.mot_dong || "")}</div></li>`;
  }).join("")}</ol>` : "";
  const cards = topics.map((t) => topicCard(t, kind)).join("");
  const inTop = new Set(topics.flatMap((t) => t.item_ids || []));
  const rest = items.filter((it) => !inTop.has(it.id));
  let list;
  if (kind === "web") {
    list = `<ul class="src">${rest.map((it) => `<li><a href="${safeUrl(it.url)}" target="_blank" rel="noopener">${esc(it.title)}</a> <span class="muted">· ${esc(it.src_name)} · ${hm(it.published)}</span></li>`).join("")}</ul>`;
  } else {
    list = `<ul class="zl">${rest.map((it) => `<li><span class="muted">${hm(it.published)} · ${esc(it.src_name)} · ${esc(it.author)}</span><br>${esc(it.text).replace(/\n/g, "<br>")}</li>`).join("")}</ul>`;
  }
  return `${err}${stat}${toc ? `<div class="card toc-card"><h4>Mục lục — bấm để nhảy tới</h4>${toc}</div>` : ""}
  ${cards || (tab.loi ? "" : `<p class="muted">Không có chủ đề đáng kể.</p>`)}
  ${rest.length ? `<details class="all"><summary>${rest.length} tin còn lại không vào top (để tra khi cần)</summary>${list}</details>` : ""}`;
}

function chamHtml(cd) {
  const t = cd?.tong_ket || {};
  const n = t.trong_tai?.n || 0;
  const DU = 30;
  const intro = `<p>Mỗi sáng AI nói một tin là <b>tốt</b> hay <b>xấu</b> cho một mã (ví dụ "▼ SSI"). Sau <b>5 phiên</b>, hệ tự lấy giá thật:
    nếu SSI chạy <b>kém hơn VN-Index</b> thì lần nói "xấu" đó được tính là <b>đúng</b>, chạy hơn thì <b>sai</b>. Tin nói về cả thị trường thì so với chiều của VN-Index.
    Tin "trung tính" không chấm. Cộng dồn lại sẽ biết AI (và từng phe) nói đúng bao nhiêu phần trăm — tung đồng xu là 50%.</p>`;
  if (n < DU) {
    return `<details class="card"><summary><b>AI đoán có đúng không?</b> — đang gom mẫu ${n}/${DU}, chưa đủ để kết luận</summary>${intro}
      <p class="muted">Cần ít nhất ${DU} nhận định đã qua 5 phiên (khoảng 2–3 tuần chạy thật) thì con số mới có nghĩa. Trước đó hệ không hiện tỷ lệ để khỏi hiểu nhầm.</p></details>`;
  }
  const row = (k, lab) => (t[k] ? `<tr><td>${lab}</td><td>${t[k].n}</td><td><b>${t[k].ty_le_dung ?? "—"}%</b></td></tr>` : "");
  const recent = (cd.chi_tiet || []).slice(-10).reverse().map((r) => `<tr><td>${fmtD(r.ngay)}</td><td>${esc(r.chu_de)}</td><td>${r.du_bao > 0 ? "▲" : "▼"} ${esc(r.doi_tuong)}</td><td>${r.vuot_t4 > 0 ? "+" : ""}${r.vuot_t4}% so VN-Index</td><td>${r.dung ? "✔ đúng" : "✘ sai"}</td></tr>`).join("");
  return `<details class="card"><summary><b>AI đoán có đúng không?</b> — trọng tài đúng ${t.trong_tai.ty_le_dung}% trên ${n} lần</summary>${intro}
  <table><tr><th>Ai nói</th><th>Số lần chấm</th><th>Tỷ lệ đúng</th></tr>${row("trong_tai", "Trọng tài (kết luận cuối)")}${row("phe_lac_quan", "Phe lạc quan")}${row("phe_than_trong", "Phe thận trọng")}${row("phe_vi_mo", "Chiến lược gia vĩ mô")}${row("tab_web", "Tin web")}${row("tab_zalo", "Tin Zalo")}${row("xac_minh_tin_don", "Tin đồn")}</table>
  ${recent ? `<h4>10 lần chấm gần nhất</h4><table class="sm"><tr><th>Ngày tin</th><th>Chủ đề</th><th>AI nói</th><th>Thực tế 5 phiên</th><th></th></tr>${recent}</table>` : ""}</details>`;
}

function macroHtml(vm) {
  if (!vm) return "";
  const s = vm.so_lieu || {};
  // chỉ tô xanh/đỏ cho VN-Index; USD/VND, DXY, lợi suất tăng KHÔNG phải tin tốt nên để màu trung tính
  const r2 = (x) => (typeof x === "number" ? Math.round(x * 100) / 100 : x);
  const cell = (k, lab, suf = "", ch = null, chsuf = "", color = false) => `<div class="kv"><span>${lab}</span><b>${r2(s[k]) ?? "—"}${s[k] != null ? suf : ""}</b>${ch && s[ch] != null ? `<i class="${color ? (s[ch] > 0 ? "up" : s[ch] < 0 ? "dn" : "") : ""}">${s[ch] > 0 ? "+" : ""}${r2(s[ch])}${chsuf}</i>` : ""}</div>`;
  const grid = [
    cell("lnh_on", "LNH qua đêm", "%", "lnh_on_chg5_bp", "bp/5p"), cell("usdvnd", "USD/VND", "", "usdvnd_chg20_pct", "%/20p"),
    cell("dxy", "DXY", "", "dxy_chg20_pct", "%/20p"), cell("us10y", "US 10Y", "%", "us10y_chg20_bp", "bp/20p"),
    cell("brent", "Brent", "$", "brent_chg20_pct", "%/20p"), cell("gold", "Vàng TG", "$", "gold_chg20_pct", "%/20p"),
    cell("vix", "VIX", ""), cell("vnindex", "VN-Index", "", "vnindex_chg5_pct", "%/5p", true),
  ].join("");
  const pb = vm.playbook || { flags: [] };
  const ST = { bat: ["BẬT", "y"], tat: ["tắt", "n"], thieu_du_lieu: ["thiếu dữ liệu", "muted2"] };
  const fl = pb.flags.map((f) => {
    const [t, c] = ST[f.trang_thai] || [f.trang_thai, "n"];
    const on = f.trang_thai === "bat";
    return `<li class="${on ? "on" : ""}">${pill(t, c)} <b>${esc(f.ten)}</b> <span class="muted">· ${esc(f.muc_ten)}</span>
      ${on ? `<div class="fd"><p>${esc(f.doc)}</p><p><b>Vĩ mô → vi mô:</b> ${esc(f.vi_mo_to_vi_mo)}</p><p><b>Gợi ý:</b> ${esc(f.goi_y_he_thong)}</p><p class="muted">${esc(f.kiem_chung)}</p></div>` : ""}</li>`;
  }).join("");
  return `<section class="card"><h2>Vĩ mô sáng nay <span class="muted">· mức cao nhất: ${esc(pb.muc_cao_nhat)}</span></h2>
  <div class="grid">${grid}</div>${vm.ghi_chu ? `<p class="muted">${esc(vm.ghi_chu)}</p>` : ""}
  ${pb.cap_ty_gia_lnh ? `<div class="warn">Cặp nguy hiểm: TỶ GIÁ CĂNG + LNH SỐC cùng bật → NHNN mất room nới lỏng.</div>` : ""}
  <details ${pb.so_co_bat ? "open" : ""}><summary>Sổ luật vĩ mô mềm (${pb.so_co_bat} cờ bật${pb.flags.filter((f) => f.trang_thai === "thieu_du_lieu").length ? ", " + pb.flags.filter((f) => f.trang_thai === "thieu_du_lieu").length + " thiếu dữ liệu" : ""}) — gợi ý soi tay, không chặn lệnh</summary><ul class="flags">${fl}</ul></details></section>`;
}

function tongHopHtml(th) {
  if (!th || th.loi) return th?.loi ? `<div class="warn">Tổng hợp lỗi: ${esc(th.loi)}</div>` : "";
  const [d, c] = DG[th.trang_thai] || ["", "n"];
  const li = (a) => (a || []).map((x) => `<li>${esc(x)}</li>`).join("");
  const bl = th.bai_luyen_vi_mo || {};
  return `<section class="card hero ${c}"><h2>${d ? pill(d, c) : ""} ${esc(th.tieu_de)}</h2>
  ${th.canh_bao ? `<div class="warn">${esc(th.canh_bao)}</div>` : ""}
  <div class="cols"><div><h4>3 điều cần biết</h4><ol>${li(th.ba_dieu_can_biet)}</ol></div>
  <div><h4>Việc hôm nay</h4><ul>${li(th.viec_hom_nay)}</ul></div></div>
  ${(th.doi_chieu_web_zalo || []).length ? `<h4>Đối chiếu web ↔ Zalo</h4><ul>${li(th.doi_chieu_web_zalo)}</ul>` : ""}
  ${bl.cau_hoi ? `<div class="luyen"><h4>Luyện vĩ mô</h4><p>${esc(bl.tinh_huong)}</p><p><b>${esc(bl.cau_hoi)}</b></p>
    <details><summary>Xem đáp án</summary><p>${esc(bl.dap_an)}</p>${(bl.chuoi_nhan_qua || []).map((x) => `<p class="chuoi">${esc(x)}</p>`).join("")}
    ${bl.luat_lien_quan ? `<p class="muted">Luật liên quan: ${esc(bl.luat_lien_quan)}</p>` : ""}</details></div>` : ""}
  </section>`;
}


const CSS = `:root{--bg:#f6f7f9;--card:#fff;--tx:#1b1f24;--mu:#6b7280;--bd:#e5e7eb;--g:#0f7b4a;--gb:#e6f4ec;--r:#b42318;--rb:#fdecea;--y:#9a6700;--yb:#fff5d6;--n:#374151;--nb:#eef0f3;--ac:#1d4ed8}
@media (prefers-color-scheme:dark){:root{--bg:#0f1115;--card:#171a21;--tx:#e6e8eb;--mu:#9aa3af;--bd:#2a2f3a;--g:#4ade80;--gb:#12301f;--r:#f87171;--rb:#3a1414;--y:#fbbf24;--yb:#3a2e0a;--n:#cbd5e1;--nb:#252a33;--ac:#93c5fd}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);font:15px/1.55 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
main{max-width:1000px;margin:0 auto;padding:16px}h1{font-size:20px;margin:4px 0}h2{font-size:17px;margin:0 0 10px}h3{font-size:16px;margin:0}h4{margin:12px 0 4px;font-size:14px}
a{color:var(--ac)}.muted{color:var(--mu);font-size:13px}.card{background:var(--card);border:1px solid var(--bd);border-radius:10px;padding:14px 16px;margin:12px 0}
.pill{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;font-weight:600;white-space:nowrap}.pill.g{background:var(--gb);color:var(--g)}.pill.r{background:var(--rb);color:var(--r)}.pill.y{background:var(--yb);color:var(--y)}.pill.n{background:var(--nb);color:var(--n)}.pill.muted2{background:transparent;color:var(--mu);border:1px dashed var(--bd)}
.warn{background:var(--yb);color:var(--y);border-radius:8px;padding:8px 12px;margin:8px 0;font-weight:600}.late{background:var(--rb);color:var(--r)}
.topic{border-left:4px solid var(--bd)}.topic.g{border-left-color:var(--g)}.topic.r{border-left-color:var(--r)}.topic header{display:flex;flex-wrap:wrap;gap:6px 12px;justify-content:space-between;align-items:center;margin-bottom:6px}
.ma{display:inline-block;padding:1px 7px;border-radius:6px;font-size:13px;margin:2px 2px 2px 0;font-weight:600}.ma.g{background:var(--gb);color:var(--g)}.ma.r{background:var(--rb);color:var(--r)}
.ct{background:var(--nb);padding:8px 10px;border-radius:8px}.chuoi{font-family:ui-monospace,Consolas,monospace;font-size:13px;margin:4px 0;color:var(--n)}
.phe{border-top:1px dashed var(--bd);padding-top:8px;margin-top:8px}.pb{color:var(--mu)}details summary{cursor:pointer;color:var(--ac);margin-top:8px}
.tabs input{display:none}.tabs label{display:inline-block;padding:8px 16px;border:1px solid var(--bd);border-bottom:none;border-radius:8px 8px 0 0;cursor:pointer;background:var(--nb);margin-right:4px;font-weight:600}
.tabs input:checked+label{background:var(--card);color:var(--ac)}.panel{display:none;border-top:1px solid var(--bd);padding-top:4px}#t1:checked~.p1,#t2:checked~.p2{display:block}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}.kv{background:var(--nb);border-radius:8px;padding:8px 10px;display:flex;flex-direction:column}.kv span{font-size:12px;color:var(--mu)}.kv i{font-size:12px;font-style:normal}.up{color:var(--g)}.dn{color:var(--r)}
.flags{list-style:none;padding:0}.flags li{padding:6px 0;border-bottom:1px solid var(--bd)}.fd{padding:6px 0 0 8px;font-size:14px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media(max-width:640px){.cols{grid-template-columns:1fr}}
.hero.r{border-top:4px solid var(--r)}.hero.g{border-top:4px solid var(--g)}.luyen{background:var(--nb);border-radius:8px;padding:8px 12px;margin-top:12px}
.src{padding-left:18px}.src li{margin:3px 0}.zl{list-style:none;padding:0}.zl li{border-bottom:1px solid var(--bd);padding:6px 0;font-size:14px}
.top{display:flex;flex-wrap:wrap;gap:8px;align-items:center;justify-content:space-between}select{padding:4px 8px;border-radius:6px;border:1px solid var(--bd);background:var(--card);color:var(--tx)}
.rank{color:var(--mu);font-weight:700;margin-right:4px}.badges{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
.blk{margin:10px 0}.blk h5{margin:0 0 3px;font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mu)}.blk p{margin:0}
.blk.main p{font-size:15.5px;line-height:1.65}.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}@media(max-width:640px){.two{grid-template-columns:1fr}}
.sl{margin:0;padding-left:18px}.sum{color:var(--mu);font-size:13.5px}.quote{border-left:3px solid var(--bd);padding-left:8px;list-style:none;margin:6px 0}
.mas{display:flex;flex-wrap:wrap;gap:4px}.ma small{font-weight:400;opacity:.85}.tn dt{font-weight:700}.tn dd{margin:0 0 6px 0;color:var(--mu)}
.toc{padding-left:0;list-style:none;margin:0}.toc li{padding:6px 0;border-bottom:1px solid var(--bd)}.toc a{text-decoration:none;color:var(--tx)}.toc .muted{padding-left:30px}
.c-g{color:var(--g)}.c-r{color:var(--r)}.why{margin-top:10px;font-style:italic}table.sm td{font-size:13px}
table{border-collapse:collapse;width:100%}td,th{padding:4px 8px;border-bottom:1px solid var(--bd);text-align:left}`;

export function renderTin(d, idx, cd) {
  if (!d) return `<!doctype html><meta charset="utf-8"><title>Bản tin sáng</title><style>${CSS}</style><main><h1>Bản tin sáng</h1><div class="warn">Chưa có bản tin nào.</div></main>`;
  const now = vnNow();
  const today = now.toISOString().slice(0, 10);
  const hhmm = now.toISOString().slice(11, 16);
  const [tt, tc] = TT[d.trang_thai_chay] || [d.trang_thai_chay, "n"];
  const late = d.ngay !== today && hhmm >= "08:30" && now.getUTCDay() % 6 !== 0;
  const opts = (idx || []).slice(0, 60).map((x) => `<option value="${x.ngay}" ${x.ngay === d.ngay ? "selected" : ""}>${fmtD(x.ngay)} · ${(TT[x.trang_thai_chay] || [x.trang_thai_chay])[0]}</option>`).join("");
  const zs = d.zalo_status || {};
  const srcErr = (d.nguon_web || []).filter((s) => s.err).map((s) => `${s.name}: ${s.err}`);
  return `<!doctype html><html lang="vi"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Bản tin sáng</title><style>${CSS}</style></head><body><main>
<div class="top"><div><h1>Bản tin sáng ${fmtD(d.ngay)}</h1>
<div class="muted">${pill(tt, tc)} xong ${hm(d.xong_luc)} ${d.dung_han ? "· đúng hạn" : "· <b>trễ hạn 8h30</b>"} · tin từ ${hm(d.cua_so?.tu)} ${fmtD(d.cua_so?.tu)} · ${d.ai?.models ? esc(d.ai.models[0]) + " · " + d.ai.so_luot + " lượt" : esc(d.ai?.loi || "")}</div></div>
<form method="get" action="/tin"><select name="ngay" onchange="this.form.submit()">${opts}</select></form></div>
${late ? `<div class="warn late">BẢN TIN HÔM NAY CHƯA CÓ — đồng hồ ảo hoặc workflow sang.yml có vấn đề. Đang hiện bản ${fmtD(d.ngay)}.</div>` : ""}
${!zs.listener_song ? `<div class="warn">${zs.heartbeat ? `Bộ nghe Zalo trên laptop im từ ${esc(zs.heartbeat.replace("T", " ").slice(0, 16))}` : "Bộ nghe Zalo trên laptop chưa từng gửi dữ liệu"} → tab Zalo có thể thiếu tin.</div>` : ""}
${tongHopHtml(d.tong_hop)}
<div class="tabs card">
<input type="radio" name="tab" id="t1" checked><label for="t1">Tin web (${(d.web?.items || []).length})</label>
<input type="radio" name="tab" id="t2"><label for="t2">Tin Zalo (${(d.zalo?.items || []).length})</label>
<div class="panel p1">${tabHtml(d.web, "web")}</div>
<div class="panel p2">${zs.theo_nhom ? `<p class="muted">${Object.entries(zs.theo_nhom).map(([k, v]) => `${esc(k)}: ${v}`).join(" · ")}</p>` : ""}${tabHtml(d.zalo, "zalo")}</div>
</div>
${macroHtml(d.vi_mo)}
${chamHtml(cd)}
${srcErr.length ? `<details class="card"><summary>Nguồn lỗi (${srcErr.length})</summary><ul>${srcErr.map((x) => `<li>${esc(x)}</li>`).join("")}</ul></details>` : ""}
<p class="muted">AI tổng hợp từ tin công khai và nhóm Zalo. Là gợi ý để soi tay, không phải khuyến nghị giao dịch; không lớp nào ở đây chặn lệnh của bộ máy.</p>
</main></body></html>`;
}

export async function handleTin(request, env) {
  const url = new URL(request.url);
  const ngay = url.searchParams.get("ngay");
  try {
    const safe = ngay && /^\d{4}-\d{2}-\d{2}$/.test(ngay) ? ngay : null;
    const [d, idx, cd] = await Promise.all([
      gh(env, safe ? `out/${safe}.json` : "out/latest.json"), gh(env, "out/index.json"), gh(env, "out/cham_diem.json").catch(() => null),
    ]);
    return new Response(renderTin(d, idx, cd), { headers: { "content-type": "text/html; charset=utf-8", "cache-control": "private, max-age=60", "x-robots-tag": "noindex" } });
  } catch (e) {
    return new Response(`Lỗi đọc bản tin: ${esc(e.message)} — kiểm TIN_REPO / TIN_TOKEN của Worker.`, { status: 502, headers: { "content-type": "text/plain; charset=utf-8" } });
  }
}
