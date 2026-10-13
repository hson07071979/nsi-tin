/* ============================================================================
   TRANG /daily — NSI Daily Market (chỉ trang quản trị nsi-quantri)
   Gắn giống /tin: trong serveSite(), sau bước kiểm admin:
     if (ADMIN && (url.pathname === '/daily' || url.pathname.startsWith('/daily/'))) return handleDaily(req, env)

   Biến của Worker nsi-quantri:
     TIN_REPO   (đã có)  hson07071979/nsi-tin
     TIN_TOKEN  (đã có)  fine-grained, repo nsi-tin, Contents: Read-only      → đọc out/daily/*.json
     DAILY_DISPATCH_TOKEN (MỚI, Secret) fine-grained, repo nsi-tin, Actions: Read and write
                                                                              → nút "Viết lại theo view"
   Đường:
     GET  /daily                 trang
     GET  /daily/data?ngay=…     JSON bản ngày đó (trống = latest)
     GET  /daily/index           danh sách ngày
     POST /daily/viet-lai        {view, ngay} → gọi workflow daily_market.yml che_do=viet_lai
     GET  /daily/ppt?ngay=…      tải PPT video (KV binding SLIDES, khóa daily/<ngày>.pptx; trống = mới nhất)
     GET  /daily/ppt-info?ngay=… {co, nguon: gemini|claude, luc} để hiện nhãn nút

   Biến mới cho nút Tải PPT (13/10/2026): KV namespace binding SLIDES → namespace nsi-slides (xem slides/README.md).
   ========================================================================== */

export async function handleDaily(req, env) {
  const url = new URL(req.url)
  const p = url.pathname.replace(/\/+$/, '') || '/daily'
  if (p === '/daily' && req.method === 'GET') {
    return new Response(DAILY_HTML, { headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'no-store' } })
  }
  if (p === '/daily/data' && req.method === 'GET') {
    const ngay = (url.searchParams.get('ngay') || '').trim()
    if (ngay && !/^\d{4}-\d{2}-\d{2}$/.test(ngay)) return jErr(400, 'ngày sai dạng')
    return docRepo(env, `out/daily/${ngay || 'latest'}.json`)
  }
  if (p === '/daily/index' && req.method === 'GET') return docRepo(env, 'out/daily/index.json')
  if (p === '/daily/viet-lai' && req.method === 'POST') return vietLai(req, env, url)
  if ((p === '/daily/ppt' || p === '/daily/ppt-info') && req.method === 'GET') return taiPpt(env, url, p.endsWith('info'))
  return jErr(404, 'không có đường này')
}

async function docRepo(env, path) {
  const repo = env.TIN_REPO || 'hson07071979/nsi-tin'
  if (!env.TIN_TOKEN) return jErr(500, 'Worker chưa có TIN_TOKEN')
  const r = await fetch(`https://api.github.com/repos/${repo}/contents/${path}?ref=main`, {
    headers: { Authorization: `Bearer ${env.TIN_TOKEN}`, Accept: 'application/vnd.github.raw',
               'User-Agent': 'nsi-quantri-daily', 'X-GitHub-Api-Version': '2022-11-28' },
  })
  if (r.status === 404) return jErr(404, 'chưa có bản nào')
  if (!r.ok) return jErr(502, `GitHub ${r.status}`)
  return new Response(r.body, { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } })
}

