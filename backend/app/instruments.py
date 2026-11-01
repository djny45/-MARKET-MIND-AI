"""Searchable, provider-neutral multi-market instrument reference directory.

Metadata only: this catalogue is not an exchange master, quote feed, or claim of
complete venue coverage. Provider identifiers and entitlements must be mapped
separately before ingesting market observations.
"""
from copy import deepcopy

# market_group partitions the four requested coverage domains. market remains
# the asset-class taxonomy used by existing callers.
_RAW_INSTRUMENTS = [
    ("AAPL", "Apple Inc.", "equities", "us", "NASDAQ", "USD", "equity"),
    ("MSFT", "Microsoft Corporation", "equities", "us", "NASDAQ", "USD", "equity"),
    ("NVDA", "NVIDIA Corporation", "equities", "us", "NASDAQ", "USD", "equity"),
    ("GOOGL", "Alphabet Inc.", "equities", "us", "NASDAQ", "USD", "equity"),
    ("AMZN", "Amazon.com Inc.", "equities", "us", "NASDAQ", "USD", "equity"),
    ("SPY", "SPDR S&P 500 ETF Trust", "funds", "us", "NYSE Arca", "USD", "etf"),
    ("QQQ", "Invesco QQQ Trust", "funds", "us", "NASDAQ", "USD", "etf"),
    ("SPX", "S&P 500 Index", "indices", "us", "Cboe", "USD", "equity_index"),
    ("NDX", "Nasdaq-100 Index", "indices", "us", "NASDAQ", "USD", "equity_index"),
    ("US10Y", "US 10-Year Treasury Yield", "rates_credit", "us", "US Treasury", "USD", "government_yield"),
    ("RELIANCE", "Reliance Industries Ltd.", "equities", "india", "NSE", "INR", "equity"),
    ("TCS", "Tata Consultancy Services Ltd.", "equities", "india", "NSE", "INR", "equity"),
    ("INFY", "Infosys Ltd.", "equities", "india", "NSE", "INR", "equity"),
    ("HDFCBANK", "HDFC Bank Ltd.", "equities", "india", "NSE", "INR", "equity"),
    ("NIFTY50", "NIFTY 50", "indices", "india", "NSE", "INR", "equity_index"),
    ("NIFTYBANK", "NIFTY Bank", "indices", "india", "NSE", "INR", "equity_index"),
    ("SENSEX", "BSE SENSEX", "indices", "india", "BSE", "INR", "equity_index"),
    ("USDINR", "US Dollar / Indian Rupee", "fx", "forex", "OTC", "INR", "spot_fx"),
    ("EURUSD", "Euro / US Dollar", "fx", "forex", "OTC", "USD", "spot_fx"),
    ("USDJPY", "US Dollar / Japanese Yen", "fx", "forex", "OTC", "JPY", "spot_fx"),
    ("GBPUSD", "British Pound / US Dollar", "fx", "forex", "OTC", "USD", "spot_fx"),
    ("AUDUSD", "Australian Dollar / US Dollar", "fx", "forex", "OTC", "USD", "spot_fx"),
    ("USDCAD", "US Dollar / Canadian Dollar", "fx", "forex", "OTC", "CAD", "spot_fx"),
    ("USDCHF", "US Dollar / Swiss Franc", "fx", "forex", "OTC", "CHF", "spot_fx"),
    ("NZDUSD", "New Zealand Dollar / US Dollar", "fx", "forex", "OTC", "USD", "spot_fx"),
    ("BTCUSD", "Bitcoin / US Dollar", "digital_assets", "crypto", "Multi-venue", "USD", "spot_crypto"),
    ("BTCUSDT", "Bitcoin / Tether", "digital_assets", "crypto", "Multi-venue", "USDT", "spot_crypto"),
    ("ETHUSD", "Ether / US Dollar", "digital_assets", "crypto", "Multi-venue", "USD", "spot_crypto"),
    ("ETHUSDT", "Ether / Tether", "digital_assets", "crypto", "Multi-venue", "USDT", "spot_crypto"),
    ("SOLUSD", "Solana / US Dollar", "digital_assets", "crypto", "Multi-venue", "USD", "spot_crypto"),
    ("XAUUSD", "Gold Spot / US Dollar", "commodities", "forex", "OTC", "USD", "spot_metal"),
    ("WTI", "WTI Crude Oil", "commodities", "us", "NYMEX", "USD", "commodity_future"),
    ("BRENT", "Brent Crude Oil", "commodities", "us", "ICE", "USD", "commodity_future"),
]

def _make_instrument(row):
    symbol, name, asset_class, group, venue, currency, instrument_type = row
    return {
        "instrument_id": f"{group}:{venue.lower().replace(' ', '-') }:{symbol}".replace(":", ":", 1),
        "symbol": symbol,
        "name": name,
        "market": asset_class,
        "market_group": group,
        "instrument_type": instrument_type,
        "venue": venue,
        "currency": currency,
        "metadata_status": "reference_only",
        "quotes_included": False,
    }

INSTRUMENTS = [_make_instrument(row) for row in _RAW_INSTRUMENTS]

def search_instruments(query="", market=None, limit=30, market_group=None):
    """Search reference metadata; never implies quote availability."""
    q = query.strip().casefold()
    rows = [
        item for item in INSTRUMENTS
        if (not market or item["market"] == market)
        and (not market_group or item["market_group"] == market_group)
        and (not q or q in item["symbol"].casefold()
             or q in item["name"].casefold()
             or q in item["venue"].casefold())
    ]
    safe_limit = max(1, min(int(limit), 100))
    return {
        "count": len(rows[:safe_limit]),
        "instruments": deepcopy(rows[:safe_limit]),
        "data_type": "reference_metadata_only",
        "quotes_included": False,
        "coverage_note": "Curated reference examples only; not a complete exchange instrument master.",
    }
