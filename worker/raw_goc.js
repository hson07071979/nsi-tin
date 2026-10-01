// ---- Trang quan tri doc web THANG tu GitHub (khong qua cong nsi-cong cua ten mien that) ----
// Ten mien that da chay qua Worker nsi-cong (bat dang nhap khach) nen nsi-quantri khong duoc lay trang tu do nua.
const RAW_GOC = 'https://raw.githubusercontent.com/hson07071979/nguyensoninvest/main';
const LOAI_RAW = { html: 'text/html; charset=utf-8', js: 'text/javascript; charset=utf-8', mjs: 'text/javascript; charset=utf-8',
  json: 'application/json; charset=utf-8', css: 'text/css; charset=utf-8', svg: 'image/svg+xml', png: 'image/png',
  jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', ico: 'image/x-icon',
  txt: 'text/plain; charset=utf-8', xml: 'application/xml', webmanifest: 'application/manifest+json',
  woff2: 'font/woff2', woff: 'font/woff', csv: 'text/csv; charset=utf-8' };
function duongRaw(p) { return (!p || p.endsWith('/')) ? (p || '/') + 'index.html' : p; }
function suaRaw(h, p) {
  for (const k of ['content-security-policy', 'x-frame-options', 'x-content-type-options', 'strict-transport-security',
    'access-control-allow-origin', 'cross-origin-resource-policy', 'source-age', 'x-github-request-id']) h.delete(k);
  const m = duongRaw(p).toLowerCase().match(/\.([a-z0-9]+)$/);
  h.set('content-type', (m && LOAI_RAW[m[1]]) || 'application/octet-stream');
}