async function vietLai(req, env, url) {
  // chống gửi chéo trang: chỉ nhận yêu cầu từ chính trang quản trị
  const origin = req.headers.get('Origin') || ''
  if (origin && origin !== url.origin) return jErr(403, 'sai nguồn gửi')
  let b
  try { b = await req.json() } catch (e) { return jErr(400, 'JSON sai') }
  const view = String(b.view || '').trim().slice(0, 2500)
  const ngay = String(b.ngay || '').trim()
  if (view.length < 10) return jErr(400, 'view quá ngắn')
  if (ngay && !/^\d{4}-\d{2}-\d{2}$/.test(ngay)) return jErr(400, 'ngày sai dạng')
  // Cách 1 (đang dùng): gọi Worker nsi-dong-ho qua Service binding DONG_HO (entrypoint DaiLyDispatch) — dùng token sẵn có
  // của đồng hồ ảo, không cần token mới, không có đường công khai.
  if (env.DONG_HO && typeof env.DONG_HO.vietLai === 'function') {
    const kq = await env.DONG_HO.vietLai(view, ngay)
    if (!kq || !kq.ok) return jErr(502, (kq && kq.loi) || 'đồng hồ ảo không trả lời')
    return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json; charset=utf-8' } })
  }
  // Cách 2 (dự phòng): token riêng DAILY_DISPATCH_TOKEN (Actions: Read and write, repo nsi-tin)
  if (!env.DAILY_DISPATCH_TOKEN) return jErr(500, 'Worker chưa có Service binding DONG_HO (hoặc DAILY_DISPATCH_TOKEN)')
  const repo = env.TIN_REPO || 'hson07071979/nsi-tin'
  const r = await fetch(`https://api.github.com/repos/${repo}/actions/workflows/daily_market.yml/dispatches`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${env.DAILY_DISPATCH_TOKEN}`, Accept: 'application/vnd.github+json',
               'User-Agent': 'nsi-quantri-daily', 'X-GitHub-Api-Version': '2022-11-28', 'Content-Type': 'application/json' },
    body: JSON.stringify({ ref: 'main', inputs: { che_do: 'viet_lai', view, ngay } }),
  })
  if (r.status !== 204) return jErr(502, `GitHub ${r.status}: ${(await r.text()).slice(0, 160)}`)
  return new Response(JSON.stringify({ ok: true }), { headers: { 'content-type': 'application/json; charset=utf-8' } })
}

async function taiPpt(env, url, chiInfo) {
  if (!env.SLIDES) return jErr(500, 'Worker chưa gắn KV binding SLIDES')
  let ngay = (url.searchParams.get('ngay') || '').trim()
  if (ngay && !/^\d{4}-\d{2}-\d{2}$/.test(ngay)) return jErr(400, 'ngày sai dạng')
  if (!ngay) {
    const l = await env.SLIDES.get('daily/latest', { type: 'json' })
    if (!l) return jErr(404, 'chưa có PPT nào')
    ngay = l.ngay
  }
  const key = `daily/${ngay}.pptx`
  const { value, metadata } = await env.SLIDES.getWithMetadata(key, { type: chiInfo ? 'text' : 'stream' })
  const m = metadata || {}
  if (chiInfo) {
    return new Response(JSON.stringify({ co: value !== null, ngay, nguon: m.nguon || '', luc: m.luc || '' }),
      { headers: { 'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store' } })
  }
  if (value === null) return jErr(404, `chưa có PPT phiên ${ngay}`)
  const nguon = m.nguon === 'claude' ? 'chinh-thuc' : 'nhap'
  return new Response(value, { headers: {
    'content-type': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    'content-disposition': `attachment; filename="NSF_RaSoat_${ngay}_${nguon}.pptx"`, 'cache-control': 'no-store' } })
}

function jErr(code, msg) {
  return new Response(JSON.stringify({ loi: msg }), { status: code, headers: { 'content-type': 'application/json; charset=utf-8' } })
}

const DAILY_HTML = `<!doctype html><html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>NSI Daily Market</title>
<style>
:root{--bg:#f6f5f2;--card:#fff;--ink:#1d1f23;--mut:#6b6f76;--line:#e4e2dc;--acc:#1f5f8b;--up:#167a3e;--dn:#b42318;--warn:#a15c07;--chip:#eef2f6}
@media (prefers-color-scheme:dark){:root{--bg:#121417;--card:#1b1e22;--ink:#e8e6e1;--mut:#9aa0a8;--line:#2c3036;--acc:#6fb0e0;--up:#4cc27a;--dn:#ff6b5e;--warn:#e0a24a;--chip:#232830}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:980px;margin:0 auto;padding:16px}a{color:var(--acc)}h1{font-size:22px;margin:4px 0}h2{font-size:18px;margin:22px 0 8px}h3{font-size:15px;margin:14px 0 6px}
.top{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.top .sp{flex:1}.mut{color:var(--mut);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin:10px 0}
.pill{display:inline-block;padding:1px 9px;border-radius:99px;font-size:12px;font-weight:600;background:var(--chip)}
.dat{color:var(--up)}.mot_phan,.dry,.chi_so_lieu{color:var(--warn)}.loi_ai{color:var(--dn)}
.tabs{display:flex;gap:6px;flex-wrap:wrap;margin:12px 0}.tabs button{border:1px solid var(--line);background:var(--card);color:var(--ink);border-radius:8px;padding:6px 12px;font:inherit;cursor:pointer}
.tabs button.on{background:var(--acc);border-color:var(--acc);color:#fff}
.sec{border-left:3px solid var(--acc);padding:2px 0 2px 12px;margin:14px 0}.sec .h{font-weight:650}.sec .hinh{font-size:12.5px;color:var(--mut);font-style:italic;margin-top:4px}
.loi{white-space:pre-wrap}b.ma{color:var(--acc);background:var(--chip);padding:0 4px;border-radius:4px}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:10px}
table{border-collapse:collapse;width:100%;font-size:13.5px}td,th{border-bottom:1px solid var(--line);padding:5px 6px;text-align:left;vertical-align:top}
textarea{width:100%;min-height:110px;border:1px solid var(--line);border-radius:8px;padding:10px;font:inherit;background:var(--card);color:var(--ink)}
.btn{border:0;background:var(--acc);color:#fff;border-radius:8px;padding:8px 14px;font:inherit;cursor:pointer}.btn.g{background:var(--chip);color:var(--ink)}
details summary{cursor:pointer;font-weight:600}.warn{color:var(--warn)}.dn{color:var(--dn)}.up{color:var(--up)}
select{font:inherit;padding:5px 8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
</style></head><body><div class="wrap">
<div class="top"><div><h1>NSI Daily Market</h1><div class="mut">Bản nháp phân tích + lời thoại sau phiên · chỉ trang quản trị · <a href="/tin">Bản tin sáng</a> · <a href="/index.html#hieusuat">Xem web</a></div></div>
<span class="sp"></span><a class="btn" id="ppt" href="/daily/ppt">Tải PPT</a><span id="pptInfo" class="mut"></span><select id="ngay"></select></div>
<div id="app" class="card">Đang tải…</div>
<div class="card"><h2 style="margin-top:0">Viết lại theo view của anh</h2>
<p class="mut">Gõ nhận định sơ bộ (ví dụ "bank yếu, chứng chưa tạo đáy, Vin kéo index"). Bot làm THESIS CHECK từng ý rồi viết lại toàn bộ lời thoại. Mất khoảng 3–6 phút; trang tự cập nhật.</p>
<textarea id="view" maxlength="2500" placeholder="View sơ bộ của anh…"></textarea>
<div style="margin-top:8px;display:flex;gap:8px;align-items:center"><button class="btn" id="gui">Viết lại</button><span id="guiKq" class="mut"></span></div></div>
</div>
<script>
const $=s=>document.querySelector(s), esc=s=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let D=null, banOn=0, cho=null;
const TT={dat:'Đạt',mot_phan:'Một phần',chi_so_lieu:'Chỉ có phân tích số liệu',loi_du_lieu:'Lỗi nguồn dữ liệu',loi_ai:'Lỗi AI',dry:'Chạy thử',khong_phien:'Không có phiên',dang_chay:'Đang chạy'};
const so=(x,n=1)=>x==null?'—':Number(x).toLocaleString('vi-VN',{maximumFractionDigits:n});
const linkMa=s=>s.replace(/(^|[^\\/\\w])([A-Z]{3})(?![\\w\\/])/g,(all,a,m)=>(D&&D.fc&&maSet().has(m))?a+'<b class="ma">'+m+'</b>':all);
function maSet(){const s=new Set();Object.values((D.fc||{}).ma_theo_nhom||{}).forEach(a=>a.forEach(r=>s.add(r.ma)));return s}
async function j(u,o){const r=await fetch(u,o);const t=await r.json().catch(()=>({loi:'trả về không phải JSON'}));if(!r.ok)throw new Error(t.loi||r.status);return t}
async function napNgay(){try{const ix=await j('/daily/index');$('#ngay').innerHTML=ix.map(x=>'<option value="'+x.ngay+'">'+x.ngay+' · '+(TT[x.trang_thai_chay]||x.trang_thai_chay)+(x.so_lan_viet_lai?' · '+x.so_lan_viet_lai+' lần viết lại':'')+'</option>').join('')}catch(e){}}
async function pptInfo(ngay){const q=ngay?'?ngay='+ngay:'';$('#ppt').href='/daily/ppt'+q;try{const x=await j('/daily/ppt-info'+q);$('#pptInfo').textContent=x.co?(x.nguon==='claude'?'bản Claude đã kiểm':'bản nháp Gemini')+' · '+String(x.luc).slice(11,16):'chưa có PPT'}catch(e){$('#pptInfo').textContent=''}}
async function nap(ngay){pptInfo(ngay);try{D=await j('/daily/data'+(ngay?'?ngay='+ngay:''));ve()}catch(e){$('#app').innerHTML='<b>Chưa đọc được bản nào.</b> '+esc(e.message)}}
function sig(fc){if(!fc||!fc.vnindex)return'';const v=fc.vnindex,b=fc.breadth_hose||{},t=fc.thanh_khoan_hose_ty||{},n=(fc.khoi_ngoai_ty||{}).phien||{},g=fc.dong_gop_diem||{};
return '<div class="grid"><div><b>Index</b><br>'+so(v.dong_cua,2)+' <span class="'+(v.diem<0?'dn':'up')+'">'+(v.diem>0?'+':'')+so(v.diem,2)+' ('+so(v.pct,2)+'%)</span><br><span class="mut">nhóm Vin '+so(g.nhom_vin,1)+' điểm · phần còn lại '+so(g.phan_con_lai,1)+'</span></div>'
+'<div><b>Cổ phiếu (HOSE)</b><br>'+so(b.tang,0)+' tăng / '+so(b.giam,0)+' giảm / '+so(b.dung,0)+' đứng<br><span class="mut">trần '+so(b.tran,0)+' · sàn '+so(b.san,0)+'</span></div>'
+'<div><b>Dòng tiền</b><br>khớp '+so(t.gt_khop,0)+' tỷ (×'+so(t.khop_so_tb20,2)+' TB20)<br><span class="mut">thỏa thuận '+so(t.gt_thoa_thuan,0)+' tỷ · khối ngoại '+so(n.rong,0)+' tỷ</span></div></div>'}
function script(sc){if(!sc||!sc.phan)return'<p class="warn">Không có lời thoại.</p>';let chu=0;sc.phan.forEach(p=>chu+=String(p.loi_thoai||'').split(/\\s+/).length);
return '<h3>'+esc(sc.tieu_de_youtube||'')+'</h3><div class="mut">~'+chu+' chữ · ước '+Math.round(chu/155)+' phút đọc · <a href="#" onclick="chep(event)">chép toàn bộ lời thoại</a></div>'
+sc.phan.map(p=>'<div class="sec"><div class="h">'+esc(p.ten)+(p.phut?' <span class="mut">· '+esc(p.phut)+"'</span>":'')+'</div><div class="loi">'+linkMa(esc(p.loi_thoai))+'</div>'+(p.chen_hinh?'<div class="hinh">Chèn hình: '+esc(p.chen_hinh)+'</div>':'')+'</div>').join('')
+'<h2>3 clip TikTok</h2><div class="grid">'+(sc.tiktok||[]).map(t=>'<div class="card"><b>'+esc(t.tieu_de)+'</b><div class="mut">'+esc(t.goc||'')+' · '+esc(t.giay||'')+'s</div><div class="loi" style="margin-top:6px">'+esc(t.loi_thoai)+'</div></div>').join('')+'</div>'}
function phanTich(pt){if(!pt||!Object.keys(pt).length)return'';const kt=pt.ky_thuat_chi_so||{},rg=pt.regime||{};
const ng=(pt.nganh||[]).map(n=>'<h3>'+esc(n.nhom)+'</h3><p>'+linkMa(esc(n.nhan_dinh||''))+'</p>'+((n.ma||[]).length?'<table><tr><th>Mã</th><th>Cấu trúc</th><th>Mốc theo dõi</th><th>SL</th><th>Mục tiêu</th><th>Thủng thì</th><th>Xác nhận</th><th>Định giá</th></tr>'+(n.ma||[]).map(m=>'<tr><td>'+linkMa(esc(m.ma))+'</td><td>'+esc(m.cau_truc)+'</td><td>'+esc(m.moc_theo_doi)+(m.rong_hon_chuan_7?' <span class="warn">(rộng hơn 7%)</span>':'')+'</td><td>'+esc(m.sl==null?'':m.sl)+'</td><td>'+esc(m.muc_tieu==null?'':m.muc_tieu)+'</td><td>'+esc(m.thung_thi)+'</td><td>'+esc(m.xac_nhan)+'</td><td>'+esc(m.dinh_gia)+'</td></tr>').join('')+'</table>':'')).join('');
return '<details><summary>Bản phân tích 9 tầng</summary>'
+(pt.signature?'<p><b>Index:</b> '+esc(pt.signature.index_noi_gi)+'<br><b>Cổ phiếu:</b> '+esc(pt.signature.co_phieu_noi_gi)+'<br><b>Dòng tiền:</b> '+esc(pt.signature.dong_tien_noi_gi)+'</p>':'')
+'<h3>Mốc chính</h3><p><b>'+esc(kt.moc_chinh)+'</b> ('+esc(kt.loai_moc)+') — '+esc(kt.nguon_goc)+'<br>Giữ: '+esc(kt.neu_giu)+'<br>Thủng: '+esc(kt.neu_thung)+'<br>Xác nhận: '+esc(kt.xac_nhan)+' · Vô hiệu: '+esc(kt.vo_hieu)+'</p>'
+'<h3>Regime: '+esc(rg.ten)+' · '+esc(rg.co_tien)+'</h3><p>Ủng hộ: '+esc((rg.ung_ho||[]).join('; '))+'<br>Phản bác: '+esc((rg.phan_bac||[]).join('; '))+'<br>'+esc(rg.so_voi_den_nsi||'')+'</p>'
+['suc_khoe_vn','thanh_khoan','dong_tien','index_distortion','xoay_vong'].map(k=>pt[k]?'<p><b>'+k.replace(/_/g,' ')+':</b> '+linkMa(esc(pt[k]))+'</p>':'').join('')
+'<h3>Thế giới</h3><table>'+(pt.the_gioi||[]).map(t=>'<tr><td><b>'+esc(t.bien)+'</b><br><span class="mut">'+esc(t.muc)+'</span></td><td>'+esc(t.kenh_truyen_dan)+'</td><td>'+esc(t.he_qua_neu_vuot)+'</td></tr>').join('')+'</table>'
+ng+'<h3>Luận điểm chính</h3><ul>'+(pt.luan_diem_chinh||[]).map(x=>'<li>'+linkMa(esc(x))+'</li>').join('')+'</ul></details>'}
function ve(){if(!D)return;if(D.trang_thai_chay==='khong_phien'){$('#app').innerHTML='<b>'+esc(D.ngay)+':</b> '+esc(D.ghi_chu||'không có phiên');return}
const ban=D.ban||[];const vl=D.viet_lai||[];const tabs=ban.map((b,i)=>'<button data-i="'+i+'" class="'+(i===banOn?'on':'')+'">'+esc(b.nhan||('Bản '+(i+1)))+'</button>').concat(vl.map((v,i)=>'<button data-i="v'+i+'" class="'+(banOn==='v'+i?'on':'')+'">Viết lại '+(i+1)+'</button>'));
let body='';if(typeof banOn==='number'&&ban[banOn]){const b=ban[banOn];body=(b.loi&&b.loi.length?'<p class="warn">Cảnh báo: '+esc(b.loi.join(' · '))+'</p>':'')+script(b.script)+phanTich(b.phan_tich)}
else if(String(banOn).startsWith('v')){const v=vl[+String(banOn).slice(1)];const k=(v||{}).ket_qua||{};body='<p class="mut">View lúc '+esc(v.luc)+':</p><blockquote>'+esc(v.view)+'</blockquote>'
+'<h3>THESIS CHECK</h3><table><tr><th>Ý</th><th>Ủng hộ</th><th>Chống lại</th><th>Kết luận</th></tr>'+(k.thesis_check||[]).map(t=>'<tr><td>'+esc(t.y)+'</td><td>'+esc((t.ung_ho||[]).join('; '))+'</td><td>'+esc((t.chong_lai||[]).join('; '))+'</td><td><b>'+esc(t.ket_luan)+'</b><br><span class="mut">tự tin '+esc(t.tu_tin)+'</span></td></tr>').join('')+'</table>'
+'<p><b>View sau phản biện:</b> '+esc(k.view_sau_phan_bien||'')+'</p>'+(k.loi&&k.loi.length?'<p class="warn">'+esc(k.loi.join(' · '))+'</p>':'')+script(k.script)}
const so_=D.so_du_bao||{};const cham=(so_.vua_cham_hom_nay||[]).map(r=>'<li>'+esc(r.noi_dung||r.doi_tuong+' '+r.loai+' '+r.moc)+' → <b class="'+(r.ket_qua==='ĐÚNG'?'up':'dn')+'">'+esc(r.ket_qua)+'</b></li>').join('');
$('#app').innerHTML='<div class="top"><b>Phiên '+esc(D.ngay)+'</b><span class="pill '+esc(D.trang_thai_chay)+'">'+esc(TT[D.trang_thai_chay]||D.trang_thai_chay)+'</span><span class="mut">xong '+esc((D.xong_luc||'').slice(11,16))+'</span><span class="sp"></span><a href="#" class="mut" id="cach">Xem cách chạy</a></div>'
+sig(D.fc)+((D.fc||{}).thieu_du_lieu||[]).map(x=>'<div class="mut warn">Thiếu: '+esc(x)+'</div>').join('')
+(cham?'<h3>Sổ dự báo vừa chấm</h3><ul>'+cham+'</ul>':'')+'<div class="tabs">'+tabs.join('')+'</div><div id="ban">'+body+'</div>';
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{const i=b.dataset.i;banOn=/^\\d+$/.test(i)?+i:i;ve()});
$('#cach').onclick=e=>{e.preventDefault();alert(ban.map(b=>(b.nhan||'')+': '+(b.cach==='cach_2_buoc'?'phân tích trước rồi viết':'một lượt làm hết')+' · '+(b.model||'')).join('\\n'))}}
window.chep=e=>{e.preventDefault();const b=typeof banOn==='number'?(D.ban||[])[banOn]:(((D.viet_lai||[])[+String(banOn).slice(1)]||{}).ket_qua);const sc=(b||{}).script||{};
navigator.clipboard.writeText((sc.phan||[]).map(p=>'['+p.ten+']\\n'+p.loi_thoai).join('\\n\\n')).then(()=>alert('Đã chép.'))};
$('#ngay').onchange=e=>{banOn=0;nap(e.target.value)};
$('#gui').onclick=async()=>{const view=$('#view').value.trim();if(view.length<10){$('#guiKq').textContent='View ngắn quá.';return}
$('#gui').disabled=true;$('#guiKq').textContent='Đang gửi…';try{await j('/daily/viet-lai',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({view,ngay:$('#ngay').value||''})});
const n0=(D.viet_lai||[]).length;$('#guiKq').textContent='Đã gửi. Bot đang viết lại (3–6 phút)…';let k=0;clearInterval(cho);cho=setInterval(async()=>{k++;try{const x=await j('/daily/data'+($('#ngay').value?'?ngay='+$('#ngay').value:''));if((x.viet_lai||[]).length>n0){D=x;banOn='v'+(x.viet_lai.length-1);ve();clearInterval(cho);$('#guiKq').textContent='Xong.';$('#gui').disabled=false}}catch(e){}if(k>40){clearInterval(cho);$('#guiKq').textContent='Quá 10 phút chưa thấy — xem tab Actions của nsi-tin.';$('#gui').disabled=false}},15000)}
catch(e){$('#guiKq').textContent='Không gửi được: '+e.message;$('#gui').disabled=false}};
napNgay().then(()=>nap(''));
</script></body></html>`
