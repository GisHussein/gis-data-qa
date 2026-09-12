"""Relationships *between* features in the same layer."""

from __future__ import annotations

import numpy as np

from ._util import usable_mask
from ..report import ERROR, WARNING, Finding, merge_ids
from ..rules import LayerRules


def check_topology(gdf, rules: LayerRules, ids) -> list[Finding]:
    findings: list[Finding] = []

    usable = usable_mask(gdf.geometry)
    if usable.sum() < 2:
        return findings

    sub = gdf[usable]
    sub_ids = [ids[i] for i in np.flatnonzero(usable.to_numpy())]

    # --- duplicate geometries -------------------------------------------
    if not rules.allow_duplicate_geometries:
        wkb = sub.geometry.to_wkb()
        seen: dict[bytes, int] = {}
        duplicates: list = []
        for position, blob in enumerate(wkb):
            if blob in seen:
                duplicates.append(sub_ids[position])
            else:
                seen[blob] = position
        if duplicates:
            findings.append(
                Finding(
                    check="topology.duplicate_geometry",
                    severity=ERROR,
                    message="identical geometries appear more than once",
                    count=len(duplicates),
                    feature_ids=duplicates,
                )
            )

    # --- overlaps --------------------------------------------------------
    # Only meaningful for polygon layers that are supposed to tile a space
    # (parcels, admin units, zoning). The spatial index keeps this from being
    # an O(n^2) walk.
    polygonal = sub.geom_type.isin(["Polygon", "MultiPolygon"]).all()
    if not rules.allow_overlaps and polygonal:
        valid = sub[sub.geometry.is_valid]
        if len(valid) > 1:
            pairs = valid.sindex.query(valid.geometry, predicate="overlaps")
            left, right = pairs
            offenders = []
            positions = {label: i for i, label in enumerate(valid.index)}
            id_lookup = {
                label: sub_ids[list(sub.index).index(label)] for label in valid.index
            }
            for a, b in zip(left, right):
                if a >= b:
                    continue  # each pair once
                label_a = valid.index[a]
                label_b = valid.index[b]
                offenders.append(id_lookup[label_a])
                offenders.append(id_lookup[label_b])
            offenders = merge_ids(offenders)
            if offenders:
                findings.append(
                    Finding(
                        check="topology.overlap",
                        severity=ERROR,
                        message="polygons overlap each other",
                        count=len(offenders),
                        feature_ids=offenders,
                        detail={"pairs": int(sum(1 for a, b in zip(left, right) if a < b))},
                    )
                )
            del positions

    # --- self-touching multiparts ---------------------------------------
    multi = sub.geom_type.str.startswith("Multi").to_numpy()
    if multi.any():
        singles = int((~multi).sum())
        if singles and multi.sum():
            findings.append(
                Finding(
                    check="topology.mixed_multipart",
                    severity=WARNING,
                    message="layer mixes single-part and multi-part geometries",
                    count=int(multi.sum()),
                    feature_ids=[sub_ids[i] for i in np.flatnonzero(multi)],
                    detail={"single_part": singles, "multi_part": int(multi.sum())},
                )
            )

    return findings
