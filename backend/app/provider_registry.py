"""Metadata-only catalogue for historical and streaming data-source readiness."""
from datetime import datetime, timezone

SOURCES = [
    {"id":"manual_csv","markets":["india","us","crypto","forex"],"mode":"historical",
     "status":"existing_importer","rights":"uploader_must_confirm_data_rights"},
    {"id":"synthetic_fixture","markets":["india","us","crypto","forex"],"mode":"historical",
     "status":"fixture_only","rights":"synthetic_data"},
    {"id":"licensed_vendor_adapter","markets":["india","us","crypto","forex"],
     "mode":"historical_and_streaming","status":"not_implemented",
     "rights":"written_contract_entitlement_and_redistribution_review_required"},
]

def provider_catalogue():
    return {"version":"1.0.0","checked_at":datetime.now(timezone.utc).isoformat(),
            "sources":SOURCES,"activation":{"enabled":False,
            "requirements":["documented licence","venue and instrument entitlement",
            "retention and redistribution review","credential validation","connector tests"]},
            "note":"This is a readiness register, not evidence of a provider contract or feed.",
            "research_only":True}
