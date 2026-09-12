"""Coordinate reference system checks.

The most expensive GIS bug I keep meeting is not a broken polygon, it is data
that is silently in the wrong coordinate system: it loads, it draws, it just
sits a few hundred metres - or a few thousand kilometres - from where it
belongs. These checks are cheap and catch it at ingest.
"""

from __future__ import annotations

import numpy as np
from pyproj import CRS

from ._util import usable_mask
from ..report import ERROR, WARNING, Finding
from ..rules import LayerRules


def _looks_like_degrees(bounds) -> bool:
    minx, miny, maxx, maxy = bounds
    return -180.5 <= minx <= 180.5 and -90.5 <= miny <= 90.5 and -180.5 <= maxx <= 180.5 and -90.5 <= maxy <= 90.5


def check_crs(gdf, rules: LayerRules, ids) -> list[Finding]:
    findings: list[Finding] = []
    crs = gdf.crs

    if crs is None:
        severity = WARNING if rules.allow_missing_crs else ERROR
        findings.append(
            Finding(
                check="crs.missing",
                severity=severity,
                message="layer has no CRS defined",
                detail={"hint": "an undefined CRS is assumed by whoever opens it next"},
            )
        )
    elif rules.crs:
        expected = CRS.from_user_input(rules.crs)
        if not CRS.from_user_input(crs).equals(expected):
            findings.append(
                Finding(
                    check="crs.mismatch",
                    severity=ERROR,
                    message="layer CRS differs from the declared CRS",
                    detail={
                        "expected": rules.crs,
                        "found": CRS.from_user_input(crs).to_string(),
                    },
                )
            )

    usable = usable_mask(gdf.geometry)
    if not usable.any():
        return findings

    bounds = gdf[usable].total_bounds
    if not np.isfinite(bounds).all():
        return findings

    # Degrees stored in a projected CRS, or metres stored in a geographic one.
    if crs is not None:
        crs_obj = CRS.from_user_input(crs)
        if crs_obj.is_projected and _looks_like_degrees(bounds):
            findings.append(
                Finding(
                    check="crs.units_mismatch",
                    severity=ERROR,
                    message="projected CRS but coordinates are in the degree range",
                    detail={
                        "bounds": [round(float(b), 4) for b in bounds],
                        "hint": "the data was probably never reprojected, only re-labelled",
                    },
                )
            )
        elif crs_obj.is_geographic and not _looks_like_degrees(bounds):
            findings.append(
                Finding(
                    check="crs.units_mismatch",
                    severity=ERROR,
                    message="geographic CRS but coordinates are outside the degree range",
                    detail={"bounds": [round(float(b), 3) for b in bounds]},
                )
            )

    # Explicit study-area envelope from the rule file.
    if rules.coordinate_bounds is not None:
        minx, miny, maxx, maxy = rules.coordinate_bounds
        geom = gdf[usable].geometry
        outside = ~(
            (geom.bounds["minx"] >= minx)
            & (geom.bounds["miny"] >= miny)
            & (geom.bounds["maxx"] <= maxx)
            & (geom.bounds["maxy"] <= maxy)
        ).to_numpy()
        if outside.any():
            sub_ids = [ids[i] for i in np.flatnonzero(usable.to_numpy())]
            offenders = [sub_ids[i] for i in np.flatnonzero(outside)]
            findings.append(
                Finding(
                    check="crs.outside_study_area",
                    severity=ERROR,
                    message="features fall outside the declared coordinate bounds",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={"declared_bounds": list(rules.coordinate_bounds)},
                )
            )

    return findings
