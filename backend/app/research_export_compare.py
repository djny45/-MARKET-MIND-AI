"""Compare historical evidence exports without inferring market direction."""

def compare_research_exports(before, after):
    """Compare export scope and observation records by timestamp and source."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("both_inputs_must_be_objects")
    if before.get("report_type") != "historical_research_evidence":
        raise ValueError("unsupported_before_export")
    if after.get("report_type") != "historical_research_evidence":
        raise ValueError("unsupported_after_export")
    old_scope = before.get("scope") or {}
    new_scope = after.get("scope") or {}
    if (old_scope.get("symbol"), old_scope.get("interval")) != (new_scope.get("symbol"), new_scope.get("interval")):
        raise ValueError("export_scope_mismatch")
    return {"different": before != after, "scope": old_scope}
