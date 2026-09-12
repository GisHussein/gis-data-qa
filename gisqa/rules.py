"""Rule loading and validation.

A rule file describes what a layer is *supposed* to look like. Everything the
checks do is driven from here, so adding a new dataset means writing a rule
file, not writing code.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import dataclass, field
from typing import Any

import yaml

VALID_GEOMETRY_TYPES = {
    "Point",
    "MultiPoint",
    "LineString",
    "MultiLineString",
    "Polygon",
    "MultiPolygon",
}


@dataclass
class FieldRule:
    """Expectations for a single attribute column."""

    name: str
    dtype: str | None = None          # "int", "float", "str", "date"
    required: bool = True             # column must exist
    nullable: bool = True             # values may be null
    unique: bool = False              # values must be unique across the layer
    allowed: list[Any] | None = None   # domain / picklist
    min: float | None = None
    max: float | None = None
    max_null_fraction: float | None = None  # e.g. 0.05 -> at most 5% nulls


@dataclass
class LayerRules:
    """Everything we expect to be true about one layer."""

    name: str = "layer"
    geometry_type: str | None = None
    crs: str | None = None                    # e.g. "EPSG:32636"
    allow_missing_crs: bool = False
    coordinate_bounds: tuple[float, float, float, float] | None = None
    min_area: float | None = None             # in CRS units; polygons only
    min_length: float | None = None           # in CRS units; lines only
    allow_overlaps: bool = True
    allow_duplicate_geometries: bool = False
    max_vertices: int | None = None
    fields: list[FieldRule] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "LayerRules":
        data = dict(data)
        raw_fields = data.pop("fields", []) or []
        fields_ = []
        for item in raw_fields:
            if "name" not in item:
                raise ValueError("every entry under 'fields' needs a 'name'")
            unknown = set(item) - set(FieldRule.__dataclass_fields__)
            if unknown:
                raise ValueError(
                    f"unknown key(s) {sorted(unknown)} in field '{item['name']}'"
                )
            fields_.append(FieldRule(**item))

        bounds = data.pop("coordinate_bounds", None)
        if bounds is not None:
            if len(bounds) != 4:
                raise ValueError("coordinate_bounds must be [minx, miny, maxx, maxy]")
            bounds = tuple(float(v) for v in bounds)

        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"unknown key(s) in rule file: {sorted(unknown)}")

        geom_type = data.get("geometry_type")
        if geom_type is not None and geom_type not in VALID_GEOMETRY_TYPES:
            raise ValueError(
                f"geometry_type '{geom_type}' is not one of {sorted(VALID_GEOMETRY_TYPES)}"
            )

        return cls(coordinate_bounds=bounds, fields=fields_, **data)

    @classmethod
    def load(cls, path: str | pathlib.Path) -> "LayerRules":
        path = pathlib.Path(path)
        text = path.read_text(encoding="utf-8")
        if path.suffix.lower() == ".json":
            data = json.loads(text)
        else:
            data = yaml.safe_load(text)
        if not isinstance(data, dict):
            raise ValueError(f"{path} does not contain a rule mapping")
        return cls.from_dict(data)
