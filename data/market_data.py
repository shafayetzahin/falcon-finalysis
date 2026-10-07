"""Small, bounded adapters for official DSE and CSE public web pages.

The exchanges do not publish a stable public API for these views.  Keep parsing
isolated here so a layout change produces a clear error instead of bad data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
import json
from pathlib import Path
import re
import ssl
from lxml import html as lxml_html
import numpy as np

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from core.config import FIELDS
from data.parsers import numeric_values, parse_date, read_tabular


# DSE's redesigned site moved the original company and archive views to the
# official legacy host. The former www.dsebd.org routes now return HTTP 410.
DSE = "https://old.dsebd.org"
DSE_CURRENT = "https://www.dse.com.bd"
CSE = "https://www.cse.com.bd"
HEADERS = {"User-Agent": "Falcon Finalysis/1.1 (local educational analytics; contact: local-user)"}
MAX_RESPONSE = 8 * 1024 * 1024
TICKER_RE = re.compile(r"^[A-Z0-9&()._-]{1,24}$")
BUNDLED_TICKERS = Path(__file__).with_name("tickers.json")
CERTIFICATES = Path(__file__).with_name("certificates")
EXCHANGE_INTERMEDIATES = {
    "old.dsebd.org": CERTIFICATES / "sectigo-dv-r36.pem",
    "www.cse.com.bd": CERTIFICATES / "globalsign-r3-dv-2020.pem",
}


class _VerifiedExchangeAdapter(HTTPAdapter):
    """Supply a published intermediate omitted by an exchange web server."""

    def __init__(self, certificate: Path):
        context = ssl.create_default_context(cafile=str(certificate))
        # These files are CA intermediates rather than self-signed roots. OpenSSL
        # still validates the server signature, dates and hostname before using
        # the selected intermediate as this host-scoped chain's trust anchor.
        context.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
        self._ssl_context = context
        super().__init__()

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._ssl_context
        return super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._ssl_context
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def _verified_exchange_session(url: str, session: requests.Session | None = None) -> requests.Session | None:
    """Return a verified session only when the named exchange omits its CA chain."""
    for host, certificate in EXCHANGE_INTERMEDIATES.items():
        prefix = f"https://{host}/"
        if url.startswith(prefix):
            session = session or requests.Session()
            session.mount(prefix, _VerifiedExchangeAdapter(certificate))
            return session
    return None


@dataclass(frozen=True)
class CompanySnapshot:
    exchange: str
    ticker: str
    company_name: str
    fields: dict[str, str]
    source_url: str
    fetched_at: str


@dataclass(frozen=True)
class ExchangeFinancials:
    frame: pd.DataFrame
    details: pd.DataFrame
    source_url: str
    fetched_at: str


def _ticker(value: str) -> str:
    value = str(value).strip().upper()
    if not TICKER_RE.fullmatch(value):
        raise ValueError("Use a valid exchange ticker (letters, numbers, &, dot, dash or parentheses).")
    return value


def _dates(start: date, end: date) -> tuple[str, str]:
    if start > end:
        raise ValueError("Start date must be on or before end date.")
    if (end - start).days > 731:
        raise ValueError("Choose a period of two years or less. DSE's public archive is limited to two years.")
    if end > date.today():
        raise ValueError("End date cannot be in the future.")
    return start.isoformat(), end.isoformat()


def _request(method: str, url: str, session: requests.Session | None = None, **kwargs) -> requests.Response:
    owned_session = session is None
    response = None
    try:
        session = _verified_exchange_session(url, session) or session
        caller = session.request if session else requests.request
        request_headers = {**HEADERS, **kwargs.pop("headers", {})}
        response = caller(method, url, headers=request_headers, timeout=(8, 30), stream=True, **kwargs)
        response.raise_for_status()
        chunks, size = [], 0
        for chunk in response.iter_content(chunk_size=64 * 1024):
            size += len(chunk)
            if size > MAX_RESPONSE:
                raise ValueError("The exchange returned more data than Falcon Finalysis can safely process at once.")
            chunks.append(chunk)
        response._content = b"".join(chunks)
        response._content_consumed = True
        return response
    except requests.exceptions.SSLError as exc:
        raise ValueError("Secure connection to the exchange failed. Check the computer's date and trusted certificates, then retry.") from exc
    except requests.RequestException as exc:
        raise ValueError("The exchange site is unavailable or rejected the request. Retry later or use the spreadsheet upload fallback.") from exc
    finally:
        if response is not None:
            response.close()
        if owned_session and session is not None:
            session.close()


def ticker_catalog(exchange: str) -> dict[str, str]:
    """Return official ticker codes mapped to exchange-provided company names."""
    exchange = exchange.upper()
    if exchange not in {"DSE", "CSE"}:
        raise ValueError("Exchange must be DSE or CSE.")
    url = f"{DSE}/data_archive.php" if exchange == "DSE" else f"{CSE}/market/marketprice"
    html = _request("GET", url).text
    options = re.findall(r"<option[^>]+value=[\"']([^\"']+)[\"'][^>]*>(.*?)</option>", html, re.I | re.S)
    catalog = {}
    for raw_value, raw_label in options:
        ticker = raw_value.split("|", 1)[0].strip().upper()
        if not TICKER_RE.fullmatch(ticker):
            continue
        label = re.sub(r"<[^>]+>", "", raw_label).strip()
        name = label.split("|", 1)[1].strip() if "|" in label else ""
        catalog[ticker] = name
    if not catalog:
        raise ValueError(f"{exchange} did not return its ticker list. Enter a ticker manually or retry later.")
    return dict(sorted(catalog.items()))


def ticker_list(exchange: str) -> list[str]:
    return list(ticker_catalog(exchange))


def bundled_ticker_list(exchange: str) -> list[str]:
    """Return the packaged ticker snapshot for instant, offline suggestions."""
    try:
        payload = json.loads(BUNDLED_TICKERS.read_text(encoding="utf-8"))
        values = payload.get("exchanges", {}).get(exchange.upper(), [])
    except (OSError, ValueError, TypeError):
        return []
    return sorted({str(value).strip().upper() for value in values
                   if TICKER_RE.fullmatch(str(value).strip().upper())})


def bundled_ticker_catalog(exchange: str) -> dict[str, str]:
    """Return packaged ticker/name pairs; old list-only snapshots remain supported."""
    try:
        payload = json.loads(BUNDLED_TICKERS.read_text(encoding="utf-8"))
        values = payload.get("companies", {}).get(exchange.upper())
        if isinstance(values, dict):
            return {str(ticker).upper(): str(name) for ticker, name in values.items()
                    if TICKER_RE.fullmatch(str(ticker).upper())}
    except (OSError, ValueError, TypeError):
        pass
    return {ticker: "" for ticker in bundled_ticker_list(exchange)}


def _tables(html: str) -> list[pd.DataFrame]:
    try:
        return pd.read_html(StringIO(html))
    except (ValueError, ImportError) as exc:
        raise ValueError("The exchange page format could not be read. Use the upload fallback while the connector is updated.") from exc


def _pairs(tables: list[pd.DataFrame]) -> dict[str, str]:
    fields: dict[str, str] = {}
    for table in tables:
        if table.shape[1] > 12 or table.shape[0] > 40:
            continue
        for row in table.itertuples(index=False, name=None):
            values = [str(x).strip() if pd.notna(x) else "" for x in row]
            for index in range(0, len(values) - 1, 2):
                key, value = values[index:index + 2]
                if (key and value and re.search(r"[A-Za-z]", key) and key.lower() != value.lower()
                        and len(key) <= 80 and len(value) <= 200):
                    fields.setdefault(key, value)
    return fields


def _cse_fields(html: str, tables: list[pd.DataFrame], ticker: str) -> dict[str, str]:
    """Read verified CSE identity and scalar fields; exclude structured tables."""
    page = lxml_html.fromstring(html)
    title = page.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' com_title ')]")
    details = page.xpath("//*[contains(concat(' ', normalize-space(@class), ' '), ' com_details ')]//b")
    identity = {}
    for index, element in enumerate(details[:-1]):
        label = element.text_content().strip().rstrip(':').strip()
        if label in {'Trading Code', 'Scrip Code'}:
            identity[label] = details[index + 1].text_content().strip()
    if identity.get('Trading Code', '').upper() != ticker:
        raise ValueError('CSE did not confirm the requested trading code. Retry or use the upload fallback.')
    name = title[0].text_content().strip() if title else ''
    if not name:
        raise ValueError('CSE did not include a readable company name.')
    allowed = {
        'Last Trade Price (LTP)', 'Last Trade Date', 'Change', 'Open Price', "Day's Range",
        'Total Trade', 'Total Volume', 'Close Price', 'Yesterday Close Price',
        'Market Capital in BDT (mn)', 'Authorized Capital in BDT* (mn)',
        'Paid-up Capital in BDT* (mn)', 'Face Value', 'Paid up Share', 'Market Lot',
        'Sector', 'Market Category', 'Listing Year', 'AGM Date', 'Record Date',
        'Dividend(%)', 'Bonus Issue', 'HY Net Turnover(mn)', 'HY Net Profit after tax(mn)',
        'HY EPS', 'Year End', 'Financial Year End',
    }
    fields = {'Company Name': name, **identity}
    for key, value in _pairs(tables).items():
        label = key.strip().rstrip(':').strip()
        if label in allowed:
            fields[label] = _display_date(value) if label in {'Last Trade Date', 'AGM Date', 'Record Date'} else value
    return fields


def _modern_dse_company(html: str) -> dict:
    """Decode the official current DSE page's server-rendered company object."""
    match = re.search(r'\\"company\\":(\{.*?\}),\\"series\\":', html, re.S)
    if not match:
        raise ValueError("DSE's current company page did not include readable company details.")
    try:
        company = json.loads(json.loads(f'"{match.group(1)}"'))
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("DSE's current company page returned unreadable company details.") from exc
    if not isinstance(company, dict) or not company.get("code") or not company.get("name"):
        raise ValueError("DSE's current company page did not include the expected company fields.")
    return company


