"""Canonical instrument taxonomy and provider capability registry."""
from dataclasses import asdict, dataclass

MARKET_CLASSES = {
 "equities":["common_stock","preferred_stock","adr"],
 "funds":["etf","mutual_fund","closed_end_fund"],
 "indices":["equity_index","volatility_index","bond_index","commodity_index"],
 "fx":["spot_fx","fx_forward","currency_index"],
 "rates_credit":["government_bond","corporate_bond","money_market","yield_curve","credit_spread"],
 "commodities":["energy","metals","agriculture","softs","livestock"],
 "derivatives":["listed_option","future","swap_reference","option_surface"],
 "digital_assets":["spot_crypto","crypto_derivative","onchain_metric"],
 "macro":["economic_series","central_bank_rate","inflation","employment","trade"],
}
@dataclass(frozen=True)
class ProviderSpec:
 name:str; market_classes:tuple[str,...]; data_types:tuple[str,...]; access:str; notes:str
PROVIDERS=[
 ProviderSpec("SEC EDGAR",("equities","funds"),("filings","company_facts","submissions"),"public","Observe fair-access policy and user-agent requirements."),
 ProviderSpec("ECB Data Portal",("fx","rates_credit","macro"),("reference_rates","yield_curves","statistics"),"public","Reference statistics, not executable FX pricing."),
 ProviderSpec("FRED",("rates_credit","macro"),("economic_series","rates"),"api_key","API key and terms apply."),
 ProviderSpec("EIA",("commodities","macro"),("energy_statistics",),"api_key","API key, quotas and terms apply."),
 ProviderSpec("CoinGecko",("digital_assets",),("market_snapshots","asset_metadata"),"provider_limited","Rate limits and commercial terms vary."),
 ProviderSpec("Official exchange APIs",tuple(MARKET_CLASSES),("quotes","trades","bars","order_book"),"entitlement_required","Venue permissions and redistribution rights apply."),
]
# Seven named research markets mapped to the canonical asset-class taxonomy
# and the venues referenced by the existing instrument registry. This is a
# taxonomy/reporting view only: it does not claim a connected provider or a
# live quote for any venue.
SEVEN_MARKETS = {
 "gold": {"market_classes": ["commodities"], "venues": ["COMEX", "MCX", "OTC"], "core_instruments": ["XAUUSD", "MCXGOLD"]},
 "silver": {"market_classes": ["commodities"], "venues": ["COMEX", "MCX", "OTC"], "core_instruments": ["XAGUSD", "MCXSILVER"]},
 "crude": {"market_classes": ["commodities"], "venues": ["NYMEX", "ICE", "MCX"], "core_instruments": ["WTI", "BRENT", "MCXCRUDE"]},
 "forex": {"market_classes": ["fx"], "venues": ["OTC"], "core_instruments": ["EURUSD", "USDJPY", "USDINR"]},
 "us": {"market_classes": ["equities", "funds", "indices"], "venues": ["NYSE", "NASDAQ", "Cboe"], "core_instruments": ["AAPL", "SPX", "NDX"]},
 "india": {"market_classes": ["equities", "indices"], "venues": ["NSE", "BSE"], "core_instruments": ["RELIANCE", "NIFTY50", "SENSEX"]},
 "crypto": {"market_classes": ["digital_assets"], "venues": ["Multi-venue"], "core_instruments": ["BTCUSD", "ETHUSD", "SOLUSD"]},
}

def seven_market_coverage():
 """Report the seven-market taxonomy with an explicit availability boundary.

 Instrument identities come from the canonical registry; this function never
 claims provider connectivity. Providers must be configured and attested
 separately before any observation is described as live or historical.
 """
 from .instruments import search_instruments  # local import avoids import cycles

 registered = {}
 for name, meta in SEVEN_MARKETS.items():
  found = []
  for symbol in meta["core_instruments"]:
   normalized = symbol.replace(":", "") if ":" in symbol else symbol
   result = search_instruments(normalized)
   found.append({"symbol": symbol, "registered": any(
    (m.get("symbol") or "").replace(":", "").upper() == normalized.upper()
    for m in result.get("instruments", [])
   )})
  registered[name] = {**meta, "core_instrument_registry": found}
 return {"markets": registered, "count": len(registered),
  "availability_note": "Taxonomy only. No provider connectivity, live quote or historical bar is implied by registry presence."}

def market_catalog():
 return {"market_classes":MARKET_CLASSES,"providers":[asdict(p) for p in PROVIDERS],
 "seven_market_coverage": seven_market_coverage(),
 "coverage_note":"Coverage depends on configured, authorized adapters; unsupported instruments must be explicit."}
