// Tải code đang chạy của Worker nsi-quantri qua Cloudflare API, áp ap-dung.mjs, kiểm cú pháp.
// Mặc định CHỈ CHẠY THỬ. Chỉ deploy khi DEPLOY=1 (anh tự bấm Run workflow, chọn deploy).
// Deploy chỉ thay code — giữ nguyên biến, secret, binding, route. Có TIN_TOKEN thì đặt luôn secret TIN_TOKEN.
import fs from 'node:fs';
import { execFileSync } from 'node:child_process';

const TOKEN = process.env.CLOUDFLARE_API_TOKEN;
const SCRIPT = process.env.SCRIPT || 'nsi-quantri';
const DEPLOY = process.env.DEPLOY === '1';
const DIR = new URL('.', import.meta.url).pathname;
const OUT = DIR + 'out';
if (!TOKEN) { console.error('Thiếu secret CLOUDFLARE_API_TOKEN trong repo nsi-tin (Settings → Secrets and variables → Actions).'); process.exit(1); }
fs.mkdirSync(OUT, { recursive: true });

const API = 'https://api.cloudflare.com/client/v4';
async function cf(path, init = {}) {
  const r = await fetch(API + path, { ...init, headers: { Authorization: `Bearer ${TOKEN}`, ...(init.headers || {}) } });
  if (!r.ok) throw new Error(`${init.method || 'GET'} ${path} → ${r.status}: ${(await r.text()).slice(0, 500)}`);
  return r;
}

const { result: accs } = await (await cf('/accounts')).json();
if (!accs?.length) throw new Error('Token không thấy tài khoản Cloudflare nào');
const account = process.env.CLOUDFLARE_ACCOUNT_ID || accs[0].id;
const base = `/accounts/${account}/workers/scripts/${SCRIPT}`;

// 1) Tải code đang chạy
const res = await cf(`${base}/content/v2`);
const entry = res.headers.get('cf-entrypoint') || 'worker.js';
const ctype = res.headers.get('content-type') || '';
let code;
if (ctype.startsWith('multipart/')) {
  const form = await new Response(await res.arrayBuffer(), { headers: { 'content-type': ctype } }).formData();
  const names = [...form.keys()];
  if (names.length !== 1) throw new Error(`Worker có ${names.length} module (${names.join(', ')}) — script này chỉ xử lý 1 file`);
  code = await form.get(names[0]).text();
} else {
  code = await res.text();
}
const isModule = /^\s*export\s+default\b/m.test(code);
console.log(`Đã tải ${entry}: ${code.length} ký tự, dạng ${isModule ? 'module' : 'service-worker'}`);
fs.writeFileSync(`${OUT}/goc-${entry}`, code); // bản gốc để lùi lại nếu cần

// 2) Áp 5 chỗ sửa + dán cuối file
const sua = `${OUT}/${entry}`;
fs.writeFileSync(sua, code);
execFileSync('node', [process.env.PATCH || DIR + 'ap-dung.mjs', sua], { stdio: 'inherit' });

// 3) Kiểm cú pháp + trùng tên với code cũ
const chk = `${OUT}/kiem.${isModule ? 'mjs' : 'cjs'}`;
fs.copyFileSync(sua, chk);
execFileSync('node', ['--check', chk], { stdio: 'inherit' });
fs.rmSync(chk);
const fixed = fs.readFileSync(sua, 'utf8');
if (SCRIPT === 'nsi-quantri') for (const k of ['RAW_GOC', 'LOAI_RAW', 'duongRaw', 'suaRaw', 'TIN_MOD']) {
  const n = (fixed.match(new RegExp(`(?:const|let|var|function)\\s+${k}\\b`, 'g')) || []).length;
  if (n !== 1) throw new Error(`"${k}" được khai báo ${n} lần — trùng tên với code cũ`);
}
if (SCRIPT === 'nsi-quantri' && !/\bADMIN\b/.test(code)) throw new Error('Code cũ không có biến ADMIN — khác với hướng dẫn, dừng');
try { execFileSync('diff', ['-U2', `${OUT}/goc-${entry}`, sua], { encoding: 'utf8' }); }
catch (e) { console.log('--- Phần thay đổi (không gồm đoạn dán cuối file) ---\n' + e.stdout.split('// ===== THEM 02/10')[0]); }
if (SCRIPT === 'nsi-quantri') console.log('Khai báo ADMIN trong code cũ:', (code.match(/^.*\bADMIN\s*=.*$/m) || ['(không thấy dòng gán)'])[0].trim());
console.log('Kiểm tra: OK. Bản gốc và bản đã sửa nằm trong mục Artifacts của lần chạy này.');

if (!DEPLOY) { console.log('CHẠY THỬ → không deploy. Muốn deploy: Actions → sua-quantri → Run workflow → chọn deploy.'); process.exit(0); }

// 4) Deploy: chỉ thay nội dung code
const fd = new FormData();
fd.append('metadata', new Blob([JSON.stringify(isModule ? { main_module: entry } : { body_part: entry })], { type: 'application/json' }));
fd.append(entry, new Blob([fixed], { type: isModule ? 'application/javascript+module' : 'application/javascript' }), entry);
await cf(`${base}/content`, { method: 'PUT', body: fd });
console.log(`Đã deploy ${SCRIPT}`);

// 5) Secret TIN_TOKEN (nếu có)
if (SCRIPT !== 'nsi-quantri') {
  // TIN_TOKEN chỉ dành cho trang quản trị
} else if (process.env.TIN_TOKEN) {
  await cf(`${base}/secrets`, { method: 'PUT', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ name: 'TIN_TOKEN', text: process.env.TIN_TOKEN, type: 'secret_text' }) });
  console.log('Đã đặt secret TIN_TOKEN');
} else {
  console.log('Chưa có secret TIN_TOKEN trong repo → trang /tin sẽ báo lỗi token cho tới khi đặt');
}
