import geopandas as gpd
import pytest

from gisqa import validate

from .conftest import UTM36N, codes, square


def test_overlap_detected(clean_layer, rules):
    clean_layer.loc[1, "geometry"] = square(420020, 2790000)  # 30 m into A1
    report = validate(clean_layer, rules)
    assert "topology.overlap" in codes(report)
    finding = next(f for f in report.findings if f.check == "topology.overlap")
    assert set(finding.feature_ids) == {"A1", "A2"}


def test_overlap_allowed_when_the_rules_say_so(clean_layer, rules):
    rules.allow_overlaps = True
    clean_layer.loc[1, "geometry"] = square(420020, 2790000)
    report = validate(clean_layer, rules)
    assert "topology.overlap" not in codes(report)


def test_touching_polygons_do_not_count_as_overlapping(clean_layer, rules):
    # Shared edge, no shared interior: this is what a correct parcel fabric
    # looks like and it must not be flagged.
    clean_layer.loc[1, "geometry"] = square(420050, 2790000)
    report = validate(clean_layer, rules)
    assert "topology.overlap" not in codes(report)


def test_duplicate_geometry(clean_layer, rules):
    clean_layer.loc[2, "geometry"] = clean_layer.loc[0, "geometry"]
    report = validate(clean_layer, rules)
    assert "topology.duplicate_geometry" in codes(report)


def test_missing_crs_is_an_error(clean_layer, rules):
    layer = clean_layer.set_crs(None, allow_override=True)
    report = validate(layer, rules)
    assert "crs.missing" in codes(report)


def test_missing_crs_can_be_downgraded(clean_layer, rules):
    rules.allow_missing_crs = True
    layer = clean_layer.set_crs(None, allow_override=True)
    report = validate(layer, rules)
    finding = next(f for f in report.findings if f.check == "crs.missing")
    assert finding.severity == "warning"


def test_crs_mismatch(clean_layer, rules):
    rules.crs = "EPSG:32637"
    report = validate(clean_layer, rules)
    assert "crs.mismatch" in codes(report)


def test_degrees_in_a_projected_crs(rules):
    layer = gpd.GeoDataFrame(
        {
            "plot_id": ["A1"],
            "status": ["approved"],
            "area_m2": [2500.0],
            "geometry": [square(34.9, 25.2, 0.01)],
        },
        crs=UTM36N,  # the label says metres, the numbers say degrees
    )
    report = validate(layer, rules)
    assert "crs.units_mismatch" in codes(report)


def test_outside_declared_bounds(clean_layer, rules):
    rules.coordinate_bounds = (0, 0, 1000, 1000)
    report = validate(clean_layer, rules)
    assert "crs.outside_study_area" in codes(report)


def test_empty_layer_is_flagged_but_not_fatal(rules):
    layer = gpd.GeoDataFrame(
        {"plot_id": [], "status": [], "area_m2": [], "geometry": []}, crs=UTM36N
    )
    report = validate(layer, rules)
    assert "layer.empty" in codes(report)
    assert report.passed


def test_geometryless_frame_raises(rules):
    import pandas as pd

    with pytest.raises(Exception):
        validate(pd.DataFrame({"plot_id": ["A1"]}), rules)
