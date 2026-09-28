"""Packaged same-industry suggestion groups for offline listed-company discovery."""
from __future__ import annotations


INDUSTRY_TICKERS = {
    "Foods & Allied": [
        "AMCL(PRAN)", "APEXFOODS", "BANGAS", "BDTHAIFOOD", "BEACHHATCH",
        "EMERALDOIL", "FINEFOODS", "FUWANGFOOD", "GHAIL", "LOVELLO",
        "OLYMPIC", "RAHIMAFOOD", "RDFOOD", "SALVO", "TAUFIKA", "ZEALBANGLA",
    ],
    "Pharmaceuticals & Chemicals": [
        "ACMELAB", "ACTIVEFINE", "AMBEEPHA", "BEACONPHAR", "BXPHARMA",
        "IBNSINA", "JHRML", "JMISMDL", "LIBRAINFU", "NAVANAPHAR",
        "ORIONINFU", "ORIONPHARM", "RENATA", "SILCOPHL", "SILVAPHL", "SQURPHARMA",
    ],
    "Banks": [
        "ABBANK", "BANKASIA", "BRACBANK", "CITYBANK", "DHAKABANK", "DUTCHBANGL",
        "EBL", "IFIC", "ISLAMIBANK", "JAMUNABANK", "MTB", "NCCBANK", "ONEBANKPLC",
        "PRIMEBANK", "PUBALIBANK", "SOUTHEASTB", "TRUSTBANK", "UCB", "UTTARABANK",
    ],
    "Cement": ["CONFIDCEM", "CROWNCEMNT", "HEIDELBCEM", "LHB", "MEGHNACEM", "PREMIERCEM"],
    "Engineering": [
        "AFTABAUTO", "ANWARGALV", "ATLASBANG", "BBSCABLES", "BDAUTOCA", "BDLAMPS",
        "BSRMLTD", "BSRMSTEEL", "GPHISPAT", "IFADAUTOS", "KAY&QUE", "RANFOUNDRY",
        "RUNNERAUTO", "SSSTEEL", "WALTONHIL",
    ],
    "Textile": [
        "ALLTEX", "ANLIMAYARN", "APEXSPINN", "ARGONDENIM", "ENVOYTEX", "ESQUIRENIT",
        "HRTEX", "MALEKSPIN", "MATINSPINN", "PARAMOUNT", "PRIMETEX", "SQUARETEXT",
    ],
    "Telecommunication": ["AAMRANET", "ADNTEL", "BDCOM", "GENEXIL", "GP", "ROBI"],
    "Fuel & Power": [
        "BARKAPOWER", "DESCO", "DOREENPWR", "GBBPOWER", "KPCL", "MJLBD",
        "POWERGRID", "SPCL", "SUMITPOWER", "TITASGAS", "UPGDCL",
    ],
    "Ceramics": ["FUWANGCER", "MONNOCERA", "RAKCERAMIC", "SPCERAMICS"],
    "Consumer Products": ["BATBC", "BERGERPBL", "KOHINOOR", "MARICO", "RECKITTBEN", "SINGERBD"],
}


def industry_for_ticker(ticker: str) -> str | None:
    ticker = str(ticker).strip().upper()
    return next((industry for industry, tickers in INDUSTRY_TICKERS.items()
                 if ticker in tickers), None)


def suggested_peers(ticker: str, industry: str | None = None,
                    available: set[str] | None = None) -> list[str]:
    ticker = str(ticker).strip().upper()
    chosen = industry or industry_for_ticker(ticker)
    values = INDUSTRY_TICKERS.get(chosen or "", [])
    if available is not None:
        values = [value for value in values if value in available]
    return [value for value in values if value != ticker]
