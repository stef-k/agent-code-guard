"""Human presentation for completed normal-analysis payloads."""

from __future__ import annotations

import json


def _loc_lines(data: dict[str, object]) -> list[str]:
    lines = []
    loc_result = data["guards"]["loc"]
    for finding in loc_result["findings"]:
        if finding["nativeStatus"] == "ok" and finding.get("baselineLoc") is None:
            continue
        label = (
            "RATCHET" if finding["nativeStatus"] == "grandfathered" else
            "EXEMPT" if finding["nativeStatus"] == "exempt" else finding["state"].upper()
        )
        baseline_detail = ""
        if finding.get("baselineLoc") is not None:
            status = {
                "within": "within", "exceeded": "exceeded", "notNeeded": "no longer needed",
            }[finding["ratchetStatus"]]
            baseline_detail = f"; baseline {finding['baselineLoc']}, {status}"
        lines.append(
            f"{label}: {finding['path']} — {finding['countedLoc']} LOC "
            f"(warn {finding['warnAt']}, fail {finding['failAt']}{baseline_detail})"
        )
        if finding["overrideIndex"] is not None:
            lines.append(f"  Threshold override: {finding['overrideIndex']}")
        if finding["reason"]:
            lines.append(f"  Reason: {finding['reason']}")
    return lines


def _callable_size_lines(data: dict[str, object]) -> list[str]:
    lines = []
    result = data["guards"].get("callableSize")
    if result:
        for finding in result["findings"]:
            if finding["state"] != "review":
                continue
            lines.append(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— {finding['callable']} is {finding['measured']} LOC "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    return lines


def _nesting_lines(data: dict[str, object]) -> list[str]:
    lines = []
    result = data["guards"].get("nesting")
    if result:
        for finding in result["findings"]:
            if finding["state"] != "review":
                continue
            deepest = finding.get("details", {}).get("deepestLine")
            explanation = f"; deepest at line {deepest}" if deepest is not None else ""
            lines.append(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— {finding['callable']} nesting depth {finding['measured']} "
                f"(review {finding['thresholds']['reviewAt']}{explanation})"
            )
    return lines


def _complexity_lines(data: dict[str, object]) -> list[str]:
    lines = []
    result = data["guards"].get("complexity")
    if result:
        for finding in result["findings"]:
            if finding["state"] != "review":
                continue
            lines.append(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— {finding['callable']} complexity {finding['measured']} "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    return lines


def _markdown_lines(data: dict[str, object]) -> list[str]:
    lines = []
    document_result = data["guards"].get("markdownDocumentSize")
    if document_result:
        for finding in document_result["findings"]:
            if finding["state"] != "review":
                continue
            lines.append(
                f"REVIEW: {finding['path']} — Markdown document is {finding['measured']} lines "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    section_result = data["guards"].get("markdownSectionSize")
    if section_result:
        for finding in section_result["findings"]:
            if finding["state"] != "review":
                continue
            lines.append(
                f"REVIEW: {finding['path']}:{finding['range']['startLine']}-{finding['range']['endLine']} "
                f"— section {json.dumps(finding['heading'], ensure_ascii=False)} is {finding['measured']} lines "
                f"(review {finding['thresholds']['reviewAt']})"
            )
    return lines


def format_completed_analysis(data: dict[str, object]) -> str:
    """Return the complete human report for an existing completed payload."""
    scope = data["scope"]
    if data["overall"] == "incomplete":
        lines = [
            f"INCOMPLETE: {scope['selected']} selected; {scope['analyzed']} analyzed; "
            f"{scope['inapplicable']} inapplicable; {scope['unavailable']} unavailable; "
            f"{scope['excluded']} excluded. Completed findings: {str(data['completedOverall']).upper()}."
        ]
        lines.extend(
            f"UNAVAILABLE: {item['path']} [{item['language']} {item['kind']}] - {item['message']}"
            for item in data["unavailable"]
        )
        incomplete_guards = [
            guard_id for guard_id, result in data["guards"].items() if not result["complete"]
        ]
        lines.append(f"Incomplete guards: {', '.join(incomplete_guards)}.")
    else:
        lines = [
            f"{str(data['overall']).upper()}: {scope['selected']} selected; {scope['analyzed']} analyzed; "
            f"{scope['inapplicable']} inapplicable; {scope['excluded']} excluded."
        ]
    lines.extend(_loc_lines(data))
    lines.extend(_callable_size_lines(data))
    lines.extend(_nesting_lines(data))
    lines.extend(_complexity_lines(data))
    lines.extend(_markdown_lines(data))
    policies = data["requiredPolicies"]
    if policies:
        lines.append(f"Required policies: {', '.join(policies)}")
        lines.append("Required action: inspect each actionable finding using its policy guidance.")
    return "\n".join(lines)
