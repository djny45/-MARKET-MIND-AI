"""Read-only structural validation for exported n8n workflow JSON.

This checks common export invariants only. It does not execute nodes, prove
credential safety, validate node compatibility against an installed n8n version,
or import/activate workflows.
"""
import math
import re
from typing import Any

_SECRET_KEYS = {
    "password", "access_token", "refresh_token", "client_secret",
    "apikey", "api_key", "authorization",
}
_CREDENTIAL_PATTERN = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-(?:proj-)?|gh[pousr]_)[A-Za-z0-9_-]{20,}"
)


def validate_n8n_workflow(workflow: Any) -> dict:
    errors: list[str] = []
    if not isinstance(workflow, dict):
        return {"structurally_valid": False, "errors": ["Workflow must be a JSON object."], "runtime_verified": False}
    if workflow.get("active") is not False:
        errors.append("Shareable workflow must explicitly set active=false.")
    nodes = workflow.get("nodes")
    if not isinstance(nodes, list) or not nodes:
        errors.append("nodes must be a nonempty array.")
        return {"structurally_valid": False, "errors": errors, "runtime_verified": False}

    names: set[str] = set()
    ids: set[str] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            errors.append(f"Node {index} must be an object.")
            continue
        for key, seen in (("name", names), ("id", ids)):
            value = node.get(key)
            if not isinstance(value, str) or not value.strip():
                errors.append(f"Node {index} needs {key}.")
            elif value in seen:
                errors.append(f"Duplicate node {key}.")
            else:
                seen.add(value)
        if not isinstance(node.get("type"), str) or not node["type"]:
            errors.append(f"Node {index} needs a type.")
        version = node.get("typeVersion")
        if isinstance(version, bool) or not isinstance(version, (int, float)) or not math.isfinite(version) or version <= 0:
            errors.append(f"Node {index} needs a finite positive typeVersion.")
        if not isinstance(node.get("parameters"), dict):
            errors.append(f"Node {index} needs a parameters object.")
        if node.get("credentials"):
            errors.append(f"Node {index} contains credential bindings; strip them from a public example.")

    connections = workflow.get("connections")
    if not isinstance(connections, dict):
        errors.append("connections must be an object.")
        connections = {}
    for source, ports in connections.items():
        if source not in names:
            errors.append("Connection starts at an unknown node.")
        if not isinstance(ports, dict):
            errors.append("Connection ports must be an object.")
            continue
        for groups in ports.values():
            if not isinstance(groups, list):
                errors.append("Connection output groups must be arrays.")
                continue
            for group in groups:
                if not isinstance(group, list):
                    errors.append("Connection output must be an array.")
                    continue
                for edge in group:
                    if not isinstance(edge, dict):
                        errors.append("Connection target must be an object.")
                        continue
                    target = edge.get("node")
                    if not isinstance(target, str) or target not in names:
                        errors.append("Connection points at an unknown node.")
                    index = edge.get("index")
                    if isinstance(index, bool) or not isinstance(index, int) or index < 0:
                        errors.append("Connection target index must be a nonnegative integer.")
                    if not isinstance(edge.get("type"), str) or not edge["type"]:
                        errors.append("Connection target needs a type.")

    def scan(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key.lower() in _SECRET_KEYS and isinstance(child, str) and child and not child.startswith("={{"):
                    errors.append("Possible embedded secret field; inspect locally (value withheld).")
                if key.lower() == "name" and isinstance(child, str) and child.lower() in _SECRET_KEYS and isinstance(value.get("value"), str) and value["value"] and not value["value"].startswith("={{"):
                    errors.append("Possible embedded secret header (value withheld).")
                scan(child)
        elif isinstance(value, list):
            for item in value:
                scan(item)
        elif isinstance(value, str) and _CREDENTIAL_PATTERN.search(value):
            errors.append("Possible credential pattern (value withheld).")

    scan(workflow)
    errors = list(dict.fromkeys(errors))
    return {"structurally_valid": not errors, "errors": errors, "runtime_verified": False}
