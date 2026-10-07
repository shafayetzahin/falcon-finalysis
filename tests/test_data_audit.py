"""Independent regression fixtures for data corruption and bounded imports."""
from datetime import date
from io import BytesIO
import json
import re
import zipfile
import requests

import pandas as pd
import pytest
from openpyxl import Workbook

from data.credit_data import normalize_transactions, read_transaction_file, evidence_checks, suggest_transaction_categories
from data.document_import import _amount, _field, extract_workbook
from data.market_data import (
    _modern_dse_history, _annual_metrics, read_price_file, _check_company_ticker,
    _modern_dse_annual_metrics, ticker_catalog, _request, _cse_fields,
)
from data.parsers import numeric_values, read_file


def workbook_bytes(rows):
    book = Workbook()
    for row in rows:
        book.active.append(row)
    stream = BytesIO()
    book.save(stream)
    return stream.getvalue()


def test_cse_profile_checks_identity_and_excludes_structured_table_headers():
    html = '''<div class="com_title">SQUARE PHARMACEUTICALS PLC.</div>
    <div class="com_details col_12"><div><b>Trading Code: </b><b>SQURPHARMA</b></div>
    <div><b>Scrip Code: </b><b>13002</b></div></div>'''
    tables = [pd.DataFrame([['Sector', 'PHARMA & CHEMICALS'], ['Face Value', 10],
                           ['Last Trade Date', '07 October, 2026']]),
              pd.DataFrame([['Sponsor/Director', 'Govt.', 'Institute', 'Foreign', 'Public'],
                            ['As on 31-Aug, 2026', 44.15, 0, 13.9, 41.95]]),
              pd.DataFrame([['Designation', 'Name'], ['Chairman', 'Example']])]
    fields = _cse_fields(html, tables, 'SQURPHARMA')
    assert fields['Company Name'] == 'SQUARE PHARMACEUTICALS PLC.'
    assert fields['Trading Code'] == 'SQURPHARMA'
    assert fields['Last Trade Date'] == '07/10/2026'
    assert fields['Sector'] == 'PHARMA & CHEMICALS'
    assert not {'Govt.', 'Foreign', 'Designation', 'Chairman'} & fields.keys()
    with pytest.raises(ValueError, match='trading code'):
        _cse_fields(html, tables, 'OLYMPIC')


def test_cse_cash_marker_is_not_lost_or_misreported_as_combined_dividend():
    table = pd.DataFrame([
        ['Performance Year', 'Basic EPS Based On', '% Dividend'],
        ['Performance Year', 'Continuous operations', '% Dividend'],
        [2023, 10, '100%C'], [2024, 11, '110%C'], [2025, 12, '120%C'],
    ])
    _, details = _annual_metrics([table], 'official CSE fixture')
    cash = details[details['Exchange metric'].eq('Cash Dividend')]
    assert cash.Value.tolist() == [100., 110., 120.]
    assert not details['Exchange metric'].eq('Dividend').any()


def test_category_suggestions_prioritize_financing_and_do_not_verify_cash_deposits():
    frame = pd.DataFrame({'Description': ['Customer loan received', 'Owner sales transfer',
                                          'Cash deposit', 'Loan installment paid', 'Customer sale'],
                          'Amount': [1000, 2000, 3000, -100, 50],
                          'Category': ['Unreviewed'] * 5})
    result = suggest_transaction_categories(frame)
    assert result.Category.tolist() == ['Loan proceeds', 'Owner / personal transfer',
                                        'Other inflow', 'Debt service', 'Business revenue']


@pytest.mark.parametrize('reader,args', [
    (read_file, ('financial.csv',)),
    (read_price_file, ('prices.csv', 'ABC')),
    (read_transaction_file, ('statement.csv',)),
])
def test_duplicate_csv_headers_are_never_silently_renamed(reader, args):
    with pytest.raises(ValueError, match='unique'):
        reader(b'Date,Amount,Amount\n01/01/2026,100,999\n', *args)


