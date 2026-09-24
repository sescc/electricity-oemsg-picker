// Bill arithmetic for every normalised price type. All rates are cents/kWh incl. GST.
// Pure functions: no DOM, unit-tested with `node --test tests/js`.

// Share of a day's consumption in each hour (index 0 = 00:00-01:00). Each array sums to 1.
// These are stated assumptions, adjustable in the UI via the night-share slider.
const shape = (w) => { const s = w.reduce((a, b) => a + b, 0); return w.map((x) => x / s); };
export const PROFILES = {
  out_daytime: {
    label: 'Out on weekdays (work / school)',
    weekday: shape([5, 5, 5, 4.5, 4.5, 4.5, 4, 3.5, 2, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 1.5, 2.5, 3.5, 5, 5.5, 6, 6, 5.5]),
    weekend: shape([5, 5, 5, 4.5, 4.5, 4.5, 4, 3.5, 3, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 3.5, 4, 5, 5.5, 6, 6, 5.5]),
  },
  home_daytime: {
    label: 'Someone home most of the day',
    weekday: shape([4.5, 4.5, 4.5, 4, 4, 4, 3.5, 3.5, 3.5, 4, 4, 4.5, 4.5, 4.5, 4.5, 4.5, 4, 4, 4.5, 5, 5.5, 5.5, 5.5, 5]),
    weekend: shape([4.5, 4.5, 4.5, 4, 4, 4, 3.5, 3.5, 3.5, 4, 4, 4.5, 4.5, 4.5, 4.5, 4.5, 4, 4, 4.5, 5, 5.5, 5.5, 5.5, 5]),
  },
  night_aircon: {
    label: 'Air-con mainly at night',
    weekday: shape([7, 7, 7, 7, 6.5, 6.5, 5, 3, 1.5, 1, 1, 1, 1, 1, 1, 1, 1, 2, 3, 4, 4.5, 5, 6, 7]),
    weekend: shape([7, 7, 7, 7, 6.5, 6.5, 5.5, 4, 3, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 2.5, 3, 3.5, 4, 4.5, 5, 6, 7]),
  },
};
const NIGHT = (h) => h >= 23 || h < 7; // 11pm-7am, the usual off-peak window

export function nightShare(profile) {
  const day = (arr) => arr.reduce((a, x, h) => a + (NIGHT(h) ? x : 0), 0);
  return (5 * day(profile.weekday) + 2 * day(profile.weekend)) / 7;
}

// Rescale a profile so that `target` of consumption falls between 11pm and 7am.
export function withNightShare(profile, target) {
  const adj = (arr) => {
    const n = arr.reduce((a, x, h) => a + (NIGHT(h) ? x : 0), 0);
    return arr.map((x, h) => (NIGHT(h) ? (x * target) / n : (x * (1 - target)) / (1 - n)));
  };
  return { ...profile, weekday: adj(profile.weekday), weekend: adj(profile.weekend) };
}

export function inWindow(w, dayType, h) {
  if (w.days !== 'all' && w.days !== dayType) return false;
  if (w.start === w.end) return true;
  return w.start < w.end ? h >= w.start && h < w.end : h >= w.start || h < w.end;
}

// Consumption-weighted average rate of a time-of-use plan for a given load profile.
export function touAverageRate(rates, profile) {
  let total = 0;
  for (const [dayType, weight] of [['weekday', 5 / 7], ['weekend', 2 / 7]]) {
    profile[dayType].forEach((share, h) => {
      const p = rates.periods.find((per) => per.windows.some((w) => inWindow(w, dayType, h)));
      total += weight * share * (p ? p.rate : rates.default_rate);
    });
  }
  return total;
}

export function blockCost(blocks, kwh) {
  let cents = 0, prev = 0;
  for (const b of blocks) {
    const top = b.upto_kwh == null ? Infinity : b.upto_kwh;
    const used = Math.max(0, Math.min(kwh, top) - prev);
    cents += used * b.rate;
    prev = top;
    if (kwh <= top) break;
  }
  return cents;
}

// Energy charge in cents for one billing month (excludes daily charge).
export function energyCents(plan, kwh, tariff, profile) {
  const r = plan.rates;
  switch (plan.price_type) {
    case 'fixed': return r.rate * kwh;
    case 'dot_pct': return tariff * (1 - r.discount_pct / 100) * kwh;
    case 'dot_cents': return Math.max(0, tariff - r.discount_cents) * kwh;
    case 'tou': return touAverageRate(r, profile) * kwh;
    case 'block': return blockCost(r.blocks, kwh);
    default: throw new Error(`unknown price_type ${plan.price_type}`);
  }
}

// One month's bill in SGD.
export function monthlyBill(plan, kwh, days, tariff, profile) {
  return (energyCents(plan, kwh, tariff, profile) + (plan.daily_charge_cents || 0) * days) / 100;
}

// Effective cents/kWh at a given monthly usage, including daily charges.
export function effectiveRate(plan, kwh, tariff, profile) {
  return (monthlyBill(plan, kwh, 30.4, tariff, profile) * 100) / kwh;
}

// Rates offered on a future re-contract, assuming retailer offers move with the regulated tariff.
// Discount-off-tariff plans already follow the tariff, so they are unchanged.
export function scalePlan(plan, factor) {
  if (factor === 1 || plan.price_type === 'dot_pct' || plan.price_type === 'dot_cents') return plan;
  const r = plan.rates;
  let rates;
  if (plan.price_type === 'fixed') rates = { rate: r.rate * factor };
  else if (plan.price_type === 'tou') rates = {
    periods: r.periods.map((p) => ({ ...p, rate: p.rate * factor })), default_rate: r.default_rate * factor,
  };
  else if (plan.price_type === 'block') rates = { blocks: r.blocks.map((b) => ({ ...b, rate: b.rate * factor })) };
  return { ...plan, rates };
}

export const SP_TARIFF_PLAN = {
  id: 'sp-regulated-tariff', retailer_id: 'sp', retailer: 'SP Group', name: 'Regulated tariff (no switch)',
  price_type: 'dot_pct', rates: { discount_pct: 0 }, contract_months: 0, daily_charge_cents: 0,
  rebate_sgd: 0, smart_meter_required: false, terms: { early_termination_fee_sgd: 0 }, conditions: [],
};
