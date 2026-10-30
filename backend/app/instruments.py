"""Searchable instrument reference directory.

This catalogue contains identifiers and metadata only. It does not provide quotes,
market status, recommendations or a claim of complete global coverage.
"""
INSTRUMENTS = [
 {"symbol":"AAPL","name":"Apple Inc.","market":"equities","venue":"NASDAQ","currency":"USD"},
 {"symbol":"MSFT","name":"Microsoft Corporation","market":"equities","venue":"NASDAQ","currency":"USD"},
 {"symbol":"NVDA","name":"NVIDIA Corporation","market":"equities","venue":"NASDAQ","currency":"USD"},
 {"symbol":"GOOGL","name":"Alphabet Inc.","market":"equities","venue":"NASDAQ","currency":"USD"},
 {"symbol":"AMZN","name":"Amazon.com Inc.","market":"equities","venue":"NASDAQ","currency":"USD"},
 {"symbol":"RELIANCE","name":"Reliance Industries Ltd.","market":"equities","venue":"NSE","currency":"INR"},
 {"symbol":"TCS","name":"Tata Consultancy Services Ltd.","market":"equities","venue":"NSE","currency":"INR"},
 {"symbol":"INFY","name":"Infosys Ltd.","market":"equities","venue":"NSE","currency":"INR"},
 {"symbol":"HDFCBANK","name":"HDFC Bank Ltd.","market":"equities","venue":"NSE","currency":"INR"},
 {"symbol":"SPY","name":"SPDR S&P 500 ETF Trust","market":"funds","venue":"NYSE Arca","currency":"USD"},
 {"symbol":"QQQ","name":"Invesco QQQ Trust","market":"funds","venue":"NASDAQ","currency":"USD"},
 {"symbol":"NIFTY50","name":"NIFTY 50","market":"indices","venue":"NSE","currency":"INR"},
 {"symbol":"SPX","name":"S&P 500 Index","market":"indices","venue":"Cboe","currency":"USD"},
 {"symbol":"NDX","name":"Nasdaq-100 Index","market":"indices","venue":"NASDAQ","currency":"USD"},
 {"symbol":"EURUSD","name":"Euro / US Dollar","market":"fx","venue":"OTC","currency":"USD"},
 {"symbol":"USDJPY","name":"US Dollar / Japanese Yen","market":"fx","venue":"OTC","currency":"JPY"},
 {"symbol":"GBPUSD","name":"British Pound / US Dollar","market":"fx","venue":"OTC","currency":"USD"},
 {"symbol":"XAUUSD","name":"Gold Spot / US Dollar","market":"commodities","venue":"OTC","currency":"USD"},
 {"symbol":"WTI","name":"WTI Crude Oil","market":"commodities","venue":"NYMEX","currency":"USD"},
 {"symbol":"BRENT","name":"Brent Crude Oil","market":"commodities","venue":"ICE","currency":"USD"},
 {"symbol":"BTCUSD","name":"Bitcoin / US Dollar","market":"digital_assets","venue":"Multi-venue","currency":"USD"},
 {"symbol":"ETHUSD","name":"Ether / US Dollar","market":"digital_assets","venue":"Multi-venue","currency":"USD"},
 {"symbol":"SOLUSD","name":"Solana / US Dollar","market":"digital_assets","venue":"Multi-venue","currency":"USD"},
 {"symbol":"US10Y","name":"US 10-Year Treasury Yield","market":"rates_credit","venue":"US Treasury","currency":"USD"},
]
def search_instruments(query="", market=None, limit=30):
 q=query.strip().casefold()
 rows=[x for x in INSTRUMENTS if (not market or x["market"]==market)
       and (not q or q in x["symbol"].casefold() or q in x["name"].casefold())]
 return {"count":len(rows[:max(1,min(limit,100))]),"instruments":rows[:max(1,min(limit,100))],
  "data_type":"reference_metadata_only","quotes_included":False}