@pytest.mark.parametrize('reader,args,rows', [
    (read_price_file, ('prices.xlsx', 'ABC'), [['Date', 'Close', 'Volume'], ['01/01/2026', '=1+1', 100]]),
    (read_transaction_file, ('statement.xlsx',), [['Date', 'Amount'], ['01/01/2026', '=1+1']]),
])
def test_xlsx_formulas_are_rejected_even_if_cached_values_exist(reader, args, rows):
    with pytest.raises(ValueError, match='Formula'):
        reader(workbook_bytes(rows), *args)


def test_understated_xlsx_dimensions_do_not_hide_rows():
    content = workbook_bytes([['Year', 'Revenue']] + [[2020 + i, i] for i in range(101)])
    altered = BytesIO()
    with zipfile.ZipFile(BytesIO(content)) as source, zipfile.ZipFile(altered, 'w') as target:
        for item in source.infolist():
            payload = source.read(item.filename)
            if item.filename == 'xl/worksheets/sheet1.xml':
                payload = re.sub(rb'<dimension ref="[^"]+"/>', b'<dimension ref="A1:B2"/>', payload)
            target.writestr(item, payload)
    with pytest.raises(ValueError, match='100 rows'):
        read_file(altered.getvalue(), 'financial.xlsx')


def test_scientific_numbers_remain_complete_and_malformed_cells_are_not_prefixes():
    parsed = numeric_values(pd.Series(['1e3', '(1,234.50)', '1,00,000', '10bad', '1,2']))
    assert parsed.iloc[:3].tolist() == [1000, -1234.5, 100000]
    assert parsed.iloc[3:].isna().all()
    with pytest.raises(ValueError, match='valid Date'):
        read_price_file(b'Date,Close,Volume\n01/02/2026,10oops,100\n', 'prices.csv', 'ABC')


def test_portfolio_upload_keeps_separate_companies_and_day_first_dates():
    content = (b'Date,Ticker,Close,Volume,Comment\n03-04-2026,ABC,1e3,100,first\n'
               b'2026/04/03,DEF,200,100,second\n')
    result = read_price_file(content, 'prices.csv', allow_multiple=True)
    assert result.Date.tolist() == [pd.Timestamp('2026-04-03')] * 2
    assert result.Close.tolist() == [1000, 200]
    assert result.Comment.tolist() == ['first', 'second']
    with pytest.raises(ValueError, match='ticker'):
        read_price_file(b'Date,Ticker,Close,Volume\n01/01/2026,,10,100\n', 'prices.csv')


@pytest.mark.parametrize('row,message', [
    ('bad,100', 'valid Date'),
    ('01/01/2026,wrong', 'invalid values'),
    ('01/01/2026,inf', 'finite'),
    ('01/01/2026,', 'valid Date'),
    ('20260101,100', 'valid Date'),
])
def test_invalid_transaction_rows_block_the_whole_import(row, message):
    content = ('Date,Amount\n02/01/2026,200\n' + row + '\n').encode()
    with pytest.raises(ValueError, match=message):
        read_transaction_file(content, 'statement.csv')


@pytest.mark.parametrize('row,message', [
    ('01/01/2026,broken,10', 'invalid values'),
    ('01/01/2026,,', 'missing values'),
    ('01/01/2026,-100,', 'non-negative'),
])
def test_invalid_credit_debit_cells_are_not_assumed_zero(row, message):
    with pytest.raises(ValueError, match=message):
        read_transaction_file(('Date,Credit,Debit\n' + row).encode(), 'statement.csv')


def test_transactions_support_mixed_iso_dates_and_keep_duplicates_for_review():
    raw = pd.DataFrame({'Date': ['2026-01-02', '03/01/2026', '03/01/2026'],
                        'Amount': [100, -20, -20], 'Description': ['Sale', 'Rent', 'Rent']})
    result = normalize_transactions(raw, 'fixture')
    assert result.Date.tolist() == [pd.Timestamp('2026-01-02'), pd.Timestamp('2026-01-03'),
                                    pd.Timestamp('2026-01-03')]
    indicator = evidence_checks(result).set_index('Indicator').loc['Potential duplicate transactions']
    assert indicator['Status'] == 'REVIEW' and indicator['Value'] == '2'


