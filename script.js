const symbolSelect = document.getElementById('symbolSelect');
const statusEl = document.getElementById('status');
const metaEl = document.getElementById('meta');
const tableBody = document.querySelector('#resultTable tbody');
const tableHeaders = document.querySelectorAll('#resultTable thead th');
const toggleCointegratedBtn = document.getElementById('toggleCointegrated');
const spreadPanel = document.getElementById('spreadPanel');
const spreadTitle = document.getElementById('spreadTitle');
const spreadSvg = document.getElementById('spreadSvg');
const spreadTooltip = document.getElementById('spreadTooltip');
const SVG_NS = spreadSvg.namespaceURI;

const CORR_CSV = 'output/correlation_matrix.csv';
const CINT_CSV = 'output/cointegrated_pairs.csv';

let symbols = [];
let matrixRows = new Map();
let cointegrationMap = new Map();
let symbolToRaw = new Map();
let priceSeriesCache = new Map();
let currentRows = [];
let showCointegratedOnly = false;
let sortState = { key: 'asset2', asc: true };
let activeSpreadAsset2 = '';

function parseCsvLine(line) {
  const values = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const c = line[i];
    if (c === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (c === ',' && !inQuotes) {
      values.push(current);
      current = '';
    } else {
      current += c;
    }
  }
  values.push(current);
  return values;
}

function normalizeSymbol(raw) {
  return raw.replace(/_D1_\d{8}_\d{8}$/, '');
}

function pairKey(a, b) {
  return `${a}||${b}`;
}

function toNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

function formatNumber(v, digits = 6) {
  if (v === null || v === undefined || Number.isNaN(v)) return '';
  return Number(v).toFixed(digits);
}

