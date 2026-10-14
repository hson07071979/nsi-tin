// Dựng PPTX Nguyen Son Finance từ content.json (do slides/make.py sinh). Không gọi AI.
// node build.js content.json out.pptx
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const [, , CJ, OUT] = process.argv;
const D = JSON.parse(fs.readFileSync(CJ, "utf8"));
const M = D.meta, N = D.notes || {};
const A = (f) => path.join(__dirname, "assets", f);

// Bảng màu mệnh Thủy (Thủy + Kim sinh Thủy)
const BG = "0A1A33", PANEL = "0F2342", CARD = "16315A", CARD2 = "1D3D6B", LINE = "2A4C7E";
const WATER = "4FC3F7", SILVER = "C5D0DE", WHITE = "F4F7FB", MUTED = "8FA3C0";
const UP = "26C281", DOWN = "EF5466", VIOLET = "B48CFF";
const FONT = "Arial";
const CX = 3.2, CY = 1.45, CW = 9.68, CB = 6.5;

const vn = (x, n = 1, sign = false) => {
  if (x === null || x === undefined) return "—";
  const s = Math.abs(x).toLocaleString("de-DE", { minimumFractionDigits: n, maximumFractionDigits: n });
  return x < 0 ? "−" + s : (sign && x > 0 ? "+" : "") + s;
};
const chgColor = (c) => { c = String(c).trim(); return c.startsWith("+") ? UP : (c.startsWith("−") || c.startsWith("-")) ? DOWN : SILVER; };

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(React.createElement(Comp, { color: "#" + color, size: String(size) }));
  return "image/png;base64," + (await sharp(Buffer.from(svg)).png().toBuffer()).toString("base64");
}
function T(s, text, o) { s.addText(text, Object.assign({ isTextBox: true, fontFace: FONT, color: WHITE, margin: 0, valign: "top" }, o)); }
function box(s, x, y, w, h, fill = CARD) { s.addShape("roundRect", { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, rectRadius: 0.08 }); }
function pill(s, x, y, w, h, text, fill, color = BG, size = 12) {
  s.addShape("roundRect", { x, y, w, h, fill: { color: fill }, line: { color: fill, width: 0 }, rectRadius: h / 2 });
  T(s, text, { x, y, w, h, fontSize: size, bold: true, color, align: "center", valign: "middle" });
}
function circleIcon(s, x, y, d, color, data) {
  s.addShape("ellipse", { x, y, w: d, h: d, fill: { color }, line: { color, width: 0 } });
  s.addImage({ data, x: x + d * 0.24, y: y + d * 0.24, w: d * 0.52, h: d * 0.52 });
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = `Rà soát thị trường ${M.date}`;
  pres.author = "Nguyen Son Finance";
  pres.theme = { headFontFace: FONT, bodyFontFace: FONT };
  const ic = {};
  for (const [k, C, col] of [["yt", fa.FaYoutube, WHITE], ["tt", fa.FaTiktok, WHITE], ["web", fa.FaGlobeAsia, WATER], ["phone", fa.FaPhoneAlt, WATER],
    ["cam", fa.FaVideo, MUTED], ["idx", fa.FaChartLine, BG], ["stk", fa.FaLayerGroup, BG], ["cash", fa.FaCoins, BG], ["up", fa.FaArrowUp, BG],
    ["down", fa.FaArrowDown, BG], ["check", fa.FaCheck, BG], ["times", fa.FaTimes, BG], ["eye", fa.FaEye, BG], ["shield", fa.FaShieldAlt, BG]]) ic[k] = await icon(C, col);

  // ---------------- KHUNG LIVE ----------------
  pres.defineSlideMaster({
    title: "NSF_FRAME", background: { color: BG },
    objects: [
      { image: { x: 0.53, y: 0.16, w: 1.9, h: 1.9, path: A("logo_round.png") } },
      { text: { text: "Rà soát thị trường mỗi ngày", options: { x: 0.2, y: 2.1, w: 2.56, h: 0.3, fontFace: FONT, fontSize: 11, color: SILVER, align: "center", margin: 0 } } },
      { rect: { x: 0.62, y: 2.5, w: 1.72, h: 1.72, fill: { color: "FFFFFF" }, line: { color: "FFFFFF", width: 0 } } },
      { image: { x: 0.7, y: 2.58, w: 1.56, h: 1.56, path: A("qr_ssi.png") } },
      { text: { text: "Mở tài khoản SSI", options: { x: 0.2, y: 4.28, w: 2.56, h: 0.24, fontFace: FONT, fontSize: 10, color: MUTED, align: "center", margin: 0 } } },
      { text: { text: `ID SSI: ${M.ssi_id}`, options: { x: 0.2, y: 4.5, w: 2.56, h: 0.32, fontFace: FONT, fontSize: 15, bold: true, color: WATER, align: "center", margin: 0 } } },
      { rect: { x: 0.2, y: 4.95, w: 2.56, h: 1.75, fill: { color: PANEL }, line: { color: WATER, width: 1, dashType: "dash" } } },
      { image: { x: 1.3, y: 5.55, w: 0.36, h: 0.36, data: ic.cam } },
      { text: { text: "CAMERA", options: { x: 0.2, y: 5.95, w: 2.56, h: 0.3, fontFace: FONT, fontSize: 11, bold: true, color: MUTED, align: "center", margin: 0, charSpacing: 3 } } },
      { rect: { x: 2.95, y: 0.16, w: 10.18, h: 6.54, fill: { color: PANEL }, line: { color: LINE, width: 0.75 } } },
      { rect: { x: 0.2, y: 6.84, w: 12.93, h: 0.52, fill: { color: PANEL }, line: { color: LINE, width: 0.75 } } },
      { image: { x: 0.42, y: 6.97, w: 0.27, h: 0.27, data: ic.yt } },
      { text: { text: M.youtube, options: { x: 0.78, y: 6.84, w: 2.0, h: 0.52, fontFace: FONT, fontSize: 13, bold: true, color: WHITE, valign: "middle", margin: 0 } } },
      { image: { x: 2.92, y: 6.97, w: 0.27, h: 0.27, data: ic.tt } },
      { text: { text: M.tiktok, options: { x: 3.28, y: 6.84, w: 2.0, h: 0.52, fontFace: FONT, fontSize: 13, bold: true, color: WHITE, valign: "middle", margin: 0 } } },
      { image: { x: 5.42, y: 6.97, w: 0.27, h: 0.27, data: ic.web } },
      { text: { text: M.website, options: { x: 5.78, y: 6.84, w: 2.4, h: 0.52, fontFace: FONT, fontSize: 13, color: WHITE, valign: "middle", margin: 0 } } },
      { image: { x: 8.25, y: 6.97, w: 0.27, h: 0.27, data: ic.phone } },
      { text: { text: M.contact, options: { x: 8.61, y: 6.84, w: 2.5, h: 0.52, fontFace: FONT, fontSize: 13, bold: true, color: WATER, valign: "middle", margin: 0 } } },
      { rect: { x: 10.92, y: 0.36, w: 1.96, h: 0.36, fill: { color: CARD }, line: { color: CARD, width: 0 } } },
    ],
    slideNumber: { x: 12.45, y: 6.3, w: 0.5, h: 0.25, fontFace: FONT, fontSize: 9, color: MUTED, align: "right" },
  });
  let n = 0;
  function slide(tag, title, notes) {
    const s = pres.addSlide({ masterName: "NSF_FRAME" }); n++;
    T(s, tag, { x: CX, y: 0.38, w: 7.4, h: 0.3, fontSize: 12, bold: true, color: WATER, charSpacing: 2 });
    T(s, title, { x: CX, y: 0.7, w: 9.68, h: 0.62, fontSize: 26, bold: true, color: WHITE, fit: "shrink" });
    T(s, M.date_long, { x: 10.92, y: 0.36, w: 1.96, h: 0.36, fontSize: 12, bold: true, color: SILVER, align: "center", valign: "middle" });
    if (notes) s.addNotes(notes);
    return s;
  }
  const bullets = (ls, gap = 8) => ls.map((t, i) => ({ text: t, options: { bullet: true, breakLine: i < ls.length - 1, paraSpaceAfter: gap } }));

  // 1. HOOK
  { const s = slide("MỞ ĐẦU", "Câu hỏi của phiên hôm nay", N.hook);
    T(s, D.hook.question, { x: CX, y: 1.6, w: CW, h: 1.6, fontSize: 32, bold: true, fit: "shrink" });
    const w = (CW - 0.6) / 3;
    D.hook.cards.forEach(([v, l, c], i) => { const x = CX + i * (w + 0.3); box(s, x, 3.55, w, 2.3);
      T(s, v, { x: x + 0.3, y: 3.85, w: w - 0.6, h: 0.9, fontSize: 42, bold: true, color: c, fit: "shrink" });
      T(s, l, { x: x + 0.3, y: 4.85, w: w - 0.6, h: 0.8, fontSize: 15, color: SILVER }); }); }

  // 2. BA LỚP
  { const s = slide("TÓM TẮT", "Index, cổ phiếu và dòng tiền đang nói gì", N.hook);
    [[ic.idx, "INDEX NÓI GÌ", WATER], [ic.stk, "CỔ PHIẾU NÓI GÌ", DOWN], [ic.cash, "DÒNG TIỀN NÓI GÌ", VIOLET]].forEach(([im, lab, col], i) => {
      const y = 1.6 + i * 1.6; box(s, CX, y, CW, 1.35); circleIcon(s, CX + 0.3, y + 0.3, 0.75, col, im);
      T(s, lab, { x: CX + 1.35, y: y + 0.18, w: 7.9, h: 0.35, fontSize: 14, bold: true, color: col, charSpacing: 1 });
      T(s, D.signature[i] || "", { x: CX + 1.35, y: y + 0.52, w: 8.1, h: 0.75, fontSize: 15, color: WHITE, fit: "shrink" }); }); }

  // 3. ĐỐI CHIẾU DỰ BÁO
  if (D.forecast.length) { const s = slide("ĐỐI CHIẾU DỰ BÁO", "Các mốc đã nêu phiên trước", N.forecast);
    const H = (t) => ({ text: t, options: { bold: true, color: MUTED, fill: { color: PANEL }, fontSize: 12 } });
    const rows = [[H("Nhận định đã nêu"), H("Diễn biến"), H("Trạng thái")]].concat(D.forecast.map(([a, b, kq, c]) => [
      { text: a, options: { color: WHITE } }, { text: b, options: { color: SILVER } }, { text: kq, options: { bold: true, color: c } }]));
    s.addTable(rows, { x: CX, y: 1.6, w: CW, colW: [4.0, 4.1, 1.58], fontFace: FONT, fontSize: 13, color: WHITE, fill: { color: CARD },
      border: { type: "solid", pt: 0.75, color: PANEL }, valign: "middle", margin: 0.1 });
    box(s, CX, 5.4, CW, 0.9, CARD2);
    T(s, "Quy tắc của kênh: mốc nào bị phá thì ghi nhận sai hoặc đổi trước, rồi mới đưa mốc mới. Không dời mốc.", { x: CX + 0.3, y: 5.4, w: CW - 0.6, h: 0.9, fontSize: 14, color: SILVER, valign: "middle" }); }

  // 4–6. THẾ GIỚI
  for (const w of D.world) { const s = slide(w.tag, w.title, N.world);
    const iw = 6.25, ih = iw * 2.9 / 5.6;
    if (w.img) s.addImage({ path: w.img, x: CX, y: CY, w: iw, h: ih });
    else { box(s, CX, CY, iw, ih); T(s, "Chưa lấy được chuỗi giá 1 năm", { x: CX, y: CY, w: iw, h: ih, fontSize: 14, color: MUTED, align: "center", valign: "middle" }); }
    const cw = (iw - 0.4) / 3, cy = CY + ih + 0.3;
    w.chips.forEach(([l, v], i) => { const x = CX + i * (cw + 0.2); box(s, x, cy, cw, 1.1);
      T(s, l, { x: x + 0.18, y: cy + 0.14, w: cw - 0.3, h: 0.3, fontSize: 11, color: MUTED });
      T(s, v, { x: x + 0.18, y: cy + 0.48, w: cw - 0.3, h: 0.45, fontSize: 17, bold: true, color: chgColor(v) === SILVER ? WHITE : chgColor(v) }); });
    const rx = CX + iw + 0.3, rw = CX + CW - rx; box(s, rx, CY, rw, CB - CY);
    T(s, w.big, { x: rx + 0.25, y: CY + 0.2, w: rw - 0.4, h: 0.75, fontSize: 38, bold: true, color: WATER, fit: "shrink" });
    T(s, w.unit, { x: rx + 0.25, y: CY + 0.95, w: rw - 0.4, h: 0.3, fontSize: 12, color: MUTED });
    T(s, [{ text: "KÊNH TRUYỀN DẪN", options: { fontSize: 11, bold: true, color: MUTED, breakLine: true, charSpacing: 1 } },
      { text: w.chan, options: { fontSize: 13.5, color: WHITE, breakLine: true, paraSpaceAfter: 12 } },
      { text: "NẾU VƯỢT NGƯỠNG", options: { fontSize: 11, bold: true, color: MUTED, breakLine: true, charSpacing: 1 } },
      { text: w.cross, options: { fontSize: 13.5, color: WHITE } }], { x: rx + 0.25, y: CY + 1.45, w: rw - 0.45, h: 3.5, fit: "shrink" }); }

  // 7. ĐỘ RỘNG
  { const B = D.breadth; const s = slide("SỨC KHỎE THỊ TRƯỜNG", "Độ rộng thị trường HOSE", N.vn);
    const items = [[String(B.tang), "mã tăng", UP], [String(B.dung), "đứng giá", SILVER], [String(B.giam), "mã giảm", DOWN], [`${B.tran ?? "—"} / ${B.san ?? "—"}`, "trần / sàn", WATER]];
    const w = (CW - 0.9) / 4;
    items.forEach(([v, l, c], i) => { const x = CX + i * (w + 0.3); box(s, x, 1.6, w, 1.6);
      T(s, v, { x: x + 0.25, y: 1.78, w: w - 0.4, h: 0.85, fontSize: 46, bold: true, color: c });
      T(s, l, { x: x + 0.25, y: 2.65, w: w - 0.4, h: 0.35, fontSize: 15, color: SILVER }); });
    const tot = B.tang + B.dung + B.giam || 1; let x = CX;
    [[B.tang, UP], [B.dung, "5B6F8E"], [B.giam, DOWN]].forEach(([v, c]) => { const w2 = CW * v / tot; if (w2 <= 0) return;
      s.addShape("rect", { x, y: 3.65, w: w2, h: 0.62, fill: { color: c }, line: { color: PANEL, width: 1.5 } });
      if (w2 > 0.5) T(s, `${Math.round(v / tot * 100)}%`, { x, y: 3.65, w: w2, h: 0.62, fontSize: 15, bold: true, color: BG, align: "center", valign: "middle" }); x += w2; });
    T(s, "Tỷ lệ mã tăng · đứng · giảm trên HOSE", { x: CX, y: 4.35, w: 5, h: 0.3, fontSize: 11, color: MUTED });
    box(s, CX, 4.85, CW, 1.4, CARD2);
    T(s, [{ text: B.head, options: { bold: true, color: B.giam > B.tang ? DOWN : UP } }, { text: B.note, options: { color: WHITE } }],
      { x: CX + 0.3, y: 4.95, w: CW - 0.6, h: 1.2, fontSize: 15, valign: "middle", fit: "shrink" }); }

  // 8. THANH KHOẢN
  { const L = D.liquidity; const s = slide("THANH KHOẢN THỰC", `Khớp lệnh ${vn(L.khop, 0)} tỷ, bằng ${vn(L.x, 2)} lần TB20`, N.vn);
    box(s, CX, CY, 5.3, CB - CY);
    s.addChart(pres.charts.BAR, [{ name: "Khớp lệnh (tỷ)", labels: ["Phiên trước", "Hôm nay", "TB5", "TB20"], values: L.vals.map((v) => v || 0) }], {
      x: CX + 0.15, y: CY + 0.15, w: 5.0, h: CB - CY - 0.3, barDir: "col", chartColors: ["5B7BA8", WATER, "5B7BA8", "5B7BA8"],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "#0\\.000", dataLabelColor: WHITE, dataLabelFontSize: 13, dataLabelFontBold: true,
      dataLabelFontFace: "+mn-lt", catAxisLabelColor: SILVER, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt", valAxisHidden: true,
      valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, showTitle: true, title: "Giá trị khớp lệnh HOSE (tỷ đồng)",
      titleColor: SILVER, titleFontSize: 13, titleFontFace: "+mn-lt", barGapWidthPct: 60, valAxisMinVal: 0 });
    const rx = CX + 5.6, rw = CW - 5.6; box(s, rx, CY, rw, 2.75);
    T(s, "TỔNG GIÁ TRỊ HOSE", { x: rx + 0.25, y: CY + 0.2, w: rw - 0.5, h: 0.3, fontSize: 11, bold: true, color: MUTED, charSpacing: 1 });
    T(s, `${vn(L.tong, 0)} tỷ`, { x: rx + 0.25, y: CY + 0.5, w: rw - 0.5, h: 0.6, fontSize: 30, bold: true });
    const bw = rw - 0.5, kx = rx + 0.25, ky = CY + 1.3, p = Math.min(Math.max((L.tt_pct || 0) / 100, 0), 1);
    s.addShape("rect", { x: kx, y: ky, w: bw * (1 - p), h: 0.42, fill: { color: WATER }, line: { color: CARD, width: 1 } });
    if (p > 0) s.addShape("rect", { x: kx + bw * (1 - p), y: ky, w: bw * p, h: 0.42, fill: { color: VIOLET }, line: { color: CARD, width: 1 } });
    T(s, [{ text: "■ ", options: { color: WATER } }, { text: `Khớp lệnh ${vn(L.khop, 0)} tỷ (${Math.round((1 - p) * 100)}%)`, options: { breakLine: true } },
      { text: "■ ", options: { color: VIOLET } }, { text: `Thỏa thuận ${vn(L.tt, 0)} tỷ (${Math.round(p * 100)}%)` }], { x: kx, y: ky + 0.55, w: bw, h: 0.75, fontSize: 14 });
    box(s, rx, CY + 2.95, rw, CB - CY - 2.95, CARD2);
    T(s, [{ text: `${vn(L.x, 2)}×`, options: { fontSize: 40, bold: true, color: (L.x || 0) < 1 ? DOWN : UP, breakLine: true } },
      { text: "khớp lệnh so với TB20", options: { fontSize: 13, color: MUTED, breakLine: true, paraSpaceAfter: 8 } },
      { text: L.note, options: { fontSize: 14, color: WHITE } }], { x: rx + 0.25, y: CY + 3.1, w: rw - 0.5, h: 1.9, fit: "shrink" }); }

  // 9. DÒNG TIỀN
  { const F = D.foreign; const s = slide("DÒNG TIỀN", `Khối ngoại ${(F.phien || 0) < 0 ? "bán" : "mua"} ròng ${vn(Math.abs(F.phien || 0), 0)} tỷ`, N.vn);
    const w = (CW - 0.6) / 3;
    [[F.phien, "Ròng phiên (HOSE)"], [F.thang, "Lũy kế tháng"], [F.nam, "Lũy kế từ đầu năm"]].forEach(([v, l], i) => { const x = CX + i * (w + 0.3); box(s, x, CY, w, 1.25);
      T(s, `${vn(v, (Math.abs(v || 0) < 1000) ? 1 : 0, true)} tỷ`, { x: x + 0.25, y: CY + 0.15, w: w - 0.4, h: 0.6, fontSize: 28, bold: true, color: (v || 0) < 0 ? DOWN : UP, fit: "shrink" });
      T(s, l, { x: x + 0.25, y: CY + 0.8, w: w - 0.4, h: 0.3, fontSize: 13, color: SILVER }); });
    box(s, CX, CY + 1.45, 6.3, CB - CY - 1.45);
    if (F.labels.length) { const mx = Math.max(...F.vals.map((v) => Math.abs(v))) * 10;
      s.addChart(pres.charts.BAR, [{ name: "Ròng", labels: F.labels, values: F.vals.map((v) => Math.round(v * 10)) }], {
        x: CX + 0.1, y: CY + 1.55, w: 6.1, h: CB - CY - 1.65, barDir: "bar", chartColors: [UP], invertedColors: [DOWN],
        showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0\\,0;-0\\,0", dataLabelColor: WHITE, dataLabelFontSize: 12, dataLabelFontBold: true,
        dataLabelFontFace: "+mn-lt", catAxisLabelColor: WHITE, catAxisLabelFontSize: 13, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin", catAxisLabelPos: "low",
        valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: -mx * 1.3, valAxisMaxVal: mx * 1.3,
        showTitle: true, title: "Mã khối ngoại giao dịch ròng nhiều nhất (tỷ)", titleColor: SILVER, titleFontSize: 12, titleFontFace: "+mn-lt", barGapWidthPct: 45 }); }
    const rx = CX + 6.6, rw = CW - 6.6; box(s, rx, CY + 1.45, rw, 1.75);
    T(s, [{ text: "TỰ DOANH", options: { fontSize: 11, bold: true, color: MUTED, breakLine: true, charSpacing: 1 } },
      { text: F.td_hom_nay ? "Phiên hôm nay" : "Chưa có số phiên hôm nay", options: { fontSize: 15, bold: true, breakLine: true } },
      { text: F.td1, options: { fontSize: 13, color: SILVER } }], { x: rx + 0.22, y: CY + 1.62, w: rw - 0.4, h: 1.45 });
    box(s, rx, CY + 3.4, rw, CB - CY - 3.4, CARD2);
    T(s, [{ text: "CÁCH ĐỌC", options: { fontSize: 11, bold: true, color: MUTED, breakLine: true, charSpacing: 1 } }, { text: F.doc, options: { fontSize: 14 } }],
      { x: rx + 0.22, y: CY + 3.55, w: rw - 0.4, h: 1.5, fit: "shrink" }); }

  // 10. WATERFALL
  { const Z = D.distort; const s = slide("INDEX THẬT SỰ TĂNG/GIẢM BAO NHIÊU", `Bỏ nhóm Vin, phần còn lại ${vn(Z.con_lai, 2, true)} điểm`, N.distort);
    box(s, CX, CY, 5.9, CB - CY);
    const vin = Z.vin || 0, rest = Z.con_lai || 0, idx = Z.index || 0;
    const top = Math.max(0, vin, vin + rest, idx), bot = Math.min(0, vin, vin + rest, idx), span = (top - bot) || 1;
    const k = 3.3 / span, zeroY = CY + 0.75 + top * k, bw = 1.25, gx = CX + 0.5;
    s.addShape("line", { x: CX + 0.3, y: zeroY, w: 5.3, h: 0, line: { color: MUTED, width: 1, dashType: "dash" } });
    [["Nhóm Vin", 0, vin], ["Phần còn lại", vin, vin + rest], ["VN-Index", 0, idx]].forEach(([lab, a, b], i) => {
      const c = b >= a ? UP : DOWN, y0 = zeroY - Math.max(a, b) * k, h = Math.max(Math.abs(a - b) * k, 0.02), x = gx + i * (bw + 0.55);
      s.addShape("rect", { x, y: y0, w: bw, h, fill: { color: c }, line: { color: c, width: 0 } });
      T(s, vn(i === 1 ? rest : b, 2, true), { x: x - 0.2, y: b >= a ? y0 - 0.45 : y0 + h + 0.05, w: bw + 0.4, h: 0.4, fontSize: 20, bold: true, color: c, align: "center" });
      T(s, lab, { x: x - 0.25, y: CB - 0.5, w: bw + 0.5, h: 0.35, fontSize: 13, bold: true, color: SILVER, align: "center" }); });
    const rx = CX + 6.2, rw = CW - 6.2; box(s, rx, CY, rw, CB - CY, CARD2);
    T(s, [{ text: `${Z.big_ma} đóng góp`, options: { fontSize: 14, color: SILVER, breakLine: true } },
      { text: `${vn(Z.big_diem, 2, true)} điểm`, options: { fontSize: 32, bold: true, color: (Z.big_diem || 0) >= 0 ? UP : DOWN, breakLine: true, paraSpaceAfter: 12 } },
      { text: Z.note, options: { fontSize: 14 } }], { x: rx + 0.25, y: CY + 0.3, w: rw - 0.45, h: 4.6, fit: "shrink" }); }

  // 11. ĐÓNG GÓP ĐIỂM
  { const Z = D.distort; const s = slide("INDEX THẬT SỰ TĂNG/GIẢM BAO NHIÊU", "Mã ảnh hưởng mạnh nhất tới VN-Index", N.distort);
    box(s, CX, CY, 6.6, CB - CY); const mx = Math.max(...Z.vals.map((v) => Math.abs(v))) * 100;
    s.addChart(pres.charts.BAR, [{ name: "Đóng góp", labels: Z.labels, values: Z.vals.map((v) => Math.round(v * 100)) }], {
      x: CX + 0.15, y: CY + 0.15, w: 6.3, h: CB - CY - 0.3, barDir: "bar", chartColors: [UP], invertedColors: [DOWN],
      showValue: true, dataLabelPosition: "outEnd", dataLabelFormatCode: "+0\\,00;-0\\,00", dataLabelColor: WHITE, dataLabelFontSize: 13, dataLabelFontBold: true,
      dataLabelFontFace: "+mn-lt", catAxisLabelColor: WHITE, catAxisLabelFontSize: 14, catAxisLabelFontFace: "+mn-lt", catAxisOrientation: "maxMin", catAxisLabelPos: "low",
      valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, valAxisMinVal: -mx * 1.25, valAxisMaxVal: mx * 1.25,
      showTitle: true, title: `Đóng góp điểm vào VN-Index phiên ${M.date}`, titleColor: SILVER, titleFontSize: 13, titleFontFace: "+mn-lt", barGapWidthPct: 40 });
    const rx = CX + 6.9, rw = CW - 6.9;
    [["Nhóm Vin", Z.vin], ["Phần còn lại", Z.con_lai], ["VN-Index", Z.index]].forEach(([l, v], i) => { const y = CY + i * 1.75; box(s, rx, y, rw, 1.5, CARD2);
      T(s, l, { x: rx + 0.25, y: y + 0.18, w: rw - 0.4, h: 0.3, fontSize: 13, color: SILVER });
      T(s, `${vn(v, 2, true)} điểm`, { x: rx + 0.25, y: y + 0.55, w: rw - 0.4, h: 0.7, fontSize: 28, bold: true, color: (v || 0) >= 0 ? UP : DOWN }); }); }

  // 12. CHART VN-INDEX
  { const s = slide("BẢN ĐỒ KỸ THUẬT", D.vni.title, N.tech); const ih = CW * 3.83 / 7.8;
    if (D.vni.img) s.addImage({ path: D.vni.img, x: CX, y: CY, w: CW, h: ih });
    T(s, D.vni.caption, { x: CX, y: CY + ih + 0.08, w: CW, h: 0.4, fontSize: 12, color: SILVER, fit: "shrink" }); }

  // 13. HAI NHÁNH
  { const S = D.scenario; const s = slide("BẢN ĐỒ KỸ THUẬT", S.title, N.tech); const cw = (CW - 0.3) / 2, ch = 2.55;
    [[UP, ic.up, "NẾU GIỮ", S.giu], [DOWN, ic.down, "NẾU THỦNG", S.thung]].forEach(([c, im, h, t], i) => { const x = CX + i * (cw + 0.3); box(s, x, CY, cw, ch);
      circleIcon(s, x + 0.25, CY + 0.25, 0.55, c, im);
      T(s, h, { x: x + 0.95, y: CY + 0.3, w: cw - 1.1, h: 0.45, fontSize: 20, bold: true, color: c });
      T(s, t, { x: x + 0.3, y: CY + 0.95, w: cw - 0.55, h: ch - 1.1, fontSize: 14.5, fit: "shrink" }); });
    const y2 = CY + ch + 0.3, h2 = CB - y2;
    [[ic.check, "XÁC NHẬN", S.xac_nhan, WATER], [ic.times, "VÔ HIỆU KỊCH BẢN", S.vo_hieu, DOWN]].forEach(([im, h, t, c], i) => { const x = CX + i * (cw + 0.3); box(s, x, y2, cw, h2, CARD2);
      circleIcon(s, x + 0.25, y2 + 0.25, 0.5, c, im);
      T(s, h, { x: x + 0.9, y: y2 + 0.3, w: cw - 1.1, h: 0.4, fontSize: 14, bold: true, color: c, charSpacing: 1 });
      T(s, t, { x: x + 0.3, y: y2 + 0.9, w: cw - 0.55, h: h2 - 1.0, fontSize: 14.5, fit: "shrink" }); }); }

  // NGÀNH + MÃ
  const SK = D.stocks;
  function stockTable(s, syms, y) {
    const H = (t) => ({ text: t, options: { bold: true, color: MUTED, fill: { color: PANEL }, fontSize: 12 } });
    const rows = [[H("Mã"), H("Giá"), H("%"), H("Mốc theo dõi"), H("Hỗ trợ kế tiếp"), H("Kháng cự kế tiếp"), H("Xác nhận"), H("Định giá")]];
    syms.forEach((k) => { const v = SK[k]; rows.push([{ text: v.sym, options: { bold: true, fontSize: 15 } }, { text: v.price }, { text: v.chg, options: { bold: true, color: chgColor(v.chg) } },
      { text: v.watch, options: { bold: true } }, { text: v.sup, options: { bold: true, color: UP } }, { text: v.res, options: { bold: true, color: DOWN } },
      { text: v.conf, options: { color: SILVER, fontSize: 11 } }, { text: v.val, options: { color: SILVER, fontSize: 11 } }]); });
    const rh = syms.length > 5 ? 0.58 : 0.7;
    s.addTable(rows, { x: CX, y, w: CW, colW: [0.75, 0.9, 0.9, 1.15, 1.15, 1.2, 2.33, 1.3], fontFace: FONT, fontSize: 14, color: WHITE,
      fill: { color: CARD }, border: { type: "solid", pt: 0.75, color: PANEL }, rowH: rh, valign: "middle", margin: 0.07 });
    return y + rh * rows.length;
  }
  function stockSlide(k, tag, notes, why) {
    const v = SK[k]; const s = slide(tag, v.head, notes); const iw = 6.75, ih = iw * 3.85 / 5.7;
    if (v.img) s.addImage({ path: v.img, x: CX, y: CY, w: iw, h: ih });
    T(s, "Mốc trong bảng phân tích (đường kẻ) + vùng tự tính (hộp mờ) · nến ngày, dữ liệu VNDirect", { x: CX, y: CY + ih + 0.1, w: iw, h: 0.3, fontSize: 10, color: MUTED });
    const rx = CX + iw + 0.2, rw = CX + CW - rx; box(s, rx, CY, rw, CB - CY);
    T(s, [{ text: v.sym + "  ", options: { fontSize: 24, bold: true } }, { text: v.price + "  ", options: { fontSize: 18, bold: true } },
      { text: v.chg, options: { fontSize: 15, bold: true, color: chgColor(v.chg) } }], { x: rx + 0.2, y: CY + 0.15, w: rw - 0.3, h: 0.5, valign: "middle" });
    const L = (t) => ({ text: t, options: { fontSize: 10, bold: true, color: MUTED, breakLine: true, charSpacing: 1 } });
    const V = (t, c = WHITE, last = false) => ({ text: t, options: { fontSize: 12.5, color: c, bold: c === UP || c === DOWN, breakLine: !last, paraSpaceAfter: 6 } });
    const runs = [...(why ? [L("VÌ SAO ĐÁNG NÓI"), V(why)] : [L("CẤU TRÚC"), V(v.struct)]), L("MỐC THEO DÕI"), V(v.watch), L("THỦNG THÌ"), V(v.broke),
      L("HỖ TRỢ KẾ TIẾP"), V(v.sup, UP), L("KHÁNG CỰ KẾ TIẾP"), V(v.res, DOWN), L("XÁC NHẬN"), V(v.conf, WATER),
      L("ĐỊNH GIÁ"), V(v.val + (v.extra && !why ? "  ·  " + v.extra : ""), SILVER, true)];
    T(s, runs, { x: rx + 0.2, y: CY + 0.75, w: rw - 0.35, h: CB - CY - 0.85, fit: "shrink" });
  }
  for (const sec of D.sectors) {
    if (!sec.syms.length) continue;
    const s = slide(sec.tag, sec.title, sec.notes); box(s, CX, CY, CW, 0.75, CARD2);
    T(s, sec.lead, { x: CX + 0.25, y: CY, w: CW - 0.5, h: 0.75, fontSize: 15, valign: "middle", fit: "shrink" });
    let y = stockTable(s, sec.syms, CY + 0.95);
    if (sec.checklist && y < CB - 1.2) { y += 0.25; const cw = (CW - 0.6) / 3;
      sec.checklist.forEach(([h, st], i) => { const x = CX + i * (cw + 0.3), ok = st.startsWith("Có"); box(s, x, y, cw, CB - y);
        circleIcon(s, x + 0.2, y + 0.2, 0.42, ok ? UP : DOWN, ok ? ic.check : ic.times);
        T(s, h, { x: x + 0.75, y: y + 0.22, w: cw - 0.9, h: 0.4, fontSize: 15, bold: true, valign: "middle" });
        T(s, st, { x: x + 0.2, y: y + 0.75, w: cw - 0.4, h: CB - y - 0.85, fontSize: 13, color: SILVER, fit: "shrink" }); }); }
    for (const k of sec.syms) stockSlide(k, sec.tag, SK[k].notes || sec.notes);
  }

  // NHÓM KHÁC
  for (const g of D.others) {
    const s = slide("QUÉT NGÀNH · CÁC NHÓM KHÁC", g.map((x) => x[0]).join(", "), N.scan);
    const cw = (CW - 0.6) / 3, ch = CB - CY;
    g.forEach(([name, note, items], i) => { const x = CX + i * (cw + 0.3); box(s, x, CY, cw, ch);
      T(s, name, { x: x + 0.22, y: CY + 0.15, w: cw - 0.4, h: 0.38, fontSize: 17, bold: true, color: WATER, fit: "shrink" });
      T(s, note, { x: x + 0.22, y: CY + 0.55, w: cw - 0.4, h: 0.5, fontSize: 11.5, color: MUTED });
      items.forEach(([m, p, c, d], j) => { const yy = CY + 1.2 + j * 0.95;
        T(s, m, { x: x + 0.22, y: yy, w: 0.8, h: 0.32, fontSize: 15, bold: true });
        T(s, p, { x: x + 1.0, y: yy, w: 0.95, h: 0.32, fontSize: 15 });
        T(s, c, { x: x + 1.95, y: yy, w: 0.95, h: 0.32, fontSize: 15, bold: true, color: chgColor(c) });
        if (d) T(s, d, { x: x + 0.22, y: yy + 0.34, w: cw - 0.4, h: 0.3, fontSize: 11.5, color: SILVER }); }); });
  }

  // XOAY VÒNG
  { const R = D.rotation; const s = slide("XOAY VÒNG", "Tiền đang đi đâu", N.picks);
    box(s, CX, CY, CW, 1.9, CARD2); T(s, R.text, { x: CX + 0.3, y: CY + 0.15, w: CW - 0.6, h: 1.6, fontSize: 15, valign: "middle", fit: "shrink" });
    box(s, CX, CY + 2.15, CW, CB - CY - 2.15);
    T(s, "LUẬN ĐIỂM CHÍNH", { x: CX + 0.3, y: CY + 2.35, w: 6, h: 0.3, fontSize: 12, bold: true, color: WATER, charSpacing: 1 });
    T(s, bullets(R.points, 8), { x: CX + 0.3, y: CY + 2.75, w: CW - 0.6, h: CB - CY - 2.95, fontSize: 14, fit: "shrink" }); }

  // MÃ ĐÁNG NÓI
  if (D.picks.length) { const s = slide("MÃ ĐÁNG NÓI", `${D.picks.length} mã kể câu chuyện của phiên`, N.picks);
    const cw = (CW - 0.6) / 3, ih = cw * 3.2 / 3.3;
    D.picks.forEach((k, i) => { const v = SK[k], x = CX + i * (cw + 0.3); box(s, x, CY, cw, CB - CY);
      if (v.mini) s.addImage({ path: v.mini, x: x + 0.08, y: CY + 0.08, w: cw - 0.16, h: ih - 0.16 });
      T(s, [{ text: v.price + "  ", options: { fontSize: 18, bold: true } }, { text: v.chg, options: { fontSize: 16, bold: true, color: chgColor(v.chg) } }], { x: x + 0.2, y: CY + ih + 0.05, w: cw - 0.3, h: 0.4 });
      T(s, D.whys[k] || "", { x: x + 0.2, y: CY + ih + 0.5, w: cw - 0.3, h: CB - CY - ih - 0.6, fontSize: 12.5, fit: "shrink" }); });
    for (const k of D.picks) stockSlide(k, "MÃ ĐÁNG NÓI", SK[k].pick_notes || N.picks, D.whys[k]); }

  // REGIME
  { const R = D.regime; const s = slide("TRẠNG THÁI THỊ TRƯỜNG", R.ten, N.regime);
    const thieu = /thiếu/i.test(R.co_tien);
    pill(s, CX, CY, 3.6, 0.5, `${(R.co_tien || "").toUpperCase()} · khớp ${vn(R.x, 2)}× TB20`, thieu ? DOWN : UP, BG, 14);
    pill(s, CX + 3.8, CY, 3.6, 0.5, R.breadth, CARD2, WHITE, 14);
    const cw = (CW - 0.3) / 2, y = CY + 0.8, h = CB - y;
    [[UP, "ỦNG HỘ", R.ung_ho], [DOWN, "PHẢN BÁC", R.phan_bac]].forEach(([c, hd, ls], i) => { const x = CX + i * (cw + 0.3); box(s, x, y, cw, h);
      T(s, hd, { x: x + 0.3, y: y + 0.25, w: cw - 0.5, h: 0.4, fontSize: 16, bold: true, color: c, charSpacing: 2 });
      T(s, bullets(ls, 12), { x: x + 0.3, y: y + 0.85, w: cw - 0.55, h: h - 1.0, fontSize: 15, fit: "shrink" }); }); }

  // PHIÊN TỚI
  { const P = D.next; const s = slide("PHIÊN TỚI CẦN THEO DÕI", "Củng cố, làm yếu, xác nhận, vô hiệu", N.regime);
    const cw = (CW - 0.3) / 2, ch = (CB - CY - 0.3) / 2;
    [[ic.shield, UP, "CỦNG CỐ", P.cung_co], [ic.eye, SILVER, "LÀM YẾU", P.lam_yeu], [ic.check, WATER, "XÁC NHẬN", P.xac_nhan], [ic.times, DOWN, "VÔ HIỆU", P.vo_hieu]].forEach(([im, c, h, t], i) => {
      const x = CX + (i % 2) * (cw + 0.3), y = CY + Math.floor(i / 2) * (ch + 0.3); box(s, x, y, cw, ch); circleIcon(s, x + 0.3, y + 0.3, 0.6, c, im);
      T(s, h, { x: x + 1.1, y: y + 0.36, w: cw - 1.3, h: 0.5, fontSize: 20, bold: true, color: c, charSpacing: 1 });
      T(s, t, { x: x + 0.3, y: y + 1.05, w: cw - 0.6, h: ch - 1.2, fontSize: 15, fit: "shrink" }); }); }

  // KẾT PHIÊN
  { const s = slide("KẾT PHIÊN", "Cảm ơn anh chị đã theo dõi", N.bye);
    T(s, "Hẹn gặp lại anh chị trong buổi rà soát phiên mai.", { x: CX, y: CY + 0.1, w: CW, h: 0.5, fontSize: 20, color: SILVER });
    const cw = (CW - 0.3) / 2;
    [[ic.yt, "YouTube", M.youtube], [ic.tt, "TikTok", M.tiktok], [ic.web, "Website", M.website], [ic.phone, "Tư vấn", M.contact.replace("Tư vấn ", "")]].forEach(([im, l, v], i) => {
      const x = CX + (i % 2) * (cw + 0.3), y = CY + 0.95 + Math.floor(i / 2) * 1.5; box(s, x, y, cw, 1.25);
      s.addImage({ data: im, x: x + 0.35, y: y + 0.4, w: 0.45, h: 0.45 });
      T(s, l, { x: x + 1.05, y: y + 0.2, w: cw - 1.2, h: 0.3, fontSize: 12, color: MUTED });
      T(s, v, { x: x + 1.05, y: y + 0.5, w: cw - 1.2, h: 0.5, fontSize: v.length > 20 ? 17 : 20, bold: true }); });
  }

  slide("TÊN PHẦN", "Khung trống để chèn nội dung khác", "Slide khung trống.");
  await pres.writeFile({ fileName: OUT });
  console.log("wrote", OUT, n, "slides");
})();
