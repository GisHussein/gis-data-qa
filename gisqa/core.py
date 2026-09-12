"""Entry points that tie the rule file, the layer and the checks together."""

from __future__ import annotations

import pathlib
from typing import Any, Sequence

import geopandas as gpd

from .checks import check_crs, check_geometry, check_schema, check_topology
from .report import Report
from .rules import LayerRules

CHECKS = (check_crs, check_geometry, check_topology, check_schema)


def _feature_ids(gdf: gpd.GeoDataFrame, rules: LayerRules) -> Sequence[Any]:
    """Prefer a declared unique key over the row number.

    Reporting "row 418 is invalid" is useless once the file has been sorted;
    reporting "parcel P-0418 is invalid" survives the next export.
    """
    for rule in rules.fields:
        if rule.unique and rule.name in gdf.columns:
            return list(gdf[rule.name])
    return list(range(len(gdf)))


def validate(
    gdf: gpd.GeoDataFrame,
    rules: LayerRules,
    source: str = "(in memory)",
) -> Report:
    if gdf.geometry.name not in gdf.columns:
        raise ValueError("the GeoDataFrame has no active geometry column")

    gdf = gdf.reset_index(drop=True)
    ids = _feature_ids(gdf, rules)

    report = Report(
        source=source,
        layer=rules.name,
        feature_count=len(gdf),
        crs=str(gdf.crs) if gdf.crs is not None else None,
    )

    if len(gdf) == 0:
        from .report import WARNING, Finding

        report.add(
            Finding(
                check="layer.empty",
                severity=WARNING,
                message="layer contains no features",
            )
        )
        return report

    for check in CHECKS:
        for finding in check(gdf, rules, ids):
            report.add(finding)

    return report


def validate_file(
    path: str | pathlib.Path,
    rules_path: str | pathlib.Path,
    layer: str | None = None,
) -> Report:
    rules = LayerRules.load(rules_path)
    read_kwargs = {"layer": layer} if layer else {}
    gdf = gpd.read_file(path, **read_kwargs)
    return validate(gdf, rules, source=str(path))
