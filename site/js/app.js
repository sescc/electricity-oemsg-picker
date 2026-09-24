import { PROFILES, SP_TARIFF_PLAN, effectiveRate, nightShare, withNightShare } from './billing.js';
import {
  DWELLINGS, addMonths, consumptionForecast, daysIn, fitHousehold, past12Months, pastCdd, quarterStartMonth,
} from './household.js';
import { etfFor, policyAt, simulate, solve } from './mdp.js';

const METER_FEE = 43.6;
const MAX_MONTHS = 36;
const BILLS_KEY = 'electricity-picker.bills.v1';
const SIM_PATHS = 800; // per plan; enough for stable P10/P90 (±~1%) while staying interactive
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const sgd = (x) => `$${Math.round(x).toLocaleString('en-SG')}`;
const cents = (x) => `${x.toFixed(2)}¢`;
const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString('en-SG', { day: 'numeric', month: 'short', year: 'numeric' }) : 'unknown');
const daysAgo = (iso) => (iso ? (Date.now() - new Date(iso).getTime()) / 864e5 : Infinity);
const safeUrl = (u) => (/^https:\/\//i.test(u || '') ? u : null);

let DATA = null;
const charts = {};

async function loadData() {
  const get = async (f) => {
    const r = await fetch(`data/${f}`, { cache: 'no-cache' });
    if (!r.ok) throw new Error(`${f}: HTTP ${r.status}`);
    return r.json();
  };
  const [plans, status, model] = await Promise.all([get('plans.json'), get('status.json'), get('model.json')]);
  return { plans, status, model };
}

// ------------------------------------------------------------------ form
function initForm() {
  const m = DATA.model;
  $('dwelling').innerHTML = DWELLINGS.filter(([k]) => m.consumption[k])
    .map(([k, label]) => `<option value="${k}">${esc(label)}</option>`).join('');
  $('dwelling').value = 'hdb4';
  $('profile').innerHTML = Object.entries(PROFILES).map(([k, p]) => `<option value="${k}">${esc(p.label)}</option>`).join('');
  const setTypical = () => {
    const c = m.consumption[$('dwelling').value];
    $('kwh').value = Math.round(c.typical_monthly_kwh / 10) * 10;
    $('kwhHint').textContent = `National average for this home type: ${Math.round(c.typical_monthly_kwh)} kWh/month (EMA, 12 months to ${c.fitted_to}). Use your own bills if you can.`;
  };
  const setNight = () => { $('night').value = nightShare(PROFILES[$('profile').value]).toFixed(2); };
  $('dwelling').addEventListener('change', setTypical);
  $('profile').addEventListener('change', setNight);
  $('current').addEventListener('change', () => {
    const v = $('current').value;
    $('currentDetails').hidden = v === 'sp';
    $('curRateLabel').textContent = v === 'dot' ? 'Your discount off the tariff (%)' : 'Your rate (¢/kWh incl. GST)';
    $('curRate').value = v === 'dot' ? 5 : 30.5;
  });
  setTypical();
  setNight();
  initBills(setTypical);
  let timer;
  const schedule = (ms) => {
    clearTimeout(timer);
    document.body.classList.add('busy');
    timer = setTimeout(run, ms); // the busy style paints before this task runs
  };
  $('form').addEventListener('input', () => schedule(350));
  $('form').addEventListener('change', () => schedule(60));
  $('showAll').addEventListener('change', () => renderRanking(window.__last));
}

const monthName = (ym) => new Date(`${ym}-01T00:00:00`).toLocaleDateString('en-SG', { month: 'short', year: 'numeric' });

// Past-12-month bill inputs. Values stay in this browser only (localStorage), never sent anywhere.
function initBills(setTypical) {
  const months = past12Months();
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(BILLS_KEY) || '{}') || {}; } catch { saved = {}; }
  $('bills').innerHTML = months.map((m) => {
    const w = pastCdd(DATA.model.weather, m);
    return `<label class="bill">${esc(monthName(m))}${w.observed ? '' : ' <span class="muted" title="Weather for this month not yet available; typical weather used">*</span>'}
      <input type="number" min="0" max="20000" step="1" inputmode="numeric" data-month="${m}" placeholder="kWh"
        value="${Number(saved[m]) > 0 ? Number(saved[m]) : ''}"></label>`;
  }).join('');
  if (months.some((m) => Number(saved[m]) > 0)) $('billsBox').open = true;
  const persist = () => {
    const obj = {};
    document.querySelectorAll('#bills input').forEach((i) => { if (Number(i.value) > 0) obj[i.dataset.month] = Number(i.value); });
    try { localStorage.setItem(BILLS_KEY, JSON.stringify(obj)); } catch { /* storage unavailable: fine */ }
  };
  $('bills').addEventListener('input', persist);
  $('billsClear').addEventListener('click', () => {
    document.querySelectorAll('#bills input').forEach((i) => { i.value = ''; });
    persist();
    setTypical();
    $('form').dispatchEvent(new Event('change'));
  });
}

