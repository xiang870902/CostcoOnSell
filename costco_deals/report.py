"""產生可搜尋、篩選、排序的單檔 HTML 彙整報表。"""
from __future__ import annotations

import json
from datetime import datetime

from .common import SITE, short_url


def _row(deal: dict) -> dict:
    return {
        "c": deal["code"],
        "n": deal["name"],
        "u": SITE + deal["path"] if deal["path"] else short_url(deal["code"]),
        "ch": deal["channel"],
        "cat": deal["category"],
        "p": deal["price"],
        "o": deal["original"],
        "d": deal["discount"],
        "pct": deal["pct"],
        "s": deal["start"],
        "e": deal["end"],
        "img": deal["image"],
        "st": 1 if deal["in_stock"] else 0,
        "nw": 1 if deal["is_new"] else 0,
        "f": deal["flag"],
        "lp": deal["low_price"],
        "ld": deal["low_date"],
        "mq": deal["min_qty"],
        "lw": 1 if deal["lower_price"] else 0,
        "r": deal["rating"],
        "rv": deal["reviews"],
        "w": deal.get("watch") or "",
    }


def build_report(deals: list[dict], generated: datetime) -> str:
    data = json.dumps([_row(d) for d in deals], ensure_ascii=False, separators=(",", ":"))
    return (
        _TEMPLATE
        .replace("__GENERATED__", generated.strftime("%Y-%m-%d %H:%M"))
        .replace("__DATA__", data.replace("</", "<\\/"))
    )


