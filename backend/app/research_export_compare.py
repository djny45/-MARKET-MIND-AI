"""Compare two historical evidence bundles."""


def compare_research_exports(before, after):
    """Return whether two JSON-compatible bundle objects differ."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("both_inputs_must_be_objects")
    return {"different": before != after}
