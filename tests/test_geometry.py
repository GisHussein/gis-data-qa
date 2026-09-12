import geopandas as gpd
from shapely.geometry import LineString, Polygon

from gisqa import validate

from .conftest import UTM36N, codes, square


def test_clean_layer_passes(clean_layer, rules):
    report = validate(clean_layer, rules)
    assert report.passed
    assert report.findings == []


def test_self_intersection_is_an_error(clean_layer, rules):
    bowtie = Polygon([(0, 0), (10, 10), (0, 10), (10, 0)])
    clean_layer.loc[0, "geometry"] = bowtie
    report = validate(clean_layer, rules)
    assert "geometry.invalid" in codes(report)
    assert not report.passed


def test_missing_geometry_is_reported(clean_layer, rules):
    clean_layer.loc[1, "geometry"] = None
    report = validate(clean_layer, rules)
    assert "geometry.missing" in codes(report)


def test_empty_geometry_is_reported(clean_layer, rules):
    clean_layer.loc[1, "geometry"] = Polygon()
    report = validate(clean_layer, rules)
    assert "geometry.empty" in codes(report)


def test_wrong_geometry_type(clean_layer, rules):
    clean_layer.loc[2, "geometry"] = LineString([(0, 0), (1, 1)])
    report = validate(clean_layer, rules)
    assert "geometry.type" in codes(report)


def test_sliver_is_a_warning_not_an_error(rules):
    layer = gpd.GeoDataFrame(
        {
            "plot_id": ["A1"],
            "status": ["approved"],
            "area_m2": [4.0],
            "geometry": [square(420000, 2790000, 2)],
        },
        crs=UTM36N,
    )
    report = validate(layer, rules)
    assert "geometry.sliver_polygon" in codes(report)
    assert report.passed  # warnings alone must not fail the run


def test_vertex_budget(clean_layer, rules):
    rules.max_vertices = 4
    report = validate(clean_layer, rules)
    assert "geometry.vertex_count" in codes(report)


def test_feature_ids_use_the_unique_key(clean_layer, rules):
    clean_layer.loc[1, "geometry"] = Polygon([(0, 0), (10, 10), (0, 10), (10, 0)])
    report = validate(clean_layer, rules)
    finding = next(f for f in report.findings if f.check == "geometry.invalid")
    assert finding.feature_ids == ["A2"]  # not row 1
