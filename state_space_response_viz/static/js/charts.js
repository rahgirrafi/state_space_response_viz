/* Minimal dependency-free SVG line charts for the live monitor.
   Adapted from state_space_setup_assistant/static/js/plots.js: same clean
   polyline approach, redrawn each animation frame from the browser's history. */

const NS = 'http://www.w3.org/2000/svg';
export const COLORS = ['#4c9aff', '#ff6b6b', '#3fb950', '#e3b341', '#bc8cff',
                       '#f778ba', '#39c5cf', '#ff9e64'];

function el(tag, attrs) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) e.setAttribute(k, v);
  return e;
}

/** Draw series [{name, values}] over shared x array t into container. */
export function renderLines(container, t, series, opts = {}) {
  const W = opts.width || container.clientWidth || 460;
  const H = opts.height || 200;
  const padL = 52, padR = 12, padT = 10, padB = 24;
  const svg = el('svg', { viewBox: `0 0 ${W} ${H}`, class: 'svgplot',
    preserveAspectRatio: 'none', width: '100%', height: H });

  if (!t || t.length < 2 || !series.length) {
    const msg = el('text', { x: W / 2, y: H / 2, 'text-anchor': 'middle',
      class: 'plot-empty' });
    msg.textContent = opts.empty || 'waiting for data…';
    svg.appendChild(msg);
    container.replaceChildren(svg);
    return;
  }

  let ymin = Infinity, ymax = -Infinity;
  for (const s of series) {
    for (const v of s.values) {
      if (Number.isFinite(v)) { ymin = Math.min(ymin, v); ymax = Math.max(ymax, v); }
    }
  }
  if (!Number.isFinite(ymin)) { ymin = -1; ymax = 1; }
  if (Math.abs(ymax - ymin) < 1e-9) { ymin -= 1; ymax += 1; }
  const yr = ymax - ymin; ymin -= yr * 0.08; ymax += yr * 0.08;

  const t0 = t[0], t1 = t[t.length - 1];
  const sx = v => padL + (v - t0) / (t1 - t0 || 1) * (W - padL - padR);
  const sy = v => H - padB - (v - ymin) / (ymax - ymin) * (H - padT - padB);

  svg.appendChild(el('line', { x1: padL, y1: H - padB, x2: W - padR, y2: H - padB,
    class: 'axis' }));
  svg.appendChild(el('line', { x1: padL, y1: padT, x2: padL, y2: H - padB,
    class: 'axis' }));
  if (ymin < 0 && ymax > 0) {
    svg.appendChild(el('line', { x1: padL, y1: sy(0), x2: W - padR, y2: sy(0),
      class: 'zeroline' }));
  }

  const label = (x, y, txt, anchor = 'middle') => {
    const e2 = el('text', { x, y, class: 'tick', 'text-anchor': anchor });
    e2.textContent = txt;
    svg.appendChild(e2);
  };
  label(padL - 6, sy(ymin) - 1, fmt(ymin), 'end');
  label(padL - 6, sy(ymax) + 8, fmt(ymax), 'end');
  label(W - padR, H - 7, `${(t1 - t0).toFixed(1)}s`, 'end');

  series.forEach((s, i) => {
    const pts = [];
    for (let k = 0; k < t.length; k++) {
      const v = s.values[k];
      if (Number.isFinite(v)) pts.push(`${sx(t[k]).toFixed(1)},${sy(v).toFixed(1)}`);
    }
    svg.appendChild(el('polyline', { points: pts.join(' '), fill: 'none',
      stroke: s.color || COLORS[i % COLORS.length], 'stroke-width': 1.7,
      'stroke-linejoin': 'round' }));
  });

  container.replaceChildren(svg);
  if (opts.legend !== false) renderLegend(opts.legendEl, series);
}

function renderLegend(legendEl, series) {
  if (!legendEl) return;
  legendEl.replaceChildren(...series.map((s, i) => {
    const span = document.createElement('span');
    span.className = 'legend-item';
    const sw = document.createElement('i');
    sw.style.background = s.color || COLORS[i % COLORS.length];
    span.append(sw, document.createTextNode(s.name));
    return span;
  }));
}

function fmt(v) {
  const a = Math.abs(v);
  if (a !== 0 && (a < 1e-2 || a >= 1e4)) return v.toExponential(1);
  return v.toFixed(a < 10 ? 2 : 1);
}