_TEMPLATE = r"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>好市多特價彙整</title>
<style>
:root {
  --bg: #f4f5f7; --card: #ffffff; --text: #1a1d21; --muted: #68707c; --line: #e3e6ea;
  --red: #d91731; --blue: #005daa; --green: #15803d; --amber: #b45309;
  --chip: #eef1f4; --shadow: 0 1px 2px rgba(16,24,40,.06), 0 1px 3px rgba(16,24,40,.08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #101316; --card: #1a1e23; --text: #e7e9ec; --muted: #98a1ac; --line: #2a3037;
    --red: #ff5a6e; --blue: #6cb4ff; --green: #4ade80; --amber: #fbbf24;
    --chip: #262b32; --shadow: none;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--text);
  font: 15px/1.5 "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", system-ui, sans-serif;
}
header { padding: 24px 16px 8px; max-width: 1280px; margin: 0 auto; }
h1 { margin: 0; font-size: 24px; letter-spacing: .02em; }
h1 span { color: var(--red); }
.sub { color: var(--muted); font-size: 13px; margin-top: 4px; }
.tabs { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 16px; }
.tab {
  border: 1px solid var(--line); background: var(--card); color: var(--text);
  border-radius: 999px; padding: 6px 14px; font: inherit; font-size: 14px; cursor: pointer;
}
.tab b { color: var(--muted); font-weight: 600; margin-left: 4px; font-variant-numeric: tabular-nums; }
.tab[aria-pressed="true"] { background: var(--text); color: var(--bg); border-color: var(--text); }
.tab[aria-pressed="true"] b { color: inherit; opacity: .7; }
.bar {
  position: sticky; top: 0; z-index: 5; background: var(--bg);
  border-bottom: 1px solid var(--line);
}
.bar-in {
  max-width: 1280px; margin: 0 auto; padding: 10px 16px;
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
}
input[type=search], select {
  font: inherit; color: var(--text); background: var(--card);
  border: 1px solid var(--line); border-radius: 8px; padding: 8px 10px; min-width: 0;
}
input[type=search] { flex: 1 1 220px; }
select { flex: 0 1 auto; max-width: 100%; }
label.tog {
  display: inline-flex; align-items: center; gap: 6px; font-size: 14px;
  padding: 6px 10px; border: 1px solid var(--line); border-radius: 8px;
  background: var(--card); cursor: pointer; user-select: none;
}
.count { color: var(--muted); font-size: 13px; margin-left: auto; font-variant-numeric: tabular-nums; }
main { max-width: 1280px; margin: 0 auto; padding: 16px; }
.grid { display: grid; gap: 12px; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); }
@media (max-width: 520px) { .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; } }
.card {
  display: flex; flex-direction: column; background: var(--card); color: inherit;
  text-decoration: none; border-radius: 12px; overflow: hidden; box-shadow: var(--shadow);
  border: 1px solid var(--line);
}
.card:hover { border-color: var(--blue); }
.card.oos { opacity: .55; }
.thumb { position: relative; aspect-ratio: 1; background: #fff; }
.thumb img { width: 100%; height: 100%; object-fit: contain; display: block; }
.pct {
  position: absolute; left: 8px; top: 8px; background: var(--red); color: #fff;
  font-weight: 700; font-size: 14px; padding: 2px 8px; border-radius: 6px;
}
@media (prefers-color-scheme: dark) { .pct { background: #d91731; } }
.new {
  position: absolute; right: 8px; top: 8px; background: #005daa; color: #fff;
  font-size: 11px; font-weight: 700; padding: 2px 6px; border-radius: 6px; letter-spacing: .05em;
}
.body { padding: 10px 12px 12px; display: flex; flex-direction: column; gap: 6px; flex: 1; }
.chips { display: flex; flex-wrap: wrap; gap: 4px; }
.chip { font-size: 11px; padding: 1px 7px; border-radius: 999px; background: var(--chip); color: var(--muted); white-space: nowrap; }
.chip.wh { color: var(--blue); }
.chip.low { color: var(--green); font-weight: 600; }
.chip.watch { color: var(--amber); font-weight: 600; }
.name { font-size: 14px; line-height: 1.4; overflow-wrap: anywhere; }
.price { margin-top: auto; display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px; }
.price b { font-size: 19px; color: var(--red); font-variant-numeric: tabular-nums; }
.price s { color: var(--muted); font-size: 13px; }
.price .off { font-size: 12px; color: var(--red); }
.price .ask { font-size: 13px; color: var(--muted); }
.meta { font-size: 12px; color: var(--muted); }
.meta .soon { color: var(--amber); font-weight: 600; }
.empty { text-align: center; color: var(--muted); padding: 60px 0; }
.more { display: block; margin: 20px auto; padding: 10px 28px; font: inherit; cursor: pointer;
  border-radius: 8px; border: 1px solid var(--line); background: var(--card); color: var(--text); }
footer { max-width: 1280px; margin: 0 auto; padding: 8px 16px 40px; color: var(--muted); font-size: 12px; }
</style>
</head>
<body>
<header>
  <h1><span>Costco</span> 好市多特價彙整</h1>
  <div class="sub">更新時間 __GENERATED__（台灣時間）・資料來源：好市多線上購物官網</div>
  <div class="tabs" id="tabs"></div>
</header>
<div class="bar"><div class="bar-in">
  <input type="search" id="q" placeholder="搜尋商品名稱…" autocomplete="off">
  <select id="cat" aria-label="分類"></select>
  <select id="sort" aria-label="排序">
    <option value="pct">折扣幅度高→低</option>
    <option value="off">折扣金額高→低</option>
    <option value="asc">價格低→高</option>
    <option value="desc">價格高→低</option>
    <option value="end">即將截止</option>
    <option value="start">最新開始</option>
    <option value="rate">評價高→低</option>
  </select>
  <label class="tog"><input type="checkbox" id="onlyNew">新上架</label>
  <label class="tog"><input type="checkbox" id="onlyLow">歷史低價</label>
  <label class="tog"><input type="checkbox" id="onlyStock">有庫存</label>
  <span class="count" id="count"></span>
</div></div>
<main>
  <div class="grid" id="grid"></div>
  <div class="empty" id="empty" hidden>沒有符合條件的特價商品</div>
  <button class="more" id="more" hidden>顯示更多</button>
</main>
<footer>
  「賣場特價」為賣場獨家商品，官網未公開售價與折扣金額，實際優惠以賣場標示為準。
  「歷史低價」依本系統開始記錄後的特價價格判斷。價格與庫存以好市多官網及賣場為準。
</footer>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById('data').textContent);
const CH = { online: '線上特價', online_only: '網路獨家', same_price: '線上賣場同價', warehouse: '賣場特價' };
const TABS = [
  ['all', '全部', d => true],
  ['web', '線上特價', d => d.ch !== 'warehouse'],
  ['online_only', '網路獨家', d => d.ch === 'online_only'],
  ['same_price', '線上賣場同價', d => d.ch === 'same_price'],
  ['warehouse', '賣場特價', d => d.ch === 'warehouse'],
];
const PAGE = 240;
const state = { tab: 'all', q: '', cat: '', sort: 'pct', onlyNew: false, onlyLow: false, onlyStock: false, limit: PAGE };
const $ = id => document.getElementById(id);
const esc = s => String(s).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const money = v => '$' + Math.round(v).toLocaleString('en-US');
const dayFmt = new Intl.DateTimeFormat('zh-TW', { timeZone: 'Asia/Taipei', month: 'numeric', day: 'numeric' });
const day = iso => dayFmt.format(new Date(iso));
const num = (v, fallback) => (v === null || v === undefined ? fallback : v);

function period(d) {
  let text = d.s && d.e ? day(d.s) + '–' + day(d.e) : d.e ? '至 ' + day(d.e) : d.s ? day(d.s) + ' 起' : '';
  if (d.e) {
    const left = Math.ceil((new Date(d.e) - Date.now()) / 864e5);
    if (left < 0) text += '・<span class="soon">已結束</span>';
    else if (left <= 1) text += '・<span class="soon">今天截止</span>';
    else if (left <= 3) text += '・<span class="soon">剩 ' + left + ' 天</span>';
    else text += '・剩 ' + left + ' 天';
  }
  return text;
}

function card(d) {
  const chips = ['<span class="chip' + (d.ch === 'warehouse' ? ' wh' : '') + '">' + CH[d.ch] + '</span>'];
  if (d.f === 'new_low') chips.push('<span class="chip low">🔥 歷史新低</span>');
  else if (d.f === 'tie_low') chips.push('<span class="chip low">平歷史低價</span>');
  if (d.w) chips.push('<span class="chip watch">⭐ 關注</span>');
  if (d.lw) chips.push('<span class="chip">最新降價</span>');
  if (d.mq > 1) chips.push('<span class="chip">買 ' + d.mq + ' 件</span>');
  if (!d.st) chips.push('<span class="chip">缺貨</span>');

  let price;
  if (d.ch === 'warehouse') price = '<span class="ask">價格請至賣場確認</span>';
  else if (d.p !== null) price = '<b>' + money(d.p) + '</b>' + (d.o ? '<s>' + money(d.o) + '</s>' : '') + (d.d ? '<span class="off">省 ' + money(d.d) + '</span>' : '');
  else price = '<b>折 ' + money(d.d) + '</b><span class="ask">多規格</span>';

  const meta = [period(d)];
  if (d.rv) meta.push('★ ' + d.r.toFixed(1) + '（' + d.rv + '）');
  let low = '';
  if (d.lp !== null && d.p !== null && !d.f) low = '<div class="meta">歷史低價 ' + money(d.lp) + '（' + esc(d.ld) + '）</div>';

  return '<a class="card' + (d.st ? '' : ' oos') + '" href="' + esc(d.u) + '" target="_blank" rel="noopener">' +
    '<div class="thumb">' + (d.img ? '<img loading="lazy" referrerpolicy="no-referrer" alt="" src="' + esc(d.img) + '">' : '') +
    (d.pct ? '<span class="pct">-' + Math.round(d.pct) + '%</span>' : '') +
    (d.nw ? '<span class="new">NEW</span>' : '') + '</div>' +
    '<div class="body"><div class="chips">' + chips.join('') + '</div>' +
    '<div class="name">' + esc(d.n) + '</div>' +
    '<div class="price">' + price + '</div>' +
    '<div class="meta">' + meta.filter(Boolean).join('・') + '</div>' + low + '</div></a>';
}

const SORTS = {
  pct: (a, b) => num(b.pct, -1) - num(a.pct, -1),
  off: (a, b) => num(b.d, -1) - num(a.d, -1),
  asc: (a, b) => num(a.p, Infinity) - num(b.p, Infinity),
  desc: (a, b) => num(b.p, -1) - num(a.p, -1),
  end: (a, b) => (a.e || '9999').localeCompare(b.e || '9999'),
  start: (a, b) => (b.s || '').localeCompare(a.s || ''),
  rate: (a, b) => (b.rv ? b.r : 0) - (a.rv ? a.r : 0) || b.rv - a.rv,
};

function filtered() {
  const tab = TABS.find(t => t[0] === state.tab)[2];
  const words = state.q.toLowerCase().split(/\s+/).filter(Boolean);
  return DATA.filter(d =>
    tab(d) &&
    (!state.cat || d.cat === state.cat) &&
    (!state.onlyNew || d.nw) &&
    (!state.onlyLow || d.f) &&
    (!state.onlyStock || d.st) &&
    words.every(w => d.n.toLowerCase().includes(w))
  ).sort(SORTS[state.sort]);
}

function render() {
  const rows = filtered();
  $('grid').innerHTML = rows.slice(0, state.limit).map(card).join('');
  $('count').textContent = rows.length + ' 項';
  $('empty').hidden = rows.length > 0;
  $('more').hidden = rows.length <= state.limit;
  $('more').textContent = '顯示更多（還有 ' + (rows.length - state.limit) + ' 項）';
}

function update(patch) { Object.assign(state, { limit: PAGE }, patch); render(); }

$('tabs').innerHTML = TABS.map(t =>
  '<button class="tab" data-tab="' + t[0] + '" aria-pressed="' + (t[0] === state.tab) + '">' + t[1] + '<b>' + DATA.filter(t[2]).length + '</b></button>'
).join('');
$('tabs').addEventListener('click', e => {
  const button = e.target.closest('.tab');
  if (!button) return;
  document.querySelectorAll('.tab').forEach(b => b.setAttribute('aria-pressed', b === button));
  update({ tab: button.dataset.tab });
});

const cats = {};
DATA.forEach(d => { cats[d.cat] = (cats[d.cat] || 0) + 1; });
$('cat').innerHTML = '<option value="">全部分類</option>' + Object.keys(cats).sort((a, b) => cats[b] - cats[a])
  .map(c => '<option value="' + esc(c) + '">' + esc(c) + '（' + cats[c] + '）</option>').join('');

$('q').addEventListener('input', e => update({ q: e.target.value }));
$('cat').addEventListener('change', e => update({ cat: e.target.value }));
$('sort').addEventListener('change', e => update({ sort: e.target.value }));
$('onlyNew').addEventListener('change', e => update({ onlyNew: e.target.checked }));
$('onlyLow').addEventListener('change', e => update({ onlyLow: e.target.checked }));
$('onlyStock').addEventListener('change', e => update({ onlyStock: e.target.checked }));
$('more').addEventListener('click', () => { state.limit += PAGE; render(); });
render();
</script>
</body>
</html>
"""