@pytest.mark.parametrize('label,target', [
    ('Total non-current assets', None),
    ('Cash flow from operations', None),
    ('Net cash from operating activities', 'Operating Cash Flow'),
    ('Revenue (Note 12)', 'Revenue'),
    ('Other operating profit', None),
    ('', None),
])
def test_statement_labels_are_not_mapped_by_unsafe_substrings(label, target):
    assert _field(label) == target


@pytest.mark.parametrize('value,result', [('1e3', 1000), ('(12.50)', -12.5),
                                         ('10abc', None), ('2.5 million', None), ('inf', None)])
def test_document_amounts_are_not_corrupted_by_removing_letters(value, result):
    assert _amount(value) == result


def test_statement_extraction_reads_multiple_sections_and_reports_conflicts():
    payload = workbook_bytes([
        ['Metric', 2023, 2024], ['Revenue', 100, 120], ['Revenue', 105, 125],
        ['Metric', 2025, 2026], ['Revenue', 140, 160],
        ['Total non-current assets', 1000, 1200],
    ])
    result = extract_workbook(payload, 'report.xlsx')
    assert result.frame.Year.tolist() == [2023, 2024, 2025, 2026]
    assert result.frame.Revenue.tolist() == [100, 120, 140, 160]
    assert result.frame['Total Current Assets'].isna().all()
    assert any('differed' in note for note in result.notes)


def test_history_previous_close_is_computed_after_chronological_sorting():
    series = [
        {'date': '2026-09-03', 'price': '13', 'open': 12, 'high': 13, 'low': 12, 'trades': 1, 'volume': 100},
        {'date': '2026-09-01', 'price': '11', 'open': 10, 'high': 11, 'low': 10, 'trades': 1, 'volume': 100},
        {'date': '2026-09-02', 'price': '12', 'open': 11, 'high': 12, 'low': 11, 'trades': 1, 'volume': 100},
    ]
    encoded = json.dumps(series).replace('"', r'\"')
    html = r'\"series\":' + encoded + r',\"suggestedCode\":null'
    result = _modern_dse_history(html, 'ABC', date(2026, 9, 2), date(2026, 9, 3))
    assert result.Close.tolist() == [12, 13]
    assert result['Previous Close'].tolist() == [11, 12]


def test_mismatched_exchange_company_is_never_accepted():
    with pytest.raises(ValueError, match='different company'):
        _check_company_ticker({'code': 'OTHER'}, 'ABC')
    with pytest.raises(ValueError, match='DSE or CSE'):
        ticker_catalog('INVALID')


def test_reported_zero_annual_metrics_are_valid_and_modern_missing_values_are_ignored():
    table = pd.DataFrame([['Year', 'Net Profit After Tax(mn)'], [2023, 0], [2024, 1], [2025, 2]])
    frame, _ = _annual_metrics([table], 'fixture')
    assert frame['Net Income'].tolist() == [0, 1_000_000, 2_000_000]
    modern, details = _modern_dse_annual_metrics({'multiYearFinancials': [
        {'year': 2025, 'profitForYear': '1e3', 'epsBasic': '$undefined', 'nav': 'inf'}],
        'dividendHistory': [{'year': 2025, 'cash': '$undefined', 'stock': 5}]}, 'fixture')
    assert modern['Net Income'].tolist() == [1_000_000_000]
    assert details['Exchange metric'].tolist() == ['Net Income', 'Stock Dividend']


def test_exchange_download_limit_is_enforced_during_streaming(monkeypatch):
    response = requests.Response()
    response.status_code = 200
    response.url = 'https://exchange.example/company'
    yielded = []
    closed = []
    def chunks(chunk_size):
        for chunk in [b'1234', b'5678', b'never-read']:
            yielded.append(chunk)
            yield chunk
    monkeypatch.setattr(response, 'iter_content', chunks)
    monkeypatch.setattr(response, 'close', lambda: closed.append(True))
    monkeypatch.setattr('data.market_data.requests.request', lambda *args, **kwargs: response)
    monkeypatch.setattr('data.market_data.MAX_RESPONSE', 5)
    with pytest.raises(ValueError, match='more data'):
        _request('GET', response.url)
    assert yielded == [b'1234', b'5678']
    assert closed == [True]