function setStatus(text) {
  statusEl.textContent = text;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function escapeLatex(text) {
  return String(text).replace(/[\\{}_$&#^%~]/g, c => `\\${c}`);
}

function renderSpreadTitleMath(asset1, asset2) {
  const a1 = escapeHtml(asset1);
  const a2 = escapeHtml(asset2);
  if (window.katex && typeof window.katex.renderToString === 'function') {
    const latex = `\\log\\left(\\mathrm{${escapeLatex(asset1)}}\\right)-\\left(\\alpha+\\beta\\cdot\\log\\left(\\mathrm{${escapeLatex(asset2)}}\\right)\\right)`;
    const formula = window.katex.renderToString(latex, { throwOnError: false, displayMode: false });
    return `${a1} vs ${a2} · <span class="math-inline">${formula}</span>`;
  }
  return `${a1} vs ${a2} · <span class="math-inline">spread: log(${a1}) − (α + β·log(${a2}))</span>`;
}

function renderTableHeaderMath() {
  if (!(window.katex && typeof window.katex.renderToString === 'function')) return;
  const map = {
    correlation: '\\rho\\,\\text{(Pearson)}',
    beta: '\\beta',
    alpha: '\\alpha',
    adf_p_spread: 'p_{\\mathrm{ADF}}',
    half_life: 't_{1/2}'
  };
  tableHeaders.forEach(th => {
    const key = th.dataset.key;
    if (!map[key]) return;
    th.innerHTML = window.katex.renderToString(map[key], { throwOnError: false, displayMode: false });
  });
}

function svgNode(name, attrs = {}, text = '') {
  const node = document.createElementNS(SVG_NS, name);
  Object.entries(attrs).forEach(([k, v]) => node.setAttribute(k, String(v)));
  if (text) node.textContent = text;
  return node;
}

function hideSpreadPanel() {
  spreadPanel.hidden = true;
  spreadSvg.innerHTML = '';
  spreadTooltip.style.opacity = '0';
  activeSpreadAsset2 = '';
}

function parsePriceCsv(text) {
  const lines = text.split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return new Map();
  const header = parseCsvLine(lines[0]);
  const timeIdx = header.indexOf('time');
  const closeIdx = header.indexOf('close');
  if (timeIdx < 0 || closeIdx < 0) return new Map();
  const out = new Map();
  for (let i = 1; i < lines.length; i++) {
    const row = parseCsvLine(lines[i]);
    if (row.length <= Math.max(timeIdx, closeIdx)) continue;
    const t = row[timeIdx];
    const c = Number(row[closeIdx]);
    if (!t || !Number.isFinite(c) || c <= 0) continue;
    out.set(t, Math.log(c));
  }
  return out;
}

async function getPriceSeries(symbol) {
  if (priceSeriesCache.has(symbol)) return priceSeriesCache.get(symbol);
  const raw = symbolToRaw.get(symbol);
  if (!raw) throw new Error(`No data mapping for ${symbol}`);
  const text = await fetch(`data/${raw}.csv`).then(r => {
    if (!r.ok) throw new Error(`Cannot load data/${raw}.csv`);
    return r.text();
  });
  const series = parsePriceCsv(text);
  priceSeriesCache.set(symbol, series);
  return series;
}

function drawSpreadChart(points) {
  const w = 1100;
  const h = 420;
  const padLeft = 64;
  const padRight = 24;
  const padTop = 26;
  const padBottom = 46;
  const innerW = w - padLeft - padRight;
  const innerH = h - padTop - padBottom;
  spreadSvg.innerHTML = '';

  const ys = points.map(p => p.spread);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const absMax = Math.max(Math.abs(minY), Math.abs(maxY), 1e-9);
  const yBound = absMax * 1.08;
  const y0 = -yBound;
  const y1 = yBound;
  const xScale = i => padLeft + (i / (points.length - 1)) * innerW;
  const yScale = v => padTop + ((y1 - v) / (y1 - y0)) * innerH;

  spreadSvg.appendChild(svgNode('rect', { x: 0, y: 0, width: w, height: h, fill: '#ffffff' }));

  for (let i = 0; i <= 4; i++) {
    const t = i / 4;
    const yv = y0 + (1 - t) * (y1 - y0);
    const yy = yScale(yv);
    spreadSvg.appendChild(svgNode('line', {
      x1: padLeft, y1: yy, x2: w - padRight, y2: yy, stroke: '#eef2f7', 'stroke-width': 1
    }));
    spreadSvg.appendChild(svgNode('text', {
      x: padLeft - 8, y: yy + 4, 'text-anchor': 'end', fill: '#64748b', 'font-size': 14
    }, yv.toFixed(3)));
  }

  const yZero = yScale(0);
  spreadSvg.appendChild(svgNode('line', {
    x1: padLeft, y1: yZero, x2: w - padRight, y2: yZero, stroke: '#94a3b8', 'stroke-width': 1.4
  }));

  spreadSvg.appendChild(svgNode('line', {
    x1: padLeft, y1: h - padBottom, x2: w - padRight, y2: h - padBottom, stroke: '#334155', 'stroke-width': 1.2
  }));
  spreadSvg.appendChild(svgNode('line', {
    x1: padLeft, y1: padTop, x2: padLeft, y2: h - padBottom, stroke: '#334155', 'stroke-width': 1.2
  }));

  const formatTickDate = t => (t && t.length >= 7 ? t.slice(0, 7) : t);
  const tickCount = Math.max(4, Math.min(10, Math.floor(innerW / 120)));
  const tickSet = new Set();
  for (let i = 0; i < tickCount; i++) {
    const idx = Math.round((i * (points.length - 1)) / Math.max(1, tickCount - 1));
    tickSet.add(idx);
  }
  const tickIndices = Array.from(tickSet).sort((a, b) => a - b);
  let lastDrawnX = -1e9;
  for (const i of tickIndices) {
    const xx = xScale(i);
    if (xx - lastDrawnX < 72) continue;
    spreadSvg.appendChild(svgNode('line', { x1: xx, y1: h - padBottom, x2: xx, y2: h - padBottom + 4, stroke: '#334155' }));
    spreadSvg.appendChild(svgNode('text', {
      x: xx, y: h - padBottom + 18, 'text-anchor': 'middle', fill: '#64748b', 'font-size': 14
    }, formatTickDate(points[i].time)));
    lastDrawnX = xx;
  }

  let d = '';
  points.forEach((p, i) => {
    const xx = xScale(i);
    const yy = yScale(p.spread);
    d += `${i === 0 ? 'M' : 'L'}${xx},${yy}`;
  });
  spreadSvg.appendChild(svgNode('path', {
    d, fill: 'none', stroke: '#2563eb', 'stroke-width': 2
  }));

  const guide = svgNode('line', {
    x1: padLeft, y1: padTop, x2: padLeft, y2: h - padBottom, stroke: '#94a3b8', 'stroke-width': 1, visibility: 'hidden'
  });
  const dot = svgNode('circle', { cx: padLeft, cy: padTop, r: 4, fill: '#1d4ed8', visibility: 'hidden' });
  spreadSvg.appendChild(guide);
  spreadSvg.appendChild(dot);

  const overlay = svgNode('rect', {
    x: padLeft, y: padTop, width: innerW, height: innerH, fill: 'transparent', cursor: 'crosshair'
  });
  overlay.addEventListener('mousemove', ev => {
    const rect = spreadSvg.getBoundingClientRect();
    const localX = ev.clientX - rect.left;
    const ratio = Math.min(1, Math.max(0, (localX - padLeft) / innerW));
    const idx = Math.round(ratio * (points.length - 1));
    const p = points[idx];
    const xx = xScale(idx);
    const yy = yScale(p.spread);
    guide.setAttribute('x1', String(xx));
    guide.setAttribute('x2', String(xx));
    dot.setAttribute('cx', String(xx));
    dot.setAttribute('cy', String(yy));
    guide.setAttribute('visibility', 'visible');
    dot.setAttribute('visibility', 'visible');
    spreadTooltip.textContent = `${p.time} · spread=${p.spread.toFixed(6)}`;
    spreadTooltip.style.left = `${ev.clientX - rect.left}px`;
    spreadTooltip.style.top = `${ev.clientY - rect.top}px`;
    spreadTooltip.style.opacity = '1';
  });
  overlay.addEventListener('mouseleave', () => {
    guide.setAttribute('visibility', 'hidden');
    dot.setAttribute('visibility', 'hidden');
    spreadTooltip.style.opacity = '0';
  });
  spreadSvg.appendChild(overlay);
}

async function showSpreadForRow(asset1, rowData) {
  if (rowData.beta === null || rowData.alpha === null) {
    spreadTitle.textContent = `${asset1} vs ${rowData.asset2} · spread unavailable (not cointegrated)`;
    spreadSvg.innerHTML = '';
    spreadPanel.hidden = false;
    activeSpreadAsset2 = rowData.asset2;
    return;
  }
  setStatus('Loading spread chart...');
  try {
    const [s1, s2] = await Promise.all([getPriceSeries(asset1), getPriceSeries(rowData.asset2)]);
    const points = [];
    const keys = Array.from(s1.keys()).filter(k => s2.has(k)).sort();
    for (const k of keys) {
      const y = s1.get(k);
      const x = s2.get(k);
      const spread = y - (rowData.alpha + rowData.beta * x);
      if (Number.isFinite(spread)) points.push({ time: k, spread });
    }
    if (points.length < 5) throw new Error('Not enough overlapping observations');
    spreadTitle.innerHTML = renderSpreadTitleMath(asset1, rowData.asset2);
    drawSpreadChart(points);
    spreadPanel.hidden = false;
    activeSpreadAsset2 = rowData.asset2;
    setStatus('Ready');
  } catch (err) {
    spreadTitle.textContent = `${asset1} vs ${rowData.asset2} · ${err.message}`;
    spreadSvg.innerHTML = '';
    spreadPanel.hidden = false;
    activeSpreadAsset2 = rowData.asset2;
    setStatus('Ready');
  }
}

function renderTable(rows) {
  const html = rows.map(r => {
    const notC = r.beta === null;
    return `<tr data-asset2="${r.asset2}">
      <td>${r.asset2}</td>
      <td>${formatNumber(r.correlation, 6)}</td>
      <td>${notC ? '<span class="label-not">Not cointegrated</span>' : formatNumber(r.beta, 6)}</td>
      <td>${notC ? '' : formatNumber(r.alpha, 6)}</td>
      <td>${notC ? '' : formatNumber(r.adf_p_spread, 6)}</td>
      <td>${notC ? '' : r.n_obs}</td>
      <td>${notC ? '' : formatNumber(r.half_life, 6)}</td>
    </tr>`;
  }).join('');
  tableBody.innerHTML = html;
  if (activeSpreadAsset2) {
    const selectedRow = tableBody.querySelector(`tr[data-asset2="${activeSpreadAsset2}"]`);
    if (selectedRow) selectedRow.classList.add('row-selected');
  }
}

function getVisibleRows() {
  if (!showCointegratedOnly) return currentRows;
  return currentRows.filter(r => r.beta !== null);
}

function updateToggleButton() {
  toggleCointegratedBtn.classList.toggle('active', showCointegratedOnly);
  toggleCointegratedBtn.textContent = showCointegratedOnly ? 'Show all pairs' : 'Hide non-cointegrated';
}

function refreshView() {
  const visibleRows = getVisibleRows();
  renderTable(visibleRows);
  const cointegratedCount = currentRows.filter(r => r.beta !== null).length;
  metaEl.textContent = `${visibleRows.length} shown · ${currentRows.length} total · ${cointegratedCount} cointegrated`;
  hideSpreadPanel();
}

function sortRows() {
  const key = sortState.key;
  const asc = sortState.asc ? 1 : -1;
  currentRows.sort((a, b) => {
    const av = a[key];
    const bv = b[key];
    const aNull = av === null || av === '';
    const bNull = bv === null || bv === '';
    if (aNull && bNull) return 0;
    if (aNull) return 1;
    if (bNull) return -1;
    if (typeof av === 'number' && typeof bv === 'number') return (av - bv) * asc;
    return String(av).localeCompare(String(bv)) * asc;
  });
  refreshView();
}

function setHeaderLabels() {
  tableHeaders.forEach(th => {
    const key = th.dataset.key;
    if (key === sortState.key) {
      th.dataset.sort = sortState.asc ? '↑' : '↓';
    } else {
      th.dataset.sort = '';
    }
  });
}

function buildRowsForSymbol(selected) {
  const rawRow = matrixRows.get(selected);
  if (!rawRow) return [];
  return symbols.map((asset2, idx) => {
    const corr = toNumber(rawRow[idx]);
    const direct = cointegrationMap.get(pairKey(selected, asset2));
    const reverse = cointegrationMap.get(pairKey(asset2, selected));
    if (!direct && !reverse) {
      return {
        asset2,
        correlation: corr,
        beta: null,
        alpha: null,
        adf_p_spread: null,
        n_obs: null,
        half_life: null
      };
    }
    let beta = null;
    let alpha = null;
    let adf_p_spread = null;
    let n_obs = null;
    let half_life = null;
    if (direct) {
      beta = direct.beta;
      alpha = direct.alpha;
      adf_p_spread = direct.adf_p_spread;
      n_obs = direct.n_obs;
      half_life = direct.half_life;
    } else if (reverse) {
      if (reverse.beta !== null && Math.abs(reverse.beta) > 1e-12) {
        beta = 1 / reverse.beta;
        alpha = -reverse.alpha / reverse.beta;
        adf_p_spread = reverse.adf_p_spread;
        n_obs = reverse.n_obs;
        half_life = reverse.half_life;
      }
    }
    return {
      asset2,
      correlation: corr,
      beta,
      alpha,
      adf_p_spread,
      n_obs,
      half_life
    };
  });
}

function onSelectSymbol() {
  const selected = symbolSelect.value;
  currentRows = buildRowsForSymbol(selected);
  sortRows();
  setHeaderLabels();
}

async function loadData() {
  try {
    setStatus('Loading correlation matrix...');
    const corrText = await fetch(CORR_CSV).then(r => {
      if (!r.ok) throw new Error(`Cannot load ${CORR_CSV}`);
      return r.text();
    });

    const corrLines = corrText.split(/\r?\n/).filter(Boolean);
    if (corrLines.length < 2) throw new Error('Correlation matrix is empty');
    const rawHeader = parseCsvLine(corrLines[0]).slice(1);
    symbols = rawHeader.map(normalizeSymbol);
    rawHeader.forEach(raw => symbolToRaw.set(normalizeSymbol(raw), raw));

    for (let i = 1; i < corrLines.length; i++) {
      const row = parseCsvLine(corrLines[i]);
      if (!row.length) continue;
      const asset1 = normalizeSymbol(row[0]);
      matrixRows.set(asset1, row.slice(1));
    }

    setStatus('Loading cointegrated pairs...');
    const cintText = await fetch(CINT_CSV).then(r => {
      if (!r.ok) throw new Error(`Cannot load ${CINT_CSV}`);
      return r.text();
    });

    const cintLines = cintText.split(/\r?\n/).filter(Boolean);
    for (let i = 1; i < cintLines.length; i++) {
      const row = parseCsvLine(cintLines[i]);
      if (row.length < 7) continue;
      const asset1 = row[0];
      const asset2 = row[1];
      cointegrationMap.set(pairKey(asset1, asset2), {
        beta: toNumber(row[2]),
        alpha: toNumber(row[3]),
        adf_p_spread: toNumber(row[4]),
        n_obs: toNumber(row[5]),
        half_life: toNumber(row[6])
      });
    }

    symbolSelect.innerHTML = symbols.map(s => `<option value="${s}">${s}</option>`).join('');
    symbolSelect.value = symbols[0];
    onSelectSymbol();
    setStatus('Ready');
  } catch (err) {
    setStatus(`Error: ${err.message}`);
  }
}

tableHeaders.forEach(th => {
  th.addEventListener('click', () => {
    const key = th.dataset.key;
    if (!key) return;
    if (sortState.key === key) {
      sortState.asc = !sortState.asc;
    } else {
      sortState.key = key;
      sortState.asc = true;
    }
    sortRows();
    setHeaderLabels();
  });
});

tableBody.addEventListener('click', async event => {
  const tr = event.target.closest('tr[data-asset2]');
  if (!tr) return;
  const asset2 = tr.dataset.asset2;
  const rowData = currentRows.find(r => r.asset2 === asset2);
  if (!rowData) return;
  tableBody.querySelectorAll('tr.row-selected').forEach(el => el.classList.remove('row-selected'));
  tr.classList.add('row-selected');
  await showSpreadForRow(symbolSelect.value, rowData);
});

toggleCointegratedBtn.addEventListener('click', () => {
  showCointegratedOnly = !showCointegratedOnly;
  updateToggleButton();
  refreshView();
});

symbolSelect.addEventListener('change', onSelectSymbol);
renderTableHeaderMath();
window.addEventListener('load', renderTableHeaderMath);
updateToggleButton();
loadData();
