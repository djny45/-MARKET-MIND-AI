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
def market_catalog():
 return {"market_classes":MARKET_CLASSES,"providers":[asdict(p) for p in PROVIDERS],
 "coverage_note":"Coverage depends on configured, authorized adapters; unsupported instruments must be explicit."}