function readBills() {
  return [...document.querySelectorAll('#bills input')]
    .map((i) => ({ month: i.dataset.month, kwh: Number(i.value) }))
    .filter((b) => Number.isFinite(b.kwh) && b.kwh >= 10 && b.kwh <= 20000);
}

function renderBillsFit(inp, fit) {
  const kwh = $('kwh');
  if (!fit) {
    kwh.disabled = false;
    $('billsFit').textContent = 'Leave months blank if you don\'t know them. Even a few months help.';
    return;
  }
  kwh.disabled = true;
  kwh.value = Math.round(fit.typicalMonthlyKwh);
  const nat = DATA.model.consumption[inp.dwelling].cdd_coef;
  const sens = fit.dataWeight < 0.15
    ? `weather sensitivity kept at the national ${(nat * 100).toFixed(1)}% (not enough weather variation in your months to estimate your own)`
    : `your weather sensitivity ≈ ${(fit.b * 100).toFixed(1)}% per cooling degree (national ${(nat * 100).toFixed(1)}%; ${Math.round(fit.dataWeight * 100)}% from your data)`;
  $('billsFit').textContent = `Using ${fit.n} month${fit.n > 1 ? 's' : ''} of your bills: a typical month is about ${Math.round(fit.typicalMonthlyKwh)} kWh; ${sens}. This replaces the average above.`;
}

function readForm() {
  const f = new FormData($('form'));
  const num = (k) => Number(f.get(k));
  $('nightOut').textContent = `${Math.round(num('night') * 100)}%`;
  $('riskOut').textContent = num('risk') === 0 ? 'average only' : `${Math.round(num('risk') * 100)}% weight on bad case`;
  return {
    dwelling: f.get('dwelling'), kwh: Math.max(30, Number($('kwh').value) || 0), bills: readBills(),
    profileKey: f.get('profile'), night: num('night'),
    hasSmartMeter: f.get('meter') === 'yes', current: f.get('current'), curRate: num('curRate'),
    curMonths: Math.min(60, Math.max(0, Math.round(num('curMonths')))), curTerm: num('curTerm') || 12,
    curEtf: Math.max(0, num('curEtf')), stay: num('stay'),
    rebates: f.get('rebates') === 'on', greenOnly: f.get('green') === 'on', standardOnly: f.get('standard') === 'on',
    hassle: Math.max(0, num('hassle')), risk: num('risk'), defaultEtf: Math.max(0, num('defEtf')),
  };
}

// ------------------------------------------------------------------ model run
function eligible(p, inp) {
  if (inp.greenOnly && !p.green) return false;
  if (inp.standardOnly && p.standard !== true) return false; // unknown status is excluded, not admitted
  if (p.eligibility === 'sp_customers_only' && inp.current !== 'sp') return false;
  return true;
}

function currentPlan(inp) {
  if (inp.current === 'sp') return { ...SP_TARIFF_PLAN, name: 'Stay on the regulated tariff' };
  return {
    id: 'current', retailer_id: 'current', retailer: 'Your current retailer', name: 'Keep your current plan',
    price_type: inp.current === 'dot' ? 'dot_pct' : 'fixed',
    rates: inp.current === 'dot' ? { discount_pct: inp.curRate } : { rate: inp.curRate },
    // contract_months is the term it renews for; the months left right now are ctx.currentR
    contract_months: inp.curTerm, months_left: inp.curMonths,
    daily_charge_cents: 0, rebate_sgd: 0, smart_meter_required: false,
    terms: { early_termination_fee_sgd: inp.curEtf }, conditions: [],
  };
}

function billsFit(inp) {
  const { model } = DATA;
  return fitHousehold(inp.bills, model.weather, model.consumption[inp.dwelling].cdd_coef);
}

