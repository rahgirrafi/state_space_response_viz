/* Live controller monitor: consume the SSE feed, keep per-channel history,
   and redraw the panels. No build step, no dependencies. */

import { renderLines, COLORS } from './charts.js';

const MAXPTS = 1500;
const hist = { t: [], x: [], ref: [], err: [], u: [], xhat: [] };
let meta = { has_diag: false, joint_names: [], sections: {}, controller: '' };
let metaRev = -1;
let lastFrame = null;
let lastMetrics = {};
let dirty = false;

const $ = sel => document.querySelector(sel);

function resetHistory() {
  hist.t = []; hist.x = []; hist.ref = []; hist.err = []; hist.u = []; hist.xhat = [];
}

function pushFrame(f) {
  hist.t.push(f.t);
  for (const key of ['x', 'ref', 'err', 'u', 'xhat']) {
    const vals = f[key] || [];
    const H = hist[key];
    for (let i = 0; i < vals.length; i++) {
      if (!H[i]) H[i] = [];
      H[i].push(vals[i]);
    }
  }
  if (hist.t.length > MAXPTS) {
    const drop = hist.t.length - MAXPTS;
    hist.t.splice(0, drop);
    for (const key of ['x', 'ref', 'err', 'u', 'xhat']) {
      for (const ch of hist[key]) ch.splice(0, drop);
    }
  }
  lastFrame = f;
}

/* ---- panels ---------------------------------------------------------- */

function jointName(i) {
  return meta.joint_names[i] || `q${i}`;
}
function errLabel(i) {
  return (meta.labels && meta.labels.error && meta.labels.error[i]) || `e${i}`;
}
function uLabel(i) {
  return (meta.labels && meta.labels.command && meta.labels.command[i]) || `u${i}`;
}
function nJoints() {
  return meta.joint_names.length || Math.floor((hist.x.length || 0) / 2) || 0;
}

function series(group, idxs, namer) {
  return idxs.filter(i => hist[group][i]).map((i, k) => ({
    name: namer(i, k), values: hist[group][i], color: COLORS[k % COLORS.length],
  }));
}

const PANELS = [
  {
    id: 'pos', title: 'Reference vs measured — position',
    need: () => hist.x.length > 0,
    draw(c, legend) {
      const n = nJoints();
      const meas = series('x', range(0, n), i => `${jointName(i)} meas`);
      // Overlay reference positions only when ref is a full-state setpoint.
      let refS = [];
      if (hist.ref.length >= 2 * n && n > 0) {
        refS = range(0, n).filter(i => hist.ref[i]).map((i, k) => ({
          name: `${jointName(i)} ref`, values: hist.ref[i],
          color: COLORS[k % COLORS.length], dash: true,
        }));
      }
      renderLines(c, hist.t, meas.concat(refS), { height: 200, legendEl: legend });
    },
  },
  {
    id: 'vel', title: 'Joint velocity',
    need: () => nJoints() > 0 && hist.x.length >= 2 * nJoints(),
    draw(c, legend) {
      const n = nJoints();
      renderLines(c, hist.t, series('x', range(n, 2 * n), i => `${jointName(i - n)} vel`),
        { height: 160, legendEl: legend });
    },
  },
  {
    id: 'err', title: 'Tracking error', diag: true,
    need: () => hist.err.length > 0,
    draw(c, legend) {
      renderLines(c, hist.t, series('err', range(0, hist.err.length), i => errLabel(i)),
        { height: 160, legendEl: legend });
    },
  },
  {
    id: 'u', title: 'Control effort  u', diag: true,
    need: () => hist.u.length > 0,
    draw(c, legend) {
      renderLines(c, hist.t, series('u', range(0, hist.u.length), i => uLabel(i)),
        { height: 160, legendEl: legend });
    },
  },
  {
    id: 'xhat', title: 'Observer state  ξ̂', diag: true,
    need: () => hist.xhat.length > 0,
    draw(c, legend) {
      renderLines(c, hist.t, series('xhat', range(0, hist.xhat.length), i => `ξ${i}`),
        { height: 160, legendEl: legend });
    },
  },
];

function range(a, b) { return Array.from({ length: b - a }, (_, i) => a + i); }

