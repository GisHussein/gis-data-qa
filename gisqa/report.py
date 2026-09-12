"""Findings and report rendering."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

ERROR = "error"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}


@dataclass
class Finding:
    """One problem found in a layer.

    ``feature_ids`` holds the row indices (or key values) of the offending
    features, so the finding can be traced back to the data rather than just
    reported as a count.
    """

    check: str
    severity: str
    message: str
    count: int = 0
    feature_ids: list[Any] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        # Keep reports small: a thousand offending ids helps nobody.
        data["feature_ids"] = self.feature_ids[:50]
        data["feature_ids_truncated"] = len(self.feature_ids) > 50
        return data


@dataclass
class Report:
    source: str
    layer: str
    feature_count: int
    crs: str | None
    findings: list[Finding] = field(default_factory=list)

    def add(self, finding: Finding) -> None:
        self.findings.append(finding)

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == ERROR]

    @property
    def warnings(self) -> list[Finding]:
        return [f for f in self.findings if f.severity == WARNING]

    @property
    def passed(self) -> bool:
        return not self.errors

    def sorted_findings(self) -> list[Finding]:
        return sorted(
            self.findings,
            key=lambda f: (_SEVERITY_ORDER.get(f.severity, 9), f.check),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "layer": self.layer,
            "feature_count": self.feature_count,
            "crs": self.crs,
            "passed": self.passed,
            "summary": {
                "errors": len(self.errors),
                "warnings": len(self.warnings),
            },
            "findings": [f.to_dict() for f in self.sorted_findings()],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_text(self, use_colour: bool = True) -> str:
        marks = {ERROR: "FAIL", WARNING: "WARN", INFO: "INFO"}
        colours = {ERROR: "\033[31m", WARNING: "\033[33m", INFO: "\033[36m"}
        reset = "\033[0m"

        def paint(severity: str, text: str) -> str:
            if not use_colour:
                return text
            return f"{colours.get(severity, '')}{text}{reset}"

        lines = [
            f"Layer:     {self.layer}",
            f"Source:    {self.source}",
            f"Features:  {self.feature_count}",
            f"CRS:       {self.crs or '(none)'}",
            "",
        ]

        if not self.findings:
            lines.append("No issues found.")
            return "\n".join(lines)

        for finding in self.sorted_findings():
            mark = marks.get(finding.severity, "????")
            head = f"[{mark}] {finding.check}: {finding.message}"
            lines.append(paint(finding.severity, head))
            if finding.count:
                sample = ", ".join(str(i) for i in finding.feature_ids[:8])
                if sample:
                    more = "" if len(finding.feature_ids) <= 8 else ", ..."
                    lines.append(f"        {finding.count} feature(s): {sample}{more}")
                else:
                    lines.append(f"        {finding.count} feature(s)")
            for key, value in finding.detail.items():
                lines.append(f"        {key}: {value}")

        lines.append("")
        lines.append(f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)")
        return "\n".join(lines)


def merge_ids(values: Iterable[Any]) -> list[Any]:
    """Stable de-duplication, so the same feature is not listed twice."""
    seen: dict[Any, None] = {}
    for value in values:
        seen.setdefault(value, None)
    return list(seen)