def _display_number(value: object, scale: float = 1.0) -> str:
    if value is None or value == "$undefined":
        return ""
    try:
        number = float(value) / scale
    except (TypeError, ValueError):
        return str(value)
    return f"{number:,.2f}" if np.isfinite(number) else ""


def _display_date(value: object, include_time: bool = False) -> str:
    text = str(value or "").strip()
    for pattern in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d-%m-%Y", "%d %B, %Y", "%d %b, %Y"):
        try:
            parsed = datetime.strptime(text, pattern)
            return parsed.strftime("%d/%m/%Y %H:%M:%S" if include_time and "%H" in pattern
                                   else "%d/%m/%Y")
        except ValueError:
            continue
    return text


def _modern_dse_fields(company: dict) -> dict[str, str]:
    """Present current DSE values with explicit units and without invented values."""
    fields = {
        "Company Name": str(company.get("name", "")),
        "Trading Code": str(company.get("code", "")),
        "Sector": str(company.get("sector", "")),
        "Board": str(company.get("board", "")),
        "Category": str(company.get("category", "")),
        "Instrument Type": str(company.get("instrumentType", "")),
        "Listing Year": str(company.get("listingYear", "")),
        "Operational Status": str(company.get("operationalStatus", "")),
        "Scrip Code": str(company.get("scripCode", "")),
        "Last Price (BDT)": _display_number(company.get("price")),
        "Previous Close (BDT)": _display_number(company.get("prevClose")),
        "Open (BDT)": _display_number(company.get("open")),
        "High (BDT)": _display_number(company.get("high")),
        "Low (BDT)": _display_number(company.get("low")),
        "Volume": _display_number(company.get("volume")),
        "Trades": _display_number(company.get("trades")),
        "Market Capitalization (BDT mn)": _display_number(company.get("marketCap"), 1_000_000),
        "P/E": _display_number(company.get("pe")),
        "EPS (BDT/share)": _display_number(company.get("eps")),
        "Dividend Yield (%)": _display_number(company.get("dividendYield")),
        "NAV per Share (BDT)": _display_number(company.get("nav")),
        "52-week High (BDT)": _display_number(company.get("weekHigh52")),
        "52-week Low (BDT)": _display_number(company.get("weekLow52")),
        "Face Value (BDT)": _display_number(company.get("faceValue")),
        "Paid-up Capital (BDT mn)": _display_number(company.get("paidUpCapital"), 1_000_000),
        "Authorized Capital (BDT mn)": _display_number(company.get("authorizedCapital")),
        "Free Float (%)": _display_number(company.get("freeFloat")),
        "Market Lot": _display_number(company.get("marketLot")),
        "Financial Year End": str(company.get("yearEnd", "")),
        "AGM Date": _display_date(company.get("agmDate")),
        "Last Price Update": _display_date(company.get("lastPriceUpdate"), include_time=True),
        "Data As of": _display_date(company.get("asOfDate")),
        "Registered Office": str(company.get("registeredOffice", "")),
        "Website": str(company.get("website", "")),
        "Email": str(company.get("email", "")),
    }
    return {key: value for key, value in fields.items()
            if value and value not in {"None", "$undefined"}}


