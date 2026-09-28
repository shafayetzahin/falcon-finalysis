"""Fictional internally reconciled manufacturer, in full BDT units."""
import pandas as pd
from core.config import FIELDS

DEMO_META = dict(company_name='Apex Consumer Industries Ltd.', industry='Consumer manufacturing',
                 currency='BDT', country='Bangladesh', description='Fictional portfolio demonstration company.')


def demo_company() -> pd.DataFrame:
    """Build five statements with balance-sheet, income, equity and cash roll-forward consistency."""
    rows = []
    cash, equity, debt, ppe = 65.0, 430.0, 240.0, 400.0
    for i, year in enumerate(range(2021, 2026)):
        revenue = [1050, 1176, 1320, 1485, 1670][i]
        cogs = revenue * (0.65 + i * 0.006)
        opex = revenue * 0.17
        depreciation = 30 + i * 3
        ebitda = revenue - cogs - opex
        ebit = ebitda - depreciation
        interest = [18, 22, 28, 35, 43][i]
        ebt = ebit - interest
        tax = ebt * 0.25
        net = ebt - tax
        dividends = net * 0.3
        new_debt = [260, 290, 325, 365, 410][i]
        ocf = [125, 135, 149, 162, 180][i]
        capex = [80, 90, 105, 115, 130][i]
        icf = -capex
        fin = new_debt - debt - dividends
        cash += ocf + icf + fin
        equity += net - dividends
        ppe += capex - depreciation
        ar = revenue * [38, 43, 49, 56, 64][i] / 365
        inventory = cogs * [64, 65, 66, 68, 70][i] / 365
        payable = cogs * 46 / 365
        other_ca, other_cl, other_ncl = 25 + i * 2, 35 + i * 2, 40
        short = new_debt * 0.3
        long = new_debt - short
        ca = cash + ar + inventory + other_ca
        cl = payable + short + other_cl
        liabilities = cl + long + other_ncl
        assets = liabilities + equity
        other_nca = assets - ca - ppe
        row = dict(zip(FIELDS[:11], [revenue, cogs, revenue-cogs, opex, ebitda, depreciation,
                                    ebit, interest, ebt, tax, net]))
        row.update(dict(zip(FIELDS[11:27], [cash, ar, inventory, other_ca, ca, ppe, other_nca, assets,
                                          payable, short, other_cl, cl, long, other_ncl, liabilities, equity])))
        row.update({'Operating Cash Flow': ocf, 'Capital Expenditure': capex, 'Investing Cash Flow': icf,
                    'Financing Cash Flow': fin, 'Cash Dividends': dividends,
                    'Shares Outstanding': 50, 'Weighted Average Shares Outstanding': 50,
                    'Preferred Dividends': 0, 'Retained Earnings': equity - 400,
                    'Cash Interest Paid': interest, 'Cash Taxes Paid': tax, 'FX Effect on Cash': 0})
        row = {k: val * 1_000_000 for k, val in row.items()}
        row.update({'Year': year, 'Market Price Per Share': 24 + i * 2})
        rows.append(row)
        debt = new_debt
    return pd.DataFrame(rows).reindex(columns=['Year'] + FIELDS)