function compute(inp) {
  const { model, plans: pj } = DATA;
  const t = model.tariff;
  const HM = Math.min(MAX_MONTHS, inp.stay);
  const moving = inp.stay < 36;           // "3 years or more": no move-out inside the horizon
  const firstQuarter = t.fan_incl_gst[0].quarter;
  const firstMonth = quarterStartMonth(firstQuarter);
  const fit = billsFit(inp);
  const usage = consumptionForecast({
    avgMonthlyKwh: inp.kwh, coef: model.consumption[inp.dwelling].cdd_coef, fit, weather: model.weather,
    firstMonth, nMonths: HM,
  });
  const typicalKwh = fit ? fit.typicalMonthlyKwh : inp.kwh;
  const profile = withNightShare(PROFILES[inp.profileKey], inp.night);
  const cur = currentPlan(inp);
  const candidates = pj.plans.filter((p) => eligible(p, inp)).map((p) => (
    // some rebates are larger for households switching away from SP Group
    inp.current !== 'sp' && typeof p.rebate_sgd_non_sp === 'number' ? { ...p, rebate_sgd: p.rebate_sgd_non_sp } : p));
  const plans = [cur, ...(cur.id === SP_TARIFF_PLAN.id ? [] : [SP_TARIFF_PLAN]), ...candidates];
  const mk = t.markov;
  const chain = { levels: mk.levels_incl_gst, P: mk.transition, initial: mk.initial };
  const ctx = {
    profile, dwelling: inp.dwelling, hassle: inp.hassle, meterFee: METER_FEE, hasSmartMeter: inp.hasSmartMeter,
    includeRebates: inp.rebates, defaultEtf: inp.defaultEtf, currentTariff: t.current_incl_gst,
    currentR: cur.id === 'current' ? inp.curMonths : 0, payEtfOnMove: moving, discount: 0.97,
  };
  const sol = solve(plans, chain, usage, ctx);
  const rows = plans.map((p, q) => {
    const sim = simulate(sol, plans, chain, ctx, q, SIM_PATHS, 11);
    const score = sim.mean + inp.risk * (sim.p90 - sim.mean);
    // exit fee shown: for the current plan, leaving now; for a new plan, leaving in its first month
    const exitR = p.id === 'current' ? inp.curMonths : p.contract_months;
    return {
      p, q, sim, score, bellman: sol.firstQ[q],
      effRate: effectiveRate(p, typicalKwh, t.current_incl_gst, profile),
      etf: exitR ? etfFor(p, exitR, ctx) : 0,
      etfKnown: p.contract_months === 0 || p.id === 'current' || hasPublishedEtf(p),
    };
  });
  rows.sort((a, b) => a.score - b.score);

  // Sensitivity: would the winner change if future re-contract offers stayed at today's prices?
  // (compared on expected cost from the Bellman values; no extra simulation needed)
  const solF = solve(plans, chain, usage, { ...ctx, frozenOffers: true });
  const frozenBest = solF.firstQ.indexOf(Math.min(...solF.firstQ));
  return { inp, HM, moving, usage, fit, typicalKwh, plans, chain, ctx, sol, rows, firstQuarter, firstMonth, profile,
    sensitivity: { frozenBest: plans[frozenBest], sameWinner: frozenBest === rows[0].q } };
}

function hasPublishedEtf(p) {
  const t = p.terms || {};
  return !!(t.etf_schedule?.length || t.etf_by_dwelling || typeof t.early_termination_fee_sgd === 'number');
}

// ------------------------------------------------------------------ rendering
function renderFreshness() {
  const { plans, status, model } = DATA;
  const rt = plans.regulated_tariff;
  const ret = Object.values(status.retailers);
  const stale = ret.filter((r) => r.stale || r.status === 'failed');
  const bits = [
    `<span>Plans updated <b>${fmtDate(plans.generated_at)}</b></span>`,
    rt ? `<span>Regulated tariff ${esc(rt.quarter || '')}: <b>${rt.cents_incl_gst.toFixed(2)}¢/kWh</b> incl. GST</span>` : '',
    `<span>${ret.length} retailers on the OEM list · ${plans.plans.length} residential plans</span>`,
    `<span>Models fitted <b>${fmtDate(model.generated_at)}</b></span>`,
  ];
  if (rt?.stale) bits.push(`<span class="badge warn">Tariff quote last read ${fmtDate(rt.observed_at)}; it may be out of date</span>`);
  if (stale.length) bits.push(`<span class="badge warn">${stale.length} retailer(s) showing last-known data</span>`);
  if (daysAgo(plans.generated_at) > 3) bits.push('<span class="badge warn">Plan data is more than 3 days old</span>');
  $('freshness').innerHTML = bits.filter(Boolean).join('');
}

const plural = (n, w) => `${n} ${w}${n === 1 ? '' : 's'}`;

function contractLabel(p, inp, long) {
  if (p.id === 'current') {
    const m = inp.curMonths;
    if (!long) return m ? `${m} mo left` : 'ended';
    return m ? `${plural(m, 'month')} left (renews for ${p.contract_months} months)` : `contract ended (renews for ${p.contract_months} months)`;
  }
  if (!p.contract_months) return long ? 'no contract' : 'none';
  return long ? `${p.contract_months}-month contract` : `${p.contract_months} mo`;
}

function planLabel(p) { return `${p.name}${p.retailer_id === 'sp' || p.id === 'current' ? '' : ` · ${p.retailer}`}`; }