def company_snapshot(exchange: str, ticker: str) -> CompanySnapshot:
    exchange, ticker = exchange.upper(), _ticker(ticker)
    if exchange == "DSE":
        current_url = f"{DSE_CURRENT}/company/{ticker}"
        try:
            response = _request("GET", current_url)
            company = _modern_dse_company(response.text)
            _check_company_ticker(company, ticker)
            fields = _modern_dse_fields(company)
            return CompanySnapshot(exchange, ticker, str(company["name"]), fields, response.url,
                                   datetime.now(timezone.utc).replace(microsecond=0).isoformat())
        except ValueError:
            url = f"{DSE}/displayCompany.php?name={ticker}"
    elif exchange == "CSE":
        url = f"{CSE}/company/companydetails/{ticker}"
    else:
        raise ValueError("Exchange must be DSE or CSE.")
    html = _request("GET", url).text
    tables = _tables(html)
    fields = _cse_fields(html, tables, ticker) if exchange == 'CSE' else _pairs(tables)
    if not fields:
        raise ValueError(f"No company details were found for {ticker} on {exchange}.")
    heading = re.search(r"Company Name:\s*<i>(.*?)</i>", html, re.I | re.S)
    clean_heading = re.sub(r"<[^>]+>", "", heading.group(1)).strip() if heading else ""
    name = next((v for k, v in fields.items() if "company name" in k.lower()), clean_heading or ticker)
    return CompanySnapshot(exchange, ticker, name, fields, url,
                           datetime.now(timezone.utc).replace(microsecond=0).isoformat())


