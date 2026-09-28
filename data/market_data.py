"""Small, bounded adapters for official DSE and CSE public web pages.

The exchanges do not publish a stable public API for these views.  Keep parsing
isolated here so a layout change produces a clear error instead of bad data.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from io import StringIO
from io import BytesIO
import json
from pathlib import Path
import re

import pandas as pd
import requests
from core.config import FIELDS

try:  # Use the operating system's trusted certificate store when available.
    import truststore
    truststore.inject_into_ssl()
except ImportError:  # requests still uses its normal certifi verification.
    pass


DSE = "https://www.dsebd.org"
CSE = "https://www.cse.com.bd"
HEADERS = {"User-Agent": "Falcon Finalysis/1.1 (local educational analytics; contact: local-user)"}
MAX_RESPONSE = 8 * 1024 * 1024
TICKER_RE = re.compile(r"^[A-Z0-9&()._-]{1,24}$")
BUNDLED_TICKERS = Path(__file__).with_name("tickers.json")


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
    try:
        caller = session.request if session else requests.request
        request_headers = {**HEADERS, **kwargs.pop("headers", {})}
        response = caller(method, url, headers=request_headers, timeout=(8, 30), **kwargs)
        response.raise_for_status()
        if len(response.content) > MAX_RESPONSE:
            raise ValueError("The exchange returned more data than Falcon Finalysis can safely process at once.")
        return response
    except requests.exceptions.SSLError as exc:
        raise ValueError("Secure connection to the exchange failed. Check the computer's date and trusted certificates, then retry.") from exc
    except requests.RequestException as exc:
        raise ValueError("The exchange site is unavailable or rejected the request. Retry later or use the spreadsheet upload fallback.") from exc


def ticker_catalog(exchange: str) -> dict[str, str]:
    """Return official ticker codes mapped to exchange-provided company names."""
    exchange = exchange.upper()
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


def company_snapshot(exchange: str, ticker: str) -> CompanySnapshot:
    exchange, ticker = exchange.upper(), _ticker(ticker)
    if exchange == "DSE":
        url = f"{DSE}/displayCompany.php?name={ticker}"
    elif exchange == "CSE":
        url = f"{CSE}/company/companydetails/{ticker}"
    else:
        raise ValueError("Exchange must be DSE or CSE.")
    html = _request("GET", url).text
    tables = _tables(html)
    fields = _pairs(tables)
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
                    value = _number(pd.Series([table.iloc[row_i, col_i]])).iloc[0]
                    if pd.notna(value) and (value != 0 or metric in {"Dividend", "Dividend Yield"}):
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


def exchange_financials(exchange: str, ticker: str) -> ExchangeFinancials:
    exchange, ticker = exchange.upper(), _ticker(ticker)
    url = (f"{DSE}/displayCompany.php?name={ticker}" if exchange == "DSE"
           else f"{CSE}/company/companydetails/{ticker}" if exchange == "CSE" else "")
    if not url:
        raise ValueError("Exchange must be DSE or CSE.")
    response = _request("GET", url)
    frame, details = _annual_metrics(_tables(response.text), url)
    return ExchangeFinancials(frame.tail(10).reset_index(drop=True), details, url,
                              datetime.now(timezone.utc).replace(microsecond=0).isoformat())


def _number(series: pd.Series) -> pd.Series:
    text = series.astype("string").str.strip().str.replace(",", "", regex=False)
    text = text.str.replace(r"^\((.*)\)$", r"-\1", regex=True)
    extracted = text.str.extract(r"([-+]?\d*\.?\d+)", expand=False)
    return pd.to_numeric(extracted, errors="coerce")


def _standardize_dse(table: pd.DataFrame, ticker: str) -> pd.DataFrame:
    rename = {"DATE": "Date", "TRADING CODE": "Ticker", "OPENP*": "Open", "HIGH": "High",
              "LOW": "Low", "CLOSEP*": "Close", "LTP*": "LTP", "YCP": "Previous Close",
              "TRADE": "Trades", "VALUE (MN)": "Value (mn)", "VOLUME": "Volume"}
    table.columns = [str(c).strip().upper() for c in table.columns]
    if not {"DATE", "TRADING CODE", "CLOSEP*", "VOLUME"}.issubset(table.columns):
        raise ValueError("DSE returned a page, but its price table format has changed.")
    out = table.rename(columns=rename)[list(rename.values())].copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out[out["Ticker"].astype(str).str.upper().eq(ticker)]
    for col in out.columns.difference(["Date", "Ticker"]):
        out[col] = _number(out[col])
    return out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def _standardize_cse(table: pd.DataFrame, ticker: str) -> pd.DataFrame:
    table.columns = [str(c).strip().upper() for c in table.columns]
    required = {"DATE", "CODE", "CLOSE PRICE", "VOLUME"}
    if not required.issubset(table.columns):
        raise ValueError("CSE returned a page, but its price table format has changed.")
    rename = {"DATE": "Date", "CODE": "Ticker", "CLOSE PRICE": "Close", "VOLUME": "Volume",
              "TURNOVER": "Turnover", "NUMBER OF TRADE": "Trades", "COMPANY": "Company"}
    out = table.rename(columns=rename)[[rename[c] for c in rename if c in table.columns]].copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce", dayfirst=False)
    out = out[out["Ticker"].astype(str).str.upper().eq(ticker)]
    for col in out.columns.difference(["Date", "Ticker", "Company"]):
        out[col] = _number(out[col])
    return out.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)


def price_history(exchange: str, ticker: str, start: date, end: date) -> tuple[pd.DataFrame, str]:
    exchange, ticker = exchange.upper(), _ticker(ticker)
    start_text, end_text = _dates(start, end)
    if exchange == "DSE":
        url = f"{DSE}/day_end_archive.php"
        params = {"startDate": start_text, "endDate": end_text, "inst": ticker, "archive": "data"}
        response = _request("GET", url, params=params)
        candidates = [t for t in _tables(response.text) if {"DATE", "TRADING CODE", "CLOSEP*", "VOLUME"}.issubset({str(c).strip().upper() for c in t.columns})]
        if not candidates:
            raise ValueError("DSE returned no matching price table for this ticker and period.")
        frame = _standardize_dse(candidates[-1], ticker)
        source = response.url
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
    return frame, source


def read_price_file(payload: bytes, filename: str, ticker: str = "") -> pd.DataFrame:
    """Read a manually downloaded price table when an exchange blocks live access."""
    if not payload or len(payload) > 10 * 1024 * 1024:
        raise ValueError("Use a non-empty CSV/XLSX file smaller than 10 MB.")
    suffix = filename.lower().rsplit(".", 1)[-1]
    try:
        if suffix == "csv":
            frame = pd.read_csv(BytesIO(payload), nrows=5001)
        elif suffix == "xlsx":
            frame = pd.read_excel(BytesIO(payload), nrows=5001)
        else:
            raise ValueError("Use a CSV or XLSX price-history file.")
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("Unable to read this price-history file.") from exc
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
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
    if "Ticker" not in frame:
        if not ticker:
            raise ValueError("Enter a ticker because the uploaded file has no Ticker/Code column.")
        frame["Ticker"] = _ticker(ticker)
    for col in frame.columns.difference(["Date", "Ticker", "Company"]):
        frame[col] = _number(frame[col])
    frame = frame.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)
    if frame.empty:
        raise ValueError("No usable dated closing prices were found.")
    return frame
