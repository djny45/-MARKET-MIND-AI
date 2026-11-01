"""Deterministic smoke evaluation for the explicitly wired worker capabilities.

Evaluations use fixed synthetic observations. They measure wiring and output
shape only; they are not evidence of predictive skill or market performance.
"""
from .worker_runtime import worker_capabilities, dispatch_worker_task

FIXTURE_VALUES = [100.0, 101.5, 99.8, 102.2, 103.1, 101.9, 104.4, 105.0, 103.7, 106.2, 107.1, 105.8, 108.3, 109.0, 107.6, 110.2]


def _has_output(operation, result):
    if result is None:
        return False
    if operation in {"sma", "ema", "rsi"}:
        return isinstance(result, dict) and isinstance(result.get("series"), list)
    if operation == "macd":
        return isinstance(result, dict) and all(key in result for key in ("macd", "signal", "histogram"))
    if operation == "bollinger":
        return isinstance(result, dict) and all(key in result for key in ("middle", "upper", "lower"))
    if operation == "returns":
        return isinstance(result, dict) and isinstance(result.get("series"), list) and "summary" in result
    if operation == "volatility":
        return isinstance(result, (int, float, dict))
    if operation == "data_quality":
        return isinstance(result, dict) and result.get("quality", {}).get("status") == "pass"
    if operation == "research_summary":
        return isinstance(result, dict) and "report" in result
    return False


def evaluate_worker_capabilities():
    """Run one fixed fixture per unique mapped operation and report wiring coverage."""
    report = worker_capabilities()
    operation_workers = {}
    for profile in report["capabilities"]:
        for operation in profile["supported_operations"]:
            operation_workers.setdefault(operation, profile["worker_id"])

    evaluations = []
    for operation, worker_id in sorted(operation_workers.items()):
        try:
            dispatched = dispatch_worker_task(
                worker_id, operation, FIXTURE_VALUES, {"period": 5}
            )
            passed = dispatched.get("status") == "completed" and _has_output(
                operation, dispatched.get("result")
            )
            evaluations.append({
                "operation": operation,
                "worker_id": worker_id,
                "status": "passed" if passed else "failed",
                "output_contract_valid": _has_output(operation, dispatched.get("result")),
            })
        except Exception as exc:
            evaluations.append({
                "operation": operation,
                "worker_id": worker_id,
                "status": "failed",
                "output_contract_valid": False,
                "error_type": type(exc).__name__,
                "error": str(exc)[:300],
            })

    passed = sum(item["status"] == "passed" for item in evaluations)
    return {
        "evaluation_version": "1.0.0",
        "worker_contract_version": report["worker_contract_version"],
        "status": "passed" if passed == len(evaluations) else "failed",
        "evaluation_mode": "fixed_synthetic_smoke_test",
        "fixture_observations": len(FIXTURE_VALUES),
        "mapped_operation_count": len(operation_workers),
        "passed_operations": passed,
        "failed_operations": len(evaluations) - passed,
        "worker_profile_count": report["worker_profiles"],
        "executable_profile_count": report["executable_profiles"],
        "template_only_profile_count": report["template_only_profiles"],
        "evaluations": evaluations,
        "limitations": [
            "One representative worker is tested per unique mapped operation.",
            "This checks deterministic wiring and output shape, not analytical correctness or predictive performance.",
            "Fixtures are synthetic and do not represent live market observations.",
            "No LLM inference, live data retrieval, investment recommendation, or order execution occurs.",
        ],
        "research_only": True,
    }