function typeLabel(p) {
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

function badges(p, row) {
  const b = [];
  if (p.data_method === 'curated') b.push(`<span class="badge" title="Hand-verified; this retailer's site cannot be scraped automatically">verified by hand ${esc(p.data_as_of || '')}</span>`);
  const st = DATA.status.retailers[p.retailer_id];
  if (st?.stale) b.push('<span class="badge warn" title="Latest scrape failed; showing last-known data">last-known data</span>');
  if (p.smart_meter_required) b.push('<span class="badge">needs smart meter</span>');
  if (p.green) b.push('<span class="badge ok">green</span>');
  if (p.standard === false) b.push('<span class="badge">non-standard plan</span>');
  if (p.daily_charge_cents) b.push(`<span class="badge warn">+${p.daily_charge_cents}¢/day charge</span>`);
  if (p.eligibility === 'sp_customers_only') b.push('<span class="badge warn">only if switching from SP</span>');
  if (row && !row.etfKnown) b.push('<span class="badge warn" title="Fee not published in a readable fact sheet; your assumption is used">termination fee assumed</span>');
  return b.join('');
}

function termsDetails(p) {
  const t = p.terms || {};
  const lines = [];
  if (t.etf_text) lines.push(`<b>Early termination:</b> ${esc(t.etf_text)}`);
  if (t.security_deposit_text) lines.push(`<b>Deposit:</b> ${esc(t.security_deposit_text.slice(0, 220))}`);
  if (t.auto_renewal_text) lines.push(`<b>Renewal:</b> ${esc(t.auto_renewal_text.slice(0, 220))}`);
  if (t.late_payment_text) lines.push(`<b>Late payment:</b> ${esc(t.late_payment_text)}`);
  (p.conditions || []).forEach((c) => lines.push(esc(c)));
  if (p.rebate_note) lines.push(`<b>Rebate:</b> ${esc(p.rebate_note)}`);
  const src = safeUrl(t.source_url) || safeUrl(p.factsheet_url);
  const page = safeUrl(p.source_url);
  const links = [src && `<a href="${esc(src)}" target="_blank" rel="noopener">fact sheet</a>`,
    page && `<a href="${esc(page)}" target="_blank" rel="noopener">retailer page</a>`].filter(Boolean).join(' · ');
  if (!lines.length && !links) return '';
  return `<details class="terms"><summary>terms</summary><div>${lines.join('<br>')}${links ? `<br>${links}` : ''}</div></details>`;
}

function renderRecommendation(res) {
  const best = res.rows[0];
  const stay = res.rows.find((r) => r.q === 0);
  const sp = res.rows.find((r) => r.p.id === SP_TARIFF_PLAN.id);
  const p = best.p;
  const saveVsStay = stay.sim.mean - best.sim.mean;
  const saveVsSp = sp ? sp.sim.mean - best.sim.mean : null;
  const months = res.HM;
  const isCurrent = p.id === 'current';
  const drivers = [];
  drivers.push(`Effective price at today's tariff: <b>${cents(best.effRate)}/kWh</b> vs regulated ${cents(DATA.model.tariff.current_incl_gst)} (at ${Math.round(res.typicalKwh)} kWh in a typical month, your usage pattern, incl. daily charges).`);
  if (res.inp.rebates && p.rebate_sgd) drivers.push(`Includes a one-off ${sgd(p.rebate_sgd)} sign-up rebate: check the promo conditions.`);
  if (isCurrent) {
    const m = res.inp.curMonths;
    drivers.push(m > 0
      ? `${plural(m, 'month')} left on your contract: switching now would cost your ${sgd(best.etf)} termination fee, so it's cheaper to wait. Unless you switch, it then renews for ${res.inp.curTerm} months.`
      : `Your contract has ended, so you can switch at no fee. Keeping it means renewing for ${res.inp.curTerm} months.`);
  } else if (p.contract_months) {
    const lock = p.contract_months > months && res.moving;
    drivers.push(`${p.contract_months}-month contract; termination fee ${best.etfKnown ? '' : '(assumed) '}~${sgd(best.etf)}${lock ? ', which is <b>already counted</b> because you expect to move out before it ends' : ''}.`);
  } else drivers.push('No lock-in contract: you can leave at any time without a termination fee.');
  if (!isCurrent && res.inp.current !== 'sp' && res.inp.curMonths > 0) {
    drivers.push(`Switching now means paying your current plan's ${sgd(etfFor(res.plans[0], res.inp.curMonths, res.ctx))} termination fee (included in the totals).`);
  }
  if (p.smart_meter_required && !res.inp.hasSmartMeter) drivers.push(`Needs a smart meter: ${sgd(METER_FEE)} installation fee included.`);
  if (!isCurrent && p.contract_months && best.sim.laterSwitchRate > 0.1) {
    drivers.push(`Part of this plan's edge is flexibility: its exit fee is low enough that in ${Math.round(best.sim.laterSwitchRate * 100)}% of simulated tariff paths it pays to leave early and re-contract after the tariff falls. That assumes new offers will then be cheaper.`);
  } else if (!isCurrent && best.sim.laterSwitchRate > 0.05) {
    drivers.push(`In ${Math.round(best.sim.laterSwitchRate * 100)}% of simulated tariff paths the best move is to switch again later.`);
  }
  (p.conditions || []).forEach((c) => drivers.push(esc(c)));
  const sens = res.sensitivity;
  const sensHtml = sens.sameWinner
    ? '<p class="hint">Robustness check: the same plan still wins if future offers stay at today\'s prices instead of following the tariff.</p>'
    : `<p class="hint"><b>Sensitive to an assumption:</b> if future offers stayed at today's prices (instead of following the tariff), <b>${esc(planLabel(sens.frozenBest))}</b> would have the lowest expected cost. Treat the top few plans as close.</p>`;

  let policyHtml = '';
  let headline = esc(p.name);
  // month index at which the chosen contract runs out (counted from the start of the analysis)
  const ends = isCurrent ? res.inp.curMonths : p.contract_months;
  if (ends > 0 && ends < res.HM) {
    const K = res.chain.levels.length;
    const acts = policyAt(res.sol, ends, best.q, 0, K);
    const when = monthName(addMonths(res.firstMonth, ends - 1));
    if (isCurrent) {
      // "keep" really means "wait out the contract, then act": name the likely next plan
      const probs = res.chain.initial; // rough weight for the tariff level at that point
      const next = new Map();
      acts.forEach((q, k) => { if (q !== best.q) next.set(q, (next.get(q) || 0) + probs[k]); });
      const [nq] = [...next.entries()].sort((x, y) => y[1] - x[1])[0] || [];
      if (nq != null) {
        headline = `Wait until your contract ends (end of ${esc(when)}), then switch to ${esc(planLabel(res.plans[nq]))}`;
      }
    }
    policyHtml = `<div class="policy"><b>When this contract ends (end of ${esc(when)}), the MDP policy says:</b>
      <table><tr><th>If the tariff is then about</th><th>Best move</th></tr>${res.chain.levels.map((lvl, k) =>
      `<tr><td>${cents(lvl)}</td><td>${acts[k] === best.q ? 'renew the same plan' : esc(planLabel(res.plans[acts[k]]))}</td></tr>`).join('')}
      </table></div>`;
  }
  $('reco').innerHTML = `
    <h2>Best fit for your household</h2>
    <p class="plan">${headline}</p>
    <p class="retailer">${esc(p.retailer)} · ${esc(typeLabel(p))} · ${esc(contractLabel(p, res.inp, true))} ${badges(p, best)}</p>
    <div class="kpis">
      <div class="kpi"><div class="v">${sgd(best.sim.mean)}</div><div class="l">expected total over ${months} months</div></div>
      <div class="kpi"><div class="v">${sgd(best.sim.p10)}–${sgd(best.sim.p90)}</div><div class="l">likely range (10th–90th pct)</div></div>
      ${res.rows[0].q === 0 ? '' : `<div class="kpi"><div class="v ${saveVsStay > 0 ? 'good' : 'bad'}">${sgd(saveVsStay)}</div><div class="l">saved vs ${res.inp.current === 'sp' ? 'staying on the tariff' : 'keeping your plan'}</div></div>`}
      ${saveVsSp != null && res.inp.current !== 'sp' ? `<div class="kpi"><div class="v">${sgd(saveVsSp)}</div><div class="l">saved vs regulated tariff</div></div>` : ''}
    </div>
    <ul>${drivers.map((d) => `<li>${d}</li>`).join('')}</ul>
    ${policyHtml}
    ${sensHtml}
    <p class="hint">Runner-up: ${esc(planLabel(res.rows[1].p))} (${sgd(res.rows[1].sim.mean)} expected). Differences under about ${sgd(best.sim.mean * 0.01)} are within rounding of the assumptions.</p>`;
}

function renderRanking(res) {
  if (!res) return;
  const all = $('showAll').checked;
  const rows = all ? res.rows : res.rows.slice(0, 12);
  const best = res.rows[0];
  $('rank').innerHTML = `<thead><tr><th>#</th><th>Plan</th><th>Price</th><th class="num">Contract</th>
    <th class="num">Effective ¢/kWh now</th><th class="num">Expected cost</th><th class="num">Bad case (P90)</th>
    <th class="num">Risk-adjusted score</th><th class="num">Score vs best</th><th class="num">Exit fee</th></tr></thead><tbody>${rows.map((r, i) => `
    <tr class="${r === best ? 'best' : ''}">
      <td>${i + 1}</td>
      <td><div class="pname">${esc(r.p.name)}</div><div class="muted">${esc(r.p.retailer)}</div>${badges(r.p, r)}${termsDetails(r.p)}</td>
      <td>${esc(typeLabel(r.p))}${r.p.rebate_sgd && res.inp.rebates ? `<div class="muted">rebate ${sgd(r.p.rebate_sgd)}</div>` : ''}</td>
      <td class="num">${esc(contractLabel(r.p, res.inp, false))}</td>
      <td class="num">${r.effRate.toFixed(2)}</td>
      <td class="num">${sgd(r.sim.mean)}</td>
      <td class="num">${sgd(r.sim.p90)}</td>
      <td class="num"><b>${sgd(r.score)}</b></td>
      <td class="num">${r === best ? '—' : `+${sgd(r.score - best.score)}`}</td>
      <td class="num">${r.etf || r.p.contract_months ? `${r.etfKnown ? '' : '~'}${sgd(r.etf)}` : '$0'}</td>
    </tr>`).join('')}</tbody>`;
  const hidden = res.rows.length - rows.length;
  $('rankNote').textContent = `${res.rows.length} options evaluated over ${res.HM} months (from ${monthName(res.firstMonth)}). Ranked by risk-adjusted score = expected cost + ${Math.round(res.inp.risk * 100)}% × (bad case − expected cost), so a plan with a wider range can rank below one with a slightly higher average.` +
    (hidden > 0 ? ` ${hidden} more hidden; tick "show every plan".` : '') +
    ' "Expected cost" follows the best decisions at each renewal, not just this plan forever.';
}

function css(name) { return getComputedStyle(document.documentElement).getPropertyValue(name).trim(); }

function chart(id, cfg) {
  if (!window.Chart) return;
  charts[id]?.destroy();
  const ink = css('--muted'), grid = css('--line');
  cfg.options = {
    responsive: true, maintainAspectRatio: false, animation: false,
    plugins: { legend: { labels: { color: ink, boxWidth: 12 } }, ...(cfg.options?.plugins || {}) },
    scales: Object.fromEntries(Object.entries(cfg.options?.scales || { x: {}, y: {} }).map(([k, v]) => [k, {
      ...v, ticks: { color: ink, ...(v.ticks || {}) }, grid: { color: grid, ...(v.grid || {}) },
      title: v.title ? { color: ink, display: true, ...v.title } : undefined }])),
    ...Object.fromEntries(Object.entries(cfg.options || {}).filter(([k]) => !['plugins', 'scales'].includes(k))),
  };
  charts[id] = new window.Chart($(id), cfg);
}

function renderTariffChart() {
  const t = DATA.model.tariff;
  const hist = t.history.filter((h) => h.quarter >= '2016Q1');
  const labels = [...hist.map((h) => h.quarter), ...t.fan_incl_gst.map((f) => f.quarter)];
  const pad = (arr, before) => [...Array(before).fill(null), ...arr];
  const n = hist.length;
  const anchor = hist[n - 1].incl_gst;
  const band = (k) => pad([anchor, ...t.fan_incl_gst.map((f) => f[k])], n - 1);
  const c1 = css('--chart-1'), c2 = css('--chart-2');
  chart('tariffChart', {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Actual', data: hist.map((h) => h.incl_gst), borderColor: c1, pointRadius: 0, borderWidth: 2, stepped: true },
        { label: '90th pct', data: band('p90'), borderColor: 'transparent', backgroundColor: `${c2}22`, pointRadius: 0, fill: '+1' },
        { label: '10th pct', data: band('p10'), borderColor: 'transparent', pointRadius: 0, fill: false },
        { label: 'Median forecast', data: band('p50'), borderColor: c2, borderDash: [5, 4], pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: {
      plugins: { legend: { labels: { filter: (i) => !i.text.includes('pct') } }, tooltip: { mode: 'index', intersect: false } },
      scales: { x: { ticks: { maxTicksLimit: 8 } }, y: { title: { text: '¢/kWh incl. GST' } } },
    },
  });
  const bt = t.backtest;
  $('tariffNote').textContent = `Shaded band: 10th–90th percentile of ${t.n_paths.toLocaleString()} simulated paths. ` +
    `Forecast dynamics: ${t.simulation_model.replace('_', ' ')} (lowest one-quarter-ahead error in a ${bt.n}-quarter backtest). ` +
    `Historical quarterly volatility ${(t.volatility.hist_sd_quarterly_dlog * 100).toFixed(1)}%; recent (EWMA) ${(t.volatility.ewma_latest * 100).toFixed(1)}%.`;
}

function renderUsageChart(res) {
  const c1 = css('--chart-1'), c2 = css('--chart-2'), c3 = css('--chart-3');
  const fit = res.fit;
  // past 12 months (your bills + what the fitted model says for those months), then the forecast
  const past = fit ? past12Months() : [];
  const billOf = Object.fromEntries((fit?.points || []).map((p) => [p.month, p.kwh]));
  const labels = [...past, ...res.usage.map((u) => u.month)];
  const datasets = [{
    label: 'Forecast', data: [...past.map(() => null), ...res.usage.map((u) => Math.round(u.kwh))],
    backgroundColor: [...past.map(() => c1), ...res.usage.map((u) => (u.source === 'seasonal forecast' ? c1 : `${c3}99`))],
  }];
  if (fit) {
    datasets.push({ label: 'Your bills', data: [...past.map((m) => billOf[m] ?? null), ...res.usage.map(() => null)], backgroundColor: c2 });
    datasets.push({ label: 'Model fit to your bills', type: 'line', pointRadius: 2, borderColor: c3, borderWidth: 1.5,
      data: [...past.map((m) => Math.round(Math.exp(fit.a + fit.b * pastCdd(DATA.model.weather, m).cddPerDay) * daysIn(m))),
        ...res.usage.map(() => null)] });
  }
  chart('usageChart', {
    type: 'bar',
    data: { labels, datasets },
    options: { plugins: { legend: { display: !!fit } }, scales: { x: { stacked: true, ticks: { maxTicksLimit: 12 } }, y: { title: { text: 'kWh / month' } } } },
  });
  const c = DATA.model.consumption[res.inp.dwelling];
  $('usageNote').textContent = (fit
    ? `Fitted to ${plural(fit.n, 'month')} of your bills with observed weather (your weather sensitivity ${(fit.b * 100).toFixed(1)}% per cooling degree, shrunk towards the national ${(c.cdd_coef * 100).toFixed(1)}% for ${c.label} homes)` +
      `${fit.residSd != null ? `; typical miss ±${Math.round(fit.residSd * 100)}% a month` : ''}. `
    : `For ${c.label} homes, each extra cooling degree (°C above 24, per day) raises daily use by about ${(c.cdd_coef * 100).toFixed(1)}% ` +
      `(fitted on EMA monthly data ${c.fitted_from} to ${c.fitted_to}, R² ${c.r2}). `) +
    'Forecast: dark bars use the Open-Meteo seasonal forecast; lighter bars use 10-year climatology.';
}

function renderCostChart(res) {
  const top = res.rows.slice(0, 10);
  const c1 = css('--chart-1'), c2 = css('--chart-2');
  chart('costChart', {
    type: 'bar',
    data: {
      labels: top.map((r) => `${r.p.name} · ${r.p.retailer}`.slice(0, 42)),
      datasets: [
        { label: '10th–90th percentile', data: top.map((r) => [r.sim.p10, r.sim.p90]), backgroundColor: `${c1}55`, borderColor: c1, borderWidth: 1 },
        { label: 'Average', type: 'scatter', data: top.map((r, i) => ({ x: r.sim.mean, y: i })), backgroundColor: c2, pointRadius: 5 },
      ],
    },
    options: {
      indexAxis: 'y',
      plugins: { tooltip: { callbacks: { label: (ctx) => (Array.isArray(ctx.raw) ? `${sgd(ctx.raw[0])} – ${sgd(ctx.raw[1])}` : `average ${sgd(ctx.raw.x)}`) } } },
      scales: { x: { title: { text: `SGD over ${res.HM} months` } }, y: {} },
    },
  });
}

function renderStatus() {
  const s = DATA.status;
  const label = {
    ok: 'scraped', curated: 'hand-verified', no_residential_plans: 'no residential plans', failed: 'scrape failed',
    blocked_by_robots: 'blocked by robots.txt',
  };
  $('status').innerHTML = `<thead><tr><th>Retailer</th><th>Status</th><th>Plans</th><th>Data as of</th><th>Notes</th></tr></thead><tbody>${
    Object.values(s.retailers).map((r) => {
      const url = safeUrl(r.plans_url);
      return `<tr><td>${url ? `<a href="${esc(url)}" target="_blank" rel="noopener">${esc(r.name)}</a>` : esc(r.name)}</td>
      <td>${esc(label[r.status] || r.status)}${r.stale ? ' <span class="badge warn">stale</span>' : ''}</td>
      <td>${r.plan_count ?? 0}</td><td>${fmtDate(r.data_as_of || r.verified_at)}</td>
      <td class="muted">${esc(r.message || '')}</td></tr>`;
    }).join('')}</tbody>`;
  const chk = s.oem_list_check || {};
  const src = DATA.model.sources || {};
  const srcTxt = Object.entries(src).map(([k, v]) => `${k.replace(/_/g, ' ')} ${v.ok ? '✓' : '✗'} (${fmtDate(v.fetched_at)})`).join(' · ');
  const oem = `<a href="${esc(s.oem_list_url)}" target="_blank" rel="noopener">OEM retailer list</a>`;
  let listTxt;
  if (!chk.checked) listTxt = `The ${oem} <b>could not be checked</b> on the last run (${esc(chk.error || 'unknown error')}).`;
  else {
    const news = chk.new_on_oem_list || [], gone = chk.missing_from_oem_list || [];
    listTxt = `Checked against the ${oem} on ${fmtDate(chk.checked_at)} (${chk.retailers_found} retailers found)` +
      (news.length ? `: <b>new retailer(s) not yet supported: ${esc(news.join(', '))}</b>` : '') +
      (gone.length ? `: <b>no longer listed: ${esc(gone.join(', '))}</b>` : '') +
      (!news.length && !gone.length ? ': matches the retailers covered here.' : '.');
  }
  $('statusNote').innerHTML = `${listTxt} ` +
    `Scrapes run once a day at most, with ≥5 s between requests to any site. Statistical inputs: ${esc(srcTxt)}.`;
}

function coefTable(rows) {
  return `<table><tr><th>term</th><th>coef</th><th>s.e.</th><th>t</th><th>p</th></tr>${rows.map((c) =>
    `<tr><td>${esc(c.name)}</td><td>${c.coef?.toFixed(4)}</td><td>${c.se?.toFixed(4)}</td><td>${c.t?.toFixed(2)}</td><td>${c.p == null ? '' : c.p < 0.001 ? '<0.001' : c.p.toFixed(3)}</td></tr>`).join('')}</table>`;
}

function renderMethods() {
  const m = DATA.model, t = m.tariff, tm = t.model, bt = t.backtest;
  const c = m.consumption.overall || Object.values(m.consumption)[0];
  $('methods').innerHTML = `
  <h3>1 · Plans and terms</h3>
  <p>Each retailer on the <a href="https://www.openelectricitymarket.sg/residential/list-of-retailers" target="_blank" rel="noopener">OEM list</a> has its own adapter. Rates are normalised to GST-inclusive ¢/kWh when they are read. Tiered, peak/off-peak and daily-charge plans are costed from their <em>full</em> rate structure, never from the headline "as low as" figure. Early-termination charges, deposits and renewal terms are read from each plan's EMA-mandated Fact Sheet; where a fact sheet can't be read, the fee is marked "assumed" and uses your setting. Two retailers can't be scraped (robots.txt / bot protection), so their plans are checked by hand and dated.</p>
  <h3>2 · Your consumption (weather as input)</h3>
  <p>ln(kWh/day) = a + b·CDD/day + trend + COVID-period dummy, fitted per home type on EMA's monthly household data. CDD = cooling degree days above 24 °C from ERA5 reanalysis. If you enter past bills, your own a and b are fitted from them against each month's observed weather. b is shrunk towards your home type's national value (Bayesian prior, sd 0.03), so a few months give your level and a full year also gives your own weather sensitivity. Next months use the Open-Meteo seasonal ensemble (level anchored to the last 10 years' climatology, because the raw model's bias can't be checked without hindcasts), then climatology. National-average fit: b = ${c.cdd_coef}, R² = ${c.r2}, n = ${c.n}.</p>
  <h3>3 · Regulated tariff (wholesale price, demand and weather as inputs)</h3>
  <p>Residential plans are fixed or priced off the regulated tariff, so price volatility reaches a household only through the quarterly tariff. Model (${esc(tm.sample[0])}–${esc(tm.sample[1])}, n = ${tm.n}): <code>${esc(tm.equation)}</code></p>
  ${coefTable(tm.coefs)}
  <p>In sample, the external inputs matter: adjusted R² ${tm.adj_r2} vs ${tm.ar_only.adj_r2} without them (F = ${tm.f_test_exog.F?.toFixed(2)} on ${tm.f_test_exog.df1}, ${tm.f_test_exog.df2} d.f.).
  Out of sample (expanding-window backtest, ${bt.n} quarters from ${esc(bt.from)}), one-quarter-ahead RMSE of the log change is ${bt.rmse_log.model} (full model), ${bt.rmse_log.ar_only} (AR only) and ${bt.rmse_log.random_walk} (random walk).
  So these inputs explain past tariff moves but <b>do not improve short-term forecasts</b>, which is common for a tariff set from lagged fuel prices. The simulation therefore uses the <b>${esc(t.simulation_model.replace('_', ' '))}</b> dynamics, with shocks drawn from history in 4-quarter blocks (these include the wholesale, demand and weather effects). 80% interval coverage in the backtest: ${Math.round((bt.coverage_80 || 0) * 100)}%.</p>
  <h3>4 · Decision model (MDP)</h3>
  <p>The simulated paths are grouped into ${t.markov.k} tariff levels (${t.markov.levels_incl_gst.map((x) => x.toFixed(1)).join(', ')} ¢), a coarse chain on purpose: about 80 quarters of history can't support a finer one. The model steps month by month, so contract ends, contract lengths and move-out dates are exact; the tariff level changes only at quarter starts. Each month you hold a plan, with months left on its contract and the tariff level when you signed. You can keep it, renew it when it expires (at an offer that moves with the tariff), or switch, paying the termination fee if you leave early, the $${METER_FEE} meter fee for peak/off-peak plans and your hassle cost. Backward induction minimises expected cost over your stay. This trades short-term savings (a cheap long contract now) against long-term costs: lock-in, exit fees, and missing a later tariff drop. Plans are ranked by the value of taking each one as your first move, then acting optimally, and by the spread of ${SIM_PATHS} simulated outcomes per plan.</p>
  <h3>Main assumptions</h3>
  <ul>
    <li>Discount-off-tariff plans are applied to the whole per-kWh tariff.</li>
    <li>Future re-contract offers move in proportion to the tariff (today's fixed-rate/tariff ratio is kept).</li>
    <li>Sign-up rebates count only for plans signed now, and only if you tick the option.</li>
    <li>Hourly load profiles are typical shapes, not measured data. Adjust the night-share slider to match your own.</li>
    <li>Security deposits are refundable, so they are shown in the terms but not counted as a cost.</li>
    <li>The planning horizon is capped at 3 years. If you're staying longer, contract time left beyond 3 years is not valued, which slightly favours contracts longer than 36 months (e.g. 60-month plans).</li>
  </ul>`;
}

function run() {
  try {
    const inp = readForm();
    const t0 = performance.now();
    const res = compute(inp);
    window.__last = res;
    renderBillsFit(inp, res.fit);
    renderRecommendation(res);
    renderRanking(res);
    renderUsageChart(res);
    renderCostChart(res);
    $('error').hidden = true;
    console.debug(`computed in ${(performance.now() - t0).toFixed(0)} ms`);
  } catch (e) {
    console.error(e);
    $('error').hidden = false;
    $('error').textContent = `Something went wrong while calculating: ${e.message}`;
  } finally {
    document.body.classList.remove('busy');
  }
}

async function main() {
  try {
    DATA = await loadData();
  } catch (e) {
    $('freshness').textContent = '';
    $('error').hidden = false;
    $('error').textContent = `Could not load the plan data (${e.message}). If you opened index.html from disk, serve the folder over HTTP instead.`;
    return;
  }
  renderFreshness();
  initForm();
  renderStatus();
  renderMethods();
  const start = () => { renderTariffChart(); run(); };
  if (window.Chart) start(); else window.addEventListener('load', start);
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => { renderTariffChart(); run(); });
}

main();
