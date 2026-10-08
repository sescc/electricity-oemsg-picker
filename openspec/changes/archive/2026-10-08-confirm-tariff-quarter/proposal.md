# confirm-tariff-quarter

## Why
Open item from 2026-10-08: only PacificLight labelled the quarter of its tariff quote. If PacificLight
failed while Senoko worked, the consensus had no quarter, so the quote was shown unlabelled, never
recorded in `tariff_quotes.json`, and `model.json` silently stayed on the last recorded quarter. The page
would show one tariff in the banner and forecast from another, with nothing flagging it. That breaks
the "degrade visibly" requirement (CLAUDE.md Q1).

Senoko's plan page also states the quarter: "… vs Q4 2026 SP Tariff of 31.16¢/kWh (w/GST)!". This was
checked on the live page on 2026-10-08, and the fixture has "Q3 2026 SP Tariff of 34.78".

## What changes
- The Senoko adapter reads the quarter label from that sentence. The label is kept only when its value
  equals the "prevailing SP tariff" figure on the same page; if the page contradicts itself, it gives no label.
- The site flags the banner quote when it is unlabelled ("quarter not confirmed") or when it differs
  from the tariff the forecast model starts from.

## Impact
Code: `scraper/retailers/senoko.py`, `site/js/ui.js`, `site/js/app.js`, tests. Published JSON
is unchanged (Senoko's observation gains `tariff_quarter`, which already exists for PacificLight).
Docs: Ingest and Site IMPLEMENTATION/ARCHITECTURE/STATUS, CLAUDE.md.
