"""Central financial schema and policy constants."""

INCOME = ['Revenue', 'COGS', 'Gross Profit', 'Operating Expenses', 'EBITDA', 'Depreciation',
          'EBIT', 'Interest Expense', 'EBT', 'Tax Expense', 'Net Income']
BALANCE = ['Cash', 'Accounts Receivable', 'Inventory', 'Other Current Assets', 'Total Current Assets',
           'Property Plant Equipment', 'Other Non-Current Assets', 'Total Assets', 'Accounts Payable',
           'Short-Term Debt', 'Other Current Liabilities', 'Total Current Liabilities', 'Long-Term Debt',
           'Other Non-Current Liabilities', 'Total Liabilities', 'Shareholders Equity']
CASH_FLOW = ['Operating Cash Flow', 'Capital Expenditure', 'Investing Cash Flow',
             'Financing Cash Flow', 'Cash Dividends']
OPTIONAL = ['Shares Outstanding', 'Weighted Average Shares Outstanding', 'Market Price Per Share',
            'Preferred Dividends', 'Retained Earnings', 'Cash Interest Paid', 'Cash Taxes Paid',
            'FX Effect on Cash']
FIELDS = INCOME + BALANCE + CASH_FLOW + OPTIONAL
CURRENCIES = {'BDT': '৳', 'USD': '$', 'EUR': '€', 'GBP': '£', 'INR': '₹'}
DISCLAIMER = ('Falcon Finalysis is an analytical and educational decision-support tool. Outputs depend on the '
              'accuracy and completeness of uploaded financial information. Results are not investment, '
              'lending, accounting, audit, tax, or legal advice.')
GUIDELINE = 'General analytical guideline; appropriate benchmarks vary by industry.'
AVERAGE_POLICY = ('First-year average-balance ratios use ending balances because opening balances are unavailable. '
                  'Later years use the mean of consecutive opening and closing balances. '
                  'Revenue proxies credit sales; COGS proxies purchases. Full fiscal years use 365 days.')
ALIASES = {
    'Year': ['fiscal year', 'fy', 'period'],
    'Revenue': ['sales', 'net sales', 'turnover', 'operating revenue', 'revenue from contracts with customers'],
    'Gross Profit': ['gross profit', 'gross operating profit'],
    'Operating Expenses': ['operating expenses', 'administrative and selling expenses', 'selling and distribution expenses'],
    'EBITDA': ['earnings before interest tax depreciation and amortization'],
    'Depreciation': ['depreciation and amortization', 'depreciation expense'],
    'Accounts Receivable': ['trade receivables', 'receivables', 'debtors'],
    'Accounts Payable': ['trade payables', 'payables', 'creditors'],
    'COGS': ['cost of sales', 'cost of goods sold'],
    'Shareholders Equity': ['equity', 'total equity', "shareholders equity", "stockholders equity"],
    'Total Current Assets': ['current assets'],
    'Total Current Liabilities': ['current liabilities'],
    'Net Income': ['net profit', 'profit after tax', 'profit for the year', 'profit for the period'],
    'EBIT': ['operating profit', 'operating income', 'profit from operations'],
    'Interest Expense': ['finance cost', 'finance costs', 'interest and finance charges'],
    'EBT': ['profit before tax', 'profit before income tax'],
    'Tax Expense': ['income tax expense', 'taxation'],
    'Capital Expenditure': ['capex'],
    'Property Plant Equipment': ['ppe', 'property plant and equipment'],
    'Operating Cash Flow': ['ocf', 'cash from operations'],
    'Investing Cash Flow': ['net cash used in investing activities', 'net cash from investing activities'],
    'Financing Cash Flow': ['net cash used in financing activities', 'net cash from financing activities'],
    'Cash Dividends': ['dividend paid', 'dividends paid'],
    'Cash': ['cash and cash equivalents', 'cash at bank and in hand'],
    'Inventory': ['inventories', 'stocks'],
    'Long-Term Debt': ['long term borrowings', 'non current borrowings'],
    'Short-Term Debt': ['short term borrowings', 'current borrowings'],
    'Total Assets': ['total assets'],
    'Total Liabilities': ['total liabilities'],
    'Retained Earnings': ['retained earnings', 'revenue reserve'],
}