def _year(value: object) -> int | None:
    match = re.fullmatch(r"(?:19|20)\d{2}", str(value).strip())
    return int(match.group()) if match else None


def _check_company_ticker(company: dict, ticker: str) -> None:
    if str(company.get("code", "")).strip().upper() != ticker:
        raise ValueError("The exchange returned a different company. Retry or use the upload fallback.")


def _annual_metrics(tables: list[pd.DataFrame], source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read explicitly reported annual market metrics without deriving missing statements."""
    observations: list[dict] = []
    patterns = [
        ("Net Income", "BDT million", ("profit for the year (mn)", "net profit after tax(mn)")),
        ("Basic EPS", "BDT/share", ("continuing operations basic original", "basic eps based on continuous operations")),
        ("NAV per Share", "BDT/share", ("nav per share original", "net asset value per share")),
        ("Dividend", "%", ("dividend in %", "% dividend")),
        ("Dividend Yield", "%", ("dividend yield in %", "% dividend yield")),
    ]
    for table in tables:
        year_rows = [i for i in range(len(table)) if _year(table.iloc[i, 0])]
        if len(year_rows) < 3:
            continue
        first = year_rows[0]
        headers = []
        for col in range(table.shape[1]):
            parts = [str(x).strip() for x in table.iloc[:first, col] if pd.notna(x)]
            headers.append(" ".join(dict.fromkeys(parts)).lower())
        for metric, unit, alternatives in patterns:
            columns = [i for i, heading in enumerate(headers) if any(p in heading for p in alternatives)]
            if not columns:
                continue
            for row_i in year_rows:
                year = _year(table.iloc[row_i, 0])
                selected = None
                for col_i in columns:
                    cell = table.iloc[row_i, col_i]
                    if metric == 'Dividend' and isinstance(cell, str):
                        marked = re.fullmatch(r'\s*(\d+(?:\.\d+)?)\s*%\s*([CB])\s*', cell, re.I)
                        if marked:
                            observations.append({
                                'Year': year,
                                'Exchange metric': 'Cash Dividend' if marked[2].upper() == 'C' else 'Stock Dividend',
                                'Value': float(marked[1]), 'Unit': '%', 'Source': source})
                            break
                    if unit == "%" and isinstance(cell, str):
                        cell = cell.strip().removesuffix("%").strip()
                    value = _number(pd.Series([cell])).iloc[0]
                    if pd.notna(value) and np.isfinite(value):
                        selected = float(value)
                        break
                if selected is not None:
                    observations.append({"Year": year, "Exchange metric": metric, "Value": selected,
                                         "Unit": unit, "Source": source})
    if not observations:
        raise ValueError("The exchange did not return a readable annual financial-performance table for this ticker.")
    details = (pd.DataFrame(observations).drop_duplicates(["Year", "Exchange metric"])
               .sort_values(["Year", "Exchange metric"]).reset_index(drop=True))
    records = []
    for year in sorted(details.Year.unique()):
        row = {"Year": int(year)}
        profit = details[(details.Year == year) & (details["Exchange metric"] == "Net Income")]
        if not profit.empty:
            row["Net Income"] = float(profit.iloc[0].Value) * 1_000_000
        records.append(row)
    frame = pd.DataFrame(records).reindex(columns=["Year"] + FIELDS)
    return frame, details


def _modern_dse_annual_metrics(company: dict, source: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Convert directly reported current-site annual metrics to the existing review table."""
    observations: list[dict] = []
    dividend_history = company.get("dividendHistory", []) or []
    annual_history = company.get("multiYearFinancials", []) or []
    if not isinstance(dividend_history, list) or not isinstance(annual_history, list):
        raise ValueError("DSE's current company page returned an unexpected annual financial layout.")
    dividends = {int(item["year"]): item for item in dividend_history
                 if isinstance(item, dict) and _year(item.get("year"))}
    for item in annual_history:
        if not isinstance(item, dict) or not (year := _year(item.get("year"))):
            continue
        metrics = [
            ("Net Income", "BDT million", item.get("profitForYear", item.get("profit"))),
            ("Basic EPS", "BDT/share", item.get("epsContBasicOriginal", item.get("epsBasic"))),
            ("NAV per Share", "BDT/share", item.get("navOriginal", item.get("nav"))),
        ]
        dividend = dividends.get(year)
        if dividend:
            cash = _number(pd.Series([dividend.get("cash")])).iloc[0]
            stock = _number(pd.Series([dividend.get("stock")])).iloc[0]
            if pd.notna(cash):
                metrics.append(("Cash Dividend", "%", cash))
            if pd.notna(stock):
                metrics.append(("Stock Dividend", "%", stock))
            if pd.notna(cash) and pd.notna(stock):
                metrics.append(("Dividend", "%", cash + stock))
            metrics.append(("Dividend Yield", "%", dividend.get("yieldPct")))
        for metric, unit, value in metrics:
            value = _number(pd.Series([value])).iloc[0]
            if pd.notna(value) and np.isfinite(value):
                observations.append({"Year": year, "Exchange metric": metric,
                                     "Value": float(value), "Unit": unit, "Source": source})
    if not observations:
        raise ValueError("DSE's current company page did not include readable annual financial metrics.")
    details = (pd.DataFrame(observations).drop_duplicates(["Year", "Exchange metric"])
               .sort_values(["Year", "Exchange metric"]).reset_index(drop=True))
    records = []
    for year in sorted(details.Year.unique()):
        row = {"Year": int(year)}
        profit = details[(details.Year == year) & (details["Exchange metric"] == "Net Income")]
        if not profit.empty:
            row["Net Income"] = float(profit.iloc[0].Value) * 1_000_000
        records.append(row)
    return pd.DataFrame(records).reindex(columns=["Year"] + FIELDS), details


def exchange_financials(exchange: str, ticker: str) -> ExchangeFinancials:
    exchange, ticker = exchange.upper(), _ticker(ticker)
    if exchange == "DSE":
        current_url = f"{DSE_CURRENT}/company/{ticker}"
        try:
            response = _request("GET", current_url)
            company = _modern_dse_company(response.text)
            _check_company_ticker(company, ticker)
            frame, details = _modern_dse_annual_metrics(
                company, response.url)
            return ExchangeFinancials(frame.tail(10).reset_index(drop=True), details, response.url,
                                      datetime.now(timezone.utc).replace(microsecond=0).isoformat())
        except ValueError:
            url = f"{DSE}/displayCompany.php?name={ticker}"
    else:
        url = f"{CSE}/company/companydetails/{ticker}" if exchange == "CSE" else ""
    if not url:
        raise ValueError("Exchange must be DSE or CSE.")
    response = _request("GET", url)
    if exchange == 'CSE':
        _cse_fields(response.text, _tables(response.text), ticker)
    frame, details = _annual_metrics(_tables(response.text), url)
    return ExchangeFinancials(frame.tail(10).reset_index(drop=True), details, url,
                              datetime.now(timezone.utc).replace(microsecond=0).isoformat())


def _number(series: pd.Series) -> pd.Series:
    return numeric_values(series)


def _price_date(value: object) -> pd.Timestamp:
    """Read daily dates explicitly; arbitrary numeric values are not timestamps."""
    return parse_date(value)


def _standardize_dse(table: pd.DataFrame, ticker: str) -> pd.DataFrame:
    rename = {"DATE": "Date", "TRADING CODE": "Ticker", "OPENP*": "Open", "HIGH": "High",
              "LOW": "Low", "CLOSEP*": "Close", "LTP*": "LTP", "YCP": "Previous Close",
              "TRADE": "Trades", "VALUE (MN)": "Value (mn)", "VOLUME": "Volume"}
    table.columns = [str(c).strip().upper() for c in table.columns]
    if not {"DATE", "TRADING CODE", "CLOSEP*", "VOLUME"}.issubset(table.columns):
        raise ValueError("DSE returned a page, but its price table format has changed.")
    out = table.rename(columns=rename)[[v for k, v in rename.items() if k in table]].copy()
    out["Date"] = out["Date"].map(_price_date)
    out = out[out["Ticker"].astype(str).str.upper().eq(ticker)]
    for col in out.columns.difference(["Date", "Ticker"]):
        out[col] = _number(out[col])
    return out.sort_values("Date").reset_index(drop=True)


def _modern_dse_history(html: str, ticker: str, start: date, end: date) -> pd.DataFrame:
    """Read the official current DSE company page's server-rendered price series."""
    if r'\"company\":' in html:
        _check_company_ticker(_modern_dse_company(html), ticker)
    match = re.search(r'\\"series\\":(\[.*?\]),\\"suggestedCode\\"', html, re.S)
    if not match:
        raise ValueError("DSE's current company page did not include a readable price series.")
    try:
        payload = json.loads(json.loads(f'"{match.group(1)}"'))
        raw = pd.DataFrame(payload)
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        raise ValueError("DSE's current company page returned an unreadable price series.") from exc
    required = {"date", "price", "open", "high", "low", "trades", "volume"}
    if raw.empty or not required.issubset(raw.columns):
        raise ValueError("DSE's current company page did not include the expected price fields.")
    out = raw.rename(columns={"date": "Date", "price": "Close", "open": "Open",
                              "high": "High", "low": "Low", "trades": "Trades",
                              "volume": "Volume"})
    out["Date"] = out["Date"].map(_price_date)
    if out["Date"].isna().any():
        raise ValueError("DSE returned invalid dates in its price series.")
    for column in ["Close", "Open", "High", "Low", "Trades", "Volume"]:
        out[column] = _number(out[column])
    out = out.sort_values("Date").reset_index(drop=True)
    out["Ticker"] = ticker
    out["LTP"] = out["Close"]
    out["Previous Close"] = out["Close"].shift(1)
    out["Value (mn)"] = pd.NA
    columns = ["Date", "Ticker", "Open", "High", "Low", "Close", "LTP",
               "Previous Close", "Trades", "Value (mn)", "Volume"]
    out = out[columns]
    mask = out["Date"].dt.date.between(start, end)
    return out.loc[mask].sort_values("Date").reset_index(drop=True)


def _standardize_cse(table: pd.DataFrame, ticker: str) -> pd.DataFrame:
    table.columns = [str(c).strip().upper() for c in table.columns]
    required = {"DATE", "CODE", "CLOSE PRICE", "VOLUME"}
    if not required.issubset(table.columns):
        raise ValueError("CSE returned a page, but its price table format has changed.")
    rename = {"DATE": "Date", "CODE": "Ticker", "CLOSE PRICE": "Close", "VOLUME": "Volume",
              "TURNOVER": "Turnover", "NUMBER OF TRADE": "Trades", "COMPANY": "Company"}
    out = table.rename(columns=rename)[[rename[c] for c in rename if c in table.columns]].copy()
    out["Date"] = out["Date"].map(_price_date)
    out = out[out["Ticker"].astype(str).str.upper().eq(ticker)]
    for col in out.columns.difference(["Date", "Ticker", "Company"]):
        out[col] = _number(out[col])
    return out.sort_values("Date").reset_index(drop=True)


def price_history(exchange: str, ticker: str, start: date, end: date) -> tuple[pd.DataFrame, str]:
    exchange, ticker = exchange.upper(), _ticker(ticker)
    start_text, end_text = _dates(start, end)
    if exchange == "DSE":
        current_url = f"{DSE_CURRENT}/company/{ticker}"
        current_error = None
        try:
            current = _request("GET", current_url)
            frame = _modern_dse_history(current.text, ticker, start, end)
            source = current.url
        except ValueError as exc:
            current_error = exc
            frame = pd.DataFrame()
        if frame.empty:
            url = f"{DSE}/day_end_archive.php"
            params = {"startDate": start_text, "endDate": end_text, "inst": ticker, "archive": "data"}
            try:
                response = _request("GET", url, params=params)
                candidates = [t for t in _tables(response.text) if {"DATE", "TRADING CODE", "CLOSEP*", "VOLUME"}.issubset({str(c).strip().upper() for c in t.columns})]
                if not candidates:
                    raise ValueError("DSE returned no matching price table for this ticker and period.")
                frame = _standardize_dse(candidates[-1], ticker)
                source = response.url
            except ValueError:
                if current_error:
                    raise current_error
                raise
    elif exchange == "CSE":
        url = f"{CSE}/market/marketprice"
        session = requests.Session()
        landing = _request("GET", url, session=session)
        token = re.search(r'name=["\']csrf_cse_token["\'][^>]+value=["\']([^"\']+)', landing.text, re.I)
        if not token:
            raise ValueError("CSE did not provide the security token needed for a history request.")
        payload = {"pe_date": start_text, "af_date": end_text, "keyword": ticker,
                   "csrf_cse_token": token.group(1), "Go": ""}
        response = _request("POST", url, session=session, data=payload,
                            headers={**HEADERS, "Referer": url})
        candidates = [t for t in _tables(response.text) if {"DATE", "CODE", "CLOSE PRICE", "VOLUME"}.issubset({str(c).strip().upper() for c in t.columns})]
        if not candidates:
            raise ValueError("CSE returned no matching price table for this ticker and period.")
        frame = _standardize_cse(candidates[-1], ticker)
        source = url
    else:
        raise ValueError("Exchange must be DSE or CSE.")
    if frame.empty:
        raise ValueError("No trading records were found for this ticker and period.")
    if frame["Date"].isna().any():
        raise ValueError("The exchange returned invalid price dates. Use the upload fallback.")
    frame = frame.loc[frame["Date"].dt.date.between(start, end)].copy()
    if frame.empty:
        raise ValueError("No trading records were found for this ticker and period.")
    _validate_prices(frame)
    return frame, source


def _validate_prices(frame: pd.DataFrame) -> None:
    if frame[["Date", "Close", "Volume"]].isna().any().any():
        raise ValueError("Every price row needs a valid Date, Close and Volume. Correct the missing or invalid values.")
    if ((frame["Close"] <= 0) | (frame["Volume"] < 0)
            | ~np.isfinite(frame[["Close", "Volume"]]).all(axis=1)).any():
        raise ValueError("Closing prices must be positive and volume non-negative; infinite values are invalid.")
    if frame.duplicated(["Ticker", "Date"]).any():
        raise ValueError("Duplicate trading dates were found for this ticker. Resolve them before uploading.")


def read_price_file(payload: bytes, filename: str, ticker: str = "", *,
                    allow_multiple: bool = False) -> pd.DataFrame:
    """Read a manually downloaded price table when an exchange blocks live access."""
    if not payload or len(payload) > 10 * 1024 * 1024:
        raise ValueError("Use a non-empty CSV/XLSX file smaller than 10 MB.")
    frame = read_tabular(payload, filename, max_rows=5000)
    aliases = {
        "date": "Date", "tradingcode": "Ticker", "tradecode": "Ticker", "code": "Ticker",
        "open": "Open", "openp": "Open", "high": "High", "low": "Low", "close": "Close",
        "closep": "Close", "closeprice": "Close", "ltp": "LTP", "ycp": "Previous Close",
        "previousclose": "Previous Close", "trade": "Trades", "numberoftrade": "Trades",
        "volume": "Volume", "valuemn": "Value (mn)", "turnover": "Turnover", "company": "Company",
    }
    frame = frame.rename(columns={c: aliases.get(re.sub(r"[^a-z0-9]", "", str(c).lower()), str(c)) for c in frame.columns})
    if not {"Date", "Close", "Volume"}.issubset(frame.columns):
        raise ValueError("The file needs Date, Close and Volume columns. Ticker/Code is recommended.")
    if frame.columns.duplicated().any():
        raise ValueError("Multiple columns map to the same price field. Keep one column per field.")
    # Slash dates follow the site's DD/MM/YYYY convention; ISO dates remain unambiguous.
    frame["Date"] = frame["Date"].map(_price_date)
    if "Ticker" not in frame:
        if not ticker:
            raise ValueError("Enter a ticker because the uploaded file has no Ticker/Code column.")
        frame["Ticker"] = _ticker(ticker)
    if frame["Ticker"].isna().any():
        raise ValueError("Every price row needs a ticker. Correct the missing ticker values.")
    frame["Ticker"] = frame["Ticker"].astype(str).str.strip().str.upper()
    if ticker:
        frame = frame.loc[frame["Ticker"] == _ticker(ticker)].copy()
        if frame.empty:
            raise ValueError(f"The file contains no rows for {_ticker(ticker)}. Check the selected ticker.")
    elif not allow_multiple and frame["Ticker"].nunique() != 1:
        raise ValueError("Choose a ticker before uploading a file containing multiple companies.")
    for value in frame["Ticker"].unique():
        _ticker(value)
    numeric_columns = {"Open", "High", "Low", "Close", "LTP", "Previous Close", "Trades",
                       "Volume", "Value (mn)", "Turnover"}
    for col in frame.columns.intersection(list(numeric_columns)):
        frame[col] = _number(frame[col])
    _validate_prices(frame)
    frame = frame.sort_values("Date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("No usable dated closing prices were found.")
    return frame
