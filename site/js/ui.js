// Pure, DOM-free helpers used by app.js. Everything here depends only on its arguments, so it can be unit-tested
// under Node (tests/js/ui.test.mjs). Scraped strings are untrusted: escape with esc(), links through safeUrl().

export const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
export const sgd = (x) => `$${Math.round(x).toLocaleString('en-SG')}`;
export const cents = (x) => `${x.toFixed(2)}¢`;
export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-SG', { day: 'numeric', month: 'short', year: 'numeric' }) : 'unknown');
export const daysAgo = (iso, now = Date.now()) => (iso ? (now - new Date(iso).getTime()) / 864e5 : Infinity);
export const safeUrl = (u) => (/^https:\/\//i.test(u || '') ? u : null);
export const monthName = (ym) => new Date(`${ym}-01T00:00:00`).toLocaleDateString('en-SG', { month: 'short', year: 'numeric' });
export const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

// Is this plan offered to this household under the user's filters? `inp` needs greenOnly, standardOnly, current.
export function eligible(p, inp) {
  if (inp.greenOnly && !p.green) return false;
  if (inp.standardOnly && p.standard !== true) return false; // unknown status is excluded, not admitted
  if (p.eligibility === 'sp_customers_only' && inp.current !== 'sp') return false;
  return true;
}

export function hasPublishedEtf(p) {
  const t = p.terms || {};
  return !!(t.etf_schedule?.length || t.etf_by_dwelling || typeof t.early_termination_fee_sgd === 'number');
}

// `inp.curMonths` is the months left on the user's current contract (only read for the current plan).
export function contractLabel(p, inp, long) {
  if (p.id === 'current') {
    const m = inp.curMonths;
    if (!long) return m ? `${m} mo left` : 'ended';
    return m ? `${plural(m, 'month')} left (renews for ${p.contract_months} months)` : `contract ended (renews for ${p.contract_months} months)`;
  }
  if (!p.contract_months) return long ? 'no contract' : 'none';
  return long ? `${p.contract_months}-month contract` : `${p.contract_months} mo`;
}

export function planLabel(p) { return `${p.name}${p.retailer_id === 'sp' || p.id === 'current' ? '' : ` · ${p.retailer}`}`; }

export function typeLabel(p) {
  const r = p.rates;
  switch (p.price_type) {
    case 'fixed': return `Fixed ${cents(r.rate)}`;
    case 'dot_pct': return r.discount_pct ? `${r.discount_pct}% off tariff` : 'Regulated tariff';
    case 'dot_cents': return `${r.discount_cents}¢ off tariff`;
    case 'tou': return `Peak ${cents(r.periods[0].rate)} / off-peak ${cents(r.default_rate)}`;
    case 'block': return `Tiered ${r.blocks.map((b) => cents(b.rate)).join(' → ')}`;
    default: return p.price_type;
  }
}

// ---- published-data contract: tariff history sources / gaps, model status -------------------------------------

export const QUOTE_LABEL = 'Retailer-quoted (official statistics not yet published)';

// Rows for the history line: rows from `fromQuarter` on, plus a null row for every quarter listed in `gaps` that
// falls strictly inside the observed range, so the chart shows a break instead of interpolating. A missing
// `source` means official. Output rows: { quarter, incl_gst (null for a gap), source, gap }.
export function historySeries(history, gaps, fromQuarter = '2016Q1') {
  const rows = (history || []).filter((h) => h.quarter >= fromQuarter)
    .map((h) => ({ quarter: h.quarter, incl_gst: h.incl_gst, source: h.source === 'retailer_quote' ? 'retailer_quote' : 'official', gap: false }));
  if (!rows.length) return rows;
  const first = rows[0].quarter, last = rows[rows.length - 1].quarter;
  const have = new Set(rows.map((r) => r.quarter));
  (Array.isArray(gaps) ? gaps : []).forEach((g) => {
    if (typeof g === 'string' && g > first && g < last && !have.has(g)) {
      rows.push({ quarter: g, incl_gst: null, source: 'official', gap: true });
      have.add(g);
    }
  });
  return rows.sort((a, b) => (a.quarter < b.quarter ? -1 : a.quarter > b.quarter ? 1 : 0));
}

// One muted warning line (HTML, escaped) for quarters nobody observed; '' when there are none.
export function gapNote(gaps) {
  const list = (Array.isArray(gaps) ? gaps : []).filter((g) => typeof g === 'string' && g);
  if (!list.length) return '';
  return `No tariff observed for ${esc(list.join(', '))}; the history skips ${list.length === 1 ? 'it' : 'them'} rather than guessing.`;
}

// Warning badge (HTML) when the last refresh could not refit the forecast model. Nothing for "ok", a missing
// file (null/undefined) or anything unrecognised. The error text goes in a title attribute, escaped.
export function modelStatusBadge(ms, fmt = fmtDate) {
  if (!ms || typeof ms !== 'object' || ms.state !== 'stale') return '';
  const text = ms.model_as_of
    ? `Forecast model last fitted ${esc(fmt(ms.model_as_of))} — latest refresh could not refit it`
    : 'Forecast model: latest refresh could not refit it';
  const why = ms.error ? ` title="${esc(ms.error)}"` : '';
  return `<span class="badge warn"${why}>${text}</span>`;
}
