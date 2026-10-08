import test from 'node:test';
import assert from 'node:assert/strict';
import {
  contractLabel, eligible, esc, gapNote, hasPublishedEtf, historySeries, modelStatusBadge, planLabel, plural, safeUrl, tariffNotice, typeLabel,
} from '../../site/js/ui.js';

test('esc escapes & < > " \' and tolerates null/undefined', () => {
  assert.equal(esc('&<>"\''), '&amp;&lt;&gt;&quot;&#39;');
  assert.equal(esc('<img src=x onerror="alert(1)">'), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt;');
  assert.equal(esc(null), '');
  assert.equal(esc(undefined), '');
  assert.equal(esc(0), '0');
  assert.equal(esc('a&amp;b'), 'a&amp;amp;b'); // no double-decoding: escaping is applied once, always
});

test('safeUrl accepts only https', () => {
  assert.equal(safeUrl('https://example.com/x?y=1'), 'https://example.com/x?y=1');
  assert.equal(safeUrl('HTTPS://EXAMPLE.COM'), 'HTTPS://EXAMPLE.COM');
  for (const bad of ['http://example.com', 'javascript:alert(1)', 'data:text/html,<b>x</b>', '', null, undefined, '//example.com', ' https://example.com']) {
    assert.equal(safeUrl(bad), null, `should reject ${JSON.stringify(bad)}`);
  }
});

test('plural', () => {
  assert.equal(plural(1, 'month'), '1 month');
  assert.equal(plural(0, 'month'), '0 months');
  assert.equal(plural(3, 'month'), '3 months');
});

const plan = (o = {}) => ({ id: 'x', green: false, standard: true, eligibility: undefined, ...o });
const base = { greenOnly: false, standardOnly: false, current: 'fixed' };

test('eligible: SP-customers-only plans are hidden unless the household is on SP', () => {
  const sp = plan({ eligibility: 'sp_customers_only' });
  assert.equal(eligible(sp, { ...base, current: 'fixed' }), false);
  assert.equal(eligible(sp, { ...base, current: 'dot' }), false);
  assert.equal(eligible(sp, { ...base, current: 'sp' }), true);
  assert.equal(eligible(plan(), { ...base, current: 'fixed' }), true);
});

test('eligible: "Standard only" excludes non-standard AND unknown standard status (decision N6)', () => {
  const inp = { ...base, standardOnly: true };
  assert.equal(eligible(plan({ standard: true }), inp), true);
  assert.equal(eligible(plan({ standard: false }), inp), false);
  assert.equal(eligible(plan({ standard: null }), inp), false);
  assert.equal(eligible(plan({ standard: undefined }), inp), false);
  // without the filter, unknown status is shown
  assert.equal(eligible(plan({ standard: null }), base), true);
});

test('eligible: green-only filter and combined filters', () => {
  assert.equal(eligible(plan({ green: false }), { ...base, greenOnly: true }), false);
  assert.equal(eligible(plan({ green: true }), { ...base, greenOnly: true }), true);
  assert.equal(eligible(plan({ green: true, standard: null }), { ...base, greenOnly: true, standardOnly: true }), false);
});

test('contractLabel: current plan with 1 month left, 0 months, and several months', () => {
  const cur = { id: 'current', contract_months: 24 };
  assert.equal(contractLabel(cur, { curMonths: 1 }, true), '1 month left (renews for 24 months)');
  assert.equal(contractLabel(cur, { curMonths: 1 }, false), '1 mo left');
  assert.equal(contractLabel(cur, { curMonths: 0 }, true), 'contract ended (renews for 24 months)');
  assert.equal(contractLabel(cur, { curMonths: 0 }, false), 'ended');
  assert.equal(contractLabel(cur, { curMonths: 5 }, true), '5 months left (renews for 24 months)');
  assert.match(contractLabel(cur, { curMonths: 1 }, true), /^1 month left/);
  assert.match(contractLabel(cur, { curMonths: 0 }, true), /^contract ended/);
});

test('contractLabel: other plans', () => {
  assert.equal(contractLabel({ id: 'a', contract_months: 0 }, {}, true), 'no contract');
  assert.equal(contractLabel({ id: 'a', contract_months: 0 }, {}, false), 'none');
  assert.equal(contractLabel({ id: 'a', contract_months: 24 }, {}, true), '24-month contract');
  assert.equal(contractLabel({ id: 'a', contract_months: 24 }, {}, false), '24 mo');
});

test('planLabel and typeLabel', () => {
  assert.equal(planLabel({ name: 'Basic', retailer: 'Acme', retailer_id: 'acme', id: 'a1' }), 'Basic · Acme');
  assert.equal(planLabel({ name: 'Regulated', retailer: 'SP', retailer_id: 'sp', id: 'sp' }), 'Regulated');
  assert.equal(planLabel({ name: 'Keep', retailer: 'Me', retailer_id: 'current', id: 'current' }), 'Keep');
  assert.equal(typeLabel({ price_type: 'fixed', rates: { rate: 27.5 } }), 'Fixed 27.50¢');
  assert.equal(typeLabel({ price_type: 'dot_pct', rates: { discount_pct: 0 } }), 'Regulated tariff');
  assert.equal(typeLabel({ price_type: 'dot_pct', rates: { discount_pct: 5 } }), '5% off tariff');
  assert.equal(typeLabel({ price_type: 'dot_cents', rates: { discount_cents: 2 } }), '2¢ off tariff');
  assert.equal(typeLabel({ price_type: 'tou', rates: { periods: [{ rate: 40 }], default_rate: 20 } }), 'Peak 40.00¢ / off-peak 20.00¢');
  assert.equal(typeLabel({ price_type: 'block', rates: { blocks: [{ rate: 20 }, { rate: 30 }] } }), 'Tiered 20.00¢ → 30.00¢');
  assert.equal(typeLabel({ price_type: 'weird', rates: {} }), 'weird');
});

test('hasPublishedEtf', () => {
  assert.equal(hasPublishedEtf({}), false);
  assert.equal(hasPublishedEtf({ terms: {} }), false);
  assert.equal(hasPublishedEtf({ terms: { early_termination_fee_sgd: 0 } }), true);
  assert.equal(hasPublishedEtf({ terms: { etf_schedule: [{ from: 1 }] } }), true);
  assert.equal(hasPublishedEtf({ terms: { etf_schedule: [] } }), false);
  assert.equal(hasPublishedEtf({ terms: { etf_by_dwelling: { hdb4: 100 } } }), true);
});

// ---- published-data contract: history sources / gaps, model status ----------------------------------------------

const H = [
  { quarter: '2015Q4', incl_gst: 25 },
  { quarter: '2026Q1', incl_gst: 29.11 },
  { quarter: '2026Q2', incl_gst: 29.72, source: 'official' },
  { quarter: '2026Q4', incl_gst: 33.1, source: 'retailer_quote' },
];

test('historySeries: filters from 2016Q1, missing source means official, marks retailer quotes', () => {
  const s = historySeries(H, []);
  assert.deepEqual(s.map((r) => r.quarter), ['2026Q1', '2026Q2', '2026Q4']);
  assert.deepEqual(s.map((r) => r.source), ['official', 'official', 'retailer_quote']);
  assert.ok(s.every((r) => !r.gap));
});

test('historySeries: a gap inside the range becomes a null row (never interpolated); gaps outside are ignored', () => {
  const s = historySeries(H, ['2026Q3', '2027Q1', '2010Q1', '2026Q2']);
  assert.deepEqual(s.map((r) => r.quarter), ['2026Q1', '2026Q2', '2026Q3', '2026Q4']);
  const g = s.find((r) => r.quarter === '2026Q3');
  assert.equal(g.incl_gst, null);
  assert.equal(g.gap, true);
  assert.equal(s.find((r) => r.quarter === '2026Q2').gap, false); // a quarter that has data is not overwritten
});

test('historySeries: old files without gaps or sources, and empty input, still work', () => {
  assert.equal(historySeries(H.slice(0, 3), undefined).length, 2);
  assert.deepEqual(historySeries([], ['2026Q3']), []);
  assert.deepEqual(historySeries(undefined, null), []);
});

test('gapNote: empty for none/missing, escapes labels, singular and plural wording', () => {
  assert.equal(gapNote(undefined), '');
  assert.equal(gapNote([]), '');
  assert.equal(gapNote(['2026Q3']), 'No tariff observed for 2026Q3; the history skips it rather than guessing.');
  assert.equal(gapNote(['2026Q3', '2026Q4']), 'No tariff observed for 2026Q3, 2026Q4; the history skips them rather than guessing.');
  assert.ok(!gapNote(['<script>x</script>']).includes('<script>'));
  assert.ok(gapNote(['<b>']).includes('&lt;b&gt;'));
});

const RT = { cents_incl_gst: 31.16, quarter: 'Q4 2026' };
const MT = { current_incl_gst: 31.16, current_quarter: '2026Q4' };

test('tariffNotice: a labelled quote that matches the forecast start shows nothing', () => {
  assert.equal(tariffNotice(RT, MT), '');
});

test('tariffNotice: an unlabelled quote warns and names the quarter and value the forecast uses', () => {
  for (const quarter of [null, undefined, '']) {
    const html = tariffNotice({ ...RT, quarter }, { current_incl_gst: 34.78, current_quarter: '2026Q3' });
    assert.equal(html, '<span class="badge warn">Tariff quarter not confirmed by any retailer page; the forecast starts from 2026Q3 at 34.78¢</span>');
  }
});

test('tariffNotice: a labelled quote that differs from the forecast start warns with both values', () => {
  const html = tariffNotice(RT, { current_incl_gst: 34.78, current_quarter: '2026Q3' });
  assert.equal(html, '<span class="badge warn">Tariff quoted by retailers (31.16¢) differs from the one the forecast starts from (34.78¢, 2026Q3)</span>');
});

test('tariffNotice: differences up to 0.005 are rounding noise', () => {
  assert.equal(tariffNotice(RT, { ...MT, current_incl_gst: 31.164 }), '');
  assert.notEqual(tariffNotice(RT, { ...MT, current_incl_gst: 31.17 }), '');
});

test('tariffNotice: missing inputs or a non-number quote show nothing', () => {
  assert.equal(tariffNotice(null, MT), '');
  assert.equal(tariffNotice(undefined, MT), '');
  assert.equal(tariffNotice(RT, null), '');
  assert.equal(tariffNotice(RT, undefined), '');
  assert.equal(tariffNotice({ ...RT, cents_incl_gst: '31.16' }, MT), '');
  assert.equal(tariffNotice({ ...RT, cents_incl_gst: null }, MT), '');
  assert.equal(tariffNotice({ ...RT, cents_incl_gst: NaN }, MT), '');
  assert.equal(tariffNotice({ quarter: null }, MT), '');
});

test('tariffNotice: the forecast quarter is escaped', () => {
  const html = tariffNotice({ ...RT, quarter: null }, { current_incl_gst: 31.16, current_quarter: '<b>2026Q4</b>' });
  assert.ok(!html.includes('<b>'));
  assert.ok(html.includes('&lt;b&gt;2026Q4&lt;/b&gt;'));
  const html2 = tariffNotice(RT, { current_incl_gst: 40, current_quarter: '<b>x</b>' });
  assert.ok(!html2.includes('<b>') && html2.includes('&lt;b&gt;'));
});

test('modelStatusBadge: only a stale state shows a warning; ok or missing file shows nothing', () => {
  assert.equal(modelStatusBadge(null), '');
  assert.equal(modelStatusBadge(undefined), '');
  assert.equal(modelStatusBadge({ state: 'ok', model_as_of: '2026-10-01T00:00:00Z', checked_at: '2026-10-08T00:00:00Z' }), '');
  assert.equal(modelStatusBadge({ state: 'weird' }), '');
  const html = modelStatusBadge({ state: 'stale', model_as_of: '2026-09-01T00:00:00Z', checked_at: 'x', error: 'boom "x" <b>' }, (d) => `D(${d})`);
  assert.match(html, /^<span class="badge warn" title="boom &quot;x&quot; &lt;b&gt;">/);
  assert.match(html, /Forecast model last fitted D\(2026-09-01T00:00:00Z\) — latest refresh could not refit it/);
  assert.ok(!html.includes('<b>'));
  // no error text -> no title; no date -> no invented date
  const bare = modelStatusBadge({ state: 'stale', model_as_of: null, checked_at: 'x' });
  assert.ok(!bare.includes('title='));
  assert.ok(!bare.includes('last fitted'));
  assert.match(bare, /could not refit it/);
});
