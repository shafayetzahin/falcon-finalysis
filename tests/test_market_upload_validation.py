"""Protect uploads against silent company/date/value corruption."""
import pandas as pd
import pytest

from data.market_data import read_price_file


def test_mixed_company_upload_filters_ticker_and_uses_day_first_dates():
    payload = b'Date,Ticker,Close,Volume\n03/04/2026, abc ,10,100\n2026-04-04,OTHER,99,400\n'
    result = read_price_file(payload, 'prices.csv', 'ABC')
    assert len(result) == 1
    assert result.iloc[0].Date == pd.Timestamp('2026-04-03')
    assert result.iloc[0].Close == 10
    with pytest.raises(ValueError, match='no rows'):
        read_price_file(payload, 'prices.csv', 'MISSING')
    with pytest.raises(ValueError, match='multiple companies'):
        read_price_file(payload, 'prices.csv')


@pytest.mark.parametrize('rows,message', [
    ('bad,10,100', 'valid Date'),
    ('2026-01-01,,100', 'valid Date'),
    ('2026-01-01,10,', 'valid Date'),
    ('2026-01-01,0,100', 'positive'),
    ('2026-01-01,10,-1', 'positive'),
    ('2026-01-01,inf,100', 'invalid'),
    ('2026-01-01,10,100\n2026-01-01,11,100', 'Duplicate'),
])
def test_invalid_prices_are_rejected_without_silently_dropping_rows(rows, message):
    with pytest.raises(ValueError, match=message):
        read_price_file(('Date,Close,Volume\n' + rows).encode(), 'prices.csv', 'ABC')


def test_price_upload_rejects_truncation_and_duplicate_aliases():
    with pytest.raises(ValueError, match='5,000'):
        read_price_file(('Date,Close,Volume\n' + '2026-01-01,10,100\n' * 5001).encode(),
                        'prices.csv', 'ABC')
    with pytest.raises(ValueError, match='Multiple columns'):
        read_price_file(b'Date,Close,ClosePrice,Volume\n2026-01-01,10,11,100', 'prices.csv', 'ABC')
