"""Attribute schema and domain checks."""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..report import ERROR, WARNING, Finding
from ..rules import FieldRule, LayerRules

_DTYPE_TESTS = {
    "int": pd.api.types.is_integer_dtype,
    "float": lambda s: pd.api.types.is_float_dtype(s) or pd.api.types.is_integer_dtype(s),
    "str": lambda s: pd.api.types.is_string_dtype(s) or pd.api.types.is_object_dtype(s),
    "bool": pd.api.types.is_bool_dtype,
    "date": lambda s: pd.api.types.is_datetime64_any_dtype(s),
}


def _check_field(series: pd.Series, rule: FieldRule, ids) -> list[Finding]:
    findings: list[Finding] = []
    null_mask = series.isna().to_numpy()

    if rule.dtype:
        test = _DTYPE_TESTS.get(rule.dtype)
        if test is None:
            findings.append(
                Finding(
                    check="schema.unknown_dtype",
                    severity=WARNING,
                    message=f"field '{rule.name}' declares unsupported dtype '{rule.dtype}'",
                )
            )
        elif not test(series):
            findings.append(
                Finding(
                    check="schema.dtype",
                    severity=ERROR,
                    message=f"field '{rule.name}' is not of type {rule.dtype}",
                    detail={"found": str(series.dtype)},
                )
            )

    if not rule.nullable and null_mask.any():
        offenders = [ids[i] for i in np.flatnonzero(null_mask)]
        findings.append(
            Finding(
                check="schema.null",
                severity=ERROR,
                message=f"field '{rule.name}' is not nullable but has nulls",
                count=len(offenders),
                feature_ids=offenders,
            )
        )

    if rule.max_null_fraction is not None and len(series):
        fraction = float(null_mask.mean())
        if fraction > rule.max_null_fraction:
            findings.append(
                Finding(
                    check="schema.null_rate",
                    severity=WARNING,
                    message=(
                        f"field '{rule.name}' is {fraction:.1%} null, "
                        f"above the {rule.max_null_fraction:.1%} allowed"
                    ),
                )
            )

    if rule.unique:
        non_null = series[~null_mask]
        duplicated = non_null.duplicated(keep="first")
        if duplicated.any():
            positions = np.flatnonzero(~null_mask)[duplicated.to_numpy()]
            offenders = [ids[i] for i in positions]
            findings.append(
                Finding(
                    check="schema.unique",
                    severity=ERROR,
                    message=f"field '{rule.name}' must be unique but repeats",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={
                        "example_values": [
                            str(v) for v in non_null[duplicated].unique()[:5]
                        ]
                    },
                )
            )

    if rule.allowed is not None:
        allowed = set(rule.allowed)
        bad = (~series.isin(allowed)).to_numpy() & ~null_mask
        if bad.any():
            offenders = [ids[i] for i in np.flatnonzero(bad)]
            found = sorted({str(v) for v in series[bad].unique()})[:8]
            findings.append(
                Finding(
                    check="schema.domain",
                    severity=ERROR,
                    message=f"field '{rule.name}' contains values outside its domain",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={"unexpected_values": ", ".join(found)},
                )
            )

    if rule.min is not None or rule.max is not None:
        numeric = pd.to_numeric(series, errors="coerce")
        bad = np.zeros(len(series), dtype=bool)
        if rule.min is not None:
            bad |= (numeric < rule.min).fillna(False).to_numpy()
        if rule.max is not None:
            bad |= (numeric > rule.max).fillna(False).to_numpy()
        if bad.any():
            offenders = [ids[i] for i in np.flatnonzero(bad)]
            findings.append(
                Finding(
                    check="schema.range",
                    severity=ERROR,
                    message=f"field '{rule.name}' has values outside its allowed range",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={
                        "min_allowed": rule.min,
                        "max_allowed": rule.max,
                        "observed_min": None if numeric.isna().all() else float(numeric.min()),
                        "observed_max": None if numeric.isna().all() else float(numeric.max()),
                    },
                )
            )

    # Leading/trailing whitespace is invisible in a table and breaks every
    # join that touches the column.
    if pd.api.types.is_object_dtype(series) or pd.api.types.is_string_dtype(series):
        as_str = series.dropna().astype(str)
        untrimmed = as_str[as_str != as_str.str.strip()]
        if len(untrimmed):
            findings.append(
                Finding(
                    check="schema.whitespace",
                    severity=WARNING,
                    message=f"field '{rule.name}' has values with leading/trailing whitespace",
                    count=len(untrimmed),
                    feature_ids=[ids[i] for i in untrimmed.index[:50]]
                    if untrimmed.index.dtype.kind == "i"
                    else [],
                )
            )

    return findings


def check_schema(gdf, rules: LayerRules, ids) -> list[Finding]:
    findings: list[Finding] = []
    columns = set(gdf.columns) - {gdf.geometry.name}

    declared = {rule.name for rule in rules.fields}

    for rule in rules.fields:
        if rule.name not in gdf.columns:
            if rule.required:
                findings.append(
                    Finding(
                        check="schema.missing_field",
                        severity=ERROR,
                        message=f"required field '{rule.name}' is missing",
                        detail={"available": ", ".join(sorted(columns))},
                    )
                )
            continue
        findings.extend(_check_field(gdf[rule.name], rule, ids))

    extra = sorted(columns - declared)
    if declared and extra:
        findings.append(
            Finding(
                check="schema.undeclared_field",
                severity=WARNING,
                message="layer carries fields that the rule file does not describe",
                detail={"fields": ", ".join(extra)},
            )
        )

    return findings
