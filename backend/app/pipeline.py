"""Market research pipeline stages and capability discovery."""
from .markets import market_catalog
from .streaming import latency_budget
PIPELINE_STAGES=[
 {"id":"ingest","name":"Authorized market, macro and news feeds"},
 {"id":"normalize","name":"Instrument, currency and timestamp normalization"},
 {"id":"validate","name":"Freshness, gaps, provenance and entitlement checks"},
 {"id":"enrich","name":"Corporate actions, macro and news enrichment"},
 {"id":"compute","name":"Indicators, statistics and microstructure features"},
 {"id":"workers","name":"Specialist analytical worker fan-out"},
 {"id":"consensus","name":"Evidence scoring, disagreement and uncertainty"},
 {"id":"publish","name":"Dashboards, reports, alerts and audit events"},
]
def system_capabilities():
 return {"markets":market_catalog(),"stages":PIPELINE_STAGES,"latency":latency_budget(),
  "modes":{"research":True,"paper_trading":False,"broker_execution":False},
  "guarantees":{"microsecond_end_to_end":False,"live_data_without_provider":False}}
