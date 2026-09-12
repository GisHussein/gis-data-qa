"""Regenerate the example datasets.

The examples are deliberately small and deliberately broken: every failure the
checks can raise is represented by at least one feature, so `gisqa` can be run
against them straight after cloning.

    python examples/make_examples.py
"""

from __future__ import annotations

import pathlib

import geopandas as gpd
from shapely.geometry import Polygon

HERE = pathlib.Path(__file__).parent
DATA = HERE / "data"
DATA.mkdir(parents=True, exist_ok=True)

UTM36N = "EPSG:32636"


def square(x: float, y: float, size: float) -> Polygon:
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


def build_clean() -> gpd.GeoDataFrame:
    """Five tourism development plots that a QA run should pass."""
    rows = [
        ("PLT-001", "approved", 2500.0, square(420000, 2790000, 50)),
        ("PLT-002", "approved", 2500.0, square(420100, 2790000, 50)),
        ("PLT-003", "pending", 2500.0, square(420200, 2790000, 50)),
        ("PLT-004", "pending", 2500.0, square(420300, 2790000, 50)),
        ("PLT-005", "rejected", 2500.0, square(420400, 2790000, 50)),
    ]
    return gpd.GeoDataFrame(
        {
            "plot_id": [r[0] for r in rows],
            "status": [r[1] for r in rows],
            "area_m2": [r[2] for r in rows],
            "geometry": [r[3] for r in rows],
        },
        crs=UTM36N,
    )


def build_dirty() -> gpd.GeoDataFrame:
    """The same layer after three hand-offs between two teams."""
    bowtie = Polygon([(420600, 2790000), (420650, 2790050), (420600, 2790050), (420650, 2790000)])
    sliver = Polygon(
        [(420700, 2790000), (420700.4, 2790000), (420700.4, 2790030), (420700, 2790030)]
    )

    rows = [
        # id,        status,       area,    geometry
        ("PLT-001", "approved", 2500.0, square(420000, 2790000, 50)),
        ("PLT-002", "approved", 2500.0, square(420100, 2790000, 50)),
        # duplicate key AND duplicate geometry - a re-import that ran twice
        ("PLT-002", "approved", 2500.0, square(420100, 2790000, 50)),
        # overlaps PLT-004 by 20 m
        ("PLT-003", "pending", 2500.0, square(420200, 2790000, 50)),
        ("PLT-004", "pending", 2500.0, square(420230, 2790000, 50)),
        # status typed by hand, outside the domain
        ("PLT-005", "Approved ", 2500.0, square(420400, 2790000, 50)),
        # self-intersecting ring
        ("PLT-006", "pending", 2500.0, bowtie),
        # sliver left behind by a clip
        ("PLT-007", "pending", 12.0, sliver),
        # status never filled in
        ("PLT-008", None, 2500.0, square(420800, 2790000, 50)),
        # negative area - a unit conversion that went the wrong way
        ("PLT-009", "approved", -2500.0, square(420900, 2790000, 50)),
    ]
    return gpd.GeoDataFrame(
        {
            "plot_id": [r[0] for r in rows],
            "status": [r[1] for r in rows],
            "area_m2": [r[2] for r in rows],
            "surveyor_note": ["" for _ in rows],
            "geometry": [r[3] for r in rows],
        },
        crs=UTM36N,
    )


def build_wrong_crs() -> gpd.GeoDataFrame:
    """Labelled UTM 36N, actually still in degrees.

    This is the one that costs a week: it opens, it draws, and it is 3000 km
    from the site.
    """
    rows = [
        ("PLT-101", "approved", 2500.0, square(34.9, 25.2, 0.001)),
        ("PLT-102", "approved", 2500.0, square(34.902, 25.2, 0.001)),
    ]
    return gpd.GeoDataFrame(
        {
            "plot_id": [r[0] for r in rows],
            "status": [r[1] for r in rows],
            "area_m2": [r[2] for r in rows],
            "geometry": [r[3] for r in rows],
        },
        crs=UTM36N,
    )


def main() -> None:
    build_clean().to_file(DATA / "plots_clean.geojson", driver="GeoJSON")
    build_dirty().to_file(DATA / "plots_dirty.geojson", driver="GeoJSON")
    build_wrong_crs().to_file(DATA / "plots_wrong_crs.geojson", driver="GeoJSON")
    print(f"wrote three example layers to {DATA}")


if __name__ == "__main__":
    main()
