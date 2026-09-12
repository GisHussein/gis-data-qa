import geopandas as gpd
import pytest
from shapely.geometry import Polygon

from gisqa.rules import FieldRule, LayerRules

UTM36N = "EPSG:32636"


def square(x, y, size=50.0):
    return Polygon([(x, y), (x + size, y), (x + size, y + size), (x, y + size)])


@pytest.fixture
def rules():
    return LayerRules(
        name="plots",
        geometry_type="Polygon",
        crs=UTM36N,
        min_area=100,
        allow_overlaps=False,
        allow_duplicate_geometries=False,
        fields=[
            FieldRule(name="plot_id", dtype="str", nullable=False, unique=True),
            FieldRule(
                name="status",
                dtype="str",
                nullable=False,
                allowed=["approved", "pending", "rejected"],
            ),
            FieldRule(name="area_m2", dtype="float", min=0),
        ],
    )


@pytest.fixture
def clean_layer():
    return gpd.GeoDataFrame(
        {
            "plot_id": ["A1", "A2", "A3"],
            "status": ["approved", "pending", "rejected"],
            "area_m2": [2500.0, 2500.0, 2500.0],
            "geometry": [square(420000, 2790000), square(420100, 2790000), square(420200, 2790000)],
        },
        crs=UTM36N,
    )


def codes(report):
    """The set of check names a report raised - what the tests assert on."""
    return {finding.check for finding in report.findings}