function buildPanels() {
  const grid = $('#grid');
  grid.replaceChildren();
  for (const p of PANELS) {
    const card = document.createElement('section');
    card.className = 'panel';
    card.id = `panel-${p.id}`;
    card.innerHTML =
      `<header><h3>${p.title}</h3><div class="legend"></div></header>` +
      `<div class="plot"></div>` +
      `<div class="overlay">enable <code>publish_diagnostics:=true</code> on the controller</div>`;
    grid.appendChild(card);
    p._plot = card.querySelector('.plot');
    p._legend = card.querySelector('.legend');
    p._card = card;
  }
}

/* ---- stat tiles ------------------------------------------------------ */

function tile(label, value, cls = '') {
  return `<div class="tile ${cls}"><span class="v">${value}</span>` +
         `<span class="l">${label}</span></div>`;
}

function renderStats() {
  const m = lastMetrics;
  const perf = $('#perf');
  const t = m.timing || {};
  const rms = m.rms_error;
  perf.innerHTML =
    tile('RMS error', rms == null ? '—' : rms.toFixed(4)) +
    tile('loop rate', t.rate_hz ? `${t.rate_hz.toFixed(0)} Hz` : '—') +
    tile('exec mean', t.update_us_mean ? `${t.update_us_mean.toFixed(0)} µs` : '—') +
    tile('exec max', t.update_us_max ? `${t.update_us_max.toFixed(0)} µs` : '—') +
    tile('deadline miss', t.deadline_misses != null ? t.deadline_misses : '—',
      t.deadline_misses ? 'bad' : 'good');

  // per-channel settling table
  const st = $('#settle');
  if (m.error && m.error.length) {
    st.innerHTML = m.error.map((e, i) =>
      `<div class="row"><span title="${errLabel(i)}">${errLabel(i)}</span>` +
      `<span class="${e.settled ? 'good' : 'warn'}">${e.settled ? 'settled' : 'settling'}</span>` +
      `<span>${e.settling_time == null ? '—' : e.settling_time.toFixed(2) + ' s'}</span>` +
      `<span>rms ${e.rms.toFixed(4)}</span></div>`).join('');
  } else {
    st.innerHTML = '<div class="muted">no error feed</div>';
  }
}

function renderStatus() {
  $('#controller').textContent = meta.controller || '—';
  const f = lastFrame;
  const badge = $('#constraint');
  if (f && !f.valid) {
    badge.textContent = `VALIDITY TRIP → ${f.safe_action}`;
    badge.className = 'badge bad';
  } else {
    badge.textContent = 'within validity region';
    badge.className = 'badge good';
  }
  const miss = $('#deadline');
  const dm = (lastMetrics.timing || {}).deadline_misses || 0;
  miss.textContent = dm ? `${dm} deadline miss(es)` : 'no deadline misses';
  miss.className = 'badge ' + (dm ? 'bad' : 'good');
}

/* ---- main loop ------------------------------------------------------- */

function redraw() {
  if (dirty) {
    dirty = false;
    for (const p of PANELS) {
      const live = p.need();
      const greyed = (p.diag && !meta.has_diag) || !live;
      p._card.classList.toggle('greyed', greyed);
      if (live) p.draw(p._plot, p._legend);
    }
    renderStats();
    renderStatus();
  }
  requestAnimationFrame(redraw);
}

function onSnapshot(snap) {
  if (snap.meta_rev !== metaRev) {
    metaRev = snap.meta_rev;
    meta = snap.meta;
    resetHistory();
  }
  for (const f of snap.frames) pushFrame(f);
  if (snap.metrics) lastMetrics = snap.metrics;
  if (snap.frames.length || snap.metrics) dirty = true;
}

function connect() {
  const es = new EventSource('/stream');
  const dot = $('#conn');
  es.onopen = () => { dot.className = 'dot on'; };
  es.onerror = () => { dot.className = 'dot off'; };
  es.onmessage = ev => {
    try { onSnapshot(JSON.parse(ev.data)); } catch (e) { /* ignore partial */ }
  };
}

buildPanels();
connect();
requestAnimationFrame(redraw);
