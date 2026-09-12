"""Geometry-level checks: is each individual shape usable?"""

from __future__ import annotations

import numpy as np
from shapely import get_coordinates, get_num_coordinates
from shapely.validation import explain_validity

from ..report import ERROR, WARNING, Finding
from ..rules import LayerRules


def _ids(ids, mask) -> list:
    return [ids[i] for i in np.flatnonzero(np.asarray(mask))]


def check_geometry(gdf, rules: LayerRules, ids) -> list[Finding]:
    findings: list[Finding] = []
    geom = gdf.geometry

    # --- missing / empty -----------------------------------------------
    missing = geom.isna().to_numpy()
    if missing.any():
        offenders = _ids(ids, missing)
        findings.append(
            Finding(
                check="geometry.missing",
                severity=ERROR,
                message="features have no geometry",
                count=len(offenders),
                feature_ids=offenders,
            )
        )

    present = ~missing
    empty = np.zeros(len(gdf), dtype=bool)
    empty[present] = geom[present].is_empty.to_numpy()
    if empty.any():
        offenders = _ids(ids, empty)
        findings.append(
            Finding(
                check="geometry.empty",
                severity=ERROR,
                message="features have an empty geometry",
                count=len(offenders),
                feature_ids=offenders,
            )
        )

    usable = present & ~empty
    if not usable.any():
        return findings

    sub = geom[usable]
    sub_ids = [ids[i] for i in np.flatnonzero(usable)]

    # --- validity --------------------------------------------------------
    invalid = ~sub.is_valid.to_numpy()
    if invalid.any():
        offenders = [sub_ids[i] for i in np.flatnonzero(invalid)]
        reasons: dict[str, int] = {}
        for g in sub[invalid]:
            reason = explain_validity(g).split("[")[0].strip()
            reasons[reason] = reasons.get(reason, 0) + 1
        findings.append(
            Finding(
                check="geometry.invalid",
                severity=ERROR,
                message="features fail OGC validity (self-intersection, bad ring order, ...)",
                count=len(offenders),
                feature_ids=offenders,
                detail={"reasons": reasons},
            )
        )

    # --- geometry type ---------------------------------------------------
    if rules.geometry_type:
        expected = rules.geometry_type
        actual = sub.geom_type.to_numpy()
        # Accept the single-part form where the layer is declared multi-part
        # and vice versa only when explicitly the same family.
        accepted = {expected}
        if expected.startswith("Multi"):
            accepted.add(expected[len("Multi"):])
        wrong = np.array([a not in accepted for a in actual])
        if wrong.any():
            offenders = [sub_ids[i] for i in np.flatnonzero(wrong)]
            found = sorted(set(actual[wrong]))
            findings.append(
                Finding(
                    check="geometry.type",
                    severity=ERROR,
                    message=f"expected {expected}, found other geometry types",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={"found": ", ".join(found)},
                )
            )

    # --- non-finite coordinates -----------------------------------------
    bad_coords = np.zeros(len(sub), dtype=bool)
    for i, g in enumerate(sub):
        coords = get_coordinates(g)
        if coords.size and not np.isfinite(coords).all():
            bad_coords[i] = True
    if bad_coords.any():
        offenders = [sub_ids[i] for i in np.flatnonzero(bad_coords)]
        findings.append(
            Finding(
                check="geometry.non_finite_coordinates",
                severity=ERROR,
                message="features contain NaN or infinite coordinates",
                count=len(offenders),
                feature_ids=offenders,
            )
        )

    # --- slivers ---------------------------------------------------------
    is_polygon = np.isin(sub.geom_type.to_numpy(), ["Polygon", "MultiPolygon"])
    if rules.min_area is not None and is_polygon.any():
        areas = sub.area.to_numpy()
        tiny = is_polygon & (areas < rules.min_area)
        if tiny.any():
            offenders = [sub_ids[i] for i in np.flatnonzero(tiny)]
            findings.append(
                Finding(
                    check="geometry.sliver_polygon",
                    severity=WARNING,
                    message=f"polygons smaller than min_area ({rules.min_area})",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={"smallest": float(np.nanmin(areas[tiny]))},
                )
            )

    is_line = np.isin(sub.geom_type.to_numpy(), ["LineString", "MultiLineString"])
    if rules.min_length is not None and is_line.any():
        lengths = sub.length.to_numpy()
        tiny = is_line & (lengths < rules.min_length)
        if tiny.any():
            offenders = [sub_ids[i] for i in np.flatnonzero(tiny)]
            findings.append(
                Finding(
                    check="geometry.short_line",
                    severity=WARNING,
                    message=f"lines shorter than min_length ({rules.min_length})",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={"shortest": float(np.nanmin(lengths[tiny]))},
                )
            )

    # --- vertex count ----------------------------------------------------
    # A boundary with 80k vertices is not a data problem in itself, but it is
    # the single most common reason a "slow spatial query" is slow.
    if rules.max_vertices is not None:
        counts = np.array([get_num_coordinates(g) for g in sub])
        heavy = counts > rules.max_vertices
        if heavy.any():
            offenders = [sub_ids[i] for i in np.flatnonzero(heavy)]
            findings.append(
                Finding(
                    check="geometry.vertex_count",
                    severity=WARNING,
                    message=f"features exceed max_vertices ({rules.max_vertices})",
                    count=len(offenders),
                    feature_ids=offenders,
                    detail={"largest": int(counts.max())},
                )
            )

    return findings
