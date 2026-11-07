from app.model_registry import list_model_integrations


def test_kronos_is_reported_as_source_only():
    report = list_model_integrations()
    assert report["mode"] == "research_metadata_only"
    assert len(report["models"]) == 1
    kronos = report["models"][0]
    assert kronos["id"] == "kronos"
    assert kronos["source_imported"] is True
    assert kronos["pretrained_weights_present"] is False
    assert kronos["runtime_installed"] is False
    assert kronos["inference_enabled"] is False
    assert kronos["execution_enabled"] is False
    assert kronos["status"] == "source_only"
