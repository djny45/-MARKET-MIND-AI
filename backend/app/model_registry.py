"""Metadata for vendored research models; this module never loads model weights."""
from __future__ import annotations


def list_model_integrations() -> dict:
    """Describe imported model source without implying weights or inference are ready."""
    return {
        "mode": "research_metadata_only",
        "models": [
            {
                "id": "kronos",
                "name": "Kronos",
                "category": "third_party_financial_time_series_foundation_model",
                "source": "https://github.com/shiyu-coder/Kronos",
                "upstream_commit": "67b630e67f6a18c9e9be918d9b4337c960db1e9a",
                "license": "MIT",
                "source_imported": True,
                "pretrained_weights_present": False,
                "runtime_installed": False,
                "inference_enabled": False,
                "execution_enabled": False,
                "status": "source_only",
                "notes": [
                    "Upstream source is vendored under third_party/Kronos.",
                    "Pretrained weights are distributed separately and are not included.",
                    "Upstream dependencies are intentionally isolated from the core application.",
                    "No model inference, market forecast, or trading action is exposed by this integration.",
                ],
            }
        ],
    }
