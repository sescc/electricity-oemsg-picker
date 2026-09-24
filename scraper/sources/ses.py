"""EMA Singapore Energy Statistics (annual publication, monthly series inside).

Sheets used:
  T5.2  monthly regulated tariff, cents/kWh, EXCLUDING GST
  T5.3  annual tariff components (energy, grid, market support, admin)
  T5.4  monthly average USEP (wholesale price), SGD/MWh
  T2.3  monthly peak system demand, MW
  T3.5  monthly kWh per household account, by dwelling type (national = Region 'Overall')
"""
from __future__ import annotations

import io

import openpyxl

SES_URL = ("https://www.ema.gov.sg/content/dam/corporate/resources/singapore-energy-statistics/"
           "excel/SES_tidy.xlsx.coredownload.xlsx")
DWELLINGS = ["1-room / 2-room", "3-room", "4-room", "5-room and Executive",
             "Private Apartments and Condominiums", "Landed Properties", "Overall"]


def _month_key(y, m) -> str | None:
    try:
        return f"{int(y):04d}-{int(m):02d}"
    except (TypeError, ValueError):
        return None


def parse_ses(content: bytes) -> dict:
    wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)

    def rows(sheet):
        it = wb[sheet].iter_rows(values_only=True)
        next(it)
        return [r for r in it if r and r[0] is not None]

    tariff = {r[0]: float(r[1]) for r in rows("T5.2") if isinstance(r[1], (int, float)) and str(r[0])[:2] in ("19", "20")}
    usep = {r[0]: float(r[1]) for r in rows("T5.4") if isinstance(r[1], (int, float)) and str(r[0])[:2] in ("19", "20")}
    demand = {}
    for r in rows("T2.3"):
        k = _month_key(r[0], r[1])
        if k and isinstance(r[2], (int, float)):
            demand[k] = float(r[2])
    components = {}
    for r in rows("T5.3"):
        if isinstance(r[0], int) and all(isinstance(x, (int, float)) for x in r[1:5]):
            components[str(r[0])] = {"energy": r[1], "grid": r[2], "market_support": r[3], "admin": r[4]}
    kwh = {d: {} for d in DWELLINGS}
    for r in rows("T3.5"):
        if r[3] == "Overall" and r[4] == "Overall" and r[0] in kwh:
            k = _month_key(r[1], r[2])
            if k and isinstance(r[5], (int, float)):
                kwh[r[0]][k] = float(r[5])
    return {"tariff_ex_gst": tariff, "usep": usep, "peak_demand_mw": demand,
            "tariff_components": components, "kwh_per_account": kwh}


def fetch_ses(session) -> dict:
    return parse_ses(session.get(SES_URL, check_robots=False).content)
